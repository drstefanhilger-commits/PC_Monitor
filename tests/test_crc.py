"""CRC32 der SDS→PC-Nachrichten (ICD 3.1): zlib-CRC über Kopf + Nutzdaten, little-endian angehängt."""
import binascii

from app.usb.sds_parser import SDSParser

# Read-Nachricht (Id 2, 532 Byte) mit Nullnutzdaten, CRC aus einem Mitschnitt der Firmware
HEX = ("EFBEADDE"          # Magic
       "14020002"          # len_id (len = 532, id = 2)
       "4E61BC00"          # Zeitstempel
       "0000" "0000"       # micNr, frameNr
       + "00" * 512        # 128 × uint32
       + "1DFACD1C")       # CRC32 little-endian


def test_crc_matches_recorded_frame():
    data = bytes.fromhex(HEX)
    assert len(data) == 532
    assert binascii.crc32(data[:-4]) & 0xFFFFFFFF == int.from_bytes(data[-4:], "little")


def _items(data: bytes):
    p = SDSParser()
    p.feed(data)
    out = []
    while (it := p.next_item()) is not None:
        out.append(it)
    return out


def test_parser_accepts_recorded_frame():
    data = bytes.fromhex(HEX)
    assert [(k, i) for k, i, *_ in _items(data)] == [("frame", 2)]


def test_parser_rejects_corrupted_crc():
    data = bytearray.fromhex(HEX)
    data[100] ^= 0x01
    items = _items(bytes(data))
    assert not any(k == "frame" for k, *_ in items)
    assert any(k == "error" and "CRC" in str(r) for k, _raw, r in items)
