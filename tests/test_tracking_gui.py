"""
Tracking in der GUI (T8): Detect + UnitReport je Frame -> Candidate Report -> Tracker; Feedback
(Id 8) nach Bestätigung; Ende nach 2 s ohne Report mit Reset-Feedback; CSV-Export.
Aufruf: QT_QPA_PLATFORM=offscreen python -m pytest tests/test_tracking_gui.py
"""
import csv
import time

import numpy as np

from app.gui.main_window import MainWindow
from tests import sds_frames as F


class FakeWriter:
    def __init__(self):
        self.feedback = []

    def send_feedback(self, ref_state=None, azimuth_deg=None, distance_m=None):
        self.feedback.append((None if ref_state is None else np.array(ref_state), azimuth_deg, distance_m))

    def __getattr__(self, name):              # übrige Kommandos ignorieren
        return lambda *a, **k: None


def feed_drone(w, n, t0_us=1_790_596_800_000_000, bands=(3, 4, 10), probs=(0.95, 0.4, 0.7), az0=40.0):
    rng = np.random.default_rng(3)
    for k in range(n):
        ts = 1000 + 32 * k
        x, y = 50 + 8 * k * 0.032, 60.0                  # 8 m/s nach Osten
        az = float(np.degrees(np.arctan2(x, y)) % 360 + rng.normal(0, 1))
        r = float(np.hypot(x, y) * (1 + rng.normal(0, 0.05)))
        w.model.detect_queue.put((1, F.detect(azi=az, dist=r, conf=0.8, ts=ts)))
        w.model.unit_queue.put((5, F.unit_report(t0_us + 32000 * k, az, list(bands), list(probs), ts=ts)))
        w.process_queue()


def test_track_feedback_timeout_export(qapp, tmp_path):
    w = MainWindow()
    w.timer.stop()
    fw = FakeWriter()
    w.writer = fw
    feed_drone(w, 40)
    t = w.tracker.track
    assert t is not None and t.confirmed and len(t.trajectory) == 38
    assert "bestätigt" in w.detect_tab.track_label.text()
    assert "Spur bestätigt" in w.status.text.toPlainText()
    fb = [f for f in fw.feedback if f[0] is not None]
    assert len(fb) == 38                                  # nach jeder Übernahme der bestätigten Spur
    ref, az, r = fb[-1]
    assert ref[3] > 0.9 and ref[20] == 0 and 30 < az < 60 and 60 < r < 120

    # Störquelle mit anderem Spektrum an derselben Stelle -> verworfen, Spur bleibt
    w.model.unit_queue.put((5, F.unit_report(1_790_596_800_000_000 + 32000 * 40, az, [30, 31, 32], [0.9] * 3, ts=5000)))
    w.process_queue()
    assert w.tracker.track.confirmed and "verworfen (akustisch)" in w.detect_tab.track_label.text()

    # 2 s ohne Report -> Ende, Reset-Feedback
    w._last_accept_host = time.monotonic() - 2.5
    w.process_queue()
    assert w.tracker.track is None and len(w.tracker.finished) == 1
    assert fw.feedback[-1][0] is None
    assert "Spur beendet" in w.status.text.toPlainText()

    # CSV
    path = tmp_path / "spur.csv"
    assert w.export_track(str(path)) == 38
    rows = list(csv.reader(open(path, encoding="utf-8"), delimiter=";"))
    assert rows[0][0] == "spur" and len(rows) == 39
    speed = float(rows[-1][8])
    assert 4 < speed < 12
    w.writer = None
    w.close()


def test_feedback_switch_off(qapp):
    w = MainWindow()
    w.timer.stop()
    fw = FakeWriter()
    w.writer = fw
    w.controls.sw_feedback.click()                       # aus -> sendet Zurücksetzen
    assert fw.feedback == [(None, None, None)]
    feed_drone(w, 10)
    assert w.tracker.track.confirmed and fw.feedback == [(None, None, None)]   # keine weiteren
    w.writer = None
    w.close()
