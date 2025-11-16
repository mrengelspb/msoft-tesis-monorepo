import argparse
import logging
import sys
import numpy as np  # Necesario para np.linspace
import pyqtgraph as pg
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, WindowOperations, DetrendOperations
from pyqtgraph.Qt import QtWidgets, QtCore


class Graph:
    def __init__(self, board_shim):
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self.board_id = board_shim.get_board_id()
        self.board_shim = board_shim
        
        try:
            self.ecg_channels = BoardShim.get_ecg_channels(self.board_id)
        except Exception as e:
            logging.warning(f"No se pudieron obtener canales ECG: {e}")
            self.ecg_channels = [1, 2, 3] # Fallback
            
        if not self.ecg_channels:
            logging.error("Esta placa no tiene canales ECG. Saliendo.")
            return

        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.update_speed_ms = 50
        self.window_size = 4  # 4 segundos de datos en pantalla
        self.num_points = self.window_size * self.sampling_rate

        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.win = pg.GraphicsLayoutWidget(title='Monitor ECG (BrainFlow)', size=(1000, 600), show=True)

        self._init_pens()
        self._init_timeseries()
        # Se eliminó _init_psd() para dar más espacio

        timer = QtCore.QTimer()
        timer.timeout.connect(self.update)
        timer.start(self.update_speed_ms)
        
        if not hasattr(sys, 'flags') or sys.flags.interactive == 0:
            QtWidgets.QApplication.instance().exec()


    def _init_pens(self):
        self.pens = list()
        self.brushes = list()
        colors = ['#A54E4E', '#A473B6', '#5B45A4'] 
        for i in range(len(colors)):
            pen = pg.mkPen({'color': colors[i], 'width': 2})
            self.pens.append(pen)
            brush = pg.mkBrush(colors[i])
            self.brushes.append(brush)

    def _init_timeseries(self):
        self.plots = list()
        self.curves = list()
        
        # --- CAMBIO 2: Crear el eje de Tiempo (X) ---
        # Crea un array que va de 0 a 4 (segundos), con 1000 puntos
        self.time_axis = np.linspace(0, self.window_size, self.num_points, endpoint=False)
        
        for i in range(len(self.ecg_channels)):
            # --- CAMBIO 3: Gráfico ocupa toda la ventana ---
            p = self.win.addPlot(row=i, col=0)
            
            # --- CAMBIOS 3 y 1: Mostrar ejes y etiquetas ---
            p.showAxis('left', True)
            p.setLabel('left', 'Amplitud (mV)')
            p.showAxis('bottom', True)
            p.setLabel('bottom', 'Tiempo (s)')
            
            # --- CAMBIO 3: Fijar el eje Y para look profesional ---
            # La señal sintética es ~1mV. Ajusta esto si ves que la señal es más grande.
            p.setYRange(-1.5, 1.5) 
            
            if i == 0:
                p.setTitle(f'ECG Canal {self.ecg_channels[i]}')
            else:
                 p.setTitle(f'Canal {self.ecg_channels[i]}')
            
            self.plots.append(p)
            curve = p.plot(pen=self.pens[i % len(self.pens)])
            self.curves.append(curve)

    def update(self):
        data = self.board_shim.get_current_board_data(self.num_points)
        
        for count, channel in enumerate(self.ecg_channels):
            if data.shape[1] < self.num_points:
                continue

            # --- Filtrado (sin cambios) ---
            DataFilter.detrend(data[channel], DetrendOperations.CONSTANT.value)
            DataFilter.perform_bandpass(data[channel], self.sampling_rate, 1.0, 40.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            DataFilter.perform_bandstop(data[channel], self.sampling_rate, 48.0, 52.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            DataFilter.perform_bandstop(data[channel], self.sampling_rate, 58.0, 62.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

            # --- CAMBIO 1: Convertir a Milivoltios (mV) ---
            # BrainFlow da los datos en microvoltios (uV)
            data_mv = data[channel] / 1000.0

            # --- CAMBIO 2: Usar eje de tiempo (X) y eje de mV (Y) ---
            self.curves[count].setData(x=self.time_axis, y=data_mv)


        self.app.processEvents()


def main():
    # ... (El código de main() no necesita cambios) ...
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, help='timeout for device discovery or connection', required=False,
                        default=0)
    parser.add_argument('--ip-port', type=int, help='ip port', required=False, default=0)
    parser.add_argument('--ip-protocol', type=int, help='ip protocol, check IpProtocolType enum', required=False,
                        default=0)
    parser.add_argument('--ip-address', type=str, help='ip address', required=False, default='')
    parser.add_argument('--serial-port', type=str, help='serial port', required=False, default='')
    parser.add_argument('--mac-address', type=str, help='mac address', required=False, default='')
    parser.add_argument('--other-info', type=str, help='other info', required=False, default='')
    parser.add_argument('--streamer-params', type=str, help='streamer params', required=False, default='')
    parser.add_argument('--serial-number', type=str, help='serial number', required=False, default='')
    parser.add_argument('--board-id', type=int, help='board id, check docs to get a list of supported boards',
                        required=False, default=BoardIds.SYNTHETIC_BOARD.value) 
    parser.add_argument('--file', type=str, help='file', required=False, default='')
    parser.add_argument('--master-board', type=int, help='master board id for streaming and playback boards',
                        required=False, default=BoardIds.NO_BOARD.value)
    args = parser.parse_args()

    params = BrainFlowInputParams()
    params.ip_port = args.ip_port
    params.serial_port = args.serial_port
    params.mac_address = args.mac_address
    params.other_info = args.other_info
    params.serial_number = args.serial_number
    params.ip_address = args.ip_address
    params.ip_protocol = args.ip_protocol
    params.timeout = args.timeout
    params.file = args.file
    params.master_board = args.master_board

    board_shim = BoardShim(args.board_id, params)
    
    try:
        board_shim.prepare_session()
        board_shim.start_stream(450000, args.streamer_params)
        Graph(board_shim) 
    except BaseException as e:
        logging.warning('Exception', exc_info=True)
    finally:
        if board_shim.is_prepared():
            logging.info('Releasing session')
            board_shim.release_session()


if __name__ == '__main__':
    main()