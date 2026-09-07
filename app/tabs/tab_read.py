import struct
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit


class TabRead(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.info_label = QLabel("READ Message Info")
        self.payload_view = QTextEdit()
        self.payload_view.setReadOnly(True)

        layout.addWidget(self.info_label)
        layout.addWidget(self.payload_view)

    # ------------------------------------------------------------
    # SDS_MsgRead Frame verarbeiten (532 Bytes)
    # ------------------------------------------------------------
    def update_frame(self, frame: bytes):
        if len(frame) != 532:
            self.info_label.setText(f"Invalid READ frame size: {len(frame)}")
            self.payload_view.clear()
            return

        # Header
        magic     = int.from_bytes(frame[0:4], "little")
        len_id    = int.from_bytes(frame[4:8], "little")
        timestamp = int.from_bytes(frame[8:12], "little")

        micNr     = int.from_bytes(frame[12:14], "little")
        frameNr   = int.from_bytes(frame[14:16], "little")

        msg_id = (len_id >> 24) & 0xFF
        length = len_id & 0x00FFFFFF

        # Payload (128 × uint32)
        data = []
        offset = 16
        for i in range(128):
            v = int.from_bytes(frame[offset:offset+4], "little")
            data.append(v)
            offset += 4

        crc32 = int.from_bytes(frame[offset:offset+4], "little")

        # Info anzeigen
        self.info_label.setText(
            f"SDS READ Frame\n"
            f"magic=0x{magic:08X}\n"
            f"msg_id={msg_id}\n"
            f"len={length}\n"
            f"timestamp={timestamp}\n"
            f"micNr={micNr}\n"
            f"frameNr={frameNr}\n"
            f"crc32=0x{crc32:08X}"
        )

        # ------------------------------------------------------------
        # 8 Mikrofone → 16 Werte pro Mikrofon
        # ------------------------------------------------------------
        mic_values = [data[i*16:(i+1)*16] for i in range(8)]

        # Intensität pro Mikrofon (Durchschnitt)
        intensities = [sum(vals) / len(vals) for vals in mic_values]

        # ASCII-Bar für Darstellung
        def bar(v):
            # Normierung für Anzeige
            length = int(v / max(intensities) * 40) if max(intensities) > 0 else 0
            return "█" * length

        # Text erzeugen
        text = "=== 8-Microphone Sound Intensity ===\n\n"
        for i, intensity in enumerate(intensities):
            text += f"Mic {i}: {intensity:10.2f}  {bar(intensity)}\n"

        text += "\n=== First 16 values of each mic ===\n\n"
        for i in range(8):
            text += f"Mic {i} values: {mic_values[i][:16]}\n"

        self.payload_view.setPlainText(text)
