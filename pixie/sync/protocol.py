"""電腦 ↔ 手機的同步格式（Android 端 Crypto.kt / Snapshot.kt 要跟這裡一致）。

傳輸：電腦 POST 到 {server}/{topic}（ntfy），手機 GET {server}/{topic}/json?poll=1 取最新一則。
內容：base64( nonce[12] + AES-256-GCM( zlib(JSON), aad="pixie-v1" ) )
電腦 → 手機（topic）：
    {"v": 1, "sent_at": "2026-11-05T10:00:00+08:00",
     "todos": [{"id": 1, "title": "交報告", "deadline": "2026-11-05T18:00:00+08:00" | null}],
     "applied": ["<op uid>", ...]}        # 最近處理過的手機操作，手機據此把它們從待送清單移除
只送未完成的待辦；手機收到後，不在清單裡的就視為已完成/刪除。
手機 → 電腦（topic + "-up"），同樣加密：
    {"v": 1, "kind": "ops", "sent_at": "...",
     "ops": [{"uid": "a1b2", "op": "add", "title": "買牛奶", "deadline": "..." | null},
             {"uid": "c3d4", "op": "done", "id": 2, "title": "交報告"}]}
手機每次送出所有還沒被確認的操作，電腦用 uid 去重。done 要編號與名稱都對得上才會執行。
配對連結（做成 QR code）：
    pixie://pair?server=<url>&topic=<topic>&key=<base64url 32 bytes, 無 padding>
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import zlib
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..todo.store import Todo

VERSION = 1
AAD = b"pixie-v1"
MAX_MESSAGE_CHARS = 4000   # ntfy.sh 單則訊息上限 4096 bytes，超過會變成附件
UP_SUFFIX = "-up"          # 手機 → 電腦用的 topic


def new_topic() -> str:
    return "pixie-" + secrets.token_urlsafe(24).replace("_", "x").replace("-", "y")


def new_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()


def decode_key(key: str) -> bytes:
    raw = base64.urlsafe_b64decode(key + "=" * (-len(key) % 4))
    if len(raw) != 32:
        raise ValueError("金鑰長度錯誤")
    return raw


def pairing_uri(server: str, topic: str, key: str) -> str:
    return "pixie://pair?" + urlencode({"server": server, "topic": topic, "key": key})


def parse_pairing_uri(uri: str) -> tuple[str, str, str]:
    q = parse_qs(urlparse(uri).query)
    return q["server"][0], q["topic"][0], q["key"][0]


def _todo_json(t: Todo) -> dict:
    d = t.deadline_dt
    return {"id": t.id, "title": t.title,
            "deadline": d.astimezone().isoformat(timespec="seconds") if d else None}


def build_snapshot(pending: list[Todo], now: datetime | None = None, applied: list[str] | None = None) -> dict:
    now = (now or datetime.now()).astimezone()
    return {"v": VERSION, "sent_at": now.isoformat(timespec="seconds"),
            "todos": [_todo_json(t) for t in pending], "applied": list(applied or [])}


def parse_ops(message: dict) -> list[dict]:
    """解析手機送來的操作，格式不對的直接略過。回傳 [{"uid", "op", "title", "deadline"|"id"}]。"""
    if message.get("kind") != "ops":
        return []
    out = []
    for o in message.get("ops", []):
        try:
            uid, op, title = str(o["uid"]), o["op"], str(o["title"]).strip()
            if not uid or not title:
                continue
            if op == "add":
                d = o.get("deadline")
                deadline = datetime.fromisoformat(d).astimezone().replace(tzinfo=None) if d else None
                out.append({"uid": uid, "op": "add", "title": title, "deadline": deadline})
            elif op == "done":
                out.append({"uid": uid, "op": "done", "id": int(o["id"]), "title": title})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def encrypt(snapshot: dict, key: str) -> str:
    data = zlib.compress(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode(), 9)
    nonce = os.urandom(12)
    return base64.b64encode(nonce + AESGCM(decode_key(key)).encrypt(nonce, data, AAD)).decode()


def decrypt(payload: str, key: str) -> dict:
    raw = base64.b64decode(payload)
    data = AESGCM(decode_key(key)).decrypt(raw[:12], raw[12:], AAD)
    return json.loads(zlib.decompress(data))


def encrypt_fitting(pending: list[Todo], key: str, applied: list[str] | None = None) -> tuple[str, int]:
    """加密；太大時從期限最遠的開始捨棄。回傳 (payload, 實際送出的件數)。"""
    items = list(pending)
    while True:
        payload = encrypt(build_snapshot(items, applied=applied), key)
        if len(payload) <= MAX_MESSAGE_CHARS or not items:
            return payload, len(items)
        items = items[: max(0, len(items) - max(1, len(items) // 10))]
