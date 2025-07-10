from PySide6.QtWidgets import QMenuBar
from PySide6.QtGui import QAction, QKeySequence
from utils import constants

class MenuBar(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        file_menu = self.addMenu("&File")
        self.open_download_folder_action = QAction("Buka Folder Unduhan", self)
        file_menu.addAction(self.open_download_folder_action)
        self.clear_input_action = QAction("Bersihkan Input", self)
        self.clear_input_action.setShortcut(QKeySequence("Ctrl+L"))
        file_menu.addAction(self.clear_input_action)
        file_menu.addSeparator()
        self.settings_action = QAction("Pengaturan...", self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        file_menu.addAction(self.settings_action)
        file_menu.addSeparator()
        self.exit_action = QAction("Keluar", self)
        self.exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        file_menu.addAction(self.exit_action)

        tools_menu = self.addMenu("&Alat")
        self.paste_and_go_action = QAction("Tempel & Proses", self)
        self.paste_and_go_action.setShortcut(QKeySequence("Ctrl+Shift+V"))
        tools_menu.addAction(self.paste_and_go_action)

        help_menu = self.addMenu("&Bantuan")
        self.check_update_action = QAction("Cek Pembaruan...", self)
        help_menu.addAction(self.check_update_action)
        self.view_logs_action = QAction("Lihat Log Debug", self)
        help_menu.addAction(self.view_logs_action)
        help_menu.addSeparator()
        self.debug_mode_action = QAction("Mode Debug", self)
        self.debug_mode_action.setCheckable(True)
        self.debug_mode_action.setChecked(constants.is_debug_mode())
        help_menu.addAction(self.debug_mode_action)
        help_menu.addSeparator()
        self.about_action = QAction("Tentang Aplikasi...", self)
        help_menu.addAction(self.about_action)
