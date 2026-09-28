"""
Read-Tab (Betriebsart READ, SDS_110 doc/ICD_SDS_PC_Monitor.md 5.3)

Jede Read-Nachricht (Id 2, 532 Byte) enthält 128 **Rohsamples** (vor der Vorverarbeitung 118)
**eines** Mikrofons (micNr 0…7) für Block blockNr 0…11 des Hops hopNr (1536 Samples, 32 ms), als
int32 mit 24 Bit (±2²³). Kopf seit 28.09.2026: [8] ts u32, [12] mic u8, [13] block u8, [14] hop u16.
Über hopNr werden fehlende Hops gezählt (USB Full Speed reicht nicht für alle 96 Nachrichten je Hop).

Aufnahme: vollständige Hops als WAV, 8 Kanäle, 24 Bit, 48 kHz – direkt für SDS_110
tools/features/sds_features. Fehlende oder unvollständige Hops werden als Stille geschrieben
(höchstens MAX_FILL_HOPS am Stück), damit die Zeitachse stimmt, und gezählt.
Im Modus READ kommen ~3000 Nachrichten/s: update_frame() legt die Samples nur in den Hop-Puffer
(billig); gezeichnet wird mit höchstens REFRESH_HZ und nur, wenn der Tab sichtbar ist.

Anzeige: Pegel je Mikrofon (RMS, dBFS), Wellenform und Spektrum des letzten Hops (Hann-Fenster,
1536 Punkte, 31,25 Hz je Bin; normiert so, dass ein Sinus mit Amplitude A als 20·log10(A) dBFS
erscheint). Markiert ist der Bereich der Analysebänder 80 Hz … 4 kHz (FSL9 §2).
"""
import struct
import time
import wave

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

N_MICS = 8
BLOCK = 128
BLOCKS_PER_HOP = 12
HOP = BLOCK * BLOCKS_PER_HOP                  # 1536
FULL_SCALE = float(1 << 23)
FRAME_LEN = 532
SAMPLE_RATE = 48000
BAND_LO_HZ, BAND_HI_HZ = 80.0, 4000.0
SPEC_MAX_HZ = 24000.0                         # Rohdaten: bis zur Nyquist-Frequenz
MAX_FILL_HOPS = 31                            # Aufnahme: längste Lücke, die mit Stille gefüllt wird (≈ 1 s)
WINDOW = np.hanning(HOP)
FREQS = np.fft.rfftfreq(HOP, 1.0 / SAMPLE_RATE)


class TabRead(QWidget):
    REFRESH_HZ = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = np.zeros((N_MICS, HOP), dtype=np.int32)
        self.filled = np.zeros((N_MICS, BLOCKS_PER_HOP), dtype=bool)
        self.last_ts = None
        self.hop = None                           # Hop-Nummer im Puffer
        self.missing_hops = 0                     # über hopNr erkannte Lücken
        self.frames = 0
        self.bad = 0
        self._wav = None                          # laufende Aufnahme
        self.rec_path = None
        self.rec_hops = self.rec_filled = 0
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
        self.rec_btn = QPushButton("Aufnahme …")
        self.rec_btn.setToolTip("Rohdaten als WAV (8 Kanäle, 24 Bit, 48 kHz) für sds_features")
        self.rec_btn.clicked.connect(self.toggle_recording)
        top.addWidget(self.rec_btn)
        top.addWidget(QLabel("Wellenform/Spektrum:"))
        top.addWidget(self.mic_combo)
        # Rohdaten ohne AGC (Firmware seit 28.09.2026) sind klein, z. B. −40 dBFS: Skala automatisch
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["Skala automatisch", "Skala ±1 (Vollaussteuerung)"])
        self.scale_combo.currentIndexChanged.connect(lambda _: self._mark())
        top.addWidget(self.scale_combo)
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
        self.wave_plot.getPlotItem().setTitle("Wellenform (1536 Samples = 32 ms)")
        self.t_ms = np.arange(HOP) / 48.0
        self.curves = [self.wave_plot.plot(pen=pg.intColor(m, N_MICS)) for m in range(N_MICS)]
        lay.addWidget(self.wave_plot, 2)

        # Spektrum des Hops
        self.spec_plot = pg.PlotWidget()
        ps = self.spec_plot.getPlotItem()
        ps.setTitle("Spektrum der Rohdaten (Hann, 31,25 Hz je Bin); markiert: Analysebänder 80 Hz – 4 kHz")
        ps.setLabel("left", "dBFS")
        ps.setLabel("bottom", "Frequenz", units="Hz")
        self.spec_plot.setXRange(0, SPEC_MAX_HZ)
        self.spec_plot.setYRange(-140, 0)
        ps.showGrid(x=True, y=True, alpha=0.3)
        band = pg.LinearRegionItem(values=(BAND_LO_HZ, BAND_HI_HZ), movable=False,
                                   brush=pg.mkBrush(80, 160, 255, 40))
        self.spec_plot.addItem(band)
        self.spec_curves = [self.spec_plot.plot(pen=pg.intColor(m, N_MICS)) for m in range(N_MICS)]
        lay.addWidget(self.spec_plot, 2)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000 // self.REFRESH_HZ)

    # ------------------------------------------------------------
    def update_frame(self, frame: bytes) -> bool:
        """Read-Nachricht in den Hop-Puffer übernehmen; False bei ungültigem Inhalt."""
        if len(frame) != FRAME_LEN:
            self.bad += 1
            return False
        ts, mic, block, hop = struct.unpack_from("<IBBH", frame, 8)
        if mic >= N_MICS or block >= BLOCKS_PER_HOP:
            self.bad += 1
            return False
        if hop != self.hop:                       # neuer Hop
            self._finish_hop(hop)
            self.hop, self.last_ts = hop, ts
            self.filled[:] = False
        self.samples[mic, block * BLOCK:(block + 1) * BLOCK] = np.frombuffer(frame, dtype="<i4", count=BLOCK, offset=16)
        self.filled[mic, block] = True
        self.frames += 1
        self._rate_n += 1
        self._dirty = True
        return True

    def _finish_hop(self, next_hop: int):
        """Hop im Puffer abschließen: Lücke bis next_hop zählen, bei Aufnahme schreiben."""
        if self.hop is None:
            return
        gap = ((next_hop - self.hop) & 0xFFFF) - 1
        if 0 < gap < 0x8000:                      # rückwärts (Neustart des Boards) zählt nicht
            self.missing_hops += gap
        if self._wav is not None:
            complete = bool(self.filled.all())
            self._write_hop(self.samples if complete else None)
            for _ in range(min(max(gap, 0), MAX_FILL_HOPS) if gap < 0x8000 else 0):
                self._write_hop(None)

    def _write_hop(self, samples):
        if samples is None:
            self.rec_filled += 1
            samples = np.zeros((N_MICS, HOP), dtype=np.int32)
        pcm = np.ascontiguousarray(samples.T).astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3]
        self._wav.writeframes(pcm.tobytes())
        self.rec_hops += 1

    def start_recording(self, path: str):
        w = wave.open(path, "wb")
        w.setnchannels(N_MICS)
        w.setsampwidth(3)
        w.setframerate(SAMPLE_RATE)
        self._wav, self.rec_path = w, path
        self.rec_hops = self.rec_filled = 0
        self.rec_btn.setText("Aufnahme stoppen")
        self._dirty = True

    def stop_recording(self):
        """Aufnahme beenden (der laufende Hop wird mitgeschrieben); Rückgabe: (Hops, davon Stille)."""
        if self._wav is None:
            return 0, 0
        if self.hop is not None:
            self._write_hop(self.samples if self.filled.all() else None)
            self.hop = None                       # nicht ein zweites Mal schreiben
        self._wav.close()
        self._wav = None
        self.rec_btn.setText("Aufnahme …")
        self._dirty = True
        return self.rec_hops, self.rec_filled

    @property
    def recording(self) -> bool:
        return self._wav is not None

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
            return
        path, _ = QFileDialog.getSaveFileName(self, "Rohdaten aufnehmen", "sds_read.wav", "WAV (*.wav)")
        if path:
            self.start_recording(path)

    def _mark(self):
        self._dirty = True

    def levels_dbfs(self) -> np.ndarray:
        x = self.samples.astype(np.float64) / FULL_SCALE
        rms = np.sqrt(np.mean(x * x, axis=1))
        return 20.0 * np.log10(np.maximum(rms, 1e-6))

    def spectrum_dbfs(self) -> np.ndarray:
        """Betrag je Mikrofon und Bin in dBFS (Sinus mit Amplitude A -> 20·log10(A))."""
        x = self.samples.astype(np.float64) / FULL_SCALE
        mag = np.abs(np.fft.rfft(x * WINDOW, axis=1)) * (2.0 / WINDOW.sum())
        return 20.0 * np.log10(np.maximum(mag, 1e-7))

    def peak(self, mic: int):
        """(Frequenz in Hz, Pegel in dBFS) des stärksten Bins ab BAND_LO_HZ."""
        s = self.spectrum_dbfs()[mic]
        lo = int(np.searchsorted(FREQS, BAND_LO_HZ))
        k = lo + int(np.argmax(s[lo:]))
        return float(FREQS[k]), float(s[k])

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
        spec = self.spectrum_dbfs()
        show = FREQS <= SPEC_MAX_HZ
        shown = range(N_MICS) if sel == N_MICS else [sel]
        peak = max(float(np.max(np.abs(self.samples[m]))) for m in shown) / FULL_SCALE
        peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
        if self.scale_combo.currentIndex() == 0:
            y = max(peak * 1.1, 1e-6)
            self.wave_plot.setYRange(-y, y, padding=0)
        else:
            self.wave_plot.setYRange(-1, 1, padding=0)
        self.wave_plot.getPlotItem().setTitle(
            f"Wellenform (1536 Samples = 32 ms), Rohdaten, Spitze {peak_db:.1f} dBFS")
        for m, (c, sc) in enumerate(zip(self.curves, self.spec_curves)):
            if sel == N_MICS or sel == m:
                c.setData(self.t_ms, self.samples[m] / FULL_SCALE)
                sc.setData(FREQS[show], spec[m][show])
            else:
                c.setData([], [])
                sc.setData([], [])
        complete = int(self.filled.sum())
        rec = ""
        if self.recording:
            rec = f"   ● Aufnahme {self.rec_hops * HOP / SAMPLE_RATE:.1f} s (Stille {self.rec_filled} Hops)"
        self.info_label.setText(
            f"Hop {self.hop} (t = {self.last_ts} ms)   Blöcke {complete}/{N_MICS * BLOCKS_PER_HOP}   "
            f"fehlende Hops {self.missing_hops}   {self.rate:.0f} Nachrichten/s   empfangen {self.frames}   "
            f"ungültig {self.bad}{rec}")
