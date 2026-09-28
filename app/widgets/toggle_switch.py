# app/widgets/toggle_switch.py

from PyQt6.QtCore import Qt, QRectF, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QSizePolicy, QWidget


class _Track(QAbstractButton):
    """Gezeichneter Schiebeschalter (Schiene + Knopf), checkable."""

    def __init__(self, on_color: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._on_color = QColor(on_color)

    def sizeHint(self):
        return QSize(46, 24)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        track = self._on_color if self.isChecked() else QColor("#9e9e9e")
        if not self.isEnabled():
            track = QColor("#cfcfcf")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 4
        x = r.right() - d - 2 if self.isChecked() else r.left() + 2
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, r.top() + 2, d, d))


class ToggleSwitch(QWidget):
    """
    Kippschalter mit Beschriftung links (aus) und rechts (ein):  Real [==o] Simulation
    toggled(bool) wie QAbstractButton; setChecked() ohne Signal über blockSignals().
    """

    toggled = pyqtSignal(bool)

    def __init__(self, off_text: str, on_text: str, on_color: str = "#2e7d32", parent=None):
        super().__init__(parent)
        self._track = _Track(on_color, self)
        self._off = QLabel(off_text)
        self._on = QLabel(on_text)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._off)
        lay.addWidget(self._track)
        lay.addWidget(self._on)
        lay.addStretch()
        self._track.toggled.connect(self._on_toggled)
        self._on_toggled(False)

    def _on_toggled(self, state: bool):
        self._off.setStyleSheet("" if state else "font-weight: bold;")
        self._on.setStyleSheet("font-weight: bold;" if state else "")
        self.toggled.emit(state)

    def isChecked(self) -> bool:
        return self._track.isChecked()

    def setChecked(self, state: bool, emit: bool = True):
        if not emit:
            self._track.blockSignals(True)
            self._track.setChecked(state)
            self._track.blockSignals(False)
            self._off.setStyleSheet("" if state else "font-weight: bold;")
            self._on.setStyleSheet("font-weight: bold;" if state else "")
        else:
            self._track.setChecked(state)

    def click(self):
        self._track.click()
