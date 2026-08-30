from collections import deque
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtGui import QColor, QTextCursor


class TabInspector(QWidget):
    def __init__(self, parent=None, max_entries=10):
        super().__init__(parent)

        # Ringbuffer für die letzten N Messages
        self.buffer = deque(maxlen=max_entries)

        # Counter für Message-IDs
        self.msg_counter = {
            1: 0,
            2: 0
        }

        layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

    # ------------------------------------------------------------
    # Eintrag hinzufügen (Ringbuffer)
    # ------------------------------------------------------------
    def add_entry(self, msg_id: int, length: int):
        # Counter aktualisieren
        if msg_id in self.msg_counter:
            self.msg_counter[msg_id] += 1

        # Kompakte Darstellung
        entry = f"ID={msg_id} len={length}"

        # Ringbuffer aktualisieren
        self.buffer.append((msg_id, entry))

        # GUI aktualisieren
        self._update_display()

    # ------------------------------------------------------------
    # Darstellung aktualisieren
    # ------------------------------------------------------------
    def _update_display(self):
        self.text.clear()

        # Summen anzeigen
        summary = (
            f"SUM ID=1: {self.msg_counter[1]}\n"
            f"SUM ID=2: {self.msg_counter[2]}\n"
            "-----------------------------\n"
        )

        self.text.setPlainText(summary)

        # Cursor ans Ende setzen
        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Letzte N Messages farbig darstellen
        for msg_id, entry in self.buffer:
            if msg_id == 1:
                color = QColor("green")
            elif msg_id == 2:
                color = QColor("blue")
            else:
                color = QColor("black")

            self._append_colored_line(entry, color)

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
