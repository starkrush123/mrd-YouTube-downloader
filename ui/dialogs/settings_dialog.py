import sys
import shutil
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QComboBox, 
    QLabel, QFileDialog, QDialogButtonBox, QGridLayout, QSpinBox, QCheckBox, QMessageBox
)
from PySide6.QtCore import Signal, QStandardPaths

class SettingsDialog(QDialog):
    settings_changed = Signal(dict)
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
        
        self.settings_changed.emit(self.current_settings)
        self.accept()

    def get_settings(self): return self.current_settings
