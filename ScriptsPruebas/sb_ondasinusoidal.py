import time
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
# Para visualizar, necesitarás matplotlib: pip install matplotlib
import matplotlib.pyplot as plt

def main():
    print("Iniciando prueba AVANZADA con SYNTHETIC_BOARD...")

    params = BrainFlowInputParams()
    
    # ¡Aquí está la magia!
    # Le decimos a la placa que genere una onda sinusoidal (sine)
    # de 1 Hz de frecuencia y 10 de amplitud en TODOS los canales ECG.
    # Formato: "canal_tipo:onda:frecuencia:amplitud"
    params.other_info = "ecg:sine:1.0:10.0" 
    
    # Si quisieras una señal de pulso (más realista para ECG):
    # params.other_info = "ecg:pulse:1.0:10.0" # 1 Hz (60 BPM)
    
    # Si quisieras afectar un canal EEG:
    # params.other_info = "eeg:sine:10.0:5.0" # Onda Alfa de 10 Hz

    board_id = BoardIds.SYNTHETIC_BOARD
    board = BoardShim(board_id, params)

    board.prepare_session()
    board.start_stream()
    print(f"Stream iniciado con configuración: '{params.other_info}'. Recolectando 5 seg...")
    time.sleep(5)
    data = board.get_board_data() 
    board.stop_stream()
    board.release_session()

    if data is not None and data.shape[1] > 0:
        fs = BoardShim.get_sampling_rate(board_id)
        ecg_channels = BoardShim.get_ecg_channels(board_id)
        
        if not ecg_channels:
            print("No se encontraron canales ECG.")
            return

        # Tomar los datos del primer canal ECG
        ecg_channel = ecg_channels[0]
        ecg_data = data[ecg_channel]
        
        # Crear un vector de tiempo para el eje X
        time_vector = np.arange(ecg_data.shape[0]) / fs
        
        print(f"Datos del canal ECG {ecg_channel} (primeras 10 muestras):")
        print(ecg_data[:10])

        print("\nMostrando gráfico. Cierra la ventana del gráfico para continuar.")
        
        # Graficar los resultados
        plt.figure(figsize=(10, 4))
        plt.plot(time_vector, ecg_data)
        plt.title(f"Señal ECG Sintética (Canal {ecg_channel}) - Config: {params.other_info}")
        plt.xlabel("Tiempo (s)")
        plt.ylabel("Amplitud (uV)")
        plt.grid(True)
        plt.show()

if __name__ == "__main__":
    main()