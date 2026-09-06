class SDSParser:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, chunk: bytes):
        self.buffer.extend(chunk)

    def next_item(self):
        if len(self.buffer) < 5:
            return None

        msg_id = self.buffer[0]
        length = int.from_bytes(self.buffer[1:4], "big")

        if len(self.buffer) < 4 + length:
            return None

        frame = bytes(self.buffer[:4 + length])
        del self.buffer[:4 + length]

        return ("frame", msg_id, frame)
