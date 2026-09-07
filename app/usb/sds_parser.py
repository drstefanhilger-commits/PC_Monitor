import struct
import logging

class SDSParser:
    MAGIC = 0xDEADBEEF

    def __init__(self):
        self.buffer = bytearray()

    def feed(self, chunk: bytes):
        self.buffer.extend(chunk)

    def _find_magic(self):
        """Synchronisation auf 0xDEADBEEF."""
        while len(self.buffer) >= 4:
            magic, = struct.unpack("<I", self.buffer[:4])
            if magic == self.MAGIC:
                return True
            self.buffer.pop(0)
        return False

    def next_item(self):
        """
        Liefert:
        ("frame", msg_id, raw_frame)
        ("error", raw_bytes, reason)
        None (wenn nicht genug Daten)
        """

        # Magic suchen
        if not self._find_magic():
            return None

        # Header prüfen
        if len(self.buffer) < 8:
            return None

        magic, len_id = struct.unpack("<II", self.buffer[:8])
        msg_len =  len_id & 0x00FFFFFF
        msg_id  = (len_id >> 24) & 0xFF

        if magic != self.MAGIC:
            raw = self.buffer[:4]
            del self.buffer[:4]
            return ("error", raw, "Magic mismatch")

        # Länge prüfen
        if msg_len < 12 or msg_len > 1024:
            raw = self.buffer[:8]
            del self.buffer[:8]
            return ("error", raw, f"Invalid msg_len={msg_len}")

        # Warten bis Frame vollständig
        if len(self.buffer) < msg_len:
            return None

        # Frame extrahieren
        raw_frame = bytes(self.buffer[:msg_len])
        del self.buffer[:msg_len]

        # CRC prüfen
        crc_expected, = struct.unpack("<I", raw_frame[-4:])
        crc_calc = self.crc32_stm32(raw_frame[:-4])

        if crc_calc != crc_expected:
            logging.warning(
                f"SDSParser: CRC mismatch calc=0x{crc_calc:08X} expected=0x{crc_expected:08X}"
            )
            return ("error", raw_frame, "CRC mismatch")

        return ("frame", msg_id, raw_frame)

    @staticmethod
    def crc32_stm32(data: bytes) -> int:
        poly = 0xEDB88320
        crc = 0xFFFFFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ poly
                else:
                    crc >>= 1
        return crc ^ 0xFFFFFFFF
