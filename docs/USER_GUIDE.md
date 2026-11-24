# Stock Multi-Agent Desktop 使用手冊

本手冊將引導您從零設定各家 AI 模型 API Key、操作桌面介面執行「過去・現在・未來・風控」Multi-Agent 股票趨勢分析，以及善用快取、歷史報告與 JSON 結構檢查功能。

---

## 目錄
1. [啟動應用程式](#1-啟動應用程式)
2. [不同 AI 模型 API 設定教學](#2-不同-ai-模型-api-設定教學)
   - [2.1 Google Gemini API（免費額度首選，系統預設）](#21-google-gemini-api免費額度首選系統預設)
   - [2.2 OpenAI API](#22-openai-api)
   - [2.3 Anthropic Claude API](#23-anthropic-claude-api)
   - [2.4 DeepSeek API](#24-deepseek-api)
   - [2.5 Ollama（完全免費・本機離線運行）](#25-ollama完全免費本機離線運行)
   - [2.6 自訂 OpenAI-Compatible API（OpenRouter / Groq / LM Studio）](#26-自訂-openai-compatible-apiopenrouter--groq--lm-studio)
   - [2.7 選填：Tavily 財經新聞搜尋 API](#27-選填tavily-財經新聞搜尋-api)
3. [Multi-Agent 模型混搭與一鍵切換策略](#3-multi-agent-模型混搭與一鍵切換策略)
4. [股票分析操作步驟](#4-股票分析操作步驟)
5. [報告閱讀、JSON 檢查與本機歷史紀錄](#5-報告閱讀json-檢查與本機歷史紀錄)
6. [進階設定：使用 `.env` 預載金鑰](#6-進階設定使用-env-預載金鑰)
7. [常見問題與排查（FAQ）](#7-常見問題與排查faq)

---

## 1. 啟動應用程式

- **開發者／Python 環境啟動**：
  ```bash
  python main.py
  ```
- **打包後獨立執行檔啟動**：
  - Windows：雙擊 `StockMultiAgent.exe`
  - macOS：雙擊 `StockMultiAgent.app`（若首次出現安全性提示，請在「系統設定 → 隱私權與安全性」允許開啟）

啟動後，請先點擊左側選單的 **「API 金鑰與模型設定」** 完成至少一組 AI 模型設定。

---

## 2. 不同 AI 模型 API 設定教學

本系統採用自建的 Provider-Agnostic Adapter Pattern，您可以依照預算與需求選擇單一供應商，或讓不同 Agent 使用不同家的模型。所有填寫的 API Key 都會以本機隨機產生的金鑰進行 **Fernet 加密**，儲存於 `config/settings.json`，**絕不會上傳至任何第三方伺服器**。

> 💡 **安全提醒**：在設定頁填完 Key 後，務必點擊最下方的 **「儲存並加密所有設定」** 才會寫入本機設定檔；點擊 **「測試連線」** 可立即驗證該供應商是否正常回應。

---

### 2.1 Google Gemini API（免費額度首選，系統預設）

如果您目前沒有任何付費 API Key，**Google Gemini 的免費方案**是最容易上手的選擇（無需綁定信用卡即可申請測試額度）。

1. **申請步驟**：
   - 前往 [Google AI Studio API Keys](https://aistudio.google.com/apikey) 並登入 Google 帳號。
   - 點擊 **Create API key**，建立一個新的金鑰（格式通常為 `AIza...`）。
2. **軟體設定**：
   - 進入 **「API 金鑰與模型設定」** → 找到 **Google Gemini API** 欄位貼上金鑰。
   - **Base URL**：維持預設 `https://generativelanguage.googleapis.com/v1beta` 即可。
   - 系統預設全部 5 個 Agent 皆為 `gemini` / `gemini-2.5-flash`，直接點擊 **「測試連線」** 確認顯示連線成功後，按下 **「儲存並加密所有設定」** 即可開始分析。
3. **常用模型名稱**：
   - `gemini-3.8-flash` / `gemini-3.5-flash`（新世代高速模型，可於下拉選單直接選用）
   - `gemini-2.5-flash`（預設，速度快、推理能力佳、免費額度較寬裕）
   - `gemini-2.5-pro`（高階深度推理，適合指派給 `Future Agent` 與 `Risk Agent`）
   - `gemini-2.0-flash`（輕量高速備選）
   - `gemma-4-31b-it` / `gemma-4-26b-it`（Google 開放權重 Gemma 4 指令微調模型，系統已自動相容處理 system prompt 與 JSON 解析）
4. **免費版注意事項**：
   - 免費版有每分鐘請求次數（RPM）限制；本系統已在底層內建 **HTTP 429 指數退避自動重試機制**，若仍遇到頻率超限提示，請稍候約 30 秒再重試，或開啟快取減少重複呼叫。

---

### 2.2 OpenAI API

1. **申請步驟**：
   - 前往 [OpenAI Platform API Keys](https://platform.openai.com/api-keys) 登入並儲值（Pay-as-you-go），點擊 **Create new secret key**（格式為 `sk-...`）。
2. **軟體設定**：
   - 在 **OpenAI API** 欄位貼上金鑰。
   - **Base URL**：維持預設 `https://api.openai.com/v1`（若使用合法企業代理可自行修改）。
3. **常用模型名稱**：
   - `gpt-4o-mini`（低成本、高性價比，適合 `Past` 與 `Present` 新聞彙整）
   - `gpt-4.1-mini` / `gpt-4.1`
   - `gpt-4o`
   - `o3-mini`（推理模型，程式會自動略過不支援的 `temperature` 參數並使用 `max_completion_tokens`）

---

### 2.3 Anthropic Claude API

1. **申請步驟**：
   - 前往 [Anthropic Console](https://console.anthropic.com/) 儲值並建立 API Key（格式為 `sk-ant-...`）。
2. **軟體設定**：
   - 在 **Anthropic Claude API** 欄位貼上金鑰。
   - **Base URL**：維持預設 `https://api.anthropic.com/v1`。
3. **常用模型名稱**：
   - `claude-3-7-sonnet-latest`（邏輯推演與結構化撰寫能力極強，推薦用於 `Future Agent` 與 `Risk Agent`）
   - `claude-sonnet-4-20250514`
   - `claude-3-5-haiku-latest`（輕量快速）

---

### 2.4 DeepSeek API

1. **申請步驟**：
   - 前往 [DeepSeek Open Platform](https://platform.deepseek.com/) 註冊儲值並建立 API Key。
2. **軟體設定**：
   - 在 **DeepSeek API** 欄位貼上金鑰。
   - **Base URL**：維持預設 `https://api.deepseek.com/v1`。
3. **常用模型名稱**：
   - `deepseek-chat`（高性價比通用模型）
   - `deepseek-reasoner`（深度思考推理模型；本系統會自動過濾 `<think>...</think>` 思考過程並提取標準 JSON，非常適合指派給 `Risk Agent` 執行反方壓力測試）

---

### 2.5 Ollama（完全免費・本機離線運行）

如果您重視**極致隱私**（分析資料完全不離開電腦）且希望**零 API 費用**，可在自己電腦上透過 Ollama 運行開源模型。

1. **安裝與準備模型**：
   - 至 [Ollama 官網](https://ollama.com/) 下載並安裝對應版本（Windows / macOS）。
   - 開啟終端機下載推薦的繁體中文與結構化 JSON 表現良好的模型（擇一或依硬體規格挑選）：
     ```bash
     # 16GB RAM 推薦（效能與品質平衡）
     ollama pull qwen2.5:14b
     # 或 8GB RAM 輕量選擇
     ollama pull llama3.1:8b
     # 推理專長模型
     ollama pull deepseek-r1:14b
     ```
   - 確認 Ollama 服務正在背景執行（預設監聽 `http://localhost:11434`）。
2. **軟體設定**：
   - **Ollama (本機模型端點)** 的 **API Key 欄位請留空**。
   - **Base URL**：維持預設 `http://localhost:11434/v1`。
   - 在下方 **「快速一鍵套用至全部 Agent」** 選擇 `ollama` 與您下載的模型名稱（例如 `qwen2.5:14b`），點擊 **「套用至全部 5 個 Agent」**，再按 **「測試連線」** 確認正常即可。

---

### 2.6 自訂 OpenAI-Compatible API（OpenRouter / Groq / LM Studio）

只要支援標準 `/v1/chat/completions` 格式的平台或本地工具，都可以透過 **自訂 OpenAI-Compatible API** 欄位串接：

| 常見服務 | 建議填入之 Base URL | 範例模型名稱 |
|---|---|---|
| **OpenRouter** | `https://openrouter.ai/api/v1` | `meta-llama/llama-3.3-70b-instruct`、`qwen/qwen-2.5-72b-instruct` |
| **Groq** | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| **LM Studio（本機）** | `http://localhost:1234/v1` | 依 LM Studio 載入的模型 ID（API Key 可填 `lm-studio`） |
| **Together AI** | `https://api.together.xyz/v1` | `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo` |

設定方式：填入對應的 **API Key** 與 **Base URL**，並在 Agent 模型指派欄位選擇 `openai_compatible`，手動輸入該平台指定的完整模型名稱。

---

### 2.7 選填：Tavily 財經新聞搜尋 API

- **用途**：提升 `Present Agent` 抓取近 7~14 天新聞內文的精準度與摘要品質。
- **申請方式**：前往 [Tavily](https://tavily.com/) 申請免費方案（提供每月免費搜尋額度，格式為 `tvly-...`）。
- **如果沒有 Tavily Key 怎麼辦？**  
  完全可以留空！系統會自動啟用**免費多來源級聯備援**：`DuckDuckGo News (ddgs)` → `Google News RSS（自動支援繁中台股與英文美股）` → `Yahoo Finance News`。

---

## 3. Multi-Agent 模型混搭與一鍵切換策略

在設定頁的第 2 區塊，您可以：
1. **一鍵統一套用**：使用上方「快速一鍵套用至全部 Agent」，瞬間將 5 個角色全部指定給同一供應商與模型（適合單一免費 Gemini Key 或本機 Ollama）。
2. **進階角色混搭（省錢＋高品質最佳實踐）**：
   - `Past Agent` & `Present Agent`（資料量較大、負責結構化整理）：指派給高速低價模型（如 `gemini-2.5-flash` 或 `gpt-4o-mini`）。
   - `Future Agent`（綜合情境推演）：指派給長文本與邏輯能力強的模型（如 `claude-3-7-sonnet-latest` 或 `gemini-2.5-pro`）。
   - `Risk Agent`（反方審查與盲點偵測）：指派給推理型模型（如 `deepseek-reasoner` 或 `o3-mini`）。
   - `Orchestrator`（總管摘要）：使用 `gemini-2.5-flash` 或 `gpt-4o-mini` 即可。

---

## 4. 股票分析操作步驟

1. 切換至左側 **「趨勢分析工作台」**。
2. 在 **股票代碼** 輸入框填寫標的：
   - **美股**：直接輸入代碼，如 `NVDA`、`AAPL`、`TSLA`、`MSFT`。
   - **台股上市／上櫃**：可輸入完整後綴（如 `2330.TW`、`6488.TWO`），或**直接輸入 4~6 碼數字（如 `2330`、`0050`、`2317`）**，系統會自動嘗試補全 `.TW` 與 `.TWO`。
3. 調整分析參數：
   - **歷史年數**：`1` ~ `5` 年（預設 `2` 年），決定 `Past Agent` 的均線與報酬區間。
   - **新聞回溯**：`3` ~ `30` 天（預設 `10` 天），決定 `Present Agent` 蒐集新聞的時間窗口。
   - **略過快取強制重新抓取**：預設會使用本機 SQLite 快取（預設 60 分鐘有效）節省請求；若盤中有重大突發新聞需即時刷新，請勾選此項。
4. 點擊 **「開始 Multi-Agent 分析」**：
   - 上方 5 階段狀態列與進度條會即時推進（若想中途放棄可點擊 **「中止」**）。
   - 第 2 階段會同時平行執行「過去基本面分析」與「現在新聞蒐集與情緒判讀」。

---

## 5. 報告閱讀、JSON 檢查與本機歷史紀錄

- **KPI 摘要列**：快速顯示最新收盤價與單日漲跌幅、過去估值評價、現在新聞情緒總分（`-1.0` ~ `+1.0`）、風控風險等級與調整後信心指數。
- **完整研究報告 (Markdown)**：支援表格排版、新聞原始連結點擊（自動以系統預設瀏覽器開啟），並可點擊右上方 **「複製 Markdown」** 或 **「匯出 .md 報告」** 存檔分享。
- **Agent JSON 結構檢查器**：可切換檢視 `past_analysis`、`present_analysis`、`future_analysis`、`risk_review` 與 `stock_data` 的原始標準 JSON，方便驗證或二次開發。
- **左側本機歷史報告**：每次完成分析皆會自動存入 `data/app_cache.db`，日後不連網也能點擊歷史項目離線重讀或刪除舊紀錄。

---

## 6. 進階設定：使用 `.env` 預載金鑰

除了透過桌面 GUI 輸入金鑰外，您也可以在專案根目錄複製 `.env.example` 為 `.env`：

```bash
cp .env.example .env
```

填入對應環境變數（如 `GEMINI_API_KEY`、`OPENAI_API_KEY` 等）。若 `config/settings.json` 中該供應商尚未儲存過金鑰，程式啟動時會自動讀取 `.env` 作為預設值，並於儲存時加密寫入 `config/settings.json`。

---

## 7. 常見問題與排查（FAQ）

1. **貼上 Google Gemini API Key 後顯示 `403` 錯誤（PERMISSION_DENIED）**
   - **原因 A（學校／企業帳號受限）**：若您登入 Google AI Studio 的是學校（如 `.edu.tw`）或企業 Google Workspace 帳號，管理員政策常會停用 Gemini Developer API 專案權限。請改用**個人 `@gmail.com` 帳號**前往 [Google AI Studio API Keys](https://aistudio.google.com/apikey) 點選「Create API key」並選擇新建專案（Create API key in new project）。
   - **原因 B（未啟用 Generative Language API）**：若您是到 Google Cloud Console 手動建立的 Key，需前往「API 和服務 → 啟用 API 和服務」搜尋並啟用 **Generative Language API**。
   - **原因 C（API Key 設了網站／Referer 限制）**：若在 Google Cloud Console 將 Key 限制為「網站 (HTTP referrers)」，桌面程式從本機直接發送請求沒有網頁 Referer 會被擋下（403）。請將應用程式限制改為「無」，或僅在 API 限制勾選 **Generative Language API**。
   - **原因 D（剛建立或地區／VPN 限制）**：新建專案約需等待 1~2 分鐘生效；若使用部分區域 VPN 也可能觸發 403。

2. **出現 `[gemini] 免費版 API 觸發頻率限制 (429 Too Many Requests)`**
   - **原因**：Google 免費方案有每分鐘請求上限（RPM），加上本系統一次會呼叫 5 個 Agent（其中兩個平行執行）。
   - **解法**：系統已會自動等待重試最多 3 次；若仍超過限制，請等待 30~60 秒後再點一次分析（先前的股價與新聞已被 SQLite 快取，重跑速度會更快），或將部分 Agent 改指派給 `gemini-2.0-flash` / 本機 Ollama。

2. **使用 Ollama 時顯示網路連線失敗**
   - 請確認電腦背景已啟動 Ollama（可於終端機執行 `ollama list` 測試）。
   - 確認設定頁中的 Ollama Base URL 為 `http://localhost:11434/v1`，且所選模型名稱已在本地下載完成。

3. **找不到台股代碼（例如上櫃股票）**
   - 可明確加上 `.TW`（上市）或 `.TWO`（上櫃），例如 `8069.TWO`、`6488.TWO`。

4. **如何完全清除本機儲存的 API Key 或快取？**
   - 清除快取：可在設定頁點擊 **「清除股價與新聞快取」**（不會刪除歷史報告）。
   - 重設所有金鑰：關閉程式後，刪除 `config/settings.json` 與 `config/.key` 即可。

5. **Windows / macOS 打包後防毒軟體或 Gatekeeper 提示**
   - PyInstaller 打包的單檔 `.exe` 因無商業數位簽章，偶爾會被 Windows Defender 詢問確認；屬於開源打包常見現象，確認來源為本機建置後放行即可。
