import queue
import time
from PyQt6.QtCore import QThread, pyqtSignal


class USBWriter(QThread):
    """
    USBWriter:
    - Thread-sicheres Schreiben über eine Queue
    - send_mode() erzeugt SDS MODE Frames über das Model
    - log_signal liefert thread-safe Logs an den Logger
    """

    log_signal = pyqtSignal(str)

    def __init__(self, ser, model):
        super().__init__()
        self.ser = ser
        self.model = model
        self.running = True
        self.write_queue = queue.Queue()

    def stop(self):
        self.running = False

    def run(self):
        self.log_signal.emit("[USBWriter] gestartet")

        while self.running:
            try:
                packet = self.write_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                self.ser.write(packet)
                time.sleep(0.002)  # deterministisches pacing
            except Exception as e:
                self.log_signal.emit(f"[USBWriter] Schreibfehler: {e}")
                time.sleep(0.05)

    # ------------------------------------------------------------
    # MODE MESSAGE SENDEN (protokoll-korrekt)
    # ------------------------------------------------------------
    def send_mode(self, mode_id: int):
        """
        Baut und sendet eine SDS MODE Message gemäß
        dem Frame-Layout in SDSUSBModel.build_mode_message().
        """

        # SDS-konformen Frame aus dem Model holen
        packet = self.model.build_mode_message(mode_id)

        # Logging (sichtbar im Inspector)
        self.log_signal.emit(f"[USBWriter] MODE Frame: {packet.hex()}")

        # Statistik aktualisieren
        self.model.update_sent(3, packet)

        # Senden
        self.write_queue.put(packet)
