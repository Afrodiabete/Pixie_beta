"""把 LLM 呼叫放到背景執行緒，避免 UI 卡住。透過 Qt signal 把文字片段送回主執行緒。"""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from .base import LLMProvider, Message


class ChatWorker(QThread):
    chunk = Signal(str)
    finished_text = Signal(str)

    def __init__(self, provider: LLMProvider, messages: list[Message], context: str = "",
                 parent: QObject | None = None):
        super().__init__(parent)
        self.provider = provider
        self.messages = list(messages)
        self.context = context

    def run(self) -> None:
        parts: list[str] = []
        try:
            for piece in self.provider.stream_chat(self.messages, self.context):
                parts.append(piece)
                self.chunk.emit(piece)
        except Exception as e:  # 背景執行緒的例外不能讓整個程式掛掉
            msg = f"\n（出錯了：{e}）"
            parts.append(msg)
            self.chunk.emit(msg)
        self.finished_text.emit("".join(parts))
