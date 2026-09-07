from PyQt6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer

from app.model.SDSUSBModel import SDSUSBModel
from app.tabs.tab_detect import TabDetect
from app.tabs.tab_read import TabRead
from app.tabs.tab_inspector import TabInspector
from app.tabs.tab_usb import TabUSB


class MainWindow(QMainWindow):
    """
    Hauptfenster:
    - Hält das SDSUSBModel
    - Besitzt Tabs (USB, Detect, Read, Inspector)
    - Pollt Queues deterministisch
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("SDS USB Monitor Version 1.00")

        # ------------------------------------------------------------
        # Model
        # ------------------------------------------------------------
        self.model = SDSUSBModel()

        # ------------------------------------------------------------
        # Tabs
        # ------------------------------------------------------------
        tabs = QTabWidget()

        # USB-Tab (verwaltet ser, USBReader, USBWriter)
        self.usb_tab = TabUSB(main_window=self)
        tabs.addTab(self.usb_tab, "SDS System")

        # Detect-Tab
        self.detect_tab = TabDetect()
        tabs.addTab(self.detect_tab, "Detect")

        # Read-Tab
        self.read_tab = TabRead()
        tabs.addTab(self.read_tab, "Read")

        # Inspector-Tab (bekommt später Reader/Writer via on_usb_connected)
        self.tab_inspector = TabInspector(self.model)
        self.model.inspector = self.tab_inspector
        tabs.addTab(self.tab_inspector, "Inspector")

        # ------------------------------------------------------------
        # Layout
        # ------------------------------------------------------------
        main = QWidget()
        layout = QVBoxLayout(main)
        layout.addWidget(tabs)
        self.setCentralWidget(main)

        # ------------------------------------------------------------
        # Timer für Queue‑Polling
        # ------------------------------------------------------------
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(20)   # 50 Hz

    # ------------------------------------------------------------
    # Callback: USB verbunden → Reader/Writer an Inspector geben
    # ------------------------------------------------------------
    def on_usb_connected(self, reader, writer):
        self.tab_inspector.set_usb(reader, writer)

    # ------------------------------------------------------------
    # Queue‑Polling
    # ------------------------------------------------------------
    def process_queue(self):
        # ------------------------------------------------------------
        # DETECT Frames
        # ------------------------------------------------------------
        while not self.model.detect_queue.empty():
            msg_id, frame = self.model.detect_queue.get()
            self.detect_tab.update_frame(frame)
            self.tab_inspector.add_valid_frame(msg_id)
            self.model.update_frame(msg_id, frame, "DETECT")

        # ------------------------------------------------------------
        # READ Frames
        # ------------------------------------------------------------
        while not self.model.read_queue.empty():
            msg_id, frame = self.model.read_queue.get()
            self.read_tab.update_frame(frame)
            self.tab_inspector.add_valid_frame(msg_id)
            self.model.update_frame(msg_id, frame, "READ")

        # ------------------------------------------------------------
        # INSPECT Frames
        # ------------------------------------------------------------
        while not self.model.inspect_queue.empty():
            kind, raw, reason = self.model.inspect_queue.get()

            if kind == "error":
                self.tab_inspector.add_error_frame(0, raw, reason)
                self.model.update_inspector(kind, raw, reason)
                continue

            if kind == "unknown_msg_id":
                self.tab_inspector.add_error_frame(-1, raw, reason)
                self.model.update_inspector(kind, raw, reason)
                continue

            if kind == "frame":
                self.model.update_inspector(kind, raw, reason)
                self.tab_inspector.update_inspector()
                continue

        # ------------------------------------------------------------
        # Inspector aktualisieren
        # ------------------------------------------------------------
        self.tab_inspector.update_inspector()

    # ------------------------------------------------------------
    # Fenster schließen → USB stoppen
    # ------------------------------------------------------------
    def closeEvent(self, event):
        try:
            self.usb_tab.disconnect_usb()
        except Exception:
            pass
        event.accept()
