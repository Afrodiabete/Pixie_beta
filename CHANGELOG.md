# Changelog

本專案的所有重要變更都會記錄在這個檔案。

格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，版本號遵循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

## Unreleased

### 變更
- 專案改名為 Pixie（小精靈）：全新原創腳色、個性設定與美術（由 `tools/draw_art.py` 程式繪製），Python 套件改為 `pixie`、Android 套件改為 `com.pixie.pet`、同步協定改為 `pixie-v1`（與舊版不相容，需重新配對）

### 新增
- 對話框背景改用 `assets/background/card.webp`，疊在白底上、不透明度 45%（可用 `panel.background`、`panel.background_opacity` 調整，留空恢復純白）
- 待機（default）時會眨眼：每 2.5～6 秒換上閉眼版 `default_blink.webp` 約 0.13 秒，偶爾連眨兩下

### 變更
- 對話框所有文字顏色加深（內文、你說的話、腳色名字、分頁、待辦清單），疊在背景圖上比較好讀

## 0.1.1 - 2026-11-06

桌面腳色新增兩個表情反應。

### 新增
- 腳色外觀 `poke`：左鍵點開對話框時短暫顯示
- 腳色外觀 `speechless`：在對話框送出訊息（聊天或指令）後短暫顯示；等待 LLM 回覆時，之後接著顯示 `thinking`
- 設定 `character.reaction_sec`：上述兩個反應的維持秒數（預設 2 秒）
- 外觀優先順序更新為：poke / speechless > thinking > tea_time > angry > default

### 變更
- Android app 只更新版本號（0.1.1），功能與 0.1.0 相同

## 0.1.0 - 2026-11-06

手機也能管理待辦了：新增與完成會同步回電腦。

### 新增

#### 手機 app
- 「＋ 新增」按鈕：輸入事項名稱，用日期 / 時間選擇器設定期限（可省略）
- 點一下事項 → 確認後標成完成，手機上立刻停止該事項的提醒
- 電腦確認前先顯示結果：新增的標示「等待電腦同步」，完成的先從清單隱藏
- 電腦沒開時，操作會留在手機上，電腦上線後自動重送（最多保留 7 天）

#### 雙向同步
- 手機的操作以同一把金鑰 AES-256-GCM 加密，送到 ntfy 的 `<topic>-up`；不需要重新配對
- 電腦每 30 秒接收一次並套用，用操作 uid 去重，同一則訊息收到多次也不會重複新增
- 電腦推送的清單新增 `applied` 欄位，回報已處理的手機操作，手機據此確認
- 套用手機的操作時，聊天框會顯示「📱 手機：新增 #2「買牛奶」」之類的訊息

### 變更
- 待辦編號改為重複使用：新增時取未完成事項中最小的空號（例如 #2 完成後，下一個新增的就是 #2）
- 手機上「完成」要編號與名稱都對得上才會執行，避免完成到重用同一編號的新事項
- 手機提醒的識別改為包含事項名稱，編號被重用時新事項仍會正常提醒

### 注意
- 更新手機 app 後，目前已逾期的事項可能會再跳一次通知（提醒識別方式改變）
- 電腦端需更新到 0.1.0 才會接收手機的操作；舊版電腦只會照常推送清單

## 0.0.0 - 2026-11-05

第一個版本。

### 新增

#### 桌面腳色
- 常駐螢幕右下角的透明置頂腳色視窗，可拖曳移動，右鍵選單可回到右下角
- 腳色外觀狀態：`default`、`thinking`（等待回覆）、`tea_time`（喝水提醒）、`angry`（待辦逾期），優先順序 thinking > tea_time > angry > default
- 系統匣圖示與右鍵選單：今日使用時間、清除記憶、測試喝水提醒、開機自啟、隱藏、離開
- 只允許同時執行一個實體，重複開啟會提示

#### 聊天
- 點腳色開關對話框（Enter 送出、Esc 收起），回覆以串流方式顯示
- LLM provider：`mock`（離線假回覆）、`anthropic`（Claude，預設 `claude-opus-5-5`）、`openai_compatible`（Ollama / LM Studio）
- 可在 `config.json` 自訂腳色名字、個性（system prompt）與固定台詞

#### 待辦事項
- 聊天指令 `/add`、`/list`、`/done`、`/del`、`/help`，以及 `+事項`、`新增`、`完成`、`刪除` 等中文寫法
- 期限文字解析：`18:00`、`明天 18:00`、`後天`、`11/5 9:30`、`2026-12-01 10:00`、`30分鐘`、`2h`，中文可不加空格
- 面板「待辦」分頁：直接新增、打勾完成、右鍵刪除
- 有事項逾期時腳色切換成 angry，全部完成或刪除後恢復

#### 作息
- 使用時間統計，鍵鼠閒置超過門檻不計入
- 每實際使用 30 分鐘跳出喝水提醒（tea time），點腳色表示「喝了」
- Windows 開機自啟（HKCU Run 登錄檔）

#### 手機同步（Android）
- 桌面未完成待辦以 AES-256-GCM 加密後，透過 ntfy.sh 隨機 topic 同步到手機（變動後 2 秒、每 6 小時重送）
- Kotlin Android app：掃描 QR code 配對、每 15 分鐘背景同步、在期限時以精準鬧鐘跳通知
- `android/tools/build_apk.ps1` 編譯 APK，`setup_toolchain.sh` 安裝 JDK 17 / Android SDK / Gradle

#### 打包
- `tools/build_exe.py` 以 PyInstaller 打包成 `dist/Pixie/Pixie.exe`
- 打包後設定與資料存在 `%APPDATA%\Pixie\`，右鍵選單可直接開啟該資料夾
- `Pixie.exe --self-test`：不開 UI 檢查圖檔解碼與 LLM 連線，結果寫入 `self_test.txt`
