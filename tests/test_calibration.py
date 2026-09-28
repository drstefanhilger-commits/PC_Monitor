"""Nordabgleich (T10): Logik (app/calibration.py), Kommando Id 9, Calibrate-Tab und Hauptfenster."""
import zlib

import numpy as np
import pytest

from app.calibration import (NorthCalibration, circular_stats, new_offset, offset_to_centi, wrap180)
from app.model.SDSUSBModel import SDSMode, SDSUSBModel


def test_wrap180():
    assert wrap180(190) == -170 and wrap180(-190) == 170 and wrap180(180) == 180 and wrap180(-180) == 180
    assert wrap180(360) == 0 and wrap180(725) == 5


def test_circular_mean_across_north():
    st = circular_stats([358.0, 359.0, 0.0, 1.0, 2.0])
    assert st.n == 5
    assert min(st.mean_deg, 360 - st.mean_deg) < 1e-9          # 0°, nicht 144°
    assert 1.0 < st.spread_deg < 2.0
    assert circular_stats([]) is None


def test_spread_of_noisy_bearings():
    rng = np.random.default_rng(1)
    b = (123.0 + rng.normal(0, 3.0, 2000)) % 360
    st = circular_stats(b)
    assert abs(st.mean_deg - 123.0) < 0.3 and abs(st.spread_deg - 3.0) < 0.3


def test_new_offset_includes_old_offset():
    # roh 10°, alter Offset +5° -> gemessen 15°; Referenz 30° -> neu 20° (roh + 20 = 30)
    assert new_offset(5.0, 30.0, 15.0) == pytest.approx(20.0)
    # über Nord: gemessen 350°, Referenz 10° -> +20°
    assert new_offset(0.0, 10.0, 350.0) == pytest.approx(20.0)
    assert new_offset(170.0, 30.0, 0.0) == pytest.approx(-160.0)   # auf ±180° gebracht


def test_offset_to_centi_range():
    assert offset_to_centi(-12.34) == -1234 and offset_to_centi(180.0) == 18000
    with pytest.raises(ValueError):
        offset_to_centi(180.01)


def test_measurement_window():
    c = NorthCalibration()
    assert not c.add(10.0, 0.0)                                   # nicht gestartet
    c.start(90.0, 2.0, 5.0, now=100.0)
    for i in range(21):                                           # je 7 × 86°, 87°, 88°
        assert c.add(87.0 + (i % 3) - 1, now=100.0 + i * 0.2)
    assert not c.finish_if_due(104.9)
    assert not c.add(0.0, now=105.5)                              # nach der Messdauer
    assert c.finish_if_due(105.0) and not c.running
    r = c.result()
    assert r.stats.n == 21 and r.error_deg == pytest.approx(3.0, abs=0.05)
    assert r.offset_deg == pytest.approx(5.0, abs=0.05) and r.warnings() == []


def test_warnings_few_and_scattered():
    c = NorthCalibration()
    c.start(0.0, 0.0, 1.0, now=0.0)
    for b in (0.0, 20.0, 340.0):
        c.add(b, now=0.1)
    w = c.result().warnings()
    assert any("Peilungen" in x for x in w) and any("Streuung" in x for x in w)


def test_azimuth_offset_message_matches_icd():
    pkt = SDSUSBModel().build_azimuth_offset_message(-12.34)
    assert pkt[:12] == bytes.fromhex("DEADBEEF09000010FFFFFB2E")
    assert pkt[12:] == (zlib.crc32(pkt[:12]) & 0xFFFFFFFF).to_bytes(4, "big")
    assert SDSUSBModel().build_azimuth_offset_message(15.0)[8:12] == (1500).to_bytes(4, "big")
    with pytest.raises(ValueError):
        SDSUSBModel().build_azimuth_offset_message(200.0)


class _R:
    def __init__(self, b):
        self.bearing_deg = b


def test_tab_measures_and_applies(qapp):
    from app.tabs.tab_calibrate import TabCalibrate
    now = [0.0]
    tab = TabCalibrate(clock=lambda: now[0])
    tab.set_offset(1.0)
    tab.ref_spin.setValue(45.0)
    tab.dur_spin.setValue(2.0)
    got = []
    tab.offset_apply.connect(got.append)
    tab.update_unit_report(_R(40.0))                              # vor dem Start: ignoriert
    tab.start_btn.click()
    assert tab.cal.running and tab.start_btn.text() == "Abbrechen"
    for i in range(30):
        now[0] = i * 0.05
        tab.update_unit_report(_R(41.0 + 0.5 * ((i % 2) * 2 - 1)))
    now[0] = 2.1
    tab.tick()
    assert tab.apply_btn.isEnabled() and "+5.00" in tab.result_label.text()
    tab.apply_btn.click()
    assert got == [pytest.approx(5.0, abs=1e-6)]


def test_tab_without_reports(qapp):
    from app.tabs.tab_calibrate import TabCalibrate
    now = [0.0]
    tab = TabCalibrate(clock=lambda: now[0])
    tab.start_btn.click()
    now[0] = 10.0
    tab.tick()
    assert not tab.apply_btn.isEnabled() and "Keine Peilungen" in tab.result_label.text()


def test_main_window_stores_offset_and_routes_reports(qapp):
    from app.gui.main_window import MainWindow
    from tests import sds_frames as F
    from app import __version__
    w = MainWindow()
    w.timer.stop()
    try:
        assert __version__ in w.windowTitle()
        assert w.azimuth_offset() == 0.0
        w.calibrate_tab.offset_apply.emit(-7.5)                   # nicht verbunden: nur speichern
        assert w.azimuth_offset() == -7.5 and "-7.50" in w.calibrate_tab.offset_label.text()
        assert MainWindow().azimuth_offset() == -7.5              # bleibt über einen Neustart
        # UnitReports erreichen den Calibrate-Tab
        w.controls.mode_dial.set_mode(SDSMode.CALIBRATE)
        w.calibrate_tab.start_btn.click()
        w.model.put_frame(w.model.unit_queue, (5, F.message(5, F.UNIT_REPORT_PAYLOAD_FW)))
        w.process_queue()
        assert len(w.calibrate_tab.cal.bearings) == 1
    finally:
        w.close()
