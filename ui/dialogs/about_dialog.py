import sys
import yt_dlp
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox
)
from PySide6.QtCore import Qt, qVersion
from utils.constants import CURRENT_APP_VERSION

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tentang mrd YouTube Downloader")
        self.setMinimumSize(450, 320)
        layout = QVBoxLayout(self)
        self.info_text_browser = QTextBrowser(self)
        self.info_text_browser.setReadOnly(True); self.info_text_browser.setOpenExternalLinks(True)
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        yt_dlp_version = "N/A"
        try: yt_dlp_version = yt_dlp.version.__version__
        except AttributeError: pass
        info_content = f"""<html><head><style> a {{ color: #007bff; text-decoration: none; }} a:hover {{ text-decoration: underline; }} </style></head><body> <h2>mrd YouTube Downloader</h2><p>Versi Aplikasi: {CURRENT_APP_VERSION}</p> <p>Aplikasi untuk mengunduh video dan audio dari YouTube dengan mudah.</p> <p><strong>Pembuat:</strong> ridho</p><p><strong>UI Framework:</strong> PySide6</p> <p><strong>Versi Qt:</strong> {qVersion()}</p><p><strong>Versi Python:</strong> {python_version}</p> <p><strong>Versi yt-dlp:</strong> {yt_dlp_version}</p><hr> <p>Dibangun menggunakan pustaka yt-dlp untuk fungsionalitas unduhan inti.</p> <p>© 2024-2025 mrido1</p></body></html>"""
        self.info_text_browser.setHtml(info_content)
        self.info_text_browser.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        layout.addWidget(self.info_text_browser)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept); layout.addWidget(button_box)
        self.info_text_browser.setFocus()
