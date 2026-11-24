# PROJECT_SPEC.md - Multi-Agent 財經新聞與股票趨勢分析桌面應用程式

## 1. 專案願景與核心目標

開發一款輕量化、可直接放置於桌面雙擊執行的獨立應用程式（Windows `.exe` / macOS `.app`）。使用者無需懂程式，只需在桌面設定介面填入各家 AI 模型的 API Key 與財經新聞搜尋 Key，輸入股票代碼（支援台股如 `2330.TW` 與美股如 `NVDA`），即可啟動多個專職 AI Agent 協同作業，產出涵蓋「過去、現在、未來、風控」時間維度的股票趨勢分析報告。

## 2. 已確認技術選型與架構原則（Single Source of Truth）

- **桌面 UI 與打包方案**：`PySide6`（Qt for Python）原生跨平台視窗 + `PyInstaller` 獨立執行檔打包。
- **完全獨立運行（Zero Lock-in）**：不依賴任何特定雲端 IDE 或沙盒環境，所有依賴套件皆透過 `requirements.txt` 管理，可在 Windows / macOS 本機離線或連網執行。
- **LLM 供應商無關（Provider-Agnostic Adapter Pattern）**：
  - 採用統一自建 Adapter Pattern（底層使用標準 `httpx` REST 呼叫，無額外重型 SDK 包袱），支援：
    - `openai`（OpenAI 官方 API）
    - `anthropic`（Anthropic Claude Messages API）
    - `gemini`（Google Gemini REST API）
    - `deepseek`（DeepSeek API，支援 `deepseek-chat` 與 `deepseek-reasoner`）
    - `ollama`（本地 Ollama OpenAI-compatible 端點）
    - `openai_compatible`（任何自訂 OpenAI 相容端點，如 OpenRouter、Groq、LM Studio）
  - 預設全部 5 個 Agent 採用 Google Gemini 免費額度友善配置（預設 `gemini-2.5-flash`，並內建 `gemini-3.8-flash` / `gemini-2.5-pro` 等下拉選項與 `max_tokens=8192`），內建 HTTP `429`/`503` 指數退避重試機制，並支援在 UI 一鍵統一切換全部 Agent 或為每個 Agent 獨立混搭不同供應商與模型。
- **本機安全儲存與持久化**：
  - API Keys 使用 `cryptography.fernet` 搭配本機產生的 `config/.key`（權限 `0o600`）加密儲存於 `config/settings.json`（不進版控），並支援 `.env` 預設值讀取。
  - 歷史分析報告、股價快取與抓取的新聞快取儲存於本機 SQLite 資料庫 `data/app_cache.db`，避免重複消耗 API 額度並支援離線回看報告。

## 3. Multi-Agent 系統設計（時間維度分工）

系統採用「總管調度 + 平行蒐集（Past & Present） + 交叉推演（Future） + 反方審查（Risk） + 報告生成」管線，所有 Agent 之間皆透過 Pydantic v2 定義的嚴格 JSON Schema 交換資料：

1. **Orchestrator（總管協調邏輯 - `src/agents/orchestrator.py`）**
   - 驗證與標準化股票代碼（支援自動補全台灣上市/上櫃 `.TW` / `.TWO` 後綴）。
   - 透過 `ThreadPoolExecutor` 平行執行 `PastAgent` 與 `PresentAgent`。
   - 串接 `FutureAgent` 與 `RiskAgent`，並彙整為完整 Markdown 報告儲存至本機 SQLite。
2. **Historical & Fundamental Agent（過去維度：`src/agents/past_agent.py`）**
   - 調取過去 1~3 年股價走勢、計算技術指標（SMA20/50/200、RSI14、MACD、最大回撤、年化波動率）與財報關鍵數據（營收、EPS、本益比區間、ROE）。
   - 資料源：`yfinance` + `pandas`。
3. **News & Sentiment Agent（現在維度：`src/agents/present_agent.py`）**
   - 搜尋近 7~14 天最新財經新聞與市場消息，進行 URL 與標題去重，保留發布時間戳記，並對每則新聞進行多空情緒打分（`-1.0` 到 `+1.0`）及事實/觀點分類（`Fact` / `Opinion` / `Mixed`）。
   - 資料源級聯：`Tavily Search API`（選填 Key） -> `DuckDuckGo Search (ddgs)`（免費備援） -> `Google News RSS` & `Yahoo Finance News`。
4. **Future Strategist Agent（未來維度：`src/agents/future_agent.py`）**
   - 結合「過去估值基準」與「現在最新催化劑」，推演未來 1 個月（短期）與 1 季（中期）的三種情境（樂觀 `Bull`、基準 `Base`、悲觀 `Bear`），包含機率分布、目標區間與關鍵觀察指標。
5. **Risk & Devil's Advocate Agent（全維度把關：`src/agents/risk_agent.py`）**
   - 針對預測結論進行壓力測試，找出潛在黑天鵝、總體經濟逆風、估值陷阱或單一新聞過度解讀的盲點，並給出調整後信心分數。

## 4. 最終專案目錄結構（Directory Structure）

```text
stock-multi-agent-desktop/
├── PROJECT_SPEC.md              # 本專案核心設計文件（Single Source of Truth）
├── README.md                    # GitHub 專案首頁說明與快速啟動指南
├── docs/
│   └── USER_GUIDE.md            # 完整使用手冊（含各家 AI API 設定教學）
├── requirements.txt             # Python 依賴套件清單
├── .env.example                 # 本機環境變數範本（選填）
├── main.py                      # PySide6 桌面應用程式啟動入口（含 PyInstaller 路徑相容）
├── config/
│   └── settings.json            # 本機加密儲存的 API Keys 與 Agent 模型分配設定（執行時自動生成）
├── data/
│   └── app_cache.db             # 本機 SQLite 資料庫（股價/新聞快取與歷史分析報告）
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config_manager.py    # 本機設定管理與 Fernet API Key 加密存取
│   │   ├── storage.py           # SQLite 快取與歷史報告讀寫模組
│   │   ├── llm_gateway.py       # Provider-Agnostic Adapter Pattern 多模型呼叫介面
│   │   └── schemas.py           # Pydantic v2 資料結構定義（Agent 間標準 JSON）
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── stock_data.py        # 歷史股價、技術指標與財報抓取工具（yfinance）
│   │   └── news_search.py       # 多來源財經新聞搜尋（Tavily / DuckDuckGo / RSS）與清洗去重
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # 總管協調邏輯（平行蒐集 + 串接推演 + 報告彙整）
│   │   ├── past_agent.py        # 過去歷史與基本面分析 Agent
│   │   ├── present_agent.py     # 現在即時新聞與情緒 Agent
│   │   ├── future_agent.py      # 未來趨勢情境推演 Agent
│   │   └── risk_agent.py        # 風控與反方審查 Agent
│   └── ui/
│       ├── __init__.py
│       └── app_window.py        # PySide6 原生桌面 GUI（分析工作台、報告閱讀與匯出、設定頁）
└── build/
    ├── stock_analyst.spec       # PyInstaller 跨平台打包規格檔
    └── build_desktop.py         # 一鍵桌面打包腳本（Windows .exe / macOS .app）
```

## 5. 本機執行與打包指令

```bash
# 1. 建立虛擬環境並安裝依賴
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 2. 啟動桌面應用程式
python main.py

# 3. 打包為獨立桌面執行檔
python build/build_desktop.py
```
