import struct
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout

from app.usb.messages import BAND_LO_HZ, BAND_WIDTH_HZ, N_BANDS, UnitReport

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

        # UnitReport (Id 5): Zeit, Qualität, akustischer Zustand p_b je Band
        self.unit_label = QLabel("UnitReport: –")
        layout.addWidget(self.unit_label)
        self.plot_state = pg.PlotWidget()
        self.plot_state.setYRange(0, 1)
        self.plot_state.setXRange(-0.5, N_BANDS - 0.5)
        pi = self.plot_state.getPlotItem()
        pi.setLabel('bottom', 'Band b (Beginn 80 Hz + b · 62,5 Hz)')
        pi.setLabel('left', 'p_b')
        pi.setTitle('Akustischer Zustand (selektierte Bänder)')
        self.state_bars = pg.BarGraphItem(x=np.arange(N_BANDS), height=np.zeros(N_BANDS), width=0.8, brush='c')
        self.plot_state.addItem(self.state_bars)
        layout.addWidget(self.plot_state)
        self.last_unit_report = None

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

    def update_unit_report(self, r: UnitReport):
        self.last_unit_report = r
        bands = ", ".join(f"{b} ({BAND_LO_HZ + b * BAND_WIDTH_HZ:.0f} Hz)" for b in r.bands[:6])
        if len(r.bands) > 6:
            bands += f", … ({len(r.bands)})"
        self.unit_label.setText(
            f"UnitReport  Unit 0x{r.unit:04X}   {r.time_text()}  [{r.source_name}]\n"
            f"Peilung {r.bearing_deg:.1f}°   Paare {r.pairs}   Residuum {r.residual_s * 1e6:.1f} µs   "
            f"Pegel {r.level:.3g}   Bänder: {bands or '–'}")
        self.state_bars.setOpts(height=np.array(r.state_vector()))
