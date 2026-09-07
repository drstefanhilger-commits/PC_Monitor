from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QTextEdit


class Logger(QObject):
    """
    Thread-sicherer Logger:
    - empfängt Log-Messages über pyqtSignal(str)
    - schreibt deterministisch in ein QTextEdit
    - keine GUI-Operationen aus Worker-Threads
    """

    def __init__(self, text_widget: QTextEdit):
        super().__init__()
        self.text_widget = text_widget

    @pyqtSlot(str)
    def log(self, message: str):
        """
        Wird IMMER im GUI-Thread ausgeführt,
        weil USBReader/USBWriter pyqtSignal(str) verwenden.
        """
        try:
            self.text_widget.append(message)
        except Exception:
            # GUI ist evtl. schon geschlossen → ignorieren
            pass
