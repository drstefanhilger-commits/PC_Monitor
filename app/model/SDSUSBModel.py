from enum import IntEnum
from queue import Queue
import threading

STOP_REQUESTED = threading.Event()

class SDSMessageID(IntEnum):
    DETECT = 1
    READ = 2
    MODE = 3

class SDSMode(IntEnum):
    DETECT = 1
    READ = 2
    CALIBRATE = 3

class SDSUSBModel:
    def __init__(self):
        self.port = None
        self.connected = False
        self.mode = SDSMode.DETECT

        self.detect_queue = Queue()
        self.read_queue = Queue()
        self.inspect_queue = Queue()

        self.last_msg_id = None
        self.last_frame = None
        self.last_reason = None

        self.last_raw_dump = None
        self.last_raw_frame = None

    def update_raw_dump(self, raw: bytes):
        self.last_raw_dump = raw

    def update_raw_frame(self, raw: bytes):
        self.last_raw_frame = raw

    def request_stop(self):
        STOP_REQUESTED.set()

    def clear_all(self):
        while not self.detect_queue.empty():
            self.detect_queue.get_nowait()
        while not self.read_queue.empty():
            self.read_queue.get_nowait()
        while not self.inspect_queue.empty():
            self.inspect_queue.get_nowait()

        self.last_msg_id = None
        self.last_frame = None
        self.last_reason = None

    def set_port(self, port):
        self.port = port

    def set_connected(self, state: bool):
        self.connected = state

    def set_mode(self, mode: SDSMode):
        self.mode = mode

    def update_frame(self, msg_id: int, frame: bytes):
        self.last_msg_id = msg_id
        self.last_frame = frame

    def update_inspector(self, kind: str, raw: bytes, reason: str):
        self.last_msg_id = kind
        self.last_frame = raw
        self.last_reason = reason
