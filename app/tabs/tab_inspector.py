from collections import deque
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel, QGridLayout
from PyQt6.QtGui import QColor, QTextCursor
from app.model.Logger import Logger


class TabInspector(QWidget):
    """
    Inspector:
    - Statistik über empfangene Frames (RX)
    - Statistik über gesendete Frames (TX)
    - Anzeige der letzten Error-Message (statt Ringbuffer)
    - Anzeige des letzten RAW-Dumps (RX)
    """

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.reader = None
        self.writer = None

        # Nur die letzte Error-Message speichern
        self.last_error = None

        layout = QVBoxLayout(self)

        # ------------------------------------------------------------
        # RX Statistik
        # ------------------------------------------------------------
        grid_rx = QGridLayout()

        self.label_total    = QLabel("Total RX: 0")
        self.label_detect   = QLabel("Detect OK: 0")
        self.label_read     = QLabel("Read OK: 0")
        self.label_corrupt  = QLabel("Corrupt: 0")
        self.label_unknown  = QLabel("Unknown: 0")
        self.label_rejected = QLabel("Rejected: 0")

        grid_rx.addWidget(self.label_total,    0, 0)
        grid_rx.addWidget(self.label_detect,   1, 0)
        grid_rx.addWidget(self.label_read,     2, 0)
        grid_rx.addWidget(self.label_corrupt,  3, 0)
        grid_rx.addWidget(self.label_unknown,  4, 0)
        grid_rx.addWidget(self.label_rejected, 5, 0)

        layout.addLayout(grid_rx)

        # ------------------------------------------------------------
        # TX Statistik (Send-Anzeige)
        # ------------------------------------------------------------
        grid_tx = QGridLayout()

        self.label_sent_total = QLabel("Total TX: 0")
        self.label_sent_mode  = QLabel("MODE TX: 0")
        self.label_sent_last  = QLabel("Last TX MsgID: -")

        grid_tx.addWidget(self.label_sent_total, 0, 0)
        grid_tx.addWidget(self.label_sent_mode,  1, 0)
        grid_tx.addWidget(self.label_sent_last,  2, 0)

        layout.addLayout(grid_tx)

        # ------------------------------------------------------------
        # Textbereich
        # ------------------------------------------------------------
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

        # ------------------------------------------------------------
        # Reason Label
        # ------------------------------------------------------------
        self.reason_label = QLabel("Reason: -")
        layout.addWidget(self.reason_label)

        # Logger
        self.logger = Logger(self.text)

    # ------------------------------------------------------------
    # USB verbinden
    # ------------------------------------------------------------
    def set_usb(self, reader, writer):
        self.reader = reader
        self.writer = writer

        self.reader.log_signal.connect(self.logger.log)
        self.writer.log_signal.connect(self.logger.log)

    # ------------------------------------------------------------
    # Öffentliche API: gültige Frames
    # ------------------------------------------------------------
    def add_valid_frame(self, msg_id: int):
        if msg_id == 1:
            self.model.stats_detect += 1
        elif msg_id == 2:
            self.model.stats_read += 1
        else:
            self.model.stats_unknown += 1

        self.model.stats_total += 1
        self.update_inspector()

    # ------------------------------------------------------------
    # Öffentliche API: fehlerhafte Frames
    # ------------------------------------------------------------
    def add_error_frame(self, msg_id: int, raw: bytes, reason: str):
        self.model.stats_corrupt += 1
        self.model.stats_rejected += 1
        self.model.stats_total += 1

        self.last_error = {
            "msg_id": msg_id,
            "reason": reason,
            "raw": raw,
            "hex": raw.hex(" ").upper(),
            "len": len(raw)
        }

        self.update_inspector()

    # ------------------------------------------------------------
    # Darstellung aktualisieren
    # ------------------------------------------------------------
    def update_inspector(self):
        self._update_display()

    # ------------------------------------------------------------
    # Darstellung aktualisieren (intern)
    # ------------------------------------------------------------
    def _update_display(self):
        self.text.clear()
        cursor = self.text.textCursor()

        # ------------------------------------------------------------
        # RX Statistik
        # ------------------------------------------------------------
        stats_rx = (
            "=== SDS Inspector Statistik (Empfangen) ===\n\n"
            f"TOTAL RX:     {self.model.stats_total}\n"
            f"DETECT OK:    {self.model.stats_detect}\n"
            f"READ OK:      {self.model.stats_read}\n"
            f"CORRUPT:      {self.model.stats_corrupt}\n"
            f"UNKNOWN:      {self.model.stats_unknown}\n"
            f"REJECTED:     {self.model.stats_rejected}\n"
        )

        self.text.setPlainText(stats_rx)
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # ------------------------------------------------------------
        # TX Statistik
        # ------------------------------------------------------------
        self._append_colored_line("\n=== Gesendete Messages (TX) ===", QColor("darkGreen"))

        self._append_colored_line(
            f"TOTAL TX:     {self.model.stats_sent_total}",
            QColor("darkGreen")
        )
        self._append_colored_line(
            f"MODE TX:      {self.model.stats_sent_by_id[3]}",
            QColor("darkGreen")
        )
        self._append_colored_line(
            f"LAST TX ID:   {self.model.last_sent_msg_id}",
            QColor("darkGreen")
        )

        if self.model.last_sent_frame:
            self._append_colored_line(
                f"LAST TX FRAME: {self.model.last_sent_frame.hex(' ').upper()}",
                QColor("black")
            )

        # ------------------------------------------------------------
        # Nur die letzte Error-Message anzeigen
        # ------------------------------------------------------------
        self._append_colored_line("\n=== Letzte Error-Message ===", QColor("red"))

        if self.last_error:
            self._append_colored_line(
                f"[ERROR] msg_id={self.last_error['msg_id']} "
                f"len={self.last_error['len']} reason={self.last_error['reason']}",
                QColor("red")
            )
            self._append_colored_line(self.last_error["hex"], QColor("gray"))
        else:
            self._append_colored_line("(keine Fehler)", QColor("gray"))

        # ------------------------------------------------------------
        # RAW-Dump anzeigen (RX)
        # ------------------------------------------------------------
        raw = self.model.last_raw_dump
        if raw is not None:
            self._append_colored_line("\n=== RAW FRAME (RX) ===", QColor("blue"))
            hex_dump = raw.hex(" ").upper()
            self._append_colored_line(hex_dump, QColor("black"))

        # Reason anzeigen
        self.reason_label.setText(f"Reason: {self.model.last_reason}")

    # ------------------------------------------------------------
    # Hilfsfunktion: farbige Zeile anhängen
    # ------------------------------------------------------------
    def _append_colored_line(self, text: str, color: QColor):
        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = cursor.charFormat()
        fmt.setForeground(color)
        cursor.setCharFormat(fmt)

        cursor.insertText(text + "\n")
