import argparse
import logging
import sys
import numpy as np 
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
            all_ecg_channels = BoardShim.get_ecg_channels(self.board_id)
            self.ecg_channels = all_ecg_channels[:2] 
            
            if len(self.ecg_channels) < 2:
                logging.error("Esta placa no tiene al menos 2 canales ECG. Saliendo.")
                return

        except Exception as e:
            logging.warning(f"No se pudieron obtener canales ECG: {e}")
            self.ecg_channels = [1, 2] 
            
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.update_speed_ms = 50
        self.window_size = 4 
        self.num_points = self.window_size * self.sampling_rate

        # --- CAMBIO 1: Añadir variables para BPM ---
        self.bpm = 0.0 # Variable para almacenar el BPM
        # Parámetro para el cálculo de HR (Tamaño de FFT)
        self.hr_psd_size = DataFilter.get_nearest_power_of_two(self.sampling_rate)

        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        # Hacemos la ventana un poco más alta para el título
        self.win = pg.GraphicsLayoutWidget(title='Monitor ECG (2 Canales)', size=(1000, 450), show=True)

        self._init_pens()
        self._init_timeseries()

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
        
        self.time_axis = np.linspace(0, self.window_size, self.num_points, endpoint=False)
        
        for i in range(len(self.ecg_channels)):
            p = self.win.addPlot(row=i, col=0)
            
            p.showAxis('left', True)
            p.setLabel('left', 'Amplitud (mV)')
            p.showAxis('bottom', True)
            p.setLabel('bottom', 'Tiempo (s)')
            
            p.setYRange(-1.5, 1.5) 
            
            # --- CAMBIO 2: Título inicial ---
            if i == 0:
                p.setTitle(f'ECG Canal {self.ecg_channels[i]}  |  BPM: Calculando...')
            else:
                p.setTitle(f'ECG Canal {self.ecg_channels[i]}')
            
            self.plots.append(p)
            curve = p.plot(pen=self.pens[i % len(self.pens)])
            self.curves.append(curve)

    def update(self):
        # Obtenemos los últimos 4 segundos de datos
        data = self.board_shim.get_current_board_data(self.num_points)
        
        for count, channel in enumerate(self.ecg_channels):
            if data.shape[1] < self.num_points:
                # Esperando que el búfer se llene al inicio
                continue
            
            # --- 1. Filtrado (sin cambios) ---
            # ¡Importante! Los filtros se aplican IN-PLACE (modifican data[channel])
            DataFilter.detrend(data[channel], DetrendOperations.CONSTANT.value)
            DataFilter.perform_bandpass(data[channel], self.sampling_rate, 1.0, 40.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            DataFilter.perform_bandstop(data[channel], self.sampling_rate, 48.0, 52.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            DataFilter.perform_bandstop(data[channel], self.sampling_rate, 58.0, 62.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

            # --- CAMBIO 3: Cálculo de BPM ---
            if count == 0: # Calcular solo usando el primer canal
                try:
                    # Usamos los datos ya filtrados (data[channel]) para el cálculo
                    # Esta función estima el BPM usando análisis de frecuencia (PSD)
                    self.bpm = DataFilter.get_heart_rate(data[channel], 
                                                         self.sampling_rate, 
                                                         self.hr_psd_size, 
                                                         self.hr_psd_size // 2)
                except Exception as e:
                    logging.warning(f"No se pudo calcular BPM: {e}")
                    # Si falla, simplemente mantenemos el último valor de self.bpm
                    pass 
                
                # Actualizar el título del primer gráfico
                # .2f formatea el número a 2 decimales
                self.plots[0].setTitle(f'ECG Canal {self.ecg_channels[0]}  |  BPM: {self.bpm:.2f}')

            # --- 4. Graficado (en mV) ---
            data_mv = data[channel] / 1000.0
            self.curves[count].setData(x=self.time_axis, y=data_mv)

        # Procesar eventos de la GUI
        self.app.processEvents()


def main():
    # ... (El código de main() no necesita cambios) ...
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    # (argumentos...)
    parser.add_argument('--timeout', type=int, help='timeout for device discovery or connection', required=False,
                        default=0)
    parser.add_argument('--ip-port', type=int, help='ip port', required=False, default=0)
    parser.add_argument('--ip-protocol', type=int, help='ip protocol, check IpProtocolType enum', required=False,
                        default=0)
    parser.add_argument('--ip-address', type=str, help='ip address', required=False, default='')
    parser.add_argument('--serial-port', type=str, help='serial port', required=False, default='')
    parser.add_font_color = '#FFFFFF'
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