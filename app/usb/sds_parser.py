"""
SDSParser – Rahmen SDS -> PC aus einem Bytestrom lösen (SDS_110 doc/ICD_SDS_PC_Monitor.md, Abschnitt 3/5)

- Synchronisation Byte für Byte auf das Magic (Bytes EF BE AD DE)
- Länge je bekannter Id fest (Detect 32, Read 532, Log 48, UnitReport 144, Standort 144, Logger 144),
  unbekannte Ids 12 … 1024 Byte
- CRC32 (zlib) über alle Bytes vor den letzten 4, little-endian
- Bei ungültiger Länge oder CRC wird nur 1 Byte verworfen und neu synchronisiert: ein
  scheinbares Magic in den Nutzdaten kostet so keine echten Frames.
"""
import struct
import zlib

MAGIC = 0xDEADBEEF
MAGIC_BYTES = struct.pack("<I", MAGIC)          # EF BE AD DE

# Id -> Gesamtlänge (Byte), siehe ICD Abschnitt 5
FRAME_LENGTH = {1: 32, 2: 532, 3: 48, 5: 144, 6: 144, 99: 144}
MIN_LEN, MAX_LEN = 12, 1024


class SDSParser:
    def __init__(self, max_buffer: int = 1 << 20):
        self.buffer = bytearray()
        self.max_buffer = max_buffer
        self.skipped = 0            # verworfene Bytes seit dem letzten gültigen Magic

    def feed(self, chunk: bytes):
        self.buffer.extend(chunk)
        if len(self.buffer) > self.max_buffer:          # Schutz gegen Dauerstörung
            drop = len(self.buffer) - self.max_buffer
            del self.buffer[:drop]
            self.skipped += drop

    def _sync(self) -> bool:
        """Puffer bis zum nächsten Magic kürzen; True, wenn ein Magic am Anfang steht."""
        i = self.buffer.find(MAGIC_BYTES)
        if i < 0:
            keep = min(len(self.buffer), 3)             # Magic könnte über die Grenze reichen
            self.skipped += len(self.buffer) - keep
            del self.buffer[:len(self.buffer) - keep]
            return False
        if i > 0:
            self.skipped += i
            del self.buffer[:i]
        return True

    def _reject(self, n: int, reason: str):
        raw = bytes(self.buffer[:n])
        del self.buffer[:1]
        self.skipped += 1
        return ("error", raw, reason)

    def next_item(self):
        """
        Liefert
          ("frame", msg_id, raw_frame)    gültiger Rahmen
          ("error", raw_bytes, reason)    reason: "resync <n> Byte", "Invalid msg_len=…", "CRC mismatch"
          None                            zu wenig Daten
        """
        if not self._sync():
            return None
        if self.skipped:                                 # Resync vor diesem Magic einmal melden
            n, self.skipped = self.skipped, 0
            return ("error", b"", f"resync {n} Byte")
        if len(self.buffer) < 8:
            return None

        _, len_id = struct.unpack_from("<II", self.buffer, 0)
        msg_len = len_id & 0x00FFFFFF
        msg_id = (len_id >> 24) & 0xFF
        expected = FRAME_LENGTH.get(msg_id)
        if (expected is not None and msg_len != expected) or not (MIN_LEN <= msg_len <= MAX_LEN):
            return self._reject(8, f"Invalid msg_len={msg_len} (id {msg_id})")

        if len(self.buffer) < msg_len:
            return None

        raw = bytes(self.buffer[:msg_len])
        crc_rx, = struct.unpack_from("<I", raw, msg_len - 4)
        if (zlib.crc32(raw[:-4]) & 0xFFFFFFFF) != crc_rx:
            return self._reject(msg_len, f"CRC mismatch (id {msg_id})")

        del self.buffer[:msg_len]
        return ("frame", msg_id, raw)

    @staticmethod
    def crc32_stm32(data: bytes) -> int:
        """Reflektiertes CRC32 wie crc32.hpp der Firmware (= zlib.crc32)."""
        return zlib.crc32(data) & 0xFFFFFFFF
