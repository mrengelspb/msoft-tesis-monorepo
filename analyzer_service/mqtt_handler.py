
import paho.mqtt.client as mqtt
import json
import time
import logging

class MQTTPublisher:
    def __init__(self, broker_host="mqtt-broker", broker_port=1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic_zone = "msoft/msrr/zone_change" # Topic para envio de cambios de datos
        self.topic_ecg_data = "msoft/msrr/debug_ecg_data" # Topica para envio de datos crudos para la GUI de DEBUG
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.connect()

    def connect(self):
        try:
            logging.info(f"Conectando a MQTT broker en {self.broker_host}...")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start() # Inicia hilo en segundo plano
            logging.info("Conectado a MQTT.")
        except Exception as e:
            logging.error(f"No se pudo conectar a MQTT: {e}")
            self.client = None

    def publish_zone_change(self, user_id, zona_anterior, zona_nueva, bpm_actual):
        if not self.client:
            return

        payload = {
            "user_id": user_id,
            "zona_anterior": zona_anterior,
            "zona_nueva": zona_nueva,
            "bpm_actual": round(bpm_actual, 2),
            "timestamp": time.time()
        }
        try:
            self.client.publish(self.topic_zone, json.dumps(payload))
            logging.info(f"Publicado cambio de zona a {self.topic_zone}: {zona_nueva}")
        except Exception as e:
            logging.error(f"Error publicando en MQTT: {e}")

    def publish_ecg_data(self, data):
        """ Publica datos del ECG para el visualizador (TODO Analizar carga) """
        if not self.client:
            return
        
        try:
            # Serializa los datos 
            # Tomar en cuenta que se publica un array grande 
            payload = {"ecg_data": data.tolist()} 
            self.client.publish(self.topic_ecg_data, json.dumps(payload))
        except Exception as e:
            logging.warning(f"Error publicando datos ECG: {e}")

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logging.info("Desconectado de MQTT.")