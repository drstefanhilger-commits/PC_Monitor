"""
Nachrichten SDS -> PC dekodieren (SDS_110 doc/ICD_SDS_PC_Monitor.md, Abschnitt 5).
Alle Felder little-endian; die Nutzlast von UnitReport und Logger beginnt bei Byte 12.
"""
import datetime
import struct
from dataclasses import dataclass, field
from typing import List

N_BANDS = 64
BAND_LO_HZ, BAND_WIDTH_HZ = 80.0, 62.5
UTC_MIN_US = 1577836800 * 1_000_000            # 01.01.2020, wie UtcClock der Firmware

TIME_SOURCE = {0: "Laufzeit", 1: "UTC (PC)", 2: "GNSS-PPS"}


@dataclass
class Detect:
    timestamp_ms: int
    unit: int
    azimuth_deg: float
    distance_m: float
    confidence: float


@dataclass
class UnitReport:
    timestamp_ms: int
    unit: int
    time_us: int
    source: int
    bearing_deg: float
    residual_s: float
    pairs: int
    level: float
    bands: List[int] = field(default_factory=list)
    probs: List[float] = field(default_factory=list)    # 0 … 1 (p_b · 255 / 255)

    @property
    def source_name(self) -> str:
        return TIME_SOURCE.get(self.source, f"? ({self.source})")

    def time_text(self) -> str:
        """UTC als Datum/Uhrzeit mit µs, sonst Laufzeit in s."""
        if self.source != 0 and self.time_us >= UTC_MIN_US:
            t = datetime.datetime.fromtimestamp(self.time_us / 1e6, tz=datetime.timezone.utc)
            return t.strftime("%Y-%m-%d %H:%M:%S.") + f"{self.time_us % 1_000_000:06d} UTC"
        return f"{self.time_us / 1e6:.6f} s seit Start"

    def state_vector(self) -> List[float]:
        """p_b über alle 64 Bänder, nicht selektierte Bänder = 0 (FSL9 §8)."""
        v = [0.0] * N_BANDS
        for b, p in zip(self.bands, self.probs):
            if 0 <= b < N_BANDS:
                v[b] = p
        return v


def parse_detect(frame: bytes) -> Detect:
    ts, unit, azi, dist, conf = struct.unpack_from("<IIfff", frame, 8)
    return Detect(ts, unit, azi, dist, conf)


UNIT_REPORT_HEAD = 25
UNIT_REPORT_MAX_BANDS = (128 - UNIT_REPORT_HEAD) // 2      # 51


def parse_unit_report(frame: bytes) -> UnitReport:
    if len(frame) != 144:
        raise ValueError(f"UnitReport: Länge {len(frame)} statt 144")
    ts, = struct.unpack_from("<I", frame, 8)
    d = frame[12:140]
    unit, time_us, src = struct.unpack_from("<HQB", d, 0)
    bearing, residual = struct.unpack_from("<ff", d, 11)
    pairs, nsel = d[19], d[20]
    level, = struct.unpack_from("<f", d, 21)
    if nsel > UNIT_REPORT_MAX_BANDS:
        raise ValueError(f"UnitReport: nsel {nsel} > {UNIT_REPORT_MAX_BANDS}")
    h = UNIT_REPORT_HEAD
    bands = list(d[h:h + nsel])
    probs = [v / 255.0 for v in d[h + nsel:h + 2 * nsel]]
    return UnitReport(ts, unit, time_us, src, bearing, residual, pairs, level, bands, probs)


@dataclass
class BoardPosition:
    """Nachricht Id 6 (ICD 5.5): lokale Position, die das Board verwendet (Ost, Nord, Oben in m)."""
    unit: int
    set: bool                   # vom PC gesetzt (False: Grundwert Ursprung)
    east_m: float
    north_m: float
    up_m: float

    def local(self):
        from app.local_position import LocalPosition
        return LocalPosition(self.east_m, self.north_m, self.up_m)

    def text(self) -> str:
        t = f"O {self.east_m:.2f} N {self.north_m:.2f} H {self.up_m:.2f} m"
        return t if self.set else t + " (Ursprung)"


def parse_position(frame: bytes) -> BoardPosition:
    if len(frame) != 144:
        raise ValueError(f"Standort: Länge {len(frame)} statt 144")
    unit, _reserved, flags, east, north, up = struct.unpack_from("<HBBiii", frame, 12)
    return BoardPosition(unit, bool(flags & 1), east / 1000.0, north / 1000.0, up / 1000.0)


def parse_logger(frame: bytes) -> str:
    """Nutzlast (128 Byte ASCII, mit Nullbytes aufgefüllt) als Text."""
    return frame[12:140].split(b"\0", 1)[0].decode("ascii", errors="replace")


class LineAssembler:
    """Logger-Pakete können Zeilen teilen: Text sammeln, vollständige Zeilen liefern."""

    def __init__(self, max_len: int = 1000):
        self.pending = ""
        self.max_len = max_len

    def push(self, text: str) -> List[str]:
        self.pending += text
        *lines, self.pending = self.pending.split("\n")
        if len(self.pending) > self.max_len:
            lines.append(self.pending)
            self.pending = ""
        return [l.rstrip("\r") for l in lines if l.strip()]
