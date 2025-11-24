import logging
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

class BrainflowHandler:
    def __init__(self, board_id=BoardIds.SYNTHETIC_BOARD.value, num_points=1024):
        # Habilito el logger interno de la placa para depuración
        BoardShim.enable_dev_board_logger()
        
        self.params = BrainFlowInputParams()
        self.board_id = board_id
        self.board_shim = BoardShim(self.board_id, self.params)
        
        self.num_points = num_points # Defino cuántos puntos voy a leer en cada ciclo
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        
        try:
            # Intento obtener automáticamente los canales de ECG de la placa seleccionada
            all_ecg_channels = BoardShim.get_ecg_channels(self.board_id)
            self.ecg_channel = all_ecg_channels[0] 
            logging.info(f"He seleccionado el canal ECG: {self.ecg_channel}") # Tomo solo el primer canal para mi análisis
        except Exception as e:
            logging.warning(f"No se puede obtener canales ECG automáticamente: {e}. Se usa  fallback [1].")
            self.ecg_channel = 1 # Uso un canal por defecto si falla la detección

    def start(self, age=30):
        logging.info("Preparando la sesión de BrainFlow...")
        self.board_shim.prepare_session()
        
        # Configuro el simulador sintético con la edad específica del usuario
        logging.info(f"Configurando el simulador con Edad: {age}")
        self.board_shim.config_board(f"AGE:{age}")
        
        logging.info("Iniciando el stream de datos...")
        self.board_shim.start_stream()
        logging.info("Stream iniciado correctamente.")

    def config_simulator_zone(self, zone):
        """ Envío un comando explícito de cambio de zona al simulador """
        if self.board_shim.is_prepared():
            logging.info(f"--- SIMULADOR: Estoy enviando comando ZONE:{zone} ---")
            self.board_shim.config_board(f"ZONE:{zone}")

    def get_data(self):
        """ Obtengo los datos más recientes del buffer de la placa """
        data = self.board_shim.get_current_board_data(self.num_points)
        
        # Verifico si tengo suficientes puntos para procesar
        if data.shape[1] < self.num_points:
            return None # No tengo suficientes datos nuevos, retorno None
            
        # Retorno únicamente los datos del canal ECG que necesito
        return data[self.ecg_channel] 

    def stop(self):
        # Si la sesión está activa, libero los recursos
        if self.board_shim.is_prepared():
            logging.info('Estoy liberando la sesión de BrainFlow...')
            self.board_shim.release_session()