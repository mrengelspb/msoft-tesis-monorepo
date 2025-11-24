import paho.mqtt.client as mqtt
import json
import time
import logging

class MQTTPublisher:
    def __init__(self, broker_host="mqtt-broker", broker_port=1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic_zone = "msoft/msrr/zone_change" # Topic donde publicaré cambios de estado importantes
        self.topic_ecg_data = "msoft/msrr/debug_ecg_data" # Topic donde enviaré el stream de datos
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.connect()

    def connect(self):
        try:
            logging.info(f"Intento conectarme al broker MQTT en {self.broker_host}...")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start() # Inicio el hilo en segundo plano para gestionar la red
            logging.info("Conectado exitosamente a MQTT.")
        except Exception as e:
            logging.error(f"No se puede conectar a MQTT: {e}")
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
            # Publico con QoS 1 para asegurar que el cambio de zona llegue al menos una vez
            self.client.publish(self.topic_zone, json.dumps(payload), qos=1)
            logging.info(f"He publicado el cambio de zona en {self.topic_zone}: {zona_nueva}")
        except Exception as e:
            logging.error(f"Tuve un error publicando en MQTT: {e}")

    def publish_ecg_data(self, data):
        """ Publico datos del ECG para el visualizador """
        if not self.client:
            return
        
        try:
            # Serializo los datos a una lista
            payload = {"ecg_data": data.tolist()} 
            # Publico con QoS 0 porque es un stream continuo y prefiero velocidad antes que confirmación
            self.client.publish(self.topic_ecg_data, json.dumps(payload), qos=0)
        except Exception as e:
            logging.warning(f"Error al intentar publicar datos ECG: {e}")

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logging.info("Desconectado de MQTT.")