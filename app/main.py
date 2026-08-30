#!/usr/bin/env python3

import sys
from PyQt6.QtWidgets import QApplication
from app.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(900, 700)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
