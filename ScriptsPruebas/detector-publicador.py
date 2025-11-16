import logging
import sys
import numpy as np 
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, WindowOperations, DetrendOperations

import time
import json
import paho.mqtt.client as mqtt

class Graph(QtWidgets.QWidget): # Cambiado a QWidget para que 'self.win' sea el layout
    def __init__(self, board_shim, age=30):
        super().__init__() # Necesario para QWidget

        self.board_id = board_shim.get_board_id()
        self.board_shim = board_shim
        
        try:
            all_ecg_channels = BoardShim.get_ecg_channels(self.board_id)
            self.ecg_channels = all_ecg_channels[:2] 
            
            # --- DEBUG: PASO 5 ---
            print(f"DEBUG: Canales ECG detectados: {self.ecg_channels}")

            if len(self.ecg_channels) < 2:
                logging.error("Esta placa no tiene al menos 2 canales ECG. Saliendo.")
                return
        except Exception as e:
            logging.warning(f"No se pudieron obtener canales ECG: {e}")
            self.ecg_channels = [1, 2] # Fallback
            
            # --- DEBUG: PASO 5 ---
            print(f"DEBUG: Usando canales ECG de fallback: {self.ecg_channels}")

             
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.update_speed_ms = 50
        self.num_points = 1024 # ¡Usamos una potencia de 2!
        self.window_size = self.num_points / self.sampling_rate # (Será 4.096)

        
        # --- Variables de Lógica de Tesis ---
        self.bpm = 0.0
        self.hr_psd_size = DataFilter.get_nearest_power_of_two(self.sampling_rate)
        self.printed_data = False
        self.age = age # Edad para los cálculos de zona
        self.current_zone = 0 # Zona detectada actual (0 = reposo)
        
        # --- Configuración MQTT (Objetivo 3) ---
        self.mqtt_topic = "msoft/msrr/zone_change"
        #self.mqtt_client = mqtt.Client()
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        try:
            # Usamos un broker público para pruebas
            #self.mqtt_client.connect("broker.hivemq.com", 1883, 60)
            self.mqtt_client.connect("localhost", 1883, 60)# Para mosquito LOCAL
            self.mqtt_client.loop_start() # Inicia el cliente en un hilo separado
            print("Conectado al broker MQTT")
        except Exception as e:
            print(f"No se pudo conectar a MQTT: {e}")
            self.mqtt_client = None

        # --- Configuración de la GUI ---
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.setWindowTitle('Monitor ECG (Tesis)')
        self.setGeometry(100, 100, 1000, 450)
        
        # 'win' es ahora el layout principal de este QWidget
        self.win = pg.GraphicsLayoutWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.win)
        self.setLayout(layout)

        self._init_pens()
        self._init_timeseries()

        # Timer para actualizar la GUI y los cálculos
        self.timer = QtCore.QTimer() # <--- El timer DEBE ser un atributo de 'self'
        self.timer.timeout.connect(self.update)
        self.timer.start(self.update_speed_ms)
        # --- Variables para ralentizar el cálculo de BPM ---
        self.bpm_update_ticks = 20 # 20 ticks * 50ms = 1000ms (1 segundo)
        self.bpm_update_counter = 0

        self.show() # Muestra la ventana


    def _init_pens(self):
        self.pens = list()
        self.brushes = list()
        colors = ['#A54E4E', '#A473B6', '#5B45A4'] 
        for i in range(len(colors)):
            pen = pg.mkPen({'color': colors[i], 'width': 2})
            self.pens.append(pen)
            brush = pg.mkBrush(colors[i])
            self.brushes.append(brush)

    def _init_timeseries(self):
        self.plots = list()
        self.curves = list()
        
        self.time_axis = np.linspace(0, self.window_size, self.num_points, endpoint=False)
        
        for i in range(len(self.ecg_channels)):
            p = self.win.addPlot(row=i, col=0)
            p.showAxis('left', True)
            p.setLabel('left', 'Amplitud (mV)')
            p.showAxis('bottom', True)
            p.setLabel('bottom', 'Tiempo (s)')
            p.setYRange(-2.0, 2.0) # Aumentamos el rango por si acaso
            
            if i == 0:
                p.setTitle(f'ECG Canal {self.ecg_channels[i]}  |  BPM: Calculando...')
            else:
                p.setTitle(f'ECG Canal {self.ecg_channels[i]}')
            
            self.plots.append(p)
            curve = p.plot(pen=self.pens[i % len(self.pens)])
            self.curves.append(curve)

    
    # --- Objetivo 2: Algoritmo de Detección ---
    def detect_zone_change(self, bpm):
        max_hr = 220 - self.age
        
        # Lógica de Umbrales (Karvonen)
        if bpm < (max_hr * 0.6):
            new_zone = 1
        elif bpm < (max_hr * 0.7):
            new_zone = 2
        elif bpm < (max_hr * 0.8):
            new_zone = 3
        elif bpm < (max_hr * 0.9):
            new_zone = 4
        else:
            new_zone = 5

        # Lógica de Detección de Evento
        if new_zone != self.current_zone:
            print(f"¡CAMBIO DE ZONA DETECTADO! De {self.current_zone} a {new_zone} (BPM: {bpm:.2f})")
            
            # --- Objetivo 3: Publicar en MQTT ---
            if self.mqtt_client:
                payload = {
                    "user_id": "atleta_01",
                    "zona_anterior": self.current_zone,
                    "zona_nueva": new_zone,
                    "bpm_actual": round(bpm, 2),
                    "timestamp": time.time()
                }
                # Convertir a JSON y publicar
                self.mqtt_client.publish(self.mqtt_topic, json.dumps(payload))
                print(f"Evento publicado en MQTT: {self.mqtt_topic}")
            
            self.current_zone = new_zone # Actualizamos el estado


    def update(self):
        self.bpm_update_counter += 1
        
        data = self.board_shim.get_current_board_data(self.num_points)
        # --- DEBUG: PASO 2 ---
        if data.shape[1] == 0:
            print("  > WARNING: No data returned from board.")
            return
        

        for count, channel in enumerate(self.ecg_channels):
            if data.shape[1] < self.num_points:
                print(f"  > SKIPPING loop: Data shape ({data.shape[1]}) is less than required ({self.num_points})")
                continue
 

            ecg_data = np.copy(data[channel]) 
            
            DataFilter.detrend(ecg_data, DetrendOperations.CONSTANT.value)
            DataFilter.perform_bandpass(ecg_data, self.sampling_rate, 1.0, 40.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            DataFilter.perform_bandstop(ecg_data, self.sampling_rate, 48.0, 52.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            DataFilter.perform_bandstop(ecg_data, self.sampling_rate, 58.0, 62.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

            if count == 0:
                if self.bpm_update_counter >= self.bpm_update_ticks:
                    self.bpm_update_counter = 0 # Reiniciar el contador
                    try:
                      
                        nperseg = len(ecg_data) # (esto será 1024)
                        noverlap = nperseg // 2 # (esto será 512) // Saltos a 14 BPM aprox
                        
                        psd_data = DataFilter.get_psd_welch(
                            ecg_data, nperseg, noverlap, 
                            self.sampling_rate, WindowOperations.BLACKMAN_HARRIS.value
                        )

                        psd_amps = psd_data[0]
                        psd_freqs = psd_data[1]

                        min_hr_hz = 0.8 # 48 BPM
                        max_hr_hz = 4.0 # 240 BPM
                        min_hr_idx = np.where(psd_freqs > min_hr_hz)[0][0]
                        max_hr_idx = np.where(psd_freqs > max_hr_hz)[0][0]

                        peak_idx_in_band = np.argmax(psd_amps[min_hr_idx:max_hr_idx])
                        peak_idx_total = min_hr_idx + peak_idx_in_band
                        peak_freq_hz = psd_freqs[peak_idx_total]

                        self.bpm = peak_freq_hz * 60.0
                        
                        # --- LLAMADA AL DETECTOR ---
                        self.detect_zone_change(self.bpm) # (Solo detectamos cambios cuando recalculamos)
                        
                    except Exception as e:
                        logging.warning(f"No se pudo calcular BPM: {e}")
                        pass 
                # --- MOVIDO: Actualiza el título SIEMPRE (cada 50ms) ---
                # (Usa el último valor guardado en self.bpm)
                self.plots[0].setTitle(f'ECG Canal {self.ecg_channels[0]}  |  BPM: {self.bpm:.2f}  |  Zona Detectada: {self.current_zone}')

            data_mv = ecg_data / 1000.0
            self.curves[count].setData(x=self.time_axis, y=data_mv)

        # No imprimas datos en cada update, es muy lento
        # self.app.processEvents() # No es necesario si la GUI maneja su propio bucle


def main():
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.DEBUG)

    params = BrainFlowInputParams() 
    board_id = BoardIds.SYNTHETIC_BOARD.value
    board_shim = BoardShim(board_id, params)
    
    try:
        board_shim.prepare_session()

        # --- CONFIGURACIÓN INICIAL DEL SIMULADOR ---
        test_age = 30 # La edad para la simulación
        board_shim.config_board(f"AGE:{test_age}")

        board_shim.start_stream() 

        # --- INICIO DE LA APLICACIÓN Y GUI ---
        # 1. Crear la aplicación
        app = QtWidgets.QApplication(sys.argv)
        
        # 2. Crear la ventana (le pasamos la edad)
        graph_window = Graph(board_shim, test_age) 

        # 3. --- CONTROLADOR DE ESCENARIO (Objetivo 1) ---
        # Usamos un QTimer para que no bloquee la GUI
        scenario_timer = QtCore.QTimer()
        
        # Guardamos el estado en un dict para que sea mutable
        scenario_state = {'zone': 0} 

        def run_scenario_step():
            # Esta función se ejecutará cada 15 segundos
            # Cicla de 1 -> 2 -> 3 -> 4 -> 5 -> 1 ...
            scenario_state['zone'] = (scenario_state['zone'] % 5) + 1
            zone_to_set = scenario_state['zone']
            
            print(f"\n--- SIMULADOR: Enviando comando ZONE:{zone_to_set} ---\n")
            board_shim.config_board(f"ZONE:{zone_to_set}")

        scenario_timer.timeout.connect(run_scenario_step)
        scenario_timer.start(15000) # 15000 ms = 15 segundos
        run_scenario_step() # Ejecuta el primer paso (Zona 1) inmediatamente

        # 4. Ejecutar el bucle principal de la aplicación
        sys.exit(app.exec()) # Inicia la GUI
    except KeyboardInterrupt:
        print("Cerrando...")
    except BaseException as e:
        logging.warning('Exception', exc_info=True)
    finally:
        if board_shim.is_prepared():
            logging.info('Releasing session')
            board_shim.release_session()
            if graph_window and graph_window.mqtt_client:
                graph_window.mqtt_client.loop_stop() # Detiene el cliente MQTT


if __name__ == '__main__':
    main()