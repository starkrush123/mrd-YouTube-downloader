from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QTextEdit, QPushButton, QLabel, QHBoxLayout
from PySide6.QtCore import Qt

class AIPanelWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout(self)

        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.layout.addWidget(self.output_display)

        input_layout = QHBoxLayout()
        self.input_label = QLabel("Perintah AI:")
        self.input_field = QLineEdit()
        self.input_label.setBuddy(self.input_field)
        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.input_field)

        self.layout.addLayout(input_layout)

        self.send_button = QPushButton("Kirim")
        self.layout.addWidget(self.send_button)

        self.input_field.returnPressed.connect(self.send_button.click)
