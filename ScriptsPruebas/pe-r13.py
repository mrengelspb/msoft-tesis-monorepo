import paho.mqtt.client as mqtt
import time # Necesario para el timestamp
import json # Necesario para el payload de MQTT

class Graph:
    def __init__(self, board_shim):
        # ... (código existente de pyqtgraph) ...
        self.board_id = board_shim.get_board_id()
        # ...
        
        # <<< CAMBIO INICIO: Lógica de Detección y MQTT >>>
        self.age = 30 # Edad del sujeto de prueba (¡importante!)
        self.current_zone = 0 # El estado actual detectado
        
        # Configurar MQTT
        self.mqtt_topic = "tesis/hr/zone_change"
        self.mqtt_client = mqtt.Client()
        try:
            # Usamos un broker público para pruebas rápidas
            self.mqtt_client.connect("broker.hivemq.com", 1883, 60)
            self.mqtt_client.loop_start() # Inicia el cliente en un hilo separado
            print("Conectado al broker MQTT (broker.hivemq.com)")
        except Exception as e:
            print(f"No se pudo conectar a MQTT: {e}")
            self.mqtt_client = None
        # <<< CAMBIO FIN >>>

        # ... (código existente: self.app, self.win, timers, etc.) ...