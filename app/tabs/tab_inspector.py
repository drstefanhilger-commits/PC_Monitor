from collections import deque
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtGui import QColor, QTextCursor
from app.model.SDSUSBModel import SDSUSBModel

class TabInspector(QWidget):
    """
    Inspector:
    - Statistik über alle empfangenen Frames (OK/ERROR)
    - Ringbuffer für Fehlerframes
    """

    def __init__(self, model, parent=None, max_errors=50):
        super().__init__(parent)
        self.model = model


        # Statistik
        self.stats = {
            "detect_ok": 0,
            "detect_err": 0,
            "read_ok": 0,
            "read_err": 0,
            "unknown": 0
        }

        # Fehler-Ringbuffer
        self.error_buffer = deque(maxlen=max_errors)

        layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

    # ------------------------------------------------------------
    # Gültige Frames (nur Statistik)
    # ------------------------------------------------------------
    def add_valid_frame(self, msg_id: int):
        if msg_id == 1:
            self.stats["detect_ok"] += 1
        elif msg_id == 2:
            self.stats["read_ok"] += 1
        else:
            self.stats["unknown"] += 1

        self._update_display()

    # ------------------------------------------------------------
    # Fehlerhafte Frames (Statistik + Ringbuffer)
    # ------------------------------------------------------------
    def add_error_frame(self, msg_id: int, raw: bytes, reason: str):
        if msg_id == 1:
            self.stats["detect_err"] += 1
        elif msg_id == 2:
            self.stats["read_err"] += 1
        else:
            self.stats["unknown"] += 1

        entry = {
            "msg_id": msg_id,
            "reason": reason,
            "raw": raw,
            "hex": raw.hex(" ").upper(),
            "len": len(raw)
        }

        self.error_buffer.append(entry)
        self._update_display()

    # ------------------------------------------------------------
    # Darstellung aktualisieren
    # ------------------------------------------------------------
    def _update_display(self):
        self.text.clear()
        cursor = self.text.textCursor()

        # Statistik
        stats_text = (
            "=== SDS Inspector Statistik ===\n\n"
            f"DETECT OK:   {self.stats['detect_ok']}\n"
            f"DETECT ERR:  {self.stats['detect_err']}\n"
            f"READ OK:     {self.stats['read_ok']}\n"
            f"READ ERR:    {self.stats['read_err']}\n"
            f"UNKNOWN:     {self.stats['unknown']}\n"
            "\n=== Fehler-Ringbuffer ===\n\n"
        )

        self.text.setPlainText(stats_text)
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Fehler anzeigen
        for entry in reversed(self.error_buffer):
            color = QColor("red")
            self._append_colored_line(
                f"[ERROR] msg_id={entry['msg_id']} len={entry['len']} reason={entry['reason']}",
                color
            )
            self._append_colored_line(entry["hex"], QColor("gray"))
            self._append_colored_line("", QColor("black"))

        # ------------------------------------------------------------
        # RAW-DUMP DES LETZTEN FRAMES (NEU)
        # ------------------------------------------------------------
        raw = self.model.last_raw_dump
        if raw is not None:
            self._append_colored_line("\n=== RAW FRAME ===", QColor("blue"))
            hex_dump = raw.hex(" ").upper()
            self._append_colored_line(hex_dump, QColor("black"))

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
