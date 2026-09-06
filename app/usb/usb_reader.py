import threading
import logging
import time
from .sds_parser import SDSParser

class USBReader(threading.Thread):
    def __init__(self, ser, model):
        super().__init__(daemon=True)
        self.ser = ser
        self.model = model
        self.running = True
        self.parser = SDSParser()

    def stop(self):
        self.running = False
        try: self.ser.cancel_read()
        except: pass
        try: self.ser.close()
        except: pass

    @staticmethod
    def expected_length_for_msg_id(msg_id):
        if msg_id == 1: return 20     # DETECT
        if msg_id == 2: return 532    # READ
        if msg_id == 3: return 12     # MODE
        return None

    def run(self):
        while self.running:
            try:
                chunk = self.ser.read(1024)
            except Exception as e:
                logging.error(f"USBReader: read error: {e}")
                time.sleep(0.01)
                continue

            if not chunk:
                time.sleep(0.001)
                continue

            self.parser.feed(chunk)

            while self.running:
                item = self.parser.next_item()
                if item is None:
                    break

                kind = item[0]

                if kind == "error":
                    raw_bytes, reason = item[1], item[2]
                    self.model.inspect_queue.put(("error", raw_bytes, reason))
                    continue

                if kind == "frame":
                    msg_id, frame = item[1], item[2]

                    if len(frame) == USBReader.expected_length_for_msg_id(msg_id):
                        self.model.update_raw_frame(frame)

                    self.model.update_raw_dump(frame)

                    if msg_id == 1:
                        self.model.detect_queue.put((msg_id, frame))
                        self.model.inspect_queue.put(("frame", frame, "DETECT"))

                    elif msg_id == 2:
                        self.model.read_queue.put((msg_id, frame))
                        self.model.inspect_queue.put(("frame", frame, "READ"))

                    elif msg_id == 3:
                        self.model.inspect_queue.put(("frame", frame, "MODE"))

                    else:
                        self.model.inspect_queue.put(
                            ("unknown_msg_id", frame, f"Unknown msg_id={msg_id}")
                        )

            time.sleep(0.001)
