import os
import json
import sys
import shutil
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtCore import QUrl, QTimer, QStandardPaths
from PySide6.QtGui import QDesktopServices

from utils import constants
from utils.constants import set_debug_mode

try:
    from nvda_control import speak as nvda_speak
    NVDA_CONTROL_AVAILABLE = True
except (ImportError, OSError):
    NVDA_CONTROL_AVAILABLE = False
    def nvda_speak(*args, **kwargs): pass

class MainWindowCore(QMainWindow):
    BASE_TITLE = "mrd YouTube downloader"

    def __init__(self):
        super().__init__()
        self._is_closing_app = False
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
        self.related_fetch_thread = None
        self.download_thread = None
        self.search_thread = None
        self.playlist_fetch_thread = None
        self.channel_fetch_thread = None
        self.is_fetching_related = False
        self.related_seed_url = None
        self.current_results_context = "none"
        self._status_reset_timer = QTimer(self)
        self._status_reset_timer.setSingleShot(True)
        self._status_reset_timer.timeout.connect(lambda: self.main_view_widget.status_label.setText(_("Siap")))

        self.setWindowTitle(self.BASE_TITLE)
        self.set_initial_window_geometry()
        self.current_video_title_for_window = ""
        
        default_music_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation)
        if not default_music_path:
            default_music_path = os.path.join(os.path.expanduser('~'), 'Music')
        
        self.default_settings = {
            'output_path': default_music_path,
            'video_format_choice': _("Video (MP4 - Kualitas Terbaik)"),
            'audio_format_choice': _("Audio (MP3 - Kualitas Terbaik)"),
            'search_results_count': 10,
            'show_completion_popup': True,
            'debug_mode': False, 
            'search_result_double_click_action': _("Unduh Video"),
            'invert_playback_shortcuts': False,
            'autohide_delay': _('5 detik'),
            'theme': _('Light'),
            'monitor_clipboard': True,
            'embed_metadata': True,
            'use_parallel_download': False,
            'smart_autoplay_related': True,
            'smart_autoplay_related_limit': 50,
            'playback_rate': 1.0,
            'playback_volume_percent': 100,
            'audio_output_device_id': None,
            'ai_features': constants.AI_FEATURES_DEFAULT.copy(),
            'cookie_source': 'none',
            'cookie_browser': 'chrome',
            'cookie_file': '',
            'language': 'id',
        }
        self.settings = self.default_settings.copy()
        self.load_app_settings()
        if self.settings.get('use_parallel_download', False):
            aria2c_executable = "aria2c.exe" if sys.platform == "win32" else "aria2c"
            if not shutil.which(aria2c_executable):
                QMessageBox.warning(self, _("Peringatan"), 
                                    _("File yang diperlukan untuk fitur akselerasi download nggak ada. Fitur akan dinonaktifkan"))
                self.settings['use_parallel_download'] = False
                self.save_app_settings(show_error=False)

    def set_status_text(self, text):
        self.main_view_widget.status_label.setText(text)
        if NVDA_CONTROL_AVAILABLE:
            nvda_speak(text, interrupt=True)
        
        if text != _("Siap"):
            self._status_reset_timer.start(5000)

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

    def stop_active_threads(self, exclude_stream_info=False, exclude_related_fetch_thread=False, exclude_download_thread=False, exclude_playlist_fetch_thread=False, exclude_search_thread=False, exclude_channel_fetch_thread=False):
        threads_to_stop = []
        if not exclude_download_thread and self.download_thread:
            threads_to_stop.append(self.download_thread)
        if not exclude_search_thread and self.search_thread:
            threads_to_stop.append(self.search_thread)
        if not exclude_stream_info and self.stream_info_thread:
            threads_to_stop.append(self.stream_info_thread)
        if not exclude_related_fetch_thread and self.related_fetch_thread:
            threads_to_stop.append(self.related_fetch_thread)
        if not exclude_playlist_fetch_thread and self.playlist_fetch_thread:
            threads_to_stop.append(self.playlist_fetch_thread)
        if not exclude_channel_fetch_thread and self.channel_fetch_thread:
            threads_to_stop.append(self.channel_fetch_thread)
        if self.update_check_thread and self.update_check_thread.isRunning():
            threads_to_stop.append(self.update_check_thread)
        if self.download_update_thread and self.download_update_thread.isRunning():
            self.download_update_thread.stop()
            threads_to_stop.append(self.download_update_thread)
        for thread in threads_to_stop:
            if thread and thread.isRunning():
                if hasattr(thread, 'stop') and thread != self.download_update_thread:
                    thread.stop()
                thread.quit()
                if not thread.wait(700):
                    thread.terminate()
                    thread.wait(100)
        if not exclude_download_thread:
            self.download_thread = None
        if not exclude_search_thread:
            self.search_thread = None
        if not exclude_stream_info:
            self.stream_info_thread = None
        if not exclude_related_fetch_thread:
            self.related_fetch_thread = None
            self.is_fetching_related = False
        if not exclude_playlist_fetch_thread:
            self.playlist_fetch_thread = None
        if not exclude_channel_fetch_thread:
            self.channel_fetch_thread = None
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
            should_close_op_dialog = (not exclude_search_thread and title.startswith(_("Mencari"))) or \
                                     (not exclude_playlist_fetch_thread and (title.startswith(_("Memuat Playlist")) or title.startswith(_("Memuat Isi Playlist")))) or \
                                     (not exclude_channel_fetch_thread and title.startswith(_("Memuat Channel"))) or \
                                     (not exclude_stream_info and title.startswith(_("Memuat")))
            if should_close_op_dialog:
                self.operation_progress_dialog.reject()
                self.operation_progress_dialog = None

    def load_app_settings(self):
        config_dir = os.path.dirname(constants.CONFIG_FILE)
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
            except OSError as e:
                _m1 = _("Gagal membuat direktori konfigurasi:")
                _m2 = _("Error:")
                _m3 = _("Pengaturan tidak akan dimuat/disimpan.")
                QMessageBox.warning(self, _("Pengaturan Error"), f"{_m1}: {config_dir}\n{_m2}: {e}\n{_m3}")
                self.settings = self.default_settings.copy()
                set_debug_mode(self.settings.get('debug_mode', False))
                return
        try:
            if os.path.exists(constants.CONFIG_FILE):
                with open(constants.CONFIG_FILE, 'r') as f:
                    loaded_s = json.load(f)
                    for key, default_value in self.default_settings.items():
                        if key not in loaded_s:
                            loaded_s[key] = default_value
                    self.settings = loaded_s
            else:
                self.settings = self.default_settings.copy()
                self.save_app_settings(show_error=False)
            
            set_debug_mode(self.settings.get('debug_mode', False))
        except (json.JSONDecodeError, IOError) as e:
            _m1 = _("Gagal muat pengaturan dari")
            _m2 = _("Pakai default.")
            QMessageBox.warning(self, _("Pengaturan Error"), f"{_m1} {constants.CONFIG_FILE}: {e}. {_m2}")
            self.settings = self.default_settings.copy()
            set_debug_mode(self.settings.get('debug_mode', False))
            self.save_app_settings(show_error=False)
        
        if hasattr(self, 'debug_mode_action'):
            self.debug_mode_action.setChecked(constants.is_debug_mode())

    def save_app_settings(self, show_error=True):
        config_dir = os.path.dirname(constants.CONFIG_FILE)
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
            except OSError as e:
                if show_error:
                    _m1 = _("Gagal membuat direktori konfigurasi:")
                    _m2 = _("Error:")
                    QMessageBox.warning(self, _("Gagal Simpan Pengaturan"), f"{_m1}: {config_dir}\n{_m2}: {e}")
                return
        try:
            with open(constants.CONFIG_FILE, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except IOError as e:
            if show_error:
                _m1 = _("Gagal simpan ke")
                QMessageBox.warning(self, _("Gagal Simpan Pengaturan"), f"{_m1} {constants.CONFIG_FILE}: {e}")

    def set_ui_busy_state(self, busy, operation_type="general"):
        is_dialog_blocking = (self.operation_progress_dialog and self.operation_progress_dialog.isVisible()) or \
                             (self.download_progress_dialog and self.download_progress_dialog.isVisible()) or \
                             (self.update_progress_dialog and self.update_progress_dialog.isVisible())
        active_threads = [
            self.stream_info_thread, self.download_thread, self.search_thread,
            self.playlist_fetch_thread, self.channel_fetch_thread, self.download_update_thread
        ]
        is_any_thread_running = any(t and t.isRunning() for t in active_threads)

        # Special handling for update_check_thread during initial startup
        if self.update_check_thread and self.update_check_thread.isRunning() and not self._is_initial_startup_check:
            is_any_thread_running = True
        
        effective_busy_state = busy or is_any_thread_running or is_dialog_blocking or self.current_list_batch_download_active
        if operation_type == "playback" or operation_type == "playback_loading":
            effective_busy_state = busy or is_any_thread_running or is_dialog_blocking or self.current_list_batch_download_active
        is_main_view_active = self.tab_widget.currentWidget() == self.main_view_widget
        enable_main_controls = not effective_busy_state and is_main_view_active
        self.main_view_widget.input_line_edit.setEnabled(enable_main_controls)
        self.main_view_widget.search_type_combo.setEnabled(enable_main_controls)
        self.main_view_widget.go_button.setEnabled(enable_main_controls)
        
        can_open_dialogs = not is_any_thread_running and not self.current_list_batch_download_active
        self.main_view_widget.settings_button.setEnabled(can_open_dialogs)
        self.main_view_widget.info_button.setEnabled(can_open_dialogs)
        
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

    def update_window_title_status(self, status_text=""):
        parts = [self.BASE_TITLE]
        if status_text and status_text != _("Siap"):
            parts.insert(0, status_text)
        vid_name = self.current_video_title_for_window
        keywords = [
            _("mencari"), _("hasil"), _("gagal"), _("memuat"), _("isi"),
            _("mengunduh"), _("batch"), _("memutar"), _("dijeda")
        ]
        if vid_name and any(s.lower() in status_text.lower() for s in keywords):
            parts.insert(1, f"({vid_name[:30] + '...' if len(vid_name) > 30 else vid_name})")
        self.setWindowTitle(" - ".join(parts))

    def open_location(self, path):
        try:
            norm_path = os.path.normpath(path)
            if not os.path.exists(norm_path):
                _m1 = _("Path tidak valid:")
                QMessageBox.warning(self, _("Lokasi Tidak Ditemukan"), f"{_m1}: {norm_path}")
                return
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(norm_path)):
                if sys.platform == 'win32':
                    os.startfile(norm_path)
                elif sys.platform == 'darwin':
                    os.system(f'open "{norm_path}"')
                else:
                    os.system(f'xdg-open "{norm_path}"')
        except Exception as e:
            _m1 = _("Tidak dapat membuka:")
            _m2 = _("Error:")
            QMessageBox.warning(self, _("Gagal Buka Lokasi"), f"{_m1}: {norm_path}\n{_m2}: {str(e)}")
