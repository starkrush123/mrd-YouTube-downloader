import sys
import os
import shutil

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QMessageBox
)
from ui.widgets.history_tab import HistoryTab
from PySide6.QtCore import (
    QTimer, Qt, QUrl, QStandardPaths
)
from PySide6.QtGui import (
    QKeySequence, QShortcut, QDesktopServices
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

# Local imports
from utils import constants
from threads.update_thread import UpdateCheckThread, DownloadUpdateThread
from threads.stream_thread import StreamInfoThread
from threads.search_thread import SearchThread, PlaylistFetchThread, ChannelFetchThread
from threads.download_thread import DownloadThread
from ui.widgets.main_layout import MainLayout
from ui.widgets.menu_bar import MenuBar
from ui.handlers.search_handler import SearchHandler
from ui.handlers.download_handler import DownloadHandler
from ui.handlers.player_handler import PlayerHandler
from ui.handlers.dialog_handler import DialogHandler
from ui.handlers.signal_connector import SignalConnector

# Import refactored modules
from ui.core.main_window_core import MainWindowCore
from ui.events.main_window_events import MainWindowEvents
from ui.update.main_window_update import MainWindowUpdate
from ui.validation.main_window_validation import MainWindowValidation
from ui.settings.main_window_settings import MainWindowSettings

try:
    from nvda_control import speak as nvda_speak
    NVDA_CONTROL_AVAILABLE = True
except (ImportError, OSError):
    NVDA_CONTROL_AVAILABLE = False
    def nvda_speak(*args, **kwargs): pass

class MainWindow(MainWindowCore):
    def __init__(self):
        super().__init__()

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        
        self.video_widget = QVideoWidget()
        self.video_player_widget = None
        self.audio_player_widget = None

        # Initialize refactored modules
        self.events = MainWindowEvents(self)
        self.update_manager = MainWindowUpdate(self)
        self.validation = MainWindowValidation(self)
        self.app_settings = MainWindowSettings(self)
        self.last_focused_widget = None
        

        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        self.main_view_widget = MainLayout()
        self.history_tab = HistoryTab()
        
        self.tab_widget.addTab(self.main_view_widget, "Downloader")
        self.tab_widget.addTab(self.history_tab, "Riwayat Download")
        
        self._create_menu_bar()
        self.main_view_widget.search_type_combo.currentTextChanged.connect(self.events._update_placeholder_text)
        self.events._update_placeholder_text(self.main_view_widget.search_type_combo.currentText())

        # Handlers
        self.search_handler = SearchHandler(self)
        self.download_handler = DownloadHandler(self)
        self.player_handler = PlayerHandler(self)
        self.dialog_handler = DialogHandler(self)
        
        self.setup_shortcuts()

        # Signal Connector
        self.signal_connector = SignalConnector(self, self.search_handler, self.download_handler, self.player_handler, self.dialog_handler)
        self.signal_connector.connect_signals()
        
        self.update_window_title_status("Siap")
        self.app_settings.apply_theme()
        self.events.init_clipboard_monitor()
        
        QTimer.singleShot(0, self.main_view_widget.input_line_edit.setFocus)
        QTimer.singleShot(2000, lambda: self.update_manager.initiate_update_check(manual_check=False))

    def _create_menu_bar(self):
        menu_bar = MenuBar(self)
        self.setMenuBar(menu_bar)

    def setup_shortcuts(self):
        self.play_video_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.play_audio_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)

    # Delegate methods to their respective modules
    def set_status_text(self, text):
        super().set_status_text(text)

    def toggle_debug_mode(self, checked):
        self.app_settings.toggle_debug_mode(checked)

    def open_debug_log(self):
        self.app_settings.open_debug_log()

    def open_current_download_folder(self):
        self.app_settings.open_current_download_folder()

    def clear_input_field(self):
        self.events.clear_input_field()

    def paste_and_process_input(self):
        self.events.paste_and_process_input()

    def initiate_update_check(self, manual_check=True):
        self.update_manager.initiate_update_check(manual_check)

    def handle_update_available(self, version_info, manual_check):
        self.update_manager.handle_update_available(version_info, manual_check)

    def handle_no_update_found(self, message, manual_check):
        self.update_manager.handle_no_update_found(message, manual_check)

    def handle_update_check_error(self, error_message, manual_check):
        self.update_manager.handle_update_check_error(error_message, manual_check)

    def start_update_download(self, sfx_url):
        self.update_manager.start_update_download(sfx_url)

    def cancel_update_download(self):
        self.update_manager.cancel_update_download()

    def handle_update_download_progress(self, percentage):
        self.update_manager.handle_update_download_progress(percentage)

    def handle_update_download_finished(self, sfx_path):
        self.update_manager.handle_update_download_finished(sfx_path)

    def handle_update_download_error(self, error_message):
        self.update_manager.handle_update_download_error(error_message)

    def is_valid_youtube_url(self, url_text):
        return self.validation.is_valid_youtube_url(url_text)
        
    def is_youtube_channel_url(self, url_text):
        return self.validation.is_youtube_channel_url(url_text)

    def is_potential_playlist_url(self, url_text):
        return self.validation.is_potential_playlist_url(url_text)

    def is_valid_youtube_video_url(self, url_text):
        return self.validation.is_valid_youtube_video_url(url_text)

    def is_likely_direct_video_url(self, url_text):
        return self.validation.is_likely_direct_video_url(url_text)

    def handle_direct_video_url_dialog(self, video_url):
        self.validation.handle_direct_video_url_dialog(video_url)

    def stop_current_operation(self, confirm=True):
        self.events.stop_current_operation(confirm)

    def _on_any_thread_finished(self):
        self.events._on_any_thread_finished()

    def restore_focus_after_download(self):
        self.events.restore_focus_after_download()

    def update_window_title_status(self, status_text=""):
        super().update_window_title_status(status_text)

    def open_location(self, path):
        super().open_location(path)

    def closeEvent(self, event):
        self.events.closeEvent(event)

    def _finalize_close(self):
        self.events._finalize_close()

    def _try_restore_focus_after_manual_check(self):
        self.update_manager._try_restore_focus_after_manual_check()

    def check_clipboard(self):
        self.events.check_clipboard()

    

    def keyPressEvent(self, event):
        self.events.keyPressEvent(event)
