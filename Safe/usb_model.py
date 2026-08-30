# app/model/usb_model.py

import queue

class SDSUSBModel:
    """
    Minimalistisches, deterministisches Datenmodell für USBReader + TabUSB.
    Keine GUI-Abhängigkeiten, nur Datenhaltung.
    """

    def __init__(self):
        # Updated frame data
        self.last_msg_id = None
        self.last_frame = None

        # Status
        self.port = None
        self.connected = False
        self.mode = "DETECT"

        # Queues für verschiedene Tabs
        self.detect_queue = queue.Queue()
        self.read_queue   = queue.Queue()

    def set_port(self, port: str):
        self.port = port

    def set_connected(self, state: bool):
        self.connected = state

    def set_mode(self, mode: str):
        self.mode = mode

    def update_frame(self, msg_id: int, frame: bytes):
        self.last_msg_id = msg_id
        self.last_frame = frame
