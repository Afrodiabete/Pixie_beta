"""命令列測試 Claude 連線（不開 UI）。

    python tools/test_claude.py
    python tools/test_claude.py "我今天還有什麼事沒做？"
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from pixie.config import load_config  # noqa: E402
from pixie.llm import create_provider  # noqa: E402
from pixie.llm.context import build_llm_context  # noqa: E402
from pixie.todo.store import Todo  # noqa: E402


def main() -> int:
    cfg = load_config()
    llm_cfg = {**cfg["llm"], "provider": "anthropic"}
    provider, err = create_provider(llm_cfg, cfg["character"]["persona"])
    if err:
        print(f"❌ {err}")
        return 1

    question = sys.argv[1] if len(sys.argv) > 1 else "用一句話自我介紹"
    now = datetime.now()
    fake_todos = [  # 測試用假資料，不會寫入 data/todos.json
        Todo(1, "交報告", (now + timedelta(hours=1)).isoformat(timespec="minutes")),
        Todo(2, "買牛奶"),
    ]
    context = build_llm_context(fake_todos, usage_seconds=5400, now=now)
    print(f"模型：{provider.model}　effort：{provider.config.get('effort', 'low')}")
    print(f"你：{question}\n{cfg['character']['name']}：", end="", flush=True)

    start = time.perf_counter()
    first = None
    for chunk in provider.stream_chat([{"role": "user", "content": question}], context):
        if first is None:
            first = time.perf_counter() - start
        print(chunk, end="", flush=True)
    total = time.perf_counter() - start
    print(f"\n\n⏱ 首字 {first or 0:.1f}s，總共 {total:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
