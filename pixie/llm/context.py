"""每次聊天附加在 system prompt 後面的狀態說明：時間、待辦、使用時間，以及腳色能力的界線。"""
from __future__ import annotations

from datetime import datetime

from ..system.usage_tracker import format_duration
from ..todo.parser import format_deadline, format_remaining
from ..todo.store import Todo

_RULES = """【回覆方式】
- 你的回覆顯示在螢幕角落的小對話框裡：保持簡短，通常 1～3 句；條列最多 5 點。
- 可以用簡單的 Markdown（粗體、條列），不要用標題和表格。

【你能做與不能做的事】
- 你看得到使用者的待辦清單，但「不能」新增、完成或刪除待辦，也看不到這次對話之後清單的變化。
- 使用者要你記事項、提醒、完成或刪除時：不要說「記下來了」「幫你整理好了」，也不要編造編號。
  直接給他一行可以複製貼上的指令，並說明輸入後才會真的記下來。指令格式：
  /add 事項 期限　例：/add 看牙醫 明天 10:00（期限可寫 18:00、明天、11/5 9:30、30分鐘、2h）
  /done 編號　　　完成某件事（編號用下面清單裡的 #數字）
  /del 編號　　　 刪除某件事"""


def build_llm_context(pending: list[Todo], usage_seconds: float, now: datetime | None = None) -> str:
    now = now or datetime.now()
    weekday = "一二三四五六日"[now.weekday()]
    lines = [
        _RULES,
        "",
        "【目前狀態，僅供參考，不需要每次都主動複述】",
        f"現在時間：{now:%Y-%m-%d %H:%M}（星期{weekday}）",
        f"使用者今天已使用電腦：{format_duration(usage_seconds)}",
    ]
    if pending:
        lines.append("使用者的未完成待辦：")
        for t in pending:
            d = t.deadline_dt
            due = f"，期限 {format_deadline(d, now)}（{format_remaining(d, now)}）" if d else "，無期限"
            lines.append(f"- #{t.id} {t.title}{due}")
    else:
        lines.append("使用者目前沒有未完成的待辦。")
    return "\n".join(lines)
