from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent

class OperationProgressDialog(QDialog):
    def __init__(self, operation_text, parent=None):
        super().__init__(parent); self.setWindowTitle(operation_text); self.setMinimumWidth(350)
        layout = QVBoxLayout(self); self.status_label = QLabel(f"{operation_text}..."); self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label); self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0, 0); self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar); self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.Dialog); self.setModal(True)

class DownloadProgressDialog(QDialog):
    cancel_requested = Signal()
    
    def __init__(self, title, parent=None):
        super().__init__(parent); 
        self.setWindowTitle(f"Mengunduh: {title[:40]}...")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout(self)
        self.title_label = QLabel(f"Mengunduh: <b>{title}</b>")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - Memulai...")
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Status: Memulai unduhan...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        self.speed_eta_label = QLabel("Kecepatan: N/A, ETA: N/A")
        layout.addWidget(self.speed_eta_label)
        
        self.cancel_button = QPushButton("Batal")
        self.cancel_button.setToolTip("Batalkan unduhan (Esc)")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self.cancel_button)
        
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.Dialog)
        self.setModal(True)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_requested.emit()
        else:
            super().keyPressEvent(event)

    def update_title(self, title): 
        self.setWindowTitle(f"Mengunduh: {title[:40]}...")
        self.title_label.setText(f"Mengunduh: <b>{title}</b>")
        
    def update_progress(self, percentage, speed, eta): 
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{percentage}%")
        self.speed_eta_label.setText(f"Kecepatan: {speed}, ETA: {eta}")
        
    def update_status(self, message):
        self.status_label.setText(f"Status: {message}")
        if "Mengonversi" in message: 
            self.progress_bar.setRange(0,0)
            self.progress_bar.setFormat("Mengonversi...")
            self.speed_eta_label.setText("")
        elif self.progress_bar.minimum() == 0 and self.progress_bar.maximum() == 0 : 
            self.progress_bar.setRange(0,100)
            
    def download_complete(self, success, message):
        self.progress_bar.setRange(0,100)
        self.progress_bar.setValue(100 if success else self.progress_bar.value())
        self.progress_bar.setFormat("Selesai!" if success else "Gagal!")
        self.status_label.setText(f"Status: {message}")
        self.speed_eta_label.setText("")
        self.cancel_button.setEnabled(False)
