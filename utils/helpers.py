import sys
import os
import datetime
import traceback
import shutil
import importlib.util
import requests
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel, QTextEdit, 
    QDialogButtonBox, QMessageBox, QProgressDialog
)
from PySide6.QtCore import Qt
from utils.constants import is_debug_mode, LOG_FILE_PATH

def dprint(message):
    if is_debug_mode():
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_message = f"[{timestamp}] [DEBUG] {message}"
        
        # Always write to file if debug mode is on
        try:
            with open(LOG_FILE_PATH, 'a', encoding='utf-8') as f:
                f.write(log_message + "\n")
        except Exception:
            pass
            
        # Also print to console
        print(log_message, flush=True)

class ErrorDialog(QDialog):
    def __init__(self, error_traceback, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Terjadi Kesalahan Fatal"))
        self.setMinimumSize(600, 400)
        self.error_traceback = error_traceback
        layout = QVBoxLayout(self)
        label = QLabel(_("Aplikasi mengalami kesalahan yang tidak terduga.\nBerikut adalah detail traceback:"))
        layout.addWidget(label)
        self.traceback_text_edit = QTextEdit()
        self.traceback_text_edit.setText(self.error_traceback)
        self.traceback_text_edit.setReadOnly(True)
        layout.addWidget(self.traceback_text_edit)
        button_box = QDialogButtonBox()
        copy_button = button_box.addButton(_("Salin Traceback"), QDialogButtonBox.ButtonRole.ActionRole)
        ok_button = button_box.addButton(QDialogButtonBox.StandardButton.Ok)
        copy_button.clicked.connect(self.copy_traceback)
        ok_button.clicked.connect(self.accept)
        layout.addWidget(button_box)
        self.setModal(True)

    def copy_traceback(self):
        QApplication.clipboard().setText(self.error_traceback)
        QMessageBox.information(self, _("Traceback Disalin"), _("Detail error traceback telah disalin ke clipboard."))

def global_exception_hook(exctype, value, tb):
    traceback_details = "".join(traceback.format_exception(exctype, value, tb))
    error_message = f"Tipe Error: {exctype.__name__}\nPesan: {value}\n\nTraceback:\n{traceback_details}"
    dprint(f"GLOBAL EXCEPTION: {error_message}")
    app = QApplication.instance()
    if not app:
        sys.exit(1)
        return
    dialog = ErrorDialog(error_message)
    dialog.exec()

def get_js_runtime_options():
    """
    Mendeteksi runtime JavaScript (QuickJS, Deno, Node) dan mengembalikan opsi yt-dlp.
    Mendukung mode portable dengan mencari qjs.exe di folder aplikasi.
    """
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    base_dir = os.path.dirname(app_dir) if getattr(sys, 'frozen', False) else app_dir
    
    # Prioritas QuickJS (Portable)
    qjs_candidates = [
        os.path.join(app_dir, "qjs.exe"),
        os.path.join(app_dir, "bin", "qjs.exe"),
        os.path.join(base_dir, "qjs.exe"),
    ]
    
    qjs_path = next((p for p in qjs_candidates if os.path.isfile(p)), None)
    
    # Build runtimes dict (hanya runtime yang benar-benar tersedia).
    runtimes_dict = {}
    if shutil.which("node"):
        runtimes_dict['node'] = {}
    if shutil.which("deno"):
        runtimes_dict['deno'] = {}
    if shutil.which("bun"):
        runtimes_dict['bun'] = {}
    if qjs_path:
        runtimes_dict['quickjs'] = {'path': qjs_path}

    opts = {}
    if runtimes_dict:
        opts['js_runtimes'] = runtimes_dict

    # Jika paket lokal yt-dlp-ejs belum ada, fallback ke remote components dari GitHub.
    if importlib.util.find_spec("yt_dlp_ejs") is None:
        opts['remote_components'] = ['ejs:github']
    return opts

def classify_yt_dlp_error(error_text):
    """Kembalikan pesan yang lebih actionable untuk error yt-dlp umum."""
    if not error_text:
        return None

    msg = str(error_text)
    low = msg.lower()

    if "failed to resolve" in low or "getaddrinfo failed" in low:
        return (
            "DNS gagal resolve youtube.com. Cek koneksi internet/DNS, "
            "lalu coba lagi (mis. ganti DNS ke 1.1.1.1 atau 8.8.8.8)."
        )

    if (
        "challenge solving failed" in low
        or "signature solving failed" in low
        or "n challenge solving failed" in low
        or "[jsc]" in low
    ):
        return (
            "Gagal menyelesaikan JavaScript challenge YouTube. "
            "Pastikan yt-dlp terbaru, yt-dlp-ejs terpasang, dan runtime Node.js tersedia."
        )

    if "403 forbidden" in low and "youtube" in low:
        return (
            "YouTube menolak akses format (403). Biasanya terkait challenge/signature atau cookies. "
            "Coba update yt-dlp, aktifkan cookies browser/file, lalu ulangi."
        )

    return None

def get_qjs_executable_path():
    """Mengembalikan path di mana qjs.exe seharusnya berada."""
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    # Jika di-freeze Nuitka/PyInstaller, gunakan folder tempat .exe berada
    base_dir = app_dir if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
    return os.path.join(base_dir, "qjs.exe")

def is_qjs_installed():
    """Cek apakah qjs.exe ada di folder aplikasi."""
    return os.path.isfile(get_qjs_executable_path())

def download_qjs(parent=None):
    """Mendownload qjs.exe dari GitHub dengan progress bar."""
    qjs_url = "https://github.com/quickjs-ng/quickjs/releases/download/v0.9.0/qjs-windows-x86_64.exe"
    target_path = get_qjs_executable_path()
    
    progress = QProgressDialog(_("Mengunduh QuickJS Runtime..."), _("Batal"), 0, 100, parent)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setWindowTitle(_("Download Dependensi"))
    progress.show()

    try:
        response = requests.get(qjs_url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if progress.wasCanceled():
                    f.close()
                    if os.path.exists(target_path): os.remove(target_path)
                    return False
                
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        progress.setValue(percent)
        
        progress.setValue(100)
        return True
    except Exception as e:
        dprint(f"Gagal mendownload QuickJS: {e}")
        _msg = _("Gagal mendownload QuickJS:")
        QMessageBox.critical(parent, _("Download Error"), f"{_msg}\n{e}")
        if os.path.exists(target_path): os.remove(target_path)
        return False

def ensure_qjs_installed(parent=None):
    """Pastikan QuickJS tersedia, minta user download jika tidak ada."""
    if is_qjs_installed():
        return True
    
    msg = (
        _("QuickJS JavaScript Runtime tidak ditemukan.") + "\n\n"
        + _("Runtime ini diperlukan agar download dari YouTube berjalan lancar (bypass JavaScript challenge).") + "\n"
        + _("Apakah Anda ingin mendownloadnya secara otomatis sekarang (ukuran ~1MB)?")
    )
    
    reply = QMessageBox.question(
        parent, _("QuickJS Diperlukan"), msg,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    
    if reply == QMessageBox.StandardButton.Yes:
        if download_qjs(parent):
            QMessageBox.information(parent, _("Berhasil"), _("QuickJS berhasil diinstal. Anda bisa mulai mendownload."))
            return True
    else:
        QMessageBox.warning(
            parent, _("Peringatan"), 
            _("Aplikasi mungkin akan mengalami error saat mengunduh dari YouTube tanpa QuickJS.")
        )
    
    return False
