from utils.gemini_client import GeminiClient
import json
import re
from PySide6.QtCore import QThread, Signal, QObject

class AIHandler:
    COMMANDS = {
        "search_youtube": {
            "description": "Mencari video, playlist, atau channel di YouTube.",
            "parameters": {
                "query": "Kata kunci pencarian (string)",
                "type": "Tipe pencarian (video, playlist, channel - string, opsional, default: video)"
            }
        },
        "download_media": {
            "description": "Mengunduh video atau audio dari URL YouTube.",
            "parameters": {
                "url": "URL video atau playlist YouTube (string)",
                "format": "Format unduhan (video, audio - string, opsional, default: video)"
            }
        },
        "play_media": {
            "description": "Memutar video atau audio dari URL YouTube.",
            "parameters": {
                "url": "URL video atau playlist YouTube (string)",
                "type": "Tipe pemutaran (video, audio - string, opsional, default: video)"
            }
        },
        "open_download_folder": {
            "description": "Membuka folder unduhan default.",
            "parameters": {}
        },
        "clear_input_field": {
            "description": "Mengosongkan kolom input utama.",
            "parameters": {}
        },
        "open_settings": {
            "description": "Membuka dialog pengaturan aplikasi.",
            "parameters": {}
        },
        "show_history": {
            "description": "Menampilkan riwayat unduhan.",
            "parameters": {}
        }
    }

    def __init__(self, main_window, gemini_client):
        self.main_window = main_window
        self.gemini_client = gemini_client
        self.ai_panel = main_window.ai_panel_widget
        self.conversation_history = []
        self._active_workers = []
        self.ai_panel.send_button.clicked.connect(self.handle_send_button_click)

    def handle_send_button_click(self):
        user_input = self.ai_panel.input_field.text()
        if not user_input:
            return

        self.ai_panel.output_display.append(f"> {user_input}")
        self.ai_panel.input_field.clear()
        self.conversation_history.append({"role": "user", "text": user_input})
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]
        self.ai_panel.send_button.setEnabled(False)

        worker = _AIWorker(
            gemini_client=self.gemini_client,
            commands=self.COMMANDS,
            conversation_history=list(self.conversation_history),
            user_input=user_input,
        )
        self._active_workers.append(worker)
        worker.signals.response_ready.connect(self._handle_ai_response)
        worker.signals.error.connect(self._handle_ai_error)
        worker.signals.command_detected.connect(self._execute_command)
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        worker.start()

    def _handle_ai_response(self, message):
        if message:
            self.conversation_history.append({"role": "assistant", "text": message})
            if len(self.conversation_history) > 50:
                self.conversation_history = self.conversation_history[-50:]
            self.ai_panel.output_display.append(f"AI: {message}")

    def _handle_ai_error(self, raw_response):
        if raw_response:
            self.ai_panel.output_display.append(f"AI: Maaf, ada masalah dalam memproses respons. Respons mentah: {raw_response}")
        self.ai_panel.send_button.setEnabled(True)

    def _execute_command(self, command, parameters):
        self.ai_panel.output_display.append(f"AI ▶ {command} {parameters}")
        if command == "search_youtube":
            query = parameters.get("query")
            search_type = parameters.get("type", "video")
            if query:
                self.main_window.main_view_widget.input_line_edit.setText(query)
                search_type_key = (search_type or "video").strip().lower()
                search_type_map = {"video": "Video", "playlist": "Playlist", "channel": "Channel"}
                target_text = search_type_map.get(search_type_key, "Video")
                if search_type_key not in search_type_map:
                    self.ai_panel.output_display.append("AI: Tipe pencarian tidak dikenali. Menggunakan tipe 'video'.")
                index = self.main_window.main_view_widget.search_type_combo.findText(target_text)
                if index >= 0:
                    self.main_window.main_view_widget.search_type_combo.setCurrentIndex(index)
                self.main_window.main_view_widget.go_button.click()
                self.ai_panel.output_display.append(f"AI: Mencari {search_type} untuk '{query}'...")
            else:
                self.ai_panel.output_display.append("AI: Perintah pencarian membutuhkan 'query'.")
        elif command == "download_media":
            url = parameters.get("url")
            media_format = parameters.get("format", "video")
            if url:
                desired_format = (media_format or "video").strip().lower()
                download_type = "audio" if desired_format.startswith("audio") else "video"
                title_hint = parameters.get("title") or "Media dari AI"
                self.main_window.main_view_widget.input_line_edit.setText(url)
                if self.main_window.is_valid_youtube_url(url):
                    self.main_window.download_handler.start_download(url, video_title_hint=title_hint, download_type=download_type)
                else:
                    self.main_window.main_view_widget.go_button.click()
                self.ai_panel.output_display.append(f"AI: Mengunduh media dari '{url}' sebagai {download_type}...")
            else:
                self.ai_panel.output_display.append("AI: Perintah unduh membutuhkan 'url'.")
        elif command == "play_media":
            url = parameters.get("url")
            play_type = parameters.get("type", "video")
            if url:
                play_type_key = (play_type or "video").strip().lower()
                play_video = not play_type_key.startswith("audio")
                title_hint = parameters.get("title") or "Media dari AI"
                self.main_window.main_view_widget.input_line_edit.setText(url)
                if self.main_window.is_valid_youtube_url(url):
                    self.main_window.player_handler.request_stream_info_and_play(url, title_hint, play_video)
                else:
                    self.main_window.main_view_widget.go_button.click()
                self.ai_panel.output_display.append(f"AI: Memutar media dari '{url}' sebagai {'video' if play_video else 'audio'}...")
            else:
                self.ai_panel.output_display.append("AI: Perintah putar membutuhkan 'url'.")
        elif command == "open_download_folder":
            self.main_window.open_current_download_folder()
            self.ai_panel.output_display.append("AI: Membuka folder unduhan...")
        elif command == "clear_input_field":
            self.main_window.clear_input_field()
            self.ai_panel.output_display.append("AI: Kolom input utama telah dikosongkan.")
        elif command == "open_settings":
            self.main_window.dialog_handler.show_settings_dialog()
            self.ai_panel.output_display.append("AI: Membuka dialog pengaturan...")
        elif command == "show_history":
            self.main_window.tab_widget.setCurrentWidget(self.main_window.history_tab)
            self.ai_panel.output_display.append("AI: Menampilkan riwayat unduhan...")
        else:
            self.ai_panel.output_display.append(f"AI: Perintah tidak dikenal: {command}")

    def _cleanup_worker(self, worker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        if not self._active_workers:
            self.ai_panel.send_button.setEnabled(True)


class _AIWorkerSignals(QObject):
    response_ready = Signal(str)
    command_detected = Signal(str, dict)
    error = Signal(str)


class _AIWorker(QThread):
    def __init__(self, gemini_client, commands, conversation_history, user_input, parent=None):
        super().__init__(parent)
        self.gemini_client = gemini_client
        self.commands = commands
        self.conversation_history = conversation_history
        self.user_input = user_input
        self.signals = _AIWorkerSignals()

    def run(self):
        raw_response = ""
        try:
            prompt = self._build_prompt()
            raw_response = self.gemini_client.generate_response(prompt)
            parsed = self._parse_ai_response(raw_response)
            reply = parsed.get("reply", "").strip()
            command = (parsed.get("command") or "none").strip()
            parameters = parsed.get("parameters") or {}

            if reply:
                self.signals.response_ready.emit(reply)
            if command and command.lower() != "none":
                if not isinstance(parameters, dict):
                    parameters = {}
                self.signals.command_detected.emit(command, parameters)
        except Exception as exc:
            fallback = raw_response or str(exc)
            self.signals.error.emit(fallback)

    def _build_prompt(self):
        commands_description = json.dumps(self.commands, indent=2, ensure_ascii=False)
        recent_history = self.conversation_history[-10:]
        history_lines = []
        for entry in recent_history:
            role = entry.get("role", "user")
            speaker = "Pengguna" if role == "user" else "AI"
            text = entry.get("text", "")
            history_lines.append(f"{speaker}: {text}")
        history_block = "\n".join(history_lines) if history_lines else "(Belum ada percakapan sebelumnya.)"

        prompt = (
            "Anda adalah asisten AI ramah yang membantu pengguna pada aplikasi mrd YouTube Downloader. "
            "Anda bisa bercakap-cakap secara alami dalam Bahasa Indonesia dan juga mengeksekusi perintah aplikasi.\n\n"
            f"Daftar perintah yang tersedia:\n{commands_description}\n\n"
            "Jika percakapan mengarah pada aksi aplikasi, pilih perintah yang tepat dan siapkan parameter yang dibutuhkan."
            " Jika tidak perlu aksi, kembalikan command 'none'.\n\n"
            "Riwayat percakapan singkat (gunakan sebagai konteks):\n"
            f"{history_block}\n\n"
            "Permintaan terbaru pengguna:\n"
            f"Pengguna: {self.user_input}\n\n"
            "Instruksi keluaran:\n"
            "- Balas dengan format JSON murni tanpa teks tambahan.\n"
            "- Struktur: {\"reply\": string, \"command\": string, \"parameters\": object}.\n"
            "- Field reply berisi jawaban ramah bagi pengguna.\n"
            "- Gunakan Bahasa Indonesia yang santai dan singkat.\n"
            "- command diisi dengan nama perintah atau 'none' jika hanya balas percakapan.\n"
            "- parameters merupakan objek berisi argumen (gunakan {} jika tidak ada).\n"
        )
        return prompt

    @staticmethod
    def _parse_ai_response(raw_response):
        if not raw_response:
            raise ValueError("Respons kosong dari model.")
        cleaned = raw_response.strip()
        code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if code_block_match:
            cleaned = code_block_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("Respons JSON tidak berbentuk objek.")
        if "reply" not in parsed:
            parsed["reply"] = ""
        if "command" not in parsed:
            parsed["command"] = "none"
        if "parameters" not in parsed or not isinstance(parsed["parameters"], dict):
            parsed["parameters"] = {}
        return parsed
