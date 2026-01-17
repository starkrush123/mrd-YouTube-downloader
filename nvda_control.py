import ctypes
import os
import sys
from ctypes import c_bool, c_wchar_p
from typing import List, Optional

if sys.platform != "win32":
    raise ImportError("nvda_control (Tolk backend) hanya tersedia di Windows.")

_tolk_dll = None  # type: Optional[ctypes.CDLL]
_is_loaded = False


def _candidate_directories() -> List[str]:
    candidates: List[str] = []
    seen = set()

    def add(path: Optional[str]) -> None:
        if not path:
            return
        normalized = os.path.abspath(path)
        if normalized not in seen and os.path.isdir(normalized):
            candidates.append(normalized)
            seen.add(normalized)

    # 1. Environment Variable
    env_dir = os.environ.get("TOLK_DIR")
    add(env_dir)

    # 2. Current Working Directory
    cwd = os.getcwd()
    add(cwd)

    # 3. Script Directory & Module Directory
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv else None
    module_dir = os.path.dirname(os.path.abspath(__file__))
    add(script_dir)
    add(module_dir)

    # 4. Common subdirectories
    potential_bases = [script_dir, module_dir, os.path.dirname(module_dir)]
    extra_subdirs = [
        "lib",
        "libs",
        "bin",
        "Tolk",
        "tolk",
        os.path.join("lib", "tolk"),
        os.path.join("libs", "tolk"),
        os.path.join("bin", "tolk"),
        "vendor",
    ]

    for base in potential_bases:
        if not base:
            continue
        for sub in extra_subdirs:
            candidate = os.path.join(base, sub)
            add(candidate)

    # 5. Program Files (Optional, but less likely for Tolk)
    # Tolk usually bundled with app
    
    return candidates


def _load_tolk_dll() -> Optional[ctypes.CDLL]:
    # Tolk usually named Tolk.dll. 
    # Check for architecture specific names if convention exists, but standard build is Tolk.dll (x86/x64 separate builds)
    candidate_names = ["Tolk.dll"] 

    candidates = []
    for directory in _candidate_directories():
        for name in candidate_names:
            candidates.append(os.path.join(directory, name))

    seen = set()
    attempted_paths: List[str] = []
    
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        
        if not os.path.isfile(candidate):
            continue

        try:
            # Tolk is usually CDECL
            dll = ctypes.CDLL(candidate)
            return dll
        except OSError as exc:
            attempted_paths.append(f"{candidate} ({exc})")
            continue

    if attempted_paths:
        details = "\n".join(attempted_paths)
        print(f"Warning: Gagal memuat Tolk.dll. Jalur yang dicoba:\n{details}", file=sys.stderr)
    
    return None


def _init_tolk():
    global _tolk_dll, _is_loaded
    if _tolk_dll:
        return

    _tolk_dll = _load_tolk_dll()
    if not _tolk_dll:
        return

    # Bind Functions
    try:
        # Tolk_Load
        _tolk_dll.Tolk_Load.restype = None
        _tolk_dll.Tolk_Load.argtypes = []

        # Tolk_IsLoaded
        _tolk_dll.Tolk_IsLoaded.restype = c_bool
        _tolk_dll.Tolk_IsLoaded.argtypes = []

        # Tolk_DetectScreenReader
        _tolk_dll.Tolk_DetectScreenReader.restype = c_wchar_p
        _tolk_dll.Tolk_DetectScreenReader.argtypes = []

        # Tolk_Speak
        _tolk_dll.Tolk_Speak.restype = c_bool
        _tolk_dll.Tolk_Speak.argtypes = [c_wchar_p, c_bool]

        # Tolk_Braille
        _tolk_dll.Tolk_Braille.restype = c_bool
        _tolk_dll.Tolk_Braille.argtypes = [c_wchar_p]
        
        # Tolk_Unload
        _tolk_dll.Tolk_Unload.restype = None
        _tolk_dll.Tolk_Unload.argtypes = []

        # Tolk_TrySAPI (Optional)
        if hasattr(_tolk_dll, 'Tolk_TrySAPI'):
            _tolk_dll.Tolk_TrySAPI.restype = None
            _tolk_dll.Tolk_TrySAPI.argtypes = [c_bool]

    except AttributeError as e:
        print(f"Error binding Tolk functions: {e}", file=sys.stderr)
        _tolk_dll = None
        return

    # Initialize
    _tolk_dll.Tolk_Load()
    _is_loaded = _tolk_dll.Tolk_IsLoaded()


# --- Public API ---

def connect() -> int:
    """
    Initializes Tolk and checks for active screen reader.
    Returns 0 if successful/active, -1 otherwise.
    """
    _init_tolk()
    if not _is_loaded or not _tolk_dll:
        return -1
    
    sr_name = _tolk_dll.Tolk_DetectScreenReader()
    return 0 if sr_name else -1


def disconnect() -> None:
    global _is_loaded
    if _tolk_dll and _is_loaded:
        _tolk_dll.Tolk_Unload()
        _is_loaded = False


def speak(text: str, interrupt: bool = False, symbol_level: int = -1) -> int:
    del symbol_level  # Unused

    if not isinstance(text, str):
        text = str(text)
    clean_text = text.strip()
    
    if not clean_text:
        return -1

    if not _is_loaded or not _tolk_dll:
        # Try connect once if not loaded
        if connect() == -1:
            return -1

    try:
        success = _tolk_dll.Tolk_Speak(clean_text, interrupt)
        return 0 if success else -1
    except Exception:
        return -1


def cancel_speech() -> int:
    if not _is_loaded or not _tolk_dll:
        return -1
    
    # Tolk doesn't have a dedicated Stop/Cancel function in all versions, 
    # but speaking empty string with interrupt usually works.
    # Some builds might have Tolk_Silence()
    
    if hasattr(_tolk_dll, 'Tolk_Silence'):
        try:
             _tolk_dll.Tolk_Silence()
             return 0
        except:
             pass

    # Fallback
    return speak("", interrupt=True)


def braille(text: str) -> int:
    if not isinstance(text, str):
        text = str(text)
    clean_text = text.strip()
    
    if not clean_text:
        return -1

    if not _is_loaded or not _tolk_dll:
        if connect() == -1:
            return -1

    try:
        success = _tolk_dll.Tolk_Braille(clean_text)
        return 0 if success else -1
    except Exception:
        return -1


def pause_speech(switch: bool) -> int:
    # Tolk does not expose pause/resume widely across all SRs.
    # We will ignore this for now or just log.
    return -1


def is_active() -> bool:
    if not _is_loaded or not _tolk_dll:
        connect()
    
    if _is_loaded and _tolk_dll:
        return bool(_tolk_dll.Tolk_DetectScreenReader())
    return False

# Initialize on module load attempt
try:
    _init_tolk()
except:
    pass
