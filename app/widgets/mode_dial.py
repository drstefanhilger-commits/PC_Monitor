# app/widgets/mode_dial.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QDial, QLabel


class ModeDial(QWidget):
    """
    Drehschalter für SDS-Mode:
    0 = DETECT, 1 = READ, 2 = CALIBRATE
    Ruft TabUSB.set_mode() auf.
    """

    def __init__(self, model, tab_usb):
        super().__init__()

        self.model = model
        self.tab_usb = tab_usb

        layout = QVBoxLayout(self)

        self.label = QLabel("Mode: DETECT")

        self.dial = QDial()
        self.dial.setMinimum(0)
        self.dial.setMaximum(2)
        self.dial.setNotchesVisible(True)
        self.dial.setWrapping(False)

        self.dial.valueChanged.connect(self.on_change)

        layout.addWidget(self.label)
        layout.addWidget(self.dial)

    def on_change(self, value: int):
        modes = ["DETECT", "CALIBRATE", "READ"]
        mode = modes[value]

        self.label.setText(f"Mode: {mode}")
        self.model.set_mode(mode)

        self.tab_usb.set_mode(mode)
