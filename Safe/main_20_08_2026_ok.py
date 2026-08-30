import sys
import math
import struct
import zlib
import serial
import threading
import time
import serial.tools.list_ports

from PyQt6.QtWidgets import QComboBox, QPushButton, QHBoxLayout
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

import pyqtgraph as pg

PORT = "COM5"
BAUD = 115200

FRAME_SIZE_DET = 24
MAGIC = 0xDEADBEEF
FRAME_SIZE_SYNC = 12


class SerialWorker(QObject):
    sds_signal = pyqtSignal(dict)
    sync_signal = pyqtSignal(str)

    def __init__(self, port, baud):
        super().__init__()
        self.port = port
        self.baud = baud
        self.running = True
        self.send_sync_request = False
        self.ser = None

    def open_port(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
            print(f"[INFO] COM-Port geöffnet: {self.port}")
        except Exception as e:
            print(f"[ERROR] Konnte Port nicht öffnen: {e}")
            self.ser = None

    def send_time_sync(self):
        unix_time = int(time.time())
        msg_id = 1
        len0, len1, len2 = 0, 0, 12
        payload = struct.pack(">I", unix_time)
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        header = struct.pack("<BBBBI", msg_id, len0, len1, len2, unix_time)
        packet = header + struct.pack("<I", crc)
        self.ser.write(packet)
        self.sync_signal.emit(f"[SEND] UnixTime Sync sent: {unix_time}")

    def send_mode(self, mode):
        if self.ser is None:
            print("[ERROR] Kein Serial-Port geöffnet.")
            return

        msg_id = 2
        len0, len1, len2 = 0, 0, 12

        # MODE muss BIG ENDIAN sein (00 00 00 02)
        payload = struct.pack(">I", mode)
        crc = zlib.crc32(payload) & 0xFFFFFFFF

        header = struct.pack("<BBBB", msg_id, len0, len1, len2)
        packet = header + payload + struct.pack("<I", crc)

        # --- PRINT AS BYTES ---
        print("\n[SEND MODE FRAME]")
        print("Decimal:", list(packet))
        print("Hex:    ", " ".join(f"{b:02X}" for b in packet))

        self.ser.write(packet)
        self.sync_signal.emit(f"[SEND] Mode set to {mode}")

    def send_simulate(self, simulate):
        if self.ser is None:
            print("[ERROR] Kein Serial-Port geöffnet.")
            return

        msg_id = 3
        len0, len1, len2 = 0, 0, 12  # total 12 bytes

        # simulate als BIG ENDIAN (00 00 00 01)
        payload = struct.pack(">I", simulate)

        # CRC über das Big-Endian-Payload
        crc = zlib.crc32(payload) & 0xFFFFFFFF

        # Header ist wie immer Little Endian
        header = struct.pack("<BBBB", msg_id, len0, len1, len2)

        # Finales Paket
        packet = header + payload + struct.pack("<I", crc)

        # --- DEBUG OUTPUT ---
        print("\n[SEND SIMULATE FRAME]")
        print("Decimal:", list(packet))
        print("Hex:    ", " ".join(f"{b:02X}" for b in packet))

        self.ser.write(packet)
        self.sync_signal.emit(f"[SEND] Simulate set to {simulate}")

    def run(self):
        self.open_port()
        if self.ser is None:
            return

        last_sync = time.time()

        while self.running:
            try:
                first = self.ser.read(1)
                if len(first) == 0:
                    if time.time() - last_sync > 1.0:
                        self.send_time_sync()
                        last_sync = time.time()
                    continue

                b0 = first[0]

                if b0 == 1:
                    rest = self.ser.read(FRAME_SIZE_SYNC - 1)
                    if len(rest) != FRAME_SIZE_SYNC - 1:
                        continue
                    msg_id, len0, len1, len2, unix_time, crc = struct.unpack(
                        "<BBBBII", first + rest
                    )
                    self.sync_signal.emit(
                        f"[SYNC] UnixTime={unix_time}  CRC=0x{crc:08X}"
                    )
                    continue

                else:
                    magic_bytes = first + self.ser.read(3)
                    if len(magic_bytes) != 4:
                        continue

                    magic = struct.unpack("<I", magic_bytes)[0]
                    if magic != MAGIC:
                        print(f"[WARN] Unknown frame start: 0x{magic:08X}")
                        continue

                    rest = self.ser.read(FRAME_SIZE_DET - 4)
                    if len(rest) != FRAME_SIZE_DET - 4:
                        continue

                    ts, mic, azi, ele, conf = struct.unpack("<IIfff", rest)

                    data = {
                        "ts": ts,
                        "mic": mic,
                        "azi": azi,
                        "dist": ele,
                        "conf": conf
                    }

                    self.sds_signal.emit(data)

                    if time.time() - last_sync > 1.0:
                        self.send_time_sync()
                        last_sync = time.time()

            except Exception as e:
                print(f"[ERROR] Serial read error: {e}")
                break

        try:
            self.ser.close()
        except Exception:
            pass
        print("[INFO] COM-Port geschlossen")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("USB Monitor")
        self.resize(800, 600)

        # Worker starten
        self.worker = SerialWorker(PORT, BAUD)
        self.thread = threading.Thread(target=self.worker.run, daemon=True)
        self.thread.start()

        # --- Hauptlayout ---
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # --- COM-Port Wahlschalter ---
        self.port_selector = QComboBox()
        self.port_selector.addItems(self.list_ports())

        self.btn_connect = QPushButton("Verbinden")
        self.btn_connect.clicked.connect(self.change_port)

        port_bar = QWidget()
        port_layout = QHBoxLayout()
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_layout.setSpacing(0)
        port_layout.addWidget(QLabel("Port:"))
        port_layout.addWidget(self.port_selector)
        port_layout.addWidget(self.btn_connect)
        port_bar.setLayout(port_layout)

        main_layout.addWidget(port_bar)

        # --- Mode Wahlschalter ---
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(["DETECT", "CALIBRATE", "READ"])

        self.btn_mode = QPushButton("Set Mode")
        self.btn_mode.clicked.connect(self.change_mode)

        mode_bar = QWidget()
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(0)
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.mode_selector)
        mode_layout.addWidget(self.btn_mode)
        mode_bar.setLayout(mode_layout)

        main_layout.addWidget(mode_bar)

        # --- Simulate Wahlschalter ---
        self.simulate_selector = QComboBox()
        self.simulate_selector.addItems(["REAL", "SIMULATED"])

        self.btn_simulate = QPushButton("Set Simulate")
        self.btn_simulate.clicked.connect(self.change_simulate)

        simulate_bar = QWidget()
        simulate_layout = QHBoxLayout()
        simulate_layout.setContentsMargins(0, 0, 0, 0)
        simulate_layout.setSpacing(0)
        simulate_layout.addWidget(QLabel("Simulate:"))
        simulate_layout.addWidget(self.simulate_selector)
        simulate_layout.addWidget(self.btn_simulate)
        simulate_bar.setLayout(simulate_layout)
        simulate_bar.setFixedHeight(40)

        main_layout.addWidget(simulate_bar)


        # --- Tabs ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.init_sds_tab()
        self.init_plot_tab()

        # --- Signale verbinden ---
        self.worker.sds_signal.connect(self.update_sds)
        self.worker.sds_signal.connect(self.update_plot)
        self.worker.sync_signal.connect(self.update_sync)

        # Plot-Daten
        self.az_history = []
        self.dist_history = []

    # ------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------

    def list_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def change_port(self):
        new_port = self.port_selector.currentText()
        print(f"[INFO] Wechsel zu Port {new_port}")

        self.worker.running = False
        time.sleep(0.2)

        self.worker = SerialWorker(new_port, BAUD)
        self.thread = threading.Thread(target=self.worker.run, daemon=True)
        self.thread.start()

        self.worker.sds_signal.connect(self.update_sds)
        self.worker.sds_signal.connect(self.update_plot)
        self.worker.sync_signal.connect(self.update_sync)

    def change_mode(self):
        mode_name = self.mode_selector.currentText()
        mode_map = {"DETECT": 1, "CALIBRATE": 2, "READ": 3}
        mode_value = mode_map[mode_name]

        print(f"[INFO] Setting mode: {mode_name} ({mode_value})")
        self.worker.send_mode(mode_value)

    def change_simulate(self):
        sim_name = self.simulate_selector.currentText()

        sim_map = {
            "REAL": 0,
            "SIMULATED": 1
        }

        sim_value = sim_map[sim_name]
        print(f"[INFO] Setting simulate: {sim_name} ({sim_value})")

        self.worker.send_simulate(sim_value)

    # ------------------------------------------------------------
    # SDS-Tab
    # ------------------------------------------------------------
    def init_sds_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        self.label_sds = QLabel("SDS Output")
        self.label_sync = QLabel("Sync Output")

        btn_sync = QPushButton("Send UnixTime Sync")
        btn_sync.clicked.connect(self.send_sync)

        layout.addWidget(self.label_sds)
        layout.addWidget(self.label_sync)
        layout.addWidget(btn_sync)

        widget.setLayout(layout)
        self.tabs.addTab(widget, "SDS")

    # ------------------------------------------------------------
    # Plot-Tab
    # ------------------------------------------------------------
    def init_plot_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        pg.setConfigOptions(antialias=True)

        self.plot_az = pg.PlotWidget(title="Azimuth (degrees)")
        self.plot_dist = pg.PlotWidget(title="Distance (meters)")

        self.curve_az = self.plot_az.plot(pen="r")
        self.curve_dist = self.plot_dist.plot(pen="b")

        layout.addWidget(self.plot_az)
        layout.addWidget(self.plot_dist)

        widget.setLayout(layout)
        self.tabs.addTab(widget, "Plot")

    # ------------------------------------------------------------
    # Update-Funktionen
    # ------------------------------------------------------------
    def update_sds(self, data):
        text = (
            f"[SDS] TS={data['ts']:10d}  Mic={data['mic']}  "
            f"Az={data['azi']:7.2f}°  Dist={data['dist']:7.2f}m  Conf={data['conf']:5.2f}"
        )
        self.label_sds.setText(text)

    def update_sync(self, text):
        self.label_sync.setText(text)

    def update_plot(self, data):
        self.az_history.append(data["azi"])
        self.dist_history.append(data["dist"])

        self.curve_az.setData(self.az_history)
        self.curve_dist.setData(self.dist_history)

    def send_sync(self):
        self.worker.send_sync_request = True

    def closeEvent(self, event):
        self.worker.running = False
        event.accept()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
