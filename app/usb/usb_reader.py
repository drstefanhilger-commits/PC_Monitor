import threading
import serial
import struct


class USBReader(threading.Thread):
    def __init__(self, port, baud, model):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.model = model
        self.running = True
        self.ser = None

    def stop(self):
        self.running = False
        if self.ser:
            try:
                self.ser.close()
            except:
                pass

    def run(self):
        # Port EINMAL öffnen
        self.ser = serial.Serial(self.port, self.baud, timeout=0.1)

        while self.running:
            try:
                header = self.ser.read(8)
            except:
                continue

            if len(header) != 8:
                continue

            magic, msg_id, length = struct.unpack("<IB3s", header)
            payload_len = length[2]

            try:
                payload = self.ser.read(payload_len)
                crc = self.ser.read(4)
            except:
                continue

            frame = header + payload + crc

            if msg_id == 1:
                self.model.detect_queue.put((msg_id, frame))
            elif msg_id == 2:
                self.model.read_queue.put((msg_id, frame))

        try:
            self.ser.close()
        except:
            pass

    def send_mode(self, mode_id: int):
        if not self.ser:
            return

        packet = self.model.build_mode_message(mode_id)

        try:
            self.ser.write(packet)
        except:
            pass
