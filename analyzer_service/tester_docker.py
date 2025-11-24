import time
import threading
import logging
import sys
import os

# Importamos brainflow para verificar que usa la versión correcta
import brainflow
from brainflow.board_shim import BoardShim

# Importo mis clases de lógica (Asumiendo que están en la misma carpeta)
try:
    from brainflow_handler import BrainflowHandler
    from data_analysis import DataAnalyzer
except ImportError as e:
    print(f"Error importando módulos locales: {e}")
    print("Asegurate de montar el volumen de docker correctamente.")
    sys.exit(1)

# Configuro el log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - DOCKER - %(message)s')

class HeadlessTester:
    def __init__(self):
        # 0. Verificación de librerías
        #print(f"--> Usando BrainFlow versión: {brainflow.__version__}")
        print(f"--> Versión interna C++: {BoardShim.get_version()}")
        
        # --- Inicialización de Lógica ---
        self.board = BrainflowHandler(num_points=1024)
        self.board.start(age=30) 

        # Instancio el analizador (V5)
        self.analyzer = DataAnalyzer(sampling_rate=self.board.sampling_rate, age=30)
        
        self.running = True

    def run_scenario_simulator(self):
        """ Simula cambios de zona """
        scenario_zone = 1
        going_up = True 
        time.sleep(2) # Espera inicial

        while self.running:
            logging.info(f"--- SIMULADOR: Configurando ZONA {scenario_zone} ---")
            try:
                self.board.config_simulator_zone(scenario_zone)
            except Exception as e:
                logging.error(f"Error configurando zona: {e}")
            
            # Espero 20 segundos antes de cambiar de zona
            for _ in range(20):
                if not self.running: break
                time.sleep(1)

            # Lógica de cambio de zona (1 -> 5 -> 1)
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

    def run_main_loop(self):
        """ 
        Bucle principal (reemplaza al timer de la GUI)
        """
        # Inicio el hilo del simulador
        sim_thread = threading.Thread(target=self.run_scenario_simulator, daemon=True)
        sim_thread.start()

        print(">>> INICIANDO TEST EN DOCKER (Ctrl+C para salir) <<<")
        
        try:
            while True:
                # Obtengo datos
                raw_data = self.board.get_data()
                
                if raw_data is not None:
                    # 1. Filtros
                    filtered_data = self.analyzer.filter_signal(raw_data)

                    # 2. Calculo BPM 
                    bpm_final = self.analyzer.calculate_bpm(filtered_data)
                    
                    # 3. Detecto cambios
                    (changed, old, new) = self.analyzer.detect_zone_change(bpm_final)
                    
                    # Output en consola (simulando la GUI)
                    status_msg = f"BPM: {bpm_final:.1f} | Zona: {self.analyzer.current_zone}"
                    
                    if changed:
                        print(f"\n🚀 CAMBIO DETECTADO: Zona {old} -> {new} ({status_msg}) 🚀\n")
                    else:
                        # Imprimo en la misma línea para no llenar la consola (opcional)
                        # sys.stdout.write(f"\r{status_msg}")
                        # sys.stdout.flush()
                        pass # O simplemente no imprimir nada si no hay cambios para mantenerlo limpio

                # Simulo los 50ms del timer de la GUI
                time.sleep(0.05)
                
        except KeyboardInterrupt:
            print("\nDeteniendo prueba...")
            self.running = False
            self.board.stop()
            print("Prueba finalizada.")

if __name__ == '__main__':
    tester = HeadlessTester()
    tester.run_main_loop()