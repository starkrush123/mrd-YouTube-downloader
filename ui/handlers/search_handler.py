from PySide6.QtWidgets import QMessageBox
from threads.search_thread import SearchThread, PlaylistFetchThread, ChannelFetchThread
from ui.dialogs.search_results_dialog import SearchResultsDialog
from ui.dialogs.progress_dialogs import OperationProgressDialog

class SearchHandler:
    def __init__(self, main_window):
        self.main_window = main_window
        self.active_search_results_dialog = None

    def _get_cookie_params(self):
        return {
            'source': self.main_window.settings.get('cookie_source', 'none'),
            'browser': self.main_window.settings.get('cookie_browser', 'chrome'),
            'file': self.main_window.settings.get('cookie_file', '')
        }

    def process_input(self):
        txt = self.main_window.main_view_widget.input_line_edit.text().strip()
        if not txt:
            QMessageBox.warning(self.main_window, "Input Kosong", "Masukkan URL atau kata kunci.")
            return

        self.main_window.stop_current_operation(confirm=False)
        if self.active_search_results_dialog and self.active_search_results_dialog.isVisible():
            self.active_search_results_dialog.close()
            self.active_search_results_dialog = None

        if self.main_window.is_youtube_channel_url(txt):
            QMessageBox.information(self.main_window, "URL Channel Terdeteksi", f"URL '{txt[:60]}...' dikenali sebagai channel. Akan menampilkan 100 video terbaru.")
            self.start_channel_item_fetch(txt)
        elif self.main_window.is_potential_playlist_url(txt):
            QMessageBox.information(self.main_window, "URL Playlist Terdeteksi", f"URL '{txt[:60]}...' dikenali sebagai playlist. Akan menampilkan isinya.")
            self.start_playlist_item_fetch_via_url(txt)
        elif self.main_window.is_likely_direct_video_url(txt):
            self.main_window.handle_direct_video_url_dialog(txt)
        else:
            self.start_search(txt, search_type=self.main_window.main_view_widget.search_type_combo.currentText())

    def start_search(self, query, search_type="Video"):
        if any((t and t.isRunning()) for t in [self.main_window.download_thread, self.main_window.playlist_fetch_thread, self.main_window.channel_fetch_thread]):
            QMessageBox.information(self.main_window, "Operasi Berjalan", "Selesaikan operasi lain.")
            return
        if self.main_window.search_thread and self.main_window.search_thread.isRunning():
            self.main_window.search_thread.terminate()
            self.main_window.search_thread.wait()

        self.main_window.search_results = []
        
        if search_type == "Channel":
            self.start_channel_item_fetch(query)
            return

        self.main_window.set_ui_busy_state(True, "search")
        lbl = "Video" if search_type == "Video" else "Playlist"
        self.main_window.set_status_text(f"Mencari {lbl} \"{query}\"..." )
        self.main_window.update_window_title_status(f"Mencari {lbl} ({query[:20]}...)")
        self.main_window.current_video_title_for_window = query
        if self.main_window.operation_progress_dialog: self.main_window.operation_progress_dialog.close()
        self.main_window.operation_progress_dialog = OperationProgressDialog(f"Mencari {lbl}: {query[:30]}...", self.main_window)
        self.main_window.operation_progress_dialog.show()

        cookie_params = self._get_cookie_params()
        self.main_window.search_thread = SearchThread(query, self.main_window.settings.get('search_results_count', 10), search_type, cookie_params, self.main_window)
        self.main_window.search_thread.results_batch_ready.connect(self.handle_search_results_batch)
        self.main_window.search_thread.search_finished.connect(self.handle_search_finished)
        self.main_window.search_thread.search_error.connect(self.handle_search_error)
        self.main_window.search_thread.finished.connect(self.main_window._on_any_thread_finished)
        self.main_window.search_thread.start()

    def handle_search_results_batch(self, results, result_type):
        if self.main_window.operation_progress_dialog and self.main_window.operation_progress_dialog.isVisible():
            self.main_window.operation_progress_dialog.accept()
            self.main_window.operation_progress_dialog = None

        if results:
            self.main_window.search_results.extend(results)

        query_ctx = self.main_window.current_video_title_for_window

        if self.active_search_results_dialog and self.active_search_results_dialog.isVisible():
            self.active_search_results_dialog.add_results(results)
        else:
            dlg_res_type = "video_search" if result_type == "video" else "playlist_search_results"
            entity = "video" if result_type == "video" else "playlist"
            self.main_window.set_status_text(f"Menampilkan hasil awal {entity} untuk \"{query_ctx}\"..." )

            if not results: return

            if self.active_search_results_dialog and self.active_search_results_dialog.isVisible():
                self.active_search_results_dialog.close()

            self.active_search_results_dialog = SearchResultsDialog(
                results, self.main_window, result_type=dlg_res_type, settings=self.main_window.settings
            )
            self.active_search_results_dialog.action_triggered.connect(self.handle_action_from_search_dialog)
            self.active_search_results_dialog.show()
            self.main_window.main_view_widget.input_line_edit.setFocus()

        # Clear reference after dialog closes (moved to process_input for proper handling)
        # self.active_search_results_dialog = None

    def handle_search_finished(self, result_type, total_count):
        if self.main_window.operation_progress_dialog and self.main_window.operation_progress_dialog.isVisible():
            self.main_window.operation_progress_dialog.accept()
            self.main_window.operation_progress_dialog = None
        if self.active_search_results_dialog:
            self.active_search_results_dialog.set_final_count(total_count)

        entity = "video" if result_type == "video" else "playlist"
        self.main_window.set_status_text(f"Pencarian selesai. Ditemukan total {total_count} hasil {entity}.")
        self.main_window.update_window_title_status(f"Hasil Pencarian {entity.capitalize()}")

    def start_playlist_item_fetch_via_url(self, playlist_url):
        if any((t and t.isRunning()) for t in [self.main_window.download_thread, self.main_window.search_thread, self.main_window.channel_fetch_thread]):
            QMessageBox.information(self.main_window, "Operasi Berjalan", "Selesaikan operasi lain.")
            return
        if self.main_window.playlist_fetch_thread and self.main_window.playlist_fetch_thread.isRunning():
            self.main_window.playlist_fetch_thread.terminate()
            self.main_window.playlist_fetch_thread.wait()
        
        self.main_window.search_results = []
        
        self.main_window.set_ui_busy_state(True, "playlist_fetching")
        self.main_window.set_status_text(f"Memuat item dari playlist: {playlist_url[:50]}...")
        self.main_window.update_window_title_status(f"Memuat Isi Playlist ({playlist_url[:30]}...)")
        self.main_window.current_video_title_for_window = playlist_url
        if self.main_window.operation_progress_dialog: self.main_window.operation_progress_dialog.close()
        self.main_window.operation_progress_dialog = OperationProgressDialog(f"Memuat Isi Playlist: {playlist_url[:40]}...", self.main_window)
        self.main_window.operation_progress_dialog.show()
        
        cookie_params = self._get_cookie_params()
        self.main_window.playlist_fetch_thread = PlaylistFetchThread(playlist_url, cookie_params, parent=self.main_window)
        self.main_window.playlist_fetch_thread.results_ready.connect(self.handle_list_items_results)
        self.main_window.playlist_fetch_thread.fetch_error.connect(self.handle_list_fetch_error)
        self.main_window.playlist_fetch_thread.finished.connect(self.main_window._on_any_thread_finished)
        self.main_window.playlist_fetch_thread.start()

    def start_channel_item_fetch(self, channel_url_or_query):
        if any((t and t.isRunning()) for t in [self.main_window.download_thread, self.main_window.search_thread, self.main_window.playlist_fetch_thread]):
            QMessageBox.information(self.main_window, "Operasi Berjalan", "Selesaikan operasi lain.")
            return
        if self.main_window.channel_fetch_thread and self.main_window.channel_fetch_thread.isRunning():
            self.main_window.channel_fetch_thread.terminate()
            self.main_window.channel_fetch_thread.wait()
        
        self.main_window.search_results = []
        
        self.main_window.set_ui_busy_state(True, "channel_fetching")
        self.main_window.set_status_text(f"Memuat video dari channel: {channel_url_or_query[:50]}...")
        self.main_window.update_window_title_status(f"Memuat Channel ({channel_url_or_query[:30]}...)")
        self.main_window.current_video_title_for_window = channel_url_or_query
        if self.main_window.operation_progress_dialog: self.main_window.operation_progress_dialog.close()
        self.main_window.operation_progress_dialog = OperationProgressDialog(f"Memuat Channel: {channel_url_or_query[:40]}...", self.main_window)
        self.main_window.operation_progress_dialog.show()
        
        cookie_params = self._get_cookie_params()
        self.main_window.channel_fetch_thread = ChannelFetchThread(channel_url_or_query, cookie_params, self.main_window)
        self.main_window.channel_fetch_thread.results_ready.connect(lambda e, t, u: self.handle_list_items_results(e, t, u, list_type='channel'))
        self.main_window.channel_fetch_thread.fetch_error.connect(self.handle_list_fetch_error)
        self.main_window.channel_fetch_thread.finished.connect(self.main_window._on_any_thread_finished)
        self.main_window.channel_fetch_thread.start()

    def handle_list_items_results(self, entries, list_title, original_list_url, list_type='playlist'):
        if self.main_window.operation_progress_dialog:
            self.main_window.operation_progress_dialog.accept()
            self.main_window.operation_progress_dialog = None
        
        self.main_window.search_results = entries
        
        list_name = "Playlist" if list_type == 'playlist' else "Channel"
        item_name = "video" if list_type == 'channel' else "item"
        dialog_result_type = "channel_items" if list_type == 'channel' else "playlist_items"
        self.main_window.set_status_text(f"{list_name} '{list_title}' berisi {len(entries)} {item_name}.")
        self.main_window.update_window_title_status(f"Isi {list_name}: {list_title[:20]}...")
        self.main_window.current_video_title_for_window = list_title
        if not entries:
            QMessageBox.information(self.main_window, f"Isi {list_name}", f"{list_name} '{list_title}' kosong atau tidak berisi video yang dapat diakses.")
            self.main_window.main_view_widget.input_line_edit.setFocus()
            self.main_window.update_window_title_status("Siap")
            return

        if self.active_search_results_dialog and self.active_search_results_dialog.isVisible():
            self.active_search_results_dialog.close()

        self.active_search_results_dialog = SearchResultsDialog(
            entries, self.main_window, result_type=dialog_result_type,
            list_title_str=list_title, original_list_url=original_list_url, settings=self.main_window.settings
        )
        self.active_search_results_dialog.action_triggered.connect(self.handle_action_from_search_dialog)
        self.active_search_results_dialog.download_all_playlist_items_requested.connect(self.main_window.download_handler.start_batch_download_list)
        self.active_search_results_dialog.show()
        self.main_window.main_view_widget.input_line_edit.setFocus()

        # Clear reference after dialog closes (moved to process_input for proper handling)
        # self.active_search_results_dialog = None

    def handle_list_fetch_error(self, error_message):
        if self.main_window.operation_progress_dialog:
            self.main_window.operation_progress_dialog.reject()
            self.main_window.operation_progress_dialog = None
        self.main_window.set_status_text(f"Gagal Muat: {error_message}")
        QMessageBox.critical(self.main_window, "Gagal Muat", error_message)
        self.main_window.restore_proper_focus()

    def handle_action_from_search_dialog(self, info):
        if info and info.get('url'):
            action, url, title, item_type = info.get('action', 'download_video'), info['url'], info['title'], info.get('type', 'video')
            self.main_window.last_selected_search_item_url = url
            if item_type == 'playlist_meta' and action == 'view_playlist_items':
                self.main_window.set_status_text(f"Pilihan Playlist: {title}. Memuat item...")
                self.start_playlist_item_fetch_via_url(url)
                return
            elif item_type == 'video':
                if action == 'play_video':
                    self.main_window.player_handler.request_stream_info_and_play(url, title, True)
                elif action == 'play_audio':
                    self.main_window.player_handler.request_stream_info_and_play(url, title, False)
                elif action == 'download_video' or action == 'download_audio':
                    self.main_window.last_downloaded_item_info = {'url': url, 'title': title, 'type': 'video' if action == 'download_video' else 'audio'}
                    self.main_window.download_initiated_from_search_dialog = True
                    self.main_window.download_handler.start_download(url, video_title_hint=title, download_type='video' if action == 'download_video' else 'audio')
                else:
                    self.main_window.set_status_text("Aksi tidak diketahui.")
                    self.main_window.update_window_title_status("Siap")
        else:
            self.main_window.set_status_text("Aksi dibatalkan.")
            self.main_window.update_window_title_status("Siap")
            self.main_window.restore_proper_focus()

    

    def handle_search_error(self, error_message):
        if self.main_window.operation_progress_dialog:
            self.main_window.operation_progress_dialog.reject()
            self.main_window.operation_progress_dialog = None
        self.main_window.set_status_text(f"Kesalahan Cari: {error_message}")
        QMessageBox.critical(self.main_window, "Kesalahan Cari", error_message)
        self.main_window.restore_proper_focus()
