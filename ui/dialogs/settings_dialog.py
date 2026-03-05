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
from utils.i18n import SUPPORTED_LANGUAGES

class SettingsDialog(QDialog):
    settings_changed = Signal(dict)

    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Pengaturan Aplikasi"))
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.current_settings = current_settings.copy()
        self._original_language = current_settings.get('language', 'id')

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

    @staticmethod
    def _set_combo_from_candidates(combo, candidates, fallback):
        for cand in candidates:
            idx = combo.findText(cand)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                return
        idx = combo.findText(fallback)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def init_general_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setLabelAlignment(sys.modules['PySide6.QtCore'].Qt.AlignmentFlag.AlignRight)

        # Output Directory
        default_output_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation)
        path_layout = QHBoxLayout()
        self.dir_line_edit = QLineEdit(self.current_settings.get('output_path', default_output_path))
        self.dir_line_edit.setReadOnly(True)
        select_dir_button = QPushButton(_("Pilih Folder..."))
        select_dir_button.clicked.connect(self.select_output_directory)
        path_layout.addWidget(self.dir_line_edit)
        path_layout.addWidget(select_dir_button)
        
        dir_label = QLabel(_("Simpan ke:"))
        dir_label.setBuddy(self.dir_line_edit)
        layout.addRow(dir_label, path_layout)

        # Language
        self.language_combo = QComboBox()
        self._lang_codes = list(SUPPORTED_LANGUAGES.keys())
        for code, name in SUPPORTED_LANGUAGES.items():
            self.language_combo.addItem(name, code)
        current_lang = self.current_settings.get('language', 'id')
        idx = self._lang_codes.index(current_lang) if current_lang in self._lang_codes else 0
        self.language_combo.setCurrentIndex(idx)
        lang_label = QLabel(_("Bahasa / Language:"))
        lang_label.setBuddy(self.language_combo)
        layout.addRow(lang_label, self.language_combo)

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems([_("Light"), _("Dark")])
        saved_theme = self.current_settings.get('theme', "Light")
        self._set_combo_from_candidates(self.theme_combo, [saved_theme, _(saved_theme)], _("Light"))
        theme_label = QLabel(_("Tema Aplikasi:"))
        theme_label.setBuddy(self.theme_combo)
        layout.addRow(theme_label, self.theme_combo)

        # Audio Output
        self.audio_output_button = QPushButton(_("Pilih Perangkat Output Audio"))
        self.audio_output_button.clicked.connect(self.select_audio_output_device)
        layout.addRow(_("Audio Output:"), self.audio_output_button)

        # Clipboard Monitor
        self.clipboard_monitor_checkbox = QCheckBox(_("Pantau Clipboard untuk URL YouTube"))
        self.clipboard_monitor_checkbox.setChecked(self.current_settings.get('monitor_clipboard', True))
        layout.addRow(self.clipboard_monitor_checkbox)

        # Completion Popup
        self.show_completion_popup_checkbox = QCheckBox(_("Tampilkan Notifikasi Selesai Unduh"))
        self.show_completion_popup_checkbox.setChecked(self.current_settings.get('show_completion_popup', True))
        layout.addRow(self.show_completion_popup_checkbox)

        self.tab_widget.addTab(tab, _("&Umum"))

    def init_download_format_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        # Video Format
        self.video_format_combo_box = QComboBox()
        video_choices = [
            _("Video (MP4 - Kualitas Terbaik)"),
            _("Video (MKV - Kualitas Terbaik)"),
            _("Video (WEBM - Kualitas Terbaik)"),
            _("Video (AVI - Kompatibilitas)")
        ]
        self.video_format_combo_box.addItems(video_choices)
        saved_video_choice = self.current_settings.get('video_format_choice', "Video (MP4 - Kualitas Terbaik)")
        self._set_combo_from_candidates(
            self.video_format_combo_box,
            [saved_video_choice, _(saved_video_choice)],
            _("Video (MP4 - Kualitas Terbaik)")
        )
        v_label = QLabel(_("Format Video Default:"))
        v_label.setBuddy(self.video_format_combo_box)
        layout.addRow(v_label, self.video_format_combo_box)

        # Audio Format
        self.audio_format_combo_box = QComboBox()
        audio_choices = [
            _("Audio (MP3 - Kualitas Terbaik)"),
            _("Audio (WAV - Tanpa Kompresi)"),
            _("Audio (AAC - Kualitas Baik)"),
            _("Audio (OGG Vorbis - Open Source)"),
            _("Audio (FLAC - Lossless)")
        ]
        self.audio_format_combo_box.addItems(audio_choices)
        saved_audio_choice = self.current_settings.get('audio_format_choice', "Audio (MP3 - Kualitas Terbaik)")
        self._set_combo_from_candidates(
            self.audio_format_combo_box,
            [saved_audio_choice, _(saved_audio_choice)],
            _("Audio (MP3 - Kualitas Terbaik)")
        )
        a_label = QLabel(_("Format Audio Default:"))
        a_label.setBuddy(self.audio_format_combo_box)
        layout.addRow(a_label, self.audio_format_combo_box)

        # Embed Metadata
        self.embed_metadata_checkbox = QCheckBox(_("Sematkan Thumbnail & Metadata (Audio)"))
        self.embed_metadata_checkbox.setChecked(self.current_settings.get('embed_metadata', True))
        layout.addRow(self.embed_metadata_checkbox)

        # Parallel Download
        self.parallel_download_checkbox = QCheckBox(_("Gunakan akselerasi pararel (aria2c)"))
        self.parallel_download_checkbox.setToolTip(_("Dapat mempercepat unduhan secara signifikan. Membutuhkan aria2c."))
        self.parallel_download_checkbox.setChecked(self.current_settings.get('use_parallel_download', False))
        self.parallel_download_checkbox.toggled.connect(self.on_parallel_download_toggled)
        layout.addRow(self.parallel_download_checkbox)

        # Search Results
        self.search_results_spinbox = QSpinBox()
        self.search_results_spinbox.setRange(1, 50)
        self.search_results_spinbox.setValue(self.current_settings.get('search_results_count', 10))
        s_label = QLabel(_("Jumlah Hasil Pencarian:"))
        s_label.setBuddy(self.search_results_spinbox)
        layout.addRow(s_label, self.search_results_spinbox)

        # Double Click Action
        self.double_click_action_combo = QComboBox()
        self.double_click_action_combo.addItems([_("Unduh Video"), _("Putar Audio"), _("Putar Video")])
        saved_action = self.current_settings.get('search_result_double_click_action', "Unduh Video")
        self._set_combo_from_candidates(
            self.double_click_action_combo,
            [saved_action, _(saved_action)],
            _("Unduh Video")
        )
        dc_label = QLabel(_("Aksi Dobel Klik:"))
        dc_label.setBuddy(self.double_click_action_combo)
        layout.addRow(dc_label, self.double_click_action_combo)

        self.tab_widget.addTab(tab, _("&Unduhan"))

    def init_playback_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        # Invert Shortcuts
        self.invert_playback_shortcuts_checkbox = QCheckBox(_("Balik Shortcut Putar (Enter / Ctrl+Enter)"))
        self.invert_playback_shortcuts_checkbox.setChecked(self.current_settings.get('invert_playback_shortcuts', False))
        self.invert_playback_shortcuts_checkbox.setToolTip(_("Jika aktif, Enter untuk memutar video dan Ctrl+Enter untuk memutar audio."))
        layout.addRow(self.invert_playback_shortcuts_checkbox)

        # Auto Play Next
        self.auto_play_next_checkbox = QCheckBox(_("Otomatis putar item berikutnya"))
        self.auto_play_next_checkbox.setChecked(self.current_settings.get('auto_play_next', True))
        layout.addRow(self.auto_play_next_checkbox)
        self.auto_play_next_checkbox.toggled.connect(self._update_related_autoplay_enabled)

        # Smart YouTube related autoplay
        self.smart_autoplay_related_checkbox = QCheckBox(
            _("Autoplay Pintar YouTube (rekomendasi lagu terkait)")
        )
        self.smart_autoplay_related_checkbox.setToolTip(
            _("Saat memutar dari YouTube, otomatis menambahkan antrean lagu yang relevan.")
        )
        self.smart_autoplay_related_checkbox.setChecked(
            self.current_settings.get('smart_autoplay_related', True)
        )
        layout.addRow(self.smart_autoplay_related_checkbox)
        self.smart_autoplay_related_checkbox.toggled.connect(self._update_related_limit_enabled)
        self.smart_autoplay_related_checkbox.toggled.connect(self._remember_related_autoplay_choice)
        self._last_related_autoplay_choice = self.smart_autoplay_related_checkbox.isChecked()

        self.smart_autoplay_related_limit_spinbox = QSpinBox()
        self.smart_autoplay_related_limit_spinbox.setRange(5, 150)
        self.smart_autoplay_related_limit_spinbox.setValue(
            int(self.current_settings.get('smart_autoplay_related_limit', 50))
        )
        self.smart_autoplay_related_limit_spinbox.setToolTip(
            _("Batas jumlah lagu rekomendasi yang ditambahkan ke antrean autoplay.")
        )
        self.related_limit_label = QLabel(_("Jumlah lagu rekomendasi maksimum:"))
        self.related_limit_label.setBuddy(self.smart_autoplay_related_limit_spinbox)
        layout.addRow(self.related_limit_label, self.smart_autoplay_related_limit_spinbox)
        self._update_related_autoplay_enabled(self.auto_play_next_checkbox.isChecked())

        self.tab_widget.addTab(tab, _("&Pintasan"))

    def _update_related_limit_enabled(self, checked):
        self.smart_autoplay_related_limit_spinbox.setEnabled(bool(checked))
        if hasattr(self, "related_limit_label"):
            self.related_limit_label.setEnabled(bool(checked))

    def _remember_related_autoplay_choice(self, checked):
        self._last_related_autoplay_choice = bool(checked)

    def _update_related_autoplay_enabled(self, autoplay_enabled):
        can_use_related = bool(autoplay_enabled)
        self.smart_autoplay_related_checkbox.setEnabled(can_use_related)
        if not can_use_related:
            self.smart_autoplay_related_checkbox.blockSignals(True)
            self.smart_autoplay_related_checkbox.setChecked(False)
            self.smart_autoplay_related_checkbox.blockSignals(False)
        else:
            self.smart_autoplay_related_checkbox.setChecked(
                bool(getattr(self, "_last_related_autoplay_choice", True))
            )
        related_limit_enabled = can_use_related and self.smart_autoplay_related_checkbox.isChecked()
        self.related_limit_label.setEnabled(related_limit_enabled)
        self.smart_autoplay_related_limit_spinbox.setEnabled(related_limit_enabled)

    def init_account_ai_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # Cookies Group
        cookies_group = QGroupBox(_("Autentikasi YouTube (Cookies)"))
        cookies_layout = QFormLayout()
        
        self.cookies_source_combo = QComboBox()
        self.cookies_source_combo.addItems([_("Tidak Ada"), _("Import dari Browser"), _("File Netscape Cookies (.txt)")])
        current_source = self.current_settings.get('cookie_source', 'none')
        if current_source == 'browser':
            self.cookies_source_combo.setCurrentIndex(1)
        elif current_source == 'file':
            self.cookies_source_combo.setCurrentIndex(2)
        else:
            self.cookies_source_combo.setCurrentIndex(0)
        self.cookies_source_combo.currentIndexChanged.connect(self.toggle_cookies_ui)
        c_label = QLabel(_("Sumber Cookies:"))
        c_label.setBuddy(self.cookies_source_combo)
        cookies_layout.addRow(c_label, self.cookies_source_combo)

        self.browser_label = QLabel(_("Browser:"))
        self.cookies_browser_combo = QComboBox()
        self.cookies_browser_combo.addItems(["chrome", "firefox", "opera", "edge", "chromium", "brave", "vivaldi", "safari"])
        self.cookies_browser_combo.setCurrentText(self.current_settings.get('cookie_browser', 'chrome'))
        self.browser_label.setBuddy(self.cookies_browser_combo)
        cookies_layout.addRow(self.browser_label, self.cookies_browser_combo)

        self.cookie_file_label = QLabel(_("Path File:"))
        file_layout = QHBoxLayout()
        self.cookie_file_edit = QLineEdit(self.current_settings.get('cookie_file', ''))
        self.cookie_file_edit.setReadOnly(True)
        self.cookie_file_btn = QPushButton(_("Pilih..."))
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
        g_label = QLabel(_("Kunci API Gemini:"))
        g_label.setBuddy(self.gemini_api_key_line_edit)
        gemini_layout.addRow(g_label, self.gemini_api_key_line_edit)
        main_layout.addLayout(gemini_layout)

        # AI Features Group
        ai_group = QGroupBox(_("Kemampuan AI"))
        ai_layout = QVBoxLayout()
        self.ai_feature_checkboxes = {}
        feature_flags = self.current_settings.get('ai_features', {}) or {}
        defaults = AI_FEATURES_DEFAULT.copy()
        
        for feature_key, label_text in AI_FEATURES_LABELS.items():
            checkbox = QCheckBox(label_text)
            _ai_label = _("Fitur AI:")
            checkbox.setAccessibleName(f"{_ai_label}: {label_text}")
            checkbox.setChecked(bool(feature_flags.get(feature_key, defaults.get(feature_key, True))))
            ai_layout.addWidget(checkbox)
            self.ai_feature_checkboxes[feature_key] = checkbox
            
        ai_group.setLayout(ai_layout)
        main_layout.addWidget(ai_group)
        main_layout.addStretch()

        self.tab_widget.addTab(tab, _("&Akun && AI"))

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
        path, _ = QFileDialog.getOpenFileName(
            self, _("Pilih File Cookies"), "", _("Text Files (*.txt);;All Files (*)")
        )
        if path:
            self.cookie_file_edit.setText(path)

    def on_parallel_download_toggled(self, checked):
        if checked:
            aria2c_executable = "aria2c.exe" if sys.platform == "win32" else "aria2c"
            if not shutil.which(aria2c_executable):
                QMessageBox.warning(self, _("Komponen Tidak Ditemukan"), _("aria2c tidak ditemukan di sistem. Fitur ini dimatikan."))
                self.parallel_download_checkbox.blockSignals(True)
                self.parallel_download_checkbox.setChecked(False)
                self.parallel_download_checkbox.blockSignals(False)

    def select_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, _("Pilih Folder Penyimpanan"), self.dir_line_edit.text())
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

        # Save Language
        selected_lang = self.language_combo.currentData()
        self.current_settings['language'] = selected_lang
        
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
        self.current_settings['smart_autoplay_related'] = self.smart_autoplay_related_checkbox.isChecked()
        self.current_settings['smart_autoplay_related_limit'] = self.smart_autoplay_related_limit_spinbox.value()
        self.current_settings['search_result_double_click_action'] = self.double_click_action_combo.currentText()
        self.current_settings['use_parallel_download'] = self.parallel_download_checkbox.isChecked()
        ai_features = dict(AI_FEATURES_DEFAULT)
        ai_features.update({key: checkbox.isChecked() for key, checkbox in self.ai_feature_checkboxes.items()})
        self.current_settings['ai_features'] = ai_features

        self.settings_changed.emit(self.current_settings)
        self.accept()

        # Notify user to restart if language changed
        if selected_lang != self._original_language:
            QMessageBox.information(
                self.parent(),
                _("Restart Diperlukan"),
                _("Bahasa telah diubah. Silakan restart aplikasi agar perubahan diterapkan sepenuhnya.")
            )

    def get_settings(self): return self.current_settings

    def select_audio_output_device(self):
        dialog = AudioOutputDialog(self)
        if dialog.exec() == QDialog.Accepted:
            selected_device_id = dialog.get_selected_device()
            if selected_device_id:
                self.current_settings['audio_output_device_id'] = selected_device_id
                QMessageBox.information(self, _("Perangkat Audio"), _("Perangkat output audio berhasil disimpan."))
            else:
                QMessageBox.warning(self, _("Perangkat Audio"), _("Tidak ada perangkat output audio yang dipilih."))
