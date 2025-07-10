import os
from PySide6.QtWidgets import QMessageBox, QApplication
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from utils import constants
from utils.constants import set_debug_mode
from utils.styles import LIGHT_THEME_STYLESHEET, DARK_THEME_STYLESHEET

class MainWindowSettings:
    def __init__(self, main_window):
        self.main_window = main_window

    def apply_theme(self):
        theme = self.main_window.settings.get("theme", "Light")
        if theme == "Dark":
            self.main_window.setStyleSheet(DARK_THEME_STYLESHEET)
        else:
            self.main_window.setStyleSheet(LIGHT_THEME_STYLESHEET)

    def toggle_debug_mode(self, checked):
        set_debug_mode(checked)
        self.main_window.settings['debug_mode'] = checked
        self.main_window.save_app_settings()
        if checked:
            self.main_window.set_status_text("Mode Debug Diaktifkan. Log akan dicetak/disimpan.")
        else:
            self.main_window.set_status_text("Mode Debug Dinonaktifkan.")
        self.main_window.update_window_title_status("Siap")

    def open_debug_log(self):
        if not constants.is_debug_mode() and not os.path.exists(constants.LOG_FILE_PATH):
            QMessageBox.information(self.main_window, "Mode Debug Nonaktif", "Mode debug saat ini nonaktif dan file log tidak ditemukan.\nAktifkan mode debug dan lakukan beberapa aksi untuk membuat log.")
            self.main_window.set_status_text("File log tidak ditemukan (mode debug nonaktif).")
            return
        
        if os.path.exists(constants.LOG_FILE_PATH):
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(constants.LOG_FILE_PATH))
                self.main_window.set_status_text(f"Membuka file log: {constants.LOG_FILE_PATH}")
            except Exception as e:
                QMessageBox.warning(self.main_window, "Gagal Buka Log", f"Tidak dapat membuka file log: {constants.LOG_FILE_PATH}\nError: {str(e)}")
                self.main_window.set_status_text("Gagal membuka file log.")
        else:
            QMessageBox.information(self.main_window, "Log Tidak Ditemukan", f"File log tidak ditemukan di: {constants.LOG_FILE_PATH}\nLog akan dibuat jika mode debug aktif dan ada aktivitas.")
            self.main_window.set_status_text("File log belum ada.")

    def open_current_download_folder(self):
        download_path = self.main_window.settings.get('output_path', '')
        if download_path and os.path.isdir(download_path):
            self.main_window.open_location(download_path)
            self.main_window.set_status_text(f"Membuka folder unduhan: {download_path}")
        else:
            QMessageBox.warning(self.main_window, "Folder Tidak Ditemukan", f"Folder unduhan '{download_path}' tidak valid atau tidak ada. Cek pengaturan.")
            self.main_window.set_status_text("Gagal membuka folder unduhan.")