import time
import re
import yt_dlp
import traceback
from PySide6.QtCore import QThread, Signal
from utils.constants import SEARCH_CACHE, CACHE_EXPIRY_SECONDS
from utils.helpers import dprint

class SearchThread(QThread):
    results_batch_ready = Signal(list, str)
    search_finished = Signal(str, int)
    search_error = Signal(str)
    def __init__(self, query, limit_count, search_type, parent=None):
        super().__init__(parent)
        self.query = query
        self.limit_count = limit_count
        self.search_type = search_type
        
    def run(self):
        cache_key = (self.query.lower(), self.search_type, self.limit_count)
        result_type = "video" if self.search_type == "Video" else "playlist_search_results"
        if cache_key in SEARCH_CACHE:
            data, timestamp = SEARCH_CACHE[cache_key]
            if time.time() - timestamp < CACHE_EXPIRY_SECONDS:
                dprint(f"Mengambil hasil pencarian dari cache untuk: {self.query}")
                self.results_batch_ready.emit(data, result_type)
                self.search_finished.emit(result_type, len(data))
                return
        try:
            entries = []
            if self.search_type == "Video":
                ydl_opts = {'quiet': True, 'nocheckcertificate': True, 'skip_download': True, 'extract_flat': True, 'noplaylist': True}
                search_query_yt = f"ytsearch{self.limit_count}:{self.query}"
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(search_query_yt, download=False)
                
                if result and 'entries' in result and result['entries']:
                    entries = result['entries']
                elif result and result.get('_type') == 'video':
                    entries = [result]
            elif self.search_type == "Playlist":
                ydl_opts_playlist_search = {'quiet': True, 'nocheckcertificate': True, 'skip_download': True, 'extract_flat': True, 'ignoreerrors': True}
                search_query_playlist = f"ytsearch{self.limit_count}:\"{self.query}\""
                with yt_dlp.YoutubeDL(ydl_opts_playlist_search) as ydl:
                    result = ydl.extract_info(search_query_playlist, download=False)
                
                if result and 'entries' in result:
                    for entry in result['entries']:
                        if entry and entry.get('_type') == 'playlist':
                            entries.append(entry)
            if entries:
                dprint(f"Pencarian ditemukan {len(entries)} hasil untuk: {self.query}")
                SEARCH_CACHE[cache_key] = (entries, time.time())
                
                progressive_yield_point = 3
                initial_batch = entries[:progressive_yield_point]
                remaining_batch = entries[progressive_yield_point:]
                
                if initial_batch:
                    self.results_batch_ready.emit(initial_batch, result_type)
                
                if remaining_batch:
                    time.sleep(0.2)
                    self.results_batch_ready.emit(remaining_batch, result_type)
                
                self.search_finished.emit(result_type, len(entries))
            else:
                self.search_error.emit(f"Tidak ada hasil {self.search_type.lower()} ditemukan untuk \"{self.query}\".")
                    
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            msg = error_msg.split('\n')[-1] if '\n' in error_msg else error_msg
            if "Unsupported URL" in error_msg: self.search_error.emit(f"URL/format pencarian tidak didukung.")
            elif "Unable to extract video data" in error_msg: self.search_error.emit("Tidak dapat mengambil data.")
            else: self.search_error.emit(f"Kesalahan yt-dlp: {msg}")
        except Exception as e:
            dprint(f"Error di SearchThread: {traceback.format_exc()}")
            self.search_error.emit(f"Kesalahan tak terduga: {str(e)}")

class PlaylistFetchThread(QThread):
    results_ready = Signal(list, str, str)
    fetch_error = Signal(str)
    playlist_info_ready = Signal(dict)
    def __init__(self, playlist_url, parent=None):
        super().__init__(parent)
        self.playlist_url = playlist_url

    def run(self):
        ydl_opts = {'quiet': True, 'nocheckcertificate': True, 'extract_flat': True, 'skip_download': True, 'ignoreerrors': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_meta = ydl.extract_info(self.playlist_url, download=False, process=False, extra_info={'extract_flat': 'discard_in_playlist'})
                if not playlist_meta or playlist_meta.get('_type') != 'playlist':
                    self.fetch_error.emit(f"URL ('{self.playlist_url[:50]}...') bukan playlist valid.")
                    return
                self.playlist_info_ready.emit(playlist_meta)
                result = ydl.extract_info(self.playlist_url, download=False, process=True)
            if result and result.get('_type') == 'playlist' and 'entries' in result:
                playlist_title = result.get('title', 'Playlist Tanpa Judul')
                original_playlist_url = result.get('webpage_url', self.playlist_url)
                entries = [entry for entry in result.get('entries', []) if entry and entry.get('url')]
                if not entries and result.get('entries'):
                    self.fetch_error.emit(f"Playlist '{playlist_title}' tidak berisi video valid.")
                    return
                if not entries:
                    self.fetch_error.emit(f"Playlist '{playlist_title}' kosong.")
                    return
                self.results_ready.emit(entries, playlist_title, original_playlist_url)
            else:
                self.fetch_error.emit(f"Tidak dapat ambil item dari URL: '{self.playlist_url[:50]}...'.")
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            detailed_error = re.search(r'ERROR: (.*?)(?:;|$)', error_msg, re.DOTALL)
            msg = detailed_error.group(1).strip() if detailed_error else error_msg.split('\n')[0]
            if "Unsupported URL" in msg: self.fetch_error.emit(f"URL tidak didukung: {self.playlist_url[:50]}...")
            elif "Unable to download webpage" in msg or "HTTP Error 404" in msg: self.fetch_error.emit(f"Playlist tidak ditemukan/akses: {self.playlist_url[:50]}...")
            elif "This playlist is private" in msg or "Video unavailable" in msg: self.fetch_error.emit(f"Playlist pribadi/tidak tersedia: {self.playlist_url[:50]}...")
            else: self.fetch_error.emit(f"Gagal ambil playlist: {msg}")
        except Exception as e:
            self.fetch_error.emit(f"Kesalahan tak terduga: {str(e)}")

class ChannelFetchThread(QThread):
    results_ready = Signal(list, str, str)
    fetch_error = Signal(str)
    
    def __init__(self, channel_url, parent=None):
        super().__init__(parent)
        self.channel_url = channel_url
        
    def run(self):
        ydl_opts = {
            'quiet': True, 'nocheckcertificate': True, 'extract_flat': False,
            'skip_download': True, 'ignoreerrors': True, 'playlistend': 100
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(self.channel_url, download=False)
            if result and result.get('_type') == 'playlist' and 'entries' in result:
                channel_title = result.get('title', 'Channel Tanpa Judul')
                original_channel_url = result.get('webpage_url', self.channel_url)
                
                entries = [entry for entry in result.get('entries', []) if entry and entry.get('url')]
                if not entries:
                    self.fetch_error.emit(f"Channel '{channel_title}' tidak berisi video atau video tidak dapat diakses.")
                    return
                    
                self.results_ready.emit(entries, channel_title, original_channel_url)
            else:
                self.fetch_error.emit(f"Tidak dapat mengambil video dari channel: '{self.channel_url[:50]}...'. Pastikan URL channel valid.")
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            msg = re.search(r'ERROR: (.*?)(?:;|$)', error_msg, re.DOTALL)
            msg = msg.group(1).strip() if msg else error_msg.split('\n')[0]
            self.fetch_error.emit(f"Gagal mengambil info channel: {msg}")
        except Exception as e:
            self.fetch_error.emit(f"Kesalahan tak terduga saat mengambil channel: {str(e)}")
