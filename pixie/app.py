"""組裝：腳色 + 面板（聊天/待辦）+ LLM + 待辦逾期檢查 + 喝水提醒 + 系統匣 + 開機自啟。

外觀優先順序（由高到低）：
    thinking  等待 LLM 回覆中
    tea_time  喝水提醒期間（點腳色或時間到就結束）
    angry     有待辦事項逾期未完成，直到全部完成/刪除
    default   其他時候（包含正常回話）
"""
from __future__ import annotations

import sys
from datetime import datetime

from PySide6.QtCore import QDir, QLockFile, QPoint, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import config as config_mod
from .llm import Message, create_provider
from .llm.context import build_llm_context
from .llm.worker import ChatWorker
from .system import autostart
from .system.usage_tracker import UsageTracker, format_duration
from .todo.parser import HELP_TEXT, Command, format_deadline, format_remaining, parse_command
from .todo.store import TodoStore
from .ui.character import CharacterWidget, State
from .sync import PhoneSync
from .ui.chat_panel import ChatPanel
from .ui.phone_sync_dialog import PhoneSyncDialog

_OVERDUE_CHECK_MS = 5_000
_ANGRY_COLOR = "#c0392b"


class DesktopPetApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.cfg = config_mod.load_config()
        char_cfg = self.cfg["character"]
        rem_cfg = self.cfg["reminder"]
        self.name = char_cfg["name"]
        data_dir = config_mod.DATA_ROOT / "data"

        self.provider, provider_error = create_provider(self.cfg["llm"], char_cfg["persona"])
        self.history: list[Message] = []
        self.worker: ChatWorker | None = None
        self.waiting_first_chunk = False
        self.reaction: State | None = None   # poke / speechless：短暫顯示後恢復
        self.reaction_timer = QTimer(singleShot=True,
                                     interval=int(float(char_cfg.get("reaction_sec", 2)) * 1000),
                                     timeout=self._end_reaction)

        # ---------- 待辦 ----------
        self.todos = TodoStore(data_dir / "todos.json")
        self.announced_overdue: set[int] = set()   # 已經罵過的逾期事項

        # ---------- 視窗 ----------
        self.character = CharacterWidget(char_cfg, config_mod.RESOURCE_ROOT)
        self.panel = ChatPanel(self.name, self.todos, self.cfg.get("panel", {}), config_mod.RESOURCE_ROOT)
        self.character.clicked.connect(self.on_character_clicked)
        self.character.moved.connect(lambda: self.panel.follow(self.character.frameGeometry()))
        self.character.menu_requested.connect(self.show_menu)
        self.panel.submitted.connect(self.on_submit)

        # ---------- 使用時間 / 喝水 ----------
        self.tea_active = False
        self.tea_timer = QTimer(singleShot=True,
                                interval=int(rem_cfg.get("tea_time_duration_sec", 60)) * 1000,
                                timeout=self.end_tea_time)
        self.usage = UsageTracker(rem_cfg, data_dir / "usage.json")
        self.usage.water_reminder.connect(self.start_tea_time)
        self.usage.updated.connect(self._update_tooltip)
        app.aboutToQuit.connect(self.usage.save)

        # ---------- 手機同步 ----------
        self.phone_sync = PhoneSync(self.cfg["phone_sync"], self.todos,
                                    lambda: config_mod.save_config(self.cfg))
        self.phone_sync.remote_applied.connect(self.panel.say)
        self._sync_dialog: PhoneSyncDialog | None = None

        self.menu = self._build_menu()
        self.tray = self._build_tray()

        # 同步開機自啟：開啟時每次都重寫，確保登錄檔指向目前這支程式（例如從 python 改成 exe 後）
        if autostart.is_supported() and (self.cfg.get("autostart") or autostart.is_enabled()):
            autostart.set_enabled(bool(self.cfg.get("autostart")))

        self.character.show()
        self.panel.say(self.line("greeting"))
        if provider_error:
            self.panel.say(f"⚠️ {provider_error}（目前改用離線 mock 模式）", color=_ANGRY_COLOR)
            self._popup_panel()
        self._greet_pending()

        self.todos.changed.connect(self.check_overdue)
        self.overdue_timer = QTimer(interval=_OVERDUE_CHECK_MS, timeout=self.check_overdue)
        self.overdue_timer.start()
        self.check_overdue()

    # ---------- 台詞 ----------
    def line(self, key: str, **kw) -> str:
        """取 config.json 的 character.lines 台詞；使用者改壞了格式就退回預設。"""
        lines = self.cfg["character"].get("lines", {})
        try:
            return lines.get(key, config_mod.PIXIE_LINES[key]).format(**kw)
        except (KeyError, IndexError, ValueError):
            return config_mod.PIXIE_LINES[key].format(**kw)

    # ---------- 外觀 ----------
    def refresh_state(self) -> None:
        if self.reaction:
            self.character.set_state(self.reaction)
        elif self.waiting_first_chunk:
            self.character.set_state(State.THINKING)
        elif self.tea_active:
            self.character.set_state(State.TEA_TIME)
        elif self.todos.overdue():
            self.character.set_state(State.ANGRY)
        else:
            self.character.set_state(State.DEFAULT)

    def react(self, state: State) -> None:
        """短暫換成某個表情，時間到回到原本的外觀（例如等待回覆時接著顯示 thinking）。"""
        self.reaction = state
        self.reaction_timer.start()
        self.refresh_state()

    def _end_reaction(self) -> None:
        self.reaction = None
        self.refresh_state()

    # ---------- 待辦：逾期檢查 ----------
    def check_overdue(self) -> None:
        overdue = self.todos.overdue()
        ids = {t.id for t in overdue}
        newly = [t for t in overdue if t.id not in self.announced_overdue]
        was_angry = bool(self.announced_overdue)

        if newly:
            names = "、".join(f"「{t.title}」" for t in newly)
            self.panel.say(self.line("overdue", names=names), color=_ANGRY_COLOR)
            self._popup_panel()
            if self.tray.supportsMessages():
                self.tray.showMessage(self.name, f"{names} 逾期了！", QSystemTrayIcon.Warning, 5000)
        elif was_angry and not ids:
            self.panel.say(self.line("forgiven"))

        self.announced_overdue = ids
        self.refresh_state()

    def _greet_pending(self) -> None:
        pending = self.todos.pending()
        if pending:
            self.panel.say(self.line("pending", n=len(pending)))

    # ---------- 輸入：先看是不是待辦指令，不是就交給 LLM ----------
    def on_submit(self, text: str) -> None:
        self.react(State.SPEECHLESS)
        cmd = parse_command(text)
        if cmd is None:
            self.send(text)
            return
        self.panel.add_user(text)
        self.handle_command(cmd)

    def handle_command(self, cmd: Command) -> None:
        if cmd.error:
            self.panel.say(cmd.error)
        elif cmd.action == "help":
            self.panel.say(HELP_TEXT)
        elif cmd.action == "list":
            self.panel.say(self._todo_list_text())
        elif cmd.action == "add":
            t = self.todos.add(cmd.title, cmd.deadline)
            if cmd.deadline:
                self.panel.say(self.line("todo_added", id=t.id, title=t.title,
                                         deadline=format_deadline(cmd.deadline),
                                         remaining=format_remaining(cmd.deadline)))
            else:
                self.panel.say(self.line("todo_added_no_deadline", id=t.id, title=t.title))
        elif cmd.action in ("done", "del"):
            t = self.todos.get(cmd.todo_id)
            if not t or t.done:
                self.panel.say(self.line("todo_not_found", id=cmd.todo_id))
            elif cmd.action == "done":
                self.todos.complete(t.id)
                self.panel.say(self.line("todo_done", title=t.title))
            else:
                self.todos.delete(t.id)
                self.panel.say(self.line("todo_deleted", title=t.title))

    def _todo_list_text(self) -> str:
        pending = self.todos.pending()
        if not pending:
            return "目前沒有待辦事項 🎉"
        lines = ["📋 待辦清單："]
        for t in pending:
            d = t.deadline_dt
            due = f"　⏰ {format_deadline(d)}（{format_remaining(d)}）" if d else ""
            lines.append(f"#{t.id} {t.title}{due}")
        return "\n".join(lines)

    # ---------- 喝水提醒 ----------
    def start_tea_time(self, today_seconds: float) -> None:
        self.tea_active = True
        self.tea_timer.start()
        self.refresh_state()
        mins = int(self.usage.interval // 60)
        self.panel.say(self.line("tea_time", mins=mins, today=format_duration(today_seconds)))
        self._popup_panel()
        if self.tray.supportsMessages():
            self.tray.showMessage(self.name, "該喝水囉！", QSystemTrayIcon.Information, 5000)

    def end_tea_time(self) -> None:
        if self.tea_active:
            self.tea_active = False
            self.tea_timer.stop()
            self.refresh_state()

    def on_character_clicked(self) -> None:
        if self.tea_active:  # 提醒期間點腳色 = 「我喝了」
            self.end_tea_time()
            self.panel.say(self.line("tea_done"))
            self._popup_panel()
            return
        opening = not self.panel.isVisible()
        if opening and self.todos.overdue() and not self.waiting_first_chunk:
            self.panel.show_tab(ChatPanel.TAB_TODO)  # 生氣時點她 → 直接看待辦
        self.toggle_panel()
        if opening:
            self.react(State.POKE)

    # ---------- 對話 ----------
    def _popup_panel(self) -> None:
        self.panel.show_tab(ChatPanel.TAB_CHAT)
        self.panel.follow(self.character.frameGeometry())
        self.panel.show_panel()

    def toggle_panel(self) -> None:
        if self.panel.isVisible():
            self.panel.hide()
        else:
            self.panel.follow(self.character.frameGeometry())
            self.panel.show_panel()

    def send(self, text: str) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-self.cfg["llm"].get("history_limit", 20):]
        if self.history[0]["role"] != "user":  # Messages API 要求第一則是 user
            self.history = self.history[1:]

        self.panel.add_user(text)
        self.panel.begin_reply()
        self.panel.set_busy(True)
        self.waiting_first_chunk = True
        self.refresh_state()

        self.worker = ChatWorker(self.provider, self.history, self._llm_context())
        self.worker.chunk.connect(self._on_chunk)
        self.worker.finished_text.connect(self._on_done)
        self.worker.start()

    def _llm_context(self) -> str:
        """讓 LLM 知道現在時間、使用者的待辦、今天用了多久電腦，以及它能力的界線。"""
        return build_llm_context(self.todos.pending(), self.usage.today_seconds)

    def _on_chunk(self, chunk: str) -> None:
        if self.waiting_first_chunk:  # 開始回話 → 從 thinking 換回來
            self.waiting_first_chunk = False
            self.refresh_state()
        self.panel.append_reply(chunk)

    def _on_done(self, full: str) -> None:
        self.history.append({"role": "assistant", "content": full})
        self.waiting_first_chunk = False
        self.refresh_state()
        self.panel.set_busy(False)

    # ---------- 選單 / 系統匣 ----------
    def _build_menu(self) -> QMenu:
        m = QMenu()
        self.usage_action = m.addAction("")
        self.usage_action.setEnabled(False)
        m.aboutToShow.connect(self._refresh_usage_action)
        m.addSeparator()
        m.addAction("聊天", lambda: self._open_tab(ChatPanel.TAB_CHAT))
        m.addAction("待辦清單", lambda: self._open_tab(ChatPanel.TAB_TODO))
        m.addAction("回到右下角", self._reset_position)
        m.addAction("清除對話記憶", self._clear_history)
        m.addAction("立即測試喝水提醒", lambda: self.start_tea_time(self.usage.today_seconds))
        m.addAction("手機同步…", self._open_phone_sync)
        m.addSeparator()
        self.autostart_action = QAction("開機時自動啟動", m, checkable=True)
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.setEnabled(autostart.is_supported())
        self.autostart_action.toggled.connect(self._toggle_autostart)
        m.addAction(self.autostart_action)
        m.addAction("隱藏 / 顯示腳色", self._toggle_character)
        m.addAction("開啟設定與資料資料夾", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(config_mod.DATA_ROOT))))
        m.addSeparator()
        m.addAction("離開", self.app.quit)
        return m

    def _open_phone_sync(self) -> None:
        if self._sync_dialog is None:
            self._sync_dialog = PhoneSyncDialog(self.phone_sync)
        self._sync_dialog.show()
        self._sync_dialog.raise_()
        self._sync_dialog.activateWindow()

    def _open_tab(self, index: int) -> None:
        self.panel.show_tab(index)
        self.panel.follow(self.character.frameGeometry())
        self.panel.show_panel()

    def _refresh_usage_action(self) -> None:
        self.usage_action.setText(f"今天已使用電腦：{format_duration(self.usage.today_seconds)}")

    def _update_tooltip(self, today_seconds: float) -> None:
        n = len(self.todos.pending())
        self.tray.setToolTip(f"{self.name}\n今天已使用：{format_duration(today_seconds)}\n待辦：{n} 件")

    def _build_tray(self) -> QSystemTrayIcon:
        pix = self.character.sprites.get(State.DEFAULT)
        icon = QIcon(pix) if pix else QIcon(self.character.grab())
        tray = QSystemTrayIcon(icon)
        tray.setContextMenu(self.menu)
        tray.activated.connect(
            lambda reason: self._toggle_character() if reason == QSystemTrayIcon.Trigger else None)
        tray.setToolTip(self.name)
        tray.show()
        return tray

    def show_menu(self, pos: QPoint) -> None:
        self.menu.popup(pos)

    def _reset_position(self) -> None:
        self.character.move_to_corner()
        self.panel.follow(self.character.frameGeometry())

    def _clear_history(self) -> None:
        self.history.clear()
        self.panel.view.clear()
        self.panel.say(self.line("history_cleared"))

    def _toggle_character(self) -> None:
        if self.character.isVisible():
            self.character.hide()
            self.panel.hide()
        else:
            self.character.show()

    def _toggle_autostart(self, on: bool) -> None:
        autostart.set_enabled(on)
        self.cfg["autostart"] = on
        config_mod.save_config(self.cfg)


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 收起對話框不會關掉程式

    # 只允許一個實例：開機自啟後又手動點 exe，不會出現兩個腳色
    lock = QLockFile(QDir.temp().filePath("pixie-desktop-pet.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "Pixie", "小精靈已經在執行了，請看螢幕右下角或系統匣。")
        return 0

    _pet = DesktopPetApp(app)
    return app.exec()
