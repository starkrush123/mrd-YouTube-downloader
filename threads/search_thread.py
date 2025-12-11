import time
import re
import os
import yt_dlp
import traceback
import urllib.parse
from PySide6.QtCore import QThread, Signal
from utils.constants import (
    SEARCH_CACHE,
    CACHE_EXPIRY_SECONDS,
    MAX_SEARCH_CACHE_ENTRIES,
    CACHE_LOCK,
)
from utils.helpers import dprint

def _cleanup_and_get_from_cache(cache_key, now):
    with CACHE_LOCK:
        entry = SEARCH_CACHE.get(cache_key)
        if entry:
            data, timestamp = entry
            if now - timestamp < CACHE_EXPIRY_SECONDS:
                SEARCH_CACHE.move_to_end(cache_key)
                return data
            SEARCH_CACHE.pop(cache_key, None)
        stale_keys = [
            key for key, (_, ts) in SEARCH_CACHE.items()
            if now - ts >= CACHE_EXPIRY_SECONDS
        ]
        for key in stale_keys:
            SEARCH_CACHE.pop(key, None)
    return None

def _store_in_cache(cache_key, data):
    with CACHE_LOCK:
        SEARCH_CACHE[cache_key] = (data, time.time())
        SEARCH_CACHE.move_to_end(cache_key)
        while len(SEARCH_CACHE) > MAX_SEARCH_CACHE_ENTRIES:
            SEARCH_CACHE.popitem(last=False)

class SearchThread(QThread):
    results_batch_ready = Signal(list, str)
    search_finished = Signal(str, int)
    search_error = Signal(str)
    def __init__(self, query, limit_count, search_type, cookie_params=None, parent=None):
        super().__init__(parent)
        self.query = query
        self.limit_count = limit_count
        self.search_type = search_type
        self.cookie_params = cookie_params or {}
        
    def run(self):
        cache_key = (self.query.lower(), self.search_type, self.limit_count)
        result_type = "video" if self.search_type == "Video" else "playlist_search_results"
        now = time.time()
        cached_data = _cleanup_and_get_from_cache(cache_key, now)
        if cached_data is not None:
            dprint(f"Mengambil hasil pencarian dari cache untuk: {self.query}")
            self.results_batch_ready.emit(cached_data, result_type)
            self.search_finished.emit(result_type, len(cached_data))
            return
        try:
            entries = []
            
            # Prepare Cookie Options
            cookie_opts = {}
            c_source = self.cookie_params.get('source', 'none')
            if c_source == 'browser':
                c_browser = self.cookie_params.get('browser', 'chrome')
                cookie_opts['cookiesfrombrowser'] = (c_browser, None, None)
            elif c_source == 'file':
                c_file = self.cookie_params.get('file', '')
                if c_file and os.path.exists(c_file):
                    cookie_opts['cookiefile'] = c_file

            if self.search_type == "Video":
                ydl_opts = {'quiet': True, 'nocheckcertificate': True, 'skip_download': True, 'extract_flat': True, 'noplaylist': True}
                ydl_opts.update(cookie_opts)
                search_query_yt = f"ytsearch{self.limit_count}:{self.query}"
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(search_query_yt, download=False)
                
                if result and 'entries' in result and result['entries']:
                    entries = result['entries']
                elif result and result.get('_type') == 'video':
                    entries = [result]
            elif self.search_type == "Playlist":
                entries = self._search_playlists_direct(self.query, self.limit_count, cookie_opts)
            if entries:
                dprint(f"Pencarian ditemukan {len(entries)} hasil untuk: {self.query}")
                _store_in_cache(cache_key, entries)
                
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
            if "Could not copy" in error_msg and "cookie" in error_msg:
                self.search_error.emit("Browser terkunci: Tutup browser Anda.")
                return
            elif "Failed to decrypt" in error_msg or "DPAPI" in error_msg:
                self.search_error.emit("Gagal dekripsi cookies browser. Gunakan metode File Cookies.")
                return

            msg = error_msg.split('\n')[-1] if '\n' in error_msg else error_msg
            if "Unsupported URL" in error_msg: self.search_error.emit(f"URL/format pencarian tidak didukung.")
            elif "Unable to extract video data" in error_msg: self.search_error.emit("Tidak dapat mengambil data.")
            else: self.search_error.emit(f"Kesalahan yt-dlp: {msg}")
        except Exception as e:
            dprint(f"Error di SearchThread: {traceback.format_exc()}")
            self.search_error.emit(f"Kesalahan tak terduga: {str(e)}")

    def _search_playlists_direct(self, query, limit_count, cookie_opts=None):
        try:
            max_results = max(1, int(limit_count))
        except (TypeError, ValueError):
            max_results = 10
        encoded_query = urllib.parse.quote(query)
        playlist_search_url = (
            f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgIQAw%253D%253D"
        )
        ydl_opts = {
            'quiet': True,
            'nocheckcertificate': True,
            'skip_download': True,
            'extract_flat': True,
            'noplaylist': False,
            'ignoreerrors': True,
            'force_generic_extractor': True,
        }
        if cookie_opts:
            ydl_opts.update(cookie_opts)

        collected = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_search_url, download=False)
        except Exception as exc:
            dprint(f"Playlist search failed for '{query}': {exc}")
            return collected

        raw_entries = []
        if isinstance(info, dict):
            entries = info.get('entries')
            if isinstance(entries, list):
                raw_entries = entries
            elif info.get('_type') == 'playlist':
                raw_entries = info.get('entries', [])

        for entry in raw_entries:
            if not entry:
                continue

            entry_ie = entry.get('ie_key')
            entry_type = entry.get('_type')

            if entry_type == 'playlist' or entry_ie in ('YoutubePlaylist', 'YoutubeTab'):
                playlist_url = entry.get('webpage_url') or entry.get('url')
                if not playlist_url:
                    playlist_id = entry.get('id')
                    if playlist_id:
                        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                if not playlist_url:
                    continue

                thumbnails = entry.get('thumbnails')
                if isinstance(thumbnails, list) and thumbnails:
                    thumbnail_url = thumbnails[-1].get('url')
                else:
                    thumbnail_url = entry.get('thumbnail')

                normalized_entry = {
                    '_type': 'playlist',
                    'id': entry.get('id'),
                    'title': entry.get('title', 'Playlist Tanpa Judul'),
                    'webpage_url': playlist_url,
                    'url': playlist_url,
                    'uploader': entry.get('uploader') or entry.get('channel') or '',
                    'thumbnail': thumbnail_url,
                    'thumbnails': thumbnails,
                    'playlist_count': entry.get('playlist_count') or entry.get('view_count'),
                    'description': entry.get('description'),
                }
                collected.append(normalized_entry)

            if len(collected) >= max_results:
                break

        return collected

class PlaylistFetchThread(QThread):
    results_ready = Signal(list, str, str)
    fetch_error = Signal(str)
    playlist_info_ready = Signal(dict)
    def __init__(self, playlist_url, cookie_params=None, parent=None):
        super().__init__(parent)
        self.playlist_url = playlist_url
        self.cookie_params = cookie_params or {}

    def run(self):
        ydl_opts = {'quiet': True, 'nocheckcertificate': True, 'extract_flat': True, 'skip_download': True, 'ignoreerrors': True}
        
        # Apply Cookies
        c_source = self.cookie_params.get('source', 'none')
        if c_source == 'browser':
            c_browser = self.cookie_params.get('browser', 'chrome')
            ydl_opts['cookiesfrombrowser'] = (c_browser, None, None)
        elif c_source == 'file':
            c_file = self.cookie_params.get('file', '')
            if c_file and os.path.exists(c_file):
                ydl_opts['cookiefile'] = c_file

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
            if "Could not copy" in error_msg and "cookie" in error_msg:
                self.fetch_error.emit("Gagal akses playlist: Browser terkunci. Harap tutup browser.")
                return
            elif "Failed to decrypt" in error_msg or "DPAPI" in error_msg:
                self.fetch_error.emit("Gagal dekripsi cookies browser. Gunakan metode File Cookies.")
                return

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
    
    def __init__(self, channel_url, cookie_params=None, parent=None):
        super().__init__(parent)
        self.channel_url = channel_url
        self.cookie_params = cookie_params or {}
        
    def run(self):
        ydl_opts = {
            'quiet': True, 'nocheckcertificate': True, 'extract_flat': False,
            'skip_download': True, 'ignoreerrors': True, 'playlistend': 100
        }
        
        # Apply Cookies
        c_source = self.cookie_params.get('source', 'none')
        if c_source == 'browser':
            c_browser = self.cookie_params.get('browser', 'chrome')
            ydl_opts['cookiesfrombrowser'] = (c_browser, None, None)
        elif c_source == 'file':
            c_file = self.cookie_params.get('file', '')
            if c_file and os.path.exists(c_file):
                ydl_opts['cookiefile'] = c_file

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
            if "Could not copy" in error_msg and "cookie" in error_msg:
                self.fetch_error.emit("Gagal akses channel: Browser terkunci. Harap tutup browser.")
                return
            elif "Failed to decrypt" in error_msg or "DPAPI" in error_msg:
                self.fetch_error.emit("Gagal dekripsi cookies browser. Gunakan metode File Cookies.")
                return

            msg = re.search(r'ERROR: (.*?)(?:;|$)', error_msg, re.DOTALL)
            msg = msg.group(1).strip() if msg else error_msg.split('\n')[0]
            self.fetch_error.emit(f"Gagal mengambil info channel: {msg}")
        except Exception as e:
            self.fetch_error.emit(f"Kesalahan tak terduga saat mengambil channel: {str(e)}")
