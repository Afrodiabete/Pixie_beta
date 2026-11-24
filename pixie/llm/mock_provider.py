"""離線假回覆，用來測試 UI 不需要 API key。"""
from __future__ import annotations

import random
import time
from typing import Iterator

from .base import LLMProvider, Message

_REPLIES = [
    "我在這裡喔～你剛剛說的是「{q}」對吧？等接上真正的 LLM 我就能好好回答了！",
    "嗯哼，「{q}」……這題我先記下來。（目前是 demo 模式）",
    "收到！不過我現在還只是 mock 版本，到 config.json 把 provider 改成 anthropic 就能真的聊天囉。",
]


class MockProvider(LLMProvider):
    name = "mock"

    def stream_chat(self, messages: list[Message], context: str = "") -> Iterator[str]:
        q = messages[-1]["content"][:20] if messages else ""
        text = random.choice(_REPLIES).format(q=q)
        time.sleep(0.6)  # 模擬思考
        for ch in text:
            time.sleep(0.03)
            yield ch
