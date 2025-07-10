import os
import sys
import tempfile
import subprocess
import webbrowser
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QApplication
from PySide6.QtCore import Qt, QUrl

from threads.update_thread import UpdateCheckThread, DownloadUpdateThread
from utils import constants

class MainWindowUpdate:
    def __init__(self, main_window):
        self.main_window = main_window

    def _try_restore_focus_after_manual_check(self):
        if self.main_window._restore_focus_to_input_after_manual_check:
            self.main_window.main_view_widget.input_line_edit.setFocus()
        self.main_window._restore_focus_to_input_after_manual_check = False

    def initiate_update_check(self, manual_check=True):
        if self.main_window.update_check_thread and self.main_window.update_check_thread.isRunning():
            if manual_check: QMessageBox.information(self.main_window, "Cek Pembaruan", "Pengecekan pembaruan sedang berjalan.")
            return
        if manual_check:
            self.main_window.set_status_text("Mengecek pembaruan...")
            self.main_window._restore_focus_to_input_after_manual_check = (QApplication.focusWidget() == self.main_window.main_view_widget.input_line_edit)
        else:
            self.main_window._restore_focus_to_input_after_manual_check = False
        self.main_window.update_check_thread = UpdateCheckThread(constants.CURRENT_APP_VERSION, constants.VERSION_INFO_URL, self.main_window)
        self.main_window.update_check_thread.update_available.connect(lambda info: self.handle_update_available(info, manual_check))
        self.main_window.update_check_thread.no_update_found.connect(lambda msg: self.handle_no_update_found(msg, manual_check))
        self.main_window.update_check_thread.update_check_error.connect(lambda msg: self.handle_update_check_error(msg, manual_check))
        self.main_window.update_check_thread.finished.connect(self._try_restore_focus_after_manual_check)
        self.main_window.update_check_thread.finished.connect(self.main_window._on_any_thread_finished)
        self.main_window.set_ui_busy_state(True, "update_checking")
        self.main_window.update_check_thread.start()

    def handle_update_available(self, version_info, manual_check):
        latest_version = version_info.get("latest_version")
        download_url_sfx = version_info.get("download_url_sfx")
        changelog = version_info.get("changelog", "Tidak ada catatan perubahan.")
        self.main_window.set_status_text(f"Pembaruan v{latest_version} tersedia.")
        msg_box = QMessageBox(self.main_window)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Pembaruan Tersedia")
        msg_box.setText(f"Versi baru (v{latest_version}) tersedia!\nAnda menggunakan v{constants.CURRENT_APP_VERSION}.\n\nCatatan Perubahan:\n{changelog}")
        msg_box.setInformativeText("Apakah Anda ingin mengunduh dan menginstal pembaruan sekarang?\n\nAplikasi akan ditutup dan updater akan berjalan.")
        yes_button = msg_box.addButton("Ya, Unduh & Instal", QMessageBox.ButtonRole.YesRole)
        no_button = msg_box.addButton("Nanti Saja", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(yes_button)
        msg_box.exec()
        if msg_box.clickedButton() == yes_button:
            self.start_update_download(download_url_sfx)
        else:
            if manual_check: self.main_window.set_status_text("Pembaruan ditunda oleh pengguna.")
            self.main_window.set_ui_busy_state(False, "update_available_declined")
            self._try_restore_focus_after_manual_check()

    def handle_no_update_found(self, message, manual_check):
        if manual_check:
            self.main_window.set_status_text(message)
            if "lebih baru dari versi yang tersedia di server" in message:
                QMessageBox.warning(self.main_window, "Cek Pembaruan", message + "\n\nDisarankan untuk tidak melakukan downgrade.")
            else:
                QMessageBox.information(self.main_window, "Cek Pembaruan", message)

    def handle_update_check_error(self, error_message, manual_check):
        if manual_check:
            self.main_window.set_status_text(f"Error cek pembaruan: {error_message}")
            QMessageBox.warning(self.main_window, "Error Cek Pembaruan", error_message)
        elif "URL info versi belum diatur" in error_message and constants.VERSION_INFO_URL == "URL_GIST_JSON_LO_DISINI":
             QMessageBox.warning(self.main_window, "Konfigurasi Update", "URL untuk info versi belum diatur di kode.\nSilakan atur konstanta VERSION_INFO_URL.")

    def start_update_download(self, sfx_url):
        if self.main_window.download_update_thread and self.main_window.download_update_thread.isRunning():
            QMessageBox.information(self.main_window, "Download Update", "Proses download update sudah berjalan.")
            return
        temp_dir = tempfile.gettempdir()
        sfx_filename = os.path.basename(QUrl(sfx_url).path())
        if not sfx_filename or not sfx_filename.lower().endswith((".exe", ".sfx")): sfx_filename = "mrd_downloader_update.sfx.exe"
        self.main_window.sfx_save_path = os.path.join(temp_dir, sfx_filename)
        self.main_window.update_progress_dialog = QProgressDialog("Mengunduh pembaruan...", "Batal", 0, 100, self.main_window)
        self.main_window.update_progress_dialog.setWindowTitle("Download Pembaruan")
        self.main_window.update_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.main_window.update_progress_dialog.setAutoClose(False)
        self.main_window.update_progress_dialog.setAutoReset(False)
        self.main_window.update_progress_dialog.setValue(0)
        self.main_window.download_update_thread = DownloadUpdateThread(sfx_url, self.main_window.sfx_save_path, self.main_window)
        self.main_window.download_update_thread.download_progress.connect(self.handle_update_download_progress)
        self.main_window.download_update_thread.download_finished.connect(self.handle_update_download_finished)
        self.main_window.download_update_thread.download_error.connect(self.handle_update_download_error)
        self.main_window.download_update_thread.finished.connect(self.main_window._on_any_thread_finished)
        self.main_window.update_progress_dialog.canceled.connect(self.cancel_update_download)
        self.main_window.set_ui_busy_state(True, "downloading_update")
        self.main_window.set_status_text(f"Mengunduh pembaruan dari {sfx_url}...")
        self.main_window.update_progress_dialog.show()

    def cancel_update_download(self):
        if self.main_window.download_update_thread and self.main_window.download_update_thread.isRunning():
            self.main_window.download_update_thread.stop()
        if self.main_window.update_progress_dialog:
            self.main_window.update_progress_dialog.close()
        self.main_window.set_status_text("Download pembaruan dibatalkan.")
        QMessageBox.information(self.main_window, "Download Dibatalkan", "Proses download pembaruan telah dibatalkan.")

    def handle_update_download_progress(self, percentage):
        if self.main_window.update_progress_dialog: self.main_window.update_progress_dialog.setValue(percentage)

    def handle_update_download_finished(self, sfx_path):
        if self.main_window.update_progress_dialog:
            try:
                self.main_window.update_progress_dialog.canceled.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.main_window.update_progress_dialog.setValue(100)
            self.main_window.update_progress_dialog.close()
        self.main_window.set_status_text("Download pembaruan selesai. Menjalankan updater...")
        confirm_run = QMessageBox.question(self.main_window, "Download Selesai", f"Pembaruan telah diunduh ke:\n{sfx_path}\n\nAplikasi akan ditutup untuk menjalankan updater.\nLanjutkan?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
        if confirm_run == QMessageBox.StandardButton.Yes:
            try:
                if sys.platform != "win32": os.chmod(sfx_path, 0o755)
                if sys.platform == "win32": subprocess.Popen([sfx_path], creationflags=subprocess.DETACHED_PROCESS, close_fds=True)
                else: subprocess.Popen([sfx_path])
                QApplication.instance().quit()
            except Exception as e:
                QMessageBox.critical(self.main_window, "Gagal Menjalankan Updater", f"Tidak bisa menjalankan file updater:\n{sfx_path}\n\nError: {str(e)}\n\nSilakan jalankan manual.")
                self.main_window.set_status_text(f"Gagal jalankan updater: {e}")
                try: webbrowser.open(os.path.dirname(sfx_path))
                except Exception: pass
        else:
            self.main_window.set_status_text("Instalasi pembaruan ditunda. File updater ada di folder temporary.")
            QMessageBox.information(self.main_window, "Instalasi Ditunda", f"File updater ada di:\n{sfx_path}\nAnda bisa menjalankannya manual nanti.")

    def handle_update_download_error(self, error_message):
        if self.main_window.update_progress_dialog:
            try:
                self.main_window.update_progress_dialog.canceled.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.main_window.update_progress_dialog.close()
        self.main_window.set_status_text(f"Gagal download update: {error_message}")
        QMessageBox.critical(self.main_window, "Download Gagal", f"Tidak bisa mengunduh pembaruan:\n{error_message}")
