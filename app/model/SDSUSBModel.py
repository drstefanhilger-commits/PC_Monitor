from enum import IntEnum
from queue import Queue


class SDSMessageID(IntEnum):
    DETECT = 1
    READ = 2
    MODE = 2


class SDSMode(IntEnum):
    DETECT = 1
    READ = 2
    CALIBRATE = 3


class SDSUSBModel:
    """
    Zentrales SDS-Datenmodell für USBReader + Tabs.
    Keine GUI-Abhängigkeiten, nur Datenhaltung + Protokolldefinition.
    """

    def __init__(self):
        # Connection state
        self.port = None
        self.connected = False

        # Current SDS mode
        self.mode = SDSMode.DETECT

        # Incoming SDS message queues
        self.detect_queue = Queue()
        self.read_queue = Queue()

        # Last received frame (Inspector)
        self.last_msg_id = None
        self.last_frame = None

        # SDS protocol constants
        self.MSG_MODE_ID = 0x02
        self.MSG_MODE_LEN = 0x00000C  # 12 bytes
        self.MSG_RESERVED = 0x00000000

    # ------------------------------------------------------------
    # Model setters
    # ------------------------------------------------------------
    def set_port(self, port):
        self.port = port

    def set_connected(self, state: bool):
        self.connected = state

    def set_mode(self, mode: SDSMode):
        self.mode = mode

    def update_frame(self, msg_id: int, frame: bytes):
        self.last_msg_id = msg_id
        self.last_frame = frame

    # ------------------------------------------------------------
    # Build SDS Mode Message
    # ------------------------------------------------------------
    def build_mode_message(self, mode_id: int) -> bytes:
        """
        SDS Mode Message Format (12 bytes):
        02 | 00 00 0C | <mode_id BE> | 00 00 00 00
        """

        msg_id     = self.MSG_MODE_ID.to_bytes(1, "big")
        length     = self.MSG_MODE_LEN.to_bytes(3, "big")
        mode_field = mode_id.to_bytes(4, "big")    
        reserved   = self.MSG_RESERVED.to_bytes(4, "big")

        return msg_id + length + mode_field + reserved
