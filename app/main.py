#!/usr/bin/env python3

import sys
import traceback
from PyQt6.QtWidgets import QApplication
from app.gui.main_window import MainWindow


def install_excepthook(window):
    """
    PyQt6 beendet das Programm bei jeder nicht abgefangenen Ausnahme in einem Slot (qFatal).
    Stattdessen: Traceback auf stderr und ins Status-Fenster, Programm läuft weiter.
    """
    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        sys.stderr.write(text)
        try:
            window.status.log(f"Programmfehler: {exc_type.__name__}: {exc} (Details auf der Konsole)", "ERROR")
        except Exception:
            pass
    sys.excepthook = hook


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    install_excepthook(w)
    w.resize(900, 700)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
