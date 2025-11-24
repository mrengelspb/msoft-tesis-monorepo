import numpy as np
import logging
import time
from collections import deque
from brainflow.data_filter import DataFilter, FilterTypes, WindowOperations, DetrendOperations

"""
-----------------------------------------------------------------------------
SUBSYSTEM: DSP & ALGORITMOS
-----------------------------------------------------------------------------
Descripción:
Este módulo encapsula toda la lógica matemática del sistema.
Implementa un pipeline de procesamiento de señales en 4 etapas para convertir
datos crudos de ECG en una frecuencia cardíaca (BPM) estable y confiable.

Pipeline de Procesamiento :
1. Pre-procesamiento: Eliminación de tendencia (Detrend) y Ruido de red.
2. Estimación Espectral: Método de Welch para encontrar la frecuencia dominante.
3. Filtrado Estadístico: Filtro de Mediana (Median Filter) para eliminar outliers.
4. Suavizado Temporal: Media Móvil Exponencial (EMA) para transiciones suaves.
5. Lógica de Negocio: Detección de cambios de zona con Histéresis temporal.
-----------------------------------------------------------------------------
"""

class DataAnalyzer:
    def __init__(self, sampling_rate, age=30):
        self.sampling_rate = sampling_rate
        self.age = age
        # Fórmula estándar de Karvonen/Fox para FC Máxima teórica
        self.max_hr = 220 - self.age
        
        # Variables de estado del atleta
        self.current_zone = 0
        self.current_bpm = 0.0 
        
        # --- ETAPA 3: Filtro de Mediana ---
        # Almacena las últimas 40 estimaciones de BPM.
        # A 20Hz (ciclo del main), 40 muestras representan ~2 segundos de historia.
        # Esto permite ignorar picos erráticos de hasta 1 segundo sin afectar la salida.
        self.bpm_history = deque(maxlen=40) 
        
        # --- ETAPA 4: SUAVIZADO (EMA) ---
        # Exponential Moving Average.
        # Alpha 0.15 significa que damos un 15% de peso al nuevo dato y 85% al histórico.
        # Esto genera una curva muy visual y orgánica, sin saltos bruscos.
        self.ema_bpm = 0.0
        self.ema_alpha = 0.15 

        # --- LÓGICA DE HISTÉRESIS (Anti-Rebote) ---
        # Variables para confirmar que un cambio de zona es real y no ruido.
        self.candidate_zone = 0
        self.zone_candidate_start_time = 0 
        # Tiempo que el atleta debe mantener la nueva intensidad para confirmar el cambio.
        self.MIN_TIME_IN_ZONE_S = 2.0

    def filter_signal(self, ecg_data):
         
        # ETAPA 1: Limpieza de Señal (DSP)
        # Aplica filtros digitales para aislar el complejo QRS del ruido ambiental.
        
        # Trabajamos sobre una copia para no alterar el buffer original de BrainFlow
        filtered_data = np.copy(ecg_data)
        
        # 1. Detrend: Elimina el componente DC (línea base) que varía por respiración/movimiento.
        DataFilter.detrend(filtered_data, DetrendOperations.CONSTANT.value)
        
        # 2. Bandpass (1.0Hz - 50.0Hz):
        # - Corte inferior (1Hz): Elimina deriva de línea base lenta.
        # - Corte superior (50Hz): Elimina ruido electromiográfico (EMG) de alta frecuencia.
        # Usamos Butterworth de orden 2 para un roll-off suave.
        DataFilter.perform_bandpass(filtered_data, self.sampling_rate, 1.0, 50.0, 2,
                                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        
        # 3. Notch Filters (Rechaza-Banda):
        # Eliminan la interferencia de la red eléctrica (50Hz Europa / 60Hz USA).
        # Aplicamos ambos por seguridad en entornos mixtos o desconocidos.
        DataFilter.perform_bandstop(filtered_data, self.sampling_rate, 48.0, 52.0, 2,
                                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        DataFilter.perform_bandstop(filtered_data, self.sampling_rate, 58.0, 62.0, 2,
                                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        
        return filtered_data

    def calculate_bpm(self, filtered_data):
        # ETAPAS 2, 3 y 4: Cálculo Robusto de BPM
        # Convierte la señal filtrada en un valor numérico estable.
        
        try:
            # --- ETAPA 2: Estimación Espectral (Welch) ---
            nperseg = len(filtered_data)
            # Necesitamos suficientes puntos para una resolución espectral decente
            if nperseg < 100: return self.current_bpm 
            
            # Calculamos la Densidad Espectral de Potencia (PSD)
            noverlap = nperseg // 2
            psd_data = DataFilter.get_psd_welch(
                filtered_data, nperseg, noverlap, 
                self.sampling_rate, WindowOperations.BLACKMAN_HARRIS.value
            )
            psd_amps = psd_data[0] # Amplitudes
            psd_freqs = psd_data[1] # Frecuencias (Eje X)

            # Limitamos la búsqueda a un rango fisiológico humano posible (45 - 230 BPM)
            # 0.75 Hz = 45 BPM
            # 3.80 Hz = 228 BPM
            min_idx = np.where(psd_freqs > 0.75)[0][0]
            max_idx = np.where(psd_freqs > 3.8)[0][0]

            # Encontramos la frecuencia con mayor energía (Pico dominante = Ritmo Cardíaco)
            peak_idx_band = np.argmax(psd_amps[min_idx:max_idx])
            peak_freq = psd_freqs[min_idx + peak_idx_band]
            raw_bpm_instant = peak_freq * 60.0

            # Validación básica de rango ("Sanity Check")
            if raw_bpm_instant < 40 or raw_bpm_instant > 240:
                return self.current_bpm

            #  ETAPA 3: Filtro de Mediana 
            # Agregamos el valor instantáneo al historial
            self.bpm_history.append(raw_bpm_instant)
            
            # Esperamos a tener suficientes datos para estadística confiable (mínimo 0.5s)
            if len(self.bpm_history) < 10:
                return self.current_bpm

            # La mediana ignora matemáticamente los valores extremos (ruido/artefactos).
            # Si el historial es [60, 61, 200, 62, 59], la mediana es ~60, ignorando el 200.
            median_bpm = float(np.median(self.bpm_history))

            # ETAPA 4: Suavizado Exponencial (EMA) 
            if self.ema_bpm == 0.0:
                self.ema_bpm = median_bpm
            else:
                # Fórmula EMA: Nuevo = (Actual * alpha) + (Anterior * (1-alpha))
                self.ema_bpm = (median_bpm * self.ema_alpha) + (self.ema_bpm * (1.0 - self.ema_alpha))

            # Actualizamos el estado global
            self.current_bpm = self.ema_bpm
            
            return self.current_bpm
            
        except Exception as e:
            # En caso de error matemático (ej. división por cero), mantenemos el último valor conocido
            # para no romper el flujo del programa.
            return self.current_bpm 

    def detect_zone_change(self, bpm):
        # ETAPA 5: Máquina de Estados de Zonas (Histéresis)
        # Determina la zona de esfuerzo (1-5) basada en % de FC Max.
        # Retorna: (bool: hubo_cambio, int: zona_anterior, int: zona_nueva)
        
        # 1. Clasificación Pura (Umbrales porcentuales)
        if bpm < (self.max_hr * 0.6): p_zone = 1      # Calentamiento (<60%)
        elif bpm < (self.max_hr * 0.7): p_zone = 2    # Aeróbica      (60-70%)
        elif bpm < (self.max_hr * 0.8): p_zone = 3    # Glicolitica 1 (70-80%)
        elif bpm < (self.max_hr * 0.9): p_zone = 4    # Glicolitica 2 (80-90%)
        else: p_zone = 5                              # Fosfagenica   (>90%)
        
        # CASO A: Seguimos en la misma zona actual
        if p_zone == self.current_zone:
            self.candidate_zone = 0
            self.zone_candidate_start_time = 0
            return (False, 0, 0)

        # CASO B: Detectamos una zona potencial distinta, pero es la primera vez (Inicia contador)
        if p_zone != self.candidate_zone:
            self.candidate_zone = p_zone
            self.zone_candidate_start_time = time.time()
            return (False, 0, 0)
        
        # CASO C: La zona potencial se mantiene estable (Evaluamos Histéresis)
        if p_zone == self.candidate_zone:
            elapsed = time.time() - self.zone_candidate_start_time
            
            # Solo confirmamos el cambio si la nueva zona se ha mantenido por X segundos
            if elapsed >= self.MIN_TIME_IN_ZONE_S:
                old = self.current_zone
                self.current_zone = self.candidate_zone # ¡Cambio Confirmado!
                
                # Reset de variables temporales
                self.candidate_zone = 0
                self.zone_candidate_start_time = 0
                
                return (True, old, self.current_zone)
        
        return (False, 0, 0)