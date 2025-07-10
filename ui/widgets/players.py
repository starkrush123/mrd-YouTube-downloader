from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtMultimedia import QMediaPlayer

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
