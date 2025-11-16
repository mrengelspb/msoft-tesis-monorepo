import time
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

def main_batch_ecg():
    print("Iniciando prueba con SYNTHETIC_BOARD: Enfoque ECG...")
    
    params = BrainFlowInputParams()
    board_id = BoardIds.SYNTHETIC_BOARD
    board = BoardShim(board_id, params)

    try:
        print("Preparando la sesión...")
        board.prepare_session()
        print("Sesión preparada.")
    except Exception as e:
        print(f"Error al preparar la sesión: {e}")
        return

    board.start_stream()
    print("Stream iniciado. Recolectando datos por 5 segundos...")
    time.sleep(5)

    # 1. Obtener TODOS los datos del búfer
    data = board.get_board_data() 

    board.stop_stream()
    board.release_session()
    print("Stream detenido y sesión liberada.")

    if data is not None and data.shape[1] > 0:

        fs = BoardShim.get_sampling_rate(board_id)
        print(f"Frecuencia de muestreo: {fs} Hz")


        print(f"\nForma de los datos (Todos los canales x Muestras): {data.shape}")


        # 2. OBTENER LOS ÍNDICES DE LOS CANALES ECG
        # Esta es la parte clave. Le preguntas a BrainFlow qué filas 
        # de la matriz 'data' corresponden a los canales ECG.
        try:
            ecg_channels = BoardShim.get_ecg_channels(board_id)
        except Exception as e:
            print(f"Error obteniendo canales ECG: {e}")
            return

        print(f"Los canales ECG para esta placa son las filas: {ecg_channels}")
        
        # 3. FILTRAR LA MATRIZ DE DATOS
        # Usamos indexación de NumPy para quedarnos solo con esas filas
        ecg_data = data[ecg_channels]
        
        print(f"Forma de los datos (Solo ECG x Muestras): {ecg_data.shape}")

        # 4. Mostrar los datos de un solo canal ECG
        # ecg_data[0] es el primer canal ECG
        print(f"Primeras 10 muestras del primer canal ECG (Canal {ecg_channels[0]}):")
        print(ecg_data[0, :10])
        
        # ecg_data[1] es el segundo canal ECG, si existe
        if len(ecg_channels) > 1:
            print(f"Primeras 10 muestras del segundo canal ECG (Canal {ecg_channels[1]}):")
            print(ecg_data[1, :10])
    
    else:
        print("No se adquirieron datos.")

if __name__ == "__main__":
    main_batch_ecg()