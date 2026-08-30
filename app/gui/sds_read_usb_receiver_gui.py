import struct
import zlib
import serial
import serial.tools.list_ports
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel,
    QComboBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, QTimer

from usb.usb_reader import USBReader


class SDS_READ_USB_RECEIVER_GUI(QWidget):
    def __init__(self, main_window=None):
        super().__init__()

        self.main_window = main_window
        self.reader: USBReader | None = None

        layout = QVBoxLayout(self)

        # Port Auswahl
        port_layout = QHBoxLayout()
        self.port_combo = QComboBox()
        self.refresh_ports()
        self.refresh_btn = QPushButton("Refresh Ports")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(QLabel("Port:"))
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.refresh_btn)
        layout.addLayout(port_layout)

        # Connect / Disconnect
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        self.connect_btn.clicked.connect(self.on_connect)
        self.disconnect_btn.clicked.connect(self.on_disconnect)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.disconnect_btn)
        layout.addLayout(btn_layout)

        # Mode Selector
        mode_layout = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["DETECT", "CALIBRATE", "READ"])
        self.mode_btn = QPushButton("Set Mode")
        self.mode_btn.clicked.connect(self.on_set_mode)
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addWidget(self.mode_btn)
        layout.addLayout(mode_layout)

        # Status
        self.status_label = QLabel("Status: idle")
        layout.addWidget(self.status_label)

        # Frame Info
        self.frame_label = QLabel("Frame: -")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.frame_label)

        # Timer
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.update_frame_info)
        self.timer.start()

    # ------------------------------------------------------------------ Ports
    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(p.device)

    # ------------------------------------------------------------------ Connect
    def on_connect(self):
        if self.reader is not None:
            return

        port = self.port_combo.currentText()
        if not port:
            self.status_label.setText("Status: no port selected")
            return
        
        self.reader = USBReader(port, main_window=self.main_window)

        try:
            self.reader.open()
            self.status_label.setText(f"Status: connected to {port}")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)

            # PlotTab bekommt den Reader
            if self.main_window is not None and hasattr(self.main_window, "plot_tab"):
                self.main_window.plot_tab.set_reader(self.reader)

        except serial.SerialException as e:
            self.status_label.setText(f"Status: error opening port: {e}")
            self.reader = None

    def on_disconnect(self):
        if self.reader:
            self.reader.close()
            self.reader = None

        self.status_label.setText("Status: disconnected")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)

        if self.main_window is not None and hasattr(self.main_window, "plot_tab"):
            self.main_window.plot_tab.set_reader(None)

    # ------------------------------------------------------------------ Mode
    def on_set_mode(self):
        mode_name = self.mode_combo.currentText()
        mode_map = {
            "DETECT": 1,
            "CALIBRATE": 2,
            "READ": 3
        }
        mode_value = mode_map[mode_name]

        self.send_mode_frame(mode_value)

        if self.main_window is not None and hasattr(self.main_window, "set_mode"):
            self.main_window.set_mode(mode_name)

    def send_mode_frame(self, mode_value: int):
        if not self.reader or not self.reader.ser:
            self.status_label.setText("Status: not connected")
            return

        # SDS Mode Frame Format:
        # ID (1 byte)
        # LEN0, LEN1, LEN2 (3 bytes)
        # PAYLOAD (4 bytes, BIG ENDIAN)
        # CRC32(PAYLOAD) (4 bytes, BIG ENDIAN)

        msg_id = 2
        len0, len1, len2 = 0, 0, 12  # 12 bytes payload length

        # BIG-ENDIAN payload
        payload = struct.pack(">I", mode_value)

        # CRC32 über BIG-ENDIAN payload → ebenfalls BIG-ENDIAN senden
        crc = zlib.crc32(payload) & 0xFFFFFFFF

        # Header bleibt LITTLE-ENDIAN (SDS erwartet das so!)
        header = struct.pack("<BBBB", msg_id, len0, len1, len2)

        # CRC muss BIG-ENDIAN gesendet werden
        crc_be = struct.pack(">I", crc)

        packet = header + payload + crc_be

        self.reader.ser.write(packet)
        self.status_label.setText(f"Mode set to {mode_value}")

    # ------------------------------------------------------------------ Frame Info
    def update_frame_info(self):
        if not self.reader:
            return

        frame = self.reader.get_latest_frame()
        if frame is None:
            return

        frameIndex, data = frame

        rms = np.sqrt(np.mean(data ** 2, axis=1))
        rms_str = ", ".join(f"{v:.3f}" for v in rms)

        self.frame_label.setText(f"Frame: {frameIndex} | RMS: [{rms_str}]")
