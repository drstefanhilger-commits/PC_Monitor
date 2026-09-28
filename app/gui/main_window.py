import time

import serial
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QSplitter, QTabWidget, QWidget

from app.model.SDSUSBModel import SDSMode, SDSUSBModel
from app.tabs.tab_calibrate import TabCalibrate
from app.tabs.tab_detect import TabDetect
from app.tabs.tab_read import TabRead
from app.usb.messages import LineAssembler, parse_logger, parse_unit_report
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

        # --- Bedienfeld links ------------------------------------------
        self.controls = ControlPanel()
        self.controls.power_toggled.connect(self.on_power)
        self.controls.simulation_toggled.connect(self.on_simulation)
        self.controls.mode_changed.connect(self.on_mode)
        self.controls.unit_id_set.connect(self.on_unit_id)
        self.controls.srp_toggled.connect(self.on_srp)
        self.controls.sync_requested.connect(self.send_sync)

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

    def disconnect_usb(self):
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
        if was:
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
