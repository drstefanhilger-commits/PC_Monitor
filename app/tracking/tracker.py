"""
Tracking-Einheit 150 (FSL9 §8–9, Ansprüche 6, 7, 11) – ohne Qt, direkt testbar.

Eingang (152): Candidate Reports (Azimut φ, Distanz r, Zeit t, akustischer Zustand s = p_b je Band).
Bei einer Sensoreinheit kommt φ, t und s aus dem UnitReport (Id 5), r aus dem Detect-Frame
(Id 1, Pegelmodell) desselben Frames.

Speicher (154):
  Referenzzustand ŝ (156): ŝ ← (1 − α)ŝ + α·s, α = 0,2, nicht selektierte Bänder = 0
  Kinematik (158): Kalman-Filter mit konstanter Geschwindigkeit in (Ost, Nord), Zustand
                   [x, y, vx, vy]; Messung = Position aus (φ, r)

Gate (160), je Report:
  (i)  akustisch: Kosinus-Ähnlichkeit σ(s, ŝ) > θ_sim = 0,7
  (ii) räumlich-zeitlich: Mahalanobis-Distanz² der Innovation < χ²₂,₀.₉₉ = 9,21
  Übernahme (Kalman-Update, ŝ-Update) nur, wenn beide erfüllt sind; sonst verwerfen, nur Prädiktion.

Spur: vorläufig ab dem ersten Report (vorläufiger Referenzzustand aus diesem Report); bestätigt,
sobald N_INIT = 3 aufeinanderfolgende Reports beide Kriterien erfüllen (der erste zählt mit).
Ein verworfener Report während der Bestätigung beginnt eine neue vorläufige Spur. Ende nach
T_END = 2 s ohne übernommenen Report. Ausgabe (162): Trajektorie der bestätigten Spur.

Azimut: 0° = Nord, im Uhrzeigersinn (SDS_110 Azimuth.hpp); x = r·sin φ (Ost), y = r·cos φ (Nord).
"""
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

N_BANDS = 64
ALPHA = 0.2
THETA_SIM = 0.7
CHI2_2_099 = 9.21
N_INIT = 3
T_END_S = 2.0
FRAME_S = 0.032                 # Report-Takt; Vorhersage für das nächste Intervall (§10)

# Messunsicherheit und Prozessrauschen (Annahmen, einstellbar)
SIGMA_AZ_DEG = 3.0              # Peilung einer Einheit bei mittlerem SNR (SDS_110 m_bearing_drone)
SIGMA_R_REL, SIGMA_R_MIN = 0.3, 5.0   # Pegelmodell: grob
SIGMA_ACC = 3.0                 # m/s², Manöver einer kleinen Drohne
SIGMA_V0 = 15.0                 # m/s, Anfangsunsicherheit der Geschwindigkeit


@dataclass
class CandidateReport:
    time_s: float               # Zeitreferenz des Frames (UTC oder Laufzeit), s
    azimuth_deg: float
    distance_m: float
    state: np.ndarray           # s: p_b über 64 Bänder, nicht selektiert = 0
    pairs: int = 0
    residual_s: float = 0.0
    unit: int = 0


@dataclass
class TrackPoint:
    time_s: float
    x: float
    y: float
    vx: float
    vy: float

    @property
    def azimuth_deg(self) -> float:
        return float(np.degrees(np.arctan2(self.x, self.y)) % 360.0)

    @property
    def distance_m(self) -> float:
        return float(np.hypot(self.x, self.y))

    @property
    def speed_ms(self) -> float:
        return float(np.hypot(self.vx, self.vy))

    @property
    def course_deg(self) -> float:
        return float(np.degrees(np.arctan2(self.vx, self.vy)) % 360.0)


@dataclass
class Decision:
    """Ergebnis eines Reports (für Anzeige und Tests)."""
    accepted: bool
    similarity: float
    mahalanobis2: float
    status: str                 # "neu", "vorläufig", "bestätigt", "verworfen", "neu gestartet"
    reason: str = ""


@dataclass
class Track:
    x: np.ndarray               # [x, y, vx, vy]
    P: np.ndarray
    ref_state: np.ndarray       # ŝ
    t_last: float               # Zeit des letzten übernommenen Reports
    t_filter: float             # Zeit, auf die x/P prädiziert sind
    hits: int = 1
    confirmed: bool = False
    trajectory: List[TrackPoint] = field(default_factory=list)


def polar_to_xy(azimuth_deg: float, r: float):
    a = np.radians(azimuth_deg)
    return r * np.sin(a), r * np.cos(a)


def measurement_cov(azimuth_deg: float, r: float) -> np.ndarray:
    """Kovarianz der Position aus σ_φ und σ_r (Jacobi der Polarumrechnung)."""
    a = np.radians(azimuth_deg)
    s_r = max(SIGMA_R_MIN, SIGMA_R_REL * r)
    s_a = np.radians(SIGMA_AZ_DEG)
    J = np.array([[np.sin(a), r * np.cos(a)],
                  [np.cos(a), -r * np.sin(a)]])
    return J @ np.diag([s_r ** 2, s_a ** 2]) @ J.T


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class Tracker:
    H = np.array([[1.0, 0, 0, 0], [0, 1.0, 0, 0]])

    def __init__(self):
        self.track: Optional[Track] = None
        self.finished: List[List[TrackPoint]] = []     # beendete bestätigte Trajektorien

    # --------------------------------------------------------------------------------
    @staticmethod
    def _F_Q(dt: float):
        F = np.eye(4)
        F[0, 2] = F[1, 3] = dt
        q = SIGMA_ACC ** 2
        Q = q * np.array([[dt ** 4 / 4, 0, dt ** 3 / 2, 0],
                          [0, dt ** 4 / 4, 0, dt ** 3 / 2],
                          [dt ** 3 / 2, 0, dt ** 2, 0],
                          [0, dt ** 3 / 2, 0, dt ** 2]])
        return F, Q

    def _new_track(self, r: CandidateReport) -> Track:
        x, y = polar_to_xy(r.azimuth_deg, r.distance_m)
        P = np.zeros((4, 4))
        P[:2, :2] = measurement_cov(r.azimuth_deg, r.distance_m)
        P[2, 2] = P[3, 3] = SIGMA_V0 ** 2
        return Track(np.array([x, y, 0.0, 0.0]), P, np.array(r.state, dtype=float), r.time_s, r.time_s)

    def _predict(self, t: Track, time_s: float):
        dt = time_s - t.t_filter
        if dt <= 0:
            return
        F, Q = self._F_Q(dt)
        t.x = F @ t.x
        t.P = F @ t.P @ F.T + Q
        t.t_filter = time_s

    def predicted(self, dt: float = FRAME_S) -> Optional[TrackPoint]:
        """Vorhersage dt nach dem Filterzeitpunkt (für das Feedback §10)."""
        t = self.track
        if t is None:
            return None
        F, _ = self._F_Q(dt)
        x = F @ t.x
        return TrackPoint(t.t_filter + dt, *x)

    def _end(self):
        if self.track is not None and self.track.confirmed and self.track.trajectory:
            self.finished.append(self.track.trajectory)
        self.track = None

    # --------------------------------------------------------------------------------
    def expire(self, time_s: float) -> bool:
        """Spur beenden, wenn seit dem letzten übernommenen Report mehr als T_END_S vergangen sind."""
        if self.track is not None and time_s - self.track.t_last > T_END_S:
            self._end()
            return True
        return False

    def process(self, r: CandidateReport) -> Decision:
        if self.track is not None and r.time_s < self.track.t_filter - 1.0:
            self._end()                                   # Zeit sprang zurück (Neustart, Sync)
        self.expire(r.time_s)
        if self.track is None:
            self.track = self._new_track(r)
            return Decision(True, 1.0, 0.0, "neu")

        t = self.track
        self._predict(t, r.time_s)
        zx, zy = polar_to_xy(r.azimuth_deg, r.distance_m)
        innov = np.array([zx, zy]) - self.H @ t.x
        S = self.H @ t.P @ self.H.T + measurement_cov(r.azimuth_deg, r.distance_m)
        d2 = float(innov @ np.linalg.solve(S, innov))
        sim = cosine(np.asarray(r.state, float), t.ref_state)
        ok_ac, ok_kin = sim > THETA_SIM, d2 < CHI2_2_099

        if not (ok_ac and ok_kin):
            reason = ", ".join(x for x, bad in (("akustisch", not ok_ac), ("räumlich", not ok_kin)) if bad)
            if not t.confirmed:                           # Bestätigung unterbrochen: neu beginnen
                self.track = self._new_track(r)
                return Decision(False, sim, d2, "neu gestartet", reason)
            return Decision(False, sim, d2, "verworfen", reason)

        # Übernahme: Kalman-Update, ŝ-Update
        K = t.P @ self.H.T @ np.linalg.inv(S)
        t.x = t.x + K @ innov
        t.P = (np.eye(4) - K @ self.H) @ t.P
        t.ref_state = (1.0 - ALPHA) * t.ref_state + ALPHA * np.asarray(r.state, float)
        t.t_last = r.time_s
        t.hits += 1
        if not t.confirmed and t.hits >= N_INIT:
            t.confirmed = True
        if t.confirmed:
            t.trajectory.append(TrackPoint(r.time_s, *t.x))
        return Decision(True, sim, d2, "bestätigt" if t.confirmed else "vorläufig")
