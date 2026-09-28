# app/widgets/control_panel.py

import serial.tools.list_ports
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QFrame, QGroupBox, QLabel, QPushButton, QSizePolicy,
                             QVBoxLayout, QHBoxLayout, QWidget)

from app.model.SDSUSBModel import SDSMode
from app.widgets.mode_dial import ModeDial
from app.widgets.toggle_switch import ToggleSwitch


class ControlPanel(QWidget):
    """
    Bedienfeld am linken Fensterrand (alle Schalter und Drehknöpfe):
      - USB-Port + On/Off (Verbindung öffnen/schließen)
      - Simulation/Real (ICD Id 3)
      - Drehschalter Detect/Read/Calibrate (ICD Id 2, wählt auch den sichtbaren Tab)
    Die Signale gehen an das MainWindow; das Panel selbst sendet nichts.
    """

    power_toggled = pyqtSignal(bool)          # True = verbinden
    simulation_toggled = pyqtSignal(bool)     # True = Simulation, False = Mikrofone
    mode_changed = pyqtSignal(object)         # SDSMode

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

        lay.addStretch()
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(line)
        lay.addWidget(QLabel("SDS_110 · ICD 28.09.2026"))

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

    def set_connected(self, connected: bool, text: str):
        """Zustand nach (Dis-)Connect; setzt den Schalter ohne erneutes Signal."""
        self.sw_power.setChecked(connected, emit=False)
        self.port_combo.setEnabled(not connected)
        self.btn_refresh.setEnabled(not connected)
        self.conn_label.setText(text)
        self.conn_label.setStyleSheet("color: #2e7d32;" if connected else "color: gray;")
