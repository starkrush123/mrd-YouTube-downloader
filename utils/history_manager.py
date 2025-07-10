
import json
import os
from datetime import datetime
from .constants import APP_DATA_DIR

HISTORY_FILE = os.path.join(APP_DATA_DIR, 'history.json')

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4)

def add_to_history(title, file_path):
    history = load_history()
    new_entry = {
        'title': title,
        'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'file_path': file_path
    }
    history.insert(0, new_entry)
    save_history(history)
