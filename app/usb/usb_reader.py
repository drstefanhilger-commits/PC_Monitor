from PyQt6.QtCore import QThread, pyqtSignal
import time
import struct


class USBReader(QThread):
    """
    USBReader:
    - Liest SDS-Frames gemäß C-Strukturen SDS_MsgDetect / SDS_MsgRead
    - Magic: 0xDEADBEEF (Little Endian auf der Leitung: EF BE AD DE)
    - len_id: [len (24bit) | msg_id (8bit)]
    - Schiebt fertige Frames in die Queues des SDSUSBModel
    - Meldet Logs über log_signal (thread-safe)
    """

    log_signal = pyqtSignal(str)

    def __init__(self, ser, model):
        super().__init__()
        self.ser = ser
        self.model = model
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        self.log_signal.emit("[USBReader] gestartet")

        while self.running:
            try:
                # ------------------------------------------------------------
                # HEADER lesen (8 Bytes)
                # ------------------------------------------------------------
                header = self.ser.read(8)
                if len(header) < 8:
                    continue

                # Magic prüfen (Little Endian)
                magic = int.from_bytes(header[0:4], "little")
                if magic != 0xDEADBEEF:
                    self.log_signal.emit(
                        f"[USBReader] MAGIC FAIL: {header[0:4].hex()}"
                    )
                    self.model.inspect_queue.put(
                        ("error", header, "magic_fail")
                    )
                    continue

                # len_id (Little Endian)
                len_id = int.from_bytes(header[4:8], "little")

                msg_id = (len_id >> 24) & 0xFF       # oberes Byte
                length = len_id & 0x00FFFFFF         # untere 24 Bits

                self.log_signal.emit(
                    f"[USBReader] Header OK: magic=DEADBEEF, msg_id={msg_id}, len={length}"
                )

                # ------------------------------------------------------------
                # Rest des Frames nachladen
                # ------------------------------------------------------------
                remaining = length - 8
                payload = self.ser.read(remaining)

                if len(payload) != remaining:
                    self.log_signal.emit(
                        f"[USBReader] Payload unvollständig: {len(payload)} / {remaining}"
                    )
                    self.model.inspect_queue.put(
                        ("error", header + payload, "payload_incomplete")
                    )
                    continue

                frame = header + payload

                # RAW dump aktualisieren
                self.model.update_raw_dump(frame)

                self.log_signal.emit(
                    f"[USBReader] RAW FRAME ({len(frame)} bytes): {frame.hex()}"
                )

                # ------------------------------------------------------------
                # SDS Message Routing
                # ------------------------------------------------------------
                if msg_id == 1:  # DETECT (32 Bytes)
                    self.model.detect_queue.put((msg_id, frame))

                elif msg_id == 2:  # READ (532 Bytes)
                    self.model.read_queue.put((msg_id, frame))

                else:
                    self.model.inspect_queue.put(
                        ("unknown_msg_id", frame, f"unknown_msg_id={msg_id}")
                    )

            except Exception as e:
                self.log_signal.emit(f"[USBReader] Lesefehler: {e}")
                time.sleep(0.05)
