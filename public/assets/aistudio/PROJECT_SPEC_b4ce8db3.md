
# PROJECT_SPEC.md - Multi-Agent 財經新聞與股票趨勢分析桌面應用程式

## 1. 專案願景與核心目標

開發一款輕量化、可直接放置於桌面雙擊執行的獨立應用程式（`.exe` / `.app`）。使用者無需懂程式，只需在設定介面填入各家 AI 模型的 API Key 與財經新聞搜尋 Key，輸入股票代碼（支援台股如 `2330.TW` 與美股如 `NVDA`），即可啟動多個專職 AI Agent 協同作業，產出涵蓋「過去、現在、未來」三個時間維度的股票趨勢分析報告。

## 2. 核心架構原則（轉移與解耦規範）

- **完全獨立運行**：不依賴任何特定雲端 IDE 或 AI Studio 沙盒環境，所有依賴套件皆透過 `requirements.txt` 管理。
- **LLM 供應商無關（LLM-Agnostic）**：
  - 支援在 UI 動態設定多個 API Key（例如：新聞摘要用低成本模型如 `gpt-4o-mini` / `gemini-2.5-flash`；趨勢推演與風控用高推理模型如 `claude-3-7-sonnet` / `gemini-2.5-pro` / `deepseek-reasoner`）。
  - 統一透過 `LiteLLM` 或標準化 `LLMClient` 介面呼叫模型，方便未來擴充新模型。
- **本機資料持久化**：
  - API Keys 儲存於本機的 `config/settings.json`（不進版控）。
  - 歷史分析報告與抓取的新聞快取儲存於本機 `data/` 目錄（SQLite 或 JSON），避免重複消耗 API 額度。

## 3. Multi-Agent 系統設計（時間維度分工）

系統採用「總管調度 + 平行蒐集 + 交叉驗證 + 報告生成」管線，所有 Agent 之間皆透過嚴格的 JSON Schema 交換資料：

1. **Orchestrator Agent（總管協調官）**
   - 負責驗證輸入的股票代碼、分配時間窗口、調度下游 Agent 並彙整最終 Markdown 報告。
2. **Historical & Fundamental Agent（過去維度：歷史與基本面分析師）**
   - 職責：調取過去 1~3 年股價走勢、財報關鍵數據（營收、EPS、本益比區間）與歷史重大事件反應。
   - 資料源：`yfinance`（美股/台股基礎數據）、公開財報摘要。
3. **News & Sentiment Agent（現在維度：即時新聞蒐集與情緒分析師）**
   - 職責：搜尋近 7~14 天最新財經新聞與市場消息，過濾重複與無關雜訊，標記發布時間戳記，並對每則新聞進行多空情緒打分（-1.0 到 +1.0）及事實/觀點分類。
   - 資料源：Tavily Search API / DuckDuckGo Search（免費備援）/ RSS Feeds。
4. **Future Strategist Agent（未來維度：趨勢推演與情境預測師）**
   - 職責：結合「過去的估值基準」與「現在的最新催化劑」，推演未來 1 個月（短期）與 1 季（中期）的三種情境（樂觀 Bull、基準 Base、悲觀 Bear）與關鍵觀察指標。
5. **Risk & Devil's Advocate Agent（全維度把關：風控與反方審查員）**
   - 職責：針對預測師的結論進行壓力測試，找出潛在黑天鵝、總體經濟逆風或單一新聞過度解讀的盲點。

## 4. 目標目錄結構（Directory Structure）

```text
stock-multi-agent-desktop/
├── PROJECT_SPEC.md          # 本專案核心設計文件（AI 認知基準）
├── requirements.txt         # Python 依賴套件清單
├── main.py                  # 桌面應用程式啟動入口
├── config/
│   └── settings.json        # 本機儲存的 API Keys 與 Agent 模型分配設定（自動生成）
├── src/
│   ├── core/
│   │   ├── llm_gateway.py   # 統一多模型 API 呼叫介面（支援切換不同 Key 與供應商）
│   │   └── schemas.py       # Pydantic 資料結構定義（確保 Agent 間傳遞標準 JSON）
│   ├── tools/
│   │   ├── stock_data.py    # 歷史股價與財報抓取工具（yfinance）
│   │   └── news_search.py   # 網路財經新聞搜尋與內文清洗工具
│   ├── agents/
│   │   ├── orchestrator.py  # 總管協調邏輯
│   │   ├── past_agent.py    # 過去基本面分析 Agent
│   │   ├── present_agent.py # 現在新聞與情緒 Agent
│   │   ├── future_agent.py  # 未來趨勢推演 Agent
│   │   └── risk_agent.py    # 風控反方審查 Agent
│   └── ui/
│       └── app_window.py    # 桌面 GUI 介面（包含 API Key 設定頁、執行進度條、報告閱讀器）
└── build/                   # PyInstaller 打包桌面執行檔的輸出目錄
```
