"""
Standort der Sensoreinheit in lokalen Koordinaten – ohne Qt, direkt testbar.

x = Ost, y = Nord, z = Oben, in m relativ zum lokalen Ursprung [0, 0, 0] (Achsen wie der Lageplan
und der Azimut: 0° = Nord, 90° = Ost). Nach dem Start steht das Board im Ursprung.
- Eingabe "Ost, Nord[, Oben]" in m prüfen und zerlegen
- Kommando Id 10 und Nachricht Id 6 (SDS_110 doc/ICD_SDS_PC_Monitor.md 4.5, 5.5): Werte in mm
Bis 29.09.2026 WGS84 (Breite, Länge, Höhe) mit GNSS-Vorrang.
"""
from dataclasses import dataclass

HORIZ_LIMIT_M = 100_000.0                 # ±100 km Ost/Nord
UP_MIN_M, UP_MAX_M = -1000.0, 10000.0


@dataclass
class LocalPosition:
    east_m: float = 0.0
    north_m: float = 0.0
    up_m: float = 0.0

    def text(self) -> str:
        return f"{self.east_m:.3f}, {self.north_m:.3f}, {self.up_m:.3f}"


ORIGIN = LocalPosition()


def validate(p: LocalPosition) -> LocalPosition:
    for name, v in (("Ost", p.east_m), ("Nord", p.north_m)):
        if not -HORIZ_LIMIT_M <= v <= HORIZ_LIMIT_M:
            raise ValueError(f"{name} {v} m außerhalb ±100 km")
    if not UP_MIN_M <= p.up_m <= UP_MAX_M:
        raise ValueError(f"Oben {p.up_m} m außerhalb {UP_MIN_M:.0f} … {UP_MAX_M:.0f} m")
    return p


def parse_position(text: str) -> LocalPosition:
    """'120, -45.5, 3' in m (Oben optional, dann 0 m); Ost/Nord positiv."""
    parts = [x for x in text.replace(";", ",").split(",") if x.strip()]
    if len(parts) not in (2, 3):
        raise ValueError("Format: Ost, Nord[, Oben] in m")
    try:
        v = [float(x) for x in parts]
    except ValueError:
        raise ValueError("Zahlen mit Dezimalpunkt eingeben, z. B. 120, -45.5, 3") from None
    return validate(LocalPosition(v[0], v[1], v[2] if len(v) == 3 else 0.0))


def to_wire(p: LocalPosition):
    """-> (Ost, Nord, Oben) in mm als int."""
    return int(round(p.east_m * 1000)), int(round(p.north_m * 1000)), int(round(p.up_m * 1000))


def same(a: LocalPosition, b: LocalPosition, tol_m: float = 0.002) -> bool:
    return abs(a.east_m - b.east_m) < tol_m and abs(a.north_m - b.north_m) < tol_m and abs(a.up_m - b.up_m) < tol_m
