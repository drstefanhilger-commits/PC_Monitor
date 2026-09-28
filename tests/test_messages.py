"""Dekodierung der Nachrichten SDS -> PC (T2). Aufruf: python -m pytest tests/test_messages.py"""
import pytest

from app.usb.messages import LineAssembler, parse_detect, parse_logger, parse_unit_report
from tests import sds_frames as F


def test_unit_report_from_firmware_bytes():
    r = parse_unit_report(F.message(5, F.UNIT_REPORT_PAYLOAD_FW, ts=99))
    assert r.unit == 0x1234 and r.source == 1 and r.source_name == "UTC (PC)"
    assert r.time_us == 1790596800123456 + 32000
    assert r.time_text() == "2026-09-28 12:00:00.155456 UTC"
    assert r.bearing_deg == pytest.approx(123.5)
    assert r.residual_s == pytest.approx(25e-6)
    assert r.pairs == 27 and r.level == pytest.approx(0.75)
    assert r.bands == [3, 4, 10]
    assert [round(p, 3) for p in r.probs] == [round(242 / 255, 3), round(51 / 255, 3), round(178 / 255, 3)]
    v = r.state_vector()
    assert len(v) == 64 and v[3] > 0.9 and v[0] == 0.0


def test_unit_report_uptime_source():
    pay = bytearray(F.UNIT_REPORT_PAYLOAD_FW); pay[10] = 0
    pay[2:10] = (12_345_678).to_bytes(8, "little")
    r = parse_unit_report(F.message(5, bytes(pay)))
    assert r.source_name == "Laufzeit" and r.time_text() == "12.345678 s seit Start"


def test_unit_report_bad_nsel():
    pay = bytearray(F.UNIT_REPORT_PAYLOAD_FW); pay[20] = 60
    with pytest.raises(ValueError):
        parse_unit_report(F.message(5, bytes(pay)))


def test_detect():
    d = parse_detect(F.detect(azi=12.5, dist=33.0, conf=0.5, ts=7, unit=3))
    assert (d.timestamp_ms, d.unit, d.azimuth_deg, d.distance_m, d.confidence) == (7, 3, 12.5, 33.0, 0.5)


def test_logger_lines():
    la = LineAssembler()
    assert la.push(parse_logger(F.message(99, b"116: SAI st"))) == []
    assert la.push(parse_logger(F.message(99, b"art ok\r\nzweite\n"))) == ["116: SAI start ok", "zweite"]
