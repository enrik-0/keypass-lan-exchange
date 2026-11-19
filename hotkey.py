"""Global Windows hotkey; only triggers when KeePassXC is foreground."""
import ctypes
import os
import threading
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

HOTKEY_ID = 0x4B53
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_CONTROL = 0x0002
MOD_ALT = 0x0001
VK_S = 0x53
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class WindowsHotkey(QObject):
    activated = Signal()
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        self.thread_id = None
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.ready = threading.Event()

    def start(self):
        self.thread.start()
        self.ready.wait(timeout=3)

    def _listen(self):
        self.thread_id = self.kernel32.GetCurrentThreadId()
        # MOD_NOREPEAT: suppress repeated events while key remains pressed.
        ok = self.user32.RegisterHotKey(None, HOTKEY_ID,
                                        MOD_CONTROL | MOD_ALT | 0x4000, VK_S)
        self.ready.set()
        if not ok:
            self.error.emit('No se pudo registrar Ctrl+Alt+S. Quizá otra aplicación utiliza ese atajo.')
            return
        msg = wintypes.MSG()
        try:
            while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self.activated.emit()
        finally:
            self.user32.UnregisterHotKey(None, HOTKEY_ID)

    def stop(self):
        if self.thread_id and self.thread.is_alive():
            self.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
            self.thread.join(timeout=2)


def keepassxc_is_foreground():
    """Inspect foreground process image, not just spoofable window title."""
    if os.name != 'nt':
        return False
    u32 = ctypes.WinDLL('user32', use_last_error=True)
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    u32.GetForegroundWindow.restype = wintypes.HWND
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    hwnd = u32.GetForegroundWindow()
    if not hwnd:
        return False
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return False
    handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return False
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if not k32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            return False
        return os.path.basename(buffer.value).lower() == 'keepassxc.exe'
    finally:
        k32.CloseHandle(handle)


def clipboard_sequence():
    u32 = ctypes.WinDLL('user32', use_last_error=True)
    u32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    return u32.GetClipboardSequenceNumber()


def copy_shortcut():
    """Inject Ctrl+C only after KeePassXC foreground was verified."""
    u32 = ctypes.WinDLL('user32', use_last_error=True)
    VK_CONTROL = 0x11
    VK_C = 0x43
    KEYEVENTF_KEYUP = 0x0002
    # At this stage Ctrl+Alt+S has been released (see timer in app.py).
    u32.keybd_event(VK_CONTROL, 0, 0, 0)
    u32.keybd_event(VK_C, 0, 0, 0)
    u32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    u32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
