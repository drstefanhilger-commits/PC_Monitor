"""Standort der Einheit lokal (Ost, Nord, Oben in m): Eingabe, Kommando Id 10, Nachricht Id 6, Anzeige, CSV."""
import csv
import struct
import zlib

import pytest

from app.local_position import ORIGIN, LocalPosition, parse_position, same, to_wire
from app.model.SDSUSBModel import SDSUSBModel
from app.usb.messages import parse_position as parse_board_position
from app.usb.sds_parser import SDSParser
from tests import sds_frames as F

P = LocalPosition(123.456, -78.9, 5.5)


def test_parse_text():
    p = parse_position("123.456, -78.9, 5.5")
    assert (p.east_m, p.north_m, p.up_m) == (123.456, -78.9, 5.5)
    assert parse_position(" -50 ; 20 ").up_m == 0.0                            # Oben optional
    assert parse_position("0, 0, 0") == ORIGIN
    for bad in ("48.1", "100001, 0", "0, -100001", "0, 0, 20000", "0, 0, -1001", "12,5 3", "a, b"):
        with pytest.raises(ValueError):
            parse_position(bad)


def test_position_message_matches_firmware_test():
    pkt = SDSUSBModel().build_position_message(P)
    # gleiche Bytes wie SDS_110 test/host/t_local_position.cpp und ICD 4.5
    assert pkt[:24].hex() == "deadbeef0a00001c0001e240fffecbcc0000157c01000000"
    assert pkt[24:] == bytes.fromhex("24CF036D") == (zlib.crc32(pkt[:24]) & 0xFFFFFFFF).to_bytes(4, "big")
    assert len(pkt) == 28
    reset = SDSUSBModel().build_position_message(None)
    assert reset[8:21] == bytes(13)                                              # Flags 0: zurück auf den Ursprung


def board_frame(unit=4660, set_=True, pos=P):
    e, n, u = to_wire(pos)
    return F.message(6, struct.pack("<HBBiii", unit, 0, 1 if set_ else 0, e, n, u))


def test_parse_board_position():
    fr = board_frame()
    p = SDSParser()
    p.feed(fr)
    assert p.next_item()[:2] == ("frame", 6)
    bp = parse_board_position(fr)
    assert bp.unit == 4660 and bp.set
    assert same(bp.local(), P, 1e-6)
    assert "O 123.46" in bp.text() and "Ursprung" not in bp.text()
    assert "(Ursprung)" in parse_board_position(board_frame(set_=False, pos=ORIGIN)).text()


def test_main_window_position(qapp, tmp_path):
    from app.gui.main_window import MainWindow
    from tests.test_tracking_gui import feed_drone
    w = MainWindow()
    w.timer.stop()
    try:
        assert w.position() == ORIGIN and w.controls.pos_edit.text() == "0.000, 0.000, 0.000"   # Grundwert
        w.controls.pos_edit.setText("0, 200000")
        w.controls.btn_pos.click()
        assert w.position() == ORIGIN and "außerhalb" in w.status.text.toPlainText()
        w.controls.pos_edit.setText("123.456, -78.9, 5.5")
        w.controls.btn_pos.click()
        assert w.position() == P and MainWindow().position() == P                   # gespeichert

        # Board meldet dieselbe Position -> normal; eine andere -> orange
        w.model.position_queue.put((6, board_frame()))
        w.process_queue()
        assert "O 123.46" in w.controls.board_pos_label.text()
        assert "ef6c00" not in w.controls.board_pos_label.styleSheet()
        w.model.position_queue.put((6, board_frame(set_=False, pos=ORIGIN)))
        w.process_queue()
        assert "ef6c00" in w.controls.board_pos_label.styleSheet()

        # CSV: Spurpunkte auch im lokalen System (Position der Einheit aus Id 6)
        w.model.position_queue.put((6, board_frame(pos=LocalPosition(10.0, -20.0, 0.0))))
        w.process_queue()
        feed_drone(w, 20)
        path = tmp_path / "spur.csv"
        n = w.export_track(str(path))
        rows = list(csv.reader(open(path, encoding="utf-8"), delimiter=";"))
        assert n > 0 and rows[0][-2:] == ["ost_lokal_m", "nord_lokal_m"]
        assert float(rows[-1][10]) == pytest.approx(float(rows[-1][2]) + 10.0, abs=0.011)
        assert float(rows[-1][11]) == pytest.approx(float(rows[-1][3]) - 20.0, abs=0.011)
    finally:
        w.close()
