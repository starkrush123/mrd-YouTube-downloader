import sys
import os
import datetime
import traceback
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
        self.setWindowTitle("Terjadi Kesalahan Fatal")
        self.setMinimumSize(600, 400)
        self.error_traceback = error_traceback
        layout = QVBoxLayout(self)
        label = QLabel("Aplikasi mengalami kesalahan yang tidak terduga.\nBerikut adalah detail traceback:")
        layout.addWidget(label)
        self.traceback_text_edit = QTextEdit()
        self.traceback_text_edit.setText(self.error_traceback)
        self.traceback_text_edit.setReadOnly(True)
        layout.addWidget(self.traceback_text_edit)
        button_box = QDialogButtonBox()
        copy_button = button_box.addButton("Salin Traceback", QDialogButtonBox.ButtonRole.ActionRole)
        ok_button = button_box.addButton(QDialogButtonBox.StandardButton.Ok)
        copy_button.clicked.connect(self.copy_traceback)
        ok_button.clicked.connect(self.accept)
        layout.addWidget(button_box)
        self.setModal(True)

    def copy_traceback(self):
        QApplication.clipboard().setText(self.error_traceback)
        QMessageBox.information(self, "Traceback Disalin", "Detail error traceback telah disalin ke clipboard.")

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
    
    # Build runtimes dict
    runtimes_dict = {
        'deno': {},
        'node': {},
        'bun': {},
        'quickjs': {}
    }
    
    if qjs_path:
        runtimes_dict['quickjs'] = {'path': qjs_path}
    
    return {
        'remote_components': ['ejs:github'],
        'js_runtimes': runtimes_dict
    }

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
    
    progress = QProgressDialog("Mengunduh QuickJS Runtime...", "Batal", 0, 100, parent)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setWindowTitle("Download Dependensi")
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
        QMessageBox.critical(parent, "Download Error", f"Gagal mendownload QuickJS:\n{e}")
        if os.path.exists(target_path): os.remove(target_path)
        return False

def ensure_qjs_installed(parent=None):
    """Pastikan QuickJS tersedia, minta user download jika tidak ada."""
    if is_qjs_installed():
        return True
    
    msg = (
        "QuickJS JavaScript Runtime tidak ditemukan.\n\n"
        "Runtime ini diperlukan agar download dari YouTube berjalan lancar (bypass JavaScript challenge).\n"
        "Apakah Anda ingin mendownloadnya secara otomatis sekarang (ukuran ~1MB)?"
    )
    
    reply = QMessageBox.question(
        parent, "QuickJS Diperlukan", msg,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    
    if reply == QMessageBox.StandardButton.Yes:
        if download_qjs(parent):
            QMessageBox.information(parent, "Berhasil", "QuickJS berhasil diinstal. Anda bisa mulai mendownload.")
            return True
    else:
        QMessageBox.warning(
            parent, "Peringatan", 
            "Aplikasi mungkin akan mengalami error saat mengunduh dari YouTube tanpa QuickJS."
        )
    
    return False
