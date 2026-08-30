import struct
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class TabDetect(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # Polar Plot
        self.polar = pg.PlotWidget()
        self.polar.setAspectLocked(True)
        self.polar.setXRange(-100, 100)
        self.polar.setYRange(-100, 100)
        self.polar.showGrid(x=True, y=True)

        # configuration for the polar plot
        plot_item = self.polar.getPlotItem()
        plot_item.setLabel('bottom', 'distance', units='m')    # x‑axis
        plot_item.setLabel('left',   'distance', units='m')    # y‑axis
        plot_item.setTitle('Angular and Distance Plot')

        for r in [25, 50, 75, 100]:
            circle = pg.QtWidgets.QGraphicsEllipseItem(-r, -r, 2*r, 2*r)
            circle.setPen(pg.mkPen('gray'))
            self.polar.addItem(circle)

        self.point = self.polar.plot(pen=None, symbol='o', symbolBrush='r')
        self.line = self.polar.plot(pen=pg.mkPen('r', width=2))

        layout.addWidget(self.polar)

        # Distance Plot
        self.dist_plot = pg.PlotWidget()
        self.dist_plot.setYRange(0, 200)
        self.dist_plot.showGrid(x=True, y=True)
        self.dist_curve = self.dist_plot.plot(pen='r')
        self.dist_history = []

        # configuration for the distance plot
        plot_item = self.dist_plot.getPlotItem()
        plot_item.setLabel('bottom', 'samples', units='')      # x‑axis
        plot_item.setLabel('left',   'distance', units='m')    # y‑axis
        plot_item.setTitle('Distance Plot')

        layout.addWidget(self.dist_plot)

         # Confidence Plot
        self.plot_conf = pg.PlotWidget()
        self.plot_conf.setYRange(0, 1)
        self.curve_conf = self.plot_conf.plot(pen='y')
        self.conf_history = []

        self.plot_conf.getPlotItem().setLabel('bottom', 'time', units='s')
        self.plot_conf.getPlotItem().setLabel('left', 'confidence', units='')
        self.plot_conf.getPlotItem().setTitle('Detection Confidence')

        layout.addWidget(self.plot_conf)

    def update_frame(self, frame: bytes):
        timestamp = struct.unpack_from("<I", frame, 8)[0]
        mic      = struct.unpack_from("<I", frame, 12)[0]
        azi      = struct.unpack_from("<f", frame, 16)[0]
        dist     = struct.unpack_from("<f", frame, 20)[0]
        conf     = struct.unpack_from("<f", frame, 24)[0]

        rad = np.deg2rad(azi)
        x = dist * np.sin(rad)
        y = dist * np.cos(rad)

        # Update polar plot
        self.point.setData([x], [y])
        self.line.setData([0, x], [0, y])

        # Update distance plot
        self.dist_history.append(dist)
        if len(self.dist_history) > 200:
            self.dist_history.pop(0)

        self.dist_curve.setData(self.dist_history)

        # Update confidence plot
        self.conf_history.append(conf)
        if len(self.conf_history) > 200:
            self.conf_history.pop(0)

        self.curve_conf.setData(self.conf_history)
        
