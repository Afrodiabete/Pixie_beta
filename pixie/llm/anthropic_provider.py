"""Claude (Anthropic 官方 SDK)。需要 `pip install anthropic` 與 ANTHROPIC_API_KEY。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from .base import LLMProvider, Message


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, config: dict, persona: str):
        super().__init__(config, persona)
        import anthropic  # 延遲匯入：沒裝也不影響 mock 模式

        self._anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model = config.get("model", "claude-opus-5-5")
        # SDK 要到送出請求才會發現沒有憑證，這裡先檢查，讓 factory 能退回 mock 並顯示原因
        has_profile = bool(os.environ.get("ANTHROPIC_PROFILE")) or \
            (Path.home() / ".config" / "anthropic").exists()
        if not (self.client.api_key or self.client.auth_token or has_profile):
            raise RuntimeError("找不到 Claude API key，請設定環境變數 ANTHROPIC_API_KEY 後重新啟動")

    def stream_chat(self, messages: list[Message], context: str = "") -> Iterator[str]:
        a = self._anthropic
        try:
            with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=self.config.get("max_tokens", 4096),
                system=self.system_prompt(context),
                messages=messages,
                output_config={"effort": self.config.get("effort", "low")},
                # 安全分類器拒答時，伺服器自動改用合適的備援模型重答
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                for text in stream.text_stream:
                    yield text
                final = stream.get_final_message()
                if final.stop_reason == "refusal":
                    yield "\n（這個問題我沒辦法回答…）"
                elif final.stop_reason == "max_tokens":
                    yield "\n（話太長被截斷了…）"
        except a.AuthenticationError:
            yield "API key 無效，請檢查 ANTHROPIC_API_KEY。"
        except a.PermissionDeniedError as e:
            yield f"這個 API key 沒有使用 {self.model} 的權限：{e.message}"
        except a.NotFoundError:
            yield f"找不到模型 {self.model}，請檢查 config.json 的 llm.anthropic.model。"
        except a.RateLimitError:
            yield "請求太頻繁或額度用完了，稍等一下再問我～"
        except a.BadRequestError as e:
            yield f"請求格式有誤：{e.message}"
        except a.APIStatusError as e:
            yield f"Claude API 錯誤 ({e.status_code})：{e.message}"
        except a.APIConnectionError:
            yield "連不上 Claude API，檢查一下網路？"
