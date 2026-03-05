class SignalConnector:
    def __init__(self, main_window, search_handler, download_handler, player_handler, dialog_handler):
        self.main_window = main_window
        self.search_handler = search_handler
        self.download_handler = download_handler
        self.player_handler = player_handler
        self.dialog_handler = dialog_handler

    def connect_signals(self):
        # Main window signals
        self.main_window.main_view_widget.input_line_edit.returnPressed.connect(self.search_handler.process_input)
        self.main_window.main_view_widget.go_button.clicked.connect(self.search_handler.process_input)
        self.main_window.main_view_widget.settings_button.clicked.connect(self.dialog_handler.open_settings_dialog)
        self.main_window.main_view_widget.info_button.clicked.connect(self.dialog_handler.show_about_dialog)

        # Menu bar signals
        menu_bar = self.main_window.menuBar()
        menu_bar.open_download_folder_action.triggered.connect(self.main_window.open_current_download_folder)
        menu_bar.clear_input_action.triggered.connect(self.main_window.clear_input_field)
        menu_bar.settings_action.triggered.connect(self.dialog_handler.open_settings_dialog)
        menu_bar.exit_action.triggered.connect(self.main_window.close)
        menu_bar.paste_and_go_action.triggered.connect(self.main_window.paste_and_process_input)
        menu_bar.check_update_action.triggered.connect(lambda: self.main_window.initiate_update_check(manual_check=True))
        menu_bar.view_logs_action.triggered.connect(self.main_window.open_debug_log)
        menu_bar.debug_mode_action.triggered.connect(self.main_window.toggle_debug_mode)
        menu_bar.about_action.triggered.connect(self.dialog_handler.show_about_dialog)

        # Player signals
        self.main_window.media_player.errorChanged.connect(self.player_handler.handle_media_player_error)
        self.main_window.media_player.playbackStateChanged.connect(self.player_handler.handle_media_player_state_changed)
        self.main_window.media_player.mediaStatusChanged.connect(self.player_handler.handle_media_player_status_changed)

        # Shortcuts
        self.main_window.play_video_shortcut.activated.connect(self.player_handler.play_video_from_input_shortcut)
        self.main_window.play_audio_shortcut.activated.connect(self.player_handler.play_audio_from_input_shortcut)
