import google.generativeai as genai
import keyring

class GeminiClient:
    def __init__(self):
        self.api_key = keyring.get_password("mrd-youtube-downloader", "gemini_api_key")
        self._model = None
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel('gemini-2.5-flash')
            except Exception as exc:
                print(f"Gagal mengonfigurasi Gemini API: {exc}")
                self._model = None
        else:
            print("Gemini API Key not found in keyring. Please set it in the settings dialog.")

    def generate_response(self, prompt):
        if not self.api_key:
            return "Error: Gemini API Key not set. Please go to settings and set your API key."
        if self._model is None:
            try:
                self._model = genai.GenerativeModel('gemini-2.5-flash')
            except Exception as exc:
                return f"Error: Failed to initialise Gemini model ({exc})."
        try:
            response = self._model.generate_content(prompt)
        except Exception as exc:
            return f"Error: Gemini request failed ({exc})."
        return getattr(response, "text", "") or ""
