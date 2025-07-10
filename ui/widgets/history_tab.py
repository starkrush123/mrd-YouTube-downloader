
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView
from PySide6.QtCore import Qt
from utils.history_manager import load_history

class HistoryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout(self))
        self.history_table = QTableWidget()
        self.layout().addWidget(self.history_table)
        self.setup_ui()

    def setup_ui(self):
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(['Judul', 'Tanggal Download', 'Buka File', 'Buka Folder'])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.populate_history()

    def populate_history(self):
        history = load_history()
        self.history_table.setRowCount(len(history))
        for i, entry in enumerate(history):
            self.history_table.setItem(i, 0, QTableWidgetItem(entry['title']))
            self.history_table.setItem(i, 1, QTableWidgetItem(entry['download_date']))

            open_file_btn = QPushButton('Buka File')
            open_file_btn.clicked.connect(lambda _, p=entry['file_path']: self.open_file(p))
            self.history_table.setCellWidget(i, 2, open_file_btn)

            open_folder_btn = QPushButton('Buka Folder')
            open_folder_btn.clicked.connect(lambda _, p=entry['file_path']: self.open_folder(p))
            self.history_table.setCellWidget(i, 3, open_folder_btn)

    def open_file(self, path):
        if os.path.exists(path):
            os.startfile(path)

    def open_folder(self, path):
        if os.path.exists(path):
            os.startfile(os.path.dirname(path))

    def refresh_history(self):
        self.populate_history()
