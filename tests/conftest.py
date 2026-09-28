"""Gemeinsame QApplication für alle Tests (Qt offscreen). Sie darf während des Laufs nicht
freigegeben werden: ein neu erzeugtes Widget nach dem Freigeben stürzt ab (Segmentation fault)."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

# Einstellungen (Nordabgleich) nicht in die Benutzerkonfiguration schreiben
_SETTINGS_DIR = tempfile.mkdtemp(prefix="pc_monitor_settings_")
for _fmt in (QSettings.Format.NativeFormat, QSettings.Format.IniFormat):
    QSettings.setPath(_fmt, QSettings.Scope.UserScope, _SETTINGS_DIR)


@pytest.fixture(autouse=True)
def _clean_settings():
    QSettings("SDS_110", "PC_Monitor").clear()
    yield


@pytest.fixture(scope="session")
def qapp():
    return _APP
