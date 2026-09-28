# app/widgets/status_panel.py

import time

from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class StatusPanel(QWidget):
    """
    Status/Error-Fenster im unteren Bereich:
      - Zählerzeile RX/TX/Fehler (aus SDSUSBModel)
      - Meldungsliste mit Zeit und Stufe (INFO, WARN, ERROR), max. MAX_LINES Zeilen
    Ersetzt den bisherigen Inspector-Tab.
    """

    MAX_LINES = 2000
    MAX_PER_SECOND = 20          # mehr Meldungen je Sekunde werden zusammengefasst (Fehlerflut)
    COLORS = {"INFO": "#424242", "WARN": "#ef6c00", "ERROR": "#c62828", "TX": "#2e7d32"}

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 4)

        top = QHBoxLayout()
        self.stats_label = QLabel()
        self.btn_clear = QPushButton("Leeren")
        self.btn_clear.setToolTip("Meldungen und Zähler RX/Fehler/TX löschen")
        self.btn_clear.clicked.connect(self.clear)
        top.addWidget(QLabel("<b>Status / Fehler</b>"))
        top.addSpacing(12)
        top.addWidget(self.stats_label)
        top.addStretch()
        top.addWidget(self.btn_clear)
        lay.addLayout(top)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(self.MAX_LINES)
        lay.addWidget(self.text)
        self._sec, self._count, self._suppressed = 0, 0, 0
        self.update_stats()

    def log(self, message: str, level: str = "INFO"):
        sec = int(time.monotonic())
        if sec != self._sec:
            if self._suppressed:
                n, self._suppressed = self._suppressed, 0
                self._write(f"… {n} weitere Meldungen in der letzten Sekunde unterdrückt", "WARN")
            self._sec, self._count = sec, 0
        self._count += 1
        if self._count > self.MAX_PER_SECOND:
            self._suppressed += 1
            return
        self._write(message, level)

    def _write(self, message: str, level: str):
        cur = self.text.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self.COLORS.get(level, "#424242")))
        cur.insertText(f"{time.strftime('%H:%M:%S')}  {level:<5} {message}\n", fmt)
        self.text.setTextCursor(cur)
        self.text.ensureCursorVisible()

    def clear(self):
        """Meldungen und Zähler (RX, Fehler, TX) löschen."""
        self.text.clear()
        self._count, self._suppressed = 0, 0
        self.model.reset_stats()
        self.update_stats()

    def update_stats(self):
        m = self.model
        self.stats_label.setText(
            f"RX {m.stats_total}  (Detect {m.stats_detect}, Unit {m.stats_unit}, Read {m.stats_read}, "
            f"Log {m.stats_log})   "
            f"Fehler {m.stats_rejected}   TX {m.stats_sent_total}")
