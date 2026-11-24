# Pixie — Desktop Fairy Companion (v0.1.1)

A little forest fairy that lives in the bottom-right corner of your screen. Click her to chat with an LLM; she also keeps track of your todos and reminds you to drink water.

The character and all artwork are original, drawn in code by [`tools/draw_art.py`](tools/draw_art.py). Run `python tools/draw_art.py` to regenerate them.

> The app's UI, default persona and fixed lines are in Traditional Chinese. UI labels below are shown as English with the original Chinese in brackets, e.g. Phone sync (「手機同步…」).

## Running
```bash
pip install -r requirements.txt
python main.py          # for development (shows logs)
pythonw main.py         # no console window
```

## Building an exe
```bash
pip install pyinstaller
python tools/build_exe.py
```
- Output goes to `dist/Pixie/`; run `Pixie.exe`. **Keep the whole folder together** (the exe depends on the `_internal/` folder next to it).
- The packaged app stores its config and data in `%APPDATA%\Pixie\` (config.json, data/), so nothing is lost when you rebuild or move the exe. The right-click menu has an entry to open this folder (「開啟設定與資料資料夾」).
- When running with `python main.py`, config.json and data/ in the project folder are used instead.
- The API key is read from the Windows environment variable `ANTHROPIC_API_KEY`.
- To check a build: `Pixie.exe --self-test`; results are written to `%APPDATA%\Pixie\self_test.txt`.
- Only one instance can run at a time; launching a second one shows a notice.

## Controls
- **Left-click the character**: open / close the chat panel (Enter sends, Esc closes)
- **Drag the character**: move her
- **Right-click the character / tray icon**: menu (today's usage time, return to corner, clear memory, test water reminder, start with Windows, hide, quit)
- **Water reminder**: after every 30 minutes of actual computer use, the character switches to the tea time sprite and shows a reminder; click her to mark it as done

## Todos
Type commands in the chat box (anything else is sent to the LLM as normal chat):

| Command | Description |
|---|---|
| `/add task deadline` (or `+task`, `新增 task`) | Add a todo; deadline is optional |
| `/list` (or `待辦`) | List open todos |
| `/done N` (or `完成 N`) | Mark #N as done |
| `/del N` (or `刪除 N`) | Delete #N |
| `/help` | Show command help |

Put the deadline at the end. Accepted formats: `18:00` (tomorrow if already past), `明天 18:00` (tomorrow), `後天` (day after tomorrow), `11/5 9:30`, `2026-12-01 10:00`, `30分鐘` (30 minutes), `2h`.
A date without a time means 23:59 that day. Chinese text needs no space before the deadline: `/add 交報告明天18:00`.

You can also add, check off and (right-click) delete todos in the panel's Todo tab (「待辦」).

**Numbering**: numbers are unique only among open todos; a new todo takes the smallest free number. E.g. after #2 is done, the next new todo becomes #2.

**Overdue**: while any todo is past its deadline, the character switches to the angry sprite until all of them are done or deleted.

**Sprite priority**: poke / speechless (brief reactions) > thinking (waiting for a reply) > tea_time (water) > angry (overdue) > default

Opening the chat panel briefly shows poke; sending a message briefly shows speechless (2 seconds by default), then the character returns to her previous look.

## Phone sync (Android)

Open todos on the desktop are encrypted and synced to your phone, which shows overdue notifications.
On the phone you can also tap "+ Add" (「＋ 新增」) to add a todo (deadline optional), or tap a todo to mark it done; changes sync back to the desktop.

1. Build the APK: `powershell -ExecutionPolicy Bypass -File android\tools\build_apk.ps1` → `dist\Pixie-android.apk`
   (first time only: run `android/tools/setup_toolchain.sh` to install JDK 17 / Android SDK / Gradle)
2. Copy the APK to your phone and install it (allow "install unknown apps"), then open it and allow notifications.
3. On the desktop, right-click → Phone sync (「手機同步…」) → enable sync → scan the QR code with the app's "Scan pairing QR code" button.

How it works: the desktop encrypts the todo JSON with AES-256-GCM and posts it to a random ntfy.sh topic (2 seconds after any change, and re-sent every 6 hours).
The phone polls in the background every 15 minutes and uses exact alarms to notify at each deadline. The key exists only on the desktop and the phone — the QR code *is* the key.
Adds / completions from the phone are likewise encrypted and sent to `<topic>-up`; the desktop polls it every 30 seconds and applies them (if the desktop is off, the phone re-sends once it's back online, for up to 7 days).
Todos added on the phone get their number once the desktop receives them.
Code: `pixie/sync/` (desktop), `android/` (Kotlin app).

## Configuration: `config.json` (created on first run)

`config.json` is not tracked by git (it stores the sync key once phone sync is enabled). See `config_example.json`, or just run the app once to generate defaults.

| Field | Description |
|---|---|
| `character.name` / `persona` | Character name and personality (system prompt) |
| `character.size` | Character size in px |
| `character.sprites` | Image per state: `default` (idle / replying), `thinking` (waiting for reply), `tea_time` (water reminder), `angry` (overdue todos), `poke` (chat opened), `speechless` (message sent), `blink` (eyes-closed version of default, used for idle blinking) |
| `panel.background` / `background_opacity` | Chat panel background image (default `assets/background/card.webp`; empty = plain white) and its opacity (default 0.45; lower is fainter, over white) |
| `character.reaction_sec` | How long `poke` / `speechless` last (default 2 seconds) |
| `reminder.water_interval_min` | Minutes of actual use between water reminders (default 30) |
| `reminder.idle_threshold_min` | Minutes of keyboard/mouse inactivity counted as away and excluded from usage time (default 5) |
| `reminder.tea_time_duration_sec` | How long the tea time sprite stays; clicking the character ends it early |
| `llm.provider` | `mock` (offline fake replies), `anthropic` (Claude), `openai_compatible` (Ollama / LM Studio) |
| `llm.anthropic.model` / `effort` | Defaults `claude-opus-5-5`, `low`; API key from the `ANTHROPIC_API_KEY` environment variable |
| `autostart` | Start with Windows (writes the HKCU Run registry key; also toggleable from the menu) |

## Architecture
```
main.py                     Entry point
pixie/
  app.py                    Wires modules together: menu, tray, chat flow
  config.py                 Config load / save
  ui/character.py           Transparent always-on-top character window: state machine (idle/think/talk), animation, dragging
  ui/chat_panel.py          Chat bubbles + input box, follows the character
  llm/base.py               LLMProvider interface (stream_chat → yields text chunks)
  llm/*_provider.py         Provider implementations
  llm/factory.py            Builds a provider from config
  llm/worker.py             Background QThread; emits streamed chunks via signals
  system/autostart.py       Start with Windows
  system/usage_tracker.py   Usage time tracking (excluding idle) + water reminder
  todo/store.py             Todo data (add / done / delete / overdue queries)
  todo/parser.py            Chat command and deadline text parsing
  ui/todo_view.py           Todo tab
assets/character/           Character sprites (default_blink.webp is the eyes-closed frame for blinking)
assets/background/          Chat panel background
tools/draw_art.py           Regenerates all artwork (character, background, Android app icons)
data/usage.json             Daily usage log (auto-generated)
data/todos.json             Todos (auto-generated)
```

### Where to extend
- **New model** → add a provider under `llm/` and register it in `factory.py`
- **Tool use / reading system state** (reminders, launching apps, …) → extend `LLMProvider` and add a `tools/` module
- **Long-term memory** → hook memory read/write around `history` in `app.py`
- **Proactive messages** (timers, events) → add a QTimer in `app.py` that calls `panel.say()`
- **More animation states** → add a state to `State` in `ui/character.py` and provide its sprite
- **Packaging** → PyInstaller (`autostart.py` already handles frozen paths)
