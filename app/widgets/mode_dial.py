# app/widgets/mode_dial.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDial, QGridLayout, QLabel, QWidget

from app.model.SDSUSBModel import SDSMode


class ModeDial(QWidget):
    """
    Drehschalter für die Betriebsart, drei Rastungen:
      links = DETECT, oben = READ, rechts = CALIBRATE
    mode_changed(SDSMode) bei jeder Änderung (auch durch set_mode(), außer emit=False).
    Die Werte der Betriebsarten (SDSMode) entsprechen der Firmware SDS_110 (ICD Id 2).
    """

    ORDER = (SDSMode.DETECT, SDSMode.READ, SDSMode.CALIBRATE)

    mode_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.dial = QDial()
        self.dial.setRange(0, len(self.ORDER) - 1)
        self.dial.setNotchesVisible(True)
        self.dial.setWrapping(False)
        self.dial.setPageStep(1)
        self.dial.setFixedSize(96, 96)

        self._labels = {m: QLabel(m.name.capitalize()) for m in self.ORDER}
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(self._labels[SDSMode.READ], 0, 1, Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(self._labels[SDSMode.DETECT], 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        grid.addWidget(self.dial, 1, 1, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self._labels[SDSMode.CALIBRATE], 1, 2, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        self.dial.valueChanged.connect(self._on_value)
        self._highlight(self.mode())

    def mode(self) -> SDSMode:
        return self.ORDER[self.dial.value()]

    def set_mode(self, mode: SDSMode, emit: bool = True):
        self.dial.blockSignals(not emit)
        self.dial.setValue(self.ORDER.index(mode))
        self.dial.blockSignals(False)
        self._highlight(mode)

    def _on_value(self, value: int):
        mode = self.ORDER[value]
        self._highlight(mode)
        self.mode_changed.emit(mode)

    def _highlight(self, mode: SDSMode):
        for m, lab in self._labels.items():
            lab.setStyleSheet("font-weight: bold; color: #1565c0;" if m == mode else "color: gray;")
