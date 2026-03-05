import sys
import yt_dlp
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QFrame
from PySide6.QtCore import Qt, qVersion
from utils.constants import CURRENT_APP_VERSION

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Tentang mrd YouTube Downloader"))
        self.setModal(True)

        layout = QVBoxLayout(self)

        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        yt_dlp_version = "N/A"
        try:
            yt_dlp_version = yt_dlp.version.__version__
        except AttributeError:
            pass

        # Judul Aplikasi
        title_label = QLabel(_("<b>mrd YouTube Downloader</b>"))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(title_label)

        # Informasi Aplikasi
        app_version_label = QLabel(f"{_('Versi Aplikasi')}: {CURRENT_APP_VERSION}")
        app_version_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(app_version_label)

        description_label = QLabel(_("Aplikasi untuk mengunduh video dan audio dari YouTube dengan mudah."))
        description_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(description_label)

        creator_label = QLabel(_("Dibuat oleh: ridho"))
        creator_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(creator_label)

        gui_framework_label = QLabel(_("GUI Framework: PySide6"))
        gui_framework_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(gui_framework_label)

        qt_version_label = QLabel(f"{_('Versi Qt')}: {qVersion()}")
        qt_version_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(qt_version_label)

        python_version_label = QLabel(f"{_('Versi Python')}: {python_version}")
        python_version_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(python_version_label)

        yt_dlp_version_label = QLabel(f"{_('Versi yt-dlp')}: {yt_dlp_version}")
        yt_dlp_version_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(yt_dlp_version_label)

        # Garis Pemisah
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setFocusPolicy(Qt.FocusPolicy.NoFocus) # Garis tidak perlu fokus
        layout.addWidget(line)

        # Informasi Tambahan
        built_with_label = QLabel(_("Dibangun menggunakan pustaka yt-dlp untuk fungsionalitas unduhan inti."))
        built_with_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(built_with_label)

        copyright_label = QLabel("© 2024-2026 mrido1")
        copyright_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(copyright_label)

        # Spacer untuk mendorong tombol ke bawah
        layout.addStretch(1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept)

        layout.addWidget(self.button_box)
        self.setLayout(layout)
        title_label.setFocus() # Menambahkan ini untuk fokus awal
        self.resize(450, 320)
