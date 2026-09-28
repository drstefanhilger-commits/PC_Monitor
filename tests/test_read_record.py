"""Read-Tab (Befund 35 SDS_110): neues Kopfformat, fehlende Hops über hopNr, Aufnahme als WAV."""
import wave

import numpy as np

from app.tabs.tab_read import BLOCK, HOP, TabRead
from tests import sds_frames as F


def hop_frames(hop, value_of, blocks=range(12), mics=range(8)):
    out = []
    for m in mics:
        x = np.full(HOP, 0, dtype=np.int32) + np.arange(HOP, dtype=np.int32) + value_of(m)
        for b in blocks:
            out.append(F.read_block(mic=m, block=b, samples=x[b * BLOCK:(b + 1) * BLOCK].tolist(), ts=32 * hop, hop=hop))
    return out


def feed(tab, frames):
    for fr in frames:
        assert tab.update_frame(fr)


def test_header_and_missing_hops(qapp):
    tab = TabRead()
    feed(tab, hop_frames(10, lambda m: 1000 * m))
    assert tab.hop == 10 and tab.filled.all() and tab.missing_hops == 0
    assert tab.samples[3, 5] == 3005                                 # Mikrofon 3, Sample 5
    feed(tab, hop_frames(11, lambda m: 0))
    feed(tab, hop_frames(15, lambda m: 0))                           # 12, 13, 14 fehlen
    assert tab.missing_hops == 3
    feed(tab, hop_frames(0xFFFF, lambda m: 0)); feed(tab, hop_frames(1, lambda m: 0))
    assert tab.missing_hops == 3 + 1                                 # Überlauf 65535 -> 1: Hop 0 fehlt
    feed(tab, hop_frames(0, lambda m: 0))                            # rückwärts (Board-Neustart): keine Lücke
    assert tab.missing_hops == 4
    bad = F.read_block(mic=9, block=0)
    assert not tab.update_frame(bad) and tab.bad == 1


def test_recording_wav(qapp, tmp_path):
    tab = TabRead()
    path = str(tmp_path / "rec.wav")
    tab.start_recording(path)
    assert tab.recording
    feed(tab, hop_frames(100, lambda m: 10000 * m))                  # vollständig
    feed(tab, hop_frames(101, lambda m: 7, blocks=range(6)))         # unvollständig -> Stille
    feed(tab, hop_frames(104, lambda m: -5000 * m))                  # 102, 103 fehlen -> Stille
    hops, silent = tab.stop_recording()
    assert (hops, silent) == (5, 3) and not tab.recording
    with wave.open(path, "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (8, 3, 48000, 5 * HOP)
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.uint8).reshape(-1, 8, 3)
    v = (raw[..., 0].astype(np.int32) | (raw[..., 1].astype(np.int32) << 8) | (raw[..., 2].astype(np.int32) << 16))
    v = np.where(v >= 1 << 23, v - (1 << 24), v)                     # 24 Bit mit Vorzeichen
    assert v[5, 2] == 20005 and v[HOP - 1, 7] == 70000 + HOP - 1     # Hop 100: Mikrofon 2 / 7
    assert not v[HOP:4 * HOP].any()                                  # Hop 101 unvollständig, 102, 103 fehlen
    assert v[4 * HOP + 3, 1] == -5000 + 3 and v[4 * HOP + 3, 4] == -20000 + 3   # Hop 104, negative Werte
