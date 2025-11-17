import sys
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
import paho.mqtt.client as mqtt
import json
import logging
from collections import deque

# --- Configuración MQTT (Conexión Local) ---
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_ZONE = "msoft/msrr/zone_change"
TOPIC_DATA = "msoft/msrr/debug_ecg_data"

# Configura un logger básico para la GUI
logging.basicConfig(level=logging.INFO)

class MqttGraph(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        
        # --- Variables de Estado ---
        # Usamos 'deque' para almacenar los datos del gráfico
        self.num_points = 1024 
        self.plot_data = deque(np.zeros(self.num_points), maxlen=self.num_points)
        self.current_bpm = 0.0
        self.current_zone = 0
        self.time_axis = np.linspace(0, 4.0, self.num_points) # Asumimos 4s de ventana

        # --- Configuración de la GUI ---
        self.setup_gui()
        
        # --- Configuración MQTT ---
        self.mqtt_client = self.setup_mqtt()

        # --- Timer de la GUI ---
        # Este timer actualiza la GUI a 60fps (aprox 16ms)
        # NO realiza cálculos, solo dibuja lo que MQTT haya recibido
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(16) 
        self.show()

    def setup_gui(self):
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        self.setWindowTitle('Visualizador ECG (Local) - Suscrito a MQTT')
        self.setGeometry(100, 100, 1000, 450)
        
        self.win = pg.GraphicsLayoutWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.win)
        self.setLayout(layout)

        # Configurar el Plot
        self.plot = self.win.addPlot(row=0, col=0)
        self.plot.showAxis('left', True)
        self.plot.setLabel('left', 'Amplitud (mV)')
        self.plot.showAxis('bottom', True)
        self.plot.setLabel('bottom', 'Tiempo (s)')
        self.plot.setYRange(-2.0, 2.0)
        
        self.curve = self.plot.plot(pen=pg.mkPen({'color': '#A54E4E', 'width': 2}))
        self.update_title() # Pone el título inicial

    def update_title(self):
        self.plot.setTitle(f'ECG (Datos desde MQTT) | BPM: {self.current_bpm:.2f} | Zona: {self.current_zone}')

    def update_plot(self):
        """ Esta función solo dibuja los datos, no los procesa """
        # Convierte el 'deque' a un array numpy para pyqtgraph
        self.curve.setData(x=self.time_axis, y=np.array(self.plot_data))

    # --- Lógica de MQTT (Callbacks) ---

    def setup_mqtt(self):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = self.on_mqtt_connect
        client.on_message = self.on_mqtt_message
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_start()
            return client
        except Exception as e:
            logging.error(f"Error al conectar MQTT: {e}")
            return None

    def on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logging.info("GUI conectada a MQTT.")
            client.subscribe(TOPIC_ZONE)
            client.subscribe(TOPIC_DATA)
            logging.info(f"Suscrito a {TOPIC_ZONE} y {TOPIC_DATA}")
        else:
            logging.error(f"Error de conexión MQTT: {rc}")

    def on_mqtt_message(self, client, userdata, msg):
        """ 
        Este callback se ejecuta en el hilo de Paho-MQTT.
        Solo actualiza las variables de estado. 
        El QTimer se encargará de dibujarlas.
        """
        try:
            payload_str = msg.payload.decode('utf-8')
            data = json.loads(payload_str)
            
            if msg.topic == TOPIC_ZONE:
                # Actualizar estado de BPM y Zona
                self.current_bpm = data.get('bpm_actual', self.current_bpm)
                self.current_zone = data.get('zona_nueva', self.current_zone)
                # Actualiza el título inmediatamente (es seguro para QTimer)
                QtCore.QTimer.singleShot(0, self.update_title)
                
            elif msg.topic == TOPIC_DATA:
                # Actualizar datos del gráfico
                ecg_list = data.get('ecg_data', [])
                # Convertimos a mV (asumiendo que el servicio envía uV)
                ecg_mv = np.array(ecg_list) / 1000.0
                
                # Reemplazamos los datos del 'deque'
                # Esto es más eficiente que 'extend'
                self.plot_data = deque(ecg_mv, maxlen=self.num_points)

        except Exception as e:
            logging.warning(f"Error procesando mensaje MQTT: {e}")

    def closeEvent(self, event):
        """ Asegura que el cliente MQTT se detenga al cerrar la ventana """
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
        event.accept()

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MqttGraph()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()