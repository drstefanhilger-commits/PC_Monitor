from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

class FrameInspectorTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.text = QTextEdit()
        self.text.setReadOnly(True)

        layout.addWidget(self.text)
        self.setLayout(layout)

    def add_entry(self, info):
        msg_id = info["msg_id"]
        length = info["len"]
        preview = info["preview_hex"]

        line = f"ID={msg_id:02X} len={length} preview={preview}\n"
        self.text.append(line)
