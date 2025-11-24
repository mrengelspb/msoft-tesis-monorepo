import paho.mqtt.client as mqtt
import json
import time
import logging

"""
-----------------------------------------------------------------------------
SUBSYSTEM: MQTT COMMUNICATION HANDLER
-----------------------------------------------------------------------------
Descripción:
Esta clase encapsula toda la lógica de conectividad con el Broker MQTT.
Actúa como una fachada (Facade Pattern) para que el núcleo del servicio
pueda enviar datos sin preocuparse por los detalles del protocolo de red.

Características:
- Gestión de Hilos: Ejecuta el cliente MQTT en un hilo de fondo (loop_start)
  para no bloquear el bucle principal de análisis matemático.
- QoS Diferenciado: Utiliza diferentes niveles de garantía de entrega según
  la criticidad del dato (Eventos vs Streaming).
-----------------------------------------------------------------------------
"""

class MQTTPublisher:
    def __init__(self, broker_host="mqtt-broker", broker_port=1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        # DEFINICIÓN DE TÓPICOS 
        # Estructura jerárquica: msoft/{usuario}/{tipo_de_dato}
        self.topic_zone = "msoft/msrr/zone_change"     # Eventos Críticos
        self.topic_ecg_data = "msoft/msrr/debug_ecg_data"  # Stream de Onda (Debug/Vis)
        self.topic_status = "msoft/msrr/status"        # Telemetría de Estado
        
        # Inicializamos cliente con la API V2 (Estándar actual de Paho)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.connect()

    def connect(self):
        """ Establece la conexión y arranca el hilo de red """
        try:
            logging.info(f"Conectando a MQTT en {self.broker_host}...")
            
            # Conexión bloqueante inicial (timeout 60s)
            self.client.connect(self.broker_host, self.broker_port, 60)
            
            # loop_start() crea un hilo secundario (Daemon Thread) que:
            # 1. Maneja la reconexión automática.
            # 2. Gestiona los PINGs (Keep-alive).
            # 3. Procesa mensajes entrantes/salientes.
            # Esto permite que el 'main.py' siga procesando ECG sin pausas.
            self.client.loop_start() 
            
            logging.info("Conexión MQTT establecida.")
        except Exception as e:
            logging.error(f"Error conexión MQTT: {e}")
            self.client = None

    def publish_zone_change(self, user_id, zona_anterior, zona_nueva, bpm_actual):
        """
        Publica un EVENTO DE CAMBIO DE ZONA.
        QoS: 1 (At Least Once) - El broker debe confirmar recepción.
        """
        if not self.client: return
        
        payload = {
            "user_id": user_id,
            "zona_anterior": zona_anterior,
            "zona_nueva": zona_nueva,
            "bpm_actual": round(bpm_actual, 2),
            "timestamp": time.time(),
            "type": "EVENT"
        }
        
        try:
            # QoS=1 asegura que el evento se guarde en la BD incluso si la red parpadea.
            self.client.publish(self.topic_zone, json.dumps(payload), qos=1)
            logging.info(f"Evento enviado: Zona {zona_nueva}")
        except Exception as e:
            logging.error(f"Error publicando evento: {e}")

    def publish_status(self, user_id, bpm_actual, current_zone):
        """
        Publica el ESTADO ACTUAL (Heartbeat).
        QoS: 0 (Fire and Forget).
        """
        if not self.client: return
        
        payload = {
            "user_id": user_id,
            "bpm": round(bpm_actual, 2),
            "zone": current_zone,
            "timestamp": time.time(),
            "type": "STATUS"
        }
        
        try:
            # QoS=0 es suficiente. Si se pierde un paquete, llegará otro en 50ms.
            self.client.publish(self.topic_status, json.dumps(payload), qos=0)
        except: pass 

    def publish_ecg_data(self, data):
        """
        Publica el STREAM DE ONDA RAW.
        QoS: 0.
        """
        if not self.client: return
        
        try:
            # 'data' es un array de Numpy. JSON estándar no soporta Numpy.
            # Debemos usar .tolist() para convertirlo a una lista nativa de Python.
            payload = {"ecg_data": data.tolist()} 
            
            self.client.publish(self.topic_ecg_data, json.dumps(payload), qos=0)
        except Exception as e:
            # En streaming de alta frecuencia, si falla un paquete, lo ignoramos (pass).
            # Loguear errores aquí saturaría la consola (IO Blocking).
            pass 

    def disconnect(self):
        """ Cierre limpio de recursos """
        if self.client:
            self.client.loop_stop() # Detiene el hilo de fondo
            self.client.disconnect()