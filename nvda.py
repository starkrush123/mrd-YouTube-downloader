import sys
import os

if sys.platform != 'win32':
    raise ImportError("Modul nvda_control hanya bisa digunakan di Windows.")

try:
    import win32pipe
    import win32file
    import pywintypes
except ImportError:
    raise ImportError("Modul pywin32 tidak ditemukan. Silakan install dengan 'pip install pywin32'.")

PIPE_NAME = r"\\.\pipe\NVDAControlPipe"
_pipe_handle = None

def connect():
    global _pipe_handle
    if _pipe_handle is not None:
        return 0
    try:
        _pipe_handle = win32file.CreateFile(
            PIPE_NAME,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None
        )
        return 0
    except pywintypes.error as e:
        if e.winerror == 2:
            pass
        else:
            pass
        _pipe_handle = None
        return -1

def disconnect():
    global _pipe_handle
    if _pipe_handle is not None:
        try:
            win32file.CloseHandle(_pipe_handle)
        except pywintypes.error:
            pass
        _pipe_handle = None

def _send_command(command_str):
    if _pipe_handle is None:
        if connect() != 0:
            return -1
    
    try:
        command_bytes = (command_str + "\n").encode('utf-8')
        win32file.WriteFile(_pipe_handle, command_bytes)
        return 0
    except pywintypes.error:
        disconnect()
        return -1

def speak(text, interrupt=False, symbol_level=-1):
    if not isinstance(text, str) or not text.strip():
        return -1
    
    if interrupt:
        cancel_speech()

    clean_text = text.replace('"', '""').replace('\n', ' ')
    command = f'speak "{clean_text}" 0 {symbol_level}'
    return _send_command(command)

def cancel_speech():
    return _send_command("cancelSpeech")

def braille(text):
    if not isinstance(text, str) or not text.strip():
        return -1
    clean_text = text.replace('"', '""').replace('\n', ' ')
    command = f'braille "{clean_text}"'
    return _send_command(command)

def pause_speech(switch):
    val = 1 if switch else 0
    command = f"pauseSpeech {val}"
    return _send_command(command)

def is_active():
    global _pipe_handle
    if _pipe_handle is None:
        if connect() != 0:
            return False
    try:
        _send_command("active")
        resp = win32file.ReadFile(_pipe_handle, 4096)
        if resp and resp[1].decode('utf-8').strip() == "NVDA":
            return True
    except pywintypes.error:
        disconnect()
    return False


