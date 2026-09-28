import queue
import time

import serial
from PyQt6.QtCore import QThread, pyqtSignal


class USBWriter(QThread):
    """
    USBWriter:
    - Thread-sicheres Schreiben über eine Queue
    - send_mode() erzeugt SDS MODE Frames über das Model
    - log_signal liefert thread-safe Logs an den Logger
    - Schreibfehler der Schnittstelle (USB gezogen) -> connection_lost(Grund), Thread endet
    """

    log_signal = pyqtSignal(str)
    connection_lost = pyqtSignal(str)

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
            except (serial.SerialException, OSError) as e:
                if self.running:
                    self.running = False
                    self.connection_lost.emit(f"Schreibfehler: {e}")
                return
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

    def send_unit_id(self, unit_id: int):
        self.send_packet(5, self.model.build_unit_id_message(unit_id), f"Unit-ID {unit_id}")

    def send_srp(self, on: bool):
        self.send_packet(6, self.model.build_srp_message(on), f"SRP {'ein' if on else 'aus'}")

    def send_feedback(self, ref_state=None, azimuth_deg=None, distance_m=None):
        """Feedback der Tracking-Einheit (Id 8); ref_state None = zurücksetzen."""
        from app.tracking.feedback import build_feedback
        pkt = build_feedback(ref_state, azimuth_deg, distance_m)
        name = "Feedback zurücksetzen" if ref_state is None else f"Feedback (Vorhersage {azimuth_deg:.1f}°, {distance_m:.0f} m)"
        self.model.update_sent(8, pkt)
        self.write_queue.put(pkt)
        if ref_state is None:                  # jedes Feedback zu melden wäre bei 31 Reports/s zu viel
            self.log_signal.emit(f"TX {name}")

    def send_sync(self, utc_us: int, temp_c=None):
        t = "unbekannt" if temp_c is None else f"{temp_c:.2f} °C"
        self.send_packet(7, self.model.build_sync_message(utc_us, temp_c), f"Sync ({t})")
