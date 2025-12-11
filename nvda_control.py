import ctypes
import importlib.util
import os
import sys
from ctypes import c_bool, c_wchar_p
from typing import Callable, Dict, List, Optional

if sys.platform != "win32":
    raise ImportError("nvda_control hanya tersedia di Windows.")

_nvda_module = None  # Optional python wrapper (nvdaController)
_controller_dll = None  # type: Optional[ctypes.WinDLL]
_controller_funcs: Dict[str, Optional[Callable]] = {}
_is_initialized = False


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

    env_dir = os.environ.get("NVDA_CONTROLLER_CLIENT_DIR")
    add(env_dir)

    cwd = os.getcwd()
    add(cwd)

    script_dir = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv else None
    module_dir = os.path.dirname(os.path.abspath(__file__))
    add(script_dir)
    add(module_dir)

    potential_bases = [script_dir, module_dir, os.path.dirname(module_dir)]
    extra_subdirs = [
        "nvda",
        os.path.join("resources", "nvda"),
        "resources",
        "lib",
        os.path.join("lib", "nvda"),
        "libs",
        os.path.join("libs", "nvda"),
        "bin",
        os.path.join("bin", "nvda"),
        "vendor",
        os.path.join("vendor", "nvda"),
        "contoh",
    ]

    for base in potential_bases:
        if not base:
            continue
        for sub in extra_subdirs:
            candidate = os.path.join(base, sub)
            add(candidate)

    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    add(program_files)
    add(program_files_x86)
    if program_files:
        add(os.path.join(program_files, "NVDA"))
    if program_files_x86:
        add(os.path.join(program_files_x86, "NVDA"))

    extra_env_dirs = os.environ.get("NVDA_CONTROLLER_ADDITIONAL_DIRS")
    if extra_env_dirs:
        for part in extra_env_dirs.split(os.pathsep):
            add(part.strip())

    return candidates


def _try_load_python_wrapper() -> bool:
    global _nvda_module
    try:
        import nvdaController as module  # type: ignore[import]

        _nvda_module = module
        return True
    except ImportError:
        pass

    for directory in _candidate_directories():
        candidate = os.path.join(directory, "nvdaController.py")
        if not os.path.isfile(candidate):
            continue
        try:
            spec = importlib.util.spec_from_file_location("nvdaController", candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules["nvdaController"] = module
                spec.loader.exec_module(module)  # type: ignore[attr-defined]
                _nvda_module = module
                return True
        except Exception:
            continue
    return False


def _load_backend() -> bool:
    """
    Try to import the nvdaController python package first. If that fails,
    fall back to loading the native nvdaControllerClient DLL via ctypes.
    """
    global _nvda_module, _controller_dll

    if _nvda_module or _controller_dll:
        return True

    if _try_load_python_wrapper():
        return True

    dll = _load_controller_dll()
    if dll is None:
        return False

    _controller_dll = dll
    _prepare_dll_functions()
    return True


def _load_controller_dll() -> Optional[ctypes.WinDLL]:
    arch_suffix = "64" if sys.maxsize > 2**32 else "32"
    candidate_names = [
        f"nvdaControllerClient{arch_suffix}.dll",
        "nvdaControllerClient.dll",
    ]

    candidates = []

    direct_path = os.environ.get("NVDA_CONTROLLER_CLIENT_DLL")
    if direct_path:
        candidates.append(direct_path)

    candidates.extend(candidate_names)

    for directory in _candidate_directories():
        for name in candidate_names:
            candidates.append(os.path.join(directory, name))

    seen = set()
    attempted_paths: List[str] = []
    last_error: Optional[OSError] = None
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            return ctypes.WinDLL(candidate)
        except OSError as exc:
            last_error = exc
            attempted_paths.append(f"{candidate} ({exc})")
            continue

    if last_error:
        details = "\n".join(attempted_paths)
        raise ImportError(f"Gagal memuat nvdaControllerClient DLL. Jalur yang dicoba:\n{details}") from last_error
    return None


def _prepare_dll_functions() -> None:
    if not _controller_dll:
        return

    def bind(name: str, restype=c_bool, argtypes=None) -> None:
        func = getattr(_controller_dll, name, None)
        if func:
            func.restype = restype
            if argtypes is not None:
                func.argtypes = argtypes
        _controller_funcs[name] = func

    bind("nvdaControllerClient_initialize")
    bind("nvdaControllerClient_terminate", restype=None)
    bind("nvdaControllerClient_isRunning")
    bind("nvdaControllerClient_speakText", argtypes=[c_wchar_p])
    bind("nvdaControllerClient_cancelSpeech")
    bind("nvdaControllerClient_brailleMessage", argtypes=[c_wchar_p])
    bind("nvdaControllerClient_pauseSpeech")
    bind("nvdaControllerClient_resumeSpeech")


try:
    if not _load_backend():
        raise ImportError("nvdaControllerClient tidak ditemukan.")
except OSError as exc:
    raise ImportError(f"Gagal memuat nvdaControllerClient: {exc}") from exc


def _ensure_initialized() -> bool:
    global _is_initialized
    if _is_initialized:
        return True

    if _nvda_module:
        init_func = getattr(_nvda_module, "initialize", None)
        if callable(init_func):
            try:
                result = init_func()
                if result is False:
                    return False
            except Exception:
                return False
        _is_initialized = True
        return True

    init_func = _controller_funcs.get("nvdaControllerClient_initialize")
    if init_func:
        try:
            if not init_func():
                return False
        except Exception:
            return False

    _is_initialized = True
    return True


def _is_nvda_running() -> bool:
    if _nvda_module:
        for attr in ("isRunning", "isInstRunning"):
            checker = getattr(_nvda_module, attr, None)
            if callable(checker):
                try:
                    result = checker()
                    if result is not None:
                        return bool(result)
                except Exception:
                    continue
        return False

    checker = _controller_funcs.get("nvdaControllerClient_isRunning")
    if checker:
        try:
            return bool(checker())
        except Exception:
            return False
    return False


def connect() -> int:
    if not _ensure_initialized():
        return -1
    return 0 if _is_nvda_running() else -1


def disconnect() -> None:
    global _is_initialized
    if not _is_initialized:
        return

    if _nvda_module:
        terminate = getattr(_nvda_module, "terminate", None)
        if callable(terminate):
            try:
                terminate()
            except Exception:
                pass
    else:
        terminate = _controller_funcs.get("nvdaControllerClient_terminate")
        if terminate:
            try:
                terminate()
            except Exception:
                pass

    _is_initialized = False


def speak(text: str, interrupt: bool = False, symbol_level: int = -1) -> int:
    del symbol_level  # Tidak digunakan oleh NVDA Controller Client

    if not isinstance(text, str):
        text = str(text)
    clean_text = text.strip()
    if not clean_text:
        return -1

    if not _ensure_initialized():
        return -1

    if interrupt:
        cancel_speech()

    if _nvda_module:
        speak_func = getattr(_nvda_module, "speakText", None)
        if callable(speak_func):
            try:
                result = speak_func(clean_text)
                return 0 if result is None or bool(result) else -1
            except Exception:
                return -1
        return -1

    speak_func = _controller_funcs.get("nvdaControllerClient_speakText")
    if not speak_func:
        return -1
    try:
        return 0 if speak_func(clean_text) else -1
    except Exception:
        return -1


def cancel_speech() -> int:
    if not _ensure_initialized():
        return -1

    if _nvda_module:
        cancel_func = getattr(_nvda_module, "cancelSpeech", None)
        if callable(cancel_func):
            try:
                result = cancel_func()
                return 0 if result is None or bool(result) else -1
            except Exception:
                return -1
        speak_func = getattr(_nvda_module, "speakText", None)
        if callable(speak_func):
            try:
                speak_func("")
                return 0
            except Exception:
                return -1
        return -1

    cancel_func = _controller_funcs.get("nvdaControllerClient_cancelSpeech")
    if cancel_func:
        try:
            return 0 if cancel_func() else -1
        except Exception:
            return -1

    speak_func = _controller_funcs.get("nvdaControllerClient_speakText")
    if speak_func:
        try:
            speak_func("")
            return 0
        except Exception:
            return -1
    return -1


def braille(text: str) -> int:
    if not isinstance(text, str):
        text = str(text)
    clean_text = text.strip()
    if not clean_text:
        return -1

    if not _ensure_initialized():
        return -1

    if _nvda_module:
        braille_func = getattr(_nvda_module, "brailleMessage", None)
        if callable(braille_func):
            try:
                result = braille_func(clean_text)
                return 0 if result is None or bool(result) else -1
            except Exception:
                return -1
        return -1

    braille_func = _controller_funcs.get("nvdaControllerClient_brailleMessage")
    if braille_func:
        try:
            return 0 if braille_func(clean_text) else -1
        except Exception:
            return -1
    return -1


def pause_speech(switch: bool) -> int:
    if not _ensure_initialized():
        return -1

    if _nvda_module:
        target_name = "pauseSpeech" if switch else "resumeSpeech"
        target = getattr(_nvda_module, target_name, None)
        if callable(target):
            try:
                result = target()
                return 0 if result is None or bool(result) else -1
            except Exception:
                return -1
        return -1

    func_name = "nvdaControllerClient_pauseSpeech" if switch else "nvdaControllerClient_resumeSpeech"
    func = _controller_funcs.get(func_name)
    if func:
        try:
            return 0 if func() else -1
        except Exception:
            return -1
    return -1


def is_active() -> bool:
    if not _ensure_initialized():
        return False
    return _is_nvda_running()
