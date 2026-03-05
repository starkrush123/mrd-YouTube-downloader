import shiboken6
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from threads.stream_thread import StreamInfoThread
from threads.related_thread import RelatedTracksThread
from ui.dialogs.progress_dialogs import OperationProgressDialog
from ui.widgets.video_player_widget import VideoPlayerWidget
from ui.widgets.audio_player_widget import AudioPlayerWidget
from nvda_control import speak as nvda_speak
from utils.helpers import dprint

class PlayerHandler:
    def __init__(self, main_window):
        self.main_window = main_window
        self._suppress_autoplay_once = False
        self._current_stream_url = ""
        self._current_play_mode_video = False
        self._stream_recovery_attempts = 0
        self._max_stream_recovery_attempts = 3
        self._recovery_in_progress = False
        self._recovery_expected_progress_from = 0
        self._watchdog_last_position = 0
        self._watchdog_stall_ticks = 0
        self._watchdog_timer = QTimer(self.main_window)
        self._watchdog_timer.setInterval(2000)
        self._watchdog_timer.timeout.connect(self._playback_watchdog_tick)
        self.set_audio_output_device()
        self.media_devices = QMediaDevices()
        self.media_devices.audioOutputsChanged.connect(self._handle_default_audio_output_changed)

    def _get_cookie_params(self):
        return {
            'source': self.main_window.settings.get('cookie_source', 'none'),
            'browser': self.main_window.settings.get('cookie_browser', 'chrome'),
            'file': self.main_window.settings.get('cookie_file', '')
        }

    def _is_youtube_url(self, url):
        low = (url or "").lower()
        return "youtube.com" in low or "youtu.be" in low

    def _ensure_playback_seed(self, page_url, title_hint):
        existing_urls = {item.get("url") for item in self.main_window.search_results if isinstance(item, dict)}
        if page_url not in existing_urls:
            self.main_window.search_results = [
                {
                    "_type": "video",
                    "url": page_url,
                    "webpage_url": page_url,
                    "title": title_hint or _("Video"),
                }
            ]
            self.main_window.related_seed_url = None
            self.main_window.current_results_context = "direct"

    def _should_use_related_autoplay(self, page_url):
        if not self.main_window.settings.get("auto_play_next", True):
            return False
        if not self.main_window.settings.get("smart_autoplay_related", True):
            return False
        if not self._is_youtube_url(page_url):
            return False
        return self.main_window.current_results_context not in (
            "playlist_items",
            "channel_items",
        )

    def _start_related_fetch(self, page_url, title_hint):
        if not self._should_use_related_autoplay(page_url):
            return
        if self.main_window.is_fetching_related:
            return
        if self.main_window.related_seed_url == page_url and len(self.main_window.search_results) > 1:
            return

        self.main_window.is_fetching_related = True
        self.main_window.related_seed_url = page_url

        if self.main_window.related_fetch_thread and self.main_window.related_fetch_thread.isRunning():
            self.main_window.related_fetch_thread.quit()
            self.main_window.related_fetch_thread.wait(500)

        related_limit = self.main_window.settings.get("smart_autoplay_related_limit", 50)
        try:
            related_limit = max(5, min(150, int(related_limit)))
        except Exception:
            related_limit = 50

        cookie_params = self._get_cookie_params()
        self.main_window.related_fetch_thread = RelatedTracksThread(
            page_url, cookie_params=cookie_params, limit=related_limit, parent=self.main_window
        )
        self.main_window.related_fetch_thread.related_ready.connect(
            lambda items, src=page_url, hint=title_hint: self._handle_related_ready(items, src, hint)
        )
        self.main_window.related_fetch_thread.related_error.connect(
            lambda err, src=page_url: self._handle_related_error(err, src)
        )
        self.main_window.related_fetch_thread.finished.connect(self.main_window._on_any_thread_finished)
        self.main_window.related_fetch_thread.start()

    def _handle_related_ready(self, related_items, source_url, title_hint):
        self.main_window.is_fetching_related = False
        if source_url != self.main_window.related_seed_url:
            return
        if not related_items:
            return

        existing_urls = {
            item.get("url")
            for item in self.main_window.search_results
            if isinstance(item, dict) and item.get("url")
        }
        items_to_insert = []
        for item in related_items:
            item_url = item.get("url")
            if not item_url or item_url in existing_urls:
                continue
            item["_autoplay_related"] = True
            items_to_insert.append(item)
            existing_urls.add(item_url)
        if not items_to_insert:
            return

        insert_at = len(self.main_window.search_results)
        current_url = self.main_window.last_selected_search_item_url
        for idx, item in enumerate(self.main_window.search_results):
            if isinstance(item, dict) and item.get("url") == current_url:
                insert_at = idx + 1
                break

        self.main_window.search_results[insert_at:insert_at] = items_to_insert
        appended = len(items_to_insert)

        if appended > 0:
            base_title = title_hint or _("Video")
            self.main_window.set_status_text(
                _("Autoplay pintar aktif: ditambahkan {count} lagu relevan dari '{title}'.").format(
                    count=appended, title=base_title
                )
            )

    def _handle_related_error(self, error_message, source_url):
        self.main_window.is_fetching_related = False
        if source_url == self.main_window.related_seed_url:
            dprint(f"[related-fetch] failed: {error_message}")

    def _retry_autoplay_if_waiting_related(self):
        if not self.main_window.settings.get('auto_play_next', True):
            return
        if self.main_window.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            return
        if self._try_play_next_item():
            return
        if not self.main_window.is_fetching_related:
            if self.main_window.tab_widget.currentWidget() != self.main_window.main_view_widget:
                self.close_player_view()
            self.main_window.set_ui_busy_state(False, operation_type="playback")

    def _can_attempt_stream_recovery(self):
        return bool(self._current_stream_url) and not self._recovery_in_progress

    def _extract_video_id(self, url):
        if not url:
            return None
        u = str(url)
        if "v=" in u:
            try:
                return u.split("v=", 1)[1].split("&", 1)[0]
            except Exception:
                return None
        if "youtu.be/" in u:
            try:
                return u.split("youtu.be/", 1)[1].split("?", 1)[0].split("/", 1)[0]
            except Exception:
                return None
        if "/shorts/" in u:
            try:
                return u.split("/shorts/", 1)[1].split("?", 1)[0].split("/", 1)[0]
            except Exception:
                return None
        return None

    def _attempt_stream_recovery(self, reason="network"):
        if not self._can_attempt_stream_recovery():
            return False
        if self._stream_recovery_attempts >= self._max_stream_recovery_attempts:
            return False
        self._stream_recovery_attempts += 1
        self._recovery_in_progress = True
        current_pos = max(0, int(self.main_window.media_player.position()))
        self._recovery_expected_progress_from = current_pos
        resume_pos = max(0, current_pos - 2000)
        dprint(
            f"[Recovery] Attempt {self._stream_recovery_attempts}/{self._max_stream_recovery_attempts}, "
            f"reason={reason}, pos={current_pos}"
        )
        self.main_window.set_status_text(
            _("Koneksi stream terganggu. Mencoba menyambung ulang ({attempt}/{total})...").format(
                attempt=self._stream_recovery_attempts, total=self._max_stream_recovery_attempts
            )
        )
        self._suppress_autoplay_once = True
        self.main_window.media_player.stop()
        self.main_window.media_player.setSource(QUrl(self._current_stream_url))
        self.main_window.media_player.play()

        def _resume_after_reopen():
            if self.main_window.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                if resume_pos > 0:
                    self.main_window.media_player.setPosition(resume_pos)
            self._recovery_in_progress = False

        QTimer.singleShot(1200, _resume_after_reopen)
        QTimer.singleShot(3200, lambda a=self._stream_recovery_attempts: self._post_recovery_check(a))
        return True

    def _post_recovery_check(self, expected_attempt):
        if expected_attempt != self._stream_recovery_attempts:
            return
        state = self.main_window.media_player.playbackState()
        current_pos = max(0, int(self.main_window.media_player.position()))
        progressed = current_pos >= (self._recovery_expected_progress_from + 500)
        if state in (
            QMediaPlayer.PlaybackState.PlayingState,
            QMediaPlayer.PlaybackState.PausedState,
        ) and progressed:
            return
        self._recovery_in_progress = False
        if self._stream_recovery_attempts < self._max_stream_recovery_attempts:
            if self._attempt_stream_recovery(reason="post-check"):
                return

        # Recovery exhausted: failover to autoplay queue so playback does not hang.
        if self.main_window.settings.get("auto_play_next", True):
            self.main_window.set_status_text(
                _("Stream gagal dipulihkan. Melanjutkan ke item berikutnya...")
            )
            if self._try_play_next_item():
                return
            if self.main_window.is_fetching_related:
                self.main_window.set_status_text(_("Menunggu rekomendasi lagu berikutnya..."))
                QTimer.singleShot(1500, self._retry_autoplay_if_waiting_related)

    def _playback_watchdog_tick(self):
        state = self.main_window.media_player.playbackState()
        if state != QMediaPlayer.PlaybackState.PlayingState:
            self._watchdog_stall_ticks = 0
            return

        current_pos = max(0, int(self.main_window.media_player.position()))
        status = self.main_window.media_player.mediaStatus()
        progressed = current_pos > (self._watchdog_last_position + 250)
        self._watchdog_last_position = current_pos

        if progressed:
            self._watchdog_stall_ticks = 0
            return

        if status in (QMediaPlayer.MediaStatus.StalledMedia, QMediaPlayer.MediaStatus.BufferingMedia):
            self._watchdog_stall_ticks += 1
        else:
            # Tetap hitung freeze walau status tidak stalled, untuk kasus demux hang.
            self._watchdog_stall_ticks += 1

        if self._watchdog_stall_ticks < 3:
            return

        self._watchdog_stall_ticks = 0
        if self._attempt_stream_recovery(reason="watchdog-stall"):
            return
        if self.main_window.settings.get("auto_play_next", True):
            if self._try_play_next_item():
                return
            if self.main_window.is_fetching_related:
                self.main_window.set_status_text(_("Menunggu rekomendasi lagu berikutnya..."))
                QTimer.singleShot(1500, self._retry_autoplay_if_waiting_related)

    def _handle_stall_check(self, expected_position):
        if self.main_window.media_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            return
        current_pos = self.main_window.media_player.position()
        status = self.main_window.media_player.mediaStatus()
        if status == QMediaPlayer.MediaStatus.StalledMedia and current_pos <= expected_position + 300:
            self._attempt_stream_recovery(reason="stalled")

    def _handle_default_audio_output_changed(self):
        dprint("[_handle_default_audio_output_changed] Dipanggil. Memanggil set_audio_output_device untuk re-evaluasi.")
        self.set_audio_output_device()


    def set_audio_output_device(self):
        dprint("[set_audio_output_device] Dipanggil.")
        device_id = self.main_window.settings.get('audio_output_device_id')
        dprint(f"[set_audio_output_device] Device ID dari pengaturan: {device_id}")

        was_playing = self.main_window.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        if was_playing:
            self.main_window.media_player.pause() # Pause playback temporarily

        target_device = None
        available_devices = QMediaDevices.audioOutputs()
        dprint(f"[set_audio_output_device] Perangkat yang tersedia: {[d.description() for d in available_devices]}")

        if device_id == "default" or device_id is None:
            target_device = QMediaDevices.defaultAudioOutput()
            dprint(f"[set_audio_output_device] Target perangkat (default/None): {target_device.description() if target_device else 'None'}")
        else:
            # Try to find the saved device
            for device in available_devices:
                if device.id() == device_id:
                    target_device = device
                    dprint(f"[set_audio_output_device] Target perangkat (tersimpan): {target_device.description()}")
                    break
            if not target_device:
                dprint("[set_audio_output_device] Perangkat tersimpan tidak ditemukan. Mencoba fallback ke default.")
                self.main_window.set_status_text(_("Perangkat audio tersimpan tidak ditemukan atau tidak valid, mencoba menggunakan default."))
                # Fallback to default if saved device is not found
                target_device = QMediaDevices.defaultAudioOutput()
                self.main_window.settings['audio_output_device_id'] = "default" # Update setting to default
                self.main_window.save_app_settings(show_error=False)

        # Now, attempt to set the target_device and validate it
        if target_device and target_device in available_devices:
            self.main_window.audio_output.setDevice(target_device)
            dprint(f"[set_audio_output_device] Berhasil mengatur perangkat ke: {target_device.description()}")
            self.main_window.set_status_text(
                _("Perangkat output audio diubah ke: {device}").format(device=target_device.description())
            )
        else:
            # If target_device is None or not in available_devices (meaning it's invalid/disconnected)
            # Try to set the current default device as a last resort
            final_fallback_device = QMediaDevices.defaultAudioOutput()
            if final_fallback_device and final_fallback_device in available_devices:
                self.main_window.audio_output.setDevice(final_fallback_device)
                self.main_window.settings['audio_output_device_id'] = "default"
                self.main_window.save_app_settings(show_error=False)
                dprint(f"[set_audio_output_device] Berhasil fallback ke perangkat default: {final_fallback_device.description()}")
                self.main_window.set_status_text(
                    _("Perangkat audio tersimpan tidak ditemukan atau tidak valid, menggunakan default: {device}.").format(
                        device=final_fallback_device.description()
                    )
                )
            else:
                dprint("[set_audio_output_device] Tidak dapat menemukan perangkat audio yang valid, bahkan perangkat default.")
                self.main_window.set_status_text(_("Tidak dapat menemukan perangkat audio yang valid, bahkan perangkat default."))
        
        if was_playing:
            self.main_window.media_player.play() # Resume playback

    def handle_media_player_error(self, error: QMediaPlayer.Error = QMediaPlayer.Error.NoError):
        if error != QMediaPlayer.Error.NoError:
            if error in (
                QMediaPlayer.Error.ResourceError,
                QMediaPlayer.Error.NetworkError,
                QMediaPlayer.Error.FormatError,
            ):
                if self._attempt_stream_recovery(reason=f"error:{int(error)}"):
                    return
                if self.main_window.settings.get("auto_play_next", True):
                    if self._try_play_next_item():
                        return
                    if self.main_window.is_fetching_related:
                        self.main_window.set_status_text(_("Menunggu rekomendasi lagu berikutnya..."))
                        QTimer.singleShot(1500, self._retry_autoplay_if_waiting_related)
                        return
            if self.main_window.operation_progress_dialog and self.main_window.operation_progress_dialog.isVisible():
                self.main_window.operation_progress_dialog.reject()
                self.main_window.operation_progress_dialog = None
            QMessageBox.critical(self.main_window, _("Kesalahan Media Player"), f"{_('Error')}: {self.main_window.media_player.errorString() or _('Kesalahan tidak diketahui')}")
            self.stop_current_playback()

    def handle_media_player_status_changed(self, status: QMediaPlayer.MediaStatus):
        if status == QMediaPlayer.MediaStatus.StalledMedia:
            pos_snapshot = self.main_window.media_player.position()
            QTimer.singleShot(1800, lambda p=pos_snapshot: self._handle_stall_check(p))
        elif status in (
            QMediaPlayer.MediaStatus.BufferedMedia,
            QMediaPlayer.MediaStatus.BufferingMedia,
            QMediaPlayer.MediaStatus.LoadedMedia,
        ):
            # Playback sehat lagi, reset counter supaya recovery tetap tersedia jika drop berikutnya.
            self._stream_recovery_attempts = 0

    def handle_media_player_state_changed(self, state: QMediaPlayer.PlaybackState):
        if self.main_window.operation_progress_dialog and self.main_window.operation_progress_dialog.isVisible() and state in [QMediaPlayer.PlaybackState.PlayingState, QMediaPlayer.PlaybackState.PausedState]:
            self.main_window.operation_progress_dialog.accept()
            self.main_window.operation_progress_dialog = None
        if state == QMediaPlayer.PlaybackState.StoppedState:
            if self._watchdog_timer.isActive():
                self._watchdog_timer.stop()
            if self._suppress_autoplay_once:
                self._suppress_autoplay_once = False
                return

            self.main_window.set_status_text(_("Playback berhenti/selesai."))
            self.main_window.update_window_title_status(_("Siap"))
            
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

            dprint(f"[AutoPlay] Stopped. Status: {media_status}, AtEnd: {is_at_end}, AutoPlaySetting: {should_autoplay}")

            if should_autoplay and is_at_end:
                 dprint("[AutoPlay] Condition met. Attempting next item.")
                 if self._try_play_next_item():
                     return
                 else:
                     if self.main_window.is_fetching_related:
                         self.main_window.set_status_text(_("Menunggu rekomendasi lagu berikutnya..."))
                         QTimer.singleShot(1500, self._retry_autoplay_if_waiting_related)
                         return
                     dprint("[AutoPlay] No next item found.")
            elif should_autoplay and self.main_window.media_player.position() > 0:
                # Failover: jika stream berhenti karena jaringan/buffering, coba lanjut ke item berikutnya.
                dprint(f"[AutoPlay] Non-end stop detected (status={media_status}). Trying failover next item.")
                if self._try_play_next_item():
                    return
                if self.main_window.is_fetching_related:
                    self.main_window.set_status_text(_("Menunggu rekomendasi lagu berikutnya..."))
                    QTimer.singleShot(1500, self._retry_autoplay_if_waiting_related)
                    return

            if self.main_window.tab_widget.currentWidget() != self.main_window.main_view_widget:
                self.close_player_view()
            self.main_window.set_ui_busy_state(False, operation_type="playback")
        elif state == QMediaPlayer.PlaybackState.PlayingState:
            self._watchdog_last_position = max(0, int(self.main_window.media_player.position()))
            self._watchdog_stall_ticks = 0
            if not self._watchdog_timer.isActive():
                self._watchdog_timer.start()
            self.main_window.set_ui_busy_state(True, operation_type="playback")
            title = self.main_window.current_video_title_for_window
            if self.main_window.tab_widget.currentWidget() == self.main_window.audio_player_widget:
                self.main_window.set_status_text(_("Audio Aktif: {title}").format(title=title))
                self.main_window.update_window_title_status(_("Memutar Audio ({title})").format(title=f"{title[:20]}..."))
            elif self.main_window.tab_widget.currentWidget() == self.main_window.video_player_widget:
                self.main_window.set_status_text(_("Video Aktif: {title}").format(title=title))
                self.main_window.update_window_title_status(_("Memutar Video ({title})").format(title=f"{title[:20]}..."))
        elif state == QMediaPlayer.PlaybackState.PausedState:
            if self._watchdog_timer.isActive():
                self._watchdog_timer.stop()
            title = self.main_window.current_video_title_for_window
            if self.main_window.tab_widget.currentWidget() == self.main_window.audio_player_widget:
                self.main_window.set_status_text(_("Audio Dijeda: {title}").format(title=title))
                self.main_window.update_window_title_status(_("Audio Dijeda ({title})").format(title=f"{title[:20]}..."))
            elif self.main_window.tab_widget.currentWidget() == self.main_window.video_player_widget:
                self.main_window.set_status_text(_("Video Dijeda: {title}").format(title=title))
                self.main_window.update_window_title_status(_("Video Dijeda ({title})").format(title=f"{title[:20]}..."))

    def play_video_from_input_shortcut(self):
        url = self.main_window.main_view_widget.input_line_edit.text().strip()
        if self.main_window.is_likely_direct_video_url(url):
            self.main_window.last_selected_search_item_url = url
            self.request_stream_info_and_play(url, _("Video dari Input"), True)
        else:
            QMessageBox.warning(self.main_window, _("Aksi Tidak Sesuai"), _("URL video YouTube yang valid diperlukan."))

    def play_audio_from_input_shortcut(self):
        url = self.main_window.main_view_widget.input_line_edit.text().strip()
        if self.main_window.is_likely_direct_video_url(url):
            self.main_window.last_selected_search_item_url = url
            self.request_stream_info_and_play(url, _("Audio dari Input"), False)
        else:
            QMessageBox.warning(self.main_window, _("Aksi Tidak Sesuai"), _("URL video YouTube yang valid diperlukan."))

    def request_stream_info_and_play(self, page_url, title_hint, play_video, trigger_related=True):
        self.stop_current_playback(suppress_autoplay=True)
        self.main_window.stop_active_threads(exclude_stream_info=True, exclude_download_thread=True)
        self.main_window.current_video_title_for_window = title_hint
        self._current_stream_url = ""
        self._current_play_mode_video = bool(play_video)
        self._stream_recovery_attempts = 0
        self._recovery_in_progress = False
        self._ensure_playback_seed(page_url, title_hint)
        if trigger_related:
            self._start_related_fetch(page_url, title_hint)
        self.main_window.set_status_text(_("Mengambil info stream: {title}...").format(title=title_hint))
        self.main_window.update_window_title_status(_("Mengambil Info Stream"))
        self.main_window.set_ui_busy_state(True, operation_type="playback_loading")
        if self.main_window.operation_progress_dialog:
            self.main_window.operation_progress_dialog.close()
        self.main_window.operation_progress_dialog = OperationProgressDialog(f"{_('Memuat')} {(_('Video') if play_video else _('Audio'))}: {title_hint[:30]}...", self.main_window)
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
        self._current_stream_url = stream_url
        self._current_play_mode_video = bool(play_video)
        self._stream_recovery_attempts = 0
        self._recovery_in_progress = False
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
                self.main_window.tab_widget.addTab(self.main_window.video_player_widget, _("Video Player"))
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
                self.main_window.tab_widget.addTab(self.main_window.audio_player_widget, _("Audio Player"))
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

            rate_text = _("kecepatan pemutar {rate}").format(rate=f"{new_rate:.2f}")
            self.main_window.set_status_text(_("Kecepatan pemutar diatur ke {rate}x").format(rate=f"{new_rate:.2f}"))
            nvda_speak(rate_text)

    def handle_stream_info_error(self, error_message):
        if self.main_window.operation_progress_dialog:
            self.main_window.operation_progress_dialog.reject()
            self.main_window.operation_progress_dialog = None
        QMessageBox.critical(self.main_window, _("Gagal Memutar"), f"{_('Tidak bisa dapat info stream')}: {error_message}")
        self.main_window.set_status_text(_("Gagal playback."))
        self.main_window.update_window_title_status(_("Gagal Playback"))

    def stop_current_playback(self, suppress_autoplay=False):
        if self.main_window.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            if suppress_autoplay:
                self._suppress_autoplay_once = True
            self.main_window.media_player.stop()

    def close_player_view(self):
        self.stop_current_playback(suppress_autoplay=True)
        self._current_stream_url = ""
        self._recovery_in_progress = False
        self._stream_recovery_attempts = 0
        if self._watchdog_timer.isActive():
            self._watchdog_timer.stop()
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
            dprint("[_try_play_next_item] No current URL.")
            return False
            
        results = self.main_window.search_results
        if not results:
            dprint("[_try_play_next_item] No search results list.")
            return False

        current_index = -1
        current_vid = self._extract_video_id(current_url)
        for i, item in enumerate(results):
            item_url = item.get('url')
            if item_url == current_url:
                current_index = i
                break
            if current_vid and self._extract_video_id(item_url) == current_vid:
                current_index = i
                break
        
        dprint(f"[_try_play_next_item] Current index: {current_index}/{len(results)}")

        if current_index != -1 and current_index + 1 < len(results):
            next_item = results[current_index + 1]
            next_url = next_item.get('url')
            next_title = next_item.get('title', _("Video Berikutnya"))
            
            # Determine play type (video/audio) based on current active widget
            is_video_mode = (self.main_window.tab_widget.currentWidget() == self.main_window.video_player_widget)
            
            self.main_window.last_selected_search_item_url = next_url
            self.request_stream_info_and_play(next_url, next_title, is_video_mode, trigger_related=False)
            
            msg = _("Memutar otomatis selanjutnya: {title}").format(title=next_title)
            self.main_window.set_status_text(msg)
            nvda_speak(msg)
            dprint(f"[_try_play_next_item] Playing next: {next_title}")
            return True
            
        return False
