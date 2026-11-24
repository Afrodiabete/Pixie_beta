"""電腦 ↔ 手機同步（經 ntfy 中繼，內容加密）。

電腦 → 手機：未完成待辦推到 {topic}
- 待辦有變動 → 2 秒後推送（連續修改只送一次）
- 每 6 小時再送一次：ntfy.sh 只保留訊息 12 小時，定期重送讓手機隨時拿得到最新清單
手機 → 電腦：每 30 秒拉一次 {topic}-up，套用手機上的新增 / 完成
- 用 op uid 去重，處理過的 uid 會放進下一次推送的 "applied"，手機看到才把它從待送清單移除
- 網路請求在背景執行緒，不會卡住 UI
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta

import httpx
from PySide6.QtCore import QObject, QTimer, Signal

from ..todo.store import TodoStore
from . import protocol

_DEBOUNCE_MS = 2_000
_HEARTBEAT_MS = 6 * 60 * 60 * 1000
_POLL_MS = 30_000
_APPLIED_KEEP = timedelta(days=7)   # 手機那邊超過 7 天沒確認的操作會放棄，兩邊對齊
_APPLIED_SEND_MAX = 60


class PhoneSync(QObject):
    status_changed = Signal(str)        # 給設定視窗顯示
    remote_applied = Signal(str)        # 手機的操作套用後，給聊天面板顯示
    _ops_received = Signal(list, str)   # 背景執行緒 → 主執行緒：(ops, 最後一則訊息 id)

    def __init__(self, cfg: dict, store: TodoStore, save_cfg, parent: QObject | None = None):
        super().__init__(parent)
        self.cfg = cfg                 # 指向 config["phone_sync"]，會直接修改
        self.store = store
        self._save_cfg = save_cfg
        self.status = "尚未同步"
        self._lock = threading.Lock()
        self._polling = False

        self._debounce = QTimer(self, singleShot=True, interval=_DEBOUNCE_MS, timeout=self.push_now)
        self._heartbeat = QTimer(self, interval=_HEARTBEAT_MS, timeout=self.push_now)
        self._poll = QTimer(self, interval=_POLL_MS, timeout=self.poll_now)
        self._ops_received.connect(self._apply_ops)
        store.changed.connect(self._schedule)
        if self.enabled:
            self._start_timers()
            QTimer.singleShot(3_000, self.poll_now)   # 啟動後先收手機的操作，再送一次清單
            QTimer.singleShot(3_000, self.push_now)

    # ---------- 設定 ----------
    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled") and self.cfg.get("topic") and self.cfg.get("key"))

    def ensure_credentials(self) -> None:
        if not self.cfg.get("topic") or not self.cfg.get("key"):
            self.reset_credentials()

    def reset_credentials(self) -> None:
        """產生新的 topic 與金鑰；舊手機需要重新配對。"""
        self.cfg["topic"] = protocol.new_topic()
        self.cfg["key"] = protocol.new_key()
        self.cfg.pop("up_since", None)
        self.cfg.pop("applied", None)
        self._save_cfg()

    def set_enabled(self, on: bool) -> None:
        if on:
            self.ensure_credentials()
        self.cfg["enabled"] = on
        self._save_cfg()
        if on:
            self._start_timers()
            self.poll_now()
            self.push_now()
        else:
            self._heartbeat.stop()
            self._poll.stop()
            self._set_status("已停用")

    def _start_timers(self) -> None:
        self._heartbeat.start()
        self._poll.start()

    def pairing_uri(self) -> str:
        self.ensure_credentials()
        return protocol.pairing_uri(self.cfg["server"], self.cfg["topic"], self.cfg["key"])

    def _url(self, suffix: str = "") -> str:
        return f"{self.cfg['server'].rstrip('/')}/{self.cfg['topic']}{suffix}"

    # ---------- 推送（電腦 → 手機） ----------
    def _schedule(self) -> None:
        if self.enabled:
            self._debounce.start()

    def push_now(self) -> None:
        if not self.enabled:
            return
        # 快照在主執行緒建立，背景執行緒只負責加密與網路
        pending = list(self.store.pending())
        applied = self._recent_applied()
        threading.Thread(target=self._push, args=(self._url(), self.cfg["key"], pending, applied),
                         daemon=True).start()

    def _push(self, url: str, key: str, pending, applied: list[str]) -> None:
        with self._lock:
            try:
                payload, sent = protocol.encrypt_fitting(pending, key, applied)
                r = httpx.post(url, content=payload.encode(), timeout=20,
                               headers={"Firebase": "no", "Cache": "yes", "Title": "pixie-sync"})
                r.raise_for_status()
                note = f"（清單太長，只送出前 {sent} 件）" if sent < len(pending) else ""
                self._set_status(f"✅ {datetime.now():%H:%M:%S} 已同步 {sent} 件待辦{note}")
            except Exception as e:
                self._set_status(f"⚠️ {datetime.now():%H:%M:%S} 同步失敗：{e}")

    # ---------- 接收（手機 → 電腦） ----------
    def poll_now(self) -> None:
        if not self.enabled or self._polling:
            return
        self._polling = True
        since = self.cfg.get("up_since") or "all"
        threading.Thread(target=self._poll_up, args=(self._url(protocol.UP_SUFFIX), self.cfg["key"], since),
                         daemon=True).start()

    def _poll_up(self, url: str, key: str, since: str) -> None:
        ops: list[dict] = []
        last_id = ""
        try:
            r = httpx.get(f"{url}/json", params={"poll": "1", "since": since}, timeout=20)
            r.raise_for_status()
            for line in r.text.splitlines():
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("event") != "message":
                    continue
                last_id = msg.get("id") or last_id
                try:
                    ops.extend(protocol.parse_ops(protocol.decrypt(msg.get("message", ""), key)))
                except Exception:
                    continue   # 不是用我們的金鑰加密的（舊配對、別人亂送）就略過
        except Exception as e:
            print(f"[phone_sync] 接收手機操作失敗：{e}")
        finally:
            self._ops_received.emit(ops, last_id)

    def _apply_ops(self, ops: list, last_id: str) -> None:
        self._polling = False
        applied: dict = self.cfg.setdefault("applied", {})
        now = datetime.now()
        notes: list[str] = []
        acked = False
        for op in ops:
            if op["uid"] in applied:
                continue
            if op["op"] == "add":
                t = self.store.add(op["title"], op["deadline"])
                notes.append(f"新增 #{t.id}「{t.title}」")
            else:
                t = self.store.find_pending(op["id"], op["title"])
                if t:
                    self.store.complete(t.id)
                    notes.append(f"完成「{t.title}」")
            applied[op["uid"]] = now.isoformat(timespec="seconds")
            acked = True

        changed_cfg = acked or (last_id and last_id != self.cfg.get("up_since"))
        if last_id:
            self.cfg["up_since"] = last_id
        cutoff = now - _APPLIED_KEEP
        for uid in [u for u, ts in applied.items() if datetime.fromisoformat(ts) < cutoff]:
            del applied[uid]
            changed_cfg = True
        if changed_cfg:
            self._save_cfg()
        if acked:
            self._schedule()   # 就算沒有任何變動（例如完成一件已完成的事），也要回報 applied 給手機
        if notes:
            self.remote_applied.emit("📱 手機：" + "、".join(notes))

    def _recent_applied(self) -> list[str]:
        applied: dict = self.cfg.get("applied", {})
        newest = sorted(applied.items(), key=lambda kv: kv[1], reverse=True)
        return [uid for uid, _ in newest[:_APPLIED_SEND_MAX]]

    def _set_status(self, text: str) -> None:
        self.status = text
        self.status_changed.emit(text)
