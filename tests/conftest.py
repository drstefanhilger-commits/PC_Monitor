"""Gemeinsame QApplication für alle Tests (Qt offscreen). Sie darf während des Laufs nicht
freigegeben werden: ein neu erzeugtes Widget nach dem Freigeben stürzt ab (Segmentation fault)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def qapp():
    return _APP
