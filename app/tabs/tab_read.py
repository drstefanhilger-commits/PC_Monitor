"""
Read-Tab (Betriebsart READ, SDS_110 doc/ICD_SDS_PC_Monitor.md 5.3)

Jede Read-Nachricht (Id 2, 532 Byte) enthält 128 Samples **eines** Mikrofons (micNr 0…7) für
Block frameNr 0…11 eines Hops (1536 Samples, 32 ms), als int32 skaliert auf 24 Bit (±2²³).
Im Modus READ kommen ~3000 Nachrichten/s: update_frame() legt die Samples nur in den Hop-Puffer
(billig); gezeichnet wird mit höchstens REFRESH_HZ und nur, wenn der Tab sichtbar ist.
"""
import struct
import time

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

N_MICS = 8
BLOCK = 128
BLOCKS_PER_HOP = 12
HOP = BLOCK * BLOCKS_PER_HOP                  # 1536
FULL_SCALE = float(1 << 23)
FRAME_LEN = 532


class TabRead(QWidget):
    REFRESH_HZ = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = np.zeros((N_MICS, HOP), dtype=np.int32)
        self.filled = np.zeros((N_MICS, BLOCKS_PER_HOP), dtype=bool)
        self.last_ts = None
        self.frames = 0
        self.bad = 0
        self._rate_t0, self._rate_n, self.rate = time.monotonic(), 0, 0.0
        self._dirty = False

        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.info_label = QLabel("READ: keine Daten")
        self.mic_combo = QComboBox()
        self.mic_combo.addItems([f"Mikrofon {m}" for m in range(N_MICS)] + ["alle"])
        self.mic_combo.setCurrentIndex(N_MICS)
        self.mic_combo.currentIndexChanged.connect(lambda _: self._mark())
        top.addWidget(self.info_label, 1)
        top.addWidget(QLabel("Wellenform:"))
        top.addWidget(self.mic_combo)
        lay.addLayout(top)

        # Pegel je Mikrofon (RMS in dBFS)
        self.level_plot = pg.PlotWidget()
        pi = self.level_plot.getPlotItem()
        pi.setTitle("Pegel je Mikrofon (RMS, letzter Hop)")
        pi.setLabel("left", "dBFS")
        pi.setLabel("bottom", "Mikrofon")
        self.level_plot.setYRange(-120, 0)
        self.level_plot.setXRange(-0.5, N_MICS - 0.5)
        self.level_bars = pg.BarGraphItem(x=np.arange(N_MICS), y0=-120, height=np.zeros(N_MICS), width=0.7, brush="g")
        self.level_plot.addItem(self.level_bars)
        lay.addWidget(self.level_plot, 1)

        # Wellenform des Hops
        self.wave_plot = pg.PlotWidget()
        pw = self.wave_plot.getPlotItem()
        pw.setTitle("Wellenform (1536 Samples = 32 ms)")
        pw.setLabel("left", "Amplitude (Vollaussteuerung = 1)")
        pw.setLabel("bottom", "Zeit", units="ms")
        self.wave_plot.setYRange(-1, 1)
        self.t_ms = np.arange(HOP) / 48.0
        self.curves = [self.wave_plot.plot(pen=pg.intColor(m, N_MICS)) for m in range(N_MICS)]
        lay.addWidget(self.wave_plot, 2)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000 // self.REFRESH_HZ)

    # ------------------------------------------------------------
    def update_frame(self, frame: bytes) -> bool:
        """Read-Nachricht in den Hop-Puffer übernehmen; False bei ungültigem Inhalt."""
        if len(frame) != FRAME_LEN:
            self.bad += 1
            return False
        ts, mic, block = struct.unpack_from("<IHH", frame, 8)
        if mic >= N_MICS or block >= BLOCKS_PER_HOP:
            self.bad += 1
            return False
        if ts != self.last_ts:                    # neuer Hop
            self.last_ts = ts
            self.filled[:] = False
        self.samples[mic, block * BLOCK:(block + 1) * BLOCK] = np.frombuffer(frame, dtype="<i4", count=BLOCK, offset=16)
        self.filled[mic, block] = True
        self.frames += 1
        self._rate_n += 1
        self._dirty = True
        return True

    def _mark(self):
        self._dirty = True

    def levels_dbfs(self) -> np.ndarray:
        x = self.samples.astype(np.float64) / FULL_SCALE
        rms = np.sqrt(np.mean(x * x, axis=1))
        return 20.0 * np.log10(np.maximum(rms, 1e-6))

    def refresh(self):
        now = time.monotonic()
        if now - self._rate_t0 >= 1.0:
            self.rate = self._rate_n / (now - self._rate_t0)
            self._rate_t0, self._rate_n = now, 0
        if not self._dirty or not self.isVisible():
            return
        self._dirty = False
        lv = self.levels_dbfs()
        self.level_bars.setOpts(height=lv + 120.0)
        sel = self.mic_combo.currentIndex()
        for m, c in enumerate(self.curves):
            if sel == N_MICS or sel == m:
                c.setData(self.t_ms, self.samples[m] / FULL_SCALE)
            else:
                c.setData([], [])
        complete = int(self.filled.sum())
        self.info_label.setText(
            f"Hop t = {self.last_ts} ms   Blöcke {complete}/{N_MICS * BLOCKS_PER_HOP}   "
            f"{self.rate:.0f} Nachrichten/s   empfangen {self.frames}   ungültig {self.bad}")
