"""Standort der Einheit: Eingabe, Kommando Id 10, Nachricht Id 6, Anzeige, CSV mit Breite/Länge."""
import csv
import struct
import zlib

import pytest

from app.geo import GeoPosition, enu_to_geodetic, parse_position, to_wire
from app.model.SDSUSBModel import SDSUSBModel
from app.usb.messages import parse_position as parse_board_position
from app.usb.sds_parser import SDSParser
from tests import sds_frames as F

MUC = GeoPosition(48.137154, 11.57549, 519.5)


def test_parse_text():
    p = parse_position("48.137154, 11.57549, 519.5")
    assert (p.lat_deg, p.lon_deg, p.alt_m) == (48.137154, 11.57549, 519.5)
    assert parse_position(" -33.8688 ; 151.2093 ").alt_m == 0.0               # Höhe optional
    for bad in ("48.1", "91, 0", "0, 181", "0, 0, 20000", "48,1 11,5", "a, b"):
        with pytest.raises(ValueError):
            parse_position(bad)


def test_position_message_matches_firmware_test():
    pkt = SDSUSBModel().build_position_message(MUC)
    # gleiche Bytes wie SDS_110 test/host/t_geo_position.cpp
    assert pkt[:24].hex() == "deadbeef0a00001c1cb1259406e647940007ed4c01000000"
    assert pkt[24:] == (zlib.crc32(pkt[:24]) & 0xFFFFFFFF).to_bytes(4, "big")
    assert len(pkt) == 28
    south = SDSUSBModel().build_position_message(GeoPosition(-33.8688, -151.2093, -12.0))
    assert struct.unpack(">iii", south[8:20]) == (-338688000, -1512093000, -12000)
    clear = SDSUSBModel().build_position_message(None)
    assert clear[8:21] == bytes(13)                                              # Flags 0: löschen


def board_frame(unit=4660, src=1, valid=True, pos=MUC):
    lat, lon, alt = to_wire(pos)
    return F.message(6, struct.pack("<HBBiii", unit, src, 1 if valid else 0, lat, lon, alt))


def test_parse_board_position():
    fr = board_frame()
    p = SDSParser()
    p.feed(fr)
    assert p.next_item()[:2] == ("frame", 6)
    bp = parse_board_position(fr)
    assert bp.unit == 4660 and bp.valid and bp.source_name == "PC"
    assert bp.lat_deg == pytest.approx(48.137154, abs=1e-9) and bp.alt_m == pytest.approx(519.5)
    assert "(PC)" in bp.text()
    assert parse_board_position(board_frame(src=0, valid=False)).text() == "kein Standort"


def _haversine_m(lat1, lon1, lat2, lon2, r=6371008.8):
    import math
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def test_enu_to_geodetic():
    # 1 km nach Nord / Ost: unabhängig über Haversine zurückgerechnet (Kugel, daher 0,5 % Toleranz)
    lat, lon = enu_to_geodetic(MUC, 0.0, 1000.0)
    assert lon == MUC.lon_deg and lat > MUC.lat_deg
    assert _haversine_m(MUC.lat_deg, MUC.lon_deg, lat, lon) == pytest.approx(1000.0, rel=5e-3)
    lat, lon = enu_to_geodetic(MUC, 1000.0, 0.0)
    assert lat == MUC.lat_deg and lon > MUC.lon_deg
    assert _haversine_m(MUC.lat_deg, MUC.lon_deg, lat, lon) == pytest.approx(1000.0, rel=5e-3)
    lat, lon = enu_to_geodetic(MUC, -300.0, -400.0)                           # Süd-West, 500 m
    assert _haversine_m(MUC.lat_deg, MUC.lon_deg, lat, lon) == pytest.approx(500.0, rel=5e-3)


def test_main_window_position(qapp, tmp_path):
    from app.gui.main_window import MainWindow
    from tests.test_tracking_gui import feed_drone
    w = MainWindow()
    w.timer.stop()
    try:
        assert w.position() is None
        w.controls.pos_edit.setText("91, 0")
        w.controls.btn_pos.click()
        assert w.position() is None and "außerhalb" in w.status.text.toPlainText()
        w.controls.pos_edit.setText("48.137154, 11.57549, 519.5")
        w.controls.btn_pos.click()
        assert w.position() == MUC and MainWindow().position() == MUC          # gespeichert

        # Board meldet denselben Standort -> normal; einen anderen -> orange
        w.model.position_queue.put((6, board_frame()))
        w.process_queue()
        assert "48.1371540" in w.controls.board_pos_label.text()
        assert "ef6c00" not in w.controls.board_pos_label.styleSheet()
        w.model.position_queue.put((6, board_frame(pos=GeoPosition(48.0, 11.0, 500.0))))
        w.process_queue()
        assert "ef6c00" in w.controls.board_pos_label.styleSheet()
        w.model.position_queue.put((6, board_frame(src=2, pos=GeoPosition(48.2, 11.6, 510.0))))
        w.process_queue()
        assert "(GNSS)" in w.controls.board_pos_label.text()

        # CSV: Breite/Länge je Punkt (Ursprung = vom Board gemeldeter Standort)
        feed_drone(w, 20)
        path = tmp_path / "spur.csv"
        n = w.export_track(str(path))
        rows = list(csv.reader(open(path, encoding="utf-8"), delimiter=";"))
        assert n > 0 and rows[0][-2:] == ["breite_deg", "laenge_deg"]
        lat, lon = float(rows[-1][10]), float(rows[-1][11])
        exp = enu_to_geodetic(GeoPosition(48.2, 11.6, 510.0), float(rows[-1][2]), float(rows[-1][3]))
        assert (lat, lon) == pytest.approx(exp, abs=1e-7)
    finally:
        w.close()
