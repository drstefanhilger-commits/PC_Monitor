from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TabCalibrate(QWidget):
    """
    Tab für die Betriebsart CALIBRATE.
    Die Firmware SDS_110 verarbeitet in CALIBRATE derzeit nichts (ProcessingTask::process());
    Inhalte folgen, sobald das Kalibrierverfahren festgelegt ist (siehe docs/ToDo.md).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        info = QLabel(
            "<h3>Calibrate</h3>"
            "<p>Die Firmware SDS_110 hat in der Betriebsart CALIBRATE noch keine Funktion; "
            "das Board sendet in diesem Modus keine Daten.</p>"
            "<p>Vorgesehen: Pegel und Laufzeit je Mikrofon, Azimut-Kalibrierung "
            "(Nordrichtung), Positionen der Einheiten.</p>")
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addStretch()
