from PySide6.QtWidgets import QMessageBox
from ui.dialogs.about_dialog import AboutDialog
from ui.dialogs.settings_dialog import SettingsDialog

class DialogHandler:
    def __init__(self, main_window):
        self.main_window = main_window

    def show_about_dialog(self):
        if any((t and t.isRunning()) for t in [self.main_window.download_thread, self.main_window.search_thread, self.main_window.playlist_fetch_thread, self.main_window.channel_fetch_thread, self.main_window.stream_info_thread, self.main_window.update_check_thread, self.main_window.download_update_thread]) or \
           self.main_window.current_list_batch_download_active:
            QMessageBox.information(self.main_window, "Operasi Berjalan", "Tunggu atau hentikan operasi aktif sebelum membuka info aplikasi.")
            return
        dialog = AboutDialog(self.main_window)
        dialog.exec()
        self.main_window.set_status_text("Dialog info aplikasi ditutup.")
        self.main_window.update_window_title_status("Siap")

    def open_settings_dialog(self):
        if any((t and t.isRunning()) for t in [self.main_window.download_thread, self.main_window.search_thread, self.main_window.playlist_fetch_thread, self.main_window.channel_fetch_thread, self.main_window.stream_info_thread, self.main_window.update_check_thread, self.main_window.download_update_thread]) or \
           self.main_window.current_list_batch_download_active:
            QMessageBox.information(self.main_window, "Operasi Berjalan", "Tunggu atau hentikan operasi aktif sebelum buka pengaturan.")
            return

        dialog = SettingsDialog(self.main_window.settings, self.main_window)
        dialog.settings_changed.connect(self.handle_settings_changed)
        dialog.exec()
        self.main_window.update_window_title_status("Siap")

    def handle_settings_changed(self):
        new_settings = self.sender().get_settings()

        if self.main_window.settings.get('theme') != new_settings.get('theme'):
            self.main_window.settings = new_settings
            self.main_window.apply_theme()
        else:
            self.main_window.settings = new_settings
        self.main_window.save_app_settings()
        self.main_window.init_clipboard_monitor()
        self.main_window.set_status_text("Pengaturan disimpan dan diterapkan.")
        if self.main_window.video_player_widget:
            self.main_window.video_player_widget.settings = self.main_window.settings
            self.main_window.video_player_widget.setup_autohide_from_settings()

        if self.main_window.active_search_results_dialog:
            self.main_window.active_search_results_dialog.settings = self.main_window.settings
            self.main_window.active_search_results_dialog.update_button_tooltips()
