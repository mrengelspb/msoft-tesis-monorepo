import logging
import time
import threading
import os  # Importo os para leer las variables de entorno del sistema

# Importo mis módulos de lógica personalizada
from brainflow_handler import BrainflowHandler
from data_analysis import DataAnalyzer
from mqtt_handler import MQTTPublisher

# --- Configuración ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Leo las configuraciones desde las variables de entorno inyectadas por Docker Compose.
# Si no existen, establezco valores por defecto para pruebas locales.
TEST_AGE = int(os.getenv("TEST_AGE", "30"))
USER_ID = os.getenv("USER_ID", "atleta_01")
UPDATE_SPEED_S = float(os.getenv("UPDATE_SPEED_S", "1.0"))  # Calculo BPM cada X segundos
DATA_WINDOW_POINTS = int(os.getenv("DATA_WINDOW_POINTS", "1024")) # Puntos que utilizo para el análisis

def run_scenario_simulator(board_handler):
    """ 
    Hilo secundario donde simulo el cambio de zonas.
    Implemento una lógica de subida y bajada (1->5 y 5->1).
    """
    scenario_zone = 1
    going_up = True # Utilizo esta bandera para saber si estoy subiendo o bajando de intensidad

    while True:
        # Configuro la zona actual en el simulador de BrainFlow
        board_handler.config_simulator_zone(scenario_zone)
        
        # Espero 15 segundos antes del siguiente cambio
        time.sleep(15)

        # Calculo la siguiente zona
        if going_up:
            scenario_zone += 1
            # Si llego a la zona 5, cambio la dirección para empezar a bajar
            if scenario_zone >= 5:
                scenario_zone = 5
                going_up = False
        else:
            scenario_zone -= 1
            # Si llego a la zona 1, cambio la dirección para empezar a subir
            if scenario_zone <= 1:
                scenario_zone = 1
                going_up = True

def main():
    logging.info("Iniciando mi Servicio Analizador...")
    
    # Inicializo mis manejadores (Handlers)
    try:
        # Instancio el manejador de la placa con el tamaño de ventana definido
        board = BrainflowHandler(num_points=DATA_WINDOW_POINTS)
        
        # Instancio mi analizador de datos pasando la tasa de muestreo y la edad del atleta
        analyzer = DataAnalyzer(sampling_rate=board.sampling_rate, age=TEST_AGE)
        
        # Inicializo la conexión MQTT apuntando al host definido en Docker
        mqtt = MQTTPublisher(broker_host="mqtt-broker") 
    except Exception as e:
        logging.critical(f"Tuve un error al inicializar mis handlers: {e}")
        return

    try:
        # Inicio la tarjeta simulada de BrainFlow
        board.start(age=TEST_AGE)
        
        # Inicio el simulador de escenarios en un hilo separado para no bloquear mi bucle principal
        scenario_thread = threading.Thread(target=run_scenario_simulator, args=(board,), daemon=True)
        scenario_thread.start()
        
        logging.info("He iniciado el servicio correctamente. Entro en mi bucle principal.")

        # Bucle principal donde proceso los datos continuamente
        while True:
            # Obtengo los datos crudos de BrainFlow
            ecg_data_raw = board.get_data()
            
            if ecg_data_raw is None:
                # Si no tengo suficientes datos, espero un poco y reintento
                time.sleep(0.1) 
                continue

            # Filtro la señal para eliminar ruido
            filtered_data = analyzer.filter_signal(ecg_data_raw)

            # =====================
            # SUAVIZADO DE BPM
            # =====================
            # Calculo el BPM "crudo" de esta ventana actual
            raw_bpm = analyzer.calculate_bpm(filtered_data)
            
            # Aplico el suavizado (Promedio Móvil Exponencial) para evitar saltos bruscos
            if analyzer.smoothed_bpm == 0.0:
                # Si es mi primer cálculo, inicializo el valor directamente
                analyzer.smoothed_bpm = raw_bpm
            else:
                # Aplico fórmula de filtro EMA
                analyzer.smoothed_bpm = (raw_bpm * analyzer.smoothing_factor) + \
                                       (analyzer.smoothed_bpm * (1.0 - analyzer.smoothing_factor))
            
            # Utilizo el BPM suavizado para determinar lógica de zonas
            bpm_para_logica = analyzer.smoothed_bpm
            
            # Detecto si ha ocurrido un cambio de zona basado en el BPM suavizado
            (change_detected, old_zone, new_zone) = analyzer.detect_zone_change(bpm_para_logica)

            if change_detected:
                logging.info(f"¡He detectado un CAMBIO DE ZONA! {old_zone} -> {new_zone} (BPM: {bpm_para_logica:.2f})")
                # Publico el cambio de zona con QoS 1 (Aseguro entrega)
                mqtt.publish_zone_change(USER_ID, old_zone, new_zone, bpm_para_logica) 
            
            # Publico los datos filtrados (Stream) con QoS 0 (Velocidad sobre fiabilidad)
            mqtt.publish_ecg_data(filtered_data) 
            
            # Espero el tiempo definido en la variable de entorno antes del próximo ciclo
            time.sleep(UPDATE_SPEED_S) 

    except KeyboardInterrupt:
        logging.info("He detectado una interrupción de teclado. Cerrando.")
    except Exception as e:
        logging.error(f"Error crítico en mi bucle principal: {e}", exc_info=True)
    finally:
        # Realizo la limpieza de recursos
        logging.info("Estoy cerrando el servicio...")
        board.stop()
        mqtt.disconnect()
        logging.info("Servicio detenido completamente.")

if __name__ == '__main__':
    main()