"""
GUI ohne Hardware (Qt offscreen): Bedienfeld links, Tabs je Betriebsart, Status unten.
Aufruf: QT_QPA_PLATFORM=offscreen python -m pytest tests/test_gui.py
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.model.SDSUSBModel import SDSMode


class FakeWriter:
    def __init__(self):
        self.sent = []

    def send_mode(self, mode_id):
        self.sent.append(("mode", mode_id))

    def send_simulation(self, on):
        self.sent.append(("sim", on))

    def send_srp(self, on):
        self.sent.append(("srp", on))

    def send_unit_id(self, uid):
        self.sent.append(("unit", uid))

    def send_sync(self, utc_us, temp):
        self.sent.append(("sync", utc_us, temp))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    w = MainWindow()
    w.timer.stop()
    yield w
    w.close()


def visible_tabs(w):
    return [w.tabs.tabText(i) for i in range(w.tabs.count()) if w.tabs.isTabVisible(i)]


def test_layout(win):
    assert [win.tabs.tabText(i) for i in range(win.tabs.count())] == ["Detect", "Read", "Calibrate"]
    assert visible_tabs(win) == ["Detect"]
    assert win.controls.width() == win.controls.WIDTH


@pytest.mark.parametrize("mode,tab", [(SDSMode.READ, "Read"), (SDSMode.CALIBRATE, "Calibrate"),
                                      (SDSMode.DETECT, "Detect")])
def test_dial_selects_tab_and_sends_mode(win, mode, tab):
    other = SDSMode.READ if mode != SDSMode.READ else SDSMode.DETECT
    win.controls.mode_dial.set_mode(other)            # Ausgangslage != Ziel (ohne Änderung kein Kommando)
    fw = FakeWriter()
    win.writer = fw
    win.controls.mode_dial.set_mode(mode)
    assert visible_tabs(win) == [tab]
    assert win.tabs.currentWidget() is win.tabs.widget(win.tab_index[mode])
    assert fw.sent[-1] == ("mode", int(mode))
    win.writer = None


def test_dial_order_detect_read_calibrate(win):
    d = win.controls.mode_dial.dial
    seen = []
    for v in range(d.minimum(), d.maximum() + 1):
        d.setValue(v)
        seen.append(visible_tabs(win)[0])
    assert seen == ["Detect", "Read", "Calibrate"]


def test_simulation_switch(win):
    fw = FakeWriter()
    win.writer = fw
    assert win.controls.simulation() is True          # Firmware-Standard Simulation
    win.controls.sw_sim.click()
    assert fw.sent[-1] == ("sim", False)
    win.controls.sw_sim.click()
    assert fw.sent[-1] == ("sim", True)
    win.writer = None


def test_power_without_port_logs_error(win):
    win.controls.port_combo.clear()
    win.controls.sw_power.click()
    assert win.controls.sw_power.isChecked() is False
    assert "Kein COM-Port" in win.status.text.toPlainText()


def test_errors_go_to_status(win):
    win.model.inspect_queue.put(("error", bytes.fromhex("0011"), "magic_fail"))
    win.process_queue()
    assert "magic_fail" in win.status.text.toPlainText()
    assert win.model.stats_rejected == 1


def test_srp_unit_id_sync_controls(win):
    import time
    fw = FakeWriter()
    win.writer = fw
    win.controls.sw_srp.click()
    assert fw.sent[-1] == ("srp", True)
    win.controls.unit_spin.setValue(0x2A)
    win.controls.btn_unit.click()
    assert fw.sent[-1] == ("unit", 0x2A)
    win.controls.temp_spin.setValue(-12.5)
    win.controls.btn_sync.click()
    kind, utc, temp = fw.sent[-1]
    assert kind == "sync" and temp == -12.5 and abs(utc / 1e6 - time.time()) < 5
    win.controls.chk_temp.setChecked(False)            # Temperatur aus -> sofort Sync mit "unbekannt"
    assert fw.sent[-1][0] == "sync" and fw.sent[-1][2] is None
    win.writer = None


def test_unit_report_and_logger_display(win):
    from tests import sds_frames as F
    win.model.unit_queue.put((5, F.message(5, F.UNIT_REPORT_PAYLOAD_FW)))
    win.model.log_queue.put((99, F.message(99, b"124: Modell ok\n")))
    win.process_queue()
    assert "Unit 4660 " in win.detect_tab.unit_label.text()          # dezimal
    assert "2026-09-28 12:00:00.155456 UTC" in win.detect_tab.unit_label.text()
    assert "Paare 27" in win.detect_tab.unit_label.text()
    assert "SDS: 124: Modell ok" in win.status.text.toPlainText()
    assert win.model.stats_unit == 1 and win.model.stats_log == 1 and win.model.stats_rejected == 0


def test_clear_resets_messages_and_counters(win):
    win.model.stats_total, win.model.stats_rejected, win.model.stats_sent_total = 12, 3, 5
    win.model.stats_detect = 9
    win.status.log("Testmeldung", "ERROR")
    win.status.update_stats()
    assert "RX 12" in win.status.stats_label.text()
    win.status.btn_clear.click()
    assert win.status.text.toPlainText() == ""
    m = win.model
    assert (m.stats_total, m.stats_detect, m.stats_rejected, m.stats_sent_total) == (0, 0, 0, 0)
    assert "RX 0" in win.status.stats_label.text() and "Fehler 0" in win.status.stats_label.text()
