# app/widgets/control_panel.py

import serial.tools.list_ports
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGroupBox, QLabel, QLineEdit,
                             QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QHBoxLayout, QWidget)

from app import __version__
from app.model.SDSUSBModel import SDSMode, SIM_DEFAULT, SIM_REAL, SIM_SCENARIOS
from app.widgets.mode_dial import ModeDial
from app.widgets.toggle_switch import ToggleSwitch


class ControlPanel(QWidget):
    """
    Bedienfeld am linken Fensterrand (alle Schalter und Drehknöpfe):
      - USB-Port + On/Off (Verbindung öffnen/schließen)
      - Simulation/Real und Simulator-Szenario (ICD Id 3)
      - Drehschalter Detect/Read/Calibrate (ICD Id 2, wählt auch den sichtbaren Tab)
      - Board: Unit-ID setzen (Id 5), SRP-Referenzscan aus/ein (Id 6)
      - Sync: UTC + Lufttemperatur (Id 7), automatisch jede Minute, bei Temperaturänderung sofort
      - Standort lokal: Ost, Nord, Oben in m (Id 10); Anzeige der Position, die das Board meldet (Id 6)
    Die Signale gehen an das MainWindow; das Panel selbst sendet nichts.
    """

    power_toggled = pyqtSignal(bool)          # True = verbinden
    simulation_changed = pyqtSignal(int)      # Wert für Id 3: 0 = Mikrofone, 1 … 7 = Szenario
    mode_changed = pyqtSignal(object)         # SDSMode
    unit_id_set = pyqtSignal(int)
    srp_toggled = pyqtSignal(bool)
    sync_requested = pyqtSignal()             # Sync jetzt senden (Knopf oder Temperatur geändert)
    position_set = pyqtSignal(str)            # Eingabe "Ost, Nord[, Oben]" in m senden
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
        self.sw_sim.toggled.connect(self._on_sim_toggled)
        vs.addWidget(self.sw_sim)
        row = QHBoxLayout()
        row.addWidget(QLabel("Szenario"))
        self.sim_combo = QComboBox()
        for value, name in SIM_SCENARIOS:
            self.sim_combo.addItem(name, value)
        self.sim_combo.setToolTip("Simulator der Firmware (Id 3 = 1 … 7). FlyBy: 5 s gerader Überflug,\n"
                                  "5 s Pause mit Rauschen, wiederholt. Nordabgleich nicht mit\n"
                                  "DroneSweep oder FlyBy messen (bewegte Quelle).")
        self.sim_combo.currentIndexChanged.connect(self._on_scenario_changed)
        row.addWidget(self.sim_combo, 1)
        vs.addLayout(row)
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

        # --- Standort (Id 10 -> Board, Id 6 <- Board) -----------------------------
        box_pos = QGroupBox("Standort (lokal, m)")
        vp = QVBoxLayout(box_pos)
        self.pos_edit = QLineEdit()
        self.pos_edit.setPlaceholderText("Ost, Nord, Oben in m")
        self.pos_edit.setToolTip("Position der Einheit relativ zum lokalen Ursprung [0, 0, 0] in m,\n"
                                 "Ost/Nord positiv, Oben optional, z. B. 0, -50, 2.\n"
                                 "Das Board startet im Ursprung. Wird gespeichert und beim Verbinden gesendet.\n"
                                 "Simulation FlyBy: die Bahn liegt um den Ursprung (kürzester Abstand 30 m).")
        self.pos_edit.returnPressed.connect(lambda: self.position_set.emit(self.pos_edit.text()))
        vp.addWidget(self.pos_edit)
        row = QHBoxLayout()
        self.btn_pos = QPushButton("Senden")
        self.btn_pos.clicked.connect(lambda: self.position_set.emit(self.pos_edit.text()))
        row.addWidget(self.btn_pos)
        row.addStretch()
        vp.addLayout(row)
        self.board_pos_label = QLabel("Board: –")
        self.board_pos_label.setWordWrap(True)
        self.board_pos_label.setStyleSheet("color: gray;")
        vp.addWidget(self.board_pos_label)
        lay.addWidget(box_pos)

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
        lay.addWidget(QLabel(f"PC-Monitor {__version__} · ICD 29.09.2026"))

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

    def scenario(self) -> int:
        """gewähltes Szenario (Id-3-Wert 1 … 7), auch wenn Real eingestellt ist"""
        return int(self.sim_combo.currentData())

    def simulation_value(self) -> int:
        """Wert für Id 3: 0 = Mikrofone, sonst das gewählte Szenario"""
        return self.scenario() if self.simulation() else SIM_REAL

    def set_scenario(self, value: int):
        """Szenario setzen ohne Signal (gespeicherter Wert beim Start); unbekannt -> Standard"""
        i = self.sim_combo.findData(int(value))
        self.sim_combo.blockSignals(True)
        self.sim_combo.setCurrentIndex(i if i >= 0 else self.sim_combo.findData(SIM_DEFAULT))
        self.sim_combo.blockSignals(False)

    def _on_sim_toggled(self, on: bool):
        self.sim_combo.setEnabled(on)
        self.simulation_changed.emit(self.simulation_value())

    def _on_scenario_changed(self, _index: int):
        if self.simulation():             # bei Real nur merken, gesendet wird beim Umschalten
            self.simulation_changed.emit(self.simulation_value())

    def mode(self) -> SDSMode:
        return self.mode_dial.mode()

    def feedback(self) -> bool:
        return self.sw_feedback.isChecked()

    def srp(self) -> bool:
        return self.sw_srp.isChecked()

    def temperature(self):
        """Lufttemperatur in °C oder None (nicht senden = unbekannt)."""
        return self.temp_spin.value() if self.chk_temp.isChecked() else None

    def set_board_position(self, text: str, ok: bool):
        self.board_pos_label.setText(f"Board: {text}")
        self.board_pos_label.setStyleSheet("" if ok else "color: #ef6c00;")

    def set_sync_text(self, text: str):
        self.sync_label.setText(text)

    def set_connected(self, connected: bool, text: str):
        """Zustand nach (Dis-)Connect; setzt den Schalter ohne erneutes Signal."""
        self.sw_power.setChecked(connected, emit=False)
        self.port_combo.setEnabled(not connected)
        self.btn_refresh.setEnabled(not connected)
        self.conn_label.setText(text)
        self.conn_label.setStyleSheet("color: #2e7d32;" if connected else "color: gray;")
