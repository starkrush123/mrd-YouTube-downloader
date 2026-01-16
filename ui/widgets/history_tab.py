
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt, QEvent
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
        self.history_table.setTabKeyNavigation(False)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.history_table.installEventFilter(self)
        self.populate_history()

    def populate_history(self):
        history = load_history()
        self.history_table.setRowCount(len(history))
        for i, entry in enumerate(history):
            item_title = QTableWidgetItem(entry['title'])
            item_title.setData(Qt.UserRole, entry['file_path'])
            self.history_table.setItem(i, 0, item_title)
            self.history_table.setItem(i, 1, QTableWidgetItem(entry['download_date']))

            open_file_btn = QPushButton('Buka File')
            open_file_btn.setFocusPolicy(Qt.NoFocus)
            open_file_btn.clicked.connect(lambda _, p=entry['file_path']: self.open_file(p))
            self.history_table.setCellWidget(i, 2, open_file_btn)

            open_folder_btn = QPushButton('Buka Folder')
            open_folder_btn.setFocusPolicy(Qt.NoFocus)
            open_folder_btn.clicked.connect(lambda _, p=entry['file_path']: self.open_folder(p))
            self.history_table.setCellWidget(i, 3, open_folder_btn)

    def eventFilter(self, source, event):
        if source == self.history_table and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                modifiers = event.modifiers()
                row = self.history_table.currentRow()
                if row >= 0:
                    item = self.history_table.item(row, 0)
                    if item:
                        path = item.data(Qt.UserRole)
                        if modifiers & Qt.ControlModifier:
                            self.open_folder(path)
                        else:
                            self.open_file(path)
                        return True
        return super().eventFilter(source, event)

    def open_file(self, path):
        if os.path.exists(path):
            os.startfile(path)

    def open_folder(self, path):
        if os.path.exists(path):
            os.startfile(os.path.dirname(path))

    def refresh_history(self):
        self.populate_history()
