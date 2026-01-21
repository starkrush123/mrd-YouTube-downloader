import sys
import shutil
import keyring
from keyring.errors import PasswordDeleteError

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QComboBox, 
    QLabel, QFileDialog, QDialogButtonBox, QGridLayout, QSpinBox, QCheckBox, QMessageBox,
    QGroupBox, QTabWidget, QWidget, QFormLayout
)
from PySide6.QtCore import Signal, QStandardPaths
from ui.dialogs.audio_output_dialog import AudioOutputDialog
from utils.constants import AI_FEATURES_DEFAULT, AI_FEATURES_LABELS

class SettingsDialog(QDialog):
    settings_changed = Signal(dict)

    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pengaturan Aplikasi")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.current_settings = current_settings.copy()

        # Main Layout
        main_layout = QVBoxLayout(self)

        # Tab Widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Initialize Tabs
        self.init_general_tab()
        self.init_download_format_tab()
        self.init_playback_tab()
        self.init_account_ai_tab()

        # Dialog Buttons (OK/Cancel)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept_settings)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        # Initial UI State updates
        self.toggle_cookies_ui()

    def init_general_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setLabelAlignment(sys.modules['PySide6.QtCore'].Qt.AlignmentFlag.AlignRight)

        # Output Directory
        default_output_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation)
        path_layout = QHBoxLayout()
        self.dir_line_edit = QLineEdit(self.current_settings.get('output_path', default_output_path))
        self.dir_line_edit.setReadOnly(True)
        select_dir_button = QPushButton("Pilih Folder...")
        select_dir_button.clicked.connect(self.select_output_directory)
        path_layout.addWidget(self.dir_line_edit)
        path_layout.addWidget(select_dir_button)
        
        dir_label = QLabel("Simpan ke:")
        dir_label.setBuddy(self.dir_line_edit)
        layout.addRow(dir_label, path_layout)

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText(self.current_settings.get('theme', "Light"))
        theme_label = QLabel("Tema Aplikasi:")
        theme_label.setBuddy(self.theme_combo)
        layout.addRow(theme_label, self.theme_combo)

        # Audio Output
        self.audio_output_button = QPushButton("Pilih Perangkat Output Audio")
        self.audio_output_button.clicked.connect(self.select_audio_output_device)
        layout.addRow("Audio Output:", self.audio_output_button)

        # Clipboard Monitor
        self.clipboard_monitor_checkbox = QCheckBox("Pantau Clipboard untuk URL YouTube")
        self.clipboard_monitor_checkbox.setChecked(self.current_settings.get('monitor_clipboard', True))
        layout.addRow(self.clipboard_monitor_checkbox)

        # Completion Popup
        self.show_completion_popup_checkbox = QCheckBox("Tampilkan Notifikasi Selesai Unduh")
        self.show_completion_popup_checkbox.setChecked(self.current_settings.get('show_completion_popup', True))
        layout.addRow(self.show_completion_popup_checkbox)

        self.tab_widget.addTab(tab, "&Umum")

    def init_download_format_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        # Video Format
        self.video_format_combo_box = QComboBox()
        self.video_format_combo_box.addItems(["Video (MP4 - Kualitas Terbaik)", "Video (MKV - Kualitas Terbaik)", "Video (WEBM - Kualitas Terbaik)", "Video (AVI - Kompatibilitas)"])
        self.video_format_combo_box.setCurrentText(self.current_settings.get('video_format_choice', "Video (MP4 - Kualitas Terbaik)"))
        v_label = QLabel("Format Video Default:")
        v_label.setBuddy(self.video_format_combo_box)
        layout.addRow(v_label, self.video_format_combo_box)

        # Audio Format
        self.audio_format_combo_box = QComboBox()
        self.audio_format_combo_box.addItems(["Audio (MP3 - Kualitas Terbaik)", "Audio (WAV - Tanpa Kompresi)", "Audio (AAC - Kualitas Baik)", "Audio (OGG Vorbis - Open Source)", "Audio (FLAC - Lossless)"])
        self.audio_format_combo_box.setCurrentText(self.current_settings.get('audio_format_choice', "Audio (MP3 - Kualitas Terbaik)"))
        a_label = QLabel("Format Audio Default:")
        a_label.setBuddy(self.audio_format_combo_box)
        layout.addRow(a_label, self.audio_format_combo_box)

        # Embed Metadata
        self.embed_metadata_checkbox = QCheckBox("Sematkan Thumbnail & Metadata (Audio)")
        self.embed_metadata_checkbox.setChecked(self.current_settings.get('embed_metadata', True))
        layout.addRow(self.embed_metadata_checkbox)

        # Parallel Download
        self.parallel_download_checkbox = QCheckBox("Gunakan akselerasi pararel (aria2c)")
        self.parallel_download_checkbox.setToolTip("Dapat mempercepat unduhan secara signifikan. Membutuhkan aria2c.")
        self.parallel_download_checkbox.setChecked(self.current_settings.get('use_parallel_download', False))
        self.parallel_download_checkbox.toggled.connect(self.on_parallel_download_toggled)
        layout.addRow(self.parallel_download_checkbox)

        # Search Results
        self.search_results_spinbox = QSpinBox()
        self.search_results_spinbox.setRange(1, 50)
        self.search_results_spinbox.setValue(self.current_settings.get('search_results_count', 10))
        s_label = QLabel("Jumlah Hasil Pencarian:")
        s_label.setBuddy(self.search_results_spinbox)
        layout.addRow(s_label, self.search_results_spinbox)

        # Double Click Action
        self.double_click_action_combo = QComboBox()
        self.double_click_action_combo.addItems(["Unduh Video", "Putar Audio", "Putar Video"])
        self.double_click_action_combo.setCurrentText(self.current_settings.get('search_result_double_click_action', "Unduh Video"))
        dc_label = QLabel("Aksi Dobel Klik:")
        dc_label.setBuddy(self.double_click_action_combo)
        layout.addRow(dc_label, self.double_click_action_combo)

        self.tab_widget.addTab(tab, "&Unduhan")

    def init_playback_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        # Invert Shortcuts
        self.invert_playback_shortcuts_checkbox = QCheckBox("Balik Shortcut Putar (Enter / Ctrl+Enter)")
        self.invert_playback_shortcuts_checkbox.setChecked(self.current_settings.get('invert_playback_shortcuts', False))
        self.invert_playback_shortcuts_checkbox.setToolTip("Jika aktif, Enter untuk memutar video dan Ctrl+Enter untuk memutar audio.")
        layout.addRow(self.invert_playback_shortcuts_checkbox)

        # Auto Play Next
        self.auto_play_next_checkbox = QCheckBox("Otomatis putar item berikutnya")
        self.auto_play_next_checkbox.setChecked(self.current_settings.get('auto_play_next', True))
        layout.addRow(self.auto_play_next_checkbox)

        self.tab_widget.addTab(tab, "&Pintasan")

    def init_account_ai_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # Cookies Group
        cookies_group = QGroupBox("Autentikasi YouTube (Cookies)")
        cookies_layout = QFormLayout()
        
        self.cookies_source_combo = QComboBox()
        self.cookies_source_combo.addItems(["Tidak Ada", "Import dari Browser", "File Netscape Cookies (.txt)"])
        current_source = self.current_settings.get('cookie_source', 'none')
        if current_source == 'browser':
            self.cookies_source_combo.setCurrentIndex(1)
        elif current_source == 'file':
            self.cookies_source_combo.setCurrentIndex(2)
        else:
            self.cookies_source_combo.setCurrentIndex(0)
        self.cookies_source_combo.currentIndexChanged.connect(self.toggle_cookies_ui)
        c_label = QLabel("Sumber Cookies:")
        c_label.setBuddy(self.cookies_source_combo)
        cookies_layout.addRow(c_label, self.cookies_source_combo)

        self.browser_label = QLabel("Browser:")
        self.cookies_browser_combo = QComboBox()
        self.cookies_browser_combo.addItems(["chrome", "firefox", "opera", "edge", "chromium", "brave", "vivaldi", "safari"])
        self.cookies_browser_combo.setCurrentText(self.current_settings.get('cookie_browser', 'chrome'))
        self.browser_label.setBuddy(self.cookies_browser_combo)
        cookies_layout.addRow(self.browser_label, self.cookies_browser_combo)

        self.cookie_file_label = QLabel("Path File:")
        file_layout = QHBoxLayout()
        self.cookie_file_edit = QLineEdit(self.current_settings.get('cookie_file', ''))
        self.cookie_file_edit.setReadOnly(True)
        self.cookie_file_btn = QPushButton("Pilih...")
        self.cookie_file_btn.clicked.connect(self.select_cookie_file)
        file_layout.addWidget(self.cookie_file_edit)
        file_layout.addWidget(self.cookie_file_btn)
        self.cookie_file_label.setBuddy(self.cookie_file_edit)
        cookies_layout.addRow(self.cookie_file_label, file_layout)

        cookies_group.setLayout(cookies_layout)
        main_layout.addWidget(cookies_group)

        # Gemini API
        gemini_layout = QFormLayout()
        gemini_api_key = keyring.get_password("mrd-youtube-downloader", "gemini_api_key")
        self.gemini_api_key_line_edit = QLineEdit(gemini_api_key if gemini_api_key else '')
        self.gemini_api_key_line_edit.setEchoMode(QLineEdit.EchoMode.Password) # Security best practice
        g_label = QLabel("Kunci API Gemini:")
        g_label.setBuddy(self.gemini_api_key_line_edit)
        gemini_layout.addRow(g_label, self.gemini_api_key_line_edit)
        main_layout.addLayout(gemini_layout)

        # AI Features Group
        ai_group = QGroupBox("Kemampuan AI")
        ai_layout = QVBoxLayout()
        self.ai_feature_checkboxes = {}
        feature_flags = self.current_settings.get('ai_features', {}) or {}
        defaults = AI_FEATURES_DEFAULT.copy()
        
        for feature_key, label_text in AI_FEATURES_LABELS.items():
            checkbox = QCheckBox(label_text)
            checkbox.setAccessibleName(f"Fitur AI: {label_text}")
            checkbox.setChecked(bool(feature_flags.get(feature_key, defaults.get(feature_key, True))))
            ai_layout.addWidget(checkbox)
            self.ai_feature_checkboxes[feature_key] = checkbox
            
        ai_group.setLayout(ai_layout)
        main_layout.addWidget(ai_group)
        main_layout.addStretch()

        self.tab_widget.addTab(tab, "&Akun && AI")

    def toggle_cookies_ui(self):
        idx = self.cookies_source_combo.currentIndex()
        # 0: None, 1: Browser, 2: File
        is_browser = (idx == 1)
        is_file = (idx == 2)
        
        self.browser_label.setVisible(is_browser)
        self.cookies_browser_combo.setVisible(is_browser)
        
        self.cookie_file_label.setVisible(is_file)
        self.cookie_file_edit.setVisible(is_file)
        self.cookie_file_btn.setVisible(is_file)

    def select_cookie_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pilih File Cookies", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.cookie_file_edit.setText(path)

    def on_parallel_download_toggled(self, checked):
        if checked:
            aria2c_executable = "aria2c.exe" if sys.platform == "win32" else "aria2c"
            if not shutil.which(aria2c_executable):
                QMessageBox.warning(self, "Komponen Tidak Ditemukan", "aria2c tidak ditemukan di sistem. Fitur ini dimatikan.")
                self.parallel_download_checkbox.blockSignals(True)
                self.parallel_download_checkbox.setChecked(False)
                self.parallel_download_checkbox.blockSignals(False)

    def select_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Pilih Folder Penyimpanan", self.dir_line_edit.text())
        if directory:
            self.dir_line_edit.setText(directory)

    def accept_settings(self):
        # Save API key to keyring
        api_key = self.gemini_api_key_line_edit.text()
        if api_key:
            keyring.set_password("mrd-youtube-downloader", "gemini_api_key", api_key)
        else:
            try:
                keyring.delete_password("mrd-youtube-downloader", "gemini_api_key")
            except PasswordDeleteError:
                pass

        self.current_settings['output_path'] = self.dir_line_edit.text()
        self.current_settings['theme'] = self.theme_combo.currentText()
        
        # Save Cookies Settings
        c_idx = self.cookies_source_combo.currentIndex()
        if c_idx == 1:
            self.current_settings['cookie_source'] = 'browser'
        elif c_idx == 2:
            self.current_settings['cookie_source'] = 'file'
        else:
            self.current_settings['cookie_source'] = 'none'
            
        self.current_settings['cookie_browser'] = self.cookies_browser_combo.currentText()
        self.current_settings['cookie_file'] = self.cookie_file_edit.text()

        self.current_settings['monitor_clipboard'] = self.clipboard_monitor_checkbox.isChecked()
        self.current_settings['embed_metadata'] = self.embed_metadata_checkbox.isChecked()
        self.current_settings['video_format_choice'] = self.video_format_combo_box.currentText()
        self.current_settings['audio_format_choice'] = self.audio_format_combo_box.currentText()
        self.current_settings['search_results_count'] = self.search_results_spinbox.value()
        self.current_settings['show_completion_popup'] = self.show_completion_popup_checkbox.isChecked()
        self.current_settings['invert_playback_shortcuts'] = self.invert_playback_shortcuts_checkbox.isChecked()
        self.current_settings['auto_play_next'] = self.auto_play_next_checkbox.isChecked()
        self.current_settings['search_result_double_click_action'] = self.double_click_action_combo.currentText()
        self.current_settings['use_parallel_download'] = self.parallel_download_checkbox.isChecked()
        ai_features = dict(AI_FEATURES_DEFAULT)
        ai_features.update({key: checkbox.isChecked() for key, checkbox in self.ai_feature_checkboxes.items()})
        self.current_settings['ai_features'] = ai_features

        self.settings_changed.emit(self.current_settings)
        self.accept()

    def get_settings(self): return self.current_settings

    def select_audio_output_device(self):
        dialog = AudioOutputDialog(self)
        if dialog.exec() == QDialog.Accepted:
            selected_device_id = dialog.get_selected_device()
            if selected_device_id:
                self.current_settings['audio_output_device_id'] = selected_device_id
                QMessageBox.information(self, "Perangkat Audio", "Perangkat output audio berhasil disimpan.")
            else:
                QMessageBox.warning(self, "Perangkat Audio", "Tidak ada perangkat output audio yang dipilih.")
