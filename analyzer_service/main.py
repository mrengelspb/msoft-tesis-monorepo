import logging
import time
import threading

# Importamos nuestros módulos de lógica
from brainflow_handler import BrainflowHandler
from data_analysis import DataAnalyzer
from mqtt_handler import MQTTPublisher

# --- Configuración ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TEST_AGE = 30
USER_ID = "atleta_01"
UPDATE_SPEED_S = 1.0  # Calcula BPM cada 1 segundo
DATA_WINDOW_POINTS = 1024 # Puntos para análisis (debe coincidir con BrainFlow)

def run_scenario_simulator(board_handler):
    """ Hilo que cambia la zona del simulador cada 15 segundos """
    scenario_zone = 0
    while True:
        scenario_zone = (scenario_zone % 5) + 1
        board_handler.config_simulator_zone(scenario_zone)
        time.sleep(15)

def main():
    logging.info("Iniciando Servicio Analizador...")
    
    #Inicializacion de Handlers
    try:
        board = BrainflowHandler(num_points=DATA_WINDOW_POINTS)
        analyzer = DataAnalyzer(sampling_rate=board.sampling_rate, age=TEST_AGE)
        # Apunta al nombre del servicio de Docker Compose
        mqtt = MQTTPublisher(broker_host="mqtt-broker") 
    except Exception as e:
        logging.critical(f"Error al inicializar handlers: {e}")
        return

    try:
        # Inicia Tarjeta simlada de BrainFlow
        board.start(age=TEST_AGE)
        
        #Inicia simulador en un hilo separado para no bloquear
        scenario_thread = threading.Thread(target=run_scenario_simulator, args=(board,), daemon=True)
        scenario_thread.start()
        
        logging.info("Servicio iniciado. Entrando en bucle principal.")

        # Bucle principal del servicio
        while True:
            # Obtener datos de BrainFlow
            ecg_data_raw = board.get_data()
            
            if ecg_data_raw is None:
                # Esperar si no hay suficientes datos
                time.sleep(0.1) 
                continue

            # Analizar datos
            filtered_data = analyzer.filter_signal(ecg_data_raw)

            # =====================
            # SUAVIZADO DE BPM
            # =====================
            # Se calcula el BPM "crudo" de esta ventana
            raw_bpm = analyzer.calculate_bpm(filtered_data)
            
            # Se aplica el suavizado (Promedio Móvil Exponencial)
            if analyzer.smoothed_bpm == 0.0:
                # Si es el primer cálculo, lo inicializamos
                analyzer.smoothed_bpm = raw_bpm
            else:
                # Aplicamos el filtro EMA
                analyzer.smoothed_bpm = (raw_bpm * analyzer.smoothing_factor) + \
                                     (analyzer.smoothed_bpm * (1.0 - analyzer.smoothing_factor))
            
            # Se usa el BPM suavizado para la lógica de zonas
            bpm_para_logica = analyzer.smoothed_bpm
            
            # =====================
            # SUAVIZADO DE BPM
            # =====================
            bpm = analyzer.smoothed_bpm         
            
            # Detectar cambios de zona
            #(change_detected, old_zone, new_zone) = analyzer.detect_zone_change(bpm)
            
            # Detectar cambios de zona (con BPM suavizado)
            (change_detected, old_zone, new_zone) = analyzer.detect_zone_change(bpm_para_logica)

            if change_detected:
                logging.info(f"¡CAMBIO DE ZONA DETECTADO! {old_zone} -> {new_zone} (BPM: {bpm:.2f})")
                mqtt.publish_zone_change(USER_ID, old_zone, new_zone, bpm) # Publicar en MQTT
            mqtt.publish_ecg_data(filtered_data) # Publicar los datos filtrados
            time.sleep(UPDATE_SPEED_S) # Espera 1 segundo (proximo ciclo)

    except KeyboardInterrupt:
        logging.info("Detectado cierre (KeyboardInterrupt).")
    except Exception as e:
        logging.error(f"Error crítico en bucle principal: {e}", exc_info=True)
    finally:
        # Limpieza
        logging.info("Cerrando servicio...")
        board.stop()
        mqtt.disconnect()
        logging.info("Servicio detenido.")

if __name__ == '__main__':
    main()