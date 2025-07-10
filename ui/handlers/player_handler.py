from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtMultimedia import QMediaPlayer
from threads.stream_thread import StreamInfoThread
from ui.dialogs.progress_dialogs import OperationProgressDialog
from ui.widgets.players import VideoPlayerWidget, AudioPlayerWidget
from nvda_control import speak as nvda_speak

class PlayerHandler:
    def __init__(self, main_window):
        self.main_window = main_window

    def handle_media_player_error(self, error: QMediaPlayer.Error = QMediaPlayer.Error.NoError):
        if error != QMediaPlayer.Error.NoError:
            if self.main_window.operation_progress_dialog and self.main_window.operation_progress_dialog.isVisible(): self.main_window.operation_progress_dialog.reject(); self.main_window.operation_progress_dialog = None
            QMessageBox.critical(self.main_window, "Kesalahan Media Player", f"Error: {self.main_window.media_player.errorString() or 'Kesalahan tidak diketahui'}")
            self.stop_current_playback()

    def handle_media_player_state_changed(self, state: QMediaPlayer.PlaybackState):
        if self.main_window.operation_progress_dialog and self.main_window.operation_progress_dialog.isVisible() and state in [QMediaPlayer.PlaybackState.PlayingState, QMediaPlayer.PlaybackState.PausedState]:
            self.main_window.operation_progress_dialog.accept()
            self.main_window.operation_progress_dialog = None
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.main_window.set_status_text("Playback berhenti/selesai.")
            self.main_window.update_window_title_status("Siap")
            if self.main_window.stacked_widget.currentWidget() != self.main_window.main_view_widget:
                self.close_player_view()
            self.main_window.set_ui_busy_state(False, operation_type="playback")
        elif state == QMediaPlayer.PlaybackState.PlayingState:
            self.main_window.set_ui_busy_state(True, operation_type="playback")
            title = self.main_window.current_video_title_for_window
            if self.main_window.stacked_widget.currentWidget() == self.main_window.audio_player_widget:
                self.main_window.set_status_text(f"Audio Aktif: {title}")
                self.main_window.update_window_title_status(f"Memutar Audio ({title[:20]}...)")
            elif self.main_window.stacked_widget.currentWidget() == self.main_window.video_player_widget:
                self.main_window.set_status_text(f"Video Aktif: {title}")
                self.main_window.update_window_title_status(f"Memutar Video ({title[:20]}...)")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            title = self.main_window.current_video_title_for_window
            if self.main_window.stacked_widget.currentWidget() == self.main_window.audio_player_widget:
                self.main_window.set_status_text(f"Audio Dijeda: {title}")
                self.main_window.update_window_title_status(f"Audio Dijeda ({title[:20]}...)")
            elif self.main_window.stacked_widget.currentWidget() == self.main_window.video_player_widget:
                self.main_window.set_status_text(f"Video Dijeda: {title}")
                self.main_window.update_window_title_status(f"Video Dijeda ({title[:20]}...)")

    def play_video_from_input_shortcut(self):
        url = self.main_window.main_view_widget.input_line_edit.text().strip()
        if self.main_window.is_likely_direct_video_url(url):
            self.main_window.last_selected_search_item_url = url
            self.request_stream_info_and_play(url, "Video dari Input", True)
        else:
            QMessageBox.warning(self.main_window, "Aksi Tidak Sesuai", "URL video YouTube yang valid diperlukan.")

    def play_audio_from_input_shortcut(self):
        url = self.main_window.main_view_widget.input_line_edit.text().strip()
        if self.main_window.is_likely_direct_video_url(url):
            self.main_window.last_selected_search_item_url = url
            self.request_stream_info_and_play(url, "Audio dari Input", False)
        else:
            QMessageBox.warning(self.main_window, "Aksi Tidak Sesuai", "URL video YouTube yang valid diperlukan.")

    def request_stream_info_and_play(self, page_url, title_hint, play_video):
        self.stop_current_playback()
        self.main_window.stop_active_threads(exclude_stream_info=True)
        self.main_window.current_video_title_for_window = title_hint
        self.main_window.set_status_text(f"Mengambil info stream: {title_hint}...")
        self.main_window.update_window_title_status("Mengambil Info Stream")
        self.main_window.set_ui_busy_state(True, operation_type="playback_loading")
        if self.main_window.operation_progress_dialog: self.main_window.operation_progress_dialog.close()
        self.main_window.operation_progress_dialog = OperationProgressDialog(f"Memuat {('Video' if play_video else 'Audio')}: {title_hint[:30]}...", self.main_window)
        self.main_window.operation_progress_dialog.show()
        if self.main_window.stream_info_thread and self.main_window.stream_info_thread.isRunning():
            self.main_window.stream_info_thread.terminate()
            self.main_window.stream_info_thread.wait()
        self.main_window.stream_info_thread = StreamInfoThread(page_url, title_hint, play_video, self.main_window)
        self.main_window.stream_info_thread.stream_url_ready.connect(self.start_playback_with_stream_url)
        self.main_window.stream_info_thread.stream_error.connect(self.handle_stream_info_error)
        self.main_window.stream_info_thread.finished.connect(self.main_window._on_any_thread_finished)
        self.main_window.stream_info_thread.start()

    def start_playback_with_stream_url(self, stream_url, title, play_video):
        if self.main_window.operation_progress_dialog:
            self.main_window.operation_progress_dialog.accept()
            self.main_window.operation_progress_dialog = None
        if self.main_window.active_search_results_dialog and self.main_window.active_search_results_dialog.isVisible():
            self.main_window.active_search_results_dialog.hide()

        self.main_window.current_video_title_for_window = title
        if play_video:
            self.main_window.media_player.setVideoOutput(self.main_window.video_widget)
            if not self.main_window.video_player_widget:
                self.main_window.video_player_widget = VideoPlayerWidget(self.main_window.media_player, self.main_window.video_widget, self.main_window, settings=self.main_window.settings)
                self.main_window.video_player_widget.close_requested.connect(self.close_player_view)
                self.main_window.video_player_widget.download_requested.connect(self.main_window.download_handler.handle_playback_download_request)
                self.main_window.video_player_widget.playback_rate_change_requested.connect(self.change_playback_rate)
                self.main_window.stacked_widget.addWidget(self.main_window.video_player_widget)
            self.main_window.video_player_widget.update_title(title)
            if self.main_window.original_geometry is None: self.main_window.original_geometry = self.main_window.geometry()
            self.main_window.stacked_widget.setCurrentWidget(self.main_window.video_player_widget)
            self.main_window.showFullScreen()
            self.main_window.video_player_widget.setFocus()
        else:
            self.main_window.media_player.setVideoOutput(None)
            if not self.main_window.audio_player_widget:
                self.main_window.audio_player_widget = AudioPlayerWidget(self.main_window.media_player, self.main_window)
                self.main_window.audio_player_widget.close_requested.connect(self.close_player_view)
                self.main_window.audio_player_widget.download_requested.connect(self.main_window.download_handler.handle_playback_download_request)
                self.main_window.audio_player_widget.playback_rate_change_requested.connect(self.change_playback_rate)
                self.main_window.stacked_widget.addWidget(self.main_window.audio_player_widget)
            self.main_window.audio_player_widget.update_title(title)
            if self.main_window.original_geometry is None: self.main_window.original_geometry = self.main_window.geometry()
            self.main_window.stacked_widget.setCurrentWidget(self.main_window.audio_player_widget)
            self.main_window.showFullScreen()
            self.main_window.audio_player_widget.setFocus()

        self.main_window.media_player.setSource(QUrl(stream_url))
        self.main_window.media_player.setPlaybackRate(self.main_window.settings.get('playback_rate', 1.0))
        self.main_window.media_player.play()

    def change_playback_rate(self, delta):
        if self.main_window.media_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            return

        current_rate = self.main_window.media_player.playbackRate()
        new_rate = round(current_rate + delta, 2)

        new_rate = max(0.25, min(new_rate, 4.0))

        if abs(new_rate - current_rate) > 0.01:
            self.main_window.media_player.setPlaybackRate(new_rate)
            self.main_window.settings['playback_rate'] = new_rate
            self.main_window.save_app_settings(show_error=False)

            rate_text = f"kecepatan pemutar {new_rate:.2f}"
            self.main_window.set_status_text(f"Kecepatan pemutar diatur ke {new_rate:.2f}x")
            nvda_speak(rate_text)

    def handle_stream_info_error(self, error_message):
        if self.main_window.operation_progress_dialog:
            self.main_window.operation_progress_dialog.reject()
            self.main_window.operation_progress_dialog = None
        QMessageBox.critical(self.main_window, "Gagal Memutar", f"Tidak bisa dapat info stream: {error_message}")
        self.main_window.set_status_text("Gagal playback.")
        self.main_window.update_window_title_status("Gagal Playback")

    def stop_current_playback(self):
        if self.main_window.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.main_window.media_player.stop()

    def close_player_view(self):
        self.stop_current_playback()
        self.main_window.stacked_widget.setCurrentWidget(self.main_window.main_view_widget)
        if self.main_window.original_geometry:
            self.main_window.showNormal()
            self.main_window.setGeometry(self.main_window.original_geometry)
            self.main_window.original_geometry = None
        
        # Restore focus
        if self.main_window.search_handler.active_search_results_dialog and not self.main_window.search_handler.active_search_results_dialog.isHidden():
            self.main_window.search_handler.active_search_results_dialog.show()
            self.main_window.search_handler.active_search_results_dialog.activateWindow()
            self.main_window.search_handler.active_search_results_dialog.raise_()
            self.main_window.search_handler.active_search_results_dialog.restore_focus_and_selection(self.main_window.last_selected_search_item_url)
        else:
            QTimer.singleShot(250, self.main_window.main_view_widget.input_line_edit.setFocus)