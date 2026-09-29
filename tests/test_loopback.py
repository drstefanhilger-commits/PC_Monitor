"""
Verbindungsweg über einen virtuellen seriellen Port (pty, nur Linux/macOS), ohne Board:
Schalter On -> Board erhält Simulation, Mode, SRP und Sync; Detect, UnitReport und Logger des "Boards"\nkommen nach Störbytes (Resync) an.
Aufruf: QT_QPA_PLATFORM=offscreen python -m pytest tests/test_loopback.py
"""
import os
import struct
import sys
import time
import zlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytestmark = pytest.mark.skipif(sys.platform.startswith("win"), reason="pty nur unter Linux/macOS")

from PyQt6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.model.SDSUSBModel import SDSMode


def detect_frame(azi=42.0, dist=80.0, conf=0.9):
    body = struct.pack("<IIIIfff", 0xDEADBEEF, (1 << 24) | 32, 1234, 7, azi, dist, conf)
    return body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)


def read_exact(fd, n, timeout=2.0):
    buf, t0 = b"", time.time()
    while len(buf) < n and time.time() - t0 < timeout:
        try:
            buf += os.read(fd, n - len(buf))
        except BlockingIOError:
            time.sleep(0.01)
    return buf


def test_power_on_sends_state_and_receives_detect():
    import tty
    app = QApplication.instance() or QApplication([])
    master, slave = os.openpty()
    tty.setraw(master); tty.setraw(slave)
    os.set_blocking(master, False)
    w = MainWindow()
    w.timer.stop()
    try:
        w.controls.port_combo.addItem(os.ttyname(slave))
        w.controls.port_combo.setCurrentText(os.ttyname(slave))
        w.controls.mode_dial.set_mode(SDSMode.READ, emit=False)
        w.settings.setValue("azimuth_offset_deg", -12.34)                     # gespeicherter Nordabgleich
        w.settings.setValue("local_position", "123.456, -78.9, 5.5")          # gespeicherte Position (lokal)
        w.controls.sim_combo.setCurrentIndex(w.controls.sim_combo.findData(7))  # Szenario FlyBy
        w.controls.sw_power.click()
        assert w.controls.sw_power.isChecked()
        cmds = read_exact(master, 16 * 4 + 28 + 24)
        assert cmds[:12] == bytes.fromhex("DEADBEEF03000010" "00000007")      # Simulation FlyBy
        assert cmds[16:28] == bytes.fromhex("DEADBEEF02000010" "00000003")    # READ = 3
        assert cmds[32:44] == bytes.fromhex("DEADBEEF06000010" "00000000")    # SRP aus
        off = cmds[48:64]                                                     # Nordabgleich −12,34°
        assert off[:12] == bytes.fromhex("DEADBEEF09000010" "FFFFFB2E")
        assert off[12:] == (zlib.crc32(off[:12]) & 0xFFFFFFFF).to_bytes(4, "big")
        pos = cmds[64:92]                                                     # Standort Id 10 (lokal)
        assert pos[:24].hex() == "deadbeef0a00001c0001e240fffecbcc0000157c01000000"
        sync = cmds[92:116]
        assert sync[:8] == bytes.fromhex("DEADBEEF07000018")                  # Sync, 24 Byte
        assert abs(int.from_bytes(sync[8:16], "big") / 1e6 - time.time()) < 5
        assert sync[16:18] == (2000).to_bytes(2, "big")                       # 20,0 °C
        assert sync[20:] == (zlib.crc32(sync[:20]) & 0xFFFFFFFF).to_bytes(4, "big")

        # Board sendet Störbytes + Detect + UnitReport + Logger: alles kommt an, Resync wird gemeldet
        from tests import sds_frames as F
        os.write(master, b"\x00\x11\x22" + detect_frame() + F.message(5, F.UNIT_REPORT_PAYLOAD_FW)
                 + F.message(99, b"hallo\n"))
        t0 = time.time()
        while (w.model.stats_detect == 0 or w.model.stats_unit == 0 or w.model.stats_log == 0) \
                and time.time() - t0 < 2:
            app.processEvents(); w.process_queue(); time.sleep(0.02)
        assert (w.model.stats_detect, w.model.stats_unit, w.model.stats_log) == (1, 1, 1)
        assert "resync 3 Byte" in w.status.text.toPlainText()

        w.controls.sw_power.click()
        assert not w.controls.sw_power.isChecked() and w.reader is None
    finally:
        w.disconnect_usb()
        w.close()
        os.close(master); os.close(slave)
