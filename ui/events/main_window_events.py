import os
import sys
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QGridLayout, QPushButton, QDialogButtonBox, QLineEdit, QTextEdit, QListWidget, QSpinBox, QComboBox
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QKeyEvent

from threads.update_thread import UpdateCheckThread, DownloadUpdateThread
from threads.stream_thread import StreamInfoThread
from threads.search_thread import SearchThread, PlaylistFetchThread, ChannelFetchThread

from utils import constants

class MainWindowEvents:
    def __init__(self, main_window):
        self.main_window = main_window

    def _update_placeholder_text(self, text):
        self.main_window.main_view_widget.url_input_label.setText(f"URL / Kata Kunci {text}:")
        self.main_window.main_view_widget.input_line_edit.setPlaceholderText(f"Masukkan URL atau kata kunci {text.lower()}")

    def keyPressEvent(self, event: QKeyEvent):
        if self.main_window.tab_widget.currentWidget() != self.main_window.main_view_widget:
            super(self.main_window.__class__, self.main_window).keyPressEvent(event)
            return
        current_focus = QApplication.focusWidget()
        key_text = event.text()
        
        is_input_like_widget = isinstance(current_focus, (QLineEdit, QTextEdit, QListWidget, QSpinBox, QComboBox))
        has_modifier = event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)
        if key_text and key_text.isprintable() and not has_modifier and not is_input_like_widget:
            if self.main_window.main_view_widget.input_line_edit.isEnabled():
                self.main_window.main_view_widget.input_line_edit.setFocus()
                self.main_window.main_view_widget.input_line_edit.setText(key_text)
                self.main_window.main_view_widget.input_line_edit.end(False)
        else:
            super(self.main_window.__class__, self.main_window).keyPressEvent(event)

    def init_clipboard_monitor(self):
        if not hasattr(self.main_window, 'clipboard_timer'):
            self.main_window.clipboard_timer = QTimer(self.main_window)
            self.main_window.clipboard_timer.setInterval(2000)
            self.main_window.clipboard_timer.timeout.connect(self.check_clipboard)
        if self.main_window.settings.get('monitor_clipboard', True):
            if not self.main_window.clipboard_timer.isActive():
                self.main_window.clipboard_timer.start()
        else:
            if self.main_window.clipboard_timer.isActive():
                self.main_window.clipboard_timer.stop()

    def check_clipboard(self):
        if QApplication.activeModalWidget() is not None:
            return
        clipboard = QApplication.clipboard()
        current_text = clipboard.text().strip()
        if not current_text or current_text == self.main_window.last_clipboard_text:
            return
        self.main_window.last_clipboard_text = current_text
        if self.main_window.is_valid_youtube_url(current_text) and not self.main_window.is_youtube_channel_url(current_text):
             if self.main_window.is_valid_youtube_video_url(current_text) or self.main_window.is_potential_playlist_url(current_text):
                self.main_window.activateWindow()
                self.main_window.handle_direct_video_url_dialog(current_text)

    def clear_input_field(self):
        self.main_window.main_view_widget.input_line_edit.clear()
        self.main_window.set_status_text("Input field dibersihkan.")
        self.main_window.main_view_widget.input_line_edit.setFocus()

    def paste_and_process_input(self):
        clipboard = QApplication.clipboard()
        clipboard_text = clipboard.text()
        if clipboard_text:
            self.main_window.main_view_widget.input_line_edit.setText(clipboard_text)
            self.main_window.set_status_text(f"Teks dari clipboard ditempel: {clipboard_text[:50]}...")
            self.main_window.search_handler.process_input()
        else:
            QMessageBox.information(self.main_window, "Clipboard Kosong", "Tidak ada teks di clipboard untuk ditempel.")
            self.main_window.set_status_text("Clipboard kosong.")

    

    def stop_current_operation(self, confirm=True):
        stopped_something = False
        if self.main_window.media_player.playbackState() != self.main_window.media_player.PlaybackState.StoppedState:
            if not confirm or QMessageBox.question(self.main_window, "Hentikan Playback?", "Yakin hentikan playback saat ini?") == QMessageBox.StandardButton.Yes:
                self.main_window.player_handler.close_player_view()
                stopped_something = True
        if self.main_window.download_thread and self.main_window.download_thread.isRunning():
            self.main_window.download_handler.handle_download_cancellation_request()
            stopped_something = True
        other_threads_info = [
            (self.main_window.search_thread, "Pencarian", self.main_window.search_handler.handle_search_error),
            (self.main_window.playlist_fetch_thread, "Pemuatan Playlist", self.main_window.search_handler.handle_list_fetch_error),
            (self.main_window.channel_fetch_thread, "Pemuatan Channel", self.main_window.search_handler.handle_list_fetch_error),
            (self.main_window.stream_info_thread, "Pengambilan Info Stream", self.main_window.player_handler.handle_stream_info_error),
            (self.main_window.update_check_thread, "Pengecekan Pembaruan", self.main_window.handle_update_check_error),
        ]
        for thread, name, error_handler in other_threads_info:
            if thread and thread.isRunning():
                if not confirm or QMessageBox.question(self.main_window, f"Hentikan {name}?", f"Yakin hentikan proses {name.lower()}?") == QMessageBox.StandardButton.Yes:
                    thread.quit()
                    thread.wait(500)
                    if thread.isRunning():
                        thread.terminate()
                        thread.wait(100)
                    if error_handler:
                        error_handler(f"{name} dihentikan pengguna.")
                    stopped_something = True
                    break
        if self.main_window.download_update_thread and self.main_window.download_update_thread.isRunning():
            if not confirm or QMessageBox.question(self.main_window, "Hentikan Download Update?", "Yakin hentikan download pembaruan?") == QMessageBox.StandardButton.Yes:
                self.main_window.cancel_update_download()
                stopped_something = True
        if not stopped_something and confirm:
            self.main_window.set_status_text("Tidak ada operasi aktif yang bisa dihentikan saat ini.")
        QTimer.singleShot(100, lambda: self.main_window.set_ui_busy_state(False, "stop_operation_attempted"))

    def _on_any_thread_finished(self):
        sender = self.main_window.sender()
        if sender == self.main_window.download_thread:
            if self.main_window.download_progress_dialog and self.main_window.download_progress_dialog.isVisible():
                self.main_window.download_progress_dialog.accept()
                self.main_window.download_progress_dialog = None
            self.main_window.download_thread = None
            self.main_window.current_list_batch_download_active = False
            if not "Selesai" in self.main_window.main_view_widget.status_label.text() and not "Gagal" in self.main_window.main_view_widget.status_label.text() and not "Batch" in self.main_window.main_view_widget.status_label.text():
                 self.main_window.set_status_text("Operasi unduhan telah selesai atau dihentikan.")
            QTimer.singleShot(150, self.restore_focus_after_download)
        elif sender == self.main_window.search_thread:
            self.main_window.search_thread = None
        elif sender == self.main_window.playlist_fetch_thread:
            self.main_window.playlist_fetch_thread = None
        elif sender == self.main_window.channel_fetch_thread:
            self.main_window.channel_fetch_thread = None
        elif sender == self.main_window.stream_info_thread:
            self.main_window.stream_info_thread = None
        elif sender == self.main_window.update_check_thread:
            self.main_window.update_check_thread = None
            if self.main_window._is_initial_startup_check:
                if not QApplication.activeModalWidget():
                    self.main_window.main_view_widget.input_line_edit.setFocus()
                self.main_window._is_initial_startup_check = False
        elif sender == self.main_window.download_update_thread:
            self.main_window.download_update_thread = None
        
        if self.main_window.operation_progress_dialog and self.main_window.operation_progress_dialog.isVisible():
            if isinstance(sender, (SearchThread, PlaylistFetchThread, ChannelFetchThread, StreamInfoThread)):
                 self.main_window.operation_progress_dialog.accept()
                 self.main_window.operation_progress_dialog = None
                 
        self.main_window.set_ui_busy_state(False, "thread_finished")
        if not (self.main_window.active_search_results_dialog and self.main_window.active_search_results_dialog.isVisible()):
             self.main_window.update_window_title_status("Siap")
        
    def restore_focus_after_download(self):
        url_to_focus = None
        if self.main_window.download_initiated_from_search_dialog:
            url_to_focus = self.main_window.last_downloaded_item_info.get('url') if self.main_window.last_downloaded_item_info else None
            self.main_window.download_initiated_from_search_dialog = False
        self.restore_proper_focus(item_url_to_focus=url_to_focus)

    def restore_proper_focus(self, item_url_to_focus=None):
        if self.main_window.search_handler.active_search_results_dialog:
            self.main_window.search_handler.active_search_results_dialog.show()
            self.main_window.search_handler.active_search_results_dialog.activateWindow()
            self.main_window.search_handler.active_search_results_dialog.raise_()
            if item_url_to_focus:
                self.main_window.search_handler.active_search_results_dialog.restore_focus_and_selection(item_url_to_focus)
            else:
                self.main_window.search_handler.active_search_results_dialog.setFocus()
        else:
            QTimer.singleShot(250, self.main_window.main_view_widget.input_line_edit.setFocus)

    def closeEvent(self, event):
        if self.main_window._is_closing_app:
            event.accept()
            return
        self.main_window._is_closing_app = True
        self.main_window.set_status_text("Menutup aplikasi, membersihkan...")
        event.ignore()
        QTimer.singleShot(100, self._finalize_close)

    def _finalize_close(self):
        all_threads = [self.main_window.search_thread, self.main_window.playlist_fetch_thread, self.main_window.channel_fetch_thread, self.main_window.stream_info_thread,
                       self.main_window.download_thread, self.main_window.update_check_thread, self.main_window.download_update_thread]
        for thread in all_threads:
             if thread and thread.isRunning():
                 if hasattr(thread, 'stop'):
                     thread.stop()
                 thread.quit()
                 if not thread.wait(300):
                     thread.terminate()
                     thread.wait(100)
        self.main_window.save_app_settings()
        self.main_window.close()
