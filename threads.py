import os
import re
import json
import time
import shutil
import yt_dlp
import requests
import traceback
from PySide6.QtCore import QThread, Signal, QObject, QRunnable
from PySide6.QtGui import QIcon, QPixmap
from config import dprint, SEARCH_CACHE, THUMBNAIL_CACHE, CACHE_EXPIRY_SECONDS

class ThumbnailSignals(QObject):
    finished = Signal(str, QIcon)

class ThumbnailDownloader(QRunnable):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = ThumbnailSignals()

    def run(self):
        if not self.url:
            return
        if self.url in THUMBNAIL_CACHE:
            self.signals.finished.emit(self.url, THUMBNAIL_CACHE[self.url])
            return
        try:
            response = requests.get(self.url, stream=True, timeout=15)
            response.raise_for_status()
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            icon = QIcon(pixmap)
            THUMBNAIL_CACHE[self.url] = icon
            self.signals.finished.emit(self.url, icon)
        except Exception:
            pass

class UpdateCheckThread(QThread):
    update_available = Signal(dict)
    no_update_found = Signal(str)
    update_check_error = Signal(str)

    def __init__(self, current_version, version_url, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.version_url = version_url

    def run(self):
        if not self.version_url or self.version_url == "URL_GIST_JSON_LO_DISINI":
            self.update_check_error.emit("URL info versi belum diatur dengan benar di kode sumber.")
            return
        try:
            headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
            response = requests.get(self.version_url, timeout=10, headers=headers)
            response.raise_for_status()
            version_info = response.json()
            latest_version = version_info.get("latest_version")
            download_url_sfx = version_info.get("download_url_sfx")
            if not latest_version or not download_url_sfx:
                self.update_check_error.emit("Format info versi tidak valid dari URL.")
                return
            if latest_version > self.current_version:
                self.update_available.emit(version_info)
            else:
                self.no_update_found.emit(f"Versi Anda ({self.current_version}) adalah yang terbaru.")
        except requests.exceptions.RequestException as e:
            self.update_check_error.emit(f"Gagal mengambil info versi: {e}.")
        except json.JSONDecodeError:
            self.update_check_error.emit("Gagal memproses info versi (format JSON salah).")
        except Exception as e:
            self.update_check_error.emit(f"Terjadi kesalahan tak terduga saat cek update: {str(e)}.")

class DownloadUpdateThread(QThread):
    download_progress = Signal(int)
    download_finished = Signal(str)
    download_error = Signal(str)

    def __init__(self, download_url, save_path, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.save_path = save_path
        self._is_running = True

    def run(self):
        try:
            response = requests.get(self.download_url, stream=True, timeout=60)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not self._is_running:
                        if os.path.exists(self.save_path):
                            try: os.remove(self.save_path)
                            except OSError: pass
                        self.download_error.emit("Download dibatalkan oleh pengguna.")
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            self.download_progress.emit(progress)
            if not self._is_running:
                return
            if downloaded_size == 0 and total_size != 0 :
                 if os.path.exists(self.save_path):
                     try: os.remove(self.save_path)
                     except OSError: pass
                 self.download_error.emit(f"Gagal download: File kosong diterima dari server.")
                 return
            self.download_progress.emit(100)
            self.download_finished.emit(self.save_path)
        except requests.exceptions.RequestException as e:
            if os.path.exists(self.save_path):
                try: os.remove(self.save_path)
                except OSError: pass
            self.download_error.emit(f"Gagal download update: {e}.")
        except Exception as e:
            if os.path.exists(self.save_path):
                try: os.remove(self.save_path)
                except OSError: pass
            self.download_error.emit(f"Terjadi kesalahan saat download: {str(e)}.")

    def stop(self):
        self._is_running = False

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

class DownloadThread(QThread):
    download_progress_signal = Signal(int, str, str)
    download_status_signal = Signal(str)
    download_title_signal = Signal(str)
    download_finished_signal = Signal(bool, str, str)
    single_item_finished_signal = Signal(bool, str, str, int, int)
    batch_overall_finished_signal = Signal(bool, str, str)
    def __init__(self, url_or_items, output_path, format_choice, embed_metadata, use_parallel_download, video_title_hint=None, is_batch=False, list_title_for_batch=None, parent=None):
        super().__init__(parent)
        self.url_or_items = url_or_items
        self.output_path = output_path
        self.format_choice = format_choice
        self.embed_metadata = embed_metadata
        self.use_parallel_download = use_parallel_download
        self.current_video_title = video_title_hint or "Video"
        self._is_stopping = False
        self.is_batch = is_batch
        self.list_title_for_batch = list_title_for_batch
        self.last_processed_filepath = None

    def stop(self):
        self._is_stopping = True

    def _progress_hook(self, d):
        if self._is_stopping:
            raise InterruptedError("Download dihentikan oleh pengguna.")
        if d['status'] == 'downloading':
            total = d.get('total_bytes', d.get('total_bytes_estimate'))
            downloaded = d.get('downloaded_bytes')
            if total and downloaded:
                self.download_progress_signal.emit(int(downloaded / total * 100), d.get('_speed_str', 'N/A'), d.get('_eta_str', 'N/A'))

    def _postprocessor_hook(self, d):
        if self._is_stopping:
            raise InterruptedError("Proses dihentikan oleh pengguna saat post-processing.")
        
        pp_name = d.get('postprocessor', 'N/A')
        status_msg = d.get('status', 'unknown')
        if status_msg == 'finished' and 'info_dict' in d and 'filepath' in d['info_dict']:
            self.last_processed_filepath = d['info_dict']['filepath']
        target_format_name = "data"
        try:
            content_in_paren = self.format_choice[self.format_choice.find('(')+1 : self.format_choice.rfind(')')]
            target_format_name = content_in_paren.split(' - ')[0].strip() if ' - ' in content_in_paren else content_in_paren.strip()
        except Exception: pass
        if status_msg == 'started': self.download_status_signal.emit(f"Memulai konversi ke {target_format_name} ({pp_name})...")
        elif status_msg == 'processing': self.download_status_signal.emit(f"Sedang mengonversi ke {target_format_name} ({pp_name})...")
        elif status_msg == 'finished': self.download_status_signal.emit(f"Konversi ke {target_format_name} ({pp_name}) selesai.")
        elif status_msg == 'error': self.download_status_signal.emit(f"Kesalahan saat konversi ({pp_name}).")

    def download_single_item(self, item_url, item_title_hint, current_index=0, total_items=1):
        if self._is_stopping: raise InterruptedError("Dihentikan pengguna sebelum memulai item.")
        actual_output_path = self.output_path
        if self.is_batch and self.list_title_for_batch:
            list_folder_name = yt_dlp.utils.sanitize_filename(self.list_title_for_batch, restricted=True)
            actual_output_path = os.path.join(self.output_path, list_folder_name)
            if not os.path.exists(actual_output_path):
                try: os.makedirs(actual_output_path, exist_ok=True)
                except OSError as e: self.download_status_signal.emit(f"Warning: Gagal buat folder '{list_folder_name}', Error: {e}"); actual_output_path = self.output_path
        self.last_processed_filepath = None
        try:
            current_title = item_title_hint
            if not current_title or current_title in ["Video", "URL dari Input", "Audio dari Input", "Video dari URL"]:
                with yt_dlp.YoutubeDL({'quiet': True, 'nocheckcertificate': True, 'skip_download': True}) as ydl_info:
                    if self._is_stopping: raise InterruptedError("Dihentikan pengguna sebelum fetch info judul")
                    info = ydl_info.extract_info(item_url, download=False)
                    current_title = info.get('title', 'Video Tanpa Judul')
            self.current_video_title = current_title
            display_title = f"{current_title} ({current_index+1}/{total_items})" if self.is_batch else current_title
            self.download_title_signal.emit(display_title)
            self.download_status_signal.emit(f"Mulai unduh: {current_title}")
            ydl_opts = {
                'progress_hooks': [self._progress_hook],
                'postprocessor_hooks': [self._postprocessor_hook],
                'nocheckcertificate': True, 'ignoreerrors': False,
                'quiet': True, 'no_warnings': True,
                'restrictfilenames': True,
                'retries': 10,
                'fragment_retries': 10,
                'http_chunk_size': 5_242_880,
                'outtmpl': os.path.join(actual_output_path, '%(title)s.%(ext)s')
            }
            
            if self.use_parallel_download:
                ydl_opts['downloader'] = 'aria2c'
                ydl_opts['downloader_args'] = '-c -x 4 -s 4 -k 1M'
            ffmpeg_path = next((p for p in [os.path.join(os.path.dirname(sys.argv[0]), fn) for fn in ["ffmpeg.exe" if sys.platform == "win32" else "ffmpeg", os.path.join("ffmpeg", "bin", "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"), os.path.join("ffmpeg", "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")]] if os.path.isfile(p)), None)
            if ffmpeg_path: ydl_opts['ffmpeg_location'] = ffmpeg_path
            expected_ext = None
            is_audio_download = any(f in self.format_choice for f in ["MP3", "WAV", "AAC", "OGG Vorbis", "FLAC"])
            if not is_audio_download:
                if "MP4" in self.format_choice:
                    expected_ext = "mp4"
                    ydl_opts['format'] = 'bestvideo[ext=mp4][height<=?1080]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best'
                    ydl_opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
                elif "MKV" in self.format_choice:
                    expected_ext = "mkv"
                    ydl_opts['format'] = 'bestvideo+bestaudio/best'
                    ydl_opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mkv'}]
                elif "WEBM" in self.format_choice:
                    expected_ext = "webm"
                    ydl_opts['format'] = 'bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/bestvideo+bestaudio/best'
                    ydl_opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'webm'}]
                elif "AVI" in self.format_choice:
                    expected_ext = "avi"
                    ydl_opts['format'] = 'bestvideo+bestaudio/best'
                    ydl_opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'avi'}]
            else: 
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio'}]
                
                if self.embed_metadata:
                    ydl_opts['embedthumbnail'] = True
                    ydl_opts['postprocessors'].append({'key': 'FFmpegMetadata', 'add_metadata': True})
                codec_map = {"MP3": "mp3", "WAV": "wav", "AAC": "aac", "OGG Vorbis": "ogg", "FLAC": "flac"}
                for key, codec_val in codec_map.items():
                    if key in self.format_choice:
                        ydl_opts['postprocessors'][0]['preferredcodec'] = codec_val
                        if key == "MP3": ydl_opts['postprocessors'][0]['preferredquality'] = "0"
                        expected_ext = codec_val
                        break
            base_name_template = os.path.join(actual_output_path, yt_dlp.utils.sanitize_filename(current_title, restricted=True))
            final_expected_filename_by_logic = f"{base_name_template}.{expected_ext}" if expected_ext else f"{base_name_template}.tmp"
            if os.path.exists(final_expected_filename_by_logic):
                status_msg = f"File sudah ada: {os.path.basename(final_expected_filename_by_logic)}. Lewati."
                if self.is_batch: self.single_item_finished_signal.emit(True, status_msg, final_expected_filename_by_logic, current_index, total_items)
                else: self.download_finished_signal.emit(True, status_msg, final_expected_filename_by_logic)
                return True, status_msg, final_expected_filename_by_logic
            self.download_status_signal.emit(f"Mengunduh sebagai (target): {os.path.basename(final_expected_filename_by_logic)}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if self._is_stopping: raise InterruptedError("Dihentikan pengguna sebelum ydl.download()")
                ydl.download([item_url])
            if self._is_stopping: raise InterruptedError("Dihentikan pengguna setelah ydl.download()")
            file_to_check = self.last_processed_filepath if self.last_processed_filepath else final_expected_filename_by_logic
            if os.path.exists(file_to_check):
                success_msg = f"Selesai: {os.path.basename(file_to_check)}"
                if self.is_batch: self.single_item_finished_signal.emit(True, success_msg, file_to_check, current_index, total_items)
                else: self.download_finished_signal.emit(True, success_msg, file_to_check)
                return True, success_msg, file_to_check
            else:
                if os.path.exists(actual_output_path):
                    for entry in os.listdir(actual_output_path):
                        if entry.startswith(os.path.basename(base_name_template)):
                            alt_file_path = os.path.join(actual_output_path, entry)
                            alt_msg = f"Selesai (file alternatif ditemukan): {entry}. Diharapkan: {os.path.basename(file_to_check)}"
                            if self.is_batch: self.single_item_finished_signal.emit(True, alt_msg, alt_file_path, current_index, total_items)
                            else: self.download_finished_signal.emit(True, alt_msg, alt_file_path)
                            return True, alt_msg, alt_file_path
                fail_msg = f"Gagal menemukan file unduhan setelah proses: {current_title}. Diharapkan: {os.path.basename(file_to_check)}"
                if self.is_batch: self.single_item_finished_signal.emit(False, fail_msg, "", current_index, total_items)
                else: self.download_finished_signal.emit(False, fail_msg, "")
                return False, fail_msg, ""
        except InterruptedError as e: msg = f"Unduhan dihentikan: {str(e)}"
        except yt_dlp.utils.DownloadError as e: msg = f"Kesalahan unduhan yt-dlp: {str(e).splitlines()[0] if str(e).splitlines() else str(e)}"
        except Exception as e: msg = f"Kesalahan tak terduga saat unduh: {str(e)}"
        
        if self.is_batch: self.single_item_finished_signal.emit(False, msg, "", current_index, total_items)
        else: self.download_finished_signal.emit(False, msg, "")
        return False, msg, ""

    def run(self):
        try:
            if self.is_batch:
                items, total = self.url_or_items, len(self.url_or_items)
                success_overall, summaries = True, []
                for i, item_data in enumerate(items):
                    if self._is_stopping:
                        summaries.append(f"Item {i+1}/{total}: Dihentikan oleh pengguna.")
                        success_overall = False; break
                        
                    url, title = item_data.get('url'), item_data.get('title', f"Item {i+1}")
                    if not url:
                        summaries.append(f"Item {i+1}/{total} ('{title}'): URL tidak valid, dilewati.")
                        self.single_item_finished_signal.emit(False, f"URL tidak valid untuk '{title}'", "", i, total)
                        success_overall = False; continue
                        
                    self.download_progress_signal.emit(0, "N/A", "N/A")
                    self.download_status_signal.emit(f"Memulai item {i+1}/{total}: {title}")
                    
                    item_success, msg, filepath = self.download_single_item(url, title, i, total)
                    summaries.append(f"Item {i+1}/{total} ('{title}'): {msg}")
                    if not item_success: success_overall = False
                    
                    if self._is_stopping:
                        summaries.append(f"Batch dihentikan oleh pengguna setelah item '{title}'.")
                        break
                        
                final_summary_message = "\n".join(summaries)
                if self._is_stopping and not any("dihentikan oleh pengguna" in m.lower() for m in summaries):
                    final_summary_message += "\n\nBatch dihentikan oleh pengguna."
                elif not self._is_stopping:
                    final_summary_message = f"Proses batch selesai.\n" + final_summary_message
                self.batch_overall_finished_signal.emit(success_overall, final_summary_message, self.output_path)
            else:
                self.download_single_item(self.url_or_items, self.current_video_title)
        except InterruptedError as e:
            msg = f"Operasi dihentikan oleh pengguna: {e}"
            if self.is_batch:
                self.batch_overall_finished_signal.emit(False, msg, self.output_path)
            else:
                self.download_finished_signal.emit(False, msg, "")
        except Exception as e:
            if self.is_batch:
                self.batch_overall_finished_signal.emit(False, f"Kesalahan fatal dalam thread batch: {e}", self.output_path)
            else:
                self.download_finished_signal.emit(False, f"Kesalahan fatal dalam thread unduhan: {e}", "")


