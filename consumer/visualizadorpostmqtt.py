import sys
import json
import time
import numpy as np
import paho.mqtt.client as mqtt
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
from collections import deque

MQTT_BROKER = "localhost"
MQTT_TOPIC_DATA = "msoft/msrr/debug_ecg_data"
MQTT_TOPIC_ZONE = "msoft/msrr/zone_change"
MQTT_TOPIC_STATUS = "msoft/msrr/status"

class MqttVisualizer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        
        # Buffer visual de 5 segundos aprox
        self.max_points = 1250 
        self.data_buffer = deque(maxlen=self.max_points)
        # Rellenar con ceros para empezar limpio
        self.data_buffer.extend(np.zeros(self.max_points))
        
        self.bpm_val = 0.0
        self.zone_val = 0
        self.msg_log = "Conectando..."

        self.init_ui()
        self.init_mqtt()

    def init_ui(self):
        self.setWindowTitle('Visualizador ECG Remoto (Alta Velocidad)')
        self.resize(1200, 600)
        
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # Info Header
        header = QtWidgets.QHBoxLayout()
        self.lbl_bpm = QtWidgets.QLabel("BPM: --")
        self.lbl_bpm.setStyleSheet("font-size: 20pt; font-weight: bold; color: #222;")
        self.lbl_zone = QtWidgets.QLabel("ZONA: --")
        self.lbl_zone.setStyleSheet("font-size: 20pt; font-weight: bold; color: #0055AA;")
        self.lbl_log = QtWidgets.QLabel("...")
        self.lbl_log.setStyleSheet("color: #666;")
        
        header.addWidget(self.lbl_bpm)
        header.addSpacing(30)
        header.addWidget(self.lbl_zone)
        header.addStretch()
        header.addWidget(self.lbl_log)
        layout.addLayout(header)

        # Plot
        self.win = pg.GraphicsLayoutWidget()
        layout.addWidget(self.win)
        self.plot = self.win.addPlot()
        self.plot.setYRange(-200, 200) # Fijo para evitar saltos de auto-rango
        self.plot.showGrid(x=True, y=True)
        self.plot.setTitle("Señal ECG en Tiempo Real")
        self.curve = self.plot.plot(pen=pg.mkPen('#00CC00', width=2))

        # Timer rápido para animación fluida (30 FPS)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(33) 

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
            self.lbl_log.setText("Conectado. Esperando stream...")
            client.subscribe(MQTT_TOPIC_DATA, qos=0)
            client.subscribe(MQTT_TOPIC_STATUS, qos=0)
            client.subscribe(MQTT_TOPIC_ZONE, qos=1)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            if msg.topic == MQTT_TOPIC_DATA:
                # Llegan pequeños paquetes de datos (chunks)
                chunk = payload.get("ecg_data", [])
                print(f"Received chunk of {len(chunk)} points")
                print(chunk)
                self.data_buffer.extend(chunk)
                
            elif msg.topic == MQTT_TOPIC_STATUS:
                self.bpm_val = payload.get("bpm", 0)
                self.zone_val = payload.get("zone", 0)
                
            elif msg.topic == MQTT_TOPIC_ZONE:
                old = payload.get("zona_anterior")
                new = payload.get("zona_nueva")
                self.msg_log = f"Evento: Cambio Zona {old} -> {new}"

        except:
            pass

    def update_plot(self):
        # Actualizar UI en el hilo principal
        self.curve.setData(np.array(self.data_buffer))
        self.lbl_bpm.setText(f"BPM: {self.bpm_val:.1f}")
        self.lbl_zone.setText(f"ZONA: {self.zone_val}")
        self.lbl_log.setText(self.msg_log)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viz = MqttVisualizer()
    viz.show()
    sys.exit(app.exec())