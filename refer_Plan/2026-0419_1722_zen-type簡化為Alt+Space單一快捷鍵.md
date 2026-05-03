# zen-type：簡化為 Alt+Space 單一快捷鍵 + 修飾鍵釋放修正

## Context（本次迭代要解決的問題）

先前的 hotkey 演化歷程與目前狀況：

| 組合 | 結果 |
|---|---|
| `Right Alt` 單鍵 | 在記事本會開「視窗系統選單」失效 |
| `Left Alt + Space` | 同樣會被 Windows 攔走開選單 |
| `Left Ctrl + Left Shift + *` | **Ctrl+Shift 是中文 IME 切換鍵**，低階 hook 與 IME 打架 → 閃爍、中文打不出來 |
| `Left Ctrl + Left Shift + Numpad+` | 同上，IME 衝突 |

使用者參考影片（三師爸 Claude code desktop 教學）指出：**Alt+Space 其實可用，關鍵是在貼上前後強制釋放修飾鍵**，避免 pyautogui 的 `Ctrl+V` 被系統解釋成 `Alt+Ctrl+V`（造成貼不出來/系統卡鍵）。

使用者決定：
1. 只保留 **Dictate** 一個模式，快捷鍵用 **`alt+space`**
2. **Transform / Ask 暫時不用**，從 UI 隱藏、不綁定 hotkey
3. Injector 要實作「貼上前後強制釋放 Alt / Ctrl / Shift / Space」的修正

---

## 需要修改的檔案與內容

### 1. `src/zen_type/core/injector.py`（核心修正）

目前 `inject()` 流程：
```
copy → sleep 0.1s → pyautogui.hotkey("ctrl","v")
```

問題：使用者剛放開 Alt+Space，Alt 可能還在彈起過程中；這時 pyautogui 送 Ctrl+V，Windows 可能把它解釋為 `Alt+Ctrl+V` → 貼不上、鍵盤卡鍵。

**新流程**（參考影片建議）：
```
1. copy 到剪貼簿
2. sleep 0.15s（等 hotkey 的 key-up 完全送完）
3. 使用 keyboard.release('alt')、('left alt')、('right alt')、
                      ('ctrl')、('left ctrl')、('right ctrl')、
                      ('shift')、('left shift')、('right shift')、
                      ('space')
   — 全部強制釋放，即使沒按也不會錯
4. sleep 0.05s
5. pyautogui.hotkey("ctrl","v")
6. sleep 0.1s
7. 再次強制釋放上述全部修飾鍵（防殘留）
8. restore 原剪貼簿內容
```

`keyboard.release(key)` 在鍵沒按下時是 no-op，安全。

### 2. `src/zen_type/config/settings.py`

`DEFAULT_CONFIG["hotkeys"]` 改為：
```python
"hotkeys": {
    "dictate":   "alt+space",
    "transform": "",           # 空字串 = 未啟用
    "ask":       "",
},
```

`DEFAULT_CONFIG["modesEnabled"]` 改為：
```python
"modesEnabled": {
    "dictate":   True,
    "transform": False,
    "ask":       False,
},
```

### 3. `src/zen_type/app.py`

`_bind_hotkeys()` 裡對空字串 hotkey 加 skip：
```python
for name, key in hotkey_map.items():
    if not modes_enabled.get(name, True):
        continue
    if not key or not key.strip():   # ← 新增
        logger.info("mode %s has no hotkey — skipping", name)
        continue
    ...
```

### 4. `src/zen_type/ui/settings.html`

在「🎯 模式與快捷鍵」分頁把 Transform / Ask 的 row 加上視覺標示：
- 標題後加 `(暫未啟用)` 或改用淡化樣式
- 或者直接用 `display: none` 隱藏（保留資料）

**選擇**：淡化但不隱藏（使用者日後要恢復可直接啟用）。用 `opacity: 0.5` + `pointer-events: none` 就夠。

### 5. 使用者當前 `%APPDATA%\zen-type\config.json`

直接覆寫 hotkeys / modesEnabled 欄位成新預設值。

---

## 關鍵檔案路徑

- `D:\000\HSY_Project\zen-type\src\zen_type\core\injector.py` ← 主要修正
- `D:\000\HSY_Project\zen-type\src\zen_type\config\settings.py` ← 預設值
- `D:\000\HSY_Project\zen-type\src\zen_type\app.py` ← skip 空 hotkey
- `D:\000\HSY_Project\zen-type\src\zen_type\ui\settings.html` ← 淡化兩模式
- `C:\Users\SYH-w10\AppData\Roaming\zen-type\config.json` ← 使用者目前設定

---

## 重用既有元件

- `zen_type.core.hotkey.HotkeyManager`（已有非阻塞 callback + 卡住自動恢復）
- `zen_type.core.hotkey.normalize_combo`（已處理 `alt+space` 格式）
- `zen_type.core.constants.CLIPBOARD_SETTLE_SECONDS`（保持用，但新增一個 `MODIFIER_RELEASE_SLEEP = 0.05`）

---

## 驗證（使用者手動測試）

1. 停掉目前所有 zen-type 行程
2. 覆寫 user config → hotkeys={dictate:"alt+space", transform:"", ask:""}, modesEnabled={dictate:true, transform:false, ask:false}
3. `uv run zen-type --debug --no-browser`
4. Log 應出現：
   ```
   hotkey registered: dictate → alt+space
   mode transform has no hotkey — skipping
   mode ask has no hotkey — skipping
   ```
5. 在記事本：
   - 按住 **Alt+Space** 說話 → 放開 → 文字應正確貼上（不會出現 Windows 系統選單、不會卡 Alt+Ctrl+V）
6. 試用 IME 切換（Ctrl+Shift）→ 應正常運作，不閃爍
7. 連續使用 20 次 Alt+Space → 應穩定

---

## 暫不處理（可後續做）

- Transform / Ask 模式恢復：使用者未來想用時，在設定頁取消淡化即可
- Alt+Space 在某些舊版 Notepad 還是會有視覺上的選單閃現：`keyboard.add_hotkey(..., suppress=True)` 絕大多數情況可抑制；若仍有殘留，下一階段再看

---

（以下是本專案初次建立時的原始初始化計畫，保留作為歷史紀錄）

---

# zen-type 專案初始化計畫

## Context

使用者要打造一個 AI 語音輸入工具 `zen-type`，安裝於 `D:\000\HSY_Project\zen-type`（目前空目錄）。

已指定：
- **參考專案**：`D:\000\HSY_Project\voicetype-0.1.0`（開源程式碼，已完成深入分析）
- **參考產品**：[Typeless](https://www.typeless.com/)（商業產品，僅研究功能設計，不複製程式碼）
- **STT**：Groq API（Whisper Large V3）
- **AI 處理**：語意整理/潤稿（LLM 多供應商可切換）
- **套件管理**：`uv` + `pyproject.toml`
- **v1 功能**：全域 Push-to-Talk、系統托盤常駐、Web 設定頁面、自動貼上到前景視窗

### Typeless 功能研究摘要（值得借鑑的設計）

Typeless 的差異化不在「聲音轉文字」，而在「AI 後處理 + 多模式快捷鍵」。整理出可納入 zen-type 的設計亮點：

| Typeless 特色 | 納入 zen-type 的方式 |
|---|---|
| 多模式快捷鍵（Dictation / Command / Transform） | **v1 設計三個獨立 hotkey**：聽寫、選取改寫、AI 問答 |
| 選取文字後語音改寫（"make professional", "fix grammar", "shorten"） | **v1 納入「選取改寫」模式**：讀剪貼簿選取 → 語音下指令 → LLM 改寫 → 貼回 |
| 口述指令（"new line", "new paragraph", 標點名稱） | **v1 加前處理**：LLM prompt 內要求把這些關鍵字轉為實際符號 |
| 電話、清單自動格式化 | 透過 LLM system prompt 指示即可 |
| 依應用切換語氣（郵件正式、聊天輕鬆） | **沿用參考專案的 context-aware**，但改為可編輯的「情境模板」表 |
| 多語自動偵測、中英混排 | Whisper 本來就支援，prompt 加強指示 |
| Zero retention 隱私主張 | 本地設定檔、無遙測、API 呼叫都即用即棄 |
| Whisper mode（安靜環境低音量） | v2 再做 |
| 個人化學習（長期累積使用者用詞） | **v1 做「自訂詞彙」**，v2 再做自動學習 |

### 參考專案優缺點摘要
**優點（保留）**：模組化清晰、多引擎支援、首啟自動開設定、Web UI、托盤狀態色彩、COM 模式管理、Hotkey suppress、窗口焦點恢復、自訂詞彙傳入 Whisper prompt。

**缺點（本專案修正）**：
1. `main.py` 混合業務邏輯與 UI → **拆出 `core/pipeline.py`**
2. 執行緒同步靠布林 flag 無鎖 → **改用 `threading.Event` + `Lock`**
3. Hotkey/unhook/register 硬編碼在 main → **封裝進 `HotkeyManager` 生命週期**
4. 無任務隊列、快速連擊會競態 → **改用 `queue.Queue` 排隊 + 取消旗標**
5. 硬編碼常數散落 → **集中於 `core/constants.py`**
6. 無日誌級別控制 → **加 `--debug` flag 與環境變數**
7. `outputMode` 欄位存在但未實現 → **實作 clipboard / auto-paste 兩種模式**
8. 無設定版本管理 → **加 `schema_version` + migration**
9. HTTP 用 `SimpleHTTPRequestHandler` 易出錯 → **沿用但加錯誤處理與路徑驗證**
10. 無測試 → **核心模組加 `pytest` 骨架**

---

## 技術堆疊

| 項目 | 選擇 |
|---|---|
| Python | 3.11+（配合 uv 與 PEP 604 語法） |
| 套件管理 | `uv` + `pyproject.toml` + `uv.lock` |
| 音訊錄製 | `sounddevice` + `numpy` |
| 全域熱鍵 | `keyboard` |
| 文字注入 | `pyperclip` + `pyautogui` |
| 系統托盤 | `pystray` + `Pillow` |
| STT | Groq API（OpenAI 相容介面，`openai` SDK）+ `whisper-large-v3` |
| LLM | Groq（預設） / OpenAI / Anthropic / Ollama（多供應商） |
| Web 設定 | stdlib `http.server`（零依賴） |
| Windows 自啟動 | `winreg`（stdlib，可選） |
| 測試 | `pytest` |
| 打包 | `PyInstaller`（可選，後期） |

---

## 目錄結構

```
zen-type/
├── pyproject.toml              # uv 專案定義（依賴、entry points）
├── .python-version             # 指定 Python 版本
├── .gitignore                  # Python + venv + IDE + 設定檔
├── README.md                   # 使用說明（中文）
├── LICENSE                     # MIT
├── start.bat                   # Windows 一鍵啟動（uv run zen-type）
│
├── src/zen_type/
│   ├── __init__.py             # 版本號 __version__
│   ├── __main__.py             # 允許 `python -m zen_type`
│   ├── app.py                  # 應用入口（替代舊 main.py），組裝各元件
│   ├── cli.py                  # CLI 參數解析（--debug、--config-path）
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── constants.py        # [新] 統一常數（取樣率、延遲、埠號）
│   │   ├── pipeline.py         # [新] 錄音→STT→潤稿→注入 業務管線
│   │   ├── recorder.py         # 音訊錄製
│   │   ├── stt.py              # Groq Whisper（主）+ 預留 local/openai
│   │   ├── llm.py              # 多供應商 LLM 潤稿
│   │   ├── injector.py         # 文字注入（clipboard / auto-paste）
│   │   ├── hotkey.py           # HotkeyManager（含 unhook/re-register 生命週期）
│   │   ├── sounds.py           # 開始/結束音效
│   │   ├── tray.py             # 系統托盤（從 main 拆出）
│   │   ├── tray_icons.py       # 狀態圖示生成
│   │   └── context.py          # 窗口上下文偵測（可選 pywin32）
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py         # JSON 讀寫 + schema_version + migration
│   │   └── settings_server.py  # HTTP API（GET/POST /api/config）
│   │
│   └── ui/
│       └── settings.html       # Web 設定頁（深色主題，分頁籤）
│
└── tests/
    ├── test_settings.py        # 設定讀寫、合併、migration
    ├── test_stt.py             # mock Groq client
    └── test_pipeline.py        # mock 全流程
```

---

## 關鍵檔案設計重點

### `pyproject.toml`
- `[project]` name="zen-type", version="0.1.0", Python ≥3.11
- `[project.scripts]` `zen-type = "zen_type.app:main"`（安裝後可直接 `zen-type` 執行）
- 依賴分組：
  - 核心：`sounddevice`, `numpy`, `keyboard`, `pyperclip`, `pyautogui`, `pystray`, `Pillow`, `openai`, `anthropic`, `requests`
  - `[project.optional-dependencies]`：
    - `windows`: `pywin32` （上下文感知）
    - `local`: `faster-whisper`（本地 STT）
    - `dev`: `pytest`, `pytest-mock`, `ruff`

### `core/pipeline.py`（新）
- `class AudioPipeline`：暴露 `start_recording(mode)` / `stop_and_process()` 兩個方法
- **三種模式**（受 Typeless 啟發）：
  - `Mode.DICTATE`：錄音 → STT → LLM 潤稿 → 貼上（預設）
  - `Mode.TRANSFORM`：先抓目前選取文字（Ctrl+C 抓進剪貼簿）→ 錄音 → STT 得到「指令」→ LLM 把選取文字按指令改寫 → 貼回
  - `Mode.ASK`：錄音 → STT → LLM 當成問題回答 → 貼上答案（或只顯示於通知）
- 狀態機：`IDLE → RECORDING → TRANSCRIBING → POLISHING → INJECTING → IDLE`
- 使用 `threading.Event` 通知狀態變化給 `tray`
- 包裝 `_safe_inject()`：暫停 hotkey → SetForegroundWindow → inject → 恢復 hotkey（修正參考專案在 main 內硬編的流程）

### `core/stt.py`
- `SpeechToText(provider="groq", model="whisper-large-v3")`
- Groq 用 `openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=...)`
- `transcribe(audio: np.ndarray) -> str`：呼叫 `client.audio.transcriptions.create`
- 支援 `prompt=` 帶入自訂詞彙
- 預留 `_transcribe_local()` / `_transcribe_openai()` 但 v1 用 `NotImplementedError` 友善訊息

### `core/llm.py`
- `LLMProcessor(settings)` 依 `llmProvider` 分派
- **三個方法**對應三種模式：
  - `polish(raw, context=None)`：去贅字、加標點、保留原意（Mode.DICTATE 用）
  - `transform(original_text, instruction)`：依指令改寫選取文字（Mode.TRANSFORM 用）
  - `ask(question, context=None)`：當成問題回答（Mode.ASK 用）
- **口述指令處理**（納入 `polish` 的 system prompt）：把「新行 / 換行 / new line」轉為 `\n`；「新段落 / new paragraph」轉為 `\n\n`；口說的「句號/逗號/問號」轉為標點
- **情境模板**：`context_templates` dict，預設含 `email`、`chat`、`code`、`doc`，每個模板有專屬 system prompt 片段，使用者可在 Web UI 編輯
- 失敗時 return 原文（不中斷使用者）
- 預設模型：
  - groq → `llama-3.3-70b-versatile`
  - openai → `gpt-4o-mini`
  - anthropic → `claude-haiku-4-5-20251001`
  - ollama → `qwen3:8b`

### `core/hotkey.py`
- `HotkeyManager` 支援**同時註冊多組快捷鍵**（受 Typeless 多模式設計啟發）
- API：`register(key, mode, on_press, on_release)` / `unregister(mode)` / `unhook_all()` / `rebind(mode, new_key)`
- 預設三組：
  - `Mode.DICTATE` → `RightAlt`
  - `Mode.TRANSFORM` → `RightCtrl`
  - `Mode.ASK` → `F9`
- 可選鍵：`RightAlt / RightCtrl / F9 / F10 / CapsLock / ScrollLock / Pause`
- `suppress=True`（參考專案已驗證有效）
- 內部 `_registered: dict[Mode, HotkeyHandle]` 管理生命週期

### `core/injector.py`
- 兩種模式：
  - `clipboard`：只複製到剪貼簿（安靜）
  - `auto_paste`：複製 + Ctrl+V（預設）
- 保留原剪貼簿內容、完成後復原（參考專案未做，本專案加強）

### `config/settings.py`
- 位置：`%APPDATA%\zen-type\config.json`
- `DEFAULT_CONFIG` 新增 `"schema_version": 1`
- 新增欄位（對應多模式設計）：
  ```json
  "hotkeys": {
    "dictate": "RightAlt",
    "transform": "RightCtrl",
    "ask": "F9"
  },
  "contextTemplates": {
    "email": "正式、有禮、結構清晰",
    "chat": "輕鬆口語、可用表情",
    "code": "技術性、簡潔、保留專有名詞原文",
    "doc": "條理分明、標點完整"
  },
  "dictionary": [],
  "telemetry": false
  ```
- `migrate(cfg)` 函式：未來升版可加規則
- 白名單驗證（沿用參考專案）
- 首啟自動建檔

### `config/settings_server.py`
- 埠號：`127.0.0.1:7878`（可設定）
- 路由：
  - `GET /` → 回傳 `ui/settings.html`
  - `GET /api/config` / `POST /api/config`
  - `POST /api/config/key`
  - `GET /api/health`
- 加入路徑白名單，避免路徑穿越

### `ui/settings.html`
- 深色主題，沿用參考專案風格但簡化
- Tab：🔑 API 金鑰 / 🎤 語音 / ⚡ LLM 潤稿 / 🎯 模式與快捷鍵 / 🧩 情境模板 / 📖 詞彙 / ⚙ 一般
- 「模式與快捷鍵」頁：展示 3 個模式、對應快捷鍵、各自開關（可停用某模式）

### `core/constants.py`
```python
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 1024
MIN_RECORDING_SECONDS = 0.3
CLIPBOARD_SETTLE_SECONDS = 0.1
INJECT_DELAY_SECONDS = 0.3
SETTINGS_SERVER_HOST = "127.0.0.1"
SETTINGS_SERVER_PORT = 7878
```

---

## 實作順序

1. **骨架**：建立目錄結構、`pyproject.toml`、`.gitignore`、`.python-version`、`README.md`、`LICENSE`
2. **設定層**：`config/settings.py` + `ui/settings.html` + `config/settings_server.py`
3. **核心元件**：`constants.py` → `recorder.py` → `stt.py`（Groq）→ `llm.py` → `injector.py`
4. **輔助元件**：`hotkey.py` → `sounds.py` → `tray_icons.py` → `tray.py`
5. **管線組裝**：`core/pipeline.py` → `app.py` → `cli.py`
6. **入口點**：`__main__.py` + `start.bat`
7. **測試骨架**：`tests/test_settings.py` 至少一支單元測試確認 import 正確

---

## 驗證方式

執行順序（使用者確認計畫後，本助手將在實作階段執行）：

1. **安裝**：`cd D:\000\HSY_Project\zen-type && uv sync`
2. **冒煙測試**：`uv run python -c "from zen_type.config.settings import Settings; print(Settings().load())"`
3. **啟動應用**：`uv run zen-type`
   - 預期：首次執行自動在 `%APPDATA%\zen-type\config.json` 建檔、瀏覽器開 `http://127.0.0.1:7878`
4. **設定 Groq Key**：在 Web UI 填入 → 按儲存 → 檢查 JSON 更新
5. **快捷鍵測試**：按住 `Right Alt` → 對著麥克風說話 → 放開 → 文字自動貼上
6. **單元測試**：`uv run pytest tests/`

---

## 預期交付物

- 可立即執行的 `zen-type` 專案骨架
- `uv sync` 一鍵安裝所有依賴
- `uv run zen-type` 一鍵啟動
- Groq STT + 多供應商 LLM 潤稿的完整語音輸入流程
- 相對參考專案：更乾淨的分層、加固的並發控制、可擴展的設定 schema

## 暫不實作（延到 v2）

- 流式 STT（降延遲）
- 多階段潤稿管線
- asyncio 重構
- PyInstaller 打包
- 完整的 pytest 覆蓋
- 本地 `faster-whisper` STT
- Whisper mode（安靜環境 VAD）
- 個人化自動學習（長期累積使用者用詞的統計）
- iOS/Android 鍵盤
- 即時翻譯模式（可用 Transform 模式 + 指令「翻譯成英文」替代）
