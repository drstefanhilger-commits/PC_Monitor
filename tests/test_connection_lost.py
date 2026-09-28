"""
T6: USB-Abbruch erkennen (ohne Hardware).
- pty: Gegenseite schließen (wie USB ziehen) -> Schalter Off, Fehlermeldung, Threads beendet
- Reader/Writer einzeln mit einer Schnittstelle, die SerialException wirft
- absichtliches Trennen meldet keinen Abbruch
Aufruf: QT_QPA_PLATFORM=offscreen python -m pytest tests/test_connection_lost.py
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import serial
from PyQt6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.model.SDSUSBModel import SDSUSBModel
from app.usb.usb_reader import USBReader
from app.usb.usb_writer import USBWriter


def app():
    return QApplication.instance()          # gehalten in conftest.py


def wait_for(cond, a, timeout=3.0):
    t0 = time.time()
    while not cond() and time.time() - t0 < timeout:
        a.processEvents(); time.sleep(0.01)
    return cond()


class BrokenSerial:
    """Liest n-mal nichts, dann SerialException (wie ein gezogenes Kabel); write wirft sofort."""
    def __init__(self, reads_before_fail=3):
        self.left = reads_before_fail
        self.in_waiting = 0

    def read(self, n):
        if self.left <= 0:
            raise serial.SerialException("ClearCommError failed (Gerät nicht mehr vorhanden)")
        self.left -= 1
        time.sleep(0.01)
        return b""

    def write(self, data):
        raise serial.SerialException("WriteFile failed")

    def close(self):
        pass


def test_reader_emits_once_and_ends():
    a = app()
    r = USBReader(BrokenSerial(), SDSUSBModel())
    got = []
    r.connection_lost.connect(got.append)
    r.start()
    assert wait_for(lambda: got, a)
    assert r.wait(2000) and len(got) == 1 and "ClearCommError" in got[0]


def test_writer_emits_on_write_error():
    a = app()
    w = USBWriter(BrokenSerial(), SDSUSBModel())
    got = []
    w.connection_lost.connect(got.append)
    w.start()
    w.send_mode(1)
    assert wait_for(lambda: got, a)
    assert w.wait(2000) and "WriteFile" in got[0]


def test_intentional_stop_is_not_a_loss():
    a = app()
    r = USBReader(BrokenSerial(reads_before_fail=10**9), SDSUSBModel())
    got = []
    r.connection_lost.connect(got.append)
    r.start(); time.sleep(0.05)
    r.stop(); assert r.wait(2000)
    a.processEvents()
    assert got == []


@pytest.mark.skipif(sys.platform.startswith("win"), reason="pty nur unter Linux/macOS")
def test_unplug_switches_off():
    import tty
    a = app()
    master, slave = os.openpty()
    tty.setraw(master); tty.setraw(slave)
    name = os.ttyname(slave)
    w = MainWindow()
    w.timer.stop()
    try:
        w.controls.port_combo.addItem(name)
        w.controls.port_combo.setCurrentText(name)
        w.controls.sw_power.click()
        assert w.controls.sw_power.isChecked() and w.ser is not None
        os.close(master); master = None           # "Kabel gezogen"
        assert wait_for(lambda: w.ser is None, a), "Abbruch nicht erkannt"
        assert not w.controls.sw_power.isChecked()
        assert w.controls.conn_label.text() == "Verbindung verloren"
        assert "USB-Verbindung zu" in w.status.text.toPlainText() and "verloren" in w.status.text.toPlainText()
        assert w.reader is None and w.writer is None and not w.sync_timer.isActive()
        assert w.controls.port_combo.isEnabled()  # neu verbinden möglich
    finally:
        w.disconnect_usb(); w.close()
        if master is not None:
            os.close(master)
        os.close(slave)
