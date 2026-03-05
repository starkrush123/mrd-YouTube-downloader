import os
import yt_dlp
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QTimer
from threads.download_thread import DownloadThread
from ui.dialogs.progress_dialogs import DownloadProgressDialog
from utils.history_manager import add_to_history

class DownloadHandler:
    def __init__(self, main_window):
        self.main_window = main_window

    def _get_cookie_params(self):
        return {
            'source': self.main_window.settings.get('cookie_source', 'none'),
            'browser': self.main_window.settings.get('cookie_browser', 'chrome'),
            'file': self.main_window.settings.get('cookie_file', '')
        }

    def start_download(self, video_url, video_title_hint=None, download_type='video'):
        if any((t and t.isRunning()) for t in [self.main_window.search_thread, self.main_window.playlist_fetch_thread, self.main_window.channel_fetch_thread]):
            QMessageBox.information(self.main_window, _("Operasi Berjalan"), _("Selesaikan atau hentikan operasi lain sebelum memulai unduhan."))
            return
        if self.main_window.download_thread and self.main_window.download_thread.isRunning():
            QMessageBox.information(self.main_window, _("Unduhan Berjalan"), _("Satu unduhan sudah berjalan. Harap tunggu atau hentikan."))
            return

        out_path = self.main_window.settings['output_path']
        fmt_choice = self.main_window.settings['video_format_choice'] if download_type == 'video' else self.main_window.settings['audio_format_choice']
        embed_meta = self.main_window.settings.get('embed_metadata', True)
        use_parallel = self.main_window.settings.get('use_parallel_download', False)
        self.main_window.set_ui_busy_state(True, "download")
        self.main_window.current_list_batch_download_active = False
        self.main_window.last_downloaded_item_info = {'url': video_url, 'title': video_title_hint or _("Media"), 'type': download_type}

        if self.main_window.download_progress_dialog:
            self.main_window.download_progress_dialog.reject()

        self.main_window.download_progress_dialog = DownloadProgressDialog(video_title_hint or _("Memuat Info..."), self.main_window)
        self.main_window.download_progress_dialog.cancel_requested.connect(self.handle_download_cancellation_request)
        self.main_window.download_progress_dialog.show()

        self.main_window.set_status_text(
            _("Mulai unduh {kind}: {title}...").format(kind=download_type, title=(video_title_hint or video_url[:50]))
        )
        self.main_window.update_window_title_status(
            _("Mengunduh {kind} ({title})").format(
                kind=download_type.capitalize(), title=f"{(video_title_hint or _('Media'))[:20]}..."
            )
        )

        cookie_params = self._get_cookie_params()
        self.main_window.download_thread = DownloadThread(video_url, out_path, fmt_choice, embed_meta, use_parallel, cookie_params, video_title_hint, is_batch=False, parent=self.main_window)
        self.main_window.download_thread.download_title_signal.connect(self.main_window.download_progress_dialog.update_title)
        self.main_window.download_thread.download_progress_signal.connect(self.main_window.download_progress_dialog.update_progress)
        self.main_window.download_thread.download_status_signal.connect(self.main_window.download_progress_dialog.update_status)
        self.main_window.download_thread.download_finished_signal.connect(self.handle_single_download_finished)
        self.main_window.download_thread.finished.connect(self.main_window._on_any_thread_finished)
        self.main_window.download_thread.start()

    def start_batch_download_list(self, items_to_download, list_title, download_type='video'):
        if not items_to_download:
            QMessageBox.warning(self.main_window, _("Tidak Ada Item"), _("Tidak ada video untuk diunduh dari list ini."))
            return
        if any((t and t.isRunning()) for t in [self.main_window.search_thread, self.main_window.playlist_fetch_thread, self.main_window.channel_fetch_thread]):
            QMessageBox.information(self.main_window, _("Operasi Berjalan"), _("Selesaikan operasi lain."))
            return
        if self.main_window.download_thread and self.main_window.download_thread.isRunning():
            QMessageBox.information(self.main_window, _("Unduhan Berjalan"), _("Satu unduhan (mungkin batch lain) sudah jalan."))
            return

        sane_title = yt_dlp.utils.sanitize_filename(list_title, restricted=True)
        item_count = len(items_to_download)
        download_as_type_text = "video" if download_type == 'video' else "audio"

        if QMessageBox.question(
            self.main_window,
            _("Konfirmasi Unduh Semua"),
            _("Unduh {count} {item_word} dari '{title}' sebagai {kind}?\nFile akan disimpan di subfolder '{folder}'.").format(
                count=item_count, item_word=_("item"), title=list_title, kind=download_as_type_text, folder=sane_title
            )
        ) == QMessageBox.StandardButton.No:
            self.main_window.set_status_text(_("Unduhan batch dibatalkan."))
            self.main_window.restore_proper_focus()
            return

        out_path = self.main_window.settings['output_path']
        fmt_choice = self.main_window.settings['video_format_choice'] if download_type == 'video' else self.main_window.settings['audio_format_choice']
        embed_meta = self.main_window.settings.get('embed_metadata', True)
        use_parallel = self.main_window.settings.get('use_parallel_download', False)
        self.main_window.set_ui_busy_state(True, "download_batch")
        self.main_window.current_list_batch_download_active = True
        self.main_window.download_initiated_from_search_dialog = True

        if self.main_window.download_progress_dialog:
            self.main_window.download_progress_dialog.reject()

        self.main_window.download_progress_dialog = DownloadProgressDialog(
            _("Batch ({kind}): {title}...").format(kind=download_as_type_text, title=list_title[:30]), self.main_window
        )
        self.main_window.download_progress_dialog.cancel_requested.connect(self.handle_download_cancellation_request)
        self.main_window.download_progress_dialog.show()

        self.main_window.set_status_text(
            _("Mulai batch ({kind}): {title} ({count} item)...").format(
                kind=download_as_type_text, title=list_title, count=item_count
            )
        )
        self.main_window.update_window_title_status(
            _("Batch Unduh ({kind}) ({title})").format(kind=download_as_type_text.capitalize(), title=f"{list_title[:20]}...")
        )

        cookie_params = self._get_cookie_params()
        self.main_window.download_thread = DownloadThread(items_to_download, out_path, fmt_choice, embed_meta, use_parallel, cookie_params, None, True, list_title, self.main_window)
        self.main_window.download_thread.download_title_signal.connect(self.main_window.download_progress_dialog.update_title)
        self.main_window.download_thread.download_progress_signal.connect(self.main_window.download_progress_dialog.update_progress)
        self.main_window.download_thread.download_status_signal.connect(self.main_window.download_progress_dialog.update_status)
        self.main_window.download_thread.single_item_finished_signal.connect(self.handle_single_playlist_item_download_finished)
        self.main_window.download_thread.batch_overall_finished_signal.connect(self.handle_batch_overall_finished)
        self.main_window.download_thread.finished.connect(self.main_window._on_any_thread_finished)
        self.main_window.download_thread.start()

    def handle_download_cancellation_request(self):
        if self.main_window.download_thread and self.main_window.download_thread.isRunning():
            op_type = _("Batch unduhan") if self.main_window.current_list_batch_download_active else _("Unduhan")
            reply = QMessageBox.question(self.main_window, _("Batalkan {op}?").format(op=op_type),
                                         _("Apakah Anda yakin ingin membatalkan {op} yang sedang berjalan?").format(op=op_type.lower()),
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.main_window.set_status_text(_("Mencoba membatalkan {op}...").format(op=op_type.lower()))
                self.main_window.update_window_title_status(_("Membatalkan {op}").format(op=op_type))
                self.main_window.download_thread.stop()
                if self.main_window.download_progress_dialog:
                    self.main_window.download_progress_dialog.update_status(_("Membatalkan..."))
                    self.main_window.download_progress_dialog.cancel_button.setEnabled(False)

    def handle_single_playlist_item_download_finished(self, success, message, filepath, current_index, total_items):
        base_filename = os.path.basename(filepath) if filepath else f"Item {current_index+1}"
        if success:
            add_to_history(base_filename, filepath)
            self.main_window.history_tab.refresh_history()
            self.main_window.set_status_text(
                _("Item {current}/{total} ('{name}'): {message}").format(
                    current=current_index + 1, total=total_items, name=base_filename, message=message
                )
            )

    def handle_batch_overall_finished(self, overall_success, final_batch_summary, base_output_path):
        self.main_window.current_list_batch_download_active = False
        if self.main_window.download_progress_dialog:
            self.main_window.download_progress_dialog.download_complete(overall_success, _("Batch selesai."))
            QTimer.singleShot(100, lambda s=overall_success, m=final_batch_summary, p=base_output_path: self.close_download_dialog_and_notify_batch(s, m, p))
        else:
            QTimer.singleShot(0, lambda s=overall_success, m=final_batch_summary, p=base_output_path: self.close_download_dialog_and_notify_batch(s, m, p))
        self.main_window.current_batch_finished_success = overall_success
        self.main_window.current_batch_finished_message = final_batch_summary
        self.main_window.current_batch_finished_base_path = base_output_path
        self.main_window.current_batch_list_title = self.main_window.download_thread.list_title_for_batch if self.main_window.download_thread else _("List")

    def close_download_dialog_and_notify_batch(self, success, message_summary, base_output_path):
        if self.main_window.download_progress_dialog and self.main_window.download_progress_dialog.isVisible():
            self.main_window.download_progress_dialog.accept()
            self.main_window.download_progress_dialog = None
        list_title = self.main_window.current_batch_list_title
        status_prefix = _("Batch Selesai") if success else _("Batch Selesai (Ada Gagal)")
        self.main_window.set_status_text(f"{status_prefix}: {message_summary.splitlines()[0] if message_summary.splitlines() else message_summary}")
        self.main_window.update_window_title_status(_("Batch Unduhan {status}").format(status=status_prefix))
        if self.main_window.settings.get('show_completion_popup', True) or not success:
            self.show_batch_download_completion_dialog(success, message_summary, base_output_path, list_title)

    def show_batch_download_completion_dialog(self, success, message_summary, base_output_path, list_title):
        title = f"{_('Batch Unduhan')} '{list_title}' {_('Selesai')}"
        text = _("Proses unduh dari '{title}' telah selesai.\n\n{summary}").format(
            title=list_title, summary=message_summary
        )
        def show_msg():
            msg_box = QMessageBox(self.main_window)
            msg_box.setIcon(QMessageBox.Icon.Information if success else QMessageBox.Icon.Warning)
            msg_box.setWindowTitle(title)
            msg_box.setText(text)
            actual_path = os.path.join(base_output_path, yt_dlp.utils.sanitize_filename(list_title, restricted=True))
            if success and os.path.isdir(actual_path):
                btn_folder = msg_box.addButton(_("Buka Folder"), QMessageBox.ButtonRole.ActionRole)
                msg_box.addButton(QMessageBox.StandardButton.Ok)
                clicked_button = msg_box.exec()
                if clicked_button == btn_folder:
                    self.main_window.open_location(actual_path)
            else:
                msg_box.addButton(QMessageBox.StandardButton.Ok)
                msg_box.exec()
            self.main_window.restore_proper_focus()
        QTimer.singleShot(0, show_msg)

    def handle_single_download_finished(self, success, message, downloaded_file_path):
        if self.main_window.current_list_batch_download_active: return
        if success:
            title = self.main_window.last_downloaded_item_info.get('title', _("Unknown Title"))
            add_to_history(title, downloaded_file_path)
            self.main_window.history_tab.refresh_history()
        if self.main_window.download_progress_dialog:
            self.main_window.download_progress_dialog.download_complete(success, message)
            QTimer.singleShot(100, lambda s=success, m=message, p=downloaded_file_path: self.close_single_download_dialog_and_notify(s, m, p))
        else:
             QTimer.singleShot(0, lambda s=success, m=message, p=downloaded_file_path: self.close_single_download_dialog_and_notify(s, m, p))

    def close_single_download_dialog_and_notify(self, success, message, downloaded_file_path):
        if self.main_window.current_list_batch_download_active: return
        if self.main_window.download_progress_dialog and self.main_window.download_progress_dialog.isVisible():
            self.main_window.download_progress_dialog.accept()
            self.main_window.download_progress_dialog = None
        download_type_text = self.main_window.last_downloaded_item_info.get('type', 'media').capitalize() if self.main_window.last_downloaded_item_info else _("Media")
        self.main_window.set_status_text(
            _("{kind} {state}: {message}").format(kind=download_type_text, state=_("Selesai") if success else _("Gagal"), message=message)
        )
        self.main_window.update_window_title_status(
            _("Unduhan {kind} {state}").format(kind=download_type_text, state=_("Selesai") if success else _("Gagal"))
        )
        if self.main_window.settings.get('show_completion_popup', True) or not success:
            self.show_single_download_completion_dialog(success, message, downloaded_file_path)

    def show_single_download_completion_dialog(self, success, message, downloaded_file_path):
        download_type_text = self.main_window.last_downloaded_item_info.get('type', 'media').capitalize() if self.main_window.last_downloaded_item_info else _("Media")
        title = f"{_('Unduhan')} {download_type_text} {_('Selesai')}" if success else f"{_('Unduhan')} {download_type_text} {_('Gagal')}"
        text = ""
        if success:
            file_name_display = os.path.basename(downloaded_file_path) if downloaded_file_path else _("File")
            text = _("File \"{name}\" berhasil diunduh.").format(name=file_name_display)
            folder_path_display = os.path.dirname(downloaded_file_path) if downloaded_file_path else self.main_window.settings['output_path']
            text += "\n" + _("Disimpan di: {path}").format(path=folder_path_display)
        else:
            text = _("Unduhan {kind} Gagal.\n\nError: {message}").format(kind=download_type_text, message=message)
        def show_msg():
            msg_box = QMessageBox(self.main_window)
            msg_box.setIcon(QMessageBox.Icon.Information if success else QMessageBox.Icon.Critical)
            msg_box.setWindowTitle(title)
            msg_box.setText(text)
            if success and downloaded_file_path and os.path.exists(downloaded_file_path):
                btn_folder = msg_box.addButton(_("Buka Folder"), QMessageBox.ButtonRole.ActionRole)
                btn_file = msg_box.addButton(_("Buka File"), QMessageBox.ButtonRole.ActionRole)
                msg_box.addButton(QMessageBox.StandardButton.Ok)
                clicked_button = msg_box.exec()
                if clicked_button == btn_folder:
                    self.main_window.open_location(os.path.dirname(downloaded_file_path))
                elif clicked_button == btn_file:
                    self.main_window.open_location(downloaded_file_path)
            else:
                msg_box.addButton(QMessageBox.StandardButton.Ok)
                msg_box.exec()
            self.main_window.restore_proper_focus()
        QTimer.singleShot(0, show_msg)

    def handle_playback_download_request(self, download_type):
        if self.main_window.last_selected_search_item_url:
            QMessageBox.information(self.main_window, f"{_('Mulai Unduh')} {download_type.capitalize()}",
                                      _("Memulai unduhan {kind} untuk:\n'{title}'.").format(
                                          kind=download_type, title=self.main_window.current_video_title_for_window
                                      ))
            self.start_download(self.main_window.last_selected_search_item_url, 
                                video_title_hint=self.main_window.current_video_title_for_window, 
                                download_type=download_type)
        else:
            QMessageBox.warning(self.main_window, _("Gagal Unduh"), _("Tidak ada informasi URL yang tersimpan untuk media yang sedang diputar."))
