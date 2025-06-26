import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QStyle

from ui import MainWindow
from exceptions import global_exception_hook

# Kondisional import untuk NVDA, biar lebih aman
try:
    from nvda import connect, disconnect
    NVDA_AVAILABLE = sys.platform == 'win32'
except (ImportError, OSError):
    NVDA_AVAILABLE = False
    # Buat fungsi dummy kalo nvda gak ada
    def connect(): pass
    def disconnect(): pass


if __name__ == "__main__":
    sys.excepthook = global_exception_hook
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    ffmpeg_lib_dir = script_dir
    if sys.platform == "win32":
        os.environ['PATH'] = ffmpeg_lib_dir + os.pathsep + os.environ.get('PATH', '')
        qt_plugin_path = os.path.join(script_dir, 'qtplugins', 'mediaservice')
        if os.path.isdir(qt_plugin_path):
             os.environ['QT_PLUGIN_PATH'] = qt_plugin_path + os.pathsep + os.environ.get('QT_PLUGIN_PATH', '')
    elif sys.platform.startswith("linux"):
        os.environ['LD_LIBRARY_PATH'] = ffmpeg_lib_dir + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
        gst_plugin_path = os.path.join(script_dir, 'gst-plugins')
        if os.path.isdir(gst_plugin_path):
            os.environ['GST_PLUGIN_PATH'] = gst_plugin_path + os.pathsep + os.environ.get('GST_PLUGIN_PATH', '')

    if NVDA_AVAILABLE:
        connect()

    app = QApplication(sys.argv)
    icon_path = os.path.join(script_dir, "youtube_downloader_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        standard_icon = app.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        if not standard_icon.isNull():
            app.setWindowIcon(standard_icon)

    main_win = MainWindow()
    main_win.show()

    exit_code = app.exec()

    if NVDA_AVAILABLE:
        disconnect()

    sys.exit(exit_code)