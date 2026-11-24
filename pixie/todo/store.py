"""待辦事項資料：存在 data/todos.json。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal


@dataclass
class Todo:
    id: int
    title: str
    deadline: str | None = None      # ISO 格式；None = 沒有期限
    done: bool = False
    created_at: str = ""
    done_at: str | None = None

    @property
    def deadline_dt(self) -> datetime | None:
        return datetime.fromisoformat(self.deadline) if self.deadline else None

    def is_overdue(self, now: datetime | None = None) -> bool:
        d = self.deadline_dt
        return (not self.done) and d is not None and d <= (now or datetime.now())


class TodoStore(QObject):
    changed = Signal()

    def __init__(self, path: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.path = path
        self.todos: list[Todo] = self._load()

    # ---------- 查詢 ----------
    def pending(self) -> list[Todo]:
        """未完成，依期限排序（沒期限的放最後）。"""
        items = [t for t in self.todos if not t.done]
        return sorted(items, key=lambda t: (t.deadline is None, t.deadline or "", t.id))

    def overdue(self, now: datetime | None = None) -> list[Todo]:
        now = now or datetime.now()
        return [t for t in self.pending() if t.is_overdue(now)]

    def get(self, todo_id: int) -> Todo | None:
        """編號會重複使用（已完成的事項保留舊編號），所以優先找未完成的。"""
        pending = next((t for t in self.todos if t.id == todo_id and not t.done), None)
        return pending or next((t for t in self.todos if t.id == todo_id), None)

    def find_pending(self, todo_id: int, title: str) -> Todo | None:
        """編號 + 名稱都對得上才算（手機送來的操作可能是舊的，編號已被別的事項重用）。"""
        return next((t for t in self.todos if not t.done and t.id == todo_id and t.title == title), None)

    def _next_id(self) -> int:
        """最小的、沒被未完成事項使用的編號：#2 完成後，下一個新增的就是 #2。"""
        used = {t.id for t in self.todos if not t.done}
        n = 1
        while n in used:
            n += 1
        return n

    # ---------- 修改 ----------
    def add(self, title: str, deadline: datetime | None) -> Todo:
        todo = Todo(
            id=self._next_id(),
            title=title,
            deadline=deadline.isoformat(timespec="minutes") if deadline else None,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        self.todos.append(todo)
        self._commit()
        return todo

    def complete(self, todo_id: int) -> Todo | None:
        t = self.get(todo_id)
        if t and not t.done:
            t.done = True
            t.done_at = datetime.now().isoformat(timespec="seconds")
            self._commit()
        return t

    def delete(self, todo_id: int) -> Todo | None:
        t = self.get(todo_id)
        if t:
            self.todos.remove(t)
            self._commit()
        return t

    # ---------- 存檔 ----------
    def _load(self) -> list[Todo]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return [Todo(**item) for item in raw]
        except (OSError, json.JSONDecodeError, TypeError):
            return []

    def _commit(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps([asdict(t) for t in self.todos], ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        except OSError as e:
            print(f"[todo] 存檔失敗：{e}")
        self.changed.emit()
