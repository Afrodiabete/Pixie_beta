"""LLM 抽象層：所有 provider 都實作 stream_chat，逐段吐出文字。
之後要加新模型 / 工具呼叫 / 記憶，只需新增 provider 或在這層擴充。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, TypedDict


class Message(TypedDict):
    role: str      # "user" | "assistant"
    content: str


class LLMProvider(ABC):
    name: str = "base"

    def __init__(self, config: dict, persona: str):
        self.config = config
        self.persona = persona

    def system_prompt(self, context: str) -> str:
        """固定的 persona 在前、每次變動的狀態（時間、待辦）在後。"""
        return f"{self.persona}\n\n{context}" if context else self.persona

    @abstractmethod
    def stream_chat(self, messages: list[Message], context: str = "") -> Iterator[str]:
        """依序 yield 回覆文字片段。在背景執行緒呼叫，可以阻塞。
        context：當下狀態（時間、待辦清單等），會附加在 system prompt 後面。"""
        raise NotImplementedError
