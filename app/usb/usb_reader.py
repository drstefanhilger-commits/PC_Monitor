from PyQt6.QtCore import QThread, pyqtSignal
import time

from app.usb.sds_parser import SDSParser


class USBReader(QThread):
    """
    USBReader (SDS_110 doc/ICD_SDS_PC_Monitor.md, Abschnitt 5):
    - liest verfügbare Bytes und zerlegt sie mit SDSParser (Resync auf das Magic, Länge je Id, CRC)
    - legt gültige Frames nach Id in die Queues des SDSUSBModel:
        1 Detect -> detect_queue, 2 Read -> read_queue, 5 UnitReport -> unit_queue,
        99 Logger -> log_queue, andere -> inspect_queue ("unknown_msg_id")
    - Fehler (Resync, Länge, CRC) -> inspect_queue ("error")
    - meldet Logs über log_signal (thread-safe)
    """

    log_signal = pyqtSignal(str)

    ROUTE = {1: "detect_queue", 2: "read_queue", 5: "unit_queue", 99: "log_queue"}
    CHUNK = 4096

    def __init__(self, ser, model, verbose: bool = False):
        super().__init__()
        self.ser = ser
        self.model = model
        self.running = True
        self.parser = SDSParser()
        # verbose: jedes Frame als Hex melden (bei READ ~3000 Frames/s -> nur zur Diagnose)
        self.verbose = verbose

    def stop(self):
        self.running = False

    def run(self):
        self.log_signal.emit("[USBReader] gestartet")
        while self.running:
            try:
                n = getattr(self.ser, "in_waiting", 0) or 1
                chunk = self.ser.read(min(n, self.CHUNK))
            except Exception as e:
                self.log_signal.emit(f"[USBReader] Lesefehler: {e}")
                time.sleep(0.05)
                continue
            if chunk:
                self.handle_bytes(chunk)

    def handle_bytes(self, chunk: bytes):
        """Bytes zerlegen und verteilen (auch ohne Thread aufrufbar, z. B. in Tests)."""
        self.parser.feed(chunk)
        while True:
            item = self.parser.next_item()
            if item is None:
                return
            if item[0] == "error":
                _, raw, reason = item
                self.model.inspect_queue.put(("error", raw, reason))
                continue
            _, msg_id, frame = item
            self.model.update_raw_dump(frame)
            if self.verbose:
                self.log_signal.emit(f"[USBReader] Frame id {msg_id} ({len(frame)} Byte): {frame.hex()}")
            queue_name = self.ROUTE.get(msg_id)
            if queue_name:
                getattr(self.model, queue_name).put((msg_id, frame))
            else:
                self.model.inspect_queue.put(("unknown_msg_id", frame, f"unknown_msg_id={msg_id}"))
