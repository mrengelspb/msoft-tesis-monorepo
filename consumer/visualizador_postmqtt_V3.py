import sys
import json
import time
import numpy as np
import paho.mqtt.client as mqtt
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

"""
-----------------------------------------------------------------------------
SUBSYSTEM: CONSUMER / VISUALIZER (FRONTEND)
-----------------------------------------------------------------------------
Descripción:
Este script actúa como un cliente final de alta velocidad. Se suscribe al 
Broker MQTT para recibir el stream de datos ECG procesados por el backend 
(Docker) y los renderiza en tiempo real.

Tecnologías:
- PyQt5 / PyQtGraph: Para renderizado de gráficos de alto rendimiento (OpenGL).
- Numpy: Para manejo eficiente de buffers circulares de datos.
- Paho MQTT: Para la recepción de telemetría.
-----------------------------------------------------------------------------
"""

# OPTIMIZACIÓN GLOBAL DE GRÁFICOS
# Antialiasing: Suaviza los bordes de la línea para que no se vea "pixelada".
pg.setConfigOptions(antialias=True)

# OpenGL: Intentamos usar aceleración por hardware (GPU) si está disponible.
# Esto reduce drásticamente el uso de CPU al dibujar 30/60 cuadros por segundo.
try:
    pg.setConfigOption('useOpenGL', True)
except Exception as e:
    print(f"Advertencia: OpenGL no disponible ({e}). Usando renderizado software.")

# CONFIGURACIÓN MQTT
MQTT_BROKER = "localhost"
MQTT_TOPIC_DATA = "msoft/msrr/debug_ecg_data"  # Stream de onda (alto volumen)
MQTT_TOPIC_ZONE = "msoft/msrr/zone_change"     # Eventos (bajo volumen)
MQTT_TOPIC_STATUS = "msoft/msrr/status"        # Heartbeat (bajo volumen)

class MqttVisualizer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        
        # --- CONFIGURACIÓN DE BUFFER CIRCULAR ---
        # Definimos la ventana de tiempo visual. 
        # Cálculo: 5 segundos * 250 Hz (tasa de muestreo) = 1250 puntos.
        self.max_points = 1250 
        
        # Usamos numpy.zeros para pre-reservar memoria contigua.
        # Es mucho más rápido que usar listas de Python (append/pop).
        self.data_buffer = np.zeros(self.max_points)
        
        # Variables de estado del atleta
        self.bpm_val = 0.0
        self.zone_val = 0
        self.msg_log = "Conectando..."
        
        # DIAGNÓSTICO DE STREAM 
        # Contadores para calcular la tasa real de llegada de paquetes (Hz reales)
        self.received_points_counter = 0
        self.lbl_stats_text = "Esperando datos..."

        # Inicialización de componentes
        self.init_ui()
        self.init_mqtt()

    def init_ui(self):
        """ Configuración de la Interfaz Gráfica (GUI) """
        self.setWindowTitle('Visualizador ECG Remoto (M-Soft Mateo Rengel)')
        self.resize(1200, 600)
        
        # Tema Oscuro 
        self.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc;")
        
        # Layout Principal
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # HEADER DE INFORMACIÓN 
        header = QtWidgets.QHBoxLayout()
        
        # Definición de Estilos CSS para las etiquetas
        style_bpm = "font-size: 24pt; font-weight: bold; color: #00FF00;" # Verde
        style_zone = "font-size: 24pt; font-weight: bold; color: #00AAFF;" # Azul
        style_info = "font-size: 10pt; color: #888;"

        # Widgets de texto
        self.lbl_bpm = QtWidgets.QLabel("BPM: --")
        self.lbl_bpm.setStyleSheet(style_bpm)
        
        self.lbl_zone = QtWidgets.QLabel("ZONA: --")
        self.lbl_zone.setStyleSheet(style_zone)
        
        self.lbl_stats = QtWidgets.QLabel("Stream: 0 Hz")
        self.lbl_stats.setStyleSheet(style_info)
        
        # Barra de estado inferior (Logs)
        self.lbl_log = QtWidgets.QLabel("Inicializando sistema...")
        self.lbl_log.setStyleSheet("color: #aaa; font-style: italic;")
        
        # Armado del Header
        header.addWidget(self.lbl_bpm)
        header.addSpacing(40)
        header.addWidget(self.lbl_zone)
        header.addStretch() # Empuja las estadísticas a la derecha
        header.addWidget(self.lbl_stats)
        
        layout.addLayout(header)
        layout.addWidget(self.lbl_log)

        #  ÁREA DE GRÁFICO (PYQTGRAPH) 
        self.win = pg.GraphicsLayoutWidget()
        self.win.setBackground('#000000') # Fondo negro 
        layout.addWidget(self.win)
        
        self.plot = self.win.addPlot()
        
        # CONFIGURACIÓN DE EJES Y RANGO
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel('bottom', 'Ventana de Tiempo (Últimos 5s)')
        self.plot.setLabel('left', 'Amplitud')
        
        # Auto-Rango (Ideal para pruebas, se adapta a la señal)
        #self.plot.enableAutoRange(axis='y')
        
        # Rango Fijo (Ideal para demo final estable, descomentar si necesario)
        self.plot.setYRange(-300, 300) 
        
        #  CURVA Y EFECTOS 
        # 'skipFiniteCheck=True' mejora rendimiento al no verificar NaNs en cada cuadro.
        self.curve = self.plot.plot(pen=pg.mkPen('#00FF00', width=2), skipFiniteCheck=True)
        
        # EFECTO GLOW (OSCILOSCOPIO): Agrega una sombra translúcida para realismo.
        self.curve.setShadowPen(pg.mkPen((0, 255, 0, 90), width=6))

        # TIMERS 
        # Timer de Renderizado (UI Update): 33ms ~= 30 FPS
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(33) 

        # Timer de Diagnóstico (Stats): Cada 1 segundo
        self.stats_timer = QtCore.QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(1000)

    def init_mqtt(self):
        """ Inicialización del cliente MQTT en hilo separado """
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        try:
            self.client.connect(MQTT_BROKER, 1883, 60)
            self.client.loop_start() # Inicia el loop en background
        except Exception as e:
            self.lbl_log.setText(f"Error Fatal MQTT: {e}")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.lbl_log.setText("✅ Conectado a MQTT. Suscribiendo...")
            # QoS 0 para datos rápidos (si se pierde un paquete ECG, no importa)
            client.subscribe(MQTT_TOPIC_DATA, qos=0)
            client.subscribe(MQTT_TOPIC_STATUS, qos=0)
            # QoS 1 para eventos (asegura datos que lleguen al menos una vez)
            client.subscribe(MQTT_TOPIC_ZONE, qos=1)

    def on_message(self, client, userdata, msg):
        """ Manejo de mensajes entrantes (Se ejecuta en hilo de red) """
        try:
            # Decodificamos el JSON
            payload = json.loads(msg.payload.decode())
            
            # CASO 1: Paquete de Datos ECG (Stream)
            if msg.topic == MQTT_TOPIC_DATA:
                chunk = payload.get("ecg_data", [])
                n_new = len(chunk)
                
                if n_new > 0:
                    # LÓGICA DE BUFFER CIRCULAR (NUMPY ROLL)
                    # 1. Desplazamos todo el array hacia la izquierda (-n_new posiciones)
                    #    Los datos más viejos al principio del array "dan la vuelta" al final.
                    self.data_buffer = np.roll(self.data_buffer, -n_new)
                    
                    # 2. Sobrescribimos el final del array con los datos nuevos.
                    #    Así eliminamos los datos viejos que dieron la vuelta.
                    self.data_buffer[-n_new:] = chunk
                    
                    # Contamos puntos para estadística
                    self.received_points_counter += n_new
                
            # CASO 2: Estado (Heartbeat)
            elif msg.topic == MQTT_TOPIC_STATUS:
                self.bpm_val = payload.get("bpm", 0)
                self.zone_val = payload.get("zone", 0)
                
            # CASO 3: Evento Crítico
            elif msg.topic == MQTT_TOPIC_ZONE:
                old = payload.get("zona_anterior")
                new = payload.get("zona_nueva")
                self.msg_log = f"CAMBIO DE ZONA DETECTADO: {old} -> {new}"

        except Exception as e:
            print(f"Error procesando mensaje MQTT: {e}")

    def update_stats(self):
        """ Calcula calidad de señal (Hz) cada segundo """
        hz = self.received_points_counter
        self.lbl_stats.setText(f"Calidad Stream: {hz} pts/seg")
        
        # Código de colores para diagnóstico rápido
        if hz < 50:
             self.lbl_stats.setStyleSheet("font-size: 10pt; color: #FF0000;") # Rojo (Mala señal)
        elif hz < 200:
             self.lbl_stats.setStyleSheet("font-size: 10pt; color: #FFFF00;") # Amarillo (Warning)
        else:
             self.lbl_stats.setStyleSheet("font-size: 10pt; color: #00FF00;") # Verde (Óptimo)
             
        self.received_points_counter = 0

    def update_plot(self):
        """ Actualización del Canvas (Se ejecuta en el hilo principal de UI) """
        # Seteamos la curva con el buffer numpy actual
        self.curve.setData(self.data_buffer)
        
        # Actualizamos etiquetas de texto
        self.lbl_bpm.setText(f"BPM: {self.bpm_val:.1f}")
        self.lbl_zone.setText(f"ZONA: {self.zone_val}")
        self.lbl_log.setText(self.msg_log)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viz = MqttVisualizer()
    viz.show()
    sys.exit(app.exec())