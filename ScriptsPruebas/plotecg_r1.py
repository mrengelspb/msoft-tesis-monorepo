import argparse
import logging
import sys  # Necesario para QApplication

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
        
        # --- CAMBIO 1: Obtener canales de ECG ---
        # Usamos get_ecg_channels() en lugar de get_exg_channels()
        # La SYNTHETIC_BOARD tiene 3 canales de ECG.
        try:
            self.ecg_channels = BoardShim.get_ecg_channels(self.board_id)
        except Exception as e:
            logging.warning(f"No se pudieron obtener canales ECG para la placa {self.board_id}: {e}")
            logging.warning("Usando canales EEG como alternativa (canales 1, 2, 3)")
            # Fallback por si acaso, aunque SYNTHETIC sí tiene.
            self.ecg_channels = [1, 2, 3] 
            
        if not self.ecg_channels:
            logging.error("Esta placa no tiene canales ECG. Saliendo.")
            return

        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.update_speed_ms = 50
        self.window_size = 10  # 4 segundos de datos en pantalla
        self.num_points = self.window_size * self.sampling_rate

        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.win = pg.GraphicsLayoutWidget(title='BrainFlow Plot (ECG)', size=(800, 600), show=True)

        self._init_pens()
        self._init_timeseries()
        self._init_psd()
        # --- CAMBIO 2: Gráfico de bandas EEG eliminado ---
        # self._init_band_plot() # Eliminado

        timer = QtCore.QTimer()
        timer.timeout.connect(self.update)
        timer.start(self.update_speed_ms)
        
        # Iniciar el bucle de eventos de la aplicación
        if not hasattr(sys, 'flags') or sys.flags.interactive == 0:
            QtWidgets.QApplication.instance().exec()


    def _init_pens(self):
        # Esta función no necesita cambios
        self.pens = list()
        self.brushes = list()
        colors = ['#A54E4E', '#A473B6', '#5B45A4'] # 3 colores para 3 canales ECG
        for i in range(len(colors)):
            pen = pg.mkPen({'color': colors[i], 'width': 2})
            self.pens.append(pen)
            brush = pg.mkBrush(colors[i])
            self.brushes.append(brush)

    def _init_timeseries(self):
        self.plots = list()
        self.curves = list()
        # Usamos self.ecg_channels
        for i in range(len(self.ecg_channels)):
            p = self.win.addPlot(row=i, col=0)
            p.showAxis('left', False)
            p.setMenuEnabled('left', False)
            p.showAxis('bottom', False)
            p.setMenuEnabled('bottom', False)
            if i == 0:
                p.setTitle(f'ECG TimeSeries (Canal {self.ecg_channels[i]})')
            else:
                 p.setTitle(f'Canal {self.ecg_channels[i]}')
            self.plots.append(p)
            curve = p.plot(pen=self.pens[i % len(self.pens)])
            self.curves.append(curve)

    def _init_psd(self):
        # Ajustamos el layout para que ocupe el espacio del gráfico de bandas
        self.psd_plot = self.win.addPlot(row=0, col=1, rowspan=len(self.ecg_channels))
        self.psd_plot.showAxis('left', False)
        self.psd_plot.setMenuEnabled('left', False)
        self.psd_plot.setTitle('PSD Plot (Densidad Espectral de Potencia)')
        self.psd_plot.setLogMode(False, True) # Eje Y logarítmico
        self.psd_curves = list()
        self.psd_size = DataFilter.get_nearest_power_of_two(self.sampling_rate)
        
        # Usamos self.ecg_channels
        for i in range(len(self.ecg_channels)):
            psd_curve = self.psd_plot.plot(pen=self.pens[i % len(self.pens)])
            psd_curve.setDownsampling(auto=True, method='mean', ds=3)
            self.psd_curves.append(psd_curve)

    # --- CAMBIO 2: Gráfico de bandas EEG eliminado ---
    # def _init_band_plot(self):
    #   ... (Toda esta función fue eliminada) ...

    def update(self):
        # Obtenemos los últimos N puntos (definidos por num_points)
        data = self.board_shim.get_current_board_data(self.num_points)
        
        # Iteramos sobre los canales de ECG
        for count, channel in enumerate(self.ecg_channels):
            if data.shape[1] < self.num_points:
                # Esperando que el búfer se llene al inicio
                continue

            # --- CAMBIO 3: Filtros de ECG ---
            
            # 1. Detrend: Elimina la deriva de la línea base (baseline wander)
            DataFilter.detrend(data[channel], DetrendOperations.CONSTANT.value)
            
            # 2. Pasa-Banda: Filtro para ECG, ej. 1Hz-40Hz
            #    Elimina ruido de muy baja frecuencia (respiración)
            #    y ruido de alta frecuencia (muscular).
            DataFilter.perform_bandpass(data[channel], self.sampling_rate, 1.0, 40.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            
            # 3. Notch (Band-Stop): Elimina el ruido de la línea eléctrica (50Hz o 60Hz)
            DataFilter.perform_bandstop(data[channel], self.sampling_rate, 48.0, 52.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0) # Filtro 50Hz
            DataFilter.perform_bandstop(data[channel], self.sampling_rate, 58.0, 62.0, 2,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0) # Filtro 60Hz

            # Actualizar el gráfico de la serie temporal (ECG)
            self.curves[count].setData(data[channel].tolist())

            # --- Cálculo de PSD (sin cambios en la lógica) ---
            if data.shape[1] > self.psd_size:
                psd_data = DataFilter.get_psd_welch(data[channel], self.psd_size, self.psd_size // 2,
                                                    self.sampling_rate,
                                                    WindowOperations.BLACKMAN_HARRIS.value)
                
                # Limitar el gráfico de PSD a 70Hz (rango de interés)
                lim = min(70, len(psd_data[0]))
                self.psd_curves[count].setData(psd_data[1][0:lim].tolist(), psd_data[0][0:lim].tolist())

            # --- CAMBIO 2: Cálculo de bandas EEG eliminado ---
            # avg_bands[0] = ... (Toda esta sección fue eliminada) ...

        # --- CAMBIO 2: Actualización de bandas EEG eliminada ---
        # self.band_bar.setOpts(height=avg_bands) 

        # Procesar eventos de la GUI para que se actualice
        self.app.processEvents()


def main():
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.DEBUG)

    # El parser no necesita cambios, ya que --board-id
    # por defecto es SYNTHETIC_BOARD.
    parser = argparse.ArgumentParser()
    # ... (todos los argumentos se quedan igual) ...
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
                        required=False, default=BoardIds.SYNTHETIC_BOARD.value) # .value es más explícito
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

    # El board_id por defecto será -1 (SYNTHETIC_BOARD)
    board_shim = BoardShim(args.board_id, params)
    
    try:
        board_shim.prepare_session()
        board_shim.start_stream(450000, args.streamer_params)
        Graph(board_shim) # Inicia la GUI
    except BaseException as e:
        logging.warning('Exception', exc_info=True)
    finally:
        if board_shim.is_prepared():
            logging.info('Releasing session')
            board_shim.release_session()


if __name__ == '__main__':
    main()