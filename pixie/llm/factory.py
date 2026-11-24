from __future__ import annotations

from .base import LLMProvider
from .mock_provider import MockProvider


def create_provider(llm_cfg: dict, persona: str) -> tuple[LLMProvider, str]:
    """回傳 (provider, 錯誤訊息)。設定的 provider 載入失敗時退回 mock，並附上原因。"""
    name = llm_cfg.get("provider", "mock")
    try:
        if name == "anthropic":
            from .anthropic_provider import AnthropicProvider
            return AnthropicProvider(llm_cfg.get("anthropic", {}), persona), ""
        if name == "openai_compatible":
            from .openai_compatible_provider import OpenAICompatibleProvider
            return OpenAICompatibleProvider(llm_cfg.get("openai_compatible", {}), persona), ""
    except ImportError as e:
        return MockProvider({}, persona), f"無法載入 {name}：缺少套件（{e.name}），請執行 pip install -r requirements.txt"
    except Exception as e:  # 例如沒有設定 API key
        return MockProvider({}, persona), f"無法啟用 {name}：{e}"
    return MockProvider({}, persona), ""
