"""
Tracking-Einheit (T8, FSL9 §8–9, Ansprüche 6, 7): simulierte Drohne im Geradeausflug, Reports mit
31,25 Hz und Messrauschen; Störquellen mit anderem Spektrum bzw. an anderer Stelle.
Aufruf: python -m pytest tests/test_tracker.py
"""
import numpy as np
import pytest

from app.tracking import tracker as T
from app.tracking.tracker import CandidateReport, Tracker, cosine

DRONE = np.zeros(64); DRONE[[3, 4, 7, 10]] = [0.95, 0.4, 0.8, 0.7]
NOISE = np.zeros(64); NOISE[[30, 31, 32, 40]] = 0.9            # z. B. Aggregat: anderes Muster


def drone_reports(n, v=(10.0, 0.0), p0=(-100.0, 80.0), dt=0.032, t0=0.0, seed=1):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(n):
        t = t0 + k * dt
        x, y = p0[0] + v[0] * (t - t0), p0[1] + v[1] * (t - t0)
        az = np.degrees(np.arctan2(x, y)) % 360 + rng.normal(0, 1.5)
        r = np.hypot(x, y) * (1 + rng.normal(0, 0.1))
        s = np.clip(DRONE + rng.normal(0, 0.05, 64) * (DRONE > 0), 0, 1)
        out.append(CandidateReport(t, az, r, s))
    return out


def test_confirmation_after_three_reports():
    tr = Tracker()
    ds = [tr.process(r) for r in drone_reports(3)]
    assert [d.status for d in ds] == ["neu", "vorläufig", "bestätigt"]
    assert tr.track.confirmed and len(tr.track.trajectory) == 1


def test_velocity_and_trajectory():
    tr = Tracker()
    for r in drone_reports(160):                                 # 5 s
        tr.process(r)
    p = tr.track.trajectory[-1]
    assert p.speed_ms == pytest.approx(10.0, abs=2.0)
    assert p.course_deg == pytest.approx(90.0, abs=15.0)         # nach Osten
    x_true = -100 + 10 * p.time_s
    assert abs(p.x - x_true) < 15 and abs(p.y - 80) < 15
    assert len(tr.track.trajectory) == 158


def test_acoustic_gate_rejects_other_source_at_plausible_position():
    tr = Tracker()
    for r in drone_reports(60):
        tr.process(r)
    pred = tr.predicted(0.032)
    fake = CandidateReport(pred.time_s, pred.azimuth_deg, pred.distance_m, NOISE)   # genau an der Vorhersage
    d = tr.process(fake)
    assert not d.accepted and d.status == "verworfen" and "akustisch" in d.reason and d.similarity < 0.7
    assert tr.track.confirmed                                    # Spur bleibt


def test_spatial_gate_rejects_same_spectrum_far_away():
    tr = Tracker()
    rs = drone_reports(60)
    for r in rs:
        tr.process(r)
    far = CandidateReport(rs[-1].time_s + 0.032, (rs[-1].azimuth_deg + 120) % 360, rs[-1].distance_m, DRONE)
    d = tr.process(far)
    assert not d.accepted and "räumlich" in d.reason and d.mahalanobis2 > T.CHI2_2_099


def test_tentative_restarts_on_failure():
    tr = Tracker()
    rs = drone_reports(2)
    tr.process(rs[0])
    d = tr.process(CandidateReport(rs[1].time_s, rs[1].azimuth_deg, rs[1].distance_m, NOISE))
    assert d.status == "neu gestartet" and not tr.track.confirmed and tr.track.hits == 1


def test_termination_after_two_seconds():
    tr = Tracker()
    rs = drone_reports(40)
    for r in rs:
        tr.process(r)
    assert not tr.expire(rs[-1].time_s + 1.9)
    assert tr.expire(rs[-1].time_s + 2.1)
    assert tr.track is None and len(tr.finished) == 1 and len(tr.finished[0]) == 38


def test_reference_state_ema():
    tr = Tracker()
    rs = drone_reports(2)
    tr.process(rs[0])
    tr.process(rs[1])
    exp = 0.8 * rs[0].state + 0.2 * rs[1].state
    assert np.allclose(tr.track.ref_state, exp)


def test_cosine():
    assert cosine(DRONE, DRONE) == pytest.approx(1.0)
    assert cosine(DRONE, NOISE) == 0.0 and cosine(np.zeros(64), DRONE) == 0.0


def test_feedback_bytes():
    from app.tracking.feedback import build_feedback
    s = np.zeros(64); s[3], s[4], s[10], s[63] = 0.8, 0.2, 1.0, 0.6
    pkt = build_feedback(s, 123.45, 87.6)
    assert len(pkt) == 52 and pkt[:8] == bytes.fromhex("DEADBEEF08000034")
    assert pkt[9] == 0x0C and pkt[10] == 0x30 and pkt[13] == 0xF0 and pkt[39] == 0x09   # Band 3 = 12, 4 = 3, 10 = 15, 63 = 9
    assert pkt[40:44] == (12345).to_bytes(2, "big") + (876).to_bytes(2, "big") and pkt[44] == 3
    reset = build_feedback(None)
    assert reset[44] == 0 and reset[8:40] == bytes(32)
