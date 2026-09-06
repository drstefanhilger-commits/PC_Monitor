# main_window.py

import sys
import logging

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
)
from PyQt6.QtCore import QTimer

from .model import SDSUSBModel
from .tabs.tab_detect import TabDetect
from .tabs.tab_read import TabRead
from .tabs.tab_inspector import TabInspector

# Falls du pyserial nutzt:
# import serial
# from .usb.usb_reader import USBReader


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("USB Monitor (SDS)")

        # Zentrales Modell
        self.model = SDSUSBModel()

        # Tabs
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self.detect_tab = TabDetect(self.model, parent=self)
        self.read_tab = TabRead(self.model, parent=self)
        self.inspector_tab = TabInspector(self.model, parent=self)

        self.tabs.addTab(self.detect_tab, "Detect")
        self.tabs.addTab(self.read_tab, "Read")
        self.tabs.addTab(self.inspector_tab, "Inspector")

        # USBReader-Thread (hier nur Platzhalter – an deine ser-Logik anpassen)
        self.usb_reader = None
        # Beispiel:
        # ser = serial.Serial("COM3", baudrate=115200, timeout=0.01)
        # self.usb_reader = USBReader(ser, self.model)
        # self.usb_reader.start()

        # GUI-Update-Timer
        self.timer = QTimer(self)
        self.timer.setInterval(50)  # ms
        self.timer.timeout.connect(self.process_queues)
        self.timer.start()

    def process_queues(self):
        """
        Holt deterministisch alle Messages aus den Queues
        und aktualisiert die Tabs.
        """
        # DETECT-Frames
        while not self.model.detect_queue.empty():
            msg_id, frame = self.model.detect_queue.get_nowait()
            self.model.update_frame(msg_id, frame)
            self.detect_tab.add_frame(msg_id, frame)

        # READ-Frames
        while not self.model.read_queue.empty():
            msg_id, frame = self.model.read_queue.get_nowait()
            self.model.update_frame(msg_id, frame)
            self.read_tab.add_frame(msg_id, frame)

        # Inspector-Events (error / frame / unknown_msg_id)
        while not self.model.inspect_queue.empty():
            kind, raw, reason = self.model.inspect_queue.get_nowait()
            self.model.update_inspector(kind, raw, reason)
            self.inspector_tab.add_event(kind, raw, reason)

        # Raw-Dump-Anzeige aktualisieren
        self.inspector_tab.update_raw_dump()

    def closeEvent(self, event):
        # USBReader sauber stoppen
        try:
            if self.usb_reader is not None:
                self.usb_reader.stop()
        except Exception as e:
            logging.error(f"MainWindow: error stopping USBReader: {e}")
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(900, 600)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
