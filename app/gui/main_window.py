from PyQt6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer

from app.model.SDSUSBModel import SDSUSBModel
from app.tabs.tab_detect import TabDetect
from app.tabs.tab_read import TabRead
from app.tabs.tab_inspector import TabInspector
from app.tabs.tab_usb import TabUSB


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SDS USB Monitor")

        self.model = SDSUSBModel()

        tabs = QTabWidget()

        self.usb_tab = TabUSB(main_window=self)
        tabs.addTab(self.usb_tab, "SDS System")

        self.detect_tab = TabDetect()
        tabs.addTab(self.detect_tab, "Detect")

        self.read_tab = TabRead()
        tabs.addTab(self.read_tab, "Read")

        self.inspector_tab = TabInspector()
        tabs.addTab(self.inspector_tab, "Inspector")

        main = QWidget()
        layout = QVBoxLayout(main)
        layout.addWidget(tabs)
        self.setCentralWidget(main)

        self.timer = QTimer()
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(20)

    def process_queue(self):
        # DETECT
        while not self.model.detect_queue.empty():
            msg_id, frame = self.model.detect_queue.get()
            self.detect_tab.update_frame(frame)

            self.inspector_tab.add_entry(msg_id, len(frame))

        # READ
        while not self.model.read_queue.empty():
            msg_id, frame = self.model.read_queue.get()
            self.read_tab.update_frame(frame)

            self.inspector_tab.add_entry(msg_id, len(frame))
