import requests
from PySide6.QtCore import QObject, Signal, QRunnable
from PySide6.QtGui import QIcon, QPixmap
from utils.constants import (
    THUMBNAIL_CACHE,
    MAX_THUMBNAIL_CACHE_ENTRIES,
    CACHE_LOCK,
)

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
        cached_icon = None
        with CACHE_LOCK:
            cached_icon = THUMBNAIL_CACHE.get(self.url)
            if cached_icon:
                THUMBNAIL_CACHE.move_to_end(self.url)
        if cached_icon:
            self.signals.finished.emit(self.url, cached_icon)
            return
        try:
            response = requests.get(self.url, stream=True, timeout=15)
            response.raise_for_status()
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            icon = QIcon(pixmap)
            with CACHE_LOCK:
                THUMBNAIL_CACHE[self.url] = icon
                THUMBNAIL_CACHE.move_to_end(self.url)
                while len(THUMBNAIL_CACHE) > MAX_THUMBNAIL_CACHE_ENTRIES:
                    THUMBNAIL_CACHE.popitem(last=False)
            self.signals.finished.emit(self.url, icon)
        except Exception:
            pass
