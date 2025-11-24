import numpy as np
import logging
from brainflow.data_filter import DataFilter, FilterTypes, WindowOperations, DetrendOperations

class DataAnalyzer:
    def __init__(self, sampling_rate, age=30):
        self.sampling_rate = sampling_rate
        self.age = age
        # Calculo la frecuencia cardíaca máxima teórica basada en la edad
        self.max_hr = 220 - self.age
        
        # Inicializo variables de estado para el seguimiento de zonas
        self.current_zone = 0
        self.current_bpm = 0.0
        
        # Variables para el suavizado EMA (Exponential Moving Average)
        self.smoothed_bpm = 0.0
        self.smoothing_factor = 0.1 # Factor de suavizado (alpha)
        
        # Variables para la lógica de histéresis/estabilidad de zona
        self.candidate_zone = 0
        self.zone_stability_counter = 0
        self.ZONE_STABILITY_THRESHOLD = 3 # Necesito 3 lecturas consecutivas para confirmar cambio

    def filter_signal(self, ecg_data):
        # Aplico una cadena de filtros para limpiar la señal ECG cruda:

        # Hago una copia del array para asegurarme de no modificar la fuente original
        filtered_data = np.copy(ecg_data)
        
        # Elimino la tendencia lineal (Detrend)
        DataFilter.detrend(filtered_data, DetrendOperations.CONSTANT.value)
        
        # Aplico un filtro Pasa-Banda (Bandpass) entre 1.0Hz y 40.0Hz
        DataFilter.perform_bandpass(filtered_data, self.sampling_rate, 1.0, 40.0, 2,
                                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        
        # Aplico filtros de corte (Bandstop) para eliminar ruido de línea eléctrica (50Hz y 60Hz)
        DataFilter.perform_bandstop(filtered_data, self.sampling_rate, 48.0, 52.0, 2,
                                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        DataFilter.perform_bandstop(filtered_data, self.sampling_rate, 58.0, 62.0, 2,
                                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        
        return filtered_data

    def calculate_bpm(self, filtered_data):
        # Calculo el BPM utilizando la Densidad Espectral de Potencia (Método Welch)
        try:
            nperseg = len(filtered_data)
            noverlap = nperseg // 2
            
            # Obtengo el PSD (Power Spectral Density) usando ventana Blackman-Harris
            psd_data = DataFilter.get_psd_welch(
                filtered_data, nperseg, noverlap, 
                self.sampling_rate, WindowOperations.BLACKMAN_HARRIS.value
            )
            psd_amps = psd_data[0] # Amplitudes
            psd_freqs = psd_data[1] # Frecuencias

            # Defino los límites de frecuencia donde espero encontrar el ritmo cardíaco (48-240 BPM)
            min_hr_hz = 0.8
            max_hr_hz = 4.0
            
            # Busco los índices correspondientes a estas frecuencias en mi array PSD
            min_hr_idx = np.where(psd_freqs > min_hr_hz)[0][0]
            max_hr_idx = np.where(psd_freqs > max_hr_hz)[0][0]

            # Encuentro el pico máximo de amplitud dentro del rango de interés
            peak_idx_in_band = np.argmax(psd_amps[min_hr_idx:max_hr_idx])
            peak_idx_total = min_hr_idx + peak_idx_in_band
            peak_freq_hz = psd_freqs[peak_idx_total]

            # Convierto la frecuencia pico (Hz) a pulsaciones por minuto (BPM)
            self.current_bpm = peak_freq_hz * 60.0
            return self.current_bpm
        
        except Exception as e:
            logging.warning(f"No pude calcular el BPM en este ciclo: {e}")
            return self.current_bpm # Retorno el último valor conocido para evitar caídas

    def detect_zone_change(self, bpm):
        # Verifico si el BPM actual corresponde a una nueva zona.
        # Implemento un mecanismo de estabilidad para evitar cambios rápidos erráticos.
        
        # Determino la zona potencial basada en porcentajes de la frecuencia máxima
        if bpm < (self.max_hr * 0.6):
            potential_zone = 1
        elif bpm < (self.max_hr * 0.7):
            potential_zone = 2
        elif bpm < (self.max_hr * 0.8):
            potential_zone = 3
        elif bpm < (self.max_hr * 0.9):
            potential_zone = 4
        else:
            potential_zone = 5
        
        # Si la zona potencial es igual a la actual, reseteo contadores
        if potential_zone == self.current_zone:
            self.zone_stability_counter = 0
            self.candidate_zone = potential_zone
            return (False, 0, 0) # No hay cambio

        # Si aparece una nueva zona candidata diferente a la anterior candidata, reinicio el conteo
        if potential_zone != self.candidate_zone:
            self.candidate_zone = potential_zone
            self.zone_stability_counter = 1
            return (False, 0, 0) # Aún no confirmo el cambio
        
        # Si la zona candidata se mantiene, incremento mi contador de estabilidad
        if potential_zone == self.candidate_zone:
            self.zone_stability_counter += 1

        # Verifico si he alcanzado el umbral de estabilidad requerido
        if self.zone_stability_counter >= self.ZONE_STABILITY_THRESHOLD:
            # Confirmo el cambio de zona
            old_zone = self.current_zone
            self.current_zone = self.candidate_zone
            self.zone_stability_counter = 0 # Reseteo el contador tras el cambio exitoso
            return (True, old_zone, self.current_zone)
        
        # Si no cumplo ninguna condición anterior, no reporto cambio
        return (False, 0, 0)