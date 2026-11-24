"""「待辦」分頁：列出未完成事項，打勾 = 完成，右鍵可刪除。"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QVBoxLayout, QWidget

from ..todo.parser import format_deadline, format_remaining, split_deadline
from ..todo.store import TodoStore

_OVERDUE = QColor("#c0392b")
_SOON = QColor("#d35400")     # 1 小時內到期
_NORMAL = QColor("#241733")


class TodoView(QWidget):
    def __init__(self, store: TodoStore, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store

        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.itemChanged.connect(self._on_item_changed)

        self.empty = QLabel("沒有待辦事項 🎉\n在下面輸入「事項 期限」新增，例如：交報告 明天 18:00",
                            alignment=Qt.AlignCenter, wordWrap=True)
        self.empty.setStyleSheet("color:#4e3f66;")

        self.input = QLineEdit(placeholderText="新增：事項 期限（例：繳費 11/5 18:00）")
        self.input.returnPressed.connect(self._quick_add)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.empty, 1)
        lay.addWidget(self.input)

        store.changed.connect(self.refresh)
        # 「剩幾分」要隨時間更新
        self._timer = QTimer(self, interval=30_000, timeout=self.refresh)
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        now = datetime.now()
        self.list.blockSignals(True)
        self.list.clear()
        for t in self.store.pending():
            d = t.deadline_dt
            if d:
                text = f"#{t.id}  {t.title}\n      ⏰ {format_deadline(d, now)}（{format_remaining(d, now)}）"
            else:
                text = f"#{t.id}  {t.title}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, t.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            color = _NORMAL
            if d and d <= now:
                color = _OVERDUE
            elif d and (d - now).total_seconds() <= 3600:
                color = _SOON
            item.setForeground(QBrush(color))
            self.list.addItem(item)
        self.list.blockSignals(False)
        has_items = self.list.count() > 0
        self.list.setVisible(has_items)
        self.empty.setVisible(not has_items)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if item.checkState() == Qt.Checked:
            # 延後執行：在 item 自己的 signal 裡重建清單會刪掉正在使用的 item
            todo_id = item.data(Qt.UserRole)
            QTimer.singleShot(0, lambda: self.store.complete(todo_id))

    def _context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.addAction("完成", lambda: self.store.complete(item.data(Qt.UserRole)))
        menu.addAction("刪除", lambda: self.store.delete(item.data(Qt.UserRole)))
        menu.exec(self.list.mapToGlobal(pos))

    def _quick_add(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        title, deadline = split_deadline(text)
        if title:
            self.store.add(title, deadline)
            self.input.clear()
