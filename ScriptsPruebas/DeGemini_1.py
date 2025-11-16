import time
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

def main():
    print("Iniciando prueba con SYNTHETIC_BOARD...")

    # 1. Configurar parámetros
    # Para la placa sintética, no se necesitan parámetros especiales 
    # (como el puerto COM o la MAC address).
    params = BrainFlowInputParams()

    # 2. Definir el ID de la placa
    # Usamos BoardIds.SYNTHETIC_BOARD.value o simplemente BoardIds.SYNTHETIC_BOARD
    # Su ID numérico interno es -1
    board_id = BoardIds.SYNTHETIC_BOARD

    # 3. Crear la instancia de BoardShim
    board = BoardShim(board_id, params)

    # 4. Preparar la sesión
    try:
        board.prepare_session()
    except Exception as e:
        print(f"Error al preparar la sesión: {e}")
        return

    # 5. Iniciar el stream de datos
    # Esto le dice a BrainFlow que comience a generar datos sintéticos
    board.start_stream()
    print("Stream iniciado. Recolectando datos por 5 segundos...")

    # 6. Esperar para recolectar datos
    # Dejamos que el búfer se llene durante 5 segundos
    time.sleep(5)

    # 7. Obtener los datos del búfer
    # get_board_data() obtiene TODOS los datos acumulados en el búfer
    data = board.get_board_data() 

    # 8. Detener y liberar la sesión
    board.stop_stream()
    board.release_session()
    print("Stream detenido y sesión liberada.")

    # --- Procesar y mostrar los datos ---
    if data is not None and data.shape[1] > 0:
        print(f"\n¡Datos adquiridos exitosamente!")
        # El formato de 'data' es un array de NumPy
        # Filas (data.shape[0]): Canales
        # Columnas (data.shape[1]): Muestras (paquetes de datos)
        print(f"Forma de los datos (Canales x Muestras): {data.shape}")

        # Puedes obtener información específica de los canales
        # Por ejemplo, cuáles son los canales de EEG para esta placa
        eeg_channels = BoardShim.get_eeg_channels(board_id)
        print(f"Canales de EEG para esta placa: {eeg_channels}")

        # Imprimir las primeras 5 muestras del primer canal de EEG
        if eeg_channels:
            primer_canal_eeg = eeg_channels[0]
            print(f"Primeras 5 muestras del canal {primer_canal_eeg}:")
            print(data[primer_canal_eeg, :5])
    else:
        print("No se adquirieron datos.")

if __name__ == "__main__":
    main()