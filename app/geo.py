"""
Standort der Sensoreinheit (WGS84) – ohne Qt, direkt testbar.

- Eingabe "Breite, Länge[, Höhe]" (z. B. aus Google Maps kopiert) prüfen und zerlegen
- Kommando Id 10 und Nachricht Id 6 (SDS_110 doc/ICD_SDS_PC_Monitor.md 4.5, 5.5) nutzen
  Breite/Länge in 1e-7°, Höhe in mm über NN
- lokale Koordinaten der Spur (Ost, Nord in m um die Einheit) -> Breite/Länge:
  Tangentialebene mit den Krümmungsradien des WGS84-Ellipsoids, genau auf wenige cm bis einige km
"""
import math
from dataclasses import dataclass

WGS84_A = 6378137.0
WGS84_E2 = 6.69437999014e-3
LAT_LIMIT, LON_LIMIT = 90.0, 180.0
ALT_MIN_M, ALT_MAX_M = -1000.0, 10000.0
SOURCE = {0: "keine", 1: "PC", 2: "GNSS"}


@dataclass
class GeoPosition:
    lat_deg: float
    lon_deg: float
    alt_m: float = 0.0

    def text(self) -> str:
        return f"{self.lat_deg:.7f}, {self.lon_deg:.7f}, {self.alt_m:.1f}"


def validate(p: GeoPosition) -> GeoPosition:
    if not -LAT_LIMIT <= p.lat_deg <= LAT_LIMIT:
        raise ValueError(f"Breite {p.lat_deg} außerhalb ±90°")
    if not -LON_LIMIT <= p.lon_deg <= LON_LIMIT:
        raise ValueError(f"Länge {p.lon_deg} außerhalb ±180°")
    if not ALT_MIN_M <= p.alt_m <= ALT_MAX_M:
        raise ValueError(f"Höhe {p.alt_m} m außerhalb {ALT_MIN_M:.0f} … {ALT_MAX_M:.0f} m")
    return p


def parse_position(text: str) -> GeoPosition:
    """'48.137154, 11.57549, 519.5' (Höhe optional, dann 0 m); Dezimalgrad, Nord/Ost positiv."""
    parts = [x for x in text.replace(";", ",").split(",") if x.strip()]
    if len(parts) not in (2, 3):
        raise ValueError("Format: Breite, Länge[, Höhe in m]")
    try:
        v = [float(x) for x in parts]
    except ValueError:
        raise ValueError("Zahlen mit Dezimalpunkt eingeben, z. B. 48.137154, 11.57549, 519.5") from None
    return validate(GeoPosition(v[0], v[1], v[2] if len(v) == 3 else 0.0))


def to_wire(p: GeoPosition):
    """-> (Breite 1e-7°, Länge 1e-7°, Höhe mm) als int."""
    return int(round(p.lat_deg * 1e7)), int(round(p.lon_deg * 1e7)), int(round(p.alt_m * 1000))


def enu_to_geodetic(origin: GeoPosition, east_m: float, north_m: float):
    """Punkt (Ost, Nord) in m um origin -> (Breite, Länge) in Grad."""
    phi = math.radians(origin.lat_deg)
    s = 1.0 - WGS84_E2 * math.sin(phi) ** 2
    m = WGS84_A * (1.0 - WGS84_E2) / s ** 1.5          # Meridiankrümmung
    n = WGS84_A / math.sqrt(s)                           # Querkrümmung
    lat = origin.lat_deg + math.degrees(north_m / m)
    lon = origin.lon_deg + math.degrees(east_m / (n * math.cos(phi)))
    return lat, lon
