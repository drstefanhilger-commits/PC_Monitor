"""
Detect-Tab (Betriebsart DETECT)

Azimut-Konvention (SDS_110 Infrastructure/Utils/Azimuth.hpp, FSL9 FIG. 5): 0° = Nord, im
Uhrzeigersinn, Mikrofon 0 zeigt nach Nord. Der Lageplan zeigt Nord oben und Ost rechts:
x = r · sin(φ) (Ost), y = r · cos(φ) (Nord).
"""
import struct
from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.usb.messages import BAND_LO_HZ, BAND_WIDTH_HZ, N_BANDS, UnitReport

RANGES_M = (25, 50, 100, 200, 500, 1000, 2000, 5000)     # Anzeigeradien (automatisch gewählt)
TRAIL = 60                                               # zuletzt angezeigte Positionen
HISTORY = 200


def compass_xy(azimuth_deg: float, r: float):
    """Azimut (0° = Nord, im Uhrzeigersinn) und Distanz -> (Ost, Nord) in m."""
    a = np.deg2rad(azimuth_deg)
    return float(r * np.sin(a)), float(r * np.cos(a))


def choose_range(distances) -> float:
    """Kleinster Anzeigeradius, der 110 % der größten Distanz fasst."""
    need = 1.1 * max([d for d in distances if np.isfinite(d)] or [0.0])
    for r in RANGES_M:
        if need <= r:
            return float(r)
    return float(RANGES_M[-1])


class TabDetect(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        top = QHBoxLayout()

        # --- Lageplan: Nord oben, Ost rechts ---------------------------------------------
        self.polar = pg.PlotWidget()
        self.polar.setAspectLocked(True)
        self.polar.setMouseEnabled(x=False, y=False)
        self.polar.hideButtons()
        pi = self.polar.getPlotItem()
        pi.setLabel('bottom', 'Ost', units='m')
        pi.setLabel('left', 'Nord', units='m')
        pi.setTitle('Lageplan (0° = Nord, im Uhrzeigersinn)')
        self._grid_items = []
        self.range_m = None
        self.trail = self.polar.plot(pen=None, symbol='o', symbolSize=5,
                                     symbolBrush=pg.mkBrush(255, 120, 120, 90), symbolPen=None)
        self.line = self.polar.plot(pen=pg.mkPen('r', width=2))
        self.point = self.polar.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='r')
        self.trail_xy = deque(maxlen=TRAIL)
        self._set_range(RANGES_M[1])
        top.addWidget(self.polar, 3)

        # --- Verläufe --------------------------------------------------------------------
        right = QVBoxLayout()
        self.pos_label = QLabel("Azimut –   Distanz –")
        self.pos_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        right.addWidget(self.pos_label)
        self.dist_plot = pg.PlotWidget()
        self.dist_plot.showGrid(x=True, y=True)
        self.dist_curve = self.dist_plot.plot(pen='r')
        self.dist_history = deque(maxlen=HISTORY)
        p = self.dist_plot.getPlotItem()
        p.setLabel('bottom', 'Report')
        p.setLabel('left', 'Distanz', units='m')
        p.setTitle('Distanz (Pegelmodell)')
        p.enableAutoRange(axis='y')
        right.addWidget(self.dist_plot)

        self.az_plot = pg.PlotWidget()
        self.az_plot.setYRange(0, 360)
        self.az_plot.showGrid(x=True, y=True)
        self.az_curve = self.az_plot.plot(pen=None, symbol='o', symbolSize=3, symbolBrush='c')
        self.az_history = deque(maxlen=HISTORY)
        p = self.az_plot.getPlotItem()
        p.setLabel('bottom', 'Report')
        p.setLabel('left', 'Azimut', units='°')
        p.setTitle('Azimut')
        right.addWidget(self.az_plot)

        self.plot_conf = pg.PlotWidget()
        self.plot_conf.setYRange(0, 1)
        self.curve_conf = self.plot_conf.plot(pen='y')
        self.conf_history = deque(maxlen=HISTORY)
        p = self.plot_conf.getPlotItem()
        p.setLabel('bottom', 'Report')
        p.setLabel('left', 'Konfidenz')
        p.setTitle('Konfidenz')
        right.addWidget(self.plot_conf)
        top.addLayout(right, 2)
        layout.addLayout(top, 3)

        # --- UnitReport (Id 5): Zeit, Qualität, akustischer Zustand p_b je Band ----------
        self.unit_label = QLabel("UnitReport: –")
        layout.addWidget(self.unit_label)
        self.plot_state = pg.PlotWidget()
        self.plot_state.setYRange(0, 1)
        self.plot_state.setXRange(-0.5, N_BANDS - 0.5)
        ps = self.plot_state.getPlotItem()
        ps.setLabel('bottom', 'Band b (Beginn 80 Hz + b · 62,5 Hz)')
        ps.setLabel('left', 'p_b')
        ps.setTitle('Akustischer Zustand (selektierte Bänder)')
        self.state_bars = pg.BarGraphItem(x=np.arange(N_BANDS), height=np.zeros(N_BANDS), width=0.8, brush='c')
        self.plot_state.addItem(self.state_bars)
        layout.addWidget(self.plot_state, 1)
        self.last_unit_report = None

    # ------------------------------------------------------------
    def _set_range(self, r: float):
        """Ringe, Strahlen und Himmelsrichtungen für Radius r zeichnen."""
        if r == self.range_m:
            return
        self.range_m = r
        for it in self._grid_items:
            self.polar.removeItem(it)
        self._grid_items = []
        pen = pg.mkPen((110, 110, 110), width=1)
        for k in (1, 2, 3, 4):
            rr = r * k / 4
            c = pg.QtWidgets.QGraphicsEllipseItem(-rr, -rr, 2 * rr, 2 * rr)
            c.setPen(pen)
            self.polar.addItem(c)
            self._grid_items.append(c)
            t = pg.TextItem(f"{rr:g} m", color=(150, 150, 150), anchor=(0, 1))
            t.setPos(*compass_xy(45, rr))
            self.polar.addItem(t)
            self._grid_items.append(t)
        for az in range(0, 360, 30):
            x, y = compass_xy(az, r)
            ln = self.polar.plot([0, x], [0, y], pen=pg.mkPen((80, 80, 80), width=1))
            self._grid_items.append(ln)
        for name, az in (("N", 0), ("O", 90), ("S", 180), ("W", 270)):
            t = pg.TextItem(name, color='w', anchor=(0.5, 0.5))
            t.setPos(*compass_xy(az, r * 1.08))
            self.polar.addItem(t)
            self._grid_items.append(t)
        m = r * 1.15
        self.polar.setXRange(-m, m, padding=0)
        self.polar.setYRange(-m, m, padding=0)

    def update_frame(self, frame: bytes):
        _ts, _unit = struct.unpack_from("<II", frame, 8)
        azi, dist, conf = struct.unpack_from("<fff", frame, 16)
        x, y = compass_xy(azi, dist)
        self.trail_xy.append((x, y))
        self.dist_history.append(dist)
        self.az_history.append(azi % 360.0)
        self.conf_history.append(conf)

        self._set_range(choose_range(self.dist_history))
        self.point.setData([x], [y])
        self.line.setData([0, x], [0, y])
        tx, ty = zip(*self.trail_xy)
        self.trail.setData(list(tx), list(ty))
        self.dist_curve.setData(list(self.dist_history))
        self.az_curve.setData(list(self.az_history))
        self.curve_conf.setData(list(self.conf_history))
        self.pos_label.setText(f"Azimut {azi % 360.0:5.1f}°   Distanz {dist:6.1f} m   Konfidenz {conf:.2f}")

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
