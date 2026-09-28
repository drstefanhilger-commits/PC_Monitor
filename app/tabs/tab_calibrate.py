"""
Calibrate-Tab (Betriebsart CALIBRATE): Nordabgleich der Sensoreinheit
(SDS_110 doc/ICD_SDS_PC_Monitor.md 4.4, Kommando Id 9; Logik in app/calibration.py).

Im Modus CALIBRATE verarbeitet die Firmware wie in DETECT und sendet UnitReports (Id 5).
Der Tab sammelt deren Peilungen, während eine Referenzquelle mit bekanntem Azimut läuft,
und schlägt den Offset vor. „Übernehmen“ sendet ihn (Signal offset_apply); das Hauptfenster
speichert ihn und sendet ihn bei jedem Verbinden erneut.
"""
import time

import pyqtgraph as pg
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                             QProgressBar, QPushButton, QVBoxLayout, QWidget)

from app.calibration import NorthCalibration


class TabCalibrate(QWidget):
    offset_apply = pyqtSignal(float)          # neuer Offset in Grad

    TICK_MS = 100

    def __init__(self, parent=None, clock=time.monotonic):
        super().__init__(parent)
        self.clock = clock
        self.cal = NorthCalibration()
        self.offset_deg = 0.0                 # zuletzt übernommener (gespeicherter) Offset
        self.result = None

        lay = QHBoxLayout(self)
        left = QVBoxLayout()

        # --- Einstellungen ------------------------------------------------
        g = QGroupBox("Nordabgleich")
        f = QFormLayout(g)
        self.offset_label = QLabel()
        f.addRow("Offset am Board:", self.offset_label)
        self.ref_spin = QDoubleSpinBox()
        self.ref_spin.setRange(0.0, 359.99)
        self.ref_spin.setDecimals(2)
        self.ref_spin.setWrapping(True)
        self.ref_spin.setSuffix(" °")
        self.ref_spin.setToolTip("Azimut der Referenzquelle, 0° = Nord, im Uhrzeigersinn")
        f.addRow("Azimut der Referenzquelle:", self.ref_spin)
        self.dur_spin = QDoubleSpinBox()
        self.dur_spin.setRange(1.0, 60.0)
        self.dur_spin.setValue(5.0)
        self.dur_spin.setSuffix(" s")
        f.addRow("Messdauer:", self.dur_spin)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        f.addRow("Fortschritt:", self.progress)
        left.addWidget(g)

        b = QHBoxLayout()
        self.start_btn = QPushButton("Messung starten")
        self.start_btn.clicked.connect(self.toggle_measurement)
        b.addWidget(self.start_btn)
        self.apply_btn = QPushButton("Übernehmen")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self.apply)
        b.addWidget(self.apply_btn)
        self.reset_btn = QPushButton("Offset 0")
        self.reset_btn.setToolTip("Nordabgleich aufheben")
        self.reset_btn.clicked.connect(lambda: self.offset_apply.emit(0.0))
        b.addWidget(self.reset_btn)
        left.addLayout(b)

        # --- Ergebnis ---------------------------------------------------
        self.result_label = QLabel("Noch keine Messung.")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-size: 11pt;")
        left.addWidget(self.result_label)
        help_ = QLabel(
            "<p>1. Referenzquelle (Lautsprecher, schwebende Drohne) in bekannter Richtung "
            "betreiben und deren Azimut eintragen.<br>2. Messung starten: die Peilungen der "
            "UnitReports werden zirkular gemittelt.<br>3. Übernehmen sendet den neuen Offset "
            "(Kommando Id 9). Er wird gespeichert und bei jedem Verbinden erneut gesendet.</p>")
        help_.setWordWrap(True)
        help_.setStyleSheet("color: gray;")
        left.addWidget(help_)
        left.addStretch()
        lay.addLayout(left, 2)

        # --- Peilungen während der Messung -----------------------------------
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True)
        p = self.plot.getPlotItem()
        p.setLabel('bottom', 'Peilung Nr.')
        p.setLabel('left', 'Abweichung zur Referenz', units='°')
        p.setTitle('φ_i − φ_ref')
        self.scatter = self.plot.plot(pen=None, symbol='o', symbolSize=4, symbolBrush='c')
        self.mean_line = pg.InfiniteLine(angle=0, pen=pg.mkPen('y', width=2))
        self.zero_line = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen((0, 220, 120), width=1))
        self.plot.addItem(self.zero_line)
        self.plot.addItem(self.mean_line)
        self.mean_line.hide()
        lay.addWidget(self.plot, 3)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.set_offset(0.0)

    # ------------------------------------------------------------
    def set_offset(self, deg: float):
        """Vom Hauptfenster: aktueller (gespeicherter) Offset."""
        self.offset_deg = deg
        self.offset_label.setText(f"{deg:+.2f} °")

    def toggle_measurement(self):
        if self.cal.running:
            self.cal.cancel()
            self.timer.stop()
            self.start_btn.setText("Messung starten")
            self.result_label.setText("Messung abgebrochen.")
            return
        self.cal.start(self.ref_spin.value(), self.offset_deg, self.dur_spin.value(), self.clock())
        self.result = None
        self.apply_btn.setEnabled(False)
        self.mean_line.hide()
        self.scatter.setData([], [])
        self.progress.setValue(0)
        self.start_btn.setText("Abbrechen")
        self.result_label.setText("Messung läuft …")
        self.timer.start(self.TICK_MS)

    def update_unit_report(self, r):
        if self.cal.add(r.bearing_deg, self.clock()):
            ref = self.cal.reference_deg
            dev = [((x - ref + 180.0) % 360.0) - 180.0 for x in self.cal.bearings]
            self.scatter.setData(list(range(len(dev))), dev)

    def tick(self):
        now = self.clock()
        self.progress.setValue(int(round(100 * self.cal.progress(now))))
        if not self.cal.finish_if_due(now):
            return
        self.timer.stop()
        self.start_btn.setText("Messung starten")
        self.progress.setValue(100)
        self.result = self.cal.result()
        if self.result is None:
            self.result_label.setText(
                "<b>Keine Peilungen empfangen.</b> Board im Modus CALIBRATE verbunden? "
                "Quelle laut genug?")
            return
        r, st = self.result, self.result.stats
        self.mean_line.setValue(-r.error_deg)
        self.mean_line.show()
        warn = r.warnings()
        colour = "#ef6c00" if warn else "#2e7d32"
        text = (f"{st.n} Peilungen · Mittel {st.mean_deg:.2f}° · Streuung {st.spread_deg:.2f}°<br>"
                f"Referenz {r.reference_deg:.2f}° − Mittel = <b>{r.error_deg:+.2f}°</b><br>"
                f"Offset {r.old_offset_deg:+.2f}° → <b style='color:{colour}'>{r.offset_deg:+.2f}°</b>")
        if warn:
            text += f"<br><span style='color:{colour}'>Achtung: {'; '.join(warn)}</span>"
        self.result_label.setText(text)
        self.apply_btn.setEnabled(True)

    def apply(self):
        if self.result is not None:
            self.offset_apply.emit(self.result.offset_deg)
            self.apply_btn.setEnabled(False)
