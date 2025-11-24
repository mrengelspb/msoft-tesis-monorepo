import sys
import json
import time
import numpy as np
import paho.mqtt.client as mqtt
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

# --- 1. OPTIMIZACIÓN GLOBAL DE GRÁFICOS ---
# Activa el suavizado de líneas (Anti-aliasing)
pg.setConfigOptions(antialias=True)
# Usa OpenGL para acelerar si la tarjeta gráfica lo permite
try:
    pg.setConfigOption('useOpenGL', True)
except:
    pass

MQTT_BROKER = "localhost"
MQTT_TOPIC_DATA = "msoft/msrr/debug_ecg_data"
MQTT_TOPIC_ZONE = "msoft/msrr/zone_change"
MQTT_TOPIC_STATUS = "msoft/msrr/status"

class MqttVisualizer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        
        # --- CONFIGURACIÓN DE BUFFER ---
        # 5 segundos a 250Hz = 1250 puntos. 
        self.max_points = 1250 
        # Usamos numpy array pre-reservado para mayor velocidad que deque
        self.data_buffer = np.zeros(self.max_points)
        self.ptr = 0 # Puntero para inserción circular (opcional, aquí usaremos roll)
        
        # Variables de estado
        self.bpm_val = 0.0
        self.zone_val = 0
        self.msg_log = "Conectando..."
        
        # Diagnóstico de recepción
        self.received_points_counter = 0
        self.last_time_check = time.time()
        self.real_fps = 0

        self.init_ui()
        self.init_mqtt()

    def init_ui(self):
        self.setWindowTitle('Visualizador ECG Remoto (High Res)')
        self.resize(1200, 600)
        
        # Estilo oscuro profesional
        self.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc;")
        
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # Header Info
        header = QtWidgets.QHBoxLayout()
        
        # Estilos CSS
        style_bpm = "font-size: 24pt; font-weight: bold; color: #00FF00;"
        style_zone = "font-size: 24pt; font-weight: bold; color: #00AAFF;"
        style_info = "font-size: 10pt; color: #888;"

        self.lbl_bpm = QtWidgets.QLabel("BPM: --")
        self.lbl_bpm.setStyleSheet(style_bpm)
        
        self.lbl_zone = QtWidgets.QLabel("ZONA: --")
        self.lbl_zone.setStyleSheet(style_zone)
        
        # Etiqueta para ver la calidad de la señal (Hz recibidos)
        self.lbl_stats = QtWidgets.QLabel("Stream: 0 Hz")
        self.lbl_stats.setStyleSheet(style_info)
        
        self.lbl_log = QtWidgets.QLabel("Inicializando...")
        self.lbl_log.setStyleSheet("color: #aaa; font-style: italic;")
        
        header.addWidget(self.lbl_bpm)
        header.addSpacing(40)
        header.addWidget(self.lbl_zone)
        header.addStretch()
        header.addWidget(self.lbl_stats)
        
        layout.addLayout(header)
        layout.addWidget(self.lbl_log)

        # Plot Widget
        self.win = pg.GraphicsLayoutWidget()
        self.win.setBackground('#000000') # Fondo negro puro para contraste
        layout.addWidget(self.win)
        
        self.plot = self.win.addPlot()
        self.plot.setYRange(-300, 300) # Rango fijo
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel('bottom', 'Muestras (Últimos 5s)')
        
        # --- MEJORA DE LA CURVA ---
        # width=2 para que se vea más sólida. skipFiniteCheck aumenta rendimiento.
        self.curve = self.plot.plot(pen=pg.mkPen('#00FF00', width=2), skipFiniteCheck=True)

        # Timer de Refresco (30 FPS = ~33ms)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(33) 

        # Timer de Diagnóstico (Cada 1 segundo)
        self.stats_timer = QtCore.QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(1000)

    def init_mqtt(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        try:
            self.client.connect(MQTT_BROKER, 1883, 60)
            self.client.loop_start()
        except Exception as e:
            self.lbl_log.setText(f"Error MQTT: {e}")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.lbl_log.setText("Conectado a MQTT Local")
            client.subscribe(MQTT_TOPIC_DATA, qos=0)
            client.subscribe(MQTT_TOPIC_STATUS, qos=0)
            client.subscribe(MQTT_TOPIC_ZONE, qos=1)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            if msg.topic == MQTT_TOPIC_DATA:
                chunk = payload.get("ecg_data", [])
                n_new = len(chunk)
                
                if n_new > 0:
                    # Técnica "Numpy Roll" (Más rápida que extend para gráficos)
                    # 1. Desplazamos el array a la izquierda
                    self.data_buffer = np.roll(self.data_buffer, -n_new)
                    # 2. Insertamos los nuevos datos al final
                    self.data_buffer[-n_new:] = chunk
                    
                    # Contador para diagnóstico
                    self.received_points_counter += n_new
                
            elif msg.topic == MQTT_TOPIC_STATUS:
                self.bpm_val = payload.get("bpm", 0)
                self.zone_val = payload.get("zone", 0)
                
            elif msg.topic == MQTT_TOPIC_ZONE:
                old = payload.get("zona_anterior")
                new = payload.get("zona_nueva")
                self.msg_log = f"CAMBIO DE ZONA: {old} -> {new}"

        except Exception as e:
            print(f"Error parsing: {e}")

    def update_stats(self):
        """ Calcula cuántos puntos por segundo están llegando realmente """
        # Debería ser cercano a 250 Hz (según tu BrainFlow config)
        hz = self.received_points_counter
        self.lbl_stats.setText(f"Calidad Stream: {hz} puntos/seg")
        
        if hz < 50:
             self.lbl_stats.setStyleSheet("font-size: 10pt; color: #FF0000;") # Rojo si es muy bajo
        elif hz < 200:
             self.lbl_stats.setStyleSheet("font-size: 10pt; color: #FFFF00;") # Amarillo
        else:
             self.lbl_stats.setStyleSheet("font-size: 10pt; color: #00FF00;") # Verde
             
        self.received_points_counter = 0

    def update_plot(self):
        # Actualizamos la curva con el buffer numpy
        self.curve.setData(self.data_buffer)
        
        # Textos
        self.lbl_bpm.setText(f"BPM: {self.bpm_val:.1f}")
        self.lbl_zone.setText(f"ZONA: {self.zone_val}")
        self.lbl_log.setText(self.msg_log)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viz = MqttVisualizer()
    viz.show()
    sys.exit(app.exec())