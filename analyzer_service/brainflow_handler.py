import logging
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

class BrainflowHandler:
    def __init__(self, board_id=BoardIds.SYNTHETIC_BOARD.value, num_points=1024):
        BoardShim.enable_dev_board_logger()
        
        self.params = BrainFlowInputParams()
        self.board_id = board_id
        self.board_shim = BoardShim(self.board_id, self.params)
        
        self.num_points = num_points # Puntos a leer
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        
        try:
            all_ecg_channels = BoardShim.get_ecg_channels(self.board_id)
            self.ecg_channel = all_ecg_channels[0] 
            logging.info(f"Canal ECG a usar: {self.ecg_channel}")# Se toma solo el primer canal para el análisis principal
        except Exception as e:
            logging.warning(f"No se pudieron obtener canales ECG: {e}. Usando fallback [1].")
            self.ecg_channel = 1 # Fallback

    def start(self, age=30):
        logging.info("Preparando sesión de BrainFlow...")
        self.board_shim.prepare_session()
        
        # Configurar simulador
        logging.info(f"Configurando simulador con Edad: {age}")
        self.board_shim.config_board(f"AGE:{age}")
        
        logging.info("Iniciando stream...")
        self.board_shim.start_stream()
        logging.info("Stream iniciado.")

    def config_simulator_zone(self, zone):
        """ Envía comando de cambio de zona al simulador """
        if self.board_shim.is_prepared():
            logging.info(f"--- SIMULADOR: Enviando comando ZONE:{zone} ---")
            self.board_shim.config_board(f"ZONE:{zone}")

    def get_data(self):
        """ Obtiene los datos más recientes del canal ECG """
        data = self.board_shim.get_current_board_data(self.num_points)
        if data.shape[1] < self.num_points:
            return None # No hay suficientes datos nuevos, retornar None
        # Retorna solo los datos del canal ECG que nos interesa
        return data[self.ecg_channel] 

    def stop(self):
        if self.board_shim.is_prepared():
            logging.info('Liberando sesión de BrainFlow...')
            self.board_shim.release_session()