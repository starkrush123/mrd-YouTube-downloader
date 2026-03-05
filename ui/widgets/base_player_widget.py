from PySide6.QtWidgets import QWidget, QDialog
from PySide6.QtCore import Signal, Qt
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from ui.dialogs.audio_output_dialog import AudioOutputDialog

class BasePlayerWidget(QWidget):
    close_requested = Signal()
    download_requested = Signal(str)
    playback_rate_change_requested = Signal(float)
    SEEK_INTERVAL = 5000
    VOLUME_STEP_PERCENT = 5

    def __init__(self, media_player, parent=None, settings=None, main_window=None):
        super().__init__(parent)
        self.media_player = media_player
        self.settings = settings if settings else {}
        self.main_window = main_window

        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self._load_audio_output_device()
        self._load_playback_volume()

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _load_audio_output_device(self):
        saved_device_id = self.settings.get("audio_output_device_id")
        if saved_device_id:
            if saved_device_id == "default":
                self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
            else:
                found_device = None
                for device in QMediaDevices.audioOutputs():
                    if device.id() == saved_device_id:
                        found_device = device
                        break
                if found_device:
                    self.audio_output.setDevice(found_device)
                else:
                    self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
        else:
            self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())

    def toggle_play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def _load_playback_volume(self):
        saved_percent = self.settings.get("playback_volume_percent", 100)
        try:
            volume_percent = max(0, min(100, int(saved_percent)))
        except (TypeError, ValueError):
            volume_percent = 100
        self.audio_output.setVolume(volume_percent / 100.0)

    def _change_volume_by_percent(self, delta_percent):
        current_percent = int(round(self.audio_output.volume() * 100))
        new_percent = max(0, min(100, current_percent + int(delta_percent)))
        if new_percent == current_percent:
            return
        self.audio_output.setVolume(new_percent / 100.0)
        self.settings["playback_volume_percent"] = new_percent
        if self.main_window:
            self.main_window.save_app_settings(show_error=False)
            self.main_window.set_status_text(
                _("Volume pemutar: {percent}%").format(percent=new_percent)
            )

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close_requested.emit()
        elif key == Qt.Key.Key_Space:
            self.toggle_play_pause()
        elif key == Qt.Key.Key_Left:
            self.media_player.setPosition(max(0, self.media_player.position() - self.SEEK_INTERVAL))
        elif key == Qt.Key.Key_Right:
            self.media_player.setPosition(self.media_player.position() + self.SEEK_INTERVAL)
        elif key == Qt.Key.Key_Up and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._change_volume_by_percent(self.VOLUME_STEP_PERCENT)
        elif key == Qt.Key.Key_Down and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._change_volume_by_percent(-self.VOLUME_STEP_PERCENT)
        elif event.key() == Qt.Key.Key_Up and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.playback_rate_change_requested.emit(0.25)
        elif event.key() == Qt.Key.Key_Down and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.playback_rate_change_requested.emit(-0.25)
        elif event.key() == Qt.Key.Key_D and event.modifiers() == Qt.KeyboardModifier.ControlModifier and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.download_requested.emit('audio')
        elif event.key() == Qt.Key.Key_D and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            self.download_requested.emit('video')
        elif key == Qt.Key.Key_U:
            self.show_audio_output_dialog()
        else:
            super().keyPressEvent(event)

    def show_audio_output_dialog(self):
        dialog = AudioOutputDialog(self)
        if dialog.exec() == QDialog.Accepted:
            selected_device_id = dialog.get_selected_device()
            if selected_device_id:
                if selected_device_id == "default":
                    self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
                    print("Perangkat output audio diubah ke: Perangkat Default")
                else:
                    found_device = None
                    for device in QMediaDevices.audioOutputs():
                        if device.id() == selected_device_id:
                            found_device = device
                            break
                    if found_device:
                        self.audio_output.setDevice(found_device)
                        print(f"Perangkat output audio diubah ke: {found_device.description()}")
                    else:
                        print(f"Perangkat dengan ID {selected_device_id} tidak ditemukan. Menggunakan perangkat default.")
                        self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
                
                self.settings["audio_output_device_id"] = selected_device_id
                if self.main_window:
                    self.main_window.save_app_settings()
            else:
                print("Tidak ada perangkat yang dipilih.")
