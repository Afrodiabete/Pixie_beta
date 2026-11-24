"""電腦使用時間追蹤 + 喝水提醒。

- 每隔幾秒檢查一次鍵盤/滑鼠閒置時間（Windows GetLastInputInfo）
- 閒置超過 idle_threshold 視為離開，不計入使用時間
- 實際使用時間每累積 water_interval 就發出 water_reminder
- 每日累計存在 data/usage.json，重開機也不會歸零
"""
from __future__ import annotations

import ctypes
import json
import sys
import time
from datetime import date
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

_POLL_SEC = 5
_SAVE_EVERY_SEC = 60


def idle_seconds() -> float:
    """距離最後一次鍵盤/滑鼠操作的秒數；非 Windows 回傳 0（視為一直在使用）。"""
    if sys.platform != "win32":
        return 0.0

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0


def format_duration(seconds: float) -> str:
    m = int(seconds // 60)
    h, m = divmod(m, 60)
    return f"{h} 小時 {m} 分" if h else f"{m} 分鐘"


class UsageTracker(QObject):
    water_reminder = Signal(float)   # 參數：今日累計使用秒數
    updated = Signal(float)          # 每次輪詢後送出今日累計秒數

    def __init__(self, cfg: dict, data_path: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.interval = float(cfg.get("water_interval_min", 30)) * 60
        self.idle_threshold = float(cfg.get("idle_threshold_min", 5)) * 60
        self.data_path = data_path

        self.today = date.today().isoformat()
        self.today_seconds = self._load().get(self.today, 0.0)
        self.since_reminder = 0.0
        self._last = time.monotonic()
        self._since_save = 0.0

        self._timer = QTimer(self, interval=_POLL_SEC * 1000, timeout=self._poll)
        self._timer.start()

    # ---------- 對外 ----------
    def reset_reminder(self) -> None:
        self.since_reminder = 0.0

    def save(self) -> None:
        data = self._load()
        data[self.today] = round(self.today_seconds)
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            self.data_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as e:
            print(f"[usage] 存檔失敗：{e}")

    # ---------- 內部 ----------
    def _load(self) -> dict:
        try:
            return json.loads(self.data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _poll(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._last = now
        # 睡眠/休眠喚醒後 elapsed 會很大，這段時間不算使用
        if elapsed > _POLL_SEC * 6:
            elapsed = 0.0

        # 跨日：存檔後換新的一天
        today = date.today().isoformat()
        if today != self.today:
            self.save()
            self.today, self.today_seconds = today, 0.0

        if idle_seconds() < self.idle_threshold:
            self.today_seconds += elapsed
            self.since_reminder += elapsed
            if self.since_reminder >= self.interval:
                self.since_reminder = 0.0
                self.water_reminder.emit(self.today_seconds)

        self._since_save += elapsed
        if self._since_save >= _SAVE_EVERY_SEC:
            self._since_save = 0.0
            self.save()
        self.updated.emit(self.today_seconds)
