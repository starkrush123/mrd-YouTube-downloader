import re
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QGridLayout, QPushButton, QDialogButtonBox

class MainWindowValidation:
    def __init__(self, main_window):
        self.main_window = main_window

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
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url_text):
             return True
        return False

    def handle_direct_video_url_dialog(self, video_url):
        dialog = QDialog(self.main_window)
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
                self.main_window.download_handler.start_download(video_url, title_hint, 'video')
            elif action == 'download_audio':
                self.main_window.download_handler.start_download(video_url, title_hint, 'audio')
            elif action == 'play_video':
                self.main_window.player_handler.request_stream_info_and_play(video_url, title_hint, True)
            elif action == 'play_audio':
                self.main_window.player_handler.request_stream_info_and_play(video_url, title_hint, False)
