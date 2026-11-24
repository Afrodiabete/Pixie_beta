"""OpenAI 相容的 /chat/completions 端點（Ollama、LM Studio 等本地模型）。用 httpx 串流 SSE。"""
from __future__ import annotations

import json
from typing import Iterator

import httpx

from .base import LLMProvider, Message


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def stream_chat(self, messages: list[Message], context: str = "") -> Iterator[str]:
        cfg = self.config
        url = cfg["base_url"].rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {cfg['api_key']}"} if cfg.get("api_key") else {}
        body = {
            "model": cfg["model"],
            "stream": True,
            "messages": [{"role": "system", "content": self.system_prompt(context)}, *messages],
        }
        try:
            with httpx.stream("POST", url, json=body, headers=headers, timeout=120) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta
        except httpx.HTTPError as e:
            yield f"本地模型連線失敗：{e}"
