"""解析聊天框裡的待辦指令與期限文字。

指令：
    /add 事項 [期限]      也可用「+ 事項」或「新增 事項」
    /list                也可用「待辦」「清單」
    /done 編號           也可用「完成 編號」
    /del 編號            也可用「刪除 編號」
    /help                也可用「指令」

期限寫在事項最後面（可加 @ 分隔）：
    18:00                今天 18:00（已過就算明天）
    明天 18:00 / 後天 9:30 / 今天
    11/5  或  11/5 18:00
    2026-11-05 18:00
    30分鐘 / 30m / 2小時 / 1.5h   （從現在起算，「後」可加可不加）
只寫日期沒寫時間 → 當天 23:59。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

_ADD = ("/add", "+", "新增")
_LIST = ("/list", "/ls", "待辦", "清單")
_DONE = ("/done", "完成")
_DEL = ("/del", "/rm", "刪除")
_HELP = ("/help", "指令")

HELP_TEXT = (
    "📋 待辦指令：\n"
    "• /add 事項 期限　例：/add 交報告 明天 18:00\n"
    "　期限可寫 18:00、明天、11/5 9:00、30分鐘、2h…不寫就是沒期限\n"
    "• /list　看清單\n"
    "• /done 編號　完成（也可以在「待辦」分頁直接打勾）\n"
    "• /del 編號　刪除"
)


@dataclass
class Command:
    action: str                 # add | list | done | del | help
    title: str = ""
    deadline: datetime | None = None
    todo_id: int | None = None
    error: str = ""


def parse_command(text: str, now: datetime | None = None) -> Command | None:
    """不是待辦指令就回傳 None（交給 LLM 聊天）。"""
    s = text.strip()
    head, _, rest = s.partition(" ")
    if s.startswith("+") and not head == "+":   # 「+買牛奶」沒空格的寫法
        head, rest = "+", s[1:]
    rest = rest.strip()
    key = head.lower()

    if key in _HELP and not rest:
        return Command("help")
    if key in _LIST and not rest:
        return Command("list")
    if key in _DONE or key in _DEL:
        action = "done" if key in _DONE else "del"
        m = re.fullmatch(r"#?(\d+)", rest)
        if not m:
            return Command(action, error=f"要告訴我編號喔，例如：{head} 1")
        return Command(action, todo_id=int(m.group(1)))
    if key in _ADD:
        if not rest:
            return Command("add", error="要新增什麼呢？例如：/add 交報告 明天 18:00")
        title, deadline = split_deadline(rest, now)
        if not title:
            return Command("add", error="事項名稱不能是空的喔")
        return Command("add", title=title, deadline=deadline)
    return None


# ---------- 期限 ----------
_DAY_WORDS = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "後天": 2}
_TIME = r"(?P<h>\d{1,2})[:：](?P<mi>\d{2})"
_PATTERNS: list[tuple[str, str]] = [
    ("relative", r"(?P<n>\d+(?:\.\d+)?)\s*(?P<unit>分鐘|分|m|min|mins|小時|h|hr|hrs)後?"),
    ("ymd", r"(?P<y>\d{4})[-/](?P<mo>\d{1,2})[-/](?P<d>\d{1,2})(?:\s+" + _TIME + ")?"),
    ("md", r"(?P<mo>\d{1,2})/(?P<d>\d{1,2})(?:\s+" + _TIME + ")?"),
    ("dayword", r"(?P<w>今天|今日|明天|明日|後天)(?:\s*" + _TIME + ")?"),
    ("time", _TIME),
]


def split_deadline(text: str, now: datetime | None = None) -> tuple[str, datetime | None]:
    """從句尾切出期限。回傳 (事項, 期限或 None)。"""
    now = (now or datetime.now()).replace(second=0, microsecond=0)
    for kind, pat in _PATTERNS:
        # 前面不能緊接數字或分隔符（避免把 2026-11-05 切成 -11-05），但允許中文直接相連：交報告明天18:00
        m = re.search(r"(?<![\d/:：.\-])" + pat + r"\s*$", text, re.IGNORECASE)
        if not m:
            continue
        dt = _build(kind, m, now)
        if dt is None:
            continue
        title = text[: m.start()].strip().rstrip("@").strip()
        return title, dt
    return text.strip(), None


def _build(kind: str, m: re.Match, now: datetime) -> datetime | None:
    g = m.groupdict()
    h = int(g["h"]) if g.get("h") else None
    mi = int(g["mi"]) if g.get("mi") else None
    try:
        if kind == "relative":
            n = float(g["n"])
            unit = g["unit"].lower()
            delta = timedelta(hours=n) if unit in ("小時", "h", "hr", "hrs") else timedelta(minutes=n)
            return now + delta
        if kind == "time":
            dt = now.replace(hour=h, minute=mi)
            return dt if dt > now else dt + timedelta(days=1)
        if kind == "dayword":
            base = now + timedelta(days=_DAY_WORDS[g["w"]])
            return base.replace(hour=h, minute=mi) if h is not None else base.replace(hour=23, minute=59)
        if kind in ("md", "ymd"):
            year = int(g["y"]) if kind == "ymd" else now.year
            dt = datetime(year, int(g["mo"]), int(g["d"]),
                          h if h is not None else 23, mi if mi is not None else 59)
            if kind == "md" and dt < now - timedelta(days=1):  # 已經過很久 → 明年
                dt = dt.replace(year=year + 1)
            return dt
    except ValueError:  # 例如 25:00、13/40
        return None
    return None


# ---------- 顯示 ----------
def format_deadline(dt: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    days = (dt.date() - now.date()).days
    day = {0: "今天", 1: "明天", 2: "後天", -1: "昨天"}.get(days, dt.strftime("%m/%d"))
    return f"{day} {dt:%H:%M}"


def format_remaining(dt: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    secs = (dt - now).total_seconds()
    mins = math.ceil(secs / 60) if secs > 0 else int(-secs // 60)
    d, rem = divmod(mins, 1440)
    h, m = divmod(rem, 60)
    parts = (f"{d} 天 " if d else "") + (f"{h} 小時 " if h else "") + (f"{m} 分" if m and not d else "")
    parts = parts.strip() or "不到 1 分"
    return f"已逾期 {parts}" if secs <= 0 else f"剩 {parts}"
