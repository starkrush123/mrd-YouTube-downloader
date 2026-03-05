from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
    QListWidgetItem, QPushButton, QDialogButtonBox, QMessageBox, QMenu, QStyle
)
from PySide6.QtCore import Signal, Qt, QUrl, QSize, QThreadPool
from PySide6.QtGui import QIcon, QDesktopServices, QAction
from threads.thumbnail_thread import ThumbnailDownloader

class SearchResultsDialog(QDialog):
    action_triggered = Signal(dict)
    download_all_playlist_items_requested = Signal(list, str, str)
    def __init__(self, results, parent=None, result_type="video_search", list_title_str=None, original_list_url=None, settings=None):
        super().__init__(parent)
        self.setModal(False)
        self.result_type = result_type
        self.original_list_url = original_list_url
        self.list_title_str = list_title_str
        self.settings = settings if settings else {}
        self.threadpool = QThreadPool()
        self.item_map = {}
        self.total_expected_results = 0
        self.all_list_items_data = []
        layout = QVBoxLayout(self)
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        if self.result_type in ["playlist_items", "channel_items"]:
            list_type_name = _("Playlist") if self.result_type == "playlist_items" else _("Channel")
            item_count_text = "video" if self.result_type == "channel_items" else "item"
            title_text = f"{_('Isi')} {list_type_name}: {self.list_title_str[:50]}{'...' if len(self.list_title_str) > 50 else ''}"
            
            self.download_all_videos_button = QPushButton(f"{_('Unduh Semua Video')} ({len(results)})")
            self.download_all_videos_button.setToolTip(f"{_('Unduh semua')} {len(results)} {_('video dari')} '{self.list_title_str}' {_('sebagai video.')}")
            self.download_all_videos_button.clicked.connect(lambda: self.handle_download_all_list_items('video'))
            layout.addWidget(self.download_all_videos_button)
            
            self.download_all_audios_button = QPushButton(f"{_('Unduh Semua Audio')} ({len(results)})")
            self.download_all_audios_button.setToolTip(f"{_('Unduh semua')} {len(results)} {_('item dari')} '{self.list_title_str}' {_('sebagai audio.')}")
            self.download_all_audios_button.clicked.connect(lambda: self.handle_download_all_list_items('audio'))
            layout.addWidget(self.download_all_audios_button)
        elif self.result_type == "playlist_search_results":
            title_text = _("Hasil Pencarian Playlist")
        else: # video_search
            title_text = _("Hasil Pencarian Video")
        self.setWindowTitle(title_text)
        self.results_list_widget = QListWidget()
        self.results_list_widget.setAccessibleName(_("Daftar hasil pencarian atau item playlist"))
        self.results_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.results_list_widget.setIconSize(QSize(128, 72))
        self.results_list_widget.setWordWrap(True)
        if not results:
            self.results_list_widget.addItem(_("Memuat hasil..."))
        else:
            self.add_results(results, is_initial=True)
        self.results_list_widget.itemDoubleClicked.connect(self.handle_double_click_action)
        layout.addWidget(self.results_list_widget)
        button_layout = QHBoxLayout()
        
        if self.result_type == "playlist_search_results":
            self.view_playlist_items_button = QPushButton(_("Lihat Isi Playlist"))
            self.view_playlist_items_button.setToolTip(_("Lihat video di playlist (Enter atau Dobel Klik)"))
            self.view_playlist_items_button.clicked.connect(self.handle_view_playlist_items_button_click)
            button_layout.addWidget(self.view_playlist_items_button)
        elif self.result_type in ["video_search", "playlist_items", "channel_items"]:
            self.download_video_button = QPushButton(_("Unduh Video"))
            self.download_audio_button = QPushButton(_("Unduh Audio"))
            self.play_video_button = QPushButton(_("Putar Video"))
            self.play_audio_button = QPushButton(_("Putar Audio"))
            self.update_button_tooltips()
            
            self.download_video_button.clicked.connect(self.handle_download_video_button_click)
            self.download_audio_button.clicked.connect(self.handle_download_audio_button_click)
            self.play_video_button.clicked.connect(self.handle_play_video_button_click)
            self.play_audio_button.clicked.connect(self.handle_play_audio_button_click)
            button_layout.addWidget(self.download_video_button)
            button_layout.addWidget(self.download_audio_button)
            button_layout.addWidget(self.play_video_button)
            button_layout.addWidget(self.play_audio_button)
            
        layout.addLayout(button_layout)
        dialog_button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        dialog_button_box.rejected.connect(self.reject)
        layout.addWidget(dialog_button_box)
        self.setMinimumSize(750, 550)

    def _normalize_double_click_action(self, action_label):
        normalized = (action_label or "").replace(_("Langsung "), "").strip()
        if normalized in ("Unduh Video", _("Unduh Video")):
            return "download_video"
        if normalized in ("Putar Audio", _("Putar Audio")):
            return "play_audio"
        if normalized in ("Putar Video", _("Putar Video")):
            return "play_video"
        return "download_video"

    def _double_click_action_label(self):
        action_key = self._normalize_double_click_action(
            self.settings.get('search_result_double_click_action', _("Unduh Video"))
        )
        if action_key == "play_audio":
            return _("Putar Audio")
        if action_key == "play_video":
            return _("Putar Video")
        return _("Unduh Video")

    def update_button_tooltips(self):
        default_double_click_action_text = self._double_click_action_label()
        invert_shortcuts = self.settings.get('invert_playback_shortcuts', False)
        play_audio_shortcut = "Ctrl+Enter" if invert_shortcuts else "Enter"
        play_video_shortcut = "Enter" if invert_shortcuts else "Ctrl+Enter"
            
        dl_vid_tt = _("Unduh sebagai video (Ctrl+Shift+D)")
        if default_double_click_action_text == _("Unduh Video"): dl_vid_tt += " / " + _("Dobel Klik")
        self.download_video_button.setToolTip(dl_vid_tt)
        
        self.download_audio_button.setToolTip(_("Unduh sebagai audio (Ctrl+D)"))
        
        play_vid_tt = f"{_('Putar video')} ({play_video_shortcut})"
        if default_double_click_action_text == _("Putar Video"): play_vid_tt += " / " + _("Dobel Klik")
        self.play_video_button.setToolTip(play_vid_tt)
        
        play_aud_tt = f"{_('Putar audio')} ({play_audio_shortcut})"
        if default_double_click_action_text == _("Putar Audio"): play_aud_tt += " / " + _("Dobel Klik")
        self.play_audio_button.setToolTip(play_aud_tt)
        
    def _create_and_add_item(self, entry):
        if not entry: return
        item_text, list_item_data = "", {}
        
        if self.result_type == "playlist_search_results":
            title = entry.get('title', _("Playlist Tanpa Judul"))
            uploader = entry.get('uploader', entry.get('channel', 'N/A'))
            url = entry.get('webpage_url', entry.get('url'))
            item_text = f"{_('Judul Playlist')}: {title}\n{_('Channel')}: {uploader}"
            list_item_data = {'url': url, 'title': title, 'type': 'playlist_meta'}
            item = QListWidgetItem(item_text)
        else: 
            title = entry.get('title', _("Tanpa Judul"))
            uploader = entry.get('uploader', entry.get('channel_name', entry.get('channel', 'N/A')))
            duration = entry.get('duration')
            dur_str = self.format_duration(duration) if duration is not None else "N/A"
            url = entry.get('webpage_url', entry.get('url'))
            if not url and entry.get('id'): url = f"https://www.youtube.com/watch?v={entry['id']}"
            
            thumbnail_url = None
            if entry.get('thumbnails'):
                thumbnail_url = entry['thumbnails'][-1]['url'] 
            elif entry.get('thumbnail'):
                thumbnail_url = entry.get('thumbnail')
            
            item_text = f"{_('Judul')}: {title}\n{_('Channel')}: {uploader}\n{_('Durasi')}: {dur_str}"
            list_item_data = {'url': url, 'title': title, 'type': 'video', 'thumbnail_url': thumbnail_url}
            item = QListWidgetItem(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)), item_text)
            if thumbnail_url:
                self.item_map[thumbnail_url] = item
                worker = ThumbnailDownloader(thumbnail_url)
                worker.signals.finished.connect(self.set_item_icon)
                self.threadpool.start(worker)
        item.setData(Qt.ItemDataRole.UserRole, list_item_data)
        self.results_list_widget.addItem(item)

    def update_info_label(self):
        current_count = len(self.all_list_items_data)
        info_label_text = ""
        default_double_click_action_text = self._double_click_action_label()
        
        if self.result_type in ["playlist_items", "channel_items"]:
            list_type_name = _("Playlist") if self.result_type == "playlist_items" else _("Channel")
            item_count_text = _("video") if self.result_type == "channel_items" else _("item")
            info_label_text = _("{list_type} '{title}' berisi {count} {item_text}. Dobel klik untuk: {action}.").format(
                list_type=list_type_name,
                title=self.list_title_str,
                count=current_count,
                item_text=item_count_text,
                action=default_double_click_action_text,
            )
        elif self.result_type == "playlist_search_results":
            if self.total_expected_results == 0 or self.total_expected_results == current_count:
                status = _("Ditemukan {count} playlist.").format(count=current_count)
            else:
                status = _("Menampilkan {current} dari {total} playlist.").format(
                    current=current_count, total=self.total_expected_results
                )
            info_label_text = _("{status} Dobel klik untuk melihat isi playlist.").format(status=status)
        else: # video_search
            if self.total_expected_results == 0 or self.total_expected_results == current_count:
                status = _("Ditemukan {count} video.").format(count=current_count)
            else:
                status = _("Menampilkan {current} dari {total} video.").format(
                    current=current_count, total=self.total_expected_results
                )
            info_label_text = _("{status} Dobel klik untuk: {action}.").format(
                status=status, action=default_double_click_action_text
            )
            
        self.info_label.setText(info_label_text)
        
    def add_results(self, new_entries, is_initial=False):
        if is_initial and self.results_list_widget.count() > 0:
            if _("Memuat hasil...") in self.results_list_widget.item(0).text():
                self.results_list_widget.clear()
        if not isinstance(new_entries, list): return
        self.all_list_items_data.extend(new_entries)
        for entry in new_entries:
            self._create_and_add_item(entry)
            
        self.update_info_label()

    def set_final_count(self, total_count):
        self.total_expected_results = total_count
        self.update_info_label()

    def set_item_icon(self, url, icon):
        if url in self.item_map:
            item = self.item_map[url]
            item.setIcon(icon)

    def handle_triggered_action_with_data(self, item_data_dict, action_type_str):
        if item_data_dict and item_data_dict.get('url'):
            self.action_triggered.emit({
                'url': item_data_dict['url'],
                'title': item_data_dict['title'],
                'action': action_type_str,
                'type': item_data_dict.get('type')
            })
        else:
            QMessageBox.warning(self, _("Aksi Gagal"), _("Data item tidak valid atau URL tidak ada."))

    def show_context_menu(self, position):
        item = self.results_list_widget.itemAt(position)
        if not item: return
        current_item_data = item.data(Qt.ItemDataRole.UserRole)
        if not current_item_data or not current_item_data.get('url'): return
        
        invert_shortcuts = self.settings.get('invert_playback_shortcuts', False)
        play_audio_shortcut = "Ctrl+Enter" if invert_shortcuts else "Enter"
        play_video_shortcut = "Enter" if invert_shortcuts else "Ctrl+Enter"
        menu = QMenu(self)
        item_type = current_item_data.get('type')
        if item_type == 'video':
            act_dl_vid = QAction(_("Unduh Video Ini (Ctrl+Shift+D)"), self); act_dl_vid.triggered.connect(lambda chk=False, d=current_item_data: self.handle_triggered_action_with_data(d, 'download_video')); menu.addAction(act_dl_vid)
            act_dl_aud = QAction(_("Unduh Audio Ini (Ctrl+D)"), self); act_dl_aud.triggered.connect(lambda chk=False, d=current_item_data: self.handle_triggered_action_with_data(d, 'download_audio')); menu.addAction(act_dl_aud)
            menu.addSeparator()
            act_pv = QAction(f"{_('Putar Video')} ({play_video_shortcut})", self); act_pv.triggered.connect(lambda chk=False, d=current_item_data: self.handle_triggered_action_with_data(d, 'play_video')); menu.addAction(act_pv)
            act_pa = QAction(f"{_('Putar Audio Saja')} ({play_audio_shortcut})", self); act_pa.triggered.connect(lambda chk=False, d=current_item_data: self.handle_triggered_action_with_data(d, 'play_audio')); menu.addAction(act_pa)
            menu.addSeparator()
            act_cu = QAction(_("Salin URL Video"), self); act_cu.triggered.connect(lambda: self.handle_context_copy_url_with_data(current_item_data)); menu.addAction(act_cu)
            act_vy = QAction(_("Lihat di YouTube"), self); act_vy.triggered.connect(lambda: self.handle_context_view_on_youtube_with_data(current_item_data)); menu.addAction(act_vy)
        elif item_type == 'playlist_meta':
            act_vi = QAction(_("Lihat Isi Playlist (Enter)"), self); act_vi.triggered.connect(lambda chk=False, d=current_item_data: self.handle_triggered_action_with_data(d, 'view_playlist_items')); menu.addAction(act_vi)
            menu.addSeparator()
            act_cu_pl = QAction(_("Salin URL Playlist"), self); act_cu_pl.triggered.connect(lambda: self.handle_context_copy_url_with_data(current_item_data)); menu.addAction(act_cu_pl)
            act_vy_pl = QAction(_("Lihat Playlist di YouTube"), self); act_vy_pl.triggered.connect(lambda: self.handle_context_view_on_youtube_with_data(current_item_data)); menu.addAction(act_vy_pl)
        menu.exec(self.results_list_widget.mapToGlobal(position))

    def handle_context_copy_url_with_data(self, item_data):
        if item_data and item_data.get('url'): QApplication.clipboard().setText(item_data['url'])
        else: QMessageBox.warning(self, _("Gagal Salin"), _("URL tidak valid."))

    def handle_context_view_on_youtube_with_data(self, item_data):
        if item_data and item_data.get('url'): QDesktopServices.openUrl(QUrl(item_data['url']))
        else: QMessageBox.warning(self, _("Gagal Buka"), _("URL tidak valid."))

    def handle_download_all_list_items(self, download_type):
        if self.all_list_items_data:
            list_title_from_dialog = self.windowTitle().replace(f"{_('Isi')} {_('Playlist')}: ", "").replace(f"{_('Isi')} {_('Channel')}: ", "").split("...")[0]
            self.download_all_playlist_items_requested.emit(self.all_list_items_data, list_title_from_dialog, download_type)
            self.accept()
        else: QMessageBox.warning(self, _("Data Tidak Lengkap"), _("Tidak dapat memulai unduhan batch."))

    def handle_view_playlist_items_button_click(self):
        item = self.results_list_widget.currentItem();
        if item: data = item.data(Qt.ItemDataRole.UserRole)
        if item and data and data.get('type') == 'playlist_meta' and data.get('url'): self.trigger_action(item, 'view_playlist_items')
        else: QMessageBox.warning(self, _("Item Tidak Valid") if item else _("Tidak Ada Pilihan"), _("Pilih playlist valid.") if item else _("Pilih playlist dari daftar."))

    def handle_play_video_button_click(self):
        item = self.results_list_widget.currentItem()
        if item: self.trigger_action(item, 'play_video')
        else: QMessageBox.warning(self, _("Tidak Ada Pilihan"), _("Pilih item dari daftar untuk diputar sebagai video."))

    def handle_play_audio_button_click(self):
        item = self.results_list_widget.currentItem()
        if item: self.trigger_action(item, 'play_audio')
        else: QMessageBox.warning(self, _("Tidak Ada Pilihan"), _("Pilih item dari daftar untuk diputar sebagai audio."))

    def handle_download_video_button_click(self):
        item = self.results_list_widget.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole).get('type') == 'video':
            self.trigger_action(item, 'download_video')
        else:
            QMessageBox.warning(self, _("Pilihan Salah") if item else _("Tidak Ada Pilihan"), _("Pilih video dari daftar untuk diunduh sebagai video.") if item else _("Pilih video dari daftar."))

    def handle_download_audio_button_click(self):
        item = self.results_list_widget.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole).get('type') == 'video':
            self.trigger_action(item, 'download_audio')
        else:
            QMessageBox.warning(self, _("Pilihan Salah") if item else _("Tidak Ada Pilihan"), _("Pilih video dari daftar untuk diunduh sebagai audio.") if item else _("Pilih video dari daftar."))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject(); return
        current_item = self.results_list_widget.currentItem()
        if not current_item: super().keyPressEvent(event); return
        data = current_item.data(Qt.ItemDataRole.UserRole)
        if not data: super().keyPressEvent(event); return
        item_type = data.get('type')
        
        if item_type == 'video':
            invert_shortcuts = self.settings.get('invert_playback_shortcuts', False)
            play_audio_action = 'play_audio'
            play_video_action = 'play_video'
            
            if event.key() == Qt.Key.Key_D and event.modifiers() == Qt.KeyboardModifier.ControlModifier and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.trigger_action(current_item, 'download_audio')
            elif event.key() == Qt.Key.Key_D and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
                self.trigger_action(current_item, 'download_video')
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                is_ctrl_pressed = event.modifiers() == Qt.KeyboardModifier.ControlModifier
                if (is_ctrl_pressed and not invert_shortcuts) or (not is_ctrl_pressed and invert_shortcuts):
                    self.trigger_action(current_item, play_video_action)
                else:
                    self.trigger_action(current_item, play_audio_action)
            else:
                super().keyPressEvent(event)
        elif item_type == 'playlist_meta':
            if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                self.trigger_action(current_item, 'view_playlist_items')
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def trigger_action(self, item, action_type):
        self.results_list_widget.setCurrentItem(item); data = item.data(Qt.ItemDataRole.UserRole)
        if data and data.get('url'):
            self.parent().last_selected_search_item_url = data['url']
            self.action_triggered.emit({'url': data['url'], 'title': data['title'], 'action': action_type, 'type': data.get('type')})
        else: QMessageBox.warning(self, _("Aksi Gagal"), _("Item tidak punya URL valid."))

    def handle_double_click_action(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            item_type = data.get('type')
            default_action_key = self._normalize_double_click_action(
                self.settings.get('search_result_double_click_action', _("Unduh Video"))
            )
            
            action_to_perform = None
            if item_type == 'video':
                if default_action_key == "download_video": action_to_perform = 'download_video'
                elif default_action_key == "play_audio": action_to_perform = 'play_audio'
                elif default_action_key == "play_video": action_to_perform = 'play_video'
            elif item_type == 'playlist_meta':
                action_to_perform = 'view_playlist_items'
            if action_to_perform:
                self.trigger_action(item, action_to_perform)
            else:
                QMessageBox.information(
                    self,
                    _("Aksi Default Tidak Diketahui"),
                    f"{_('Tidak ada aksi default yang cocok untuk tipe item')} '{item_type}' {_('dengan pengaturan')} '{self._double_click_action_label()}'."
                )
        else:
            QMessageBox.warning(self, _("Aksi Gagal"), _("Item tidak punya data valid."))

    def format_duration(self, seconds):
        if seconds is None: return "N/A"
        try: s = int(seconds); m, s = divmod(s, 60); h, m = divmod(m, 60); return f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        except: return "N/A"
    
    def closeEvent(self, event):
        self.threadpool.clear()
        self.threadpool.waitForDone(-1)
        super().closeEvent(event)

    def restore_focus_and_selection(self, item_url_to_focus=None):
        url_to_check = item_url_to_focus or self.parent().last_selected_search_item_url
        if url_to_check:
            for i in range(self.results_list_widget.count()):
                item = self.results_list_widget.item(i)
                if not item: continue
                data = item.data(Qt.ItemDataRole.UserRole)
                if data and data.get('url') == url_to_check:
                    self.results_list_widget.setCurrentItem(item)
                    self.results_list_widget.scrollToItem(item)
                    break
        self.results_list_widget.setFocus(Qt.FocusReason.OtherFocusReason)
