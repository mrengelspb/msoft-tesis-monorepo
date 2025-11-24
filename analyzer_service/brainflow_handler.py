import logging
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

"""
-----------------------------------------------------------------------------
SUBSYSTEM: HARDWARE ABSTRACTION LAYER (HAL)
-----------------------------------------------------------------------------
Descripción:
Esta clase actúa como el controlador de bajo nivel del sistema.
Encapsula la complejidad de la librería BrainFlow (C++) y expone una API
simple para que el servicio de análisis pueda iniciar, detener y configurar
el hardware de adquisición de señales.

Características Clave:
- Soporte Multi-Placa: Diseñado para funcionar con placas reales (Cyton/Ganglion)
  o simuladas como en nuestro caso: Synthetic Board.
- Inyección de Comandos: Permite enviar strings de configuración dinámicos
  al núcleo C++ (vital para la simulación de zonas de la tesis).
- Gestión de Canales: Detecta automáticamente en qué canal físico viaja el ECG.
-----------------------------------------------------------------------------
"""

class BrainflowHandler:
    def __init__(self, board_id=BoardIds.SYNTHETIC_BOARD.value, num_points=1024):
        # Habilitamos logs internos de BrainFlow para depuración profunda del driver C++
        BoardShim.enable_dev_board_logger()
        
        self.params = BrainFlowInputParams()
        self.board_id = board_id
        
        # Instancia del controlador principal (Bridge Python <-> C++)
        self.board_shim = BoardShim(self.board_id, self.params)
        
        self.num_points = num_points
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        
        # AUTO-DETECCIÓN DE CANALES
        # Diferentes placas envían el ECG en diferentes índices del array.
        # BrainFlow nos permite consultar metadata para no "adivinar" el índice.
        try:
            all_ecg_channels = BoardShim.get_ecg_channels(self.board_id)
            # Tomamos el primer canal ECG disponible (Lead I)
            self.ecg_channel = all_ecg_channels[0] 
            logging.info(f"Hardware inicializado. Canal ECG en índice: {self.ecg_channel}")
        except Exception as e:
            # Fallback de seguridad por si la placa no reporta canales ECG explícitos
            logging.warning(f"No se detectaron canales ECG nativos ({e}). Usando canal por defecto [1].")
            self.ecg_channel = 1 

    def start(self, age=30):
        # Inicia la sesión de streaming.
        # Envía parámetros iniciales al driver C++ (ej. Edad para simulador).
        
        logging.info("Iniciando sesión BrainFlow (C++ Core)...")
        
        # 1. Prepara memoria y buffers en el lado de C++
        self.board_shim.prepare_session()
        
        # 2. Configuración Inicial
        # Enviamos el comando "AGE:XX" que implementamos en synthetic_board.cpp
        # Esto ajusta la FC Máxima base del simulador interno.
        self.board_shim.config_board(f"AGE:{age}")
        
        # 3. Arrancar adquisición de datos
        self.board_shim.start_stream()
        logging.info("Stream de datos activo.")

    def config_simulator_zone(self, zone):
        # INTERFAZ DE SIMULACIÓN:
        # Envía el comando personalizado 'ZONE:X' al driver compilado.
        # Esto altera instantáneamente la frecuencia de generación de ondas
        # en el código nativo para simular esfuerzo físico.

        if self.board_shim.is_prepared():
            logging.info(f"--- HARDWARE: Enviando comando ZONE:{zone} ---")
            # Este string viaja hasta 'synthetic_board.cpp' -> 'config_board()'
            self.board_shim.config_board(f"ZONE:{zone}")

    def get_data(self):
        # Obtiene una ventana deslizante de los últimos N datos.
        
        # Se usa 'get_current_board_data', el cual obtiene los datos 
        # MÁS RECIENTES sin borrarlos del buffer interno. Esto es ideal para 
        # ventanas deslizantes (Sliding Windows) en procesamiento de tiempo real.
         
        # Obtenemos matriz [num_canales x num_puntos]
        data = self.board_shim.get_current_board_data(self.num_points)
        
        # Validación de buffer lleno (para evitar errores al inicio)
        if data.shape[1] < self.num_points:
            return None 
            
        # Retornamos SOLO la fila correspondiente al canal ECG seleccionado
        return data[self.ecg_channel] 

    def stop(self):
        # Libera recursos y cierra la conexión con la placa
        if self.board_shim.is_prepared():
            logging.info('Deteniendo BrainFlow y liberando driver...')
            try:
                self.board_shim.release_session()
            except:
                pass # Evita crash si ya estaba cerrado