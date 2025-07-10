import requests
from PySide6.QtCore import QObject, Signal, QRunnable
from PySide6.QtGui import QIcon, QPixmap
from utils.constants import THUMBNAIL_CACHE

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
