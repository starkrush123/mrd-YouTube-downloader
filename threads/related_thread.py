import re
from urllib.parse import urlparse, parse_qs

import yt_dlp
from PySide6.QtCore import QThread, Signal

from utils.helpers import get_js_runtime_options, classify_yt_dlp_error


class RelatedTracksThread(QThread):
    related_ready = Signal(list)
    related_error = Signal(str)

    def __init__(self, page_url, cookie_params=None, limit=50, parent=None):
        super().__init__(parent)
        self.page_url = page_url
        self.cookie_params = cookie_params or {}
        self.limit = max(1, int(limit))

    def _extract_video_id(self, url):
        if not url:
            return None
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if "youtu.be" in host:
            return parsed.path.strip("/").split("/")[0] or None
        qs = parse_qs(parsed.query or "")
        if "v" in qs and qs["v"]:
            return qs["v"][0]
        m = re.search(r"/shorts/([A-Za-z0-9_-]{6,})", url)
        if m:
            return m.group(1)
        return None

    def run(self):
        video_id = self._extract_video_id(self.page_url)
        if not video_id:
            self.related_ready.emit([])
            return

        radio_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "lazy_playlist": True,
            "playlist_items": f"2-{self.limit + 1}",
            "nocheckcertificate": True,
            "ignoreerrors": True,
        }

        c_source = self.cookie_params.get("source", "none")
        if c_source == "browser":
            c_browser = self.cookie_params.get("browser", "chrome")
            ydl_opts["cookiesfrombrowser"] = (c_browser, None, None)
        elif c_source == "file":
            c_file = self.cookie_params.get("file", "")
            if c_file:
                ydl_opts["cookiefile"] = c_file

        ydl_opts.update(get_js_runtime_options())

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(radio_url, download=False)

            entries = info.get("entries") if isinstance(info, dict) else []
            if not isinstance(entries, list):
                self.related_ready.emit([])
                return

            out = []
            for entry in entries:
                if not entry:
                    continue
                item_url = entry.get("webpage_url") or entry.get("url")
                item_id = entry.get("id")
                if not item_url and item_id:
                    item_url = f"https://www.youtube.com/watch?v={item_id}"
                if not item_url:
                    continue
                out.append(
                    {
                        "_type": "video",
                        "id": item_id,
                        "title": entry.get("title", _("Video Tanpa Judul")),
                        "url": item_url,
                        "webpage_url": item_url,
                        "uploader": entry.get("uploader") or entry.get("channel"),
                        "thumbnail": entry.get("thumbnail"),
                        "thumbnails": entry.get("thumbnails"),
                        "duration": entry.get("duration"),
                    }
                )
                if len(out) >= self.limit:
                    break
            self.related_ready.emit(out)
        except yt_dlp.utils.DownloadError as e:
            classified = classify_yt_dlp_error(str(e))
            self.related_error.emit(classified or str(e))
        except Exception as e:
            self.related_error.emit(str(e))
