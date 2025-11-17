import numpy as np
import logging
from brainflow.data_filter import DataFilter, FilterTypes, WindowOperations, DetrendOperations

class DataAnalyzer:
    def __init__(self, sampling_rate, age=30):
        self.sampling_rate = sampling_rate
        self.age = age
        self.max_hr = 220 - self.age
        
        self.current_zone = 0
        self.current_bpm = 0.0

    def filter_signal(self, ecg_data):
        """ Aplica filtros de limpieza a la señal ECG """
        # Hacemos una copia para no modificar el original
        filtered_data = np.copy(ecg_data)
        
        DataFilter.detrend(filtered_data, DetrendOperations.CONSTANT.value)
        DataFilter.perform_bandpass(filtered_data, self.sampling_rate, 1.0, 40.0, 2,
                                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        DataFilter.perform_bandstop(filtered_data, self.sampling_rate, 48.0, 52.0, 2,
                                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        DataFilter.perform_bandstop(filtered_data, self.sampling_rate, 58.0, 62.0, 2,
                                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        
        return filtered_data

    def calculate_bpm(self, filtered_data):
        """ Calcula el BPM usando el método Welch """
        try:
            nperseg = len(filtered_data)
            noverlap = nperseg // 2
            
            psd_data = DataFilter.get_psd_welch(
                filtered_data, nperseg, noverlap, 
                self.sampling_rate, WindowOperations.BLACKMAN_HARRIS.value
            )
            psd_amps = psd_data[0]
            psd_freqs = psd_data[1]

            # Rangos de BPM en Hz (48-240 BPM)
            min_hr_hz = 0.8
            max_hr_hz = 4.0
            min_hr_idx = np.where(psd_freqs > min_hr_hz)[0][0]
            max_hr_idx = np.where(psd_freqs > max_hr_hz)[0][0]

            peak_idx_in_band = np.argmax(psd_amps[min_hr_idx:max_hr_idx])
            peak_idx_total = min_hr_idx + peak_idx_in_band
            peak_freq_hz = psd_freqs[peak_idx_total]

            self.current_bpm = peak_freq_hz * 60.0
            return self.current_bpm
        
        except Exception as e:
            logging.warning(f"No se pudo calcular BPM: {e}")
            return self.current_bpm # Retorna el último valor bueno

    def detect_zone_change(self, bpm):
        # Detecta si el BPM ha cruzado un umbral de zona
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
        
        if potential_zone == self.current_zone:
            # El BPM está en la zona actual, resetear cualquier conteo
            self.zone_stability_counter = 0
            self.candidate_zone = potential_zone
            return (False, 0, 0) # Sin cambio

        if potential_zone != self.candidate_zone:
            # Es una nueva zona candidata, empezar a contar desde 1
            self.candidate_zone = potential_zone
            self.zone_stability_counter = 1
            return (False, 0, 0) # Sin cambio
        
        if potential_zone == self.candidate_zone:
            # Sigue siendo la misma candidata, incrementar contador
            self.zone_stability_counter += 1

        # 3. Comprobar si se ha alcanzado el umbral de estabilidad
        if self.zone_stability_counter >= self.ZONE_STABILITY_THRESHOLD:
            # ¡CAMBIO CONFIRMADO!
            old_zone = self.current_zone
            self.current_zone = self.candidate_zone
            self.zone_stability_counter = 0 # Resetear contador
            return (True, old_zone, self.current_zone)
        
        # Aún no es estable, no hay cambio
        return (False, 0, 0)
    