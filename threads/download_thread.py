import os
import sys
import re
from copy import deepcopy
import yt_dlp
from PySide6.QtCore import QThread, Signal

ANSI_ESCAPE_RE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

class DownloadThread(QThread):
    download_progress_signal = Signal(int, str, str)
    download_status_signal = Signal(str)
    download_title_signal = Signal(str)
    download_finished_signal = Signal(bool, str, str)
    single_item_finished_signal = Signal(bool, str, str, int, int)
    batch_overall_finished_signal = Signal(bool, str, str)
    def __init__(self, url_or_items, output_path, format_choice, embed_metadata, use_parallel_download, cookie_params=None, video_title_hint=None, is_batch=False, list_title_for_batch=None, parent=None):
        super().__init__(parent)
        self.url_or_items = url_or_items
        self.output_path = output_path
        self.format_choice = format_choice
        self.embed_metadata = embed_metadata
        self.use_parallel_download = use_parallel_download
        self.cookie_params = cookie_params or {}
        self.current_video_title = video_title_hint or "Video"
        self._is_stopping = False
        self.is_batch = is_batch
        self.list_title_for_batch = list_title_for_batch
        self.last_processed_filepath = None

    def stop(self):
        self._is_stopping = True

    @staticmethod
    def _sanitize_error_message(raw_message):
        if not raw_message:
            return ""
        cleaned = ANSI_ESCAPE_RE.sub("", raw_message)
        cleaned = cleaned.replace("[0;31m", "").replace("[0m", "").strip()
        return cleaned

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

    def _invoke_yt_dlp(self, options, item_url):
        worker_opts = deepcopy(options)
        with yt_dlp.YoutubeDL(worker_opts) as ydl:
            if self._is_stopping:
                raise InterruptedError("Dihentikan pengguna sebelum ydl.download()")
            ydl.download([item_url])
        if self._is_stopping:
            raise InterruptedError("Dihentikan pengguna setelah ydl.download()")

    def _perform_download_with_retry(self, base_opts, item_url):
        try:
            self._invoke_yt_dlp(base_opts, item_url)
            return
        except yt_dlp.utils.DownloadError as first_error:
            cleaned_first = self._sanitize_error_message(str(first_error))
            if "video unavailable" in cleaned_first.lower() and "youtube" in item_url.lower():
                fallback_opts = deepcopy(base_opts)
                fallback_opts.pop('downloader', None)
                fallback_opts.pop('downloader_args', None)
                fallback_args = fallback_opts.setdefault('extractor_args', {}).setdefault('youtube', {})
                fallback_clients = fallback_args.get('player_client')
                if isinstance(fallback_clients, list):
                    combined = list({client for client in fallback_clients})
                elif fallback_clients:
                    combined = [fallback_clients]
                else:
                    combined = []
                for client in ["android", "ios", "web", "mweb", "tv"]:
                    if client not in combined:
                        combined.append(client)
                fallback_args['player_client'] = combined
                fallback_opts['allow_unplayable_formats'] = True
                fallback_opts['ignore_no_formats_error'] = True
                self.download_status_signal.emit("Percobaan ulang dengan mode kompatibilitas YouTube...")
                try:
                    self._invoke_yt_dlp(fallback_opts, item_url)
                    return
                except yt_dlp.utils.DownloadError as second_error:
                    raise second_error from first_error
            raise first_error

    def download_single_item(self, item_url, item_title_hint, current_index=0, total_items=1):
        if self._is_stopping: raise InterruptedError("Dihentikan pengguna sebelum memulai item.")
        
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
                info_opts = {'quiet': True, 'nocheckcertificate': True, 'skip_download': True}
                info_opts.update(cookie_opts)
                with yt_dlp.YoutubeDL(info_opts) as ydl_info:
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
            ydl_opts.update(cookie_opts)
            
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
            
            self._perform_download_with_retry(ydl_opts, item_url)
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
        except yt_dlp.utils.DownloadError as e:
            cleaned_err = self._sanitize_error_message(str(e))
            if "Could not copy" in cleaned_err and "cookie" in cleaned_err:
                msg = "Gagal akses cookies: Browser sedang terbuka/terkunci. Harap tutup browser sepenuhnya."
            elif "Failed to decrypt" in cleaned_err or "DPAPI" in cleaned_err:
                msg = "Gagal dekripsi cookies browser. Coba tutup browser atau gunakan metode File Cookies (.txt)."
            else:
                first_line = cleaned_err.splitlines()[0] if cleaned_err.splitlines() else cleaned_err
                msg = f"Kesalahan unduhan yt-dlp: {first_line or 'Tidak diketahui'}"
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
