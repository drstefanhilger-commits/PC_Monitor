import csv
import time
from collections import OrderedDict

import numpy as np
import serial
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QMainWindow, QSplitter, QTabWidget, QWidget

from app.model.SDSUSBModel import SDSMode, SDSUSBModel
from app.tabs.tab_calibrate import TabCalibrate
from app.tabs.tab_detect import TabDetect
from app.tabs.tab_read import TabRead
from app.tracking.tracker import CandidateReport, Tracker, T_END_S
from app.usb.messages import LineAssembler, parse_detect, parse_logger, parse_unit_report
from app.usb.usb_reader import USBReader
from app.usb.usb_writer import USBWriter
from app.widgets.control_panel import ControlPanel
from app.widgets.status_panel import StatusPanel


class MainWindow(QMainWindow):
    """
    Aufbau:
      ┌──────────┬───────────────────────────────┐
      │ Bedien-  │ [Detect|Read|Calibrate]       │  Tabs links oben; sichtbar ist nur der
      │ feld     │                               │  Tab, den der Drehschalter wählt
      │ (links)  │                               │
      ├──────────┴───────────────────────────────┤
      │ Status / Fehler                          │  unten, Höhe per Splitter
      └──────────────────────────────────────────┘
    Hält das SDSUSBModel, öffnet/schließt die USB-Verbindung (Schalter On/Off) und pollt
    die Queues des Readers mit 50 Hz.
    """

    SERIAL_BAUD = 115200          # USB-CDC: Baudrate ohne Bedeutung
    STATS_EVERY = 10              # Zählerzeile alle 10 Polls (200 ms)
    SYNC_PERIOD_MS = 60_000       # Sync (UTC + Temperatur) jede Minute, ICD 4.2
    POLL_BUDGET_S = 0.015         # je Poll höchstens 15 ms arbeiten, dann zurück in die Ereignisschleife

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SDS USB Monitor Version 1.10")

        self.model = SDSUSBModel()
        self.ser = None
        self.reader = None
        self.writer = None
        self._poll_count = 0
        self._log_lines = LineAssembler()
        # Tracking-Einheit (Komponente B, FSL9 §8–10)
        self.tracker = Tracker()
        self._detects = OrderedDict()          # timestamp_ms -> Detect (Distanz für den Candidate Report)
        self._last_accept_host = None          # time.monotonic() der letzten Übernahme

        # --- Bedienfeld links ------------------------------------------
        self.controls = ControlPanel()
        self.controls.power_toggled.connect(self.on_power)
        self.controls.simulation_toggled.connect(self.on_simulation)
        self.controls.mode_changed.connect(self.on_mode)
        self.controls.unit_id_set.connect(self.on_unit_id)
        self.controls.srp_toggled.connect(self.on_srp)
        self.controls.sync_requested.connect(self.send_sync)
        self.controls.feedback_toggled.connect(self.on_feedback_toggled)
        self.controls.export_requested.connect(self.on_export)

        # --- Tabs, je Betriebsart einer -------------------------------------
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::tab-bar { alignment: left; }")
        self.detect_tab = TabDetect()
        self.read_tab = TabRead()
        self.calibrate_tab = TabCalibrate()
        self.tab_index = {
            SDSMode.DETECT: self.tabs.addTab(self.detect_tab, "Detect"),
            SDSMode.READ: self.tabs.addTab(self.read_tab, "Read"),
            SDSMode.CALIBRATE: self.tabs.addTab(self.calibrate_tab, "Calibrate"),
        }

        # --- Status/Fehler unten ------------------------------------------
        self.status = StatusPanel(self.model)

        top = QWidget()
        h = QHBoxLayout(top)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(self.controls)
        h.addWidget(self.tabs, 1)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(top)
        split.addWidget(self.status)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)
        split.setSizes([560, 180])
        self.setCentralWidget(split)

        self.show_mode_tab(self.controls.mode())
        self.status.log("Bereit. Port wählen und Schalter auf On.")

        self.timer = QTimer()
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(20)   # 50 Hz

        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.send_sync)

    # ------------------------------------------------------------
    # Tabs: nur der Tab der gewählten Betriebsart ist sichtbar
    # ------------------------------------------------------------
    def show_mode_tab(self, mode: SDSMode):
        for m, i in self.tab_index.items():
            self.tabs.setTabVisible(i, m == mode)
        self.tabs.setCurrentIndex(self.tab_index[mode])

    # ------------------------------------------------------------
    # Schalter
    # ------------------------------------------------------------
    def on_power(self, on: bool):
        if on:
            self.connect_usb()
        else:
            self.disconnect_usb()

    def on_simulation(self, on: bool):
        if self.writer:
            self.writer.send_simulation(on)
        else:
            self.status.log(f"{'Simulation' if on else 'Real'} gewählt; wird beim Verbinden gesendet")

    def on_mode(self, mode: SDSMode):
        self.model.set_mode(mode)
        self.show_mode_tab(mode)
        if self.writer:
            self.writer.send_mode(int(mode))
        else:
            self.status.log(f"Betriebsart {mode.name}; wird beim Verbinden gesendet")

    def on_unit_id(self, unit_id: int):
        if self.writer:
            self.writer.send_unit_id(unit_id)
        else:
            self.status.log("Unit-ID: nicht verbunden", "WARN")

    def on_srp(self, on: bool):
        if self.writer:
            self.writer.send_srp(on)
        else:
            self.status.log(f"SRP {'ein' if on else 'aus'}; wird beim Verbinden gesendet")

    # ------------------------------------------------------------
    # Tracking-Einheit
    # ------------------------------------------------------------
    DETECT_KEEP = 64
    LEVEL_DIST_K, LEVEL_DIST_EPS = 100.0, 1e-3     # wie SDS_110 Config (nur falls Detect fehlt)

    def candidate_from(self, r):
        """Candidate Report aus UnitReport + Detect desselben Frames (gleicher ms-Zeitstempel)."""
        d = self._detects.pop(r.timestamp_ms, None)
        dist = d.distance_m if d is not None else self.LEVEL_DIST_K / (r.level + self.LEVEL_DIST_EPS)
        return CandidateReport(r.time_us / 1e6, r.bearing_deg % 360.0, dist, np.array(r.state_vector()),
                               r.pairs, r.residual_s, r.unit)

    def track_report(self, r):
        cand = self.candidate_from(r)
        was = self.tracker.track
        was_confirmed = was is not None and was.confirmed
        dec = self.tracker.process(cand)
        t = self.tracker.track
        if dec.accepted:
            self._last_accept_host = time.monotonic()
        if was_confirmed and (t is None or t is not was):
            self._track_ended("neuer Beginn")
        if t is not None and t.confirmed and not was_confirmed:
            self.status.log(f"Spur bestätigt bei {cand.azimuth_deg:.0f}°, {cand.distance_m:.0f} m")
        if dec.accepted and t is not None and t.confirmed and self.writer and self.controls.feedback():
            p = self.tracker.predicted()
            self.writer.send_feedback(t.ref_state, p.azimuth_deg, p.distance_m)
        self.detect_tab.update_track(self.tracker, dec)

    def _track_ended(self, why: str):
        n = len(self.tracker.finished[-1]) if self.tracker.finished else 0
        self.status.log(f"Spur beendet ({why}), {n} Punkte")
        if self.writer and self.controls.feedback():
            self.writer.send_feedback(None)                 # Board setzt Schwellen und Gewichte zurück

    def check_track_timeout(self):
        """Ende nach T_END_S ohne übernommenen Report, auch wenn gar keine Reports mehr kommen."""
        t = self.tracker.track
        if t is None or self._last_accept_host is None:
            return
        if time.monotonic() - self._last_accept_host > T_END_S:
            confirmed = t.confirmed
            self.tracker.expire(t.t_last + T_END_S + 1e-3)
            if confirmed:
                self._track_ended(f"{T_END_S:.0f} s ohne Report")
            self.detect_tab.update_track(self.tracker, None)

    def on_feedback_toggled(self, on: bool):
        if not on and self.writer:
            self.writer.send_feedback(None)
        self.status.log(f"Tracking-Feedback {'ein' if on else 'aus'}")

    def export_track(self, path: str) -> int:
        """Beendete und laufende bestätigte Trajektorien als CSV; Rückgabe: Zahl der Punkte."""
        tracks = list(self.tracker.finished)
        if self.tracker.track is not None and self.tracker.track.confirmed:
            tracks.append(self.tracker.track.trajectory)
        n = 0
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["spur", "zeit_s", "ost_m", "nord_m", "v_ost_ms", "v_nord_ms",
                        "azimut_deg", "distanz_m", "geschw_ms", "kurs_deg"])
            for k, tr in enumerate(tracks, 1):
                for p in tr:
                    w.writerow([k, f"{p.time_s:.6f}", f"{p.x:.2f}", f"{p.y:.2f}", f"{p.vx:.2f}", f"{p.vy:.2f}",
                                f"{p.azimuth_deg:.2f}", f"{p.distance_m:.2f}", f"{p.speed_ms:.2f}", f"{p.course_deg:.1f}"])
                    n += 1
        return n

    def on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Trajektorie speichern", "trajektorie.csv", "CSV (*.csv)")
        if path:
            n = self.export_track(path)
            self.status.log(f"{n} Trajektorienpunkte gespeichert: {path}")

    def send_sync(self):
        """Sync (Id 7): aktuelle UTC in µs und die eingestellte Temperatur (oder unbekannt)."""
        if not self.writer:
            return
        temp = self.controls.temperature()
        self.writer.send_sync(time.time_ns() // 1000, temp)
        t = "–" if temp is None else f"{temp:.1f} °C"
        self.controls.set_sync_text(f"{time.strftime('%H:%M:%S')}, {t}")

    # ------------------------------------------------------------
    # USB
    # ------------------------------------------------------------
    def connect_usb(self):
        port = self.controls.port()
        if not port:
            self.status.log("Kein COM-Port ausgewählt", "ERROR")
            self.controls.set_connected(False, "kein Port")
            return
        try:
            self.ser = serial.Serial(port, self.SERIAL_BAUD, timeout=0.1)
        except Exception as e:
            self.ser = None
            self.status.log(f"Verbinden mit {port} fehlgeschlagen: {e}", "ERROR")
            self.controls.set_connected(False, "Fehler")
            return

        self.model.set_port(port)
        self.model.set_connected(True)
        self.reader = USBReader(self.ser, self.model)
        self.writer = USBWriter(self.ser, self.model)
        self.reader.log_signal.connect(lambda m: self.status.log(m, "WARN"))
        self.writer.log_signal.connect(lambda m: self.status.log(m, "TX" if m.startswith("TX") else "WARN"))
        self.reader.connection_lost.connect(self.on_connection_lost)     # Qt: in den GUI-Thread
        self.writer.connection_lost.connect(self.on_connection_lost)
        self.reader.start()
        self.writer.start()
        self.controls.set_connected(True, f"verbunden: {port}")
        self.status.log(f"Verbunden mit {port}")

        # Board auf den Stand der Schalter bringen, Zeit und Temperatur senden
        self.writer.send_simulation(self.controls.simulation())
        self.writer.send_mode(int(self.controls.mode()))
        self.writer.send_srp(self.controls.srp())
        self.send_sync()
        self.sync_timer.start(self.SYNC_PERIOD_MS)

    def on_connection_lost(self, reason: str):
        """USB-Verbindung abgebrochen (T6): trennen, Schalter auf Off, Ports neu einlesen."""
        if self.ser is None:              # schon getrennt (Reader und Writer melden beide)
            return
        port = self.model.port
        self.status.log(f"USB-Verbindung zu {port} verloren ({reason})", "ERROR")
        self.disconnect_usb(quiet=True)
        self.controls.set_connected(False, "Verbindung verloren")
        self.controls.refresh_ports()

    def disconnect_usb(self, quiet: bool = False):
        self.sync_timer.stop()
        for t in (self.reader, self.writer):
            if t:
                t.stop()
                t.wait()
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        was = self.ser is not None
        self.ser = self.reader = self.writer = None
        self.model.set_connected(False)
        self.controls.set_connected(False, "getrennt")
        if was and not quiet:
            self.status.log("Verbindung getrennt")

    # ------------------------------------------------------------
    # Queue-Polling
    # ------------------------------------------------------------
    def process_queue(self):
        """
        Queues abarbeiten, aber höchstens POLL_BUDGET_S lang: im Modus READ kommen ~3000
        Nachrichten/s, ohne Budget kehrte die GUI nie in die Ereignisschleife zurück (eingefroren).
        Übrig gebliebene Nachrichten folgen im nächsten Poll (20 ms später).
        """
        deadline = time.monotonic() + self.POLL_BUDGET_S
        self._process_queues(deadline)
        self.check_track_timeout()
        self._poll_count += 1
        if self._poll_count % self.STATS_EVERY == 0:
            dropped = self.model.take_dropped()
            if dropped:
                self.status.log(f"{dropped} Nachrichten verworfen (Anzeige zu langsam, Queue voll)", "WARN")
            self.status.update_stats()

    def _process_queues(self, deadline: float):
        while not self.model.detect_queue.empty():
            msg_id, frame = self.model.detect_queue.get()
            self.detect_tab.update_frame(frame)
            d = parse_detect(frame)
            self._detects[d.timestamp_ms] = d
            while len(self._detects) > self.DETECT_KEEP:
                self._detects.popitem(last=False)
            self.model.stats_total += 1
            self.model.stats_detect += 1
            self.model.update_frame(msg_id, frame, "DETECT")

        while not self.model.read_queue.empty() and time.monotonic() < deadline:
            msg_id, frame = self.model.read_queue.get()
            self.read_tab.update_frame(frame)
            self.model.stats_total += 1
            self.model.stats_read += 1

        while not self.model.unit_queue.empty():
            msg_id, frame = self.model.unit_queue.get()
            self.model.stats_total += 1
            try:
                r = parse_unit_report(frame)
            except ValueError as e:
                self.model.stats_rejected += 1
                self.status.log(f"UnitReport: {e}", "ERROR")
                continue
            self.model.stats_unit += 1
            self.detect_tab.update_unit_report(r)
            self.track_report(r)

        while not self.model.log_queue.empty():
            msg_id, frame = self.model.log_queue.get()
            self.model.stats_total += 1
            self.model.stats_log += 1
            for line in self._log_lines.push(parse_logger(frame)):
                self.status.log(f"SDS: {line}")

        while not self.model.inspect_queue.empty():
            kind, raw, reason = self.model.inspect_queue.get()
            self.model.update_inspector(kind, raw, reason)
            if kind == "frame":
                continue
            self.model.stats_total += 1
            self.model.stats_rejected += 1
            if kind == "unknown_msg_id":
                self.model.stats_unknown += 1
            else:
                self.model.stats_corrupt += 1
            if raw:
                self.status.log(f"{reason} ({len(raw)} Byte): {raw[:32].hex(' ').upper()}", "ERROR")
            else:
                self.status.log(f"Datenstrom: {reason}", "WARN")      # Resync auf das Magic

    # ------------------------------------------------------------
    # Fenster schließen -> USB stoppen
    # ------------------------------------------------------------
    def closeEvent(self, event):
        try:
            self.disconnect_usb()
        except Exception:
            pass
        event.accept()
