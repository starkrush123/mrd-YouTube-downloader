import os
import threading
from collections import OrderedDict

APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), 'mrido1')
if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(APP_DATA_DIR, "downloader_settings.json")
LOG_FILE_PATH = os.path.join(APP_DATA_DIR, "app_debug.log")

CURRENT_APP_VERSION = "1.6.0"
VERSION_INFO_URL = "https://gist.githubusercontent.com/starkrush123/241a35eab14fa99ea45603191f6c0471/raw/mrd_downloader_version.json"

_GLOBAL_DEBUG_MODE = False
SEARCH_CACHE = OrderedDict()
THUMBNAIL_CACHE = OrderedDict()
CACHE_LOCK = threading.RLock()
CACHE_EXPIRY_SECONDS = 600
MAX_SEARCH_CACHE_ENTRIES = 30
MAX_THUMBNAIL_CACHE_ENTRIES = 64

AI_FEATURES_DEFAULT = {
    "search_youtube": True,
    "download_media": True,
    "play_media": True,
    "open_download_folder": True,
    "clear_input_field": True,
    "open_settings": True,
    "show_history": True,
    "search_and_play": True,
}

AI_FEATURES_LABELS = {
    "search_youtube": "Cari di YouTube",
    "download_media": "Unduh Media",
    "play_media": "Putar Media",
    "open_download_folder": "Buka Folder Unduhan",
    "clear_input_field": "Bersihkan Kolom Input",
    "open_settings": "Buka Pengaturan",
    "show_history": "Tampilkan Riwayat Unduhan",
    "search_and_play": "Cari & Putar Otomatis",
}

def is_debug_mode():
    global _GLOBAL_DEBUG_MODE
    return _GLOBAL_DEBUG_MODE

def set_debug_mode(value):
    global _GLOBAL_DEBUG_MODE
    _GLOBAL_DEBUG_MODE = value
