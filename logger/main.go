package main

import (
	"log/slog"
	"os"
)

func main() {
	// Configura un logger JSON que escriba en la salida estándar (stdout)
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	// Simulación de un evento recibido de MQTT
	eventoPython := `{"user_id": 123, "action": "login", "status": "success"}`

	// En tu servicio real, decodificarías el JSON,
	// pero aquí solo lo añadimos como un atributo.
	// O, mejor aún, registras los campos clave:

	logger.Info(
		"Evento MQTT recibido",                   // Mensaje principal
		slog.String("servicio_origen", "python"), // Contexto
		slog.String("topico_mqtt", "eventos/login"),
		slog.Int("user_id", 123),
		slog.String("action", "login"),
	)
}
