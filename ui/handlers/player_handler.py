import shiboken6
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from threads.stream_thread import StreamInfoThread
from ui.dialogs.progress_dialogs import OperationProgressDialog
from ui.widgets.video_player_widget import VideoPlayerWidget
from ui.widgets.audio_player_widget import AudioPlayerWidget
from nvda_control import speak as nvda_speak

class PlayerHandler:
    def __init__(self, main_window):
        self.main_window = main_window
        self.set_audio_output_device()
        self.media_devices = QMediaDevices()
        self.media_devices.audioOutputsChanged.connect(self._handle_default_audio_output_changed)

    def _get_cookie_params(self):
        return {
            'source': self.main_window.settings.get('cookie_source', 'none'),
            'browser': self.main_window.settings.get('cookie_browser', 'chrome'),
            'file': self.main_window.settings.get('cookie_file', '')
        }

    def _handle_default_audio_output_changed(self):
        print("[_handle_default_audio_output_changed] Dipanggil. Memanggil set_audio_output_device untuk re-evaluasi.")
        self.set_audio_output_device()


    def set_audio_output_device(self):
        print("[set_audio_output_device] Dipanggil.")
        device_id = self.main_window.settings.get('audio_output_device_id')
        print(f"[set_audio_output_device] Device ID dari pengaturan: {device_id}")

        was_playing = self.main_window.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        if was_playing:
            self.main_window.media_player.pause() # Pause playback temporarily

        target_device = None
        available_devices = QMediaDevices.audioOutputs()
        print(f"[set_audio_output_device] Perangkat yang tersedia: {[d.description() for d in available_devices]}")

        if device_id == "default" or device_id is None:
            target_device = QMediaDevices.defaultAudioOutput()
            print(f"[set_audio_output_device] Target perangkat (default/None): {target_device.description() if target_device else 'None'}")
        else:
            # Try to find the saved device
            for device in available_devices:
                if device.id() == device_id:
                    target_device = device
                    print(f"[set_audio_output_device] Target perangkat (tersimpan): {target_device.description()}")
                    break
            if not target_device:
                print("[set_audio_output_device] Perangkat tersimpan tidak ditemukan. Mencoba fallback ke default.")
                self.main_window.set_status_text("Perangkat audio tersimpan tidak ditemukan atau tidak valid, mencoba menggunakan default.")
                # Fallback to default if saved device is not found
                target_device = QMediaDevices.defaultAudioOutput()
                self.main_window.settings['audio_output_device_id'] = "default" # Update setting to default
                self.main_window.save_app_settings(show_error=False)

        # Now, attempt to set the target_device and validate it
        if target_device and target_device in available_devices:
            self.main_window.audio_output.setDevice(target_device)
            print(f"[set_audio_output_device] Berhasil mengatur perangkat ke: {target_device.description()}")
            self.main_window.set_status_text(f"Perangkat output audio diubah ke: {target_device.description()}")
        else:
            # If target_device is None or not in available_devices (meaning it's invalid/disconnected)
            # Try to set the current default device as a last resort
            final_fallback_device = QMediaDevices.defaultAudioOutput()
            if final_fallback_device and final_fallback_device in available_devices:
                self.main_window.audio_output.setDevice(final_fallback_device)
                self.main_window.settings['audio_output_device_id'] = "default"
                self.main_window.save_app_settings(show_error=False)
                print(f"[set_audio_output_device] Berhasil fallback ke perangkat default: {final_fallback_device.description()}")
                self.main_window.set_status_text(f"Perangkat audio tersimpan tidak ditemukan atau tidak valid, menggunakan default: {final_fallback_device.description()}.")
            else:
                print("[set_audio_output_device] Tidak dapat menemukan perangkat audio yang valid, bahkan perangkat default.")
                self.main_window.set_status_text("Tidak dapat menemukan perangkat audio yang valid, bahkan perangkat default.")
        
        if was_playing:
            self.main_window.media_player.play() # Resume playback

    def handle_media_player_error(self, error: QMediaPlayer.Error = QMediaPlayer.Error.NoError):
        if error != QMediaPlayer.Error.NoError:
            if self.main_window.operation_progress_dialog and self.main_window.operation_progress_dialog.isVisible():
                self.main_window.operation_progress_dialog.reject()
                self.main_window.operation_progress_dialog = None
            QMessageBox.critical(self.main_window, "Kesalahan Media Player", f"Error: {self.main_window.media_player.errorString() or 'Kesalahan tidak diketahui'}")
            self.stop_current_playback()

    def handle_media_player_state_changed(self, state: QMediaPlayer.PlaybackState):
        if self.main_window.operation_progress_dialog and self.main_window.operation_progress_dialog.isVisible() and state in [QMediaPlayer.PlaybackState.PlayingState, QMediaPlayer.PlaybackState.PausedState]:
            self.main_window.operation_progress_dialog.accept()
            self.main_window.operation_progress_dialog = None
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.main_window.set_status_text("Playback berhenti/selesai.")
            self.main_window.update_window_title_status("Siap")
            
            # Auto-play next logic
            should_autoplay = self.main_window.settings.get('auto_play_next', True)
            media_status = self.main_window.media_player.mediaStatus()
            
            # Check if media finished (EndOfMedia) OR if it stopped at the end (LoadedMedia with position at duration)
            # Sometimes Qt reports LoadedMedia instead of EndOfMedia when stopped manually or naturally
            is_at_end = (media_status == QMediaPlayer.MediaStatus.EndOfMedia)
            if not is_at_end and media_status == QMediaPlayer.MediaStatus.LoadedMedia:
                if self.main_window.media_player.position() > 0 and \
                   self.main_window.media_player.position() >= self.main_window.media_player.duration() - 1000: # tolerance 1s
                    is_at_end = True

            if should_autoplay and is_at_end:
                 if self._try_play_next_item():
                     return

            if self.main_window.tab_widget.currentWidget() != self.main_window.main_view_widget:
                self.close_player_view()
            self.main_window.set_ui_busy_state(False, operation_type="playback")
        elif state == QMediaPlayer.PlaybackState.PlayingState:
            self.main_window.set_ui_busy_state(True, operation_type="playback")
            title = self.main_window.current_video_title_for_window
            if self.main_window.tab_widget.currentWidget() == self.main_window.audio_player_widget:
                self.main_window.set_status_text(f"Audio Aktif: {title}")
                self.main_window.update_window_title_status(f"Memutar Audio ({title[:20]}...)")
            elif self.main_window.tab_widget.currentWidget() == self.main_window.video_player_widget:
                self.main_window.set_status_text(f"Video Aktif: {title}")
                self.main_window.update_window_title_status(f"Memutar Video ({title[:20]}...)")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            title = self.main_window.current_video_title_for_window
            if self.main_window.tab_widget.currentWidget() == self.main_window.audio_player_widget:
                self.main_window.set_status_text(f"Audio Dijeda: {title}")
                self.main_window.update_window_title_status(f"Audio Dijeda ({title[:20]}...)")
            elif self.main_window.tab_widget.currentWidget() == self.main_window.video_player_widget:
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
        if self.main_window.operation_progress_dialog:
            self.main_window.operation_progress_dialog.close()
        self.main_window.operation_progress_dialog = OperationProgressDialog(f"Memuat {('Video' if play_video else 'Audio')}: {title_hint[:30]}...", self.main_window)
        self.main_window.operation_progress_dialog.show()
        if self.main_window.stream_info_thread and self.main_window.stream_info_thread.isRunning():
            self.main_window.stream_info_thread.terminate()
            self.main_window.stream_info_thread.wait()
            
        cookie_params = self._get_cookie_params()
        self.main_window.stream_info_thread = StreamInfoThread(page_url, title_hint, play_video, cookie_params, self.main_window)
        self.main_window.stream_info_thread.stream_url_ready.connect(self.start_playback_with_stream_url)
        self.main_window.stream_info_thread.stream_error.connect(self.handle_stream_info_error)
        self.main_window.stream_info_thread.finished.connect(self.main_window._on_any_thread_finished)
        self.main_window.stream_info_thread.start()

    def start_playback_with_stream_url(self, stream_url, title, play_video):
        if self.main_window.operation_progress_dialog:
            self.main_window.operation_progress_dialog.accept()
            self.main_window.operation_progress_dialog = None
        if self.main_window.search_handler.active_search_results_dialog and self.main_window.search_handler.active_search_results_dialog.isVisible():
            self.main_window.search_handler.active_search_results_dialog.hide()

        self.main_window.current_video_title_for_window = title
        if play_video:
            need_new_video_widget = (
                self.main_window.video_widget is None
                or not shiboken6.isValid(self.main_window.video_widget)
            )
            if need_new_video_widget:
                self.main_window.video_widget = QVideoWidget()
            self.main_window.media_player.setVideoOutput(self.main_window.video_widget)
            if not self.main_window.video_player_widget:
                self.main_window.video_player_widget = VideoPlayerWidget(self.main_window.media_player, self.main_window.video_widget, self.main_window, settings=self.main_window.settings)
                self.main_window.video_player_widget.close_requested.connect(self.close_player_view)
                self.main_window.video_player_widget.download_requested.connect(self.main_window.download_handler.handle_playback_download_request)
                self.main_window.video_player_widget.playback_rate_change_requested.connect(self.change_playback_rate)
                self.main_window.tab_widget.addTab(self.main_window.video_player_widget, "Video Player")
            self.main_window.video_player_widget.update_title(title)
            if self.main_window.original_geometry is None:
                self.main_window.original_geometry = self.main_window.geometry()
            self.main_window.tab_widget.setCurrentWidget(self.main_window.video_player_widget)
            self.main_window.menuBar().hide()
            self.main_window.tab_widget.tabBar().hide()
            self.main_window.showFullScreen()
            self.main_window.video_player_widget.setFocus()
        else:
            self.main_window.media_player.setVideoOutput(None)
            if not self.main_window.audio_player_widget:
                self.main_window.audio_player_widget = AudioPlayerWidget(self.main_window.media_player, self.main_window)
                self.main_window.audio_player_widget.close_requested.connect(self.close_player_view)
                self.main_window.audio_player_widget.download_requested.connect(self.main_window.download_handler.handle_playback_download_request)
                self.main_window.audio_player_widget.playback_rate_change_requested.connect(self.change_playback_rate)
                self.main_window.tab_widget.addTab(self.main_window.audio_player_widget, "Audio Player")
            self.main_window.audio_player_widget.update_title(title)
            if self.main_window.original_geometry is None:
                self.main_window.original_geometry = self.main_window.geometry()
            self.main_window.tab_widget.setCurrentWidget(self.main_window.audio_player_widget)
            self.main_window.menuBar().hide()
            self.main_window.tab_widget.tabBar().hide()
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
        self.main_window.media_player.setVideoOutput(None)
        self.main_window.tab_widget.setCurrentWidget(self.main_window.main_view_widget)
        self.main_window.menuBar().show()
        self.main_window.tab_widget.tabBar().show()
        if self.main_window.original_geometry:
            self.main_window.showNormal()
            self.main_window.setGeometry(self.main_window.original_geometry)
            self.main_window.original_geometry = None
        
        # Restore focus
        QTimer.singleShot(250, self.main_window.events.restore_proper_focus)

        # Remove player tabs and clear references
        if self.main_window.video_player_widget:
            idx = self.main_window.tab_widget.indexOf(self.main_window.video_player_widget)
            if idx != -1:
                self.main_window.tab_widget.removeTab(idx)
            self.main_window.video_player_widget.deleteLater()
            self.main_window.video_player_widget = None
            self.main_window.video_widget = None
        
        if self.main_window.audio_player_widget:
            idx = self.main_window.tab_widget.indexOf(self.main_window.audio_player_widget)
            if idx != -1:
                self.main_window.tab_widget.removeTab(idx)
            self.main_window.audio_player_widget.deleteLater()
            self.main_window.audio_player_widget = None

    def _try_play_next_item(self):
        """Mencoba memutar item selanjutnya dari daftar hasil pencarian."""
        current_url = self.main_window.last_selected_search_item_url
        if not current_url:
            return False
            
        results = self.main_window.search_results
        if not results:
            return False

        current_index = -1
        for i, item in enumerate(results):
            if item.get('url') == current_url:
                current_index = i
                break
        
        if current_index != -1 and current_index + 1 < len(results):
            next_item = results[current_index + 1]
            next_url = next_item.get('url')
            next_title = next_item.get('title', 'Video Berikutnya')
            
            # Determine play type (video/audio) based on current active widget
            is_video_mode = (self.main_window.tab_widget.currentWidget() == self.main_window.video_player_widget)
            
            self.main_window.last_selected_search_item_url = next_url
            self.request_stream_info_and_play(next_url, next_title, is_video_mode)
            
            msg = f"Memutar otomatis selanjutnya: {next_title}"
            self.main_window.set_status_text(msg)
            nvda_speak(msg)
            return True
            
        return False
