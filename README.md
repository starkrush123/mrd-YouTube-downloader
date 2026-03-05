# mrd YouTube Downloader

mrd YouTube Downloader is a desktop app (PySide6 + yt-dlp) for searching, playing, and downloading YouTube content.
It supports single videos, playlists, channels, AI-assisted commands, smart autoplay, and update checks.

## Important Notes

- The AI Panel is still experimental.
- This project is actively developed; behavior may change between versions.
- The app is currently designed primarily for Windows.

## Feature Overview

### 1. Search and Discovery

- Search YouTube by `Video`, `Playlist`, or `Channel` directly from the app.
- In-memory search cache with expiry for faster repeated queries.
- Playlist search view with "open playlist contents" action.
- Channel fetch mode loads up to the latest 100 videos.
- Thumbnail loading for result items.

### 2. Downloading

- Download single item as video or audio.
- Batch download all items from playlist/channel results.
- Download format presets:
  - Video: MP4, MKV, WEBM, AVI
  - Audio: MP3, WAV, AAC, OGG Vorbis, FLAC
- Optional metadata + thumbnail embedding for audio downloads.
- Optional aria2c accelerated downloads.
- Cookie-based authenticated access:
  - None
  - Import from browser
  - Netscape cookie file (`.txt`)
- yt-dlp fallback/retry flow for common YouTube extraction failures.

### 3. Playback

- Play as video (fullscreen player) or audio (dedicated audio player).
- Playback rate control, persistent across sessions.
- Persistent volume (`Up/Down` by 5% per press).
- Audio output device selector (manual device binding).
- Direct play from:
  - Search results
  - Input URL
  - AI commands

### 4. Autoplay and Smart Autoplay

- Standard autoplay to next item in queue/list.
- Smart autoplay (YouTube related tracks) for normal video search/direct playback context.
- Playlist/channel contexts keep list-based next-item autoplay.
- Smart autoplay limit is configurable (5-150 items).
- Smart autoplay is disabled automatically when main autoplay is disabled.
- Network-drop playback resilience:
  - Stream stall detection
  - Automatic reconnect/resume attempts
  - Automatic failover to next queue item if recovery is exhausted

### 5. AI Panel (Experimental)

- Chat-style AI assistant with command execution.
- Supported commands in code:
  - `search_youtube`
  - `download_media`
  - `play_media`
  - `open_download_folder`
  - `clear_input_field`
  - `open_settings`
  - `show_history`
  - `search_and_play`
- Per-feature AI permissions can be toggled in Settings.
- Gemini API key is stored using `keyring`.

### 6. History, Logs, and Utilities

- Download history tab with:
  - Open file
  - Open containing folder
- Clipboard monitoring for YouTube URLs.
- One-click "Paste & Process".
- Debug mode + debug log viewer.
- Automatic update check + in-app updater download.

### 7. Localization and UI

- Built-in localization support (`id`, `en`).
- Theme options: Light and Dark.
- Language switch is available from Settings (restart recommended after change).

## Keyboard Shortcuts

### Global/Main Window

- `Ctrl+P`: Play video from input URL
- `Ctrl+Shift+P`: Play audio from input URL
- `Ctrl+L`: Clear input
- `Ctrl+,`: Open Settings
- `Ctrl+Shift+V`: Paste and Process
- `Ctrl+Q`: Exit app

### Search Results Dialog

- `Ctrl+D`: Download selected item as audio
- `Ctrl+Shift+D`: Download selected item as video
- `Enter` / `Ctrl+Enter`: Play action (depends on "invert playback shortcuts" setting)
- `Double click`: Configurable action (download/play audio/play video)

### Player (Audio/Video)

- `Space`: Play/Pause
- `Left/Right`: Seek -/+ 5 seconds
- `Up/Down`: Volume +5%/-5%
- `Ctrl+Up/Ctrl+Down`: Playback speed +0.25/-0.25
- `Ctrl+D`: Download current media as audio
- `Ctrl+Shift+D`: Download current media as video
- `U`: Open audio output device dialog
- `Esc`: Close player view

## Settings Reference

### General

- Output directory
- Language
- Theme
- Audio output device
- Clipboard monitor
- Download completion notifications

### Download

- Default video format
- Default audio format
- Embed metadata/thumbnail (audio)
- aria2c acceleration toggle
- Search result count
- Double-click default action

### Playback

- Invert Enter/Ctrl+Enter play mapping
- Autoplay next item
- Smart autoplay related tracks
- Smart autoplay max related count

### Account & AI

- YouTube cookies source (none/browser/file)
- Browser selection for cookies
- Cookie file path
- Gemini API key
- AI feature toggles

## Installation

## 1) Quick Start (Recommended)

Download the latest release from:

- https://github.com/starkrush123/mrd-YouTube-downloader/releases

Use the installer package if available.

## 2) Run from Source

### Requirements

- Python 3.10+
- Windows (primary tested environment)

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python main.py
```

## External Runtime Tools (Recommended/Optional)

| Tool | Required | Why |
|---|---:|---|
| `ffmpeg` | Recommended | Better merge/conversion reliability and format support |
| `node.js` | Recommended | Improves yt-dlp EJS challenge solving reliability |
| `qjs.exe` (QuickJS) | Recommended | Lightweight JS runtime fallback for yt-dlp challenge solving |
| `aria2c` | Optional | Parallel download acceleration |

Notes:

- The app can auto-prompt QuickJS setup (`qjs.exe`) if missing.
- `yt-dlp` and `yt-dlp-ejs` behavior depends on current YouTube challenge state.

## Data and Config Paths

On Windows, app data is stored under:

- `%APPDATA%\\mrido1`

Important files:

- `downloader_settings.json`
- `app_debug.log`

## Update System

The app supports update checks and updater downloads using metadata from:

- `utils/constants.py` -> `VERSION_INFO_URL`

Current app version is defined in:

- `utils/constants.py` -> `CURRENT_APP_VERSION`

## Project Structure (High-Level)

- `ui/` : windows, dialogs, widgets, handlers, events
- `threads/` : async worker threads (search, download, stream, related, update)
- `utils/` : helpers, constants, styles, i18n, history manager
- `locales/` : translation catalogs (`.po`/`.mo`)
- `main.py` : app entry point

## Troubleshooting

### 1) YouTube JS challenge / signature errors

Symptoms:

- Signature solving failed
- Challenge solving failed
- Missing formats

Actions:

- Update `yt-dlp`
- Ensure Node.js is installed
- Ensure `qjs.exe` is available
- Try cookie auth (browser/file)

### 2) DNS/network failures

Symptoms:

- Failed to resolve `youtube.com`
- Intermittent extraction failures

Actions:

- Check internet connection
- Try a different DNS resolver (for example 1.1.1.1 or 8.8.8.8)

### 3) FFmpeg demux/partial file errors during streaming

Symptoms:

- `qt.multimedia.ffmpeg.demuxer: Demuxing failed`
- stream stalls/freeze

Current behavior:

- App attempts automatic stream recovery and resume.
- If recovery fails repeatedly, app fails over to next autoplay item (when enabled).

### 4) Cookies from browser fail

Symptoms:

- Could not copy/decrypt cookies

Actions:

- Close the target browser completely
- Try file-based Netscape cookies mode

### 5) aria2c option does nothing

Make sure `aria2c` is installed and discoverable in `PATH`.

## Development Notes

### Compile translation catalogs

```bash
python compile_mo.py
```

### Main dependencies

See:

- `requirements.txt`

