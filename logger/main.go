package main

/*
 * -----------------------------------------------------------------------------
 * SERVICIO: MSOFT LOGGER (GOLANG)
 * -----------------------------------------------------------------------------
 * Descripción:
 * Este microservicio es dedicado a almacenar los cambios de zona y frecuencia cardíaca.
 * Escucha los cambios de evento y los almacena en una base de datos relacional (PostgreSQL).
 *
 * Arquitectura:
 * - Lenguaje: Go (Golang) versión 1.21+
 * - Patrón: Pub/Sub (Suscriptor)
 * - Driver DB: lib/pq (PostgreSQL)
 * - Cliente MQTT: Paho MQTT
 * -----------------------------------------------------------------------------
 */

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	mqtt "github.com/eclipse/paho.mqtt.golang"

	// Importamos el driver de postgres de forma anónima (con el guion bajo).
	// Esto ejecuta la función 'init()' del paquete, registrando el driver
	// para que el paquete standard "database/sql" pueda usarlo.
	_ "github.com/lib/pq"
)

// -----------------------------------------------------------------------------
// ESTRUCTURAS DE DATOS (MODELOS)
// -----------------------------------------------------------------------------

// ZoneChangePayload define la estructura exacta del JSON que envía el servicio de Python.
// Las etiquetas `json:"..."` permiten al decodificador mapear los campos automáticamente.
type ZoneChangePayload struct {
	UserID       string  `json:"user_id"`
	ZonaAnterior int     `json:"zona_anterior"`
	ZonaNueva    int     `json:"zona_nueva"`
	BpmActual    float64 `json:"bpm_actual"`
	Timestamp    float64 `json:"timestamp"` // Se usa float64 porque Python envía tiempo en UNIX
}

// -----------------------------------------------------------------------------
// VARIABLES GLOBALES Y CONFIGURACIÓN
// -----------------------------------------------------------------------------

// Variables globales para mantener simple la inyección de dependencias en este microservicio.
var (
	db     *sql.DB      // Pool de conexiones a la base de datos
	logger *slog.Logger // Logger estructurado (JSON) para observabilidad en Docker
)

// connectDB gestiona la conexión segura a PostgreSQL.
// Lee las credenciales desde variables de entorno inyectadas por Docker Compose.
func connectDB() (*sql.DB, error) {
	host := os.Getenv("DB_HOST")
	port := os.Getenv("DB_PORT")
	user := os.Getenv("DB_USER")
	password := os.Getenv("DB_PASSWORD")
	dbname := os.Getenv("DB_NAME")

	// Construcción del Data Source Name (DSN) estándar para Postgres
	psqlInfo := fmt.Sprintf("postgres://%s:%s@%s:%s/%s?sslmode=disable",
		user, password, host, port, dbname)

	// sql.Open valida los argumentos pero NO crea la conexión inmediatamente.
	dbConnection, err := sql.Open("postgres", psqlInfo)
	if err != nil {
		return nil, err
	}

	// db.Ping() fuerza una conexión real para verificar que la BD está viva y accesible.
	err = dbConnection.Ping()
	if err != nil {
		return nil, err
	}

	logger.Info("Conexión establecida con PostgreSQL", slog.String("host", host))
	return dbConnection, nil
}

// -----------------------------------------------------------------------------
// MANEJADOR MQTT)
// -----------------------------------------------------------------------------

// messageHandler es la función Callback que se ejecuta asíncronamente
// cada vez que el Broker MQTT entrega un mensaje al tópico suscrito.
var messageHandler mqtt.MessageHandler = func(client mqtt.Client, msg mqtt.Message) {

	// Decodificación: Convertimos los bytes del mensaje MQTT en nuestra estructura Go (ZoneChangePayload).
	var payload ZoneChangePayload
	err := json.Unmarshal(msg.Payload(), &payload)

	if err != nil {
		// Si el JSON está malformado, logueamos el error y el payload crudo para debug.
		logger.Error("Fallo al decodificar JSON",
			slog.String("topico", msg.Topic()),
			slog.String("payload_raw", string(msg.Payload())),
			slog.String("error", err.Error()),
		)
		return
	}

	// Persistencia (SQL) Se parametriza ($1, $2...) para prevenir Inyección SQL.
	sqlStatement := `
    INSERT INTO sch_msoft.tbl_zone_change_events 
      (message, service_origin, mqtt_topic, user_id, zone_previous, zone_new, bpm)
    VALUES ($1, $2, $3, $4, $5, $6, $7)`

	// Insertamos: No insertamos el timestamp de Python, dejamos que Postgres use su DEFAULT CURRENT_TIMESTAMP
	// para tener la hora exacta de persistencia.
	_, err = db.Exec(sqlStatement,
		"Cambio de Zona Detectado", // message (descripción)
		"analyzer_service",         // service_origin
		msg.Topic(),                // mqtt_topic
		payload.UserID,             // user_id
		payload.ZonaAnterior,       // zone_previous
		payload.ZonaNueva,          // zone_new
		payload.BpmActual,          // bpm
	)

	if err != nil {
		logger.Error("Fallo al insertar en DB", slog.String("error", err.Error()))
		return
	}

	// Paso C: Confirmación
	logger.Info("Evento persistido correctamente",
		slog.String("user", payload.UserID),
		slog.Int("zona_nueva", payload.ZonaNueva),
	)
}

// -----------------------------------------------------------------------------
// MAIN
// -----------------------------------------------------------------------------

func main() {
	// Inicializamos el Logger Estructurado (JSON Handler).
	logger = slog.New(slog.NewJSONHandler(os.Stdout, nil))

	// Inicializar Base de Datos
	var err error
	db, err = connectDB()
	if err != nil {
		logger.Error("Error Fatal: No se pudo conectar a la BD", slog.String("detalle", err.Error()))
		os.Exit(1) // Terminamos el contenedor si no hay BD, Docker lo reiniciará.
	}
	defer db.Close() // Aseguramos cerrar la conexión al terminar el programa.

	// Configuración Cliente MQTT
	mqttHost := os.Getenv("MQTT_HOST")
	mqttPort := os.Getenv("MQTT_PORT")
	brokerURL := fmt.Sprintf("tcp://%s:%s", mqttHost, mqttPort)

	opts := mqtt.NewClientOptions()
	opts.AddBroker(brokerURL)
	opts.SetClientID("go_logger_service_db")

	// Configuración de Resiliencia:
	// Si el contenedor de Mosquitto se cae, este servicio intentará reconectar infinitamente.
	opts.SetAutoReconnect(true)
	opts.SetConnectRetry(true)
	opts.SetConnectRetryInterval(5 * 1000000000) // 5 segundos (en nanosegundos)

	// OnConnect Callback:
	// Si la conexión se pierde y vuelve, 'OnConnect' se ejecuta de nuevo, restaurando la suscripción automáticamente.
	opts.OnConnect = func(c mqtt.Client) {
		logger.Info("Conectado a MQTT Broker. Suscribiendo a tópicos...")

		// QoS 1 (At least once): Asegura que el mensaje llegue al menos una vez.
		token := c.Subscribe("msoft/msrr/zone_change", 1, messageHandler)
		token.Wait()

		if token.Error() != nil {
			logger.Error("Error en suscripción", slog.String("err", token.Error().Error()))
		} else {
			logger.Info("Suscripción activa: msoft/msrr/zone_change")
		}
	}

	opts.OnConnectionLost = func(c mqtt.Client, err error) {
		logger.Warn("Conexión MQTT perdida. Reintentando...", slog.String("err", err.Error()))
	}

	// Iniciar Cliente MQTT
	client := mqtt.NewClient(opts)
	if token := client.Connect(); token.Wait() && token.Error() != nil {
		// Si falla la primera conexión, Docker reiniciará el servicio
		panic(token.Error())
	}

	logger.Info("Servicio Logger OPERATIVO. Esperando eventos...")

	// Bloqueo (Graceful Shutdown)
	// Creamos un canal para escuchar señales del sistema operativo (Ctrl+C o Docker Stop).
	// Esto evita que el programa termine inmediatamente.
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	// El programa se bloquea aquí esperando una señal.
	<-sig

	logger.Info("Apagando servicio...")
	client.Disconnect(250) // Desconexión limpia de MQTT (250ms timeout)
}
