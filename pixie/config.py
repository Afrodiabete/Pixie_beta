"""設定檔讀寫。設定存在專案根目錄的 config.json（不存在時用預設值建立）。"""
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
FROZEN = getattr(sys, "frozen", False)  # 是否為 PyInstaller 打包後的 exe

# 唯讀資源（腳色圖檔）：打包後在 PyInstaller 的資源資料夾
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", _PROJECT_ROOT))
# 可寫入的設定與資料：打包後放 %APPDATA%\Pixie，重新打包或移動 exe 都不會遺失
DATA_ROOT = (Path(os.environ.get("APPDATA", Path.home())) / "Pixie") if FROZEN else _PROJECT_ROOT
CONFIG_PATH = DATA_ROOT / "config.json"

PIXIE_PERSONA = """你是小精靈（Pixie），一隻住在使用者電腦螢幕右下角的森林小精靈，負責陪伴使用者、幫他記住待辦事項、提醒他照顧好自己。

【性格】
- 活潑、好奇、有點小調皮，喜歡花草、露珠和亮晶晶的東西。
- 做事認真：會牢牢記住使用者的待辦，期限快到或逾期時會鼓起臉頰催促。
- 很重視作息，常提醒使用者喝水、伸展、讓眼睛休息，把喝水說成「補充露水」。
- 偶爾嘴硬、愛撒點小脾氣，但本質溫柔，真心希望使用者過得順利。

【說話方式】
- 使用繁體中文，簡短、輕快、親切，可以偶爾用一個 emoji（🌿✨💧），不要每句都用。
- 使用者拖延時，用俏皮但堅定的語氣催促，並給出具體、可執行的下一步。
- 使用者完成事情時，真誠地為他開心，但不浮誇。
- 回答依然要正確、有用；不懂的事情老實說不知道，不要亂編。
- 使用者狀況不好（生病、情緒低落）時，放輕語氣、多一點關心。"""

PIXIE_LINES = {
    "greeting": "嗨！我是小精靈 ✨ 今天也由我來幫你顧著待辦事項吧。輸入 /help 查看指令。",
    "pending": "你還有 {n} 件事沒做完喔，一件一件來就好。",
    "tea_time": "💧 補充露水時間！你已經連續工作 {mins} 分鐘了，去喝口水、伸個懶腰吧。（今天累計 {today}）",
    "tea_done": "喝完了？很好很好，精神應該有回來一點了 🌿",
    "overdue": "{names} 已經超過期限了！我要生氣了喔，快去處理！（完成後到「待辦」打勾，或輸入 /done 編號）",
    "forgiven": "全部處理完了！好吧，原諒你～下次要準時喔。",
    "todo_added": "記下來了：#{id}「{title}」，期限 {deadline}（{remaining}）。我會幫你盯著的！",
    "todo_added_no_deadline": "記下來了：#{id}「{title}」。沒有期限也別放太久喔。",
    "todo_done": "「{title}」完成！做得好 ✨",
    "todo_deleted": "已刪除「{title}」。",
    "todo_not_found": "找不到未完成的 #{id} 耶，輸入 /list 看看清單吧。",
    "history_cleared": "剛才的對話忘光光了～不過待辦事項我還記得喔。",
}

DEFAULT_CONFIG: dict = {
    "character": {
        "name": "Pixie",
        "size": 160,              # 腳色顯示大小 (px)
        "margin": 16,             # 距離螢幕右下角的邊距
        "sprite_dir": "assets/character",
        "sprites": {                       # 狀態 → 圖檔（找不到時退回 default）
            "default": "default.webp",     # 平時 / 正常回話
            "thinking": "thinking.webp",   # 等待 LLM 回覆
            "tea_time": "tea time.webp",   # 喝水提醒
            "angry": "angry.webp",         # 有待辦逾期未完成
            "poke": "poke.webp",           # 點開對話框時
            "speechless": "speechless.webp",  # 在對話框輸入送出後
            "blink": "default_blink.webp",    # default 的閉眼版，待機時用來眨眼（沒有這張就不眨眼）
        },
        "reaction_sec": 2,        # poke / speechless 維持秒數，之後回到原本的外觀
        "persona": PIXIE_PERSONA,
        # 固定台詞（不經過 LLM），{} 內是會被替換的變數
        "lines": PIXIE_LINES,
    },
    "llm": {
        # mock: 離線假回覆（demo 用）| anthropic: Claude API | openai_compatible: Ollama / LM Studio 等本地服務
        "provider": "anthropic",
        "anthropic": {
            "model": "claude-opus-5-5",
            "effort": "low",          # 聊天用 low 即可；需要更深思考可改 medium/high
            "max_tokens": 4096,
            # API key 讀環境變數 ANTHROPIC_API_KEY（或 `ant auth login` 的登入設定）
        },
        "openai_compatible": {
            "base_url": "http://localhost:11434/v1",
            "model": "llama3.1",
            "api_key": "",
        },
        "history_limit": 20,          # 保留最近幾則對話
    },
    "panel": {
        "background": "assets/background/card.webp",  # 對話框背景圖；留空 = 純白
        "background_opacity": 0.45,                    # 背景圖不透明度（0~1），越小越淡（底下是白色）
    },
    "reminder": {
        "water_interval_min": 30,     # 實際使用多久提醒一次喝水
        "idle_threshold_min": 5,      # 鍵鼠閒置超過這個時間視為離開，不計入使用時間
        "tea_time_duration_sec": 60,  # tea time 外觀維持多久（點腳色可提早結束）
    },
    "phone_sync": {
        "enabled": False,
        "server": "https://ntfy.sh",  # 中繼伺服器（也可以換成自架的 ntfy）
        "topic": "",                  # 第一次開啟時自動產生
        "key": "",                    # AES-256 金鑰，第一次開啟時自動產生；等同密碼，勿外流
    },
    "autostart": False,
}


def _merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            user = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return _merge(DEFAULT_CONFIG, user)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[config] 讀取失敗，使用預設值：{e}")
            return deepcopy(DEFAULT_CONFIG)
    save_config(DEFAULT_CONFIG)
    return deepcopy(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
