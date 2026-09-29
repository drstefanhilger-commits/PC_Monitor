"""Detect-Tab (T5): Azimut 0° = Nord, im Uhrzeigersinn; Lageplan Nord oben, Ost rechts; Radius automatisch."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from app.tabs.tab_detect import choose_range, compass_xy, TabDetect
from tests import sds_frames as F


@pytest.mark.parametrize("az,exp", [(0, (0, 100)), (90, (100, 0)), (180, (0, -100)), (270, (-100, 0)),
                                    (45, (70.71, 70.71))])
def test_compass_xy(az, exp):
    x, y = compass_xy(az, 100)
    assert x == pytest.approx(exp[0], abs=0.01) and y == pytest.approx(exp[1], abs=0.01)


def test_choose_range():
    assert choose_range([]) == 25 and choose_range([40]) == 50 and choose_range([95]) == 200
    assert choose_range([300, 10]) == 500 and choose_range([1e6]) == 5000


def test_point_east_and_range_follows_distance():
    app = QApplication.instance() or QApplication([])
    t = TabDetect()
    t.update_frame(F.detect(azi=90.0, dist=300.0, conf=0.7))
    xs, ys = t.point.getData()
    assert xs[0] == pytest.approx(300, abs=0.01) and ys[0] == pytest.approx(0, abs=0.01)
    assert t.range_m == 500
    assert "Azimut  90.0°" in t.pos_label.text()
    t.update_frame(F.detect(azi=359.0, dist=20.0, conf=0.7))
    assert t.range_m == 500                         # Verlauf enthält noch 300 m
    assert len(t.trail_xy) == 2


def _finite(curve):
    import numpy as np
    _x, y = curve.getData()
    return 0 if y is None else int(np.isfinite(np.asarray(y, dtype=float)).sum())


def test_gap_without_detect_clears_display():
    """FlyBy-Pause: ohne Detect laufen Distanz, Azimut, Konfidenz mit Lücken weiter, alte Werte laufen hinaus."""
    import numpy as np
    from app.tabs.tab_detect import FRAME_S, GAP_S, HISTORY
    app = QApplication.instance() or QApplication([])
    t = TabDetect()
    for k in range(3):
        t.update_frame(F.detect(azi=10.0 * k, dist=80.0, conf=0.8), now=k * FRAME_S)
    last = 2 * FRAME_S
    t.tick(now=last + GAP_S * 0.9)                        # kurze Pause: nichts ändert sich
    assert len(t.dist_history) == 3 and len(t.point.getData()[0]) == 1

    t.tick(now=last + 1.0)                                # 1 s ohne Detect
    n = int(1.0 / FRAME_S)
    assert len(t.dist_history) == 3 + n and np.isnan(t.dist_history[-1]) and np.isnan(t.conf_history[-1])
    assert _finite(t.dist_curve) == 3 and _finite(t.curve_conf) == 3 and _finite(t.az_curve) == 3
    xs, _ = t.point.getData()
    assert xs is None or len(xs) == 0                     # Punkt und Linie gelöscht
    assert t.pos_label.text().startswith("Azimut –")

    t.tick(now=last + 1.0 + HISTORY * FRAME_S)            # lange Pause: alte Werte vollständig hinaus
    assert len(t.dist_history) == HISTORY
    assert _finite(t.dist_curve) == 0 and _finite(t.az_curve) == 0 and _finite(t.curve_conf) == 0
    assert all(p is None for p in t.trail_xy)

    t.update_frame(F.detect(azi=90.0, dist=80.0, conf=0.9), now=last + 20.0)   # nächster Überflug
    assert _finite(t.dist_curve) == 1 and "Azimut  90.0°" in t.pos_label.text()
    assert len(t.dist_history) == HISTORY                 # Takt läuft weiter, kein Nachfüllen rückwirkend
