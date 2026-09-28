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
