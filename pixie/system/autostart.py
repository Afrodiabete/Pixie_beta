"""Windows 開機自啟：寫入 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run（不需系統管理員權限）。"""
from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "PixieDesktopPet"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _command() -> str:
    if getattr(sys, "frozen", False):  # 之後用 PyInstaller 打包成 exe 時
        return f'"{sys.executable}"'
    main = Path(__file__).resolve().parents[2] / "main.py"
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")  # 用 pythonw 才不會跳出黑色主控台
    return f'"{pythonw if pythonw.exists() else exe}" "{main}"'


def is_supported() -> bool:
    return sys.platform == "win32"


def is_enabled() -> bool:
    if not is_supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool) -> None:
    if not is_supported():
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
