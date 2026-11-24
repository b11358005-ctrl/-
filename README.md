# Stock Multi-Agent Desktop

> **完全獨立、零平台綁定（Zero Lock-in）的跨平台桌面端 Multi-Agent 財經新聞與股票趨勢分析工作台**  
> 基於 **PySide6** 原生桌面介面與 **PyInstaller** 打包方案，支援 Windows (`.exe`) 與 macOS (`.app`) 本機執行，結合「過去・現在・未來・風控」多維度 AI Agent 協同產出結構化股票研究報告。

---

## 核心特色

- **時間維度 Multi-Agent 協同架構**：
  - **Orchestrator（總管協調官）**：驗證與標準化股票代碼、平行調度蒐集分支、彙整總管執行摘要與 Markdown 研究報告。
  - **Past Agent（過去維度）**：透過 `yfinance` 與 `pandas` 擷取 1~5 年歷史價量、計算技術指標（SMA20/50/200、RSI14、MACD、年化波動率、最大回撤）與財報估值基準。
  - **Present Agent（現在維度）**：級聯搜尋近 3~30 天財經新聞（Tavily → DuckDuckGo → Google News RSS → Yahoo Finance），進行去重、時間戳標記、多空情緒打分（`-1.0` ~ `+1.0`）與事實／觀點分類。
  - **Future Agent（未來維度）**：結合歷史估值與即時催化劑，推演未來 1 個月（1M）與 1 季（1Q）的 **Bull / Base / Bear** 三情境機率矩陣與觀察指標。
  - **Risk Agent（全維度把關）**：獨立反方審查員（Devil's Advocate），進行壓力測試、揭露總經逆風、黑天鵝與單一新聞過度解讀盲點。
- **Provider-Agnostic（無供應商綁定）**：
  - 底層以純 `httpx` 自建 Adapter Pattern，無重型 SDK 綁定。
  - 支援 **Google Gemini（預設免費額度友善配置 `gemini-2.5-flash`）**、**OpenAI**、**Anthropic Claude**、**DeepSeek**、**本機 Ollama（完全離線零費用）**，以及任意 **OpenAI-Compatible** 端點（OpenRouter / Groq / LM Studio）。
  - 支援一鍵統一切換全部 Agent，或為 5 個 Agent 各自指派不同模型與參數。
- **本機安全與離線持久化**：
  - 所有 API Key 透過 `cryptography.fernet` 搭配本機金鑰加密儲存於 `config/settings.json`，絕不寫死在程式碼中。
  - 股價數據、新聞快取與歷史報告儲存於本機 SQLite（`data/app_cache.db`），避免重複消耗 API 額度並支援離線回看與匯出 `.md`。

---

## 系統架構流程

```text
使用者輸入股票代碼 (例: NVDA / 2330 / 2330.TW)
        │
        ▼
[1. Orchestrator] 代碼驗證與台/美股後綴自動補全
        │
        ├──────────────────────────┐
        ▼ (平行執行)               ▼ (平行執行)
[2a. Past Agent]            [2b. Present Agent]
 yfinance 歷史價量/財報      Tavily / DuckDuckGo / RSS / YF
 技術指標 & 估值評估         新聞清洗去重 & 情緒評分 (-1~+1)
        │                          │
        └────────────┬─────────────┘
                     ▼ (嚴格 Pydantic JSON 傳遞)
           [3. Future Agent]
            1M & 1Q 三情境推演 (Bull / Base / Bear)
                     │
                     ▼
           [4. Risk Agent]
            壓力測試 / 盲點偵測 / 調整後信心分數
                     │
                     ▼
           [5. Orchestrator]
            彙整 Markdown 報告 + 寫入本機 SQLite + GUI 渲染
```

---

## 專案目錄結構

```text
stock-multi-agent-desktop/
├── PROJECT_SPEC.md              # 專案設計單一真實來源（Single Source of Truth）
├── README.md                    # 專案說明與快速啟動指南
├── docs/
│   └── USER_GUIDE.md            # 完整使用手冊（含各家 AI API 設定教學）
├── requirements.txt             # Python 依賴套件清單
├── .env.example                 # 可選的本機環境變數範本
├── main.py                      # PySide6 桌面應用程式啟動入口
├── config/
│   └── settings.json            # 本機加密儲存的 API Keys 與模型分配（執行時自動生成，已忽略版控）
├── data/
│   └── app_cache.db             # 本機 SQLite 快取與歷史報告資料庫（執行時自動生成，已忽略版控）
├── src/
│   ├── core/
│   │   ├── config_manager.py    # 本機設定讀寫與 Fernet API Key 加密
│   │   ├── storage.py           # SQLite 快取與歷史報告持久化
│   │   ├── llm_gateway.py       # Provider-Agnostic Adapter Pattern（含 429 退避重試）
│   │   └── schemas.py           # Pydantic v2 嚴格資料契約
│   ├── tools/
│   │   ├── stock_data.py        # yfinance 歷史股價、技術指標與基本面工具
│   │   └── news_search.py       # 多來源財經新聞搜尋與內文清洗去重工具
│   ├── agents/
│   │   ├── orchestrator.py      # 總管協調邏輯
│   │   ├── past_agent.py        # 過去基本面分析 Agent
│   │   ├── present_agent.py     # 現在新聞與情緒分析 Agent
│   │   ├── future_agent.py      # 未來趨勢情境推演 Agent
│   │   └── risk_agent.py        # 風控與反方審查 Agent
│   └── ui/
│       └── app_window.py        # PySide6 原生桌面 GUI
└── build/
    ├── stock_analyst.spec       # PyInstaller 跨平台打包規格檔
    └── build_desktop.py         # 一鍵打包執行檔腳本
```

---

## 快速開始（本機開發與執行）

### 1. 環境需求
- Python `3.10` ~ `3.12`（建議 `3.11`）
- Windows 10/11 或 macOS（Apple Silicon / Intel）

### 2. 安裝依賴
```bash
git clone <你的 GitHub Repo URL>
cd <專案資料夾名稱>

python -m venv .venv
# Windows PowerShell / CMD:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. 啟動桌面應用程式
```bash
python main.py
```

首次開啟後，點擊左側 **「API 金鑰與模型設定」**：
- 若您沒有付費 API Key，可至 [Google AI Studio](https://aistudio.google.com/apikey) 免費申請一組 Gemini API Key 並貼入 **Google Gemini API** 欄位（系統預設全部 5 個 Agent 皆採用免費額度友善的 `gemini-2.5-flash`）。
- 若要完全離線零費用運行，也可使用本機 **Ollama**。
- 詳細各家 API 申請與設定步驟請參閱 **[📖 完整使用手冊 (`docs/USER_GUIDE.md`)](docs/USER_GUIDE.md)**。

---

## 打包為獨立桌面執行檔（`.exe` / `.app`）

完成測試後，可使用專案內附的打包腳本一鍵生成獨立執行檔（輸出於 `dist/` 目錄）：

```bash
python build/build_desktop.py
```

- **Windows**：產出 `dist/StockMultiAgent.exe`
- **macOS**：產出 `dist/StockMultiAgent.app`

> 打包後第一次執行時，程式會在執行檔同層自動建立 `config/` 與 `data/` 資料夾（若目錄無寫入權限則自動改存於使用者家目錄 `~/StockMultiAgentDesktop/`）。

---

## 推送至公開 GitHub 前的安全檢查

本專案已在 `.gitignore` 中排除所有本機機密與使用者資料，推送前請再次確認以下項目**沒有**被加入 Git 追蹤：
- `config/settings.json`（加密後的 API Key 與個人設定）
- `config/.key`（本機 Fernet 加密金鑰）
- `.env`（環境變數檔，僅保留 `.env.example` 範本）
- `data/*.db`（本機 SQLite 報告與快取）
- `dist/`、`build/work/`（打包輸出產物）

---

## 延伸閱讀與開發規範

- **[使用手冊 (`docs/USER_GUIDE.md`)](docs/USER_GUIDE.md)**：UI 操作教學與各家 AI API（Gemini / OpenAI / Claude / DeepSeek / Ollama / 自訂端點 / Tavily）完整設定指南。
- **[架構規格書 (`PROJECT_SPEC.md`)](PROJECT_SPEC.md)**：本專案單一真實來源，記錄所有技術選型、Agent JSON Schema 與目錄規範。

---

## 免責聲明

本應用程式產出之所有數據摘要、新聞情緒評分、情境推演與風險分析僅供**個人研究學習與資訊整理參考**，不構成任何形式之投資建議、買賣邀約或獲利保證。投資人應獨立判斷並自負交易風險。
