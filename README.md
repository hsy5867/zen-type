# zen-type

> 禪意般簡潔的 AI 語音輸入工具 — 按住快捷鍵說話，AI 自動潤稿，貼上即用。

## 功能

- **Push-to-Talk**：按住 `Right Alt` 說話，放開自動轉文字並貼上
- **三模式快捷鍵**（受 Typeless 啟發）：
  - `Right Alt` — **Dictate**：錄音 → STT → LLM 潤稿 → 貼上
  - `Right Ctrl` — **Transform**：抓取選取文字 → 語音下指令 → LLM 改寫 → 貼回
  - `F9` — **Ask**：錄音 → STT → LLM 回答 → 貼上
- **Groq Whisper-Large-V3**：極快、極準、成本低
- **多供應商 LLM 潤稿**：Groq / OpenAI / Anthropic / Ollama 自由切換
- **口述指令**：說「新行」「新段落」「句號」自動轉符號
- **情境模板**：根據目前應用（郵件、聊天、程式、文件）調整語氣
- **自訂詞彙**：加入專有名詞提升辨識準確度
- **系統托盤常駐**：背景執行，狀態圖示即時顯示
- **原生設定視窗**：pywebview 打造的深色 UI，含麥克風來源選擇與音量測試
- **全應用支援**：VS Code、Chrome、Word、LINE、Slack…

## 快速開始

### 需求

- Windows 10/11
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 套件管理器
- Groq API Key（[免費申請](https://console.groq.com/)）

### 安裝

```bash
cd D:\000\HSY_Project\zen-type
uv sync
```

### 啟動

```bash
uv run zen-type
```

首次啟動會自動開啟原生設定視窗，填入 Groq API Key 即可。

或雙擊 `start.bat` 一鍵啟動。

## 設定檔位置

```
%APPDATA%\zen-type\config.json
```

## 使用方式

1. 啟動後確認系統列右下角出現 🎤 圖示
2. 打開任意輸入框（VS Code、Word、Chrome 等）
3. 按住 `Right Alt` 說話
4. 放開快捷鍵 → 等待 1~2 秒 → 文字自動貼上

## 架構

```
src/zen_type/
├── app.py              # 應用入口（tray + hotkey + pipeline）
├── settings_window.py  # pywebview 設定視窗（獨立子行程）
├── cli.py              # CLI 參數
├── core/
│   ├── pipeline.py     # 核心業務管線（錄音→STT→LLM→注入）
│   ├── recorder.py     # 音訊錄製（可指定裝置）
│   ├── audio_devices.py  # 裝置列舉 + 音量測試表
│   ├── stt.py          # Groq Whisper STT
│   ├── llm.py          # 多供應商 LLM（polish/transform/ask）
│   ├── injector.py     # 文字注入（clipboard/auto-paste）
│   ├── hotkey.py       # 多模式全域快捷鍵
│   ├── tray.py         # 系統托盤
│   └── ...
├── config/
│   └── settings.py     # JSON 設定 + migration
└── ui/
    └── settings.html   # 設定頁面（pywebview 載入）
```

## 開發

```bash
# 安裝開發依賴
uv sync --extra dev

# 執行測試
uv run pytest

# Lint
uv run ruff check src/
```

## 打包成單一 exe

適合分發給其他電腦使用（不需安裝 Python / uv）：

```bash
# 安裝打包依賴（第一次）
uv sync --extra build

# 一鍵打包（輸出在 dist\zen-type-<版本>.exe）
uv run python build.py

# 或雙擊：build.bat
```

**打包後產物**：
- `dist\zen-type-2.0.8.exe` — 約 40 MB 的單檔 exe，可直接複製到其他 Windows 電腦執行
- **不含任何 API Key**：設定值存在目標電腦的 `%APPDATA%\zen-type\config.json`，新機器首次啟動會建立空白設定
- **詞彙檔自動遷移**：首次啟動會把內建的 `refer_doc\*.txt` 複製到 `%APPDATA%\zen-type\refer_doc\`，使用者可自由編輯

**目標電腦需求**：
- Windows 10 / 11（x64）
- Edge WebView2 執行期（Windows 11 內建；Windows 10 絕大多數已裝）

**其他電腦首次執行步驟**：
1. 複製 `zen-type-2.0.8.exe` 過去，雙擊執行
2. 自動開啟設定視窗，填入 Groq API Key
3. 按 **Pause** 鍵即可開始語音輸入

## 版本

當前：**2.0.8** — 詳見 `zen_type.__release_notes__`

## 授權

MIT License
