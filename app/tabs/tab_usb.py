from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QDial
from app.model.SDSUSBModel import SDSMode
import serial.tools.list_ports
import serial

from app.usb.usb_reader import USBReader
from app.usb.usb_writer import USBWriter


class TabUSB(QWidget):
    def __init__(self, main_window):
        super().__init__()

        self.main_window = main_window
        self.model = main_window.model

        # USB Objekte
        self.ser = None
        self.reader = None
        self.writer = None

        layout = QVBoxLayout(self)

        # ------------------------------------------------------------
        # USB-Port Auswahl
        # ------------------------------------------------------------
        port_layout = QHBoxLayout()
        self.port_combo = QComboBox()
        self.refresh_ports()

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_ports)

        port_layout.addWidget(QLabel("USB Port:"))
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(btn_refresh)

        # ------------------------------------------------------------
        # Connect / Disconnect
        # ------------------------------------------------------------
        conn_layout = QHBoxLayout()
        btn_connect = QPushButton("Connect")
        btn_disconnect = QPushButton("Disconnect")

        btn_connect.clicked.connect(self.connect_usb)
        btn_disconnect.clicked.connect(self.disconnect_usb)

        conn_layout.addWidget(btn_connect)
        conn_layout.addWidget(btn_disconnect)

        # ------------------------------------------------------------
        # MODE SELECTOR (QDial)
        # ------------------------------------------------------------
        mode_layout = QVBoxLayout()

        self.mode_label = QLabel("Mode: DETECT")

        self.mode_dial = QDial()
        self.mode_dial.setMinimum(0)
        self.mode_dial.setMaximum(2)
        self.mode_dial.setNotchesVisible(True)
        self.mode_dial.setWrapping(False)
        self.mode_dial.setMinimumSize(100, 100)

        self.mode_dial.valueChanged.connect(self.change_mode)

        mode_layout.addWidget(QLabel("SDS Mode Selector"))
        mode_layout.addWidget(self.mode_dial)
        mode_layout.addWidget(self.mode_label)
        mode_layout.addStretch()

        # ------------------------------------------------------------
        # Status
        # ------------------------------------------------------------
        self.status_label = QLabel("USB: disconnected")

        # ------------------------------------------------------------
        # Layout zusammenbauen
        # ------------------------------------------------------------
        layout.addLayout(port_layout)
        layout.addLayout(conn_layout)
        layout.addLayout(mode_layout)
        layout.addWidget(self.status_label)

    # ------------------------------------------------------------
    # USB Port Handling
    # ------------------------------------------------------------
    def refresh_ports(self):
        self.port_combo.clear()
        for p in serial.tools.list_ports.comports():
            self.port_combo.addItem(p.device)

    def connect_usb(self):
        port = self.port_combo.currentText()
        if not port:
            self.status_label.setText("USB: no port selected")
            return

        try:
            # COM-Port öffnen
            self.ser = serial.Serial(port, 115200, timeout=0.1)
            self.model.set_port(port)
            self.model.set_connected(True)

            # Reader/Writer erzeugen (JETZT ist ser gültig)
            self.reader = USBReader(self.ser, self.model)
            self.writer = USBWriter(self.ser, self.model)

            # Threads starten
            self.reader.start()
            self.writer.start()

            # MainWindow informieren
            self.main_window.on_usb_connected(self.reader, self.writer)

            self.status_label.setText(f"USB: connected to {port}")

        except Exception as e:
            self.model.set_connected(False)
            self.status_label.setText(f"USB: connect failed: {e}")

    def disconnect_usb(self):
        try:
            if self.reader:
                self.reader.stop()
                self.reader.wait()

            if self.writer:
                self.writer.stop()
                self.writer.wait()

            if self.ser:
                self.ser.close()

        except Exception:
            pass

        self.model.set_connected(False)
        self.status_label.setText("USB: disconnected")

    # ------------------------------------------------------------
    # MODE CHANGE (QDial)
    # ------------------------------------------------------------
    def change_mode(self, value):
        modes = [SDSMode.DETECT, SDSMode.READ, SDSMode.CALIBRATE]
        mode = modes[value]

        self.model.set_mode(mode)
        self.mode_label.setText(f"Mode: {mode.name}")

        try:
            if self.writer:
                self.writer.send_mode(mode.value)
            else:
                self.status_label.setText("USB: writer not ready")
        except Exception:
            self.status_label.setText("USB: send_mode failed")
