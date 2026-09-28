"""
Betriebsart READ unter Last (ohne Hardware): ein Thread liefert wie das Board 96 Read-Nachrichten
je 32 ms (~3000/s, ~1,6 MB/s) über den Parser, die Ereignisschleife läuft. Früher fror die GUI ein
(Read-Tab baute je Nachricht Text neu, process_queue ohne Zeitgrenze).
Aufruf: QT_QPA_PLATFORM=offscreen python -m pytest tests/test_read_load.py
"""
import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.model.SDSUSBModel import SDSMode
from app.tabs.tab_read import BLOCK, FULL_SCALE
from app.usb.usb_reader import USBReader
from tests import sds_frames as F


def make_hop(ts, amp):
    """8 Mikrofone × 12 Blöcke; Mikrofon m: Sinus mit Amplitude amp[m] (Anteil der Vollaussteuerung)."""
    n = np.arange(1536)
    out = []
    for m in range(8):
        x = (amp[m] * FULL_SCALE * np.sin(2 * np.pi * 500 * n / 48000)).astype(np.int32)
        for b in range(12):
            out.append(F.read_block(mic=m, block=b, samples=x[b * BLOCK:(b + 1) * BLOCK].tolist(), ts=ts))
    return b"".join(out)


def test_read_mode_under_board_load():
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.show()
    w.controls.mode_dial.set_mode(SDSMode.READ)
    reader = USBReader(None, w.model)
    amp = [0.5 / 2 ** m for m in range(8)]                # -9 dB ... -51 dB (RMS)
    hops = [make_hop(32 * i, amp) for i in range(4)]
    stop = threading.Event()
    sent = [0]

    def board():
        t_next = time.monotonic()
        i = 0
        while not stop.is_set():
            reader.handle_bytes(hops[i % 4]); sent[0] += 96; i += 1
            t_next += 0.032
            time.sleep(max(0.0, t_next - time.monotonic()))

    th = threading.Thread(target=board, daemon=True)
    worst = 0.0
    orig = w.process_queue

    def timed():
        nonlocal worst
        t = time.monotonic(); orig(); worst = max(worst, time.monotonic() - t)
    w.timer.timeout.disconnect()
    w.timer.timeout.connect(timed)

    th.start()
    t_end, gaps, last = time.monotonic() + 2.0, [], time.monotonic()
    while time.monotonic() < t_end:
        app.processEvents()
        now = time.monotonic(); gaps.append(now - last); last = now
        time.sleep(0.005)
    stop.set(); th.join()
    for _ in range(50):                                   # Rest abarbeiten
        app.processEvents(); timed(); time.sleep(0.005)
    w.read_tab.refresh()

    print(f"gesendet {sent[0]}, angezeigt {w.read_tab.frames}, verworfen {w.model.take_dropped()}, "
          f"längster Poll {worst * 1e3:.1f} ms, längste Pause der Ereignisschleife {max(gaps) * 1e3:.1f} ms")
    assert worst < 0.05, "process_queue darf die GUI nicht blockieren"
    assert max(gaps) < 0.15
    assert w.read_tab.frames == sent[0] and w.read_tab.bad == 0
    lv = w.read_tab.levels_dbfs()                          # Sinus: RMS = A / sqrt(2)
    exp = 20 * np.log10(np.array(amp) / np.sqrt(2))
    assert np.allclose(lv, exp, atol=0.1), (lv, exp)
    assert "Blöcke 96/96" in w.read_tab.info_label.text()
    w.close()
