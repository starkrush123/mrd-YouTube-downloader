from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtMultimedia import QMediaPlayer
from ui.widgets.base_player_widget import BasePlayerWidget

class VideoPlayerWidget(BasePlayerWidget):
    def __init__(self, media_player, video_widget, parent=None, settings=None, main_window=None):
        super().__init__(media_player, parent, settings, main_window)
        self.video_widget = video_widget
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
        super().toggle_play_pause()
        self.reset_hide_controls_timer()

    def update_play_pause_button_text(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_button.setText("Jeda")
            self.play_pause_button.setToolTip("Jeda (Spasi)")
            if self.autohide_ms > 0:
                self.reset_hide_controls_timer()
        else:
            self.play_pause_button.setText("Putar")
            self.play_pause_button.setToolTip("Lanjutkan (Spasi)")
            if self.hide_controls_timer.isActive():
                self.hide_controls_timer.stop()
            self.show_controls()
