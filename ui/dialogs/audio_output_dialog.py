from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QLabel
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaDevices

class AudioOutputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Pilih Perangkat Output Audio"))
        self.setModal(True)
        self.setFixedSize(400, 300)

        self.selected_device = None

        layout = QVBoxLayout(self)

        self.label = QLabel(_("Perangkat Output Audio yang tersedia"))
        layout.addWidget(self.label)

        self.device_list_widget = QListWidget()
        layout.addWidget(self.device_list_widget)
        self.label.setBuddy(self.device_list_widget)

        self.select_button = QPushButton(_("Pilih"))
        self.select_button.clicked.connect(self.accept)
        layout.addWidget(self.select_button)

        self.cancel_button = QPushButton(_("Batal"))
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)

        self.populate_devices()

    def populate_devices(self):
        self.device_list_widget.clear()
        default_device = QMediaDevices.defaultAudioOutput()
        if default_device.description():
            self.device_list_widget.addItem(_("Perangkat Default"))
            self.device_list_widget.item(0).setData(Qt.UserRole, default_device) # Store the actual default device
        
        self.available_devices = QMediaDevices.audioOutputs()
        for device in self.available_devices:
            if device.description() != default_device.description(): # Avoid duplicating the default device if it's already listed
                item_text = device.description()
                item = self.device_list_widget.addItem(item_text)
                self.device_list_widget.item(self.device_list_widget.count() - 1).setData(Qt.UserRole, device) # Store the actual device

    def accept(self):
        selected_items = self.device_list_widget.selectedItems()
        if selected_items:
            self.selected_device = selected_items[0].data(Qt.UserRole)
        super().accept()

    def get_selected_device(self):
        if self.selected_device:
            # Check if the selected device is the system's default device
            if self.selected_device.id() == QMediaDevices.defaultAudioOutput().id():
                return "default"
            return self.selected_device.id()
        return None
