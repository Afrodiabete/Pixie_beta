# Pixie 小精靈 桌面腳色（v0.1.1）

常駐在螢幕右下角的森林小精靈，點一下就能跟 LLM 聊天，幫你記待辦、提醒喝水。

腳色與美術皆為原創，由 [`tools/draw_art.py`](tools/draw_art.py) 以程式繪製，執行 `python tools/draw_art.py` 即可重新產生。

## 執行
```bash
pip install -r requirements.txt
python main.py          # 開發時用（看得到 log）
pythonw main.py         # 不跳主控台視窗
```

## 打包成 exe
```bash
pip install pyinstaller
python tools/build_exe.py
```
- 輸出在 `dist/Pixie/`，執行 `Pixie.exe`。**整個資料夾要一起帶走**（exe 依賴旁邊的 `_internal/`）
- 打包後的設定與資料存在 `%APPDATA%\Pixie\`（config.json、data/），重新打包或搬移 exe 都不會遺失；右鍵選單「開啟設定與資料資料夾」可以直接打開
- 用 `python main.py` 開發時，仍讀寫專案資料夾裡的 config.json 與 data/
- API key 一樣讀 Windows 環境變數 `ANTHROPIC_API_KEY`
- 檢查打包結果：`Pixie.exe --self-test`，結果寫在 `%APPDATA%\Pixie\self_test.txt`
- 同時只能開一個；重複開啟會提示已在執行

## 操作
- **左鍵點腳色**：開 / 關對話框（Enter 送出、Esc 收起）
- **拖曳腳色**：移動位置
- **右鍵腳色 / 系統匣圖示**：選單（今日使用時間、回到右下角、清除記憶、測試喝水提醒、開機自啟、隱藏、離開）
- **喝水提醒**：每實際使用 30 分鐘，腳色換成 tea time 並跳出提醒；點一下腳色＝「喝了」

## 待辦事項
在聊天框輸入指令（其他文字會當成一般聊天交給 LLM）：

| 指令 | 說明 |
|---|---|
| `/add 事項 期限`（或 `+事項`、`新增 事項`） | 新增，期限可省略 |
| `/list`（或 `待辦`） | 列出未完成事項 |
| `/done 編號`（或 `完成 編號`） | 完成 |
| `/del 編號`（或 `刪除 編號`） | 刪除 |
| `/help` | 指令說明 |

期限寫在最後，可寫：`18:00`（已過則算明天）、`明天 18:00`、`後天`、`11/5 9:30`、`2026-12-01 10:00`、`30分鐘`、`2h`。
只寫日期沒寫時間 → 當天 23:59。中文可不加空格：`/add 交報告明天18:00`。

也可以在面板的「待辦」分頁直接新增、打勾完成、右鍵刪除。

**編號**：只在未完成的事項之間不重複，新增時取最小的空號。例如 #2 完成後再新增，新事項就是 #2。

**逾期**：只要有任何事項過了期限還沒完成，腳色就切換成 angry，直到全部完成或刪除。

**外觀優先順序**：poke / speechless（短暫反應）> thinking（等回覆）> tea_time（喝水）> angry（有逾期）> default

點開對話框時會短暫顯示 poke，在對話框送出訊息後短暫顯示 speechless（預設 2 秒），之後回到原本的外觀。

## 手機同步（Android）

桌面上的未完成待辦會加密後同步到手機，手機在通知列顯示逾期提醒。
手機上也可以按「＋ 新增」新增待辦（可選期限），或點一下事項標成完成，會同步回電腦。

1. 編譯 APK：`powershell -ExecutionPolicy Bypass -File android\tools\build_apk.ps1` → `dist\Pixie-android.apk`
   （第一次需先跑 `android/tools/setup_toolchain.sh` 安裝 JDK 17 / Android SDK / Gradle）
2. 把 APK 傳到手機安裝（需允許「安裝不明應用程式」），開啟後允許通知。
3. 桌面右鍵選單 →「手機同步…」→ 勾選同步 → 用 app 的「掃描配對 QR code」掃描。

原理：桌面把待辦 JSON 以 AES-256-GCM 加密後發到 ntfy.sh 的隨機 topic（變動後 2 秒、每 6 小時重送）；
手機每 15 分鐘背景抓取，並在每個期限用精準鬧鐘跳通知。金鑰只存在電腦與手機，QR code 等同金鑰。
手機上的新增 / 完成同樣加密後送到 `<topic>-up`，電腦每 30 秒收一次並套用（電腦沒開時，手機會在電腦上線後重送，最多保留 7 天）；
新增的事項要等電腦收到後才有編號。
程式碼：`pixie/sync/`（桌面）、`android/`（Kotlin app）。

## 設定 `config.json`（第一次執行自動產生）

`config.json` 不進 git（啟用手機同步後會存入金鑰）。可參考 `config_example.json`，或直接執行一次讓程式自動產生預設值。

| 欄位 | 說明 |
|---|---|
| `character.name` / `persona` | 腳色名字與個性（system prompt） |
| `character.size` | 腳色大小 px |
| `character.sprites` | 狀態對應的圖檔：`default`（平時/回話）、`thinking`（等待回覆）、`tea_time`（喝水提醒）、`angry`（待辦逾期）、`poke`（點開對話框）、`speechless`（輸入送出後）、`blink`（default 的閉眼版，待機時眨眼用） |
| `panel.background` / `background_opacity` | 對話框背景圖（預設 `assets/background/card.webp`，留空 = 純白）與不透明度（預設 0.45，越小越淡，底下是白色） |
| `character.reaction_sec` | `poke` / `speechless` 維持秒數（預設 2），之後回到原本的外觀 |
| `reminder.water_interval_min` | 實際使用電腦多久提醒喝水（預設 30） |
| `reminder.idle_threshold_min` | 鍵鼠閒置超過幾分鐘算離開，不計入使用時間（預設 5） |
| `reminder.tea_time_duration_sec` | tea time 外觀維持秒數；提醒期間點腳色可提早結束 |
| `llm.provider` | `mock`（離線假回覆）、`anthropic`（Claude）、`openai_compatible`（Ollama / LM Studio） |
| `llm.anthropic.model` / `effort` | 預設 `claude-opus-5-5`、`low`；API key 讀環境變數 `ANTHROPIC_API_KEY` |
| `autostart` | 開機自啟（寫入 HKCU Run 登錄檔，選單裡也能切換） |

## 架構
```
main.py                     進入點
pixie/
  app.py                    組裝各模組、選單、系統匣、對話流程
  config.py                 設定讀寫
  ui/character.py           透明置頂腳色視窗：狀態機(idle/think/talk)、動畫、拖曳
  ui/chat_panel.py          對話泡泡 + 輸入框，跟隨腳色位置
  llm/base.py               LLMProvider 介面（stream_chat → 逐段 yield 文字）
  llm/*_provider.py         各家模型實作
  llm/factory.py            依設定建立 provider
  llm/worker.py             QThread 背景呼叫，signal 回傳串流片段
  system/autostart.py       Windows 開機自啟
  system/usage_tracker.py   使用時間統計（排除閒置）+ 喝水提醒
  todo/store.py             待辦資料（新增/完成/刪除/逾期查詢）
  todo/parser.py            聊天指令與期限文字解析
  ui/todo_view.py           「待辦」分頁
assets/character/           腳色圖檔（default_blink.webp 是眨眼用的閉眼版）
tools/draw_art.py           重新產生所有美術素材（腳色、背景、手機 app 圖示）
assets/background/          對話框背景圖
data/usage.json             每日使用時間紀錄（自動產生）
data/todos.json             待辦事項（自動產生）
```

### 之後擴充的位置
- **新模型** → `llm/` 加一個 provider，在 `factory.py` 註冊
- **工具呼叫 / 讀取電腦狀態**（提醒、開程式…）→ 擴充 `LLMProvider`，加 `tools/` 模組
- **長期記憶** → 在 `app.py` 的 `history` 前後接記憶存取
- **主動說話**（定時、事件觸發）→ `app.py` 加 QTimer 呼叫 `panel.say()`
- **更多動畫狀態** → `ui/character.py` 的 `State` 加狀態並放對應圖檔
- **打包成 exe** → PyInstaller（`autostart.py` 已處理 frozen 路徑）
