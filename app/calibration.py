"""
Nordabgleich einer Sensoreinheit (SDS_110 doc/ICD_SDS_PC_Monitor.md 4.4, USB-Kommando Id 9) –
ohne Qt, direkt testbar.

Ablauf:
  1. Referenzquelle mit bekanntem Azimut φ_ref betreiben (Lautsprecher, schwebende Drohne).
  2. Peilungen φ_i der UnitReports (Id 5) für einige Sekunden sammeln; zirkulares Mittel
     φ̄ = atan2(Σ sin φ_i, Σ cos φ_i), Streuung σ = √(−2 ln R) mit R = |Σ e^{iφ_i}| / N.
  3. Neuer Offset o_neu = wrap180(o_alt + φ_ref − φ̄); die Peilungen enthalten schon o_alt.
  4. o_neu mit Id 9 senden (i32 BE in 0,01°, −180,00 … +180,00°).

Azimut: 0° = Nord, im Uhrzeigersinn (SDS_110 Azimuth.hpp).
"""
import math
from dataclasses import dataclass
from typing import List, Optional

OFFSET_LIMIT_DEG = 180.0
MIN_BEARINGS = 10                  # weniger Peilungen: Ergebnis nur mit Warnung übernehmen
MAX_SPREAD_DEG = 5.0               # größere Streuung: Quelle zu schwach oder Mehrwege


def wrap180(deg: float) -> float:
    """Winkel auf (−180°, +180°]."""
    d = math.fmod(deg, 360.0)
    if d <= -180.0:
        d += 360.0
    elif d > 180.0:
        d -= 360.0
    return d


def offset_to_centi(deg: float) -> int:
    """Offset in Grad -> i32 in 0,01° für Id 9; ValueError außerhalb ±180°."""
    c = int(round(deg * 100.0))
    if abs(c) > int(OFFSET_LIMIT_DEG * 100):
        raise ValueError(f"Offset {deg:.2f}° außerhalb ±{OFFSET_LIMIT_DEG:.0f}°")
    return c


@dataclass
class CircularStats:
    n: int
    mean_deg: float                # 0 … < 360
    spread_deg: float              # zirkulare Standardabweichung
    resultant: float               # R, 0 … 1


def circular_stats(bearings_deg) -> Optional[CircularStats]:
    b = list(bearings_deg)
    if not b:
        return None
    s = sum(math.sin(math.radians(x)) for x in b)
    c = sum(math.cos(math.radians(x)) for x in b)
    r = math.hypot(s, c) / len(b)
    mean = math.degrees(math.atan2(s, c)) % 360.0
    spread = math.degrees(math.sqrt(-2.0 * math.log(r))) if r > 1e-12 else 180.0
    return CircularStats(len(b), mean, spread, r)


def new_offset(old_offset_deg: float, reference_deg: float, measured_deg: float) -> float:
    return wrap180(old_offset_deg + wrap180(reference_deg - measured_deg))


@dataclass
class CalibrationResult:
    stats: CircularStats
    reference_deg: float
    old_offset_deg: float
    offset_deg: float              # vorgeschlagener neuer Offset

    @property
    def error_deg(self) -> float:
        """φ_ref − φ̄ auf ±180°."""
        return wrap180(self.reference_deg - self.stats.mean_deg)

    def warnings(self) -> List[str]:
        w = []
        if self.stats.n < MIN_BEARINGS:
            w.append(f"nur {self.stats.n} Peilungen (mindestens {MIN_BEARINGS})")
        if self.stats.spread_deg > MAX_SPREAD_DEG:
            w.append(f"Streuung {self.stats.spread_deg:.1f}° > {MAX_SPREAD_DEG:.0f}°")
        return w


class NorthCalibration:
    """Sammelt Peilungen für duration_s ab start(); Zeiten in Sekunden (time.monotonic())."""

    def __init__(self):
        self.bearings: List[float] = []
        self.t_start: Optional[float] = None
        self.duration_s = 5.0
        self.reference_deg = 0.0
        self.old_offset_deg = 0.0

    @property
    def running(self) -> bool:
        return self.t_start is not None

    def start(self, reference_deg: float, old_offset_deg: float, duration_s: float, now: float):
        self.bearings = []
        self.reference_deg = reference_deg % 360.0
        self.old_offset_deg = old_offset_deg
        self.duration_s = duration_s
        self.t_start = now

    def cancel(self):
        self.t_start = None

    def progress(self, now: float) -> float:
        if self.t_start is None:
            return 0.0
        return min(1.0, (now - self.t_start) / self.duration_s)

    def add(self, bearing_deg: float, now: float) -> bool:
        """Peilung aufnehmen, solange die Messung läuft."""
        if self.t_start is None or now - self.t_start > self.duration_s:
            return False
        self.bearings.append(bearing_deg % 360.0)
        return True

    def finish_if_due(self, now: float) -> bool:
        """Nach Ablauf der Messdauer die Messung beenden (True); Ergebnis dann mit result()."""
        if self.t_start is None or now - self.t_start < self.duration_s:
            return False
        self.t_start = None
        return True

    def result(self) -> Optional[CalibrationResult]:
        """None ohne Peilungen."""
        st = circular_stats(self.bearings)
        if st is None:
            return None
        return CalibrationResult(st, self.reference_deg, self.old_offset_deg,
                                 new_offset(self.old_offset_deg, self.reference_deg, st.mean_deg))
