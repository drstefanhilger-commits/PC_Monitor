import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from app.usb.usb_reader import USBReader


class PlotTab(QWidget):
    def __init__(self, main_window=None):
        super().__init__()

        self.main_window = main_window
        self.reader: USBReader | None = None

        layout = QVBoxLayout(self)

        self.fig = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

        self.axes = [self.fig.add_subplot(8, 1, i + 1) for i in range(8)]
        for i, ax in enumerate(self.axes):
            ax.set_ylim(-1.0, 1.0)
            ax.set_xlim(0, 256)
            ax.grid(True)
            ax.set_ylabel(f"Ch {i}")

        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def set_reader(self, reader: USBReader | None):
        self.reader = reader

    def update_plot(self):
        # Nur im READ‑Modus plotten
        if self.main_window is not None and hasattr(self.main_window, "current_mode"):
            if self.main_window.current_mode != "READ":
                return

        if self.reader is None:
            return

        frame = self.reader.get_latest_frame()
        if frame is None:
            return

        frameIndex, data = frame

        for i in range(8):
            ax = self.axes[i]
            ax.clear()
            ax.plot(data[i], color="blue")
            ax.set_ylim(-1.0, 1.0)
            ax.set_xlim(0, data.shape[1])
            ax.grid(True)
            ax.set_ylabel(f"Ch {i}")

        self.canvas.draw()
