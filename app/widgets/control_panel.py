# app/widgets/control_panel.py

import serial.tools.list_ports
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGroupBox, QLabel,
                             QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QHBoxLayout, QWidget)

from app import __version__
from app.model.SDSUSBModel import SDSMode
from app.widgets.mode_dial import ModeDial
from app.widgets.toggle_switch import ToggleSwitch


class ControlPanel(QWidget):
    """
    Bedienfeld am linken Fensterrand (alle Schalter und Drehknöpfe):
      - USB-Port + On/Off (Verbindung öffnen/schließen)
      - Simulation/Real (ICD Id 3)
      - Drehschalter Detect/Read/Calibrate (ICD Id 2, wählt auch den sichtbaren Tab)
      - Board: Unit-ID setzen (Id 5), SRP-Referenzscan aus/ein (Id 6)
      - Sync: UTC + Lufttemperatur (Id 7), automatisch jede Minute, bei Temperaturänderung sofort
    Die Signale gehen an das MainWindow; das Panel selbst sendet nichts.
    """

    power_toggled = pyqtSignal(bool)          # True = verbinden
    simulation_toggled = pyqtSignal(bool)     # True = Simulation, False = Mikrofone
    mode_changed = pyqtSignal(object)         # SDSMode
    unit_id_set = pyqtSignal(int)
    srp_toggled = pyqtSignal(bool)
    sync_requested = pyqtSignal()             # Sync jetzt senden (Knopf oder Temperatur geändert)
    feedback_toggled = pyqtSignal(bool)       # Tracking-Feedback an das Board (Id 8)
    export_requested = pyqtSignal()           # Trajektorien als CSV speichern

    WIDTH = 230

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(self.WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        # --- Verbindung -------------------------------------------------
        box_conn = QGroupBox("Verbindung")
        vc = QVBoxLayout(box_conn)
        row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setToolTip("COM-Ports neu einlesen")
        self.btn_refresh.setFixedWidth(30)
        self.btn_refresh.clicked.connect(self.refresh_ports)
        row.addWidget(self.port_combo)
        row.addWidget(self.btn_refresh)
        vc.addLayout(row)
        self.sw_power = ToggleSwitch("Off", "On", on_color="#2e7d32")
        self.sw_power.toggled.connect(self.power_toggled)
        vc.addWidget(self.sw_power)
        self.conn_label = QLabel("getrennt")
        vc.addWidget(self.conn_label)
        lay.addWidget(box_conn)

        # --- Signalquelle -----------------------------------------------
        box_src = QGroupBox("Signalquelle")
        vs = QVBoxLayout(box_src)
        self.sw_sim = ToggleSwitch("Real", "Simulation", on_color="#ef6c00")
        self.sw_sim.setChecked(True, emit=False)      # Firmware-Standard: Simulation (ICD Id 3)
        self.sw_sim.toggled.connect(self.simulation_toggled)
        vs.addWidget(self.sw_sim)
        lay.addWidget(box_src)

        # --- Betriebsart --------------------------------------------------
        box_mode = QGroupBox("Betriebsart")
        vm = QVBoxLayout(box_mode)
        self.mode_dial = ModeDial()
        self.mode_dial.mode_changed.connect(self.mode_changed)
        vm.addWidget(self.mode_dial)
        lay.addWidget(box_mode)

        # --- Board --------------------------------------------------------
        box_board = QGroupBox("Board")
        vb = QVBoxLayout(box_board)
        row = QHBoxLayout()
        row.addWidget(QLabel("Unit-ID"))
        self.unit_spin = QSpinBox()
        self.unit_spin.setRange(0, 0xFFFF)
        self.btn_unit = QPushButton("Setzen")
        self.btn_unit.clicked.connect(lambda: self.unit_id_set.emit(self.unit_spin.value()))
        row.addWidget(self.unit_spin, 1)
        row.addWidget(self.btn_unit)
        vb.addLayout(row)
        self.sw_srp = ToggleSwitch("SRP aus", "ein", on_color="#6a1b9a")
        self.sw_srp.setToolTip("SRP-PHAT-Referenzscan (Vergleich, ~2,3 ms je Frame)")
        self.sw_srp.toggled.connect(self.srp_toggled)
        vb.addWidget(self.sw_srp)
        lay.addWidget(box_board)

        # --- Sync (UTC + Temperatur) -----------------------------------------
        box_sync = QGroupBox("Sync (UTC, Temperatur)")
        vy = QVBoxLayout(box_sync)
        row = QHBoxLayout()
        self.chk_temp = QCheckBox("Temp.")
        self.chk_temp.setChecked(True)
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(-40.0, 60.0)
        self.temp_spin.setDecimals(1)
        self.temp_spin.setSingleStep(0.5)
        self.temp_spin.setSuffix(" °C")
        self.temp_spin.setValue(20.0)
        self.chk_temp.toggled.connect(self.temp_spin.setEnabled)
        self.chk_temp.toggled.connect(lambda _: self.sync_requested.emit())
        self.temp_spin.editingFinished.connect(self.sync_requested)
        row.addWidget(self.chk_temp)
        row.addWidget(self.temp_spin, 1)
        vy.addLayout(row)
        row = QHBoxLayout()
        self.btn_sync = QPushButton("Sync jetzt")
        self.btn_sync.clicked.connect(self.sync_requested)
        self.sync_label = QLabel("–")
        row.addWidget(self.btn_sync)
        row.addWidget(self.sync_label, 1)
        vy.addLayout(row)
        lay.addWidget(box_sync)

        # --- Tracking (FSL9 §8–10) -------------------------------------------
        box_trk = QGroupBox("Tracking")
        vt = QVBoxLayout(box_trk)
        self.sw_feedback = ToggleSwitch("Feedback aus", "ein", on_color="#00838f")
        self.sw_feedback.setToolTip("ŝ und Vorhersage nach jeder Übernahme an das Board (Id 8)")
        self.sw_feedback.setChecked(True, emit=False)
        self.sw_feedback.toggled.connect(self.feedback_toggled)
        vt.addWidget(self.sw_feedback)
        self.btn_export = QPushButton("Trajektorie als CSV …")
        self.btn_export.clicked.connect(self.export_requested)
        vt.addWidget(self.btn_export)
        lay.addWidget(box_trk)

        lay.addStretch()
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(line)
        lay.addWidget(QLabel(f"PC-Monitor {__version__} · ICD 28.09.2026"))

        self.refresh_ports()

    # ------------------------------------------------------------
    def refresh_ports(self):
        current = self.port_combo.currentText()
        self.port_combo.clear()
        for p in serial.tools.list_ports.comports():
            self.port_combo.addItem(p.device)
        i = self.port_combo.findText(current)
        if i >= 0:
            self.port_combo.setCurrentIndex(i)

    def port(self) -> str:
        return self.port_combo.currentText()

    def simulation(self) -> bool:
        return self.sw_sim.isChecked()

    def mode(self) -> SDSMode:
        return self.mode_dial.mode()

    def feedback(self) -> bool:
        return self.sw_feedback.isChecked()

    def srp(self) -> bool:
        return self.sw_srp.isChecked()

    def temperature(self):
        """Lufttemperatur in °C oder None (nicht senden = unbekannt)."""
        return self.temp_spin.value() if self.chk_temp.isChecked() else None

    def set_sync_text(self, text: str):
        self.sync_label.setText(text)

    def set_connected(self, connected: bool, text: str):
        """Zustand nach (Dis-)Connect; setzt den Schalter ohne erneutes Signal."""
        self.sw_power.setChecked(connected, emit=False)
        self.port_combo.setEnabled(not connected)
        self.btn_refresh.setEnabled(not connected)
        self.conn_label.setText(text)
        self.conn_label.setStyleSheet("color: #2e7d32;" if connected else "color: gray;")
