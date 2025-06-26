import sys
import os
import re
import json
import yt_dlp
import requests
import tempfile
import subprocess
import webbrowser
import shutil
import time

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QComboBox, QProgressBar, QLabel,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QGridLayout,
    QListWidget, QListWidgetItem, QSpinBox, QCheckBox, QMenu, QStyle,
    QTextBrowser, QProgressDialog, QTextEdit, QStackedWidget
)
from PySide6.QtCore import (
    QThread, Signal, Qt, QUrl, QTimer, qVersion, QStandardPaths, QRunnable, 
    QThreadPool, QObject, QSize
)
from PySide6.QtGui import (
    QIcon, QKeySequence, QShortcut, QDesktopServices, QAction, QScreen,
    QKeyEvent, QMouseEvent, QPixmap
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

try:
    from nvda import connect as nvda_connect, disconnect as nvda_disconnect, speak as nvda_speak
    NVDA_CONTROL_AVAILABLE = True
except (ImportError, OSError):
    NVDA_CONTROL_AVAILABLE = False
    def nvda_connect(): pass
    def nvda_disconnect(): pass
    def nvda_speak(*args, **kwargs): pass

from config import *
from threads import (
    UpdateCheckThread, DownloadUpdateThread, SearchThread, PlaylistFetchThread, 
    ChannelFetchThread, DownloadThread, StreamInfoThread, ThumbnailDownloader
)

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tentang mrd YouTube Downloader")
        self.setMinimumSize(450, 320)
        layout = QVBoxLayout(self)
        self.info_text_browser = QTextBrowser(self)
        self.info_text_browser.setReadOnly(True); self.info_text_browser.setOpenExternalLinks(True)
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        yt_dlp_version = "N/A"
        try: yt_dlp_version = yt_dlp.version.__version__
        except AttributeError: pass
        info_content = f"""<html><head><style> a {{ color: #007bff; text-decoration: none; }} a:hover {{ text-decoration: underline; }} </style></head><body> <h2>mrd YouTube Downloader</h2><p>Versi Aplikasi: {CURRENT_APP_VERSION}</p> <p>Aplikasi untuk mengunduh video dan audio dari YouTube dengan mudah.</p> <p><strong>Pembuat:</strong> ridho</p><p><strong>UI Framework:</strong> PySide6</p> <p><strong>Versi Qt:</strong> {qVersion()}</p><p><strong>Versi Python:</strong> {python_version}</p> <p><strong>Versi yt-dlp:</strong> {yt_dlp_version}</p><hr> <p>Dibangun menggunakan pustaka yt-dlp untuk fungsionalitas unduhan inti.</p> <p>© 2024-2025 mrido1</p></body></html>"""
        self.info_text_browser.setHtml(info_content)
        self.info_text_browser.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        layout.addWidget(self.info_text_browser)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept); layout.addWidget(button_box)
        self.info_text_browser.setFocus()

class SettingsDialog(QDialog):
    settings_changed = Signal()
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pengaturan Aplikasi")
        self.setMinimumWidth(550)
        self.current_settings = current_settings.copy()
        layout = QVBoxLayout(self)
        dir_label = QLabel("Simpan ke:")
        default_output_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation)
        self.dir_line_edit = QLineEdit(self.current_settings.get('output_path', default_output_path))
        self.dir_line_edit.setReadOnly(True)
        dir_label.setBuddy(self.dir_line_edit)
        select_dir_button = QPushButton("Pilih Folder...")
        select_dir_button.clicked.connect(self.select_output_directory)
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_line_edit)
        dir_layout.addWidget(select_dir_button)
        layout.addLayout(dir_layout)
        general_group_layout = QGridLayout()
        theme_label = QLabel("Tema Aplikasi:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText(self.current_settings.get('theme', "Light"))
        theme_label.setBuddy(self.theme_combo)
        general_group_layout.addWidget(theme_label, 0, 0)
        general_group_layout.addWidget(self.theme_combo, 0, 1)
        self.clipboard_monitor_checkbox = QCheckBox("Pantau Clipboard untuk URL YouTube")
        self.clipboard_monitor_checkbox.setChecked(self.current_settings.get('monitor_clipboard', True))
        general_group_layout.addWidget(self.clipboard_monitor_checkbox, 1, 0, 1, 2)
        layout.addLayout(general_group_layout)
        
        search_results_label = QLabel("Jumlah Hasil Pencarian:")
        self.search_results_spinbox = QSpinBox()
        self.search_results_spinbox.setRange(1, 50)
        self.search_results_spinbox.setValue(self.current_settings.get('search_results_count', 10))
        search_results_label.setBuddy(self.search_results_spinbox)
        search_layout = QHBoxLayout()
        search_layout.addWidget(search_results_label)
        search_layout.addWidget(self.search_results_spinbox)
        layout.addLayout(search_layout)
        format_group_layout = QGridLayout()
        video_format_label = QLabel("Format Video Default:")
        self.video_format_combo_box = QComboBox()
        self.video_format_combo_box.addItems(["Video (MP4 - Kualitas Terbaik)", "Video (MKV - Kualitas Terbaik)", "Video (WEBM - Kualitas Terbaik)", "Video (AVI - Kompatibilitas)"])
        self.video_format_combo_box.setCurrentText(self.current_settings.get('video_format_choice', "Video (MP4 - Kualitas Terbaik)"))
        video_format_label.setBuddy(self.video_format_combo_box)
        
        audio_format_label = QLabel("Format Audio Default:")
        self.audio_format_combo_box = QComboBox()
        self.audio_format_combo_box.addItems(["Audio (MP3 - Kualitas Terbaik)", "Audio (WAV - Tanpa Kompresi)", "Audio (AAC - Kualitas Baik)", "Audio (OGG Vorbis - Open Source)", "Audio (FLAC - Lossless)"])
        self.audio_format_combo_box.setCurrentText(self.current_settings.get('audio_format_choice', "Audio (MP3 - Kualitas Terbaik)"))
        audio_format_label.setBuddy(self.audio_format_combo_box)
        
        self.embed_metadata_checkbox = QCheckBox("Sematkan Thumbnail & Metadata (untuk Audio)")
        self.embed_metadata_checkbox.setChecked(self.current_settings.get('embed_metadata', True))
        
        format_group_layout.addWidget(video_format_label, 0, 0)
        format_group_layout.addWidget(self.video_format_combo_box, 0, 1)
        format_group_layout.addWidget(audio_format_label, 1, 0)
        format_group_layout.addWidget(self.audio_format_combo_box, 1, 1)
        format_group_layout.addWidget(self.embed_metadata_checkbox, 2, 0, 1, 2)
        layout.addLayout(format_group_layout)
        actions_group_layout = QGridLayout()
        double_click_action_label = QLabel("Aksi Dobel Klik (Video):")
        self.double_click_action_combo = QComboBox()
        self.double_click_action_combo.addItems(["Unduh Video", "Putar Audio", "Putar Video"])
        self.double_click_action_combo.setCurrentText(self.current_settings.get('search_result_double_click_action', "Unduh Video"))
        double_click_action_label.setBuddy(self.double_click_action_combo)
        
        self.invert_playback_shortcuts_checkbox = QCheckBox("Balik Shortcut Putar (Enter/Ctrl+Enter)")
        self.invert_playback_shortcuts_checkbox.setChecked(self.current_settings.get('invert_playback_shortcuts', False))
        actions_group_layout.addWidget(double_click_action_label, 0, 0)
        actions_group_layout.addWidget(self.double_click_action_combo, 0, 1)
        actions_group_layout.addWidget(self.invert_playback_shortcuts_checkbox, 1, 0, 1, 2)
        layout.addLayout(actions_group_layout)
        self.show_completion_popup_checkbox = QCheckBox("Tampilkan Notifikasi Selesai Unduh")
        self.show_completion_popup_checkbox.setChecked(self.current_settings.get('show_completion_popup', True))
        layout.addWidget(self.show_completion_popup_checkbox)
        self.parallel_download_checkbox = QCheckBox("Gunakan akselerasi pararel (beta)")
        self.parallel_download_checkbox.setToolTip("Dapat mempercepat unduhan secara signifikan.")
        self.parallel_download_checkbox.setChecked(self.current_settings.get('use_parallel_download', False))
        self.parallel_download_checkbox.toggled.connect(self.on_parallel_download_toggled)
        layout.addWidget(self.parallel_download_checkbox)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def on_parallel_download_toggled(self, checked):
        if checked:
            aria2c_executable = "aria2c.exe" if sys.platform == "win32" else "aria2c"
            if not shutil.which(aria2c_executable):
                QMessageBox.warning(self, "gagal mengaktifkan fitur", "aria2c.exe nggak ketemu")
                self.parallel_download_checkbox.blockSignals(True)
                self.parallel_download_checkbox.setChecked(False)
                self.parallel_download_checkbox.blockSignals(False)

    def select_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Pilih Folder Penyimpanan", self.dir_line_edit.text())
        if directory: self.dir_line_edit.setText(directory)

    def accept_settings(self):
        self.current_settings['output_path'] = self.dir_line_edit.text()
        self.current_settings['theme'] = self.theme_combo.currentText()
        self.current_settings['monitor_clipboard'] = self.clipboard_monitor_checkbox.isChecked()
        self.current_settings['embed_metadata'] = self.embed_metadata_checkbox.isChecked()
        self.current_settings['video_format_choice'] = self.video_format_combo_box.currentText()
        self.current_settings['audio_format_choice'] = self.audio_format_combo_box.currentText()
        self.current_settings['search_results_count'] = self.search_results_spinbox.value()
        self.current_settings['show_completion_popup'] = self.show_completion_popup_checkbox.isChecked()
        self.current_settings['invert_playback_shortcuts'] = self.invert_playback_shortcuts_checkbox.isChecked()
        self.current_settings['search_result_double_click_action'] = self.double_click_action_combo.currentText()
        self.current_settings['use_parallel_download'] = self.parallel_download_checkbox.isChecked()
        
        self.settings_changed.emit()
        self.accept()

    def get_settings(self): return self.current_settings

class OperationProgressDialog(QDialog):
    def __init__(self, operation_text, parent=None):
        super().__init__(parent); self.setWindowTitle(operation_text); self.setMinimumWidth(350)
        layout = QVBoxLayout(self); self.status_label = QLabel(f"{operation_text}..."); self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label); self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0, 0); self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar); self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.Dialog); self.setModal(True)

class DownloadProgressDialog(QDialog):
    cancel_requested = Signal()
    
    def __init__(self, title, parent=None):
        super().__init__(parent); 
        self.setWindowTitle(f"Mengunduh: {title[:40]}...")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout(self)
        self.title_label = QLabel(f"Mengunduh: <b>{title}</b>")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - Memulai...")
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Status: Memulai unduhan...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        self.speed_eta_label = QLabel("Kecepatan: N/A, ETA: N/A")
        layout.addWidget(self.speed_eta_label)
        
        self.cancel_button = QPushButton("Batal")
        self.cancel_button.setToolTip("Batalkan unduhan (Esc)")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self.cancel_button)
        
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.Dialog)
        self.setModal(True)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_requested.emit()
        else:
            super().keyPressEvent(event)

    def update_title(self, title): 
        self.setWindowTitle(f"Mengunduh: {title[:40]}...")
        self.title_label.setText(f"Mengunduh: <b>{title}</b>")
        
    def update_progress(self, percentage, speed, eta): 
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{percentage}%")
        self.speed_eta_label.setText(f"Kecepatan: {speed}, ETA: {eta}")
        
    def update_status(self, message):
        self.status_label.setText(f"Status: {message}")
        if "Mengonversi" in message: 
            self.progress_bar.setRange(0,0)
            self.progress_bar.setFormat("Mengonversi...")
            self.speed_eta_label.setText("")
        elif self.progress_bar.minimum() == 0 and self.progress_bar.maximum() == 0 : 
            self.progress_bar.setRange(0,100)
            
    def download_complete(self, success, message):
        self.progress_bar.setRange(0,100)
        self.progress_bar.setValue(100 if success else self.progress_bar.value())
        self.progress_bar.setFormat("Selesai!" if success else "Gagal!")
        self.status_label.setText(f"Status: {message}")
        self.speed_eta_label.setText("")
        self.cancel_button.setEnabled(False)

class SearchResultsDialog(QDialog):
    action_triggered = Signal(dict)
    download_all_playlist_items_requested = Signal(list, str, str)
    def __init__(self, results, parent=None, result_type="video_search", list_title_str=None, original_list_url=None, settings=None):
        super().__init__(parent)
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
            list_type_name = "Playlist" if self.result_type == "playlist_items" else "Channel"
            item_count_text = "video" if self.result_type == "channel_items" else "item"
            title_text = f"Isi {list_type_name}: {self.list_title_str[:50]}{'...' if len(self.list_title_str) > 50 else ''}"
            
            self.download_all_videos_button = QPushButton(f"Unduh Semua Video ({len(results)})")
            self.download_all_videos_button.setToolTip(f"Unduh semua {len(results)} video dari '{self.list_title_str}' sebagai video.")
            self.download_all_videos_button.clicked.connect(lambda: self.handle_download_all_list_items('video'))
            layout.addWidget(self.download_all_videos_button)
            
            self.download_all_audios_button = QPushButton(f"Unduh Semua Audio ({len(results)})")
            self.download_all_audios_button.setToolTip(f"Unduh semua {len(results)} item dari '{self.list_title_str}' sebagai audio.")
            self.download_all_audios_button.clicked.connect(lambda: self.handle_download_all_list_items('audio'))
            layout.addWidget(self.download_all_audios_button)
        elif self.result_type == "playlist_search_results":
            title_text = "Hasil Pencarian Playlist"
        else: # video_search
            title_text = "Hasil Pencarian Video"
        self.setWindowTitle(title_text)
        self.results_list_widget = QListWidget()
        self.results_list_widget.setAccessibleName("Daftar hasil pencarian atau item playlist")
        self.results_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.results_list_widget.setIconSize(QSize(128, 72))
        self.results_list_widget.setWordWrap(True)
        if not results:
            self.results_list_widget.addItem("Memuat hasil...")
        else:
            self.add_results(results, is_initial=True)
        self.results_list_widget.itemDoubleClicked.connect(self.handle_double_click_action)
        layout.addWidget(self.results_list_widget)
        button_layout = QHBoxLayout()
        
        if self.result_type == "playlist_search_results":
            self.view_playlist_items_button = QPushButton("Lihat Isi Playlist")
            self.view_playlist_items_button.setToolTip("Lihat video di playlist (Enter atau Dobel Klik)")
            self.view_playlist_items_button.clicked.connect(self.handle_view_playlist_items_button_click)
            button_layout.addWidget(self.view_playlist_items_button)
        elif self.result_type in ["video_search", "playlist_items", "channel_items"]:
            self.download_video_button = QPushButton("Unduh Video")
            self.download_audio_button = QPushButton("Unduh Audio")
            self.play_video_button = QPushButton("Putar Video")
            self.play_audio_button = QPushButton("Putar Audio")
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

    def update_button_tooltips(self):
        default_double_click_action_text = self.settings.get('search_result_double_click_action', "Unduh Video").replace("Langsung ", "")
        invert_shortcuts = self.settings.get('invert_playback_shortcuts', False)
        play_audio_shortcut = "Ctrl+Enter" if invert_shortcuts else "Enter"
        play_video_shortcut = "Enter" if invert_shortcuts else "Ctrl+Enter"
            
        dl_vid_tt = "Unduh sebagai video (Ctrl+Shift+D)"
        if default_double_click_action_text == "Unduh Video": dl_vid_tt += " / Dobel Klik"
        self.download_video_button.setToolTip(dl_vid_tt)
        
        self.download_audio_button.setToolTip("Unduh sebagai audio (Ctrl+D)")
        
        play_vid_tt = f"Putar video ({play_video_shortcut})"
        if default_double_click_action_text == "Putar Video": play_vid_tt += " / Dobel Klik"
        self.play_video_button.setToolTip(play_vid_tt)
        
        play_aud_tt = f"Putar audio ({play_audio_shortcut})"
        if default_double_click_action_text == "Putar Audio": play_aud_tt += " / Dobel Klik"
        self.play_audio_button.setToolTip(play_aud_tt)
        
    def _create_and_add_item(self, entry):
        if not entry: return
        item_text, list_item_data = "", {}
        
        if self.result_type == "playlist_search_results":
            title = entry.get('title', 'Playlist Tanpa Judul')
            uploader = entry.get('uploader', entry.get('channel', 'N/A'))
            item_count = str(entry.get('playlist_count', entry.get('item_count', 'N/A')))
            url = entry.get('webpage_url', entry.get('url'))
            item_text = f"Judul Playlist: {title}\nChannel: {uploader} | Jumlah Video: {item_count}"
            list_item_data = {'url': url, 'title': title, 'type': 'playlist_meta'}
            item = QListWidgetItem(item_text)
        else: 
            title = entry.get('title', 'Tanpa Judul')
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
            
            item_text = f"Judul: {title}\nChannel: {uploader}\nDurasi: {dur_str}"
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
        
        default_double_click_action_text = self.settings.get('search_result_double_click_action', "Unduh Video").replace("Langsung ", "")
        
        if self.result_type in ["playlist_items", "channel_items"]:
            list_type_name = "Playlist" if self.result_type == "playlist_items" else "Channel"
            item_count_text = "video" if self.result_type == "channel_items" else "item"
            info_label_text = f"{list_type_name} '{self.list_title_str}' berisi {current_count} {item_count_text}. Dobel klik untuk: {default_double_click_action_text}."
        elif self.result_type == "playlist_search_results":
            status = f"Ditemukan {current_count} playlist." if self.total_expected_results == 0 or self.total_expected_results == current_count else f"Menampilkan {current_count} dari {self.total_expected_results} playlist."
            info_label_text = f"{status} Dobel klik untuk melihat isi playlist."
        else: # video_search
            status = f"Ditemukan {current_count} video." if self.total_expected_results == 0 or self.total_expected_results == current_count else f"Menampilkan {current_count} dari {self.total_expected_results} video."
            info_label_text = f"{status} Dobel klik untuk: {default_double_click_action_text}."
            
        self.info_label.setText(info_label_text)
        
    def add_results(self, new_entries, is_initial=False):
        if is_initial and self.results_list_widget.count() > 0:
            if "Memuat hasil..." in self.results_list_widget.item(0).text():
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
            QMessageBox.warning(self, "Aksi Gagal", "Data item tidak valid atau URL tidak ada.")

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
            act_dl_vid = QAction("Unduh Video Ini (Ctrl+Shift+D)", self); act_dl_vid.triggered.connect(lambda chk=False, d=current_item_data: self.handle_triggered_action_with_data(d, 'download_video')); menu.addAction(act_dl_vid)
            act_dl_aud = QAction("Unduh Audio Ini (Ctrl+D)", self); act_dl_aud.triggered.connect(lambda chk=False, d=current_item_data: self.handle_triggered_action_with_data(d, 'download_audio')); menu.addAction(act_dl_aud)
            menu.addSeparator()
            act_pv = QAction(f"Putar Video ({play_video_shortcut})", self); act_pv.triggered.connect(lambda chk=False, d=current_item_data: self.handle_triggered_action_with_data(d, 'play_video')); menu.addAction(act_pv)
            act_pa = QAction(f"Putar Audio Saja ({play_audio_shortcut})", self); act_pa.triggered.connect(lambda chk=False, d=current_item_data: self.handle_triggered_action_with_data(d, 'play_audio')); menu.addAction(act_pa)
            menu.addSeparator()
            act_cu = QAction("Salin URL Video", self); act_cu.triggered.connect(lambda: self.handle_context_copy_url_with_data(current_item_data)); menu.addAction(act_cu)
            act_vy = QAction("Lihat di YouTube", self); act_vy.triggered.connect(lambda: self.handle_context_view_on_youtube_with_data(current_item_data)); menu.addAction(act_vy)
        elif item_type == 'playlist_meta':
            act_vi = QAction("Lihat Isi Playlist (Enter)", self); act_vi.triggered.connect(lambda chk=False, d=current_item_data: self.handle_triggered_action_with_data(d, 'view_playlist_items')); menu.addAction(act_vi)
            menu.addSeparator()
            act_cu_pl = QAction("Salin URL Playlist", self); act_cu_pl.triggered.connect(lambda: self.handle_context_copy_url_with_data(current_item_data)); menu.addAction(act_cu_pl)
            act_vy_pl = QAction("Lihat Playlist di YouTube", self); act_vy_pl.triggered.connect(lambda: self.handle_context_view_on_youtube_with_data(current_item_data)); menu.addAction(act_vy_pl)
        menu.exec(self.results_list_widget.mapToGlobal(position))

    def handle_context_copy_url_with_data(self, item_data):
        if item_data and item_data.get('url'): QApplication.clipboard().setText(item_data['url'])
        else: QMessageBox.warning(self, "Gagal Salin", "URL tidak valid.")

    def handle_context_view_on_youtube_with_data(self, item_data):
        if item_data and item_data.get('url'): QDesktopServices.openUrl(QUrl(item_data['url']))
        else: QMessageBox.warning(self, "Gagal Buka", "URL tidak valid.")

    def handle_download_all_list_items(self, download_type):
        if self.all_list_items_data:
            list_title_from_dialog = self.windowTitle().replace("Isi Playlist: ", "").replace("Isi Channel: ", "").split("...")[0]
            self.download_all_playlist_items_requested.emit(self.all_list_items_data, list_title_from_dialog, download_type)
            self.accept()
        else: QMessageBox.warning(self, "Data Tidak Lengkap", "Tidak dapat memulai unduhan batch.")

    def handle_view_playlist_items_button_click(self):
        item = self.results_list_widget.currentItem();
        if item: data = item.data(Qt.ItemDataRole.UserRole)
        if item and data and data.get('type') == 'playlist_meta' and data.get('url'): self.trigger_action(item, 'view_playlist_items')
        else: QMessageBox.warning(self, "Item Tidak Valid" if item else "Tidak Ada Pilihan", "Pilih playlist valid." if item else "Pilih playlist dari daftar.")

    def handle_play_video_button_click(self):
        item = self.results_list_widget.currentItem()
        if item: self.trigger_action(item, 'play_video')
        else: QMessageBox.warning(self, "Tidak Ada Pilihan", "Pilih item dari daftar untuk diputar sebagai video.")

    def handle_play_audio_button_click(self):
        item = self.results_list_widget.currentItem()
        if item: self.trigger_action(item, 'play_audio')
        else: QMessageBox.warning(self, "Tidak Ada Pilihan", "Pilih item dari daftar untuk diputar sebagai audio.")

    def handle_download_video_button_click(self):
        item = self.results_list_widget.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole).get('type') == 'video':
            self.trigger_action(item, 'download_video')
        else:
            QMessageBox.warning(self, "Pilihan Salah" if item else "Tidak Ada Pilihan", "Pilih video dari daftar untuk diunduh sebagai video." if item else "Pilih video dari daftar.")

    def handle_download_audio_button_click(self):
        item = self.results_list_widget.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole).get('type') == 'video':
            self.trigger_action(item, 'download_audio')
        else:
            QMessageBox.warning(self, "Pilihan Salah" if item else "Tidak Ada Pilihan", "Pilih video dari daftar untuk diunduh sebagai audio." if item else "Pilih video dari daftar.")

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
        if data and data.get('url'): self.action_triggered.emit({'url': data['url'], 'title': data['title'], 'action': action_type, 'type': data.get('type')})
        else: QMessageBox.warning(self, "Aksi Gagal", "Item tidak punya URL valid.")

    def handle_double_click_action(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            item_type = data.get('type')
            default_action_key = self.settings.get('search_result_double_click_action', "Unduh Video")
            
            action_to_perform = None
            if item_type == 'video':
                if default_action_key == "Unduh Video": action_to_perform = 'download_video'
                elif default_action_key == "Putar Audio": action_to_perform = 'play_audio'
                elif default_action_key == "Putar Video": action_to_perform = 'play_video'
            elif item_type == 'playlist_meta':
                action_to_perform = 'view_playlist_items'
            if action_to_perform:
                self.trigger_action(item, action_to_perform)
            else:
                QMessageBox.information(self, "Aksi Default Tidak Diketahui", f"Tidak ada aksi default yang cocok untuk tipe item '{item_type}' dengan pengaturan '{default_action_key}'.")
        else:
            QMessageBox.warning(self, "Aksi Gagal", "Item tidak punya data valid.")

    def format_duration(self, seconds):
        if seconds is None: return "N/A"
        try: s = int(seconds); m, s = divmod(s, 60); h, m = divmod(m, 60); return f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        except: return "N/A"
    
    def closeEvent(self, event):
        self.threadpool.clear()
        self.threadpool.waitForDone(-1)
        super().closeEvent(event)

class VideoPlayerWidget(QWidget):
    close_requested = Signal()
    download_requested = Signal(str)
    playback_rate_change_requested = Signal(float)
    SEEK_INTERVAL = 5000

    def __init__(self, media_player, video_widget, parent=None, settings=None):
        super().__init__(parent)
        self.media_player = media_player
        self.video_widget = video_widget
        self.settings = settings if settings else {}
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setMouseTracking(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.title_label = QLabel(self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("background-color: rgba(0, 0, 0, 0.6); color: white; padding: 10px; font-size: 14pt; font-weight: bold;")
        self.title_label.setWordWrap(True)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        video_layout = QStackedWidget()
        video_layout.addWidget(self.video_widget)
        
        self.controls_widget = QWidget(self)
        self.controls_widget.setStyleSheet("background-color: rgba(0,0,0,0.6);")
        self.controls_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        controls_v_layout = QVBoxLayout(self.controls_widget)
        controls_v_layout.setContentsMargins(0, 0, 0, 10)
        controls_v_layout.addStretch()
        
        controls_layout_internal = QHBoxLayout()
        controls_layout_internal.setContentsMargins(10, 0, 10, 0)
        self.play_pause_button = QPushButton("Jeda")
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.play_pause_button.setStyleSheet("color: white; background-color: transparent; border: 1px solid white; padding: 8px 16px; border-radius: 4px;")
        
        self.stop_button_dialog = QPushButton("Hentikan & Tutup")
        self.stop_button_dialog.clicked.connect(self.close_requested.emit)
        self.stop_button_dialog.setStyleSheet("color: white; background-color: transparent; border: 1px solid white; padding: 8px 16px; border-radius: 4px;")
        
        controls_layout_internal.addStretch()
        controls_layout_internal.addWidget(self.play_pause_button)
        controls_layout_internal.addWidget(self.stop_button_dialog)
        controls_layout_internal.addStretch()
        controls_v_layout.addLayout(controls_layout_internal)
        main_player_layout = QVBoxLayout()
        main_player_layout.setContentsMargins(0,0,0,0)
        main_player_layout.setSpacing(0)
        main_player_layout.addWidget(self.title_label)
        main_player_layout.addStretch()
        main_player_layout.addWidget(self.controls_widget)
        
        player_container_widget = QWidget()
        player_container_widget.setLayout(main_player_layout)
        
        video_layout.addWidget(player_container_widget)
        layout.addWidget(video_layout)
        self.media_player.playbackStateChanged.connect(self.update_play_pause_button_text)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.hide_controls_timer = QTimer(self)
        self.hide_controls_timer.setSingleShot(True)
        self.hide_controls_timer.timeout.connect(self.hide_controls)
        
        self.update_play_pause_button_text(self.media_player.playbackState())
        self.setup_autohide_from_settings()

    def setup_autohide_from_settings(self):
        delay_text = self.settings.get('autohide_delay', '5 detik')
        if delay_text == "Tidak Pernah":
            self.autohide_ms = -1
        else:
            try:
                self.autohide_ms = int(delay_text.split(' ')[0]) * 1000
            except (ValueError, IndexError):
                self.autohide_ms = 5000
        
        if self.autohide_ms > 0:
            self.reset_hide_controls_timer()
        else:
            self.show_controls()

    def update_title(self, title):
        self.title_label.setText(title)

    def reset_hide_controls_timer(self):
        if self.autohide_ms > 0:
            self.show_controls()
            self.hide_controls_timer.start(self.autohide_ms)

    def show_controls(self):
        self.title_label.setVisible(True)
        self.controls_widget.setVisible(True)
        self.unsetCursor()

    def hide_controls(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.title_label.setVisible(False)
            self.controls_widget.setVisible(False)
            self.setCursor(Qt.CursorShape.BlankCursor)

    def enterEvent(self, event: QMouseEvent):
        self.reset_hide_controls_timer()
        super().enterEvent(event)
        
    def mouseMoveEvent(self, event: QMouseEvent):
        self.reset_hide_controls_timer()
        super().mouseMoveEvent(event)

    def toggle_play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
        self.reset_hide_controls_timer()

    def update_play_pause_button_text(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_button.setText("Jeda")
            self.play_pause_button.setToolTip("Jeda (Spasi)")
            if self.autohide_ms > 0: self.reset_hide_controls_timer()
        else:
            self.play_pause_button.setText("Putar")
            self.play_pause_button.setToolTip("Lanjutkan (Spasi)")
            if self.hide_controls_timer.isActive(): self.hide_controls_timer.stop()
            self.show_controls()

    def keyPressEvent(self, event):
        self.reset_hide_controls_timer()
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close_requested.emit()
        elif key == Qt.Key.Key_Space:
            self.toggle_play_pause()
        elif key == Qt.Key.Key_Left:
            self.media_player.setPosition(max(0, self.media_player.position() - self.SEEK_INTERVAL))
        elif key == Qt.Key.Key_Right:
            self.media_player.setPosition(self.media_player.position() + self.SEEK_INTERVAL)
        elif event.key() == Qt.Key.Key_Up and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.playback_rate_change_requested.emit(0.25)
        elif event.key() == Qt.Key.Key_Down and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.playback_rate_change_requested.emit(-0.25)
        elif event.key() == Qt.Key.Key_D and event.modifiers() == Qt.KeyboardModifier.ControlModifier and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.download_requested.emit('audio')
        elif event.key() == Qt.Key.Key_D and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            self.download_requested.emit('video')
        else:
            super().keyPressEvent(event)

class AudioPlayerWidget(QWidget):
    close_requested = Signal()
    download_requested = Signal(str)
    playback_rate_change_requested = Signal(float)
    SEEK_INTERVAL = 5000

    def __init__(self, media_player, parent=None):
        super().__init__(parent)
        self.media_player = media_player
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("background-color: #2c3e50;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30,30,30,30)
        
        self.title_label = QLabel("Pemutar Audio")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 28px; color: white; font-weight: bold; margin-bottom: 15px;")
        layout.addWidget(self.title_label)
        
        self.status_label = QLabel("Memuat audio...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 18px; color: lightgray; margin-bottom: 20px;")
        layout.addWidget(self.status_label)
        
        layout.addStretch(1)
        self.controls_layout = QHBoxLayout()
        
        self.play_pause_button = QPushButton("Jeda")
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.play_pause_button.setStyleSheet("QPushButton { color: white; background-color: #3498db; border: none; padding: 12px 25px; font-size: 16px; border-radius: 5px;} QPushButton:hover { background-color: #2980b9; }")
        self.play_pause_button.setMinimumHeight(40)
        
        self.stop_button_dialog = QPushButton("Hentikan & Tutup")
        self.stop_button_dialog.clicked.connect(self.close_requested.emit)
        self.stop_button_dialog.setStyleSheet("QPushButton { color: white; background-color: #e74c3c; border: none; padding: 12px 25px; font-size: 16px; border-radius: 5px;} QPushButton:hover { background-color: #c0392b; }")
        self.stop_button_dialog.setMinimumHeight(40)
        
        self.controls_layout.addStretch()
        self.controls_layout.addWidget(self.play_pause_button)
        self.controls_layout.addSpacing(20)
        self.controls_layout.addWidget(self.stop_button_dialog)
        self.controls_layout.addStretch()
        
        layout.addLayout(self.controls_layout)
        layout.addStretch(1)
        
        self.media_player.playbackStateChanged.connect(self.update_controls_on_state_change)
        self.media_player.positionChanged.connect(self.update_status_labels)
        self.media_player.durationChanged.connect(self.update_status_labels)
        self.update_controls_on_state_change(self.media_player.playbackState())
        self.update_status_labels()
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def update_title(self, title):
        self.title_label.setText(title)

    def format_duration_ms(self, ms):
        try:
            if not isinstance(ms, (int, float)) or ms < 0: return "00:00"
            s_total = round(ms / 1000.0)
            m_total, s_val = divmod(s_total, 60)
            h_val, m_val = divmod(m_total, 60)
            return f"{int(h_val):d}:{int(m_val):02d}:{int(s_val):02d}" if h_val > 0 else f"{int(m_val):02d}:{int(s_val):02d}"
        except Exception: return "00:00"

    def update_status_labels(self):
        pos, dur, state = self.media_player.position(), self.media_player.duration(), self.media_player.playbackState()
        status_text = f"{self.format_duration_ms(pos)} / {self.format_duration_ms(dur)}"
        if state == QMediaPlayer.PlaybackState.PlayingState: self.status_label.setText(f"Memutar: {status_text}")
        elif state == QMediaPlayer.PlaybackState.PausedState: self.status_label.setText(f"Dijeda: {status_text}")
        else: self.status_label.setText(f"Berhenti: {status_text}")

    def toggle_play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState: self.media_player.pause()
        else: self.media_player.play()

    def update_controls_on_state_change(self, state):
        self.update_status_labels()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_button.setText("Jeda")
            self.play_pause_button.setToolTip("Jeda (Spasi)")
        else:
            self.play_pause_button.setText("Putar")
            self.play_pause_button.setToolTip("Lanjutkan (Spasi)")

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close_requested.emit()
        elif key == Qt.Key.Key_Space:
            self.toggle_play_pause()
        elif key == Qt.Key.Key_Left:
            self.media_player.setPosition(max(0, self.media_player.position() - self.SEEK_INTERVAL))
        elif key == Qt.Key.Key_Right:
            self.media_player.setPosition(self.media_player.position() + self.SEEK_INTERVAL)
        elif event.key() == Qt.Key.Key_Up and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.playback_rate_change_requested.emit(0.25)
        elif event.key() == Qt.Key.Key_Down and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.playback_rate_change_requested.emit(-0.25)
        elif event.key() == Qt.Key.Key_D and event.modifiers() == Qt.KeyboardModifier.ControlModifier and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.download_requested.emit('audio')
        elif event.key() == Qt.Key.Key_D and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            self.download_requested.emit('video')
        else:
            super().keyPressEvent(event)

class MainWindow(QMainWindow):
    BASE_TITLE = "mrd YouTube downloader"
    def __init__(self):
        super().__init__()
        self._is_closing_app = False
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        
        self.video_widget = QVideoWidget() 
        self.video_player_widget = None
        self.audio_player_widget = None
        self.download_progress_dialog = None
        self.operation_progress_dialog = None
        self.active_search_results_dialog = None
        self.last_selected_search_item_url = None
        self.last_downloaded_item_info = None
        self.current_list_batch_download_active = False
        self.update_check_thread = None
        self.download_update_thread = None
        self.update_progress_dialog = None
        self.sfx_save_path = ""
        self._restore_focus_to_input_after_manual_check = False
        self.download_initiated_from_search_dialog = False
        self.settings_dialog_instance = None
        self.original_geometry = None
        self._is_initial_startup_check = True
        self.last_clipboard_text = ""
        self.stream_info_thread = None
        self.download_thread = None
        self.search_thread = None
        self.playlist_fetch_thread = None
        self.channel_fetch_thread = None
        self.media_player.errorChanged.connect(self.handle_media_player_error)
        self.media_player.playbackStateChanged.connect(self.handle_media_player_state_changed)
        self.setWindowTitle(self.BASE_TITLE)
        self.set_initial_window_geometry()
        self.current_video_title_for_window = ""
        
        self.settings = DEFAULT_SETTINGS.copy()
        self.load_app_settings()
        if self.settings.get('use_parallel_download', False):
            aria2c_executable = "aria2c.exe" if sys.platform == "win32" else "aria2c"
            if not shutil.which(aria2c_executable):
                QMessageBox.warning(self, "Peringatan", 
                                    "File yang diperlukan untuk fitur akselerasi download nggak ada. Fitur akan dinonaktifkan")
                self.settings['use_parallel_download'] = False
                self.save_app_settings(show_error=False)
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        self.main_view_widget = QWidget()
        self.stacked_widget.addWidget(self.main_view_widget)
        
        main_layout = QVBoxLayout(self.main_view_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        self._create_menu_bar()
        input_layout = QHBoxLayout()
        self.url_input_label = QLabel()
        self.input_line_edit = QLineEdit()
        self.input_line_edit.returnPressed.connect(self.process_input)
        self.url_input_label.setBuddy(self.input_line_edit)
        input_layout.addWidget(self.url_input_label)
        input_layout.addWidget(self.input_line_edit, 1)
        input_label = QLabel("Tipe:")
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["Video", "Playlist", "Channel"])
        self.search_type_combo.setToolTip("Pilih jenis input jika bukan URL pasti")
        self.search_type_combo.currentTextChanged.connect(self._update_placeholder_text)
        self._update_placeholder_text(self.search_type_combo.currentText())
        input_label.setBuddy(self.search_type_combo)
        input_layout.addWidget(input_label)
        input_layout.addWidget(self.search_type_combo)
        self.go_button = QPushButton("Go!")
        self.go_button.setObjectName("go_button")
        self.go_button.clicked.connect(self.process_input)
        input_layout.addWidget(self.go_button)
        main_layout.addLayout(input_layout)
        
        action_buttons_layout = QHBoxLayout()
        self.settings_button = QPushButton("Pengaturan...")
        self.settings_button.setObjectName("settings_button")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        self.info_button = QPushButton("Info")
        self.info_button.setObjectName("info_button")
        self.info_button.clicked.connect(self.show_about_dialog)
        action_buttons_layout.addStretch()
        action_buttons_layout.addWidget(self.settings_button)
        action_buttons_layout.addWidget(self.info_button)
        main_layout.addLayout(action_buttons_layout)
        
        self.main_progress_bar = QProgressBar()
        self.main_progress_bar.setVisible(False)
        main_layout.addWidget(self.main_progress_bar)
        
        self.status_label = QLabel("Siap. Masukkan URL atau kata kunci.")
        self.status_label.setWordWrap(True)
        self.status_label.setProperty("accessibleLiveRegion", "polite")
        main_layout.addWidget(self.status_label)
        main_layout.addStretch()
        
        self.update_window_title_status("Siap")
        self.setup_shortcuts()
        self.apply_theme()
        self.init_clipboard_monitor()
        
        QTimer.singleShot(0, self.input_line_edit.setFocus)
        QTimer.singleShot(2000, lambda: self.initiate_update_check(manual_check=False))

    def apply_theme(self):
        theme = self.settings.get("theme", "Light")
        if theme == "Dark":
            self.setStyleSheet(DARK_THEME_STYLESHEET)
        else:
            self.setStyleSheet(LIGHT_THEME_STYLESHEET)

    def init_clipboard_monitor(self):
        if not hasattr(self, 'clipboard_timer'):
            self.clipboard_timer = QTimer(self)
            self.clipboard_timer.setInterval(2000)
            self.clipboard_timer.timeout.connect(self.check_clipboard)
        if self.settings.get('monitor_clipboard', True):
            if not self.clipboard_timer.isActive():
                self.clipboard_timer.start()
        else:
            if self.clipboard_timer.isActive():
                self.clipboard_timer.stop()

    def check_clipboard(self):
        if QApplication.activeModalWidget() is not None:
            return
        clipboard = QApplication.clipboard()
        current_text = clipboard.text().strip()
        if not current_text or current_text == self.last_clipboard_text:
            return
        self.last_clipboard_text = current_text
        if self.is_valid_youtube_url(current_text) and not self.is_youtube_channel_url(current_text):
             if self.is_valid_youtube_video_url(current_text) or self.is_potential_playlist_url(current_text):
                self.activateWindow()
                self.handle_direct_video_url_dialog(current_text)

    def _update_placeholder_text(self, text):
        self.url_input_label.setText(f"URL / Kata Kunci {text}:")
        self.input_line_edit.setPlaceholderText(f"Masukkan URL atau kata kunci {text.lower()}")

    def keyPressEvent(self, event: QKeyEvent):
        if self.stacked_widget.currentWidget() != self.main_view_widget:
            super().keyPressEvent(event)
            return
        current_focus = QApplication.focusWidget()
        key_text = event.text()
        
        is_input_like_widget = isinstance(current_focus, (QLineEdit, QTextEdit, QListWidget, QSpinBox, QComboBox))
        has_modifier = event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)
        if key_text and key_text.isprintable() and not has_modifier and not is_input_like_widget:
            if self.input_line_edit.isEnabled():
                self.input_line_edit.setFocus()
                self.input_line_edit.setText(key_text)
                self.input_line_edit.end(False)
        else:
            super().keyPressEvent(event)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        self.open_download_folder_action = QAction("Buka Folder Unduhan", self)
        self.open_download_folder_action.triggered.connect(self.open_current_download_folder)
        file_menu.addAction(self.open_download_folder_action)
        self.clear_input_action = QAction("Bersihkan Input", self)
        self.clear_input_action.setShortcut(QKeySequence("Ctrl+L"))
        self.clear_input_action.triggered.connect(self.clear_input_field)
        file_menu.addAction(self.clear_input_action)
        file_menu.addSeparator()
        self.settings_action = QAction("Pengaturan...", self)
        self.settings_action.triggered.connect(self.open_settings_dialog)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        file_menu.addAction(self.settings_action)
        file_menu.addSeparator()
        exit_action = QAction("Keluar", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        file_menu.addAction(exit_action)
        tools_menu = menu_bar.addMenu("&Alat")
        self.paste_and_go_action = QAction("Tempel & Proses", self)
        self.paste_and_go_action.setShortcut(QKeySequence("Ctrl+Shift+V"))
        self.paste_and_go_action.triggered.connect(self.paste_and_process_input)
        tools_menu.addAction(self.paste_and_go_action)
        
        help_menu = menu_bar.addMenu("&Bantuan")
        self.check_update_action = QAction("Cek Pembaruan...", self)
        self.check_update_action.triggered.connect(lambda: self.initiate_update_check(manual_check=True))
        help_menu.addAction(self.check_update_action)
        
        self.view_logs_action = QAction("Lihat Log Debug", self)
        self.view_logs_action.triggered.connect(self.open_debug_log)
        help_menu.addAction(self.view_logs_action)
        
        help_menu.addSeparator()
        self.debug_mode_action = QAction("Mode Debug", self)
        self.debug_mode_action.setCheckable(True)
        self.debug_mode_action.setChecked(_GLOBAL_DEBUG_MODE)
        self.debug_mode_action.triggered.connect(self.toggle_debug_mode)
        help_menu.addAction(self.debug_mode_action)
        
        help_menu.addSeparator()
        self.about_action = QAction("Tentang Aplikasi...", self)
        self.about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(self.about_action)

    def set_status_text(self, text):
        self.status_label.setText(text)
        if NVDA_CONTROL_AVAILABLE:
            nvda_speak(text, interrupt=True)

    def toggle_debug_mode(self, checked):
        global _GLOBAL_DEBUG_MODE
        _GLOBAL_DEBUG_MODE = checked
        self.settings['debug_mode'] = checked
        self.save_app_settings()
        if checked:
            self.set_status_text("Mode Debug Diaktifkan. Log akan dicetak/disimpan.")
            dprint("Mode Debug Diaktifkan via menu.")
        else:
            self.set_status_text("Mode Debug Dinonaktifkan.")
        self.update_window_title_status("Siap")

    def open_debug_log(self):
        if not _GLOBAL_DEBUG_MODE and not os.path.exists(LOG_FILE_PATH):
            QMessageBox.information(self, "Mode Debug Nonaktif", "Mode debug saat ini nonaktif dan file log tidak ditemukan.\nAktifkan mode debug dan lakukan beberapa aksi untuk membuat log.")
            self.set_status_text("File log tidak ditemukan (mode debug nonaktif).")
            return
        
        if os.path.exists(LOG_FILE_PATH):
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(LOG_FILE_PATH))
                self.set_status_text(f"Membuka file log: {LOG_FILE_PATH}")
            except Exception as e:
                QMessageBox.warning(self, "Gagal Buka Log", f"Tidak dapat membuka file log: {LOG_FILE_PATH}\nError: {str(e)}")
                self.set_status_text("Gagal membuka file log.")
        else:
            QMessageBox.information(self, "Log Tidak Ditemukan", f"File log tidak ditemukan di: {LOG_FILE_PATH}\nLog akan dibuat jika mode debug aktif dan ada aktivitas.")
            self.set_status_text("File log belum ada.")

    def open_current_download_folder(self):
        download_path = self.settings.get('output_path', '')
        if download_path and os.path.isdir(download_path):
            self.open_location(download_path)
            self.set_status_text(f"Membuka folder unduhan: {download_path}")
        else:
            QMessageBox.warning(self, "Folder Tidak Ditemukan", f"Folder unduhan '{download_path}' tidak valid atau tidak ada. Cek pengaturan.")
            self.set_status_text("Gagal membuka folder unduhan.")

    def clear_input_field(self):
        self.input_line_edit.clear()
        self.set_status_text("Input field dibersihkan.")
        self.input_line_edit.setFocus()

    def paste_and_process_input(self):
        clipboard = QApplication.clipboard()
        clipboard_text = clipboard.text()
        if clipboard_text:
            self.input_line_edit.setText(clipboard_text)
            self.set_status_text(f"Teks dari clipboard ditempel: {clipboard_text[:50]}...")
            self.process_input()
        else:
            QMessageBox.information(self, "Clipboard Kosong", "Tidak ada teks di clipboard untuk ditempel.")
            self.set_status_text("Clipboard kosong.")

    def _try_restore_focus_after_manual_check(self):
        if self._restore_focus_to_input_after_manual_check:
            self.input_line_edit.setFocus()
        self._restore_focus_to_input_after_manual_check = False

    def initiate_update_check(self, manual_check=True):
        if self.update_check_thread and self.update_check_thread.isRunning():
            if manual_check: QMessageBox.information(self, "Cek Pembaruan", "Pengecekan pembaruan sedang berjalan.")
            return
        if manual_check:
            self.set_status_text("Mengecek pembaruan...")
            self._restore_focus_to_input_after_manual_check = (QApplication.focusWidget() == self.input_line_edit)
        else:
            self._restore_focus_to_input_after_manual_check = False
        self.update_check_thread = UpdateCheckThread(CURRENT_APP_VERSION, VERSION_INFO_URL, self)
        self.update_check_thread.update_available.connect(lambda info: self.handle_update_available(info, manual_check))
        self.update_check_thread.no_update_found.connect(lambda msg: self.handle_no_update_found(msg, manual_check))
        self.update_check_thread.update_check_error.connect(lambda msg: self.handle_update_check_error(msg, manual_check))
        self.update_check_thread.finished.connect(self._try_restore_focus_after_manual_check)
        self.update_check_thread.finished.connect(self._on_any_thread_finished)
        self.set_ui_busy_state(True, "update_checking")
        self.update_check_thread.start()

    def handle_update_available(self, version_info, manual_check):
        latest_version = version_info.get("latest_version")
        download_url_sfx = version_info.get("download_url_sfx")
        changelog = version_info.get("changelog", "Tidak ada catatan perubahan.")
        self.set_status_text(f"Pembaruan v{latest_version} tersedia.")
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Pembaruan Tersedia")
        msg_box.setText(f"Versi baru (v{latest_version}) tersedia!\nAnda menggunakan v{CURRENT_APP_VERSION}.\n\nCatatan Perubahan:\n{changelog}")
        msg_box.setInformativeText("Apakah Anda ingin mengunduh dan menginstal pembaruan sekarang?\n\nAplikasi akan ditutup dan updater akan berjalan.")
        yes_button = msg_box.addButton("Ya, Unduh & Instal", QMessageBox.ButtonRole.YesRole)
        no_button = msg_box.addButton("Nanti Saja", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(yes_button)
        msg_box.exec()
        if msg_box.clickedButton() == yes_button:
            self.start_update_download(download_url_sfx)
        else:
            if manual_check: self.set_status_text("Pembaruan ditunda oleh pengguna.")
            self.set_ui_busy_state(False, "update_available_declined")
            self._try_restore_focus_after_manual_check()

    def handle_no_update_found(self, message, manual_check):
        if manual_check:
            self.set_status_text(message)
            QMessageBox.information(self, "Cek Pembaruan", message)

    def handle_update_check_error(self, error_message, manual_check):
        if manual_check:
            self.set_status_text(f"Error cek pembaruan: {error_message}")
            QMessageBox.warning(self, "Error Cek Pembaruan", error_message)
        elif "URL info versi belum diatur" in error_message and VERSION_INFO_URL == "URL_GIST_JSON_LO_DISINI":
             QMessageBox.warning(self, "Konfigurasi Update", "URL untuk info versi belum diatur di kode.\nSilakan atur konstanta VERSION_INFO_URL.")

    def start_update_download(self, sfx_url):
        if self.download_update_thread and self.download_update_thread.isRunning():
            QMessageBox.information(self, "Download Update", "Proses download update sudah berjalan.")
            return
        temp_dir = tempfile.gettempdir()
        sfx_filename = os.path.basename(QUrl(sfx_url).path())
        if not sfx_filename or not sfx_filename.lower().endswith((".exe", ".sfx")): sfx_filename = "mrd_downloader_update.sfx.exe"
        self.sfx_save_path = os.path.join(temp_dir, sfx_filename)
        self.update_progress_dialog = QProgressDialog("Mengunduh pembaruan...", "Batal", 0, 100, self)
        self.update_progress_dialog.setWindowTitle("Download Pembaruan")
        self.update_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.update_progress_dialog.setAutoClose(False)
        self.update_progress_dialog.setAutoReset(False)
        self.update_progress_dialog.setValue(0)
        self.download_update_thread = DownloadUpdateThread(sfx_url, self.sfx_save_path, self)
        self.download_update_thread.download_progress.connect(self.handle_update_download_progress)
        self.download_update_thread.download_finished.connect(self.handle_update_download_finished)
        self.download_update_thread.download_error.connect(self.handle_update_download_error)
        self.download_update_thread.finished.connect(self._on_any_thread_finished)
        self.update_progress_dialog.canceled.connect(self.cancel_update_download)
        self.set_ui_busy_state(True, "downloading_update")
        self.download_update_thread.start()
        self.set_status_text(f"Mengunduh pembaruan dari {sfx_url}...")
        self.update_progress_dialog.show()

    def cancel_update_download(self):
        if self.download_update_thread and self.download_update_thread.isRunning():
            self.download_update_thread.stop()
        if self.update_progress_dialog:
            self.update_progress_dialog.close()
        self.set_status_text("Download pembaruan dibatalkan.")
        QMessageBox.information(self, "Download Dibatalkan", "Proses download pembaruan telah dibatalkan.")

    def handle_update_download_progress(self, percentage):
        if self.update_progress_dialog: self.update_progress_dialog.setValue(percentage)

    def handle_update_download_finished(self, sfx_path):
        if self.update_progress_dialog:
            try:
                self.update_progress_dialog.canceled.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.update_progress_dialog.setValue(100)
            self.update_progress_dialog.close()
        self.set_status_text("Download pembaruan selesai. Menjalankan updater...")
        confirm_run = QMessageBox.question(self, "Download Selesai", f"Pembaruan telah diunduh ke:\n{sfx_path}\n\nAplikasi akan ditutup untuk menjalankan updater.\nLanjutkan?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
        if confirm_run == QMessageBox.StandardButton.Yes:
            try:
                if sys.platform != "win32": os.chmod(sfx_path, 0o755)
                if sys.platform == "win32": subprocess.Popen([sfx_path], creationflags=subprocess.DETACHED_PROCESS, close_fds=True)
                else: subprocess.Popen([sfx_path])
                QApplication.instance().quit()
            except Exception as e:
                QMessageBox.critical(self, "Gagal Menjalankan Updater", f"Tidak bisa menjalankan file updater:\n{sfx_path}\n\nError: {str(e)}\n\nSilakan jalankan manual.")
                self.set_status_text(f"Gagal jalankan updater: {e}")
                try: webbrowser.open(os.path.dirname(sfx_path))
                except Exception: pass
        else:
            self.set_status_text("Instalasi pembaruan ditunda. File updater ada di folder temporary.")
            QMessageBox.information(self, "Instalasi Ditunda", f"File updater ada di:\n{sfx_path}\nAnda bisa menjalankannya manual nanti.")

    def handle_update_download_error(self, error_message):
        if self.update_progress_dialog:
            try:
                self.update_progress_dialog.canceled.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.update_progress_dialog.close()
        self.set_status_text(f"Gagal download update: {error_message}")
        QMessageBox.critical(self, "Download Gagal", f"Tidak bisa mengunduh pembaruan:\n{error_message}")

    def set_initial_window_geometry(self):
        window_width = 800
        window_height = 250
        self.resize(window_width, window_height)
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            screen_center = screen_geometry.center()
            top_left_x = screen_center.x() - window_width // 2
            top_left_y = screen_center.y() - window_height // 2
            self.move(top_left_x, top_left_y)
        else:
            self.setGeometry(100, 100, window_width, window_height)

    def show_about_dialog(self):
        if any((t and t.isRunning()) for t in [self.download_thread, self.search_thread, self.playlist_fetch_thread, self.channel_fetch_thread, self.stream_info_thread, self.update_check_thread, self.download_update_thread]) or \
           self.current_list_batch_download_active:
            QMessageBox.information(self, "Operasi Berjalan", "Tunggu atau hentikan operasi aktif sebelum membuka info aplikasi.")
            return
        dialog = AboutDialog(self)
        dialog.exec()
        self.set_status_text("Dialog info aplikasi ditutup.")
        self.update_window_title_status("Siap")

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(self.play_video_from_input_shortcut)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self).activated.connect(self.play_audio_from_input_shortcut)

    def handle_media_player_error(self, error: QMediaPlayer.Error = QMediaPlayer.Error.NoError):
        if error != QMediaPlayer.Error.NoError:
            if self.operation_progress_dialog and self.operation_progress_dialog.isVisible(): self.operation_progress_dialog.reject(); self.operation_progress_dialog = None
            QMessageBox.critical(self, "Kesalahan Media Player", f"Error: {self.media_player.errorString() or 'Kesalahan tidak diketahui'}")
            self.stop_current_playback()

    def handle_media_player_state_changed(self, state: QMediaPlayer.PlaybackState):
        if self.operation_progress_dialog and self.operation_progress_dialog.isVisible() and state in [QMediaPlayer.PlaybackState.PlayingState, QMediaPlayer.PlaybackState.PausedState]:
            self.operation_progress_dialog.accept()
            self.operation_progress_dialog = None
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.set_status_text("Playback berhenti/selesai.")
            self.update_window_title_status("Siap")
            if self.stacked_widget.currentWidget() != self.main_view_widget:
                self.close_player_view()
            self.set_ui_busy_state(False, operation_type="playback")
        elif state == QMediaPlayer.PlaybackState.PlayingState:
            self.set_ui_busy_state(True, operation_type="playback")
            title = self.current_video_title_for_window
            if self.stacked_widget.currentWidget() == self.audio_player_widget:
                self.set_status_text(f"Audio Aktif: {title}")
                self.update_window_title_status(f"Memutar Audio ({title[:20]}...)")
            elif self.stacked_widget.currentWidget() == self.video_player_widget:
                self.set_status_text(f"Video Aktif: {title}")
                self.update_window_title_status(f"Memutar Video ({title[:20]}...)")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            title = self.current_video_title_for_window
            if self.stacked_widget.currentWidget() == self.audio_player_widget:
                self.set_status_text(f"Audio Dijeda: {title}")
                self.update_window_title_status(f"Audio Dijeda ({title[:20]}...)")
            elif self.stacked_widget.currentWidget() == self.video_player_widget:
                self.set_status_text(f"Video Dijeda: {title}")
                self.update_window_title_status(f"Video Dijeda ({title[:20]}...)")

    def restore_proper_focus(self, item_url_to_focus=None):
        current_widget = self.stacked_widget.currentWidget()
        if current_widget != self.main_view_widget:
            current_widget.activateWindow()
            current_widget.setFocus()
            return
            
        if self.active_search_results_dialog:
            self.active_search_results_dialog.show()
            self.active_search_results_dialog.activateWindow()
            self.active_search_results_dialog.raise_()
            url_to_check = item_url_to_focus or self.last_selected_search_item_url
            if url_to_check:
                for i in range(self.active_search_results_dialog.results_list_widget.count()):
                    item = self.active_search_results_dialog.results_list_widget.item(i)
                    if not item: continue
                    data = item.data(Qt.ItemDataRole.UserRole)
                    if data and data.get('url') == url_to_check:
                        self.active_search_results_dialog.results_list_widget.setCurrentItem(item)
                        self.active_search_results_dialog.results_list_widget.scrollToItem(item)
                        break
            self.active_search_results_dialog.results_list_widget.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self.input_line_edit.setFocus()

    def play_video_from_input_shortcut(self):
        url = self.input_line_edit.text().strip()
        if self.is_likely_direct_video_url(url):
            self.last_selected_search_item_url = url
            self.request_stream_info_and_play(url, "Video dari Input", True)
        else:
            QMessageBox.warning(self, "Aksi Tidak Sesuai", "URL video YouTube yang valid diperlukan.")

    def play_audio_from_input_shortcut(self):
        url = self.input_line_edit.text().strip()
        if self.is_likely_direct_video_url(url):
            self.last_selected_search_item_url = url
            self.request_stream_info_and_play(url, "Audio dari Input", False)
        else:
            QMessageBox.warning(self, "Aksi Tidak Sesuai", "URL video YouTube yang valid diperlukan.")

    def request_stream_info_and_play(self, page_url, title_hint, play_video):
        self.stop_current_playback()
        self.stop_active_threads(exclude_stream_info=True)
        self.current_video_title_for_window = title_hint
        self.set_status_text(f"Mengambil info stream: {title_hint}...")
        self.update_window_title_status("Mengambil Info Stream")
        self.set_ui_busy_state(True, operation_type="playback_loading")
        if self.operation_progress_dialog: self.operation_progress_dialog.close()
        self.operation_progress_dialog = OperationProgressDialog(f"Memuat {('Video' if play_video else 'Audio')}: {title_hint[:30]}...", self)
        self.operation_progress_dialog.show()
        if self.stream_info_thread and self.stream_info_thread.isRunning():
            self.stream_info_thread.terminate()
            self.stream_info_thread.wait()
        self.stream_info_thread = StreamInfoThread(page_url, title_hint, play_video, self)
        self.stream_info_thread.stream_url_ready.connect(self.start_playback_with_stream_url)
        self.stream_info_thread.stream_error.connect(self.handle_stream_info_error)
        self.stream_info_thread.finished.connect(self._on_any_thread_finished)
        self.stream_info_thread.start()

    def start_playback_with_stream_url(self, stream_url, title, play_video):
        if self.operation_progress_dialog:
            self.operation_progress_dialog.accept()
            self.operation_progress_dialog = None
        if self.active_search_results_dialog and self.active_search_results_dialog.isVisible():
            self.active_search_results_dialog.hide()
        
        self.current_video_title_for_window = title
        if play_video:
            self.media_player.setVideoOutput(self.video_widget)
            if not self.video_player_widget:
                self.video_player_widget = VideoPlayerWidget(self.media_player, self.video_widget, self, settings=self.settings)
                self.video_player_widget.close_requested.connect(self.close_player_view)
                self.video_player_widget.download_requested.connect(self.handle_playback_download_request)
                self.video_player_widget.playback_rate_change_requested.connect(self.change_playback_rate)
                self.stacked_widget.addWidget(self.video_player_widget)
            self.video_player_widget.update_title(title)
            if self.original_geometry is None: self.original_geometry = self.geometry()
            self.stacked_widget.setCurrentWidget(self.video_player_widget)
            self.showFullScreen()
            self.video_player_widget.setFocus()
        else:
            self.media_player.setVideoOutput(None)
            if not self.audio_player_widget:
                self.audio_player_widget = AudioPlayerWidget(self.media_player, self)
                self.audio_player_widget.close_requested.connect(self.close_player_view)
                self.audio_player_widget.download_requested.connect(self.handle_playback_download_request)
                self.audio_player_widget.playback_rate_change_requested.connect(self.change_playback_rate)
                self.stacked_widget.addWidget(self.audio_player_widget)
            self.audio_player_widget.update_title(title)
            if self.original_geometry is None: self.original_geometry = self.geometry()
            self.stacked_widget.setCurrentWidget(self.audio_player_widget)
            self.showFullScreen()
            self.audio_player_widget.setFocus()
        
        self.media_player.setSource(QUrl(stream_url))
        self.media_player.setPlaybackRate(self.settings.get('playback_rate', 1.0))
        self.media_player.play()

    def change_playback_rate(self, delta):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            return
        
        current_rate = self.media_player.playbackRate()
        new_rate = round(current_rate + delta, 2)
        
        new_rate = max(0.25, min(new_rate, 4.0))
        
        if abs(new_rate - current_rate) > 0.01:
            self.media_player.setPlaybackRate(new_rate)
            self.settings['playback_rate'] = new_rate
            self.save_app_settings(show_error=False)
            
            rate_text = f"kecepatan pemutar {new_rate:.2f}"
            self.set_status_text(f"Kecepatan pemutar diatur ke {new_rate:.2f}x")
            nvda_speak(rate_text)

    def handle_stream_info_error(self, error_message):
        if self.operation_progress_dialog:
            self.operation_progress_dialog.reject()
            self.operation_progress_dialog = None
        QMessageBox.critical(self, "Gagal Memutar", f"Tidak bisa dapat info stream: {error_message}")
        self.set_status_text("Gagal playback.")
        self.update_window_title_status("Gagal Playback")
        self.restore_proper_focus()

    def stop_current_playback(self):
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()

    def close_player_view(self):
        self.stop_current_playback()
        self.stacked_widget.setCurrentWidget(self.main_view_widget)
        if self.original_geometry:
            self.showNormal()
            self.setGeometry(self.original_geometry)
            self.original_geometry = None
        self.restore_proper_focus()

    def handle_playback_download_request(self, download_type):
        if self.last_selected_search_item_url:
            QMessageBox.information(self, f"Mulai Unduh {download_type.capitalize()}",
                                      f"Memulai unduhan {download_type} untuk:\n'{self.current_video_title_for_window}'.")
            self.start_download(self.last_selected_search_item_url, 
                                video_title_hint=self.current_video_title_for_window, 
                                download_type=download_type)
        else:
            QMessageBox.warning(self, "Gagal Unduh", "Tidak ada informasi URL yang tersimpan untuk media yang sedang diputar.")

    def stop_active_threads(self, exclude_stream_info=False, exclude_download_thread=False, exclude_playlist_fetch_thread=False, exclude_search_thread=False, exclude_channel_fetch_thread=False):
        threads_to_stop = []
        if not exclude_download_thread and self.download_thread: threads_to_stop.append(self.download_thread)
        if not exclude_search_thread and self.search_thread: threads_to_stop.append(self.search_thread)
        if not exclude_stream_info and self.stream_info_thread: threads_to_stop.append(self.stream_info_thread)
        if not exclude_playlist_fetch_thread and self.playlist_fetch_thread: threads_to_stop.append(self.playlist_fetch_thread)
        if not exclude_channel_fetch_thread and self.channel_fetch_thread: threads_to_stop.append(self.channel_fetch_thread)
        if self.update_check_thread and self.update_check_thread.isRunning(): threads_to_stop.append(self.update_check_thread)
        if self.download_update_thread and self.download_update_thread.isRunning():
            self.download_update_thread.stop()
            threads_to_stop.append(self.download_update_thread)
        for thread in threads_to_stop:
            if thread and thread.isRunning():
                if hasattr(thread, 'stop') and thread != self.download_update_thread : thread.stop()
                thread.quit()
                if not thread.wait(700):
                    thread.terminate()
                    thread.wait(100)
        if not exclude_download_thread: self.download_thread = None
        if not exclude_search_thread: self.search_thread = None
        if not exclude_stream_info: self.stream_info_thread = None
        if not exclude_playlist_fetch_thread: self.playlist_fetch_thread = None
        if not exclude_channel_fetch_thread: self.channel_fetch_thread = None
        self.update_check_thread = None
        self.download_update_thread = None
        if not exclude_download_thread and self.download_progress_dialog:
            self.download_progress_dialog.reject()
            self.download_progress_dialog = None
        if self.update_progress_dialog:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None
        if (not exclude_search_thread or not exclude_playlist_fetch_thread or not exclude_stream_info or not exclude_channel_fetch_thread) and self.operation_progress_dialog:
            title = self.operation_progress_dialog.windowTitle()
            should_close_op_dialog = (not exclude_search_thread and title.startswith("Mencari")) or \
                                     (not exclude_playlist_fetch_thread and (title.startswith("Memuat Playlist") or title.startswith("Memuat Isi Playlist"))) or \
                                     (not exclude_channel_fetch_thread and title.startswith("Memuat Channel")) or \
                                     (not exclude_stream_info and title.startswith("Memuat"))
            if should_close_op_dialog:
                self.operation_progress_dialog.reject()
                self.operation_progress_dialog = None

    def load_app_settings(self):
        global _GLOBAL_DEBUG_MODE
        config_dir = os.path.dirname(CONFIG_FILE)
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.warning(self, "Pengaturan Error", f"Gagal membuat direktori konfigurasi: {config_dir}\nError: {e}\nPengaturan tidak akan dimuat/disimpan.")
                self.settings = DEFAULT_SETTINGS.copy()
                _GLOBAL_DEBUG_MODE = self.settings.get('debug_mode', False) 
                return
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    loaded_s = json.load(f)
                    for key, default_value in DEFAULT_SETTINGS.items():
                        if key not in loaded_s:
                            loaded_s[key] = default_value
                    self.settings = loaded_s
            else:
                self.settings = DEFAULT_SETTINGS.copy()
                self.save_app_settings(show_error=False)
            
            _GLOBAL_DEBUG_MODE = self.settings.get('debug_mode', False)
        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.warning(self, "Pengaturan Error", f"Gagal muat pengaturan dari {CONFIG_FILE}: {e}. Pakai default.")
            self.settings = DEFAULT_SETTINGS.copy()
            _GLOBAL_DEBUG_MODE = self.settings.get('debug_mode', False)
            self.save_app_settings(show_error=False)
        
        if hasattr(self, 'debug_mode_action'):
            self.debug_mode_action.setChecked(_GLOBAL_DEBUG_MODE)

    def save_app_settings(self, show_error=True):
        config_dir = os.path.dirname(CONFIG_FILE)
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
            except OSError as e:
                if show_error: QMessageBox.warning(self, "Gagal Simpan Pengaturan", f"Gagal membuat direktori konfigurasi: {config_dir}\nError: {e}")
                return
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except IOError as e:
            if show_error: QMessageBox.warning(self, "Gagal Simpan Pengaturan", f"Gagal simpan ke {CONFIG_FILE}: {e}")

    def set_ui_busy_state(self, busy, operation_type="general"):
        is_media_playing = self.media_player.playbackState() in [QMediaPlayer.PlaybackState.PlayingState, QMediaPlayer.PlaybackState.PausedState]
        is_dialog_blocking = (self.operation_progress_dialog and self.operation_progress_dialog.isVisible()) or \
                             (self.download_progress_dialog and self.download_progress_dialog.isVisible()) or \
                             (self.update_progress_dialog and self.update_progress_dialog.isVisible())
        active_threads = [
            self.stream_info_thread, self.download_thread, self.search_thread,
            self.playlist_fetch_thread, self.channel_fetch_thread, self.update_check_thread, self.download_update_thread
        ]
        is_any_thread_running = any(t and t.isRunning() for t in active_threads)
        
        effective_busy_state = busy or is_any_thread_running or is_dialog_blocking or self.current_list_batch_download_active
        if operation_type == "playback" or operation_type == "playback_loading":
            effective_busy_state = busy or is_any_thread_running or is_dialog_blocking or self.current_list_batch_download_active
        is_main_view_active = self.stacked_widget.currentWidget() == self.main_view_widget
        enable_main_controls = not effective_busy_state and is_main_view_active
        self.input_line_edit.setEnabled(enable_main_controls)
        self.search_type_combo.setEnabled(enable_main_controls)
        self.go_button.setEnabled(enable_main_controls)
        
        can_open_dialogs = not is_any_thread_running and not self.current_list_batch_download_active
        self.settings_button.setEnabled(can_open_dialogs)
        self.info_button.setEnabled(can_open_dialogs)
        
        if hasattr(self, 'check_update_action'):
            self.check_update_action.setEnabled(not (self.update_check_thread and self.update_check_thread.isRunning()))
        if hasattr(self, 'settings_action'):
            self.settings_action.setEnabled(can_open_dialogs)
        if hasattr(self, 'about_action'):
            self.about_action.setEnabled(can_open_dialogs)
        if hasattr(self, 'open_download_folder_action'):
            self.open_download_folder_action.setEnabled(True)
        if hasattr(self, 'clear_input_action'):
            self.clear_input_action.setEnabled(not effective_busy_state and is_main_view_active)
        if hasattr(self, 'paste_and_go_action'):
            self.paste_and_go_action.setEnabled(not effective_busy_state and is_main_view_active)

    def is_valid_youtube_url(self, url_text):
        return 'youtube.com/' in url_text or 'youtu.be/' in url_text
        
    def is_youtube_channel_url(self, url_text):
        patterns = [
            re.compile(r'https?://(?:www\.)?youtube\.com/(?:c/|channel/|user/|@)([a-zA-Z0-9_-]+)/?(?:videos|featured|playlists|community|about)?/?$'),
            re.compile(r'https?://(?:www\.)?youtube\.com/(?:c/|channel/|user/|@)([a-zA-Z0-9_-]+)$')
        ]
        return any(p.match(url_text) for p in patterns)

    def is_potential_playlist_url(self, url_text):
        pat_playlist = re.compile(r'https?://(?:www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)')
        return bool(pat_playlist.match(url_text))

    def is_valid_youtube_video_url(self, url_text):
        video_id_char_class = r'[a-zA-Z0-9_-]'
        patterns = [
            re.compile(fr'^(https?://)?([a-zA-Z0-9-]+\.)*youtube\.com/watch\?.*v=({video_id_char_class}{{11,}}).*'),
            re.compile(fr'^(https?://)?youtu\.be/({video_id_char_class}{{11,}})(\?.*)?'),
            re.compile(fr'^(https?://)?([a-zA-Z0-9-]+\.)*youtube\.com/embed/({video_id_char_class}{{11,}})(\?.*)?'),
            re.compile(fr'^(https?://)?([a-zA-Z0-9-]+\.)*youtube\.com/shorts/({video_id_char_class}{{11,}})(\?.*)?'),
            re.compile(fr'^(https?://)?([a-zA-Z0-9-]+\.)*youtube\.com/live/({video_id_char_class}{{11,}})(\?.*)?')
        ]
        return any(pat.match(url_text) for pat in patterns)

    def is_likely_direct_video_url(self, url_text):
        if self.is_valid_youtube_video_url(url_text):
            return True
        if re.match(r'^(https?://)?googleusercontent\.com/youtube\.com/0[a-zA-Z0-9_-]{10,}$', url_text):
             return True
        return False

    def process_input(self):
        txt = self.input_line_edit.text().strip()
        if not txt:
            QMessageBox.warning(self, "Input Kosong", "Masukkan URL atau kata kunci.")
            return
        self.stop_current_operation(confirm=False)
        if self.active_search_results_dialog and self.active_search_results_dialog.isVisible():
            self.active_search_results_dialog.reject()
            self.active_search_results_dialog = None
        if self.is_youtube_channel_url(txt):
            QMessageBox.information(self, "URL Channel Terdeteksi", f"URL '{txt[:60]}...' dikenali sebagai channel. Akan menampilkan 100 video terbaru.")
            self.start_channel_item_fetch(txt)
        elif self.is_potential_playlist_url(txt):
            QMessageBox.information(self, "URL Playlist Terdeteksi", f"URL '{txt[:60]}...' dikenali sebagai playlist. Akan menampilkan isinya.")
            self.start_playlist_item_fetch_via_url(txt)
        elif self.is_likely_direct_video_url(txt):
            self.handle_direct_video_url_dialog(txt)
        else:
            self.start_search(txt, search_type=self.search_type_combo.currentText())

    def handle_direct_video_url_dialog(self, video_url):
        dialog = QDialog(self)
        dialog.setWindowTitle("URL Video Terdeteksi")
        layout = QVBoxLayout(dialog)
        
        label = QLabel(f"URL video terdeteksi:\n{video_url[:70]}{'...' if len(video_url) > 70 else ''}\n\nApa yang ingin Anda lakukan?")
        label.setWordWrap(True)
        layout.addWidget(label)
        
        button_layout = QGridLayout()
        btn_dl_vid = QPushButton("Unduh Video")
        btn_dl_aud = QPushButton("Unduh Audio")
        btn_play_vid = QPushButton("Putar Video")
        btn_play_aud = QPushButton("Putar Audio")
        
        button_layout.addWidget(btn_dl_vid, 0, 0)
        button_layout.addWidget(btn_dl_aud, 0, 1)
        button_layout.addWidget(btn_play_vid, 1, 0)
        button_layout.addWidget(btn_play_aud, 1, 1)
        layout.addLayout(button_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        action_map = {
            btn_dl_vid: "download_video",
            btn_dl_aud: "download_audio",
            btn_play_vid: "play_video",
            btn_play_aud: "play_audio"
        }
        chosen_action_key = [None] 
        def on_action_chosen(button_key):
            chosen_action_key[0] = action_map[button_key]
            dialog.accept()
        btn_dl_vid.clicked.connect(lambda: on_action_chosen(btn_dl_vid))
        btn_dl_aud.clicked.connect(lambda: on_action_chosen(btn_dl_aud))
        btn_play_vid.clicked.connect(lambda: on_action_chosen(btn_play_vid))
        btn_play_aud.clicked.connect(lambda: on_action_chosen(btn_play_aud))
        if dialog.exec() == QDialog.DialogCode.Accepted and chosen_action_key[0]:
            action = chosen_action_key[0]
            title_hint = "Video dari URL"
            if action == 'download_video':
                self.start_download(video_url, title_hint, 'video')
            elif action == 'download_audio':
                self.start_download(video_url, title_hint, 'audio')
            elif action == 'play_video':
                self.request_stream_info_and_play(video_url, title_hint, True)
            elif action == 'play_audio':
                self.request_stream_info_and_play(video_url, title_hint, False)

    def start_search(self, query, search_type="Video"):
        if any((t and t.isRunning()) for t in [self.download_thread, self.playlist_fetch_thread, self.channel_fetch_thread]):
            QMessageBox.information(self, "Operasi Berjalan", "Selesaikan operasi lain.")
            return
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()
        
        if search_type == "Channel":
            self.start_channel_item_fetch(query)
            return
        self.set_ui_busy_state(True, "search")
        lbl = "Video" if search_type == "Video" else "Playlist"
        self.set_status_text(f"Mencari {lbl} \"{query}\"...")
        self.update_window_title_status(f"Mencari {lbl} ({query[:20]}...)")
        self.current_video_title_for_window = query
        if self.operation_progress_dialog: self.operation_progress_dialog.close()
        self.operation_progress_dialog = OperationProgressDialog(f"Mencari {lbl}: {query[:30]}...", self)
        self.operation_progress_dialog.show()
        
        self.search_thread = SearchThread(query, self.settings.get('search_results_count', 10), search_type, self)
        self.search_thread.results_batch_ready.connect(self.handle_search_results_batch)
        self.search_thread.search_finished.connect(self.handle_search_finished)
        self.search_thread.search_error.connect(self.handle_search_error)
        self.search_thread.finished.connect(self._on_any_thread_finished)
        self.search_thread.start()
        
    def handle_search_results_batch(self, results, result_type):
        if self.operation_progress_dialog and self.operation_progress_dialog.isVisible():
            self.operation_progress_dialog.accept()
            self.operation_progress_dialog = None
        
        query_ctx = self.current_video_title_for_window
        
        if self.active_search_results_dialog and self.active_search_results_dialog.isVisible():
            self.active_search_results_dialog.add_results(results)
        else:
            dlg_res_type = "video_search" if result_type == "video" else "playlist_search_results"
            entity = "video" if result_type == "video" else "playlist"
            self.set_status_text(f"Menampilkan hasil awal {entity} untuk \"{query_ctx}\"...")
            
            if not results: return
            
            if self.active_search_results_dialog and self.active_search_results_dialog.isVisible():
                self.active_search_results_dialog.close()
            
            self.active_search_results_dialog = SearchResultsDialog(results, self, result_type=dlg_res_type, settings=self.settings)
            self.active_search_results_dialog.action_triggered.connect(self.handle_action_from_search_dialog)
            self.active_search_results_dialog.rejected.connect(self.handle_search_dialog_rejected)
            self.active_search_results_dialog.show()
            self.active_search_results_dialog.activateWindow()

    def handle_search_finished(self, result_type, total_count):
        if self.operation_progress_dialog and self.operation_progress_dialog.isVisible():
            self.operation_progress_dialog.accept()
            self.operation_progress_dialog = None
        if self.active_search_results_dialog:
            self.active_search_results_dialog.set_final_count(total_count)
        
        entity = "video" if result_type == "video" else "playlist"
        self.set_status_text(f"Pencarian selesai. Ditemukan total {total_count} hasil {entity}.")
        self.update_window_title_status(f"Hasil Pencarian {entity.capitalize()}")

    def start_playlist_item_fetch_via_url(self, playlist_url):
        if any((t and t.isRunning()) for t in [self.download_thread, self.search_thread, self.channel_fetch_thread]):
            QMessageBox.information(self, "Operasi Berjalan", "Selesaikan operasi lain.")
            return
        if self.playlist_fetch_thread and self.playlist_fetch_thread.isRunning():
            self.playlist_fetch_thread.terminate()
            self.playlist_fetch_thread.wait()
        self.set_ui_busy_state(True, "playlist_fetching")
        self.set_status_text(f"Memuat item dari playlist: {playlist_url[:50]}...")
        self.update_window_title_status(f"Memuat Isi Playlist ({playlist_url[:30]}...)")
        self.current_video_title_for_window = playlist_url
        if self.operation_progress_dialog: self.operation_progress_dialog.close()
        self.operation_progress_dialog = OperationProgressDialog(f"Memuat Isi Playlist: {playlist_url[:40]}...", self)
        self.operation_progress_dialog.show()
        self.playlist_fetch_thread = PlaylistFetchThread(playlist_url, parent=self)
        self.playlist_fetch_thread.results_ready.connect(self.handle_list_items_results)
        self.playlist_fetch_thread.fetch_error.connect(self.handle_list_fetch_error)
        self.playlist_fetch_thread.finished.connect(self._on_any_thread_finished)
        self.playlist_fetch_thread.start()
        
    def start_channel_item_fetch(self, channel_url_or_query):
        if any((t and t.isRunning()) for t in [self.download_thread, self.search_thread, self.playlist_fetch_thread]):
            QMessageBox.information(self, "Operasi Berjalan", "Selesaikan operasi lain.")
            return
        if self.channel_fetch_thread and self.channel_fetch_thread.isRunning():
            self.channel_fetch_thread.terminate()
            self.channel_fetch_thread.wait()
        self.set_ui_busy_state(True, "channel_fetching")
        self.set_status_text(f"Memuat video dari channel: {channel_url_or_query[:50]}...")
        self.update_window_title_status(f"Memuat Channel ({channel_url_or_query[:30]}...)")
        self.current_video_title_for_window = channel_url_or_query
        if self.operation_progress_dialog: self.operation_progress_dialog.close()
        self.operation_progress_dialog = OperationProgressDialog(f"Memuat Channel: {channel_url_or_query[:40]}...", self)
        self.operation_progress_dialog.show()
        self.channel_fetch_thread = ChannelFetchThread(channel_url_or_query, self)
        self.channel_fetch_thread.results_ready.connect(lambda e, t, u: self.handle_list_items_results(e, t, u, list_type='channel'))
        self.channel_fetch_thread.fetch_error.connect(self.handle_list_fetch_error)
        self.channel_fetch_thread.finished.connect(self._on_any_thread_finished)
        self.channel_fetch_thread.start()

    def handle_list_items_results(self, entries, list_title, original_list_url, list_type='playlist'):
        if self.operation_progress_dialog:
            self.operation_progress_dialog.accept()
            self.operation_progress_dialog = None
        list_name = "Playlist" if list_type == 'playlist' else "Channel"
        item_name = "video" if list_type == 'channel' else "item"
        dialog_result_type = "channel_items" if list_type == 'channel' else "playlist_items"
        self.set_status_text(f"{list_name} '{list_title}' berisi {len(entries)} {item_name}.")
        self.update_window_title_status(f"Isi {list_name}: {list_title[:20]}...")
        self.current_video_title_for_window = list_title
        if not entries:
            QMessageBox.information(self, f"Isi {list_name}", f"{list_name} '{list_title}' kosong atau tidak berisi video yang dapat diakses.")
            self.input_line_edit.setFocus()
            self.update_window_title_status("Siap")
            return
            
        if self.active_search_results_dialog and self.active_search_results_dialog.isVisible():
            self.active_search_results_dialog.close()
            
        self.active_search_results_dialog = SearchResultsDialog(
            entries, self, result_type=dialog_result_type,
            list_title_str=list_title, original_list_url=original_list_url, settings=self.settings
        )
        self.active_search_results_dialog.action_triggered.connect(self.handle_action_from_search_dialog)
        self.active_search_results_dialog.rejected.connect(self.handle_search_dialog_rejected)
        self.active_search_results_dialog.download_all_playlist_items_requested.connect(self.start_batch_download_list)
        self.active_search_results_dialog.show()
        self.active_search_results_dialog.activateWindow()

    def handle_list_fetch_error(self, error_message):
        if self.operation_progress_dialog:
            self.operation_progress_dialog.reject()
            self.operation_progress_dialog = None
        self.set_status_text(f"Gagal Muat: {error_message}")
        QMessageBox.critical(self, "Gagal Muat", error_message)
        self.restore_proper_focus()

    def handle_action_from_search_dialog(self, info):
        if info and info.get('url'):
            action, url, title, item_type = info.get('action', 'download_video'), info['url'], info['title'], info.get('type', 'video')
            self.last_selected_search_item_url = url
            if item_type == 'playlist_meta' and action == 'view_playlist_items':
                self.set_status_text(f"Pilihan Playlist: {title}. Memuat item...")
                if self.active_search_results_dialog:
                    self.active_search_results_dialog.hide()
                self.start_playlist_item_fetch_via_url(url)
                return
            elif item_type == 'video':
                if action == 'play_video': self.request_stream_info_and_play(url, title, True)
                elif action == 'play_audio': self.request_stream_info_and_play(url, title, False)
                elif action == 'download_video' or action == 'download_audio':
                    self.last_downloaded_item_info = {'url': url, 'title': title, 'type': 'video' if action == 'download_video' else 'audio'}
                    self.download_initiated_from_search_dialog = True
                    self.start_download(url, video_title_hint=title, download_type='video' if action == 'download_video' else 'audio')
                else:
                    self.set_status_text("Aksi tidak diketahui.")
                    self.update_window_title_status("Siap")
        else:
            self.set_status_text("Aksi dibatalkan.")
            self.update_window_title_status("Siap")
            self.restore_proper_focus()

    def handle_search_dialog_rejected(self):
        if self.active_search_results_dialog:
            self.active_search_results_dialog.close()
            self.active_search_results_dialog = None
        self.set_status_text("Dialog hasil pencarian ditutup.")
        self.update_window_title_status("Siap")
        self.input_line_edit.setFocus()

    def handle_search_error(self, error_message):
        if self.operation_progress_dialog:
            self.operation_progress_dialog.reject()
            self.operation_progress_dialog = None
        self.set_status_text(f"Kesalahan Cari: {error_message}")
        QMessageBox.critical(self, "Kesalahan Cari", error_message)
        self.restore_proper_focus()

    def start_download(self, video_url, video_title_hint=None, download_type='video'):
        if any((t and t.isRunning()) for t in [self.search_thread, self.playlist_fetch_thread, self.channel_fetch_thread]):
            QMessageBox.information(self, "Operasi Berjalan", "Selesaikan atau hentikan operasi lain sebelum memulai unduhan.")
            return
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.information(self, "Unduhan Berjalan", "Satu unduhan sudah berjalan. Harap tunggu atau hentikan.")
            return
            
        out_path = self.settings['output_path']
        fmt_choice = self.settings['video_format_choice'] if download_type == 'video' else self.settings['audio_format_choice']
        embed_meta = self.settings.get('embed_metadata', True)
        use_parallel = self.settings.get('use_parallel_download', False)
        self.set_ui_busy_state(True, "download")
        self.current_list_batch_download_active = False
        self.last_downloaded_item_info = {'url': video_url, 'title': video_title_hint or "Media", 'type': download_type}
        
        if self.download_progress_dialog:
            self.download_progress_dialog.reject()
            
        self.download_progress_dialog = DownloadProgressDialog(video_title_hint or "Memuat Info...", self)
        self.download_progress_dialog.cancel_requested.connect(self.handle_download_cancellation_request)
        self.download_progress_dialog.show()
        
        self.set_status_text(f"Mulai unduh {download_type}: {video_title_hint or video_url[:50]}...")
        self.update_window_title_status(f"Mengunduh {download_type.capitalize()} ({ (video_title_hint or 'Media')[:20] }...)")
        
        self.download_thread = DownloadThread(video_url, out_path, fmt_choice, embed_meta, use_parallel, video_title_hint, is_batch=False, parent=self)
        self.download_thread.download_title_signal.connect(self.download_progress_dialog.update_title)
        self.download_thread.download_progress_signal.connect(self.download_progress_dialog.update_progress)
        self.download_thread.download_status_signal.connect(self.download_progress_dialog.update_status)
        self.download_thread.download_finished_signal.connect(self.handle_single_download_finished)
        self.download_thread.finished.connect(self._on_any_thread_finished)
        self.download_thread.start()

    def start_batch_download_list(self, items_to_download, list_title, download_type='video'):
        if not items_to_download:
            QMessageBox.warning(self, "Tidak Ada Item", "Tidak ada video untuk diunduh dari list ini.")
            return
        if any((t and t.isRunning()) for t in [self.search_thread, self.playlist_fetch_thread, self.channel_fetch_thread]):
            QMessageBox.information(self, "Operasi Berjalan", "Selesaikan operasi lain.")
            return
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.information(self, "Unduhan Berjalan", "Satu unduhan (mungkin batch lain) sudah jalan.")
            return
            
        sane_title = yt_dlp.utils.sanitize_filename(list_title, restricted=True)
        item_count = len(items_to_download)
        download_as_type_text = "video" if download_type == 'video' else "audio"
        
        if QMessageBox.question(self, "Konfirmasi Unduh Semua", f"Unduh {item_count} item dari '{list_title}' sebagai {download_as_type_text}?\nFile akan disimpan di subfolder '{sane_title}'.") == QMessageBox.StandardButton.No:
            self.set_status_text("Unduhan batch dibatalkan.")
            self.restore_proper_focus()
            return
            
        out_path = self.settings['output_path']
        fmt_choice = self.settings['video_format_choice'] if download_type == 'video' else self.settings['audio_format_choice']
        embed_meta = self.settings.get('embed_metadata', True)
        use_parallel = self.settings.get('use_parallel_download', False)
        self.set_ui_busy_state(True, "download_batch")
        self.current_list_batch_download_active = True
        self.download_initiated_from_search_dialog = True
        
        if self.download_progress_dialog:
            self.download_progress_dialog.reject()
            
        self.download_progress_dialog = DownloadProgressDialog(f"Batch ({download_as_type_text}): {list_title[:30]}...", self)
        self.download_progress_dialog.cancel_requested.connect(self.handle_download_cancellation_request)
        self.download_progress_dialog.show()
        
        self.set_status_text(f"Mulai batch ({download_as_type_text}): {list_title} ({item_count} item)...")
        self.update_window_title_status(f"Batch Unduh ({download_as_type_text.capitalize()}) ({list_title[:20]}...)")
        
        self.download_thread = DownloadThread(items_to_download, out_path, fmt_choice, embed_meta, use_parallel, None, True, list_title, self)
        self.download_thread.download_title_signal.connect(self.download_progress_dialog.update_title)
        self.download_thread.download_progress_signal.connect(self.download_progress_dialog.update_progress)
        self.download_thread.download_status_signal.connect(self.download_progress_dialog.update_status)
        self.download_thread.single_item_finished_signal.connect(self.handle_single_playlist_item_download_finished)
        self.download_thread.batch_overall_finished_signal.connect(self.handle_batch_overall_finished)
        self.download_thread.finished.connect(self._on_any_thread_finished)
        self.download_thread.start()

    def handle_download_cancellation_request(self):
        if self.download_thread and self.download_thread.isRunning():
            op_type = "Batch unduhan" if self.current_list_batch_download_active else "Unduhan"
            reply = QMessageBox.question(self, f"Batalkan {op_type}?", 
                                         f"Apakah Anda yakin ingin membatalkan {op_type.lower()} yang sedang berjalan?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.set_status_text(f"Mencoba membatalkan {op_type.lower()}...")
                self.update_window_title_status(f"Membatalkan {op_type}")
                self.download_thread.stop()
                if self.download_progress_dialog:
                    self.download_progress_dialog.update_status("Membatalkan...")
                    self.download_progress_dialog.cancel_button.setEnabled(False)

    def handle_single_playlist_item_download_finished(self, success, message, filepath, current_index, total_items):
        base_filename = os.path.basename(filepath) if filepath else f"Item {current_index+1}"
        self.set_status_text(f"Item {current_index + 1}/{total_items} ('{base_filename}'): {message}")

    def handle_batch_overall_finished(self, overall_success, final_batch_summary, base_output_path):
        self.current_list_batch_download_active = False
        if self.download_progress_dialog:
            self.download_progress_dialog.download_complete(overall_success, "Batch selesai.")
            QTimer.singleShot(100, lambda s=overall_success, m=final_batch_summary, p=base_output_path: self.close_download_dialog_and_notify_batch(s, m, p))
        else:
            QTimer.singleShot(0, lambda s=overall_success, m=final_batch_summary, p=base_output_path: self.close_download_dialog_and_notify_batch(s, m, p))
        self.current_batch_finished_success = overall_success
        self.current_batch_finished_message = final_batch_summary
        self.current_batch_finished_base_path = base_output_path
        self.current_batch_list_title = self.download_thread.list_title_for_batch if self.download_thread else "List"

    def close_download_dialog_and_notify_batch(self, success, message_summary, base_output_path):
        if self.download_progress_dialog and self.download_progress_dialog.isVisible():
            self.download_progress_dialog.accept()
            self.download_progress_dialog = None
        list_title = self.current_batch_list_title
        status_prefix = "Batch Selesai" if success else "Batch Selesai (Ada Gagal)"
        self.set_status_text(f"{status_prefix}: {message_summary.splitlines()[0] if message_summary.splitlines() else message_summary}")
        self.update_window_title_status(f"Batch Unduhan {status_prefix}")
        if self.settings.get('show_completion_popup', True) or not success:
            self.show_batch_download_completion_dialog(success, message_summary, base_output_path, list_title)

    def show_batch_download_completion_dialog(self, success, message_summary, base_output_path, list_title):
        title = f"Batch Unduhan '{list_title}' Selesai"
        text = f"Proses unduh dari '{list_title}' telah selesai.\\n\\n{message_summary}"
        def show_msg():
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Information if success else QMessageBox.Icon.Warning)
            msg_box.setWindowTitle(title)
            msg_box.setText(text)
            actual_path = os.path.join(base_output_path, yt_dlp.utils.sanitize_filename(list_title, restricted=True))
            if success and os.path.isdir(actual_path):
                btn_folder = msg_box.addButton("Buka Folder", QMessageBox.ButtonRole.ActionRole)
                msg_box.addButton(QMessageBox.StandardButton.Ok)
                clicked_button = msg_box.exec()
                if clicked_button == btn_folder:
                    self.open_location(actual_path)
            else:
                msg_box.addButton(QMessageBox.StandardButton.Ok)
                msg_box.exec()
            self.restore_proper_focus()
        QTimer.singleShot(0, show_msg)

    def handle_single_download_finished(self, success, message, downloaded_file_path):
        if self.current_list_batch_download_active: return
        if self.download_progress_dialog:
            self.download_progress_dialog.download_complete(success, message)
            QTimer.singleShot(100, lambda s=success, m=message, p=downloaded_file_path: self.close_single_download_dialog_and_notify(s, m, p))
        else:
             QTimer.singleShot(0, lambda s=success, m=message, p=downloaded_file_path: self.close_single_download_dialog_and_notify(s, m, p))

    def close_single_download_dialog_and_notify(self, success, message, downloaded_file_path):
        if self.current_list_batch_download_active: return
        if self.download_progress_dialog and self.download_progress_dialog.isVisible():
            self.download_progress_dialog.accept()
            self.download_progress_dialog = None
        download_type_text = self.last_downloaded_item_info.get('type', 'media').capitalize() if self.last_downloaded_item_info else "Media"
        self.set_status_text(f"{download_type_text} {'Selesai' if success else 'Gagal'}: {message}")
        self.update_window_title_status(f"Unduhan {download_type_text} {'Selesai' if success else 'Gagal'}")
        if self.settings.get('show_completion_popup', True) or not success:
            self.show_single_download_completion_dialog(success, message, downloaded_file_path)

    def show_single_download_completion_dialog(self, success, message, downloaded_file_path):
        download_type_text = self.last_downloaded_item_info.get('type', 'media').capitalize() if self.last_downloaded_item_info else "Media"
        title = f"Unduhan {download_type_text} Selesai" if success else f"Unduhan {download_type_text} Gagal"
        text = ""
        if success:
            file_name_display = os.path.basename(downloaded_file_path) if downloaded_file_path else "File"
            text = f"File \"{file_name_display}\" berhasil diunduh."
            folder_path_display = os.path.dirname(downloaded_file_path) if downloaded_file_path else self.settings['output_path']
            text += f"\nDisimpan di: {folder_path_display}"
        else:
            text = f"Unduhan {download_type_text} Gagal.\n\nError: {message}"
        def show_msg():
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Information if success else QMessageBox.Icon.Critical)
            msg_box.setWindowTitle(title)
            msg_box.setText(text)
            if success and downloaded_file_path and os.path.exists(downloaded_file_path):
                btn_folder = msg_box.addButton("Buka Folder", QMessageBox.ButtonRole.ActionRole)
                btn_file = msg_box.addButton("Buka File", QMessageBox.ButtonRole.ActionRole)
                msg_box.addButton(QMessageBox.StandardButton.Ok)
                clicked_button = msg_box.exec()
                if clicked_button == btn_folder:
                    self.open_location(os.path.dirname(downloaded_file_path))
                elif clicked_button == btn_file:
                    self.open_location(downloaded_file_path)
            else:
                msg_box.addButton(QMessageBox.StandardButton.Ok)
                msg_box.exec()
            self.restore_proper_focus()
        QTimer.singleShot(0, show_msg)

    def stop_current_operation(self, confirm=True):
        stopped_something = False
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            if not confirm or QMessageBox.question(self, "Hentikan Playback?", "Yakin hentikan playback saat ini?") == QMessageBox.StandardButton.Yes:
                self.close_player_view()
                stopped_something = True
        if self.download_thread and self.download_thread.isRunning():
            self.handle_download_cancellation_request()
            stopped_something = True
        other_threads_info = [
            (self.search_thread, "Pencarian", self.handle_search_error),
            (self.playlist_fetch_thread, "Pemuatan Playlist", self.handle_list_fetch_error),
            (self.channel_fetch_thread, "Pemuatan Channel", self.handle_list_fetch_error),
            (self.stream_info_thread, "Pengambilan Info Stream", self.handle_stream_info_error),
            (self.update_check_thread, "Pengecekan Pembaruan", self.handle_update_check_error),
        ]
        for thread, name, error_handler in other_threads_info:
            if thread and thread.isRunning():
                if not confirm or QMessageBox.question(self, f"Hentikan {name}?", f"Yakin hentikan proses {name.lower()}?") == QMessageBox.StandardButton.Yes:
                    thread.quit()
                    thread.wait(500)
                    if thread.isRunning():
                        thread.terminate()
                        thread.wait(100)
                    if error_handler:
                        error_handler(f"{name} dihentikan pengguna.")
                    stopped_something = True
                    break
        if self.download_update_thread and self.download_update_thread.isRunning():
            if not confirm or QMessageBox.question(self, "Hentikan Download Update?", "Yakin hentikan download pembaruan?") == QMessageBox.StandardButton.Yes:
                self.cancel_update_download()
                stopped_something = True
        if not stopped_something and confirm:
            self.set_status_text("Tidak ada operasi aktif yang bisa dihentikan saat ini.")
        QTimer.singleShot(100, lambda: self.set_ui_busy_state(False, "stop_operation_attempted"))

    def _on_any_thread_finished(self):
        sender = self.sender()
        if sender == self.download_thread:
            if self.download_progress_dialog and self.download_progress_dialog.isVisible():
                self.download_progress_dialog.accept()
                self.download_progress_dialog = None
            self.download_thread = None
            self.current_list_batch_download_active = False
            if not "Selesai" in self.status_label.text() and not "Gagal" in self.status_label.text() and not "Batch" in self.status_label.text():
                 self.set_status_text("Operasi unduhan telah selesai atau dihentikan.")
            QTimer.singleShot(150, self.restore_focus_after_download)
        elif sender == self.search_thread:
            self.search_thread = None
        elif sender == self.playlist_fetch_thread:
            self.playlist_fetch_thread = None
        elif sender == self.channel_fetch_thread:
            self.channel_fetch_thread = None
        elif sender == self.stream_info_thread:
            self.stream_info_thread = None
        elif sender == self.update_check_thread:
            self.update_check_thread = None
            if self._is_initial_startup_check:
                if not QApplication.activeModalWidget():
                    self.input_line_edit.setFocus()
                self._is_initial_startup_check = False
        elif sender == self.download_update_thread:
            self.download_update_thread = None
        
        if self.operation_progress_dialog and self.operation_progress_dialog.isVisible():
            if isinstance(sender, (SearchThread, PlaylistFetchThread, ChannelFetchThread, StreamInfoThread)):
                 self.operation_progress_dialog.accept()
                 self.operation_progress_dialog = None
                 
        self.set_ui_busy_state(False, "thread_finished")
        if not (self.active_search_results_dialog and self.active_search_results_dialog.isVisible()):
             self.update_window_title_status("Siap")
        
    def restore_focus_after_download(self):
        url_to_focus = None
        if self.download_initiated_from_search_dialog:
            url_to_focus = self.last_downloaded_item_info.get('url') if self.last_downloaded_item_info else None
            self.download_initiated_from_search_dialog = False
        self.restore_proper_focus(item_url_to_focus=url_to_focus)

    def update_window_title_status(self, status_text=""):
        parts = [self.BASE_TITLE]
        if status_text and status_text != "Siap":
            parts.insert(0, status_text)
        vid_name = self.current_video_title_for_window
        if vid_name and any(s in status_text.lower() for s in ["mencari", "hasil", "gagal", "memuat", "isi", "mengunduh", "batch", "memutar", "dijeda"]):
            parts.insert(1, f"({vid_name[:30] + '...' if len(vid_name) > 30 else vid_name})")
        self.setWindowTitle(" - ".join(parts))

    def open_settings_dialog(self):
        if any((t and t.isRunning()) for t in [self.download_thread, self.search_thread, self.playlist_fetch_thread, self.channel_fetch_thread, self.stream_info_thread, self.update_check_thread, self.download_update_thread]) or \
           self.current_list_batch_download_active:
            QMessageBox.information(self, "Operasi Berjalan", "Tunggu atau hentikan operasi aktif sebelum buka pengaturan.")
            return
        
        dialog = SettingsDialog(self.settings, self)
        dialog.settings_changed.connect(self.handle_settings_changed)
        dialog.exec()
        self.update_window_title_status("Siap")

    def handle_settings_changed(self):
        new_settings = self.sender().get_settings()
        
        if self.settings.get('theme') != new_settings.get('theme'):
            self.settings = new_settings
            self.apply_theme()
        else:
            self.settings = new_settings
        self.save_app_settings()
        self.init_clipboard_monitor()
        self.set_status_text("Pengaturan disimpan dan diterapkan.")
        if self.video_player_widget:
            self.video_player_widget.settings = self.settings
            self.video_player_widget.setup_autohide_from_settings()
        
        if self.active_search_results_dialog:
            self.active_search_results_dialog.settings = self.settings
            self.active_search_results_dialog.update_button_tooltips()

    def open_location(self, path):
        try:
            norm_path = os.path.normpath(path)
            if not os.path.exists(norm_path):
                QMessageBox.warning(self, "Lokasi Tidak Ditemukan", f"Path tidak valid: {norm_path}")
                return
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(norm_path)):
                if sys.platform == 'win32': os.startfile(norm_path)
                elif sys.platform == 'darwin': os.system(f'open "{norm_path}"')
                else: os.system(f'xdg-open "{norm_path}"')
        except Exception as e:
            QMessageBox.warning(self, "Gagal Buka Lokasi", f"Tidak dapat membuka: {norm_path}\nError: {str(e)}")

    def closeEvent(self, event):
        if self._is_closing_app:
            event.accept()
            return
        self._is_closing_app = True
        self.set_status_text("Menutup aplikasi, membersihkan...")
        event.ignore()
        QTimer.singleShot(100, self._finalize_close)

    def _finalize_close(self):
        all_threads = [self.search_thread, self.playlist_fetch_thread, self.channel_fetch_thread, self.stream_info_thread,
                       self.download_thread, self.update_check_thread, self.download_update_thread]
        for thread in all_threads:
             if thread and thread.isRunning():
                 if hasattr(thread, 'stop'):
                     thread.stop()
                 thread.quit()
                 if not thread.wait(300):
                     thread.terminate()
                     thread.wait(100)
        self.save_app_settings()
        if NVDA_CONTROL_AVAILABLE:
            nvda_disconnect()
        self.close()


