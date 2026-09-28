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
