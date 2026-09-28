"""SDSParser (T1): Resync, Längengrenzen je Id, CRC. Aufruf: python -m pytest tests/test_parser.py"""
from app.usb.sds_parser import SDSParser
from tests import sds_frames as F


def drain(p):
    out = []
    while (it := p.next_item()) is not None:
        out.append(it)
    return out


def frames_of(items):
    return [(it[1], it[2]) for it in items if it[0] == "frame"]


def test_single_frames_all_ids():
    p = SDSParser()
    data = F.detect() + F.message(5, F.UNIT_REPORT_PAYLOAD_FW) + F.message(99, b"hello\n") + F.read_block()
    p.feed(data)
    items = drain(p)
    assert [i for i, _ in frames_of(items)] == [1, 5, 99, 2]
    assert all(it[0] == "frame" for it in items)


def test_resync_after_garbage_at_any_offset():
    for k in range(1, 9):                        # alter Reader: Versatz k blieb erhalten
        p = SDSParser()
        p.feed(bytes(range(k)) + F.detect() + F.detect(azi=10))
        items = drain(p)
        assert [i for i, _ in frames_of(items)] == [1, 1], k
        assert items[0] == ("error", b"", f"resync {k} Byte")


def test_split_feed_byte_by_byte():
    p = SDSParser()
    data = F.detect() + F.read_block(mic=3)
    got = []
    for b in data:
        p.feed(bytes([b]))
        got += drain(p)
    assert [i for i, _ in frames_of(got)] == [1, 2]


def test_crc_error_is_rejected_and_next_frame_survives():
    p = SDSParser()
    bad = bytearray(F.detect()); bad[20] ^= 0xFF
    p.feed(bytes(bad) + F.detect(azi=5))
    items = drain(p)
    assert any(it[0] == "error" and it[2].startswith("CRC mismatch") for it in items)
    assert [i for i, _ in frames_of(items)] == [1]


def test_wrong_length_for_known_id():
    p = SDSParser()
    f = bytearray(F.detect()); f[4] = 40            # len_id: Länge 40 statt 32 bei Id 1
    p.feed(bytes(f) + F.detect())
    items = drain(p)
    assert any(it[0] == "error" and "Invalid msg_len=40" in it[2] for it in items)
    assert len(frames_of(items)) == 1


def test_fake_magic_inside_payload():
    # Magic-Bytes in den Samples eines Read-Frames dürfen den Rahmen nicht zerreißen
    s = [0] * 128; s[10] = -0x21524111           # = 0xDEADBEEF als int32 -> Bytes EF BE AD DE
    p = SDSParser()
    p.feed(F.read_block(samples=s) + F.detect())
    assert [i for i, _ in frames_of(drain(p))] == [2, 1]


def test_unknown_id_passes_with_valid_crc():
    p = SDSParser()
    p.feed(F.frame(42, b"\x01\x02\x03\x04"))
    assert frames_of(drain(p)) == [(42, F.frame(42, b"\x01\x02\x03\x04"))]
