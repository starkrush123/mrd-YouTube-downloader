import sys
import os

# Initialize translations BEFORE any UI imports so _() is available globally
from utils.i18n import setup_translation
setup_translation()

from PySide6.QtWidgets import QApplication, QStyle
from PySide6.QtGui import QIcon
from utils.helpers import global_exception_hook
from ui.main_window import MainWindow

try:
    from nvda_control import connect as nvda_connect, disconnect as nvda_disconnect
    NVDA_CONTROL_AVAILABLE = True
except (ImportError, OSError):
    NVDA_CONTROL_AVAILABLE = False
    def nvda_connect(): pass
    def nvda_disconnect(): pass

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
    
    app = QApplication(sys.argv)
    
    if NVDA_CONTROL_AVAILABLE:
        nvda_connect()

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
    
    if NVDA_CONTROL_AVAILABLE:
        nvda_disconnect()
        
    sys.exit(exit_code)
