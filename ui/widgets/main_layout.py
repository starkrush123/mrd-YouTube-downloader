from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QComboBox, QProgressBar, QLabel
)

class MainLayout(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        input_layout = QHBoxLayout()
        self.url_input_label = QLabel()
        self.input_line_edit = QLineEdit()
        self.url_input_label.setBuddy(self.input_line_edit)
        input_layout.addWidget(self.url_input_label)
        input_layout.addWidget(self.input_line_edit, 1)

        input_label = QLabel("Tipe:")
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["Video", "Playlist", "Channel"])
        self.search_type_combo.setToolTip("Pilih jenis input jika bukan URL pasti")
        input_label.setBuddy(self.search_type_combo)
        input_layout.addWidget(input_label)
        input_layout.addWidget(self.search_type_combo)

        self.go_button = QPushButton("Go!")
        self.go_button.setObjectName("go_button")
        input_layout.addWidget(self.go_button)
        main_layout.addLayout(input_layout)

        action_buttons_layout = QHBoxLayout()
        self.settings_button = QPushButton("Pengaturan...")
        self.settings_button.setObjectName("settings_button")
        self.info_button = QPushButton("Info")
        self.info_button.setObjectName("info_button")
        action_buttons_layout.addStretch()
        action_buttons_layout.addWidget(self.settings_button)
        action_buttons_layout.addWidget(self.info_button)
        main_layout.addLayout(action_buttons_layout)

        self.main_progress_bar = QProgressBar()
        self.main_progress_bar.setVisible(False)
        main_layout.addWidget(self.main_progress_bar)

        self.status_label = QLabel("Siap. Masukkan URL atau kata kunci.")
        self.status_label.setWordWrap(True)
        self.status_label.setProperty("accessibleLiveRegion", "polite")
        main_layout.addWidget(self.status_label)
        main_layout.addStretch()
