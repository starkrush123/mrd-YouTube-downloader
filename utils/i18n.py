"""
Internationalization (i18n) module for mrd YouTube Downloader.
Uses Python's built-in gettext with Babel-generated message catalogs.

Best practice approach:
- Source language: Indonesian (id) — msgid strings are in Indonesian
- Translations: .po/.mo files per language under locales/<lang>/LC_MESSAGES/
- At startup, .mo files are auto-compiled from .po if missing or stale
- Falls back to NullTranslations (pass-through) if no .mo found
"""
import gettext
import os
import sys
import json
from utils.constants import CONFIG_FILE

# Supported languages: code -> display name
SUPPORTED_LANGUAGES = {
    'id': 'Indonesia',
    'en': 'English',
}
DEFAULT_LANGUAGE = 'id'

_current_translator = None
_current_language = DEFAULT_LANGUAGE


def _get_locales_dir():
    """Return the path to the locales directory."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'locales')


def _get_config_file():
    """Return the path to the app config file."""
    return CONFIG_FILE


def get_saved_language():
    """Read the saved language preference from config file."""
    config_file = _get_config_file()
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                lang = data.get('language', DEFAULT_LANGUAGE)
                if lang in SUPPORTED_LANGUAGES:
                    return lang
    except Exception:
        pass
    return DEFAULT_LANGUAGE


def _compile_mo_if_needed(locales_dir, language):
    """
    Auto-compile .po -> .mo if the .mo file is missing or older than the .po.
    This is the best practice for development: no manual compile step needed.
    """
    lc_dir = os.path.join(locales_dir, language, 'LC_MESSAGES')
    po_path = os.path.join(lc_dir, 'messages.po')
    mo_path = os.path.join(lc_dir, 'messages.mo')

    if not os.path.exists(po_path):
        return  # Nothing to compile

    # Compile if .mo is missing or .po is newer
    needs_compile = (
        not os.path.exists(mo_path) or
        os.path.getmtime(po_path) > os.path.getmtime(mo_path)
    )

    if needs_compile:
        try:
            from babel.messages.pofile import read_po
            from babel.messages.mofile import write_mo
            with open(po_path, 'rb') as f:
                catalog = read_po(f, locale=language)
            with open(mo_path, 'wb') as f:
                write_mo(f, catalog)
        except Exception:
            pass  # Silently ignore compile errors; gettext will handle missing .mo


def setup_translation(language=None):
    """
    Initialize the translation system.
    Call this once at application startup before any UI is created.

    Best practices applied:
    - Auto-compiles .mo from .po if stale/missing (great for development)
    - Falls back gracefully to NullTranslations if no catalog found
    - Installs _() into builtins so all modules can use it without importing
    """
    global _current_translator, _current_language

    if language is None:
        language = get_saved_language()

    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    _current_language = language
    locales_dir = _get_locales_dir()

    # Auto-compile .po -> .mo if needed (dev convenience + ensures freshness)
    _compile_mo_if_needed(locales_dir, language)

    try:
        translator = gettext.translation(
            domain='messages',
            localedir=locales_dir,
            languages=[language],
        )
        translator.install()
        _current_translator = translator
    except FileNotFoundError:
        # Fallback: strings pass through unchanged (works fine for 'id' source lang)
        fallback = gettext.NullTranslations()
        fallback.install()
        _current_translator = fallback


def get_current_language():
    """Return the currently active language code."""
    return _current_language


def get_translator():
    """Return the active translator object."""
    return _current_translator
