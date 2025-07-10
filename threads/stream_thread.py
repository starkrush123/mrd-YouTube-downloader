import yt_dlp
from PySide6.QtCore import QThread, Signal

class StreamInfoThread(QThread):
    stream_url_ready = Signal(str, str, bool)
    stream_error = Signal(str)
    
    def __init__(self, page_url, title_hint, play_video, parent=None):
        super().__init__(parent)
        self.page_url, self.title_hint, self.play_video = page_url, title_hint, play_video
        
    def run(self):
        try:
            ydl_opts = {
                'quiet': True, 
                'nocheckcertificate': True, 
                'format': 'best[ext=mp4][height<=?1080]/best[ext=mp4]/best' if self.play_video else 'bestaudio/best'
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: 
                info = ydl.extract_info(self.page_url, download=False)
                stream_url = info.get('url')
                
            if not stream_url and 'formats' in info:
                formats = sorted(
                    [f for f in info['formats'] if f.get('url') and (
                        (self.play_video and f.get('vcodec') != 'none') or \
                        (not self.play_video and f.get('acodec') != 'none' and f.get('vcodec') == 'none')
                    )],
                    key=lambda f: (f.get('height') or 0) + (f.get('abr') or 0),
                    reverse=True
                )
                if formats: stream_url = formats[0]['url']
                
            if stream_url:
                self.stream_url_ready.emit(stream_url, info.get('title', self.title_hint or "Media Tanpa Judul"), self.play_video)
            else:
                self.stream_error.emit("Tidak dapat menemukan URL streaming valid.")
        except Exception as e:
            self.stream_error.emit(f"Gagal dapat info stream: {str(e)}")
