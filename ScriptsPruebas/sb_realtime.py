import time
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

def main_realtime_ecg():
    print("Iniciando prueba con SYNTHETIC_BOARD (Tiempo Real ECG)...")
    
    params = BrainFlowInputParams()
    board_id = BoardIds.SYNTHETIC_BOARD
    board = BoardShim(board_id, params)

    try:
        board.prepare_session()
    except Exception as e:
        print(f"Error al preparar la sesión: {e}")
        return

    # Obtener los canales ECG ANTES de empezar el bucle
    try:
        ecg_channels = BoardShim.get_ecg_channels(board_id)
        print(f"Canales ECG detectados: {ecg_channels}")
    except Exception as e:
        print(f"Error obteniendo canales ECG: {e}")
        return
        
    print(f"Stream iniciado. Monitoreando canales ECG: {ecg_channels}")
    print("Presiona Ctrl+C para detener.")
    
    board.start_stream()
    
    try:
        while True:
            # Dormir un corto período. 250ms es un buen balance.
            time.sleep(0.25) 
            
            # Obtener los datos que han llegado desde la última llamada
            data = board.get_board_data() 

            if data.shape[1] > 0:
                # Tenemos datos nuevos
                print(f"--- Nuevas {data.shape[1]} muestras recibidas ---")
                
                # Filtrar solo los canales ECG
                ecg_data = data[ecg_channels]
                
                # Para este ejemplo, solo mostraremos el valor PROMEDIO
                # de las muestras recibidas para cada canal ECG
                for i, chan_index in enumerate(ecg_channels):
                    canal_data = ecg_data[i] # Datos de un solo canal ECG
                    print(f"  Canal ECG {chan_index} (Promedio): {np.mean(canal_data):.4f} \t(Max): {np.max(canal_data):.4f}")

    except KeyboardInterrupt:
        print("\nDeteniendo stream...")
    finally:
        board.stop_stream()
        board.release_session()
        print("Stream detenido y sesión liberada.")

if __name__ == "__main__":
    main_realtime_ecg()