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
    # Kommandos senden (Frames baut das Model, ICD Abschnitt 4)
    # ------------------------------------------------------------
    def send_packet(self, msg_id: int, packet: bytes, name: str):
        self.log_signal.emit(f"TX {name}: {packet.hex(' ').upper()}")
        self.model.update_sent(int(msg_id), packet)
        self.write_queue.put(packet)

    def send_mode(self, mode_id: int):
        self.send_packet(2, self.model.build_mode_message(mode_id), f"Mode {mode_id}")

    def send_simulation(self, on: bool):
        self.send_packet(3, self.model.build_simulation_message(1 if on else 0),
                         "Simulation" if on else "Real")
