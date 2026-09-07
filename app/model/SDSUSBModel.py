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
    """
    Zentrales SDS-Datenmodell für USBReader + USBWriter + Inspector.
    Thread-safe durch Queues.
    """

    def __init__(self):
        # ------------------------------------------------------------
        # Connection state
        # ------------------------------------------------------------
        self.port = None
        self.connected = False
        self.mode = SDSMode.DETECT

        # ------------------------------------------------------------
        # Incoming SDS message queues
        # ------------------------------------------------------------
        self.detect_queue = Queue()
        self.read_queue = Queue()
        self.inspect_queue = Queue()

        # ------------------------------------------------------------
        # Inspector last-frame info (empfangen)
        # ------------------------------------------------------------
        self.last_msg_id = None
        self.last_frame = None
        self.last_reason = None

        # RAW dump (letzter empfangener Chunk)
        self.last_raw_dump = None

        # Vollständiger Frame (nur wenn Länge korrekt)
        self.last_raw_frame = None

        # ------------------------------------------------------------
        # Inspector statistics (empfangen)
        # ------------------------------------------------------------
        self.stats_total = 0
        self.stats_detect = 0
        self.stats_read = 0
        self.stats_rejected = 0
        self.stats_unknown = 0
        self.stats_corrupt = 0

        # ------------------------------------------------------------
        # Send-Statistik
        # ------------------------------------------------------------
        self.stats_sent_total = 0
        self.stats_sent_by_id = {1: 0, 2: 0, 3: 0}
        self.last_sent_frame = None
        self.last_sent_msg_id = None

        # Inspector-Tab Referenz (wird im MainWindow gesetzt)
        self.inspector = None

    # ------------------------------------------------------------
    # RAW-Dump aktualisieren
    # ------------------------------------------------------------
    def update_raw_dump(self, raw: bytes):
        self.last_raw_dump = raw

    # ------------------------------------------------------------
    # Vollständigen Frame aktualisieren
    # ------------------------------------------------------------
    def update_raw_frame(self, raw: bytes):
        self.last_raw_frame = raw

    # ------------------------------------------------------------
    # Stop-Flag setzen
    # ------------------------------------------------------------
    def request_stop(self):
        STOP_REQUESTED.set()

    # ------------------------------------------------------------
    # Queues leeren
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # Model setters
    # ------------------------------------------------------------
    def set_port(self, port):
        self.port = port

    def set_connected(self, state: bool):
        self.connected = state

    def set_mode(self, mode: SDSMode):
        self.mode = mode

    # ------------------------------------------------------------
    # Letzten empfangenen Frame + Reason aktualisieren
    # ------------------------------------------------------------
    def update_frame(self, msg_id: int, frame: bytes, reason: str):
        self.last_msg_id = msg_id
        self.last_frame = frame
        self.last_reason = reason

    # ------------------------------------------------------------
    # Inspector-Update (Fehler/Unknown)
    # ------------------------------------------------------------
    def update_inspector(self, kind: str, raw: bytes, reason: str):
        self.last_msg_id = kind
        self.last_frame = raw
        self.last_reason = reason

    # ------------------------------------------------------------
    # Statistik für empfangene Frames aktualisieren
    # ------------------------------------------------------------
    def update_stats(self, msg_id: int, reason: str):
        self.stats_total += 1

        if reason == "DETECT":
            self.stats_detect += 1

        elif reason == "READ":
            self.stats_read += 1

        elif reason == "CORRUPT":
            self.stats_corrupt += 1
            self.stats_rejected += 1

        elif reason == "UNKNOWN":
            self.stats_unknown += 1
            self.stats_rejected += 1

    # ------------------------------------------------------------
    # Send-Statistik aktualisieren
    # ------------------------------------------------------------
    def update_sent(self, msg_id: int, frame: bytes):
        self.stats_sent_total += 1
        if msg_id in self.stats_sent_by_id:
            self.stats_sent_by_id[msg_id] += 1
        self.last_sent_msg_id = msg_id
        self.last_sent_frame = frame

    # ------------------------------------------------------------
    # MODE-Message bauen (USBWriter) – SDS-Protokoll-korrekt
    # ------------------------------------------------------------
    def _build_header_and_payload(self, msg_id: int, value: int) -> bytes:
        magic = b"\xDE\xAD\xBE\xEF"              # Magic (Big Endian)
        msg_id_b = msg_id.to_bytes(1, "big")    # 1, 2, 3
        total_len = (16).to_bytes(3, "big")     # 00 00 10

        payload = value.to_bytes(4, "big")      # 00 00 00 vv
        crc = b"\x12\x34\x56\x78"               # Dummy CRC

        return magic + msg_id_b + total_len + payload + crc

    def build_time_sync_message(self) -> bytes:
        # Time-Sync: Wert immer 0
        return self._build_header_and_payload(1, 0)

    def build_mode_message(self, mode_id: int) -> bytes:
        # Mode: 1=Detect, 2=Read, 3=Calibrate
        return self._build_header_and_payload(2, mode_id)

    def build_simulation_message(self, sim_state: int) -> bytes:
        # Simulation: 0=Real, 1=Simulated
        return self._build_header_and_payload(3, sim_state)
