import yt_dlp
import os
from PySide6.QtCore import QThread, Signal
from utils.helpers import get_js_runtime_options, classify_yt_dlp_error

class StreamInfoThread(QThread):
    stream_url_ready = Signal(str, str, bool)
    stream_error = Signal(str)
    
    def __init__(self, page_url, title_hint, play_video, cookie_params=None, parent=None):
        super().__init__(parent)
        self.page_url, self.title_hint, self.play_video = page_url, title_hint, play_video
        self.cookie_params = cookie_params or {}
        
    def run(self):
        try:
            ydl_opts = {
                'quiet': True, 
                'nocheckcertificate': True, 
                'format': 'best[protocol^=http][ext=mp4][height<=?1080]/best[protocol^=http][height<=?1080]/best[protocol^=http]' if self.play_video else 'bestaudio[protocol^=http]/bestaudio/best[protocol^=http]'
            }
            
            # Apply Cookie Options
            c_source = self.cookie_params.get('source', 'none')
            if c_source == 'browser':
                c_browser = self.cookie_params.get('browser', 'chrome')
                ydl_opts['cookiesfrombrowser'] = (c_browser, None, None)
            elif c_source == 'file':
                c_file = self.cookie_params.get('file', '')
                if c_file and os.path.exists(c_file):
                    ydl_opts['cookiefile'] = c_file
            
            ydl_opts.update(get_js_runtime_options())

            with yt_dlp.YoutubeDL(ydl_opts) as ydl: 
                info = ydl.extract_info(self.page_url, download=False)
                stream_url = info.get('url')
                
            if not stream_url and 'formats' in info:
                formats = sorted(
                    [f for f in info['formats'] if f.get('url') and (f.get('protocol', '').startswith('http')) and (
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
        except yt_dlp.utils.DownloadError as e:
            err_str = str(e)
            classified = classify_yt_dlp_error(err_str)
            if classified:
                self.stream_error.emit(classified)
            elif "Could not copy" in err_str and "cookie" in err_str:
                self.stream_error.emit("Browser terkunci: Tutup browser untuk import cookies.")
            elif "Failed to decrypt" in err_str or "DPAPI" in err_str:
                self.stream_error.emit("Gagal dekripsi cookies. Gunakan metode File Cookies (.txt).")
            else:
                self.stream_error.emit(f"Gagal dapat info stream: {err_str}")
        except Exception as e:
            self.stream_error.emit(f"Gagal dapat info stream: {str(e)}")
