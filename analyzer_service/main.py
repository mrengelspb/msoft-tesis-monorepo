import logging
import time
import threading
import os
import numpy as np

from brainflow_handler import BrainflowHandler
from data_analysis import DataAnalyzer
from mqtt_handler import MQTTPublisher

"""
-----------------------------------------------------------------------------
SUBSYSTEM: ANALYZER SERVICE (BACKEND CORE)
-----------------------------------------------------------------------------
Descripción:
Este script es la logica principal en el entorno Docker. 
Orquesta la adquisición de señales del simulador de SYNTHETIC BOARD de BRAINFLOW,
el procesamiento matemático y la transmisión de telemetría vía MQTT.

Responsabilidades:
1. Adquisición: Controla la placa BrainFlow (Simulada o Real).
2. Procesamiento: Aplica filtros DSP y algoritmos de cálculo de BPM.
3. Simulación: Ejecuta un escenario de prueba automático (cambios de zona)
   para validar la lógica sin necesidad de un atleta real conectado.
4. Transmisión: Publica tres tipos de tópicos MQTT (Eventos, Status, Stream).

Arquitectura:
- Ejecución: Single-process con un hilo secundario para el simulador.
- Ciclo de Vida: Bucle infinito controlado por tiempo (20Hz).
-----------------------------------------------------------------------------
"""

# Configuración de Logs (Salida estándar capturada por Docker Compose)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - SERVICIO - %(message)s')

# CONFIGURACIÓN DINÁMICA (VARIABLES DE ENTORNO) 
# Permite ajustar parámetros desde docker-compose.yml sin tocar el código.
TEST_AGE = int(os.getenv("TEST_AGE", "30"))
USER_ID = os.getenv("USER_ID", "atleta_01")
DATA_WINDOW_POINTS = int(os.getenv("DATA_WINDOW_POINTS", "1024")) 

# SINCRONIZACIÓN DE BUCLE
# Velocidad del bucle principal: 0.05s (20Hz).
# Esto define la frecuencia de actualización de los cálculos y el envío MQTT.
LOOP_SPEED_S = 0.05

# Duración de cada "Zona de Esfuerzo" en la simulación.
SIMULATION_DURATION_S = 20 

def run_scenario_simulator(board_handler):
    """ 
    HILO DE SIMULACIÓN (Background Thread):
    Controla el hardware virtual de BrainFlow para inyectar diferentes 
    patrones de señal ECG correspondientes a zonas de esfuerzo reales.
    
    Lógica: (Zona 1 -> 5 -> 1)
    Propósito: Validar que el algoritmo detecta correctamente los cambios
    de zonas de frecuencia cardiaca.
    """
    scenario_zone = 1
    going_up = True
    
    # Pausa inicial para permitir que el buffer de datos se llene y estabilice
    time.sleep(3)
    
    while True:
        try:
            # Inyectamos el comando a la placa simulada
            board_handler.config_simulator_zone(scenario_zone)
        except: pass
        
        # Mantenemos la zona activa por el tiempo definido
        time.sleep(SIMULATION_DURATION_S) 
        
        # Cálculo de la siguiente zona (Subida o Bajada)
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

def main():
    logging.info("--> INICIANDO SERVICIO DE ANALISIS (BACKEND) <--")
    
    # INICIALIZACIÓN DE COMPONENTES
    try:
        # Hardware: Interfaz con BrainFlow (C++)
        board = BrainflowHandler(num_points=DATA_WINDOW_POINTS)
        # Lógica: Algoritmos matemáticos
        analyzer = DataAnalyzer(sampling_rate=board.sampling_rate, age=TEST_AGE)
        # Red: Cliente MQTT
        mqtt = MQTTPublisher(broker_host="mqtt-broker") 
    except Exception as e:
        logging.critical(f"Error fatal iniciando componentes: {e}")
        return

    try:
        # ARRANQUE DE PROCESOS
        board.start(age=TEST_AGE)
        
        # Iniciamos el simulador en un hilo paralelo para no bloquear el análisis
        sim_thread = threading.Thread(target=run_scenario_simulator, args=(board,), daemon=True)
        sim_thread.start()
        
        # CALCULO DE TAMAÑO DE PAQUETE (STREAMING)
        # Para enviar la señal ECG en tiempo real, no enviamos toda la ventana (1024 pts)
        # en cada ciclo, porque eso duplicaría datos y saturaría la red.
        # Enviamos solo los puntos NUEVOS generados en los últimos 0.05 segundos.
        # Fórmula: Frecuencia (250Hz) * Tiempo (0.05s) = ~12.5 puntos.
        points_per_chunk = int(board.sampling_rate * LOOP_SPEED_S)
        if points_per_chunk < 1: points_per_chunk = 1
        
        logging.info(f"Configuración: Bucle {LOOP_SPEED_S}s | Chunk MQTT {points_per_chunk} pts")

        # BUCLE PRINCIPAL (MAIN LOOP)
        while True:
            # A. ADQUISICIÓN DE DATOS
            # Obtenemos la ventana deslizante completa (ej. últimos 4 segundos)
            ecg_data_raw = board.get_data()
            
            if ecg_data_raw is None:
                time.sleep(0.01)
                continue

            # B. PROCESAMIENTO DE SEÑAL (DSP)
            # Aplicamos filtros Pasa-Banda (1-50Hz) y Notch (50/60Hz)
            # Usamos la ventana completa para que los filtros funcionen mejor.
            filtered_data = analyzer.filter_signal(ecg_data_raw)
            
            # C. ANÁLISIS MATEMÁTICO (Extracción de Características)
            # Calculamos BPM usando Welch + Filtro de Mediana
            bpm = analyzer.calculate_bpm(filtered_data)
            
            # D. DETECCION DE EVENTOS
            # Verificamos si el atleta cambió de Zona de Frecuencia Cardíaca
            (change, old_z, new_z) = analyzer.detect_zone_change(bpm)

            # E. COMUNICACIÓN (MQTT)
            
            # Tópico 1: EVENTOS (Alta Prioridad - QoS 1)
            # Solo se envía cuando ocurre un cambio de estado significativo.
            if change:
                logging.info(f"¡CAMBIO DETECTADO! Zona {old_z} -> {new_z} (BPM: {bpm:.2f})")
                mqtt.publish_zone_change(USER_ID, old_z, new_z, bpm)
            
            # Tópico 2: STATUS (Baja Prioridad - QoS 0)
            # Heartbeat del sistema (1 vez por ciclo) para dashboards.
            mqtt.publish_status(USER_ID, bpm, analyzer.current_zone)

            # Tópico 3: STREAM DE ONDA (Alta Frecuencia)
            # Aquí ocurre la magia del streaming. Recortamos ("Slicing") solo
            # el final del array filtrado para enviarlo al visualizador.
            if len(filtered_data) >= points_per_chunk:
                chunk_to_send = filtered_data[-points_per_chunk:]
                mqtt.publish_ecg_data(chunk_to_send)
            
            # Control de Ritmo (20Hz)
            time.sleep(LOOP_SPEED_S) 

    except KeyboardInterrupt:
        logging.info("Deteniendo servicio por solicitud de usuario...")
    except Exception as e:
        logging.error(f"Error no controlado en bucle principal: {e}")
    finally:
        # Limpieza de recursos (Hardware y Red)
        board.stop()
        mqtt.disconnect()
        logging.info("Servicio finalizado correctamente.")

if __name__ == '__main__':
    main()