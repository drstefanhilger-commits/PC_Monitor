"""
Feedback der Tracking-Einheit an das Board (FSL9 §10, Anspruch 8), Kommando Id 8, 52 Byte
(SDS_110 doc/ICD_SDS_PC_Monitor.md 4.3, Firmware Infrastructure/Utils/FeedbackCodec.hpp):
  [0..7]   DE AD BE EF 08 00 00 34
  [8..39]  ŝ: 64 Bänder × 4 Bit (q = round(ŝ·15)), Band 2i oben, 2i+1 unten
  [40..41] vorhergesagter Azimut u16 BE in 0,01° (0° = Nord, im Uhrzeigersinn)
  [42..43] vorhergesagte Distanz u16 BE in 0,1 m
  [44]     Flags: Bit 0 = ŝ gültig (0 = Feedback zurücksetzen), Bit 1 = Position gültig
  [45..47] reserviert
  [48..51] CRC32 BE über Byte 0–47
"""
import zlib

import numpy as np

FLAG_STATE, FLAG_POSITION = 0x01, 0x02
HEADER = bytes.fromhex("DEADBEEF08000034")


def build_feedback(ref_state=None, azimuth_deg=None, distance_m=None) -> bytes:
    """ref_state None -> Zurücksetzen; azimuth/distance None -> keine Positionsvorhersage."""
    flags = 0
    nib = bytearray(32)
    if ref_state is not None:
        q = np.clip(np.rint(np.asarray(ref_state, float) * 15.0), 0, 15).astype(int)
        if q.size != 64:
            raise ValueError("ŝ muss 64 Bänder haben")
        for i in range(32):
            nib[i] = (q[2 * i] << 4) | q[2 * i + 1]
        flags |= FLAG_STATE
    az = r = 0
    if azimuth_deg is not None and distance_m is not None:
        az = int(round((azimuth_deg % 360.0) * 100)) % 36000
        r = min(int(round(max(distance_m, 0.0) * 10)), 0xFFFF)
        flags |= FLAG_POSITION
    body = HEADER + bytes(nib) + az.to_bytes(2, "big") + r.to_bytes(2, "big") + bytes([flags, 0, 0, 0])
    return body + (zlib.crc32(body) & 0xFFFFFFFF).to_bytes(4, "big")
