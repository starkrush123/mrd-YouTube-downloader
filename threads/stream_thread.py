import yt_dlp
import os
from PySide6.QtCore import QThread, Signal
from utils.helpers import get_js_runtime_options, classify_yt_dlp_error

class StreamInfoThread(QThread):
    stream_url_ready = Signal(str, str, bool)
    stream_error = Signal(str)
    PLAYBACK_PROFILE_LIMITS = {
        "hq": {"max_height": 2160, "max_abr": 256},
        "balanced": {"max_height": 720, "max_abr": 128},
        "stable": {"max_height": 480, "max_abr": 96},
        "data_saver": {"max_height": 360, "max_abr": 64},
    }
    
    def __init__(self, page_url, title_hint, play_video, cookie_params=None, playback_profile="balanced", parent=None):
        super().__init__(parent)
        self.page_url, self.title_hint, self.play_video = page_url, title_hint, play_video
        self.cookie_params = cookie_params or {}
        self.playback_profile = playback_profile if playback_profile in self.PLAYBACK_PROFILE_LIMITS else "balanced"

    def _get_profile_limits(self):
        return self.PLAYBACK_PROFILE_LIMITS.get(self.playback_profile, self.PLAYBACK_PROFILE_LIMITS["balanced"])

    def _build_format_selector(self):
        limits = self._get_profile_limits()
        if self.play_video:
            max_height = limits["max_height"]
            return (
                f"best[protocol^=http][ext=mp4][vcodec!=none][acodec!=none][height<=?{max_height}]/"
                f"best[protocol^=http][vcodec!=none][acodec!=none][height<=?{max_height}]/"
                f"best[vcodec!=none][acodec!=none][height<=?{max_height}]/"
                f"best[protocol^=http][height<=?{max_height}]/"
                f"best[height<=?{max_height}]/best"
            )
        max_abr = limits["max_abr"]
        return (
            f"bestaudio[protocol^=http][acodec^=mp4a][abr<=?{max_abr}]/"
            f"bestaudio[protocol^=http][abr<=?{max_abr}]/"
            f"bestaudio[abr<=?{max_abr}]/bestaudio/best"
        )

    def _select_best_format_url(self, info):
        formats = info.get("formats") or []
        if not formats:
            return info.get("url")

        limits = self._get_profile_limits()
        http_formats = [f for f in formats if f.get("url") and str(f.get("protocol", "")).startswith("http")]
        candidates = []

        if self.play_video:
            for fmt in http_formats:
                if fmt.get("vcodec") in (None, "none") or fmt.get("acodec") in (None, "none"):
                    continue
                candidates.append(fmt)
            max_height = limits["max_height"]
            limited = [f for f in candidates if (f.get("height") or 0) <= max_height]
            if limited:
                candidates = limited
            candidates.sort(
                key=lambda f: (
                    1 if self.playback_profile == "hq" and str(f.get("vcodec", "")).startswith(("av01", "vp9", "vp09")) else 0,
                    1 if f.get("ext") == "mp4" else 0,
                    int(f.get("height") or 0),
                    int(f.get("fps") or 0),
                    int(f.get("tbr") or f.get("abr") or 0),
                ),
                reverse=True,
            )
        else:
            for fmt in http_formats:
                if fmt.get("acodec") in (None, "none"):
                    continue
                if fmt.get("vcodec") not in (None, "none"):
                    continue
                candidates.append(fmt)
            max_abr = limits["max_abr"]
            limited = [f for f in candidates if (f.get("abr") or 0) <= max_abr]
            if limited:
                candidates = limited
            candidates.sort(
                key=lambda f: (
                    1 if self.playback_profile == "hq" and str(f.get("acodec", "")).startswith(("opus", "mp4a")) else 0,
                    1 if str(f.get("acodec", "")).startswith("mp4a") else 0,
                    1 if f.get("ext") in ("m4a", "mp4") else 0,
                    int(f.get("abr") or f.get("tbr") or 0),
                ),
                reverse=True,
            )

        if candidates:
            return candidates[0].get("url")
        return info.get("url")
        
    def run(self):
        try:
            ydl_opts = {
                'quiet': True, 
                'nocheckcertificate': True, 
                'format': self._build_format_selector(),
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
                stream_url = self._select_best_format_url(info)
                
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
