from ytmusicapi import YTMusic
import os

class YTMusicManager:
    def __init__(self, config_path='browser.json', auth_mode='unauthenticated'):
        self.config_path = config_path
        self.auth_mode = auth_mode
        self.ytmusic = None
        self.authenticated = False

        if self.auth_mode == 'unauthenticated':
            self.ytmusic = YTMusic()
            self.authenticated = True # In unauthenticated mode, we consider it "authenticated" for search purposes
        elif self.auth_mode == 'authenticated':
            self.authenticated = self._check_authenticated_file()
            if self.authenticated:
                self.ytmusic = YTMusic(self.config_path)

    def _check_authenticated_file(self):
        return os.path.exists(self.config_path)

    def is_authenticated(self):
        return self.authenticated

    def setup_authentication(self):
        if self.auth_mode == 'unauthenticated':
            return "Authentication is not required in unauthenticated mode."

        if not self._check_authenticated_file():
            try:
                YTMusic.setup(filepath=self.config_path)
                self.ytmusic = YTMusic(self.config_path)
                self.authenticated = True
                return "Authentication successful."
            except Exception as e:
                self.authenticated = False
                return f"Authentication failed: {e}"
        else:
            self.ytmusic = YTMusic(self.config_path)
            self.authenticated = True
            return "Already authenticated."

    def set_auth_mode(self, mode):
        if mode not in ['unauthenticated', 'authenticated']:
            raise ValueError("Invalid auth mode. Must be 'unauthenticated' or 'authenticated'.")
        self.auth_mode = mode
        if self.auth_mode == 'unauthenticated':
            self.ytmusic = YTMusic()
            self.authenticated = True
        elif self.auth_mode == 'authenticated':
            self.authenticated = self._check_authenticated_file()
            if self.authenticated:
                self.ytmusic = YTMusic(self.config_path)
            else:
                self.ytmusic = None # Clear ytmusic if not authenticated"

    def search(self, query, filter=None, limit=20):
        if not self.authenticated:
            return []
        try:
            search_results = self.ytmusic.search(query, filter=filter, limit=limit)
            return search_results
        except Exception as e:
            print(f"An error occurred during search: {e}")
            return []

