from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer
from ui.widgets.base_player_widget import BasePlayerWidget

class AudioPlayerWidget(BasePlayerWidget):
    def __init__(self, media_player, parent=None, settings=None, main_window=None):
        super().__init__(media_player, parent, settings, main_window)
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

    def update_title(self, title):
        self.title_label.setText(title)

    def format_duration_ms(self, ms):
        try:
            if not isinstance(ms, (int, float)) or ms < 0:
                return "00:00"
            s_total = round(ms / 1000.0)
            m_total, s_val = divmod(s_total, 60)
            h_val, m_val = divmod(m_total, 60)
            return f"{int(h_val):d}:{int(m_val):02d}:{int(s_val):02d}" if h_val > 0 else f"{int(m_val):02d}:{int(s_val):02d}"
        except Exception:
            return "00:00"

    def update_status_labels(self):
        pos, dur, state = self.media_player.position(), self.media_player.duration(), self.media_player.playbackState()
        status_text = f"{self.format_duration_ms(pos)} / {self.format_duration_ms(dur)}"
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.status_label.setText(f"Memutar: {status_text}")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.status_label.setText(f"Dijeda: {status_text}")
        else:
            self.status_label.setText(f"Berhenti: {status_text}")

    def update_controls_on_state_change(self, state):
        self.update_status_labels()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_button.setText("Jeda")
            self.play_pause_button.setToolTip("Jeda (Spasi)")
        else:
            self.play_pause_button.setText("Putar")
            self.play_pause_button.setToolTip("Lanjutkan (Spasi)")
