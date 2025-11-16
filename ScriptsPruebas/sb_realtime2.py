import time
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

def main():
    print("Iniciando prueba REAL-TIME con SYNTHETIC_BOARD (enfocado en ECG)...")

    params = BrainFlowInputParams()
    board_id = BoardIds.SYNTHETIC_BOARD
    board = BoardShim(board_id, params)

    try:
        board.prepare_session()
    except Exception as e:
        print(f"Error al preparar la sesión: {e}")
        return

    board.start_stream()
    print("Stream iniciado. Llenando el búfer inicial por 2 segundos...")
    time.sleep(2) # Dejar que se acumulen algunos datos

    # Obtener la información del canal ECG ANTES del bucle
    try:
        ecg_channels = BoardShim.get_ecg_channels(board_id)
        if not ecg_channels:
            print("Esta placa no tiene canales ECG.")
            board.stop_stream()
            board.release_session()
            return
        
        # Usaremos el primer canal ECG disponible
        ecg_channel = ecg_channels[0]
        print(f"Monitoreando el canal ECG: {ecg_channel}. Presiona Ctrl+C para parar.")

    except Exception as e:
        print(f"Error al obtener canales: {e}")
        board.stop_stream()
        board.release_session()
        return

    # Cuántas muestras queremos sacar del búfer en cada iteración
    # La placa sintética corre a 250Hz. Saquemos 25 muestras (0.1 seg de datos)
    num_samples_por_pull = 25 

    try:
        while True:
            # 1. Obtener solo los datos MÁS RECIENTES
            # Pide las últimas N muestras. El búfer interno se limpia.
            data = board.get_current_board_data(num_samples_por_pull)
            
            # data.shape[1] es el número de muestras que realmente se recibieron
            if data.shape[1] > 0:
                # Obtenemos la última muestra (la más reciente) de nuestro canal ECG
                # data[ecg_channel] -> Todas las muestras de ese pull para ese canal
                # data[ecg_channel, -1] -> La última muestra
                latest_ecg_value = data[ecg_channel, -1]
                
                # \r y end='' hacen que la línea se sobreescriba
                print(f"Último valor ECG: {latest_ecg_value:10.2f}", end='\r')
            
            # Esperar un poco antes del siguiente pull
            time.sleep(0.1) # Actualizamos 10 veces por segundo

    except KeyboardInterrupt:
        print("\nDeteniendo el stream...")
    finally:
        board.stop_stream()
        board.release_session()
        print("Stream detenido y sesión liberada.")

if __name__ == "__main__":
    main()