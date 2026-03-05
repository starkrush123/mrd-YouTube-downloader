import os
import json
import requests
from PySide6.QtCore import QThread, Signal
import re


def _parse_version(version_text):
    """Parse semantic-ish version string into tuple for safe comparison."""
    if not version_text:
        return (0,)
    parts = re.findall(r'\d+', str(version_text))
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)

class UpdateCheckThread(QThread):
    update_available = Signal(dict)
    no_update_found = Signal(str)
    update_check_error = Signal(str)

    def __init__(self, current_version, version_url, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.version_url = version_url

    def run(self):
        if not self.version_url or self.version_url == "URL_GIST_JSON_LO_DISINI":
            self.update_check_error.emit("URL info versi belum diatur dengan benar di kode sumber.")
            return
        try:
            headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
            response = requests.get(self.version_url, timeout=10, headers=headers)
            response.raise_for_status()
            version_info = response.json()
            latest_version = version_info.get("latest_version")
            download_url_sfx = version_info.get("download_url_sfx")
            if not latest_version or not download_url_sfx:
                self.update_check_error.emit("Format info versi tidak valid dari URL.")
                return
            latest_v = _parse_version(latest_version)
            current_v = _parse_version(self.current_version)
            if latest_v > current_v:
                self.update_available.emit(version_info)
            elif current_v > latest_v:
                self.no_update_found.emit(f"Versi Anda ({self.current_version}) lebih baru dari versi yang tersedia di server ({latest_version}).")
            else:
                self.no_update_found.emit(f"Versi Anda ({self.current_version}) adalah yang terbaru.")
        except requests.exceptions.RequestException as e:
            self.update_check_error.emit(f"Gagal mengambil info versi: {e}.")
        except json.JSONDecodeError:
            self.update_check_error.emit("Gagal memproses info versi (format JSON salah).")
        except Exception as e:
            self.update_check_error.emit(f"Terjadi kesalahan tak terduga saat cek update: {str(e)}.")

class DownloadUpdateThread(QThread):
    download_progress = Signal(int)
    download_finished = Signal(str)
    download_error = Signal(str)

    def __init__(self, download_url, save_path, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.save_path = save_path
        self._is_running = True

    def run(self):
        try:
            response = requests.get(self.download_url, stream=True, timeout=60)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not self._is_running:
                        if os.path.exists(self.save_path):
                            try: os.remove(self.save_path)
                            except OSError: pass
                        self.download_error.emit("Download dibatalkan oleh pengguna.")
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            self.download_progress.emit(progress)
            if not self._is_running:
                return
            if downloaded_size == 0 and total_size != 0 :
                 if os.path.exists(self.save_path):
                     try: os.remove(self.save_path)
                     except OSError: pass
                 self.download_error.emit(f"Gagal download: File kosong diterima dari server.")
                 return
            self.download_progress.emit(100)
            self.download_finished.emit(self.save_path)
        except requests.exceptions.RequestException as e:
            if os.path.exists(self.save_path):
                try: os.remove(self.save_path)
                except OSError: pass
            self.download_error.emit(f"Gagal download update: {e}.")
        except Exception as e:
            if os.path.exists(self.save_path):
                try: os.remove(self.save_path)
                except OSError: pass
            self.download_error.emit(f"Terjadi kesalahan saat download: {str(e)}.")

    def stop(self):
        self._is_running = False
