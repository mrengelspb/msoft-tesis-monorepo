import sys
import time
import threading
import logging
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

# Importo mis clases de lógica 
from brainflow_handler import BrainflowHandler
from data_analysis import DataAnalyzer

# Configuro un log básico para ver qué pasa en la consola
logging.basicConfig(level=logging.INFO, format='%(asctime)s - LOCAL - %(message)s')

class LocalGuiTester(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        
        # --- Inicialización de Lógica ---
        # Instancio el manejador de BrainFlow igual que lo hará el servicio de Docker
        self.board = BrainflowHandler(num_points=1024)
        self.board.start(age=30) # Inicio la simulación para un atleta de 30 años

        # Instancio el analizador matemático
        self.analyzer = DataAnalyzer(sampling_rate=self.board.sampling_rate, age=30)

        # --- Configuración de la GUI ---
        self.setWindowTitle('Probador de Lógica Local (Sin Docker/MQTT)')
        self.resize(1000, 600)
        
        # Creo el layout para el gráfico
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.win = pg.GraphicsLayoutWidget()
        self.layout.addWidget(self.win)

        # Configuro el plot
        self.plot = self.win.addPlot(title="Señal Filtrada en Tiempo Real")
        self.plot.setYRange(-200, 200) # Ajusto rango visual (uV aprox)
        self.curve = self.plot.plot(pen='y') # Línea amarilla

        # --- Timers y Hilos ---
        # Configuro un timer rápido para actualizar la gráfica (cada 50ms)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_logic_and_graph)
        self.timer.start(50)

        # Inicio el hilo que simula el cambio de zonas (Ping-Pong 1->5->1)
        self.scenario_thread = threading.Thread(target=self.run_scenario_simulator, daemon=True)
        self.scenario_thread.start()

    def run_scenario_simulator(self):
        # Hilo secundario: Yo simulo el cambio de intensidad del ejercicio.
        # Subo de zona 1 a 5 y luego bajo de 5 a 1.
        scenario_zone = 1
        going_up = True 

        while True:
            logging.info(f"--- ESCENARIO: Solicitando al simulador ZONA {scenario_zone} ---")
            self.board.config_simulator_zone(scenario_zone)
            
            time.sleep(10) # Espero 10 segundos por zona

            # Calculo la siguiente zona 
            if going_up:
                scenario_zone += 1
                if scenario_zone >= 5:
                    scenario_zone = 5
                    going_up = False
            else:
                scenario_zone -= 1
                if scenario_zone <= 1:
                    scenario_zone = 1
                    going_up = True

    def update_logic_and_graph(self):
        #Obtengo datos crudos del board
        raw_data = self.board.get_data()
        
        if raw_data is None:
            return

        # Aplico mis filtros (los mismos que usará el Docker)
        filtered_data = self.analyzer.filter_signal(raw_data)

        # Calculo BPM
        raw_bpm = self.analyzer.calculate_bpm(filtered_data)
        
        # Aplico suavizado EMA
        if self.analyzer.smoothed_bpm == 0.0:
            self.analyzer.smoothed_bpm = raw_bpm
        else:
            self.analyzer.smoothed_bpm = (raw_bpm * self.analyzer.smoothing_factor) + \
                                   (self.analyzer.smoothed_bpm * (1.0 - self.analyzer.smoothing_factor))
        
        bpm_final = self.analyzer.smoothed_bpm

        # Detecto cambios de zona
        (changed, old, new) = self.analyzer.detect_zone_change(bpm_final)
        
        if changed:
            print(f"\n>>> CAMBIO DETECTADO: Zona {old} -> {new} (BPM: {bpm_final:.2f}) <<<\n")

        # Actualizo el título del gráfico con la info actual
        current_zone = self.analyzer.current_zone
        self.plot.setTitle(f"BPM: {bpm_final:.1f} | Zona Actual: {current_zone} | Buffer: {len(filtered_data)}")

        # Dibujo la señal
        self.curve.setData(filtered_data)

    def closeEvent(self, event):
        # Me aseguro de cerrar la sesión de la placa al cerrar la ventana
        self.board.stop()
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    tester = LocalGuiTester()
    tester.show()
    sys.exit(app.exec())