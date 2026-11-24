"""浮在腳色上方的面板：「聊天」與「待辦」兩個分頁。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QGuiApplication, QKeyEvent, QPainter, QPainterPath, QPixmap,
                           QTextBlockFormat, QTextCharFormat, QTextDocumentFragment)
from PySide6.QtWidgets import QFrame, QLineEdit, QTabWidget, QTextBrowser, QVBoxLayout, QWidget

from ..todo.store import TodoStore
from .character import load_pixmap
from .todo_view import TodoView

_STYLE = """
#panel { background: transparent; border: 2px solid #9b7bc4; border-radius: 14px; }
QTextBrowser, QListWidget { border: none; background: transparent; color: #241733; font-size: 14px; }
QListWidget::item { padding: 4px 2px; border-bottom: 1px solid #efe7f8; }
QListWidget::item:selected { background: #f3ecfb; }
QListWidget::indicator { width: 14px; height: 14px; border: 2px solid #9b7bc4;
                         border-radius: 4px; background: white; }
QListWidget::indicator:hover { background: #efe7f8; }
QListWidget::indicator:checked { background: #9b7bc4; }
QLineEdit { border: 1px solid #d7c6ee; border-radius: 8px; padding: 6px 8px;
            background: #faf6ff; color: #241733; font-size: 13px; }
QLineEdit:focus { border-color: #9b7bc4; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: transparent; color: #4e3f66; padding: 4px 12px; font-size: 13px; }
QTabBar::tab:selected { color: #241733; font-weight: bold; border-bottom: 2px solid #9b7bc4; }
"""


class ChatPanel(QWidget):
    submitted = Signal(str)

    WIDTH, HEIGHT = 320, 320
    TAB_CHAT, TAB_TODO = 0, 1

    RADIUS = 14

    def __init__(self, title: str, todo_store: TodoStore, cfg: dict | None = None, root: Path | None = None):
        super().__init__()
        cfg = cfg or {}
        self._bg_opacity = max(0.0, min(1.0, float(cfg.get("background_opacity", 0.45))))
        self._bg = self._load_background(root / cfg["background"]) if root and cfg.get("background") else None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setWindowTitle(f"{title}：")
        self._reply_start = 0
        self._current_reply = ""

        frame = QFrame(self, objectName="panel")
        frame.setStyleSheet(_STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

        # 聊天分頁
        chat = QWidget()
        chat_lay = QVBoxLayout(chat)
        chat_lay.setContentsMargins(0, 4, 0, 0)
        self.view = QTextBrowser(openExternalLinks=True)
        self.input = QLineEdit(placeholderText="聊天，或輸入 /add 事項 期限（/help 看指令）")
        self.input.returnPressed.connect(self._submit)
        chat_lay.addWidget(self.view, 1)
        chat_lay.addWidget(self.input)

        # 待辦分頁
        self.todo_view = TodoView(todo_store)

        self.tabs = QTabWidget(documentMode=True)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.addTab(chat, "聊天")
        self.tabs.addTab(self.todo_view, "待辦")
        todo_store.changed.connect(self._update_todo_tab_title)
        self._todo_store = todo_store
        self._update_todo_tab_title()

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.addWidget(self.tabs)

    # ---------- 背景 ----------
    def _load_background(self, path: Path) -> QPixmap | None:
        if not path.exists():
            print(f"[panel] 找不到背景圖 {path}")
            return None
        pix = load_pixmap(path)
        if pix.isNull():
            return None
        # 等比例放大到蓋滿整個面板，多出來的部分從中間裁掉
        pix = pix.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x, y = (pix.width() - self.width()) // 2, (pix.height() - self.height()) // 2
        return pix.copy(x, y, self.width(), self.height())

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), self.RADIUS, self.RADIUS)
        p.setClipPath(path)
        p.fillPath(path, QColor(255, 255, 255, 245))   # 先鋪白底：圖調淡時是變白，不會透出桌面
        if self._bg:
            p.setOpacity(self._bg_opacity)
            p.drawPixmap(0, 0, self._bg)
        p.end()

    # ---------- 分頁 ----------
    def _update_todo_tab_title(self) -> None:
        n = len(self._todo_store.pending())
        self.tabs.setTabText(self.TAB_TODO, f"待辦 ({n})" if n else "待辦")

    def show_tab(self, index: int) -> None:
        self.tabs.setCurrentIndex(index)

    # ---------- 聊天內容 ----------
    def _submit(self) -> None:
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.submitted.emit(text)

    def add_user(self, text: str) -> None:
        self.view.append(f'<p style="color:#3f3156;"><b>你：</b>{_esc(text)}</p>')

    def begin_reply(self) -> None:
        self._current_reply = ""
        self.view.append(f'<b style="color:#4f3480;">{_esc(self.windowTitle())}</b>')
        # 回覆放在下一個段落，並清掉粗體格式，避免回覆第一段繼承名字的樣式
        cursor = self.view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertBlock(QTextBlockFormat(), QTextCharFormat())
        self._reply_start = cursor.position()

    def append_reply(self, chunk: str) -> None:
        self._current_reply += chunk
        cursor = self.view.textCursor()
        cursor.setPosition(self._reply_start)
        cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        # LLM 回覆常帶 Markdown（粗體、條列），每收到一段就整段重新渲染
        cursor.insertFragment(QTextDocumentFragment.fromMarkdown(self._current_reply))
        self._scroll_bottom()

    def say(self, text: str, color: str | None = None) -> None:
        """腳色主動說一句話（招呼、提醒、指令回覆）。"""
        style = f' style="color:{color};"' if color else ""
        self.view.append(f"<p{style}>{_esc(text)}</p>")
        self._scroll_bottom()

    def _scroll_bottom(self) -> None:
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_busy(self, busy: bool) -> None:
        self.input.setEnabled(not busy)
        if not busy:
            self.input.setFocus()

    # ---------- 位置：貼在腳色上方，超出螢幕就往內收 ----------
    def follow(self, anchor: QRect) -> None:
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = anchor.right() - self.width()
        y = anchor.top() - self.height() - 4
        if y < area.top():
            y = anchor.bottom() + 4
        x = max(area.left(), min(x, area.right() - self.width()))
        self.move(QPoint(x, y))

    def show_panel(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        if self.tabs.currentIndex() == self.TAB_CHAT:
            self.input.setFocus()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace("\n", "<br>"))
