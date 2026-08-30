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
    # SDS_MsgRead1 Frame verarbeiten
    # ------------------------------------------------------------
    def update_frame(self, frame: bytes):
        """
        Erwartet SDS_MsgRead1 mit exakt 1048 Bytes:
        magic (4) | id (1) | len[3] | timestamp (4) | frameNumber (4)
        micNumber (4) | payload[256 floats] | crc32 (4)
        """

        if len(frame) != 1048:
            self.info_label.setText(f"Invalid READ frame size: {len(frame)}")
            return

        # Header auspacken
        magic, msg_id = struct.unpack("<IB", frame[:5])
        length = frame[5:8]
        timestamp = struct.unpack("<I", frame[8:12])[0]
        frameNumber = struct.unpack("<I", frame[12:16])[0]
        micNumber = struct.unpack("<I", frame[16:20])[0]

        # Payload floats
        payload = struct.unpack("<256f", frame[20:20 + 1024])

        # CRC
        crc32 = struct.unpack("<I", frame[-4:])[0]

        # Info anzeigen
        self.info_label.setText(
            f"READ Frame\n"
            f"magic=0x{magic:08X}\n"
            f"id={msg_id}\n"
            f"len={length.hex()}\n"
            f"timestamp={timestamp}\n"
            f"frameNumber={frameNumber}\n"
            f"micNumber={micNumber}\n"
            f"crc32=0x{crc32:08X}"
        )

        # Payload kompakt anzeigen
        text = "\n".join(f"{i:03d}: {v:.6f}" for i, v in enumerate(payload[:32]))
        self.payload_view.setPlainText(text)
