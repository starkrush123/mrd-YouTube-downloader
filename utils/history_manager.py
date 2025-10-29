import json
import os
from datetime import datetime
from .constants import APP_DATA_DIR

HISTORY_FILE = os.path.join(APP_DATA_DIR, 'history.json')
MAX_HISTORY_ENTRIES = 200
_HISTORY_CACHE = None

def _read_history_from_disk():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def _ensure_history_loaded():
    global _HISTORY_CACHE
    if _HISTORY_CACHE is None:
        _HISTORY_CACHE = _read_history_from_disk()
    return _HISTORY_CACHE

def load_history():
    return list(_ensure_history_loaded())

def save_history(history):
    global _HISTORY_CACHE
    trimmed_history = list(history)[:MAX_HISTORY_ENTRIES]
    _HISTORY_CACHE = trimmed_history
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(trimmed_history, f, indent=4)

def add_to_history(title, file_path):
    history = _ensure_history_loaded()
    new_entry = {
        'title': title,
        'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'file_path': file_path
    }
    history.insert(0, new_entry)
    if len(history) > MAX_HISTORY_ENTRIES:
        del history[MAX_HISTORY_ENTRIES:]
    save_history(history)
