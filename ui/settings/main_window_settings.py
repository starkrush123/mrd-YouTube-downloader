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
            self.main_window.set_status_text(_("Mode Debug Diaktifkan. Log akan dicetak/disimpan."))
        else:
            self.main_window.set_status_text(_("Mode Debug Dinonaktifkan."))
        self.main_window.update_window_title_status(_("Siap"))

    def open_debug_log(self):
        if not constants.is_debug_mode() and not os.path.exists(constants.LOG_FILE_PATH):
            QMessageBox.information(self.main_window, _("Mode Debug Nonaktif"), _("Mode debug saat ini nonaktif dan file log tidak ditemukan.\nAktifkan mode debug dan lakukan beberapa aksi untuk membuat log."))
            self.main_window.set_status_text(_("File log tidak ditemukan (mode debug nonaktif)."))
            return
        
        if os.path.exists(constants.LOG_FILE_PATH):
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(constants.LOG_FILE_PATH))
                _m = _("Membuka file log:")
                self.main_window.set_status_text(f"{_m}: {constants.LOG_FILE_PATH}")
            except Exception as e:
                _m1 = _("Tidak dapat membuka file log:")
                _m2 = _("Error:")
                QMessageBox.warning(self.main_window, _("Gagal Buka Log"), f"{_m1}: {constants.LOG_FILE_PATH}\n{_m2}: {str(e)}")
                self.main_window.set_status_text(_("Gagal membuka file log."))
        else:
            _m1 = _("File log tidak ditemukan di:")
            _m2 = _("Log akan dibuat jika mode debug aktif dan ada aktivitas.")
            QMessageBox.information(self.main_window, _("Log Tidak Ditemukan"), f"{_m1}: {constants.LOG_FILE_PATH}\n{_m2}")
            self.main_window.set_status_text(_("File log belum ada."))

    def open_current_download_folder(self):
        download_path = self.main_window.settings.get('output_path', '')
        if download_path and os.path.isdir(download_path):
            self.main_window.open_location(download_path)
            _m = _("Membuka folder unduhan:")
            self.main_window.set_status_text(f"{_m}: {download_path}")
        else:
            _m1 = _("Folder unduhan")
            _m2 = _("tidak valid atau tidak ada. Cek pengaturan.")
            QMessageBox.warning(self.main_window, _("Folder Tidak Ditemukan"), f"{_m1} '{download_path}' {_m2}")
            self.main_window.set_status_text(_("Gagal membuka folder unduhan."))