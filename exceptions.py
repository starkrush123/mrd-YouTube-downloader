import sys
import traceback
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox, QMessageBox
from config import dprint

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


