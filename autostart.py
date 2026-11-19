"""Current-user autostart for portable builds; installer uses the same registry key."""
import os
import sys

KEY_NAME = 'KeePassLANShare'


def is_enabled():
    if os.name != 'nt':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            return bool(winreg.QueryValueEx(key, KEY_NAME)[0])
    except FileNotFoundError:
        return False


def set_enabled(enabled):
    if os.name != 'nt':
        raise RuntimeError('Solo disponible en Windows')
    import winreg
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('El inicio automático solo se habilita desde la versión .exe instalada.')
    path = '"' + sys.executable + '" --background'
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Run',
                            0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, KEY_NAME, 0, winreg.REG_SZ, path)
        else:
            try:
                winreg.DeleteValue(key, KEY_NAME)
            except FileNotFoundError:
                pass
