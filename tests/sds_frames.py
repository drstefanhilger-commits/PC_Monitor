"""Hilfen für Tests: Frames SDS -> PC wie die Firmware (USBDriver) sie baut."""
import struct
import zlib

# Nutzlast eines UnitReport (128 Byte), erzeugt mit dem Firmware-Code Output_Interface_130
# (SDS_110, dump_unit_report): Unit 0x1234, UTC 1790596800123456 + 32000 µs, Quelle 1 (PC),
# Peilung 123,5°, Residuum 25 µs, 27 Paare, Pegel 0,75, Bänder 3/4/10 mit p = 0,95/0,2/0,7
UNIT_REPORT_PAYLOAD_FW = bytes.fromhex("3412408f35ce895c0600010000f74217b7d1371b030000403f03040af233b200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000")


def frame(msg_id: int, body_after_len: bytes) -> bytes:
    """[magic][len_id][body][crc] wie USBDriver; body_after_len = alles nach len_id."""
    length = 8 + len(body_after_len) + 4
    head = struct.pack("<II", 0xDEADBEEF, (msg_id << 24) | length)
    raw = head + body_after_len
    return raw + struct.pack("<I", zlib.crc32(raw) & 0xFFFFFFFF)


def detect(azi=42.0, dist=80.0, conf=0.9, ts=1234, unit=7) -> bytes:
    return frame(1, struct.pack("<IIfff", ts, unit, azi, dist, conf))


def message(msg_id: int, payload: bytes, ts=0) -> bytes:
    """Message-Rahmen (144 Byte): timestamp + 128 Byte Nutzlast."""
    return frame(msg_id, struct.pack("<I", ts) + payload.ljust(128, b"\0"))


def read_block(mic=0, block=0, samples=None, ts=5, hop=0) -> bytes:
    """Read-Nachricht (Id 2) wie SDS_110 seit 28.09.2026: ts u32, mic u8, block u8, hop u16 (ICD 5.3)."""
    samples = samples or [0] * 128
    return frame(2, struct.pack("<IBBH", ts, mic, block, hop) + struct.pack("<128i", *samples))


def unit_report(time_us, bearing, bands, probs, unit=0x1234, src=1, residual=2e-5, pairs=27, level=0.5, ts=0):
    """UnitReport-Nutzlast (Id 5) wie Output_Interface_130 der Firmware (ICD 5.2)."""
    p = struct.pack("<HQBffBB", unit, time_us, src, bearing, residual, pairs, len(bands))
    p += struct.pack("<f", level) + bytes(bands) + bytes(int(x * 255) for x in probs)
    return message(5, p, ts=ts)
