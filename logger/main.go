package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	mqtt "github.com/eclipse/paho.mqtt.golang"
	// Importamos el driver de postgres
	// El guion bajo _ significa que solo necesitamos sus
	// efectos secundarios (registrar el driver "postgres")
	_ "github.com/lib/pq"
)

// Define la estructura del mensaje que esperamos recibir
type ZoneChangePayload struct {
	UserID       string  `json:"user_id"`
	ZonaAnterior int     `json:"zona_anterior"`
	ZonaNueva    int     `json:"zona_nueva"`
	BpmActual    float64 `json:"bpm_actual"`
	Timestamp    float64 `json:"timestamp"` // Dejamos que la BD maneje su propio timestamp
}

// ---- Variables Globales ----
// Hacemos que la conexión a la BD y el logger
// sean globales para que el 'messageHandler' pueda usarlos.
var db *sql.DB
var logger *slog.Logger

// connectDB se conecta a la base de datos Postgres usando
// las variables de entorno que nos pasa Docker Compose.
func connectDB() (*sql.DB, error) {
	// Leemos las variables de entorno
	host := os.Getenv("DB_HOST")
	port := os.Getenv("DB_PORT")
	user := os.Getenv("DB_USER")
	password := os.Getenv("DB_PASSWORD")
	dbname := os.Getenv("DB_NAME")

	// Creamos la cadena de conexión (DSN)
	// Esta es la forma estándar de 'postgres://...'
	psqlInfo := fmt.Sprintf("postgres://%s:%s@%s:%s/%s?sslmode=disable",
		user, password, host, port, dbname)

	// Abrimos la conexión
	db, err := sql.Open("postgres", psqlInfo)
	if err != nil {
		return nil, err
	}

	// Verificamos que la conexión sea válida
	err = db.Ping()
	if err != nil {
		return nil, err
	}

	logger.Info("¡Conectado exitosamente a la base de datos Postgres!")
	return db, nil
}

// messageHandler se ejecuta CADA VEZ que llega un mensaje MQTT
var messageHandler mqtt.MessageHandler = func(client mqtt.Client, msg mqtt.Message) {

	// 1. Decodificar el payload JSON
	var payload ZoneChangePayload
	err := json.Unmarshal(msg.Payload(), &payload)

	if err != nil {
		logger.Error(
			"Error al decodificar JSON de MQTT",
			slog.String("topico", msg.Topic()),
			slog.String("payload_crudo", string(msg.Payload())),
			slog.String("error", err.Error()),
		)
		return
	}

	// 2. Definir el SQL para insertar en la tabla
	sqlStatement := `
	INSERT INTO zone_change_events 
	  (message, service_origin, mqtt_topic, user_id, zone_previous, zone_new, bpm)
	VALUES ($1, $2, $3, $4, $5, $6, $7)`

	// 3. Ejecutar el SQL
	_, err = db.Exec(sqlStatement,
		"Cambio de Zona Registrado", // message
		"analyzer_service",          // service_origin
		msg.Topic(),                 // mqtt_topic
		payload.UserID,              // user_id
		payload.ZonaAnterior,        // zone_previous
		payload.ZonaNueva,           // zone_new
		payload.BpmActual,           // bpm
	)

	if err != nil {
		logger.Error(
			"Error al insertar en la base de datos",
			slog.String("error", err.Error()),
		)
		return
	}

	// ¡Éxito!
	logger.Info(
		"Evento almacenado en la BD",
		slog.String("user_id", payload.UserID),
		slog.Int("zona_nueva", payload.ZonaNueva),
	)
}

func main() {
	// Configuramos nuestro logger JSON
	logger = slog.New(slog.NewJSONHandler(os.Stdout, nil))

	// 1. Conectar a la Base de Datos
	var err error // Declaramos err aquí para poder reusarla
	db, err = connectDB()
	if err != nil {
		logger.Error("Fallo crítico al conectar a la BD", slog.String("error", err.Error()))
		os.Exit(1) // Salir si no nos podemos conectar
	}
	// Nos aseguramos de cerrar la conexión al salir
	defer db.Close()

	// 2. Conectar a MQTT
	// Leemos las variables de entorno de MQTT
	mqttHost := os.Getenv("MQTT_HOST")
	mqttPort := os.Getenv("MQTT_PORT")
	mqttBroker := fmt.Sprintf("tcp://%s:%s", mqttHost, mqttPort)

	opts := mqtt.NewClientOptions()
	opts.AddBroker(mqttBroker)
	opts.SetClientID("go_logger_service_db")
	opts.SetAutoReconnect(true)
	opts.SetConnectRetry(true)

	// Callback que se llama cuando nos conectamos
	opts.OnConnect = func(c mqtt.Client) {
		logger.Info("Logger conectado a MQTT. Suscribiendo...")
		// Nos suscribimos al tópico
		// AHORA usará nuestro 'messageHandler' global
		if token := c.Subscribe("msoft/msrr/zone_change", 1, messageHandler); token.Wait() && token.Error() != nil {
			logger.Error("Error al suscribir", slog.String("error", token.Error().Error()))
			os.Exit(1)
		}
		logger.Info("Suscripción exitosa. Esperando mensajes...")
	}
	opts.OnConnectionLost = func(c mqtt.Client, err error) {
		logger.Warn("Conexión MQTT perdida", slog.String("error", err.Error()))
	}

	// Conectar al cliente
	client := mqtt.NewClient(opts)
	if token := client.Connect(); token.Wait() && token.Error() != nil {
		logger.Error("No se pudo conectar a MQTT", slog.String("error", token.Error().Error()))
		panic(token.Error())
	}

	logger.Info("Servicio de Logger iniciado (Modo DB).")

	// 3. Esperar una señal para terminar limpiamente
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig

	logger.Info("Apagando servicio de logger...")
	client.Disconnect(250)
	logger.Info("Desconectado de MQTT.")
}
