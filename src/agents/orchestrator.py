"""Orchestrator Agent: Validates ticker, runs Past & Present in parallel, chains Future -> Risk, and builds final report."""

from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from src.agents.future_agent import FutureStrategistAgent
from src.agents.past_agent import HistoricalFundamentalAgent
from src.agents.present_agent import NewsSentimentAgent
from src.agents.risk_agent import RiskDevilAdvocateAgent
from src.core.config_manager import DEFAULT_BASE_URLS, ResolvedRuntimeSettings
from src.core.llm_gateway import LLMCallConfig, LLMGateway
from src.core.schemas import (
    FullAnalysisReport,
    FutureAnalysisOutput,
    PastAnalysisOutput,
    PresentAnalysisOutput,
    RiskReviewOutput,
    StockDataBundle,
)
from src.core.storage import LocalStorage
from src.tools.news_search import NewsSearchTool
from src.tools.stock_data import StockDataTool


ProgressCallback = Callable[[int, int, str], None]


class AnalysisCancelledError(RuntimeError):
    """Raised when the user cancels a running analysis from the desktop UI."""


def _fmt_num(val: Optional[float], suffix: str = "", decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    return f"{val:,.{decimals}f}{suffix}"


def _fmt_market_cap(val: Optional[float], currency: str) -> str:
    if val is None:
        return "N/A"
    if val >= 1e12:
        return f"{val / 1e12:.2f}T {currency}"
    if val >= 1e9:
        return f"{val / 1e9:.2f}B {currency}"
    if val >= 1e6:
        return f"{val / 1e6:.2f}M {currency}"
    return f"{val:,.0f} {currency}"


class AnalysisOrchestrator:
    """Coordinates the full Past / Present / Future / Risk multi-agent pipeline."""

    def __init__(
        self,
        gateway: LLMGateway | None = None,
        storage: LocalStorage | None = None,
        stock_tool: StockDataTool | None = None,
        news_tool: NewsSearchTool | None = None,
    ) -> None:
        self.gateway = gateway or LLMGateway()
        self.storage = storage or LocalStorage()
        self.stock_tool = stock_tool or StockDataTool()
        self.news_tool = news_tool or NewsSearchTool()

        self.past_agent = HistoricalFundamentalAgent(self.gateway)
        self.present_agent = NewsSentimentAgent(self.gateway)
        self.future_agent = FutureStrategistAgent(self.gateway)
        self.risk_agent = RiskDevilAdvocateAgent(self.gateway)

    @staticmethod
    def _build_llm_config(role: str, runtime: ResolvedRuntimeSettings) -> LLMCallConfig:
        agent_cfg = runtime.settings.agent_models[role]
        provider = agent_cfg.provider
        return LLMCallConfig(
            provider=provider,
            model=agent_cfg.model,
            api_key=runtime.api_keys.get(provider, ""),
            base_url=runtime.settings.base_urls.get(provider, DEFAULT_BASE_URLS.get(provider, "")),
            temperature=agent_cfg.temperature,
            max_tokens=agent_cfg.max_tokens,
        )

    @staticmethod
    def _check_cancel(cancel_event: Optional[threading.Event]) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise AnalysisCancelledError("使用者已中止本次分析任務。")

    def run_pipeline(
        self,
        raw_ticker: str,
        runtime: ResolvedRuntimeSettings,
        history_years: Optional[int] = None,
        news_lookback_days: Optional[int] = None,
        force_refresh: bool = False,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> FullAnalysisReport:
        start_time = time.perf_counter()

        def emit(stage: int, pct: int, msg: str) -> None:
            if progress_cb:
                progress_cb(stage, pct, msg)

        prefs = runtime.settings.preferences
        years = history_years or prefs.history_years
        lookback = news_lookback_days or prefs.news_lookback_days
        ttl = 0 if force_refresh else prefs.cache_ttl_minutes

        # Stage 1: Validate Ticker
        self._check_cancel(cancel_event)
        emit(1, 8, f"正在驗證股票代碼 '{raw_ticker}'...")
        validation = self.stock_tool.validate_ticker(raw_ticker)
        if not validation.is_valid:
            raise ValueError(validation.error_message)

        ticker = validation.normalized_ticker
        emit(1, 15, f"代碼驗證成功：{ticker}（{validation.company_name} / {validation.currency}）")

        # Prepare LLM configs per role
        past_cfg = self._build_llm_config("past_agent", runtime)
        present_cfg = self._build_llm_config("present_agent", runtime)
        future_cfg = self._build_llm_config("future_agent", runtime)
        risk_cfg = self._build_llm_config("risk_agent", runtime)
        orch_cfg = self._build_llm_config("orchestrator", runtime)

        models_used: Dict[str, str] = {
            "orchestrator": f"{orch_cfg.provider}:{orch_cfg.model}",
            "past_agent": f"{past_cfg.provider}:{past_cfg.model}",
            "present_agent": f"{present_cfg.provider}:{present_cfg.model}",
            "future_agent": f"{future_cfg.provider}:{future_cfg.model}",
            "risk_agent": f"{risk_cfg.provider}:{risk_cfg.model}",
        }

        # Stage 2: Parallel execution of Past & Present branches
        self._check_cancel(cancel_event)
        emit(2, 22, "平行啟動 [過去基本面分析] 與 [現在即時新聞蒐集與情緒判讀]...")

        def _past_branch() -> tuple[StockDataBundle, PastAnalysisOutput]:
            self._check_cancel(cancel_event)
            bundle = self.storage.get_cached_stock_data(ticker, years, ttl)
            if bundle is None:
                emit(2, 28, f"從 yfinance 抓取 {ticker} 過去 {years} 年歷史價量與財報數據...")
                bundle = self.stock_tool.fetch_stock_bundle(validation, history_years=years)
                self.storage.save_stock_data(bundle)
            else:
                emit(2, 28, f"命中本機 SQLite 股價快取：{ticker}（{years} 年）")

            self._check_cancel(cancel_event)
            emit(2, 40, f"PastAgent（{past_cfg.provider}/{past_cfg.model}）正在分析歷史位階與估值...")
            past_res = self.past_agent.run(bundle, past_cfg, prefs.report_language)
            return bundle, past_res

        def _present_branch() -> PresentAnalysisOutput:
            self._check_cancel(cancel_event)
            news_items = self.storage.get_cached_news(ticker, lookback, ttl)
            if news_items is None:
                emit(2, 32, f"搜尋 {ticker} 近 {lookback} 天即時財經新聞（Tavily / DuckDuckGo / RSS）...")
                news_items = self.news_tool.search_news(
                    ticker=ticker,
                    company_name=validation.company_name,
                    market=validation.market,
                    lookback_days=lookback,
                    tavily_api_key=runtime.api_keys.get("tavily", ""),
                )
                self.storage.save_news(ticker, lookback, news_items)
            else:
                emit(2, 32, f"命中本機 SQLite 新聞快取：{len(news_items)} 則新聞")

            self._check_cancel(cancel_event)
            emit(2, 46, f"PresentAgent（{present_cfg.provider}/{present_cfg.model}）正在判讀多空情緒與事實分類...")
            return self.present_agent.run(
                ticker=ticker,
                company_name=validation.company_name,
                lookback_days=lookback,
                raw_news=news_items,
                llm_config=present_cfg,
                report_language=prefs.report_language,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            past_future = pool.submit(_past_branch)
            present_future = pool.submit(_present_branch)
            stock_bundle, past_output = past_future.result()
            present_output = present_future.result()

        self._check_cancel(cancel_event)
        emit(3, 60, f"FutureAgent（{future_cfg.provider}/{future_cfg.model}）正在推演未來 1 個月與 1 季三情境...")
        future_output = self.future_agent.run(
            stock_data=stock_bundle,
            past_output=past_output,
            present_output=present_output,
            llm_config=future_cfg,
            report_language=prefs.report_language,
        )

        self._check_cancel(cancel_event)
        emit(4, 78, f"RiskAgent（{risk_cfg.provider}/{risk_cfg.model}）正在執行壓力測試與反方審查...")
        risk_output = self.risk_agent.run(
            stock_data=stock_bundle,
            past_output=past_output,
            present_output=present_output,
            future_output=future_output,
            llm_config=risk_cfg,
            report_language=prefs.report_language,
        )

        self._check_cancel(cancel_event)
        emit(5, 92, f"Orchestrator（{orch_cfg.provider}/{orch_cfg.model}）正在彙整最終研究報告並寫入本機資料庫...")
        executive_synthesis = self._generate_executive_synthesis(
            stock_data=stock_bundle,
            past_output=past_output,
            present_output=present_output,
            future_output=future_output,
            risk_output=risk_output,
            llm_config=orch_cfg,
        )

        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        elapsed = round(time.perf_counter() - start_time, 2)
        report_id = f"{ticker}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        markdown_report = self._render_markdown_report(
            report_id=report_id,
            created_at=created_at,
            elapsed=elapsed,
            models_used=models_used,
            executive_synthesis=executive_synthesis,
            stock_data=stock_bundle,
            past_output=past_output,
            present_output=present_output,
            future_output=future_output,
            risk_output=risk_output,
        )

        full_report = FullAnalysisReport(
            report_id=report_id,
            ticker=ticker,
            company_name=stock_bundle.company_name,
            currency=stock_bundle.currency,
            created_at=created_at,
            history_years=years,
            news_lookback_days=lookback,
            stock_data=stock_bundle,
            past_analysis=past_output,
            present_analysis=present_output,
            future_analysis=future_output,
            risk_review=risk_output,
            markdown_report=markdown_report,
            models_used=models_used,
            execution_time_seconds=elapsed,
        )

        self.storage.save_report(full_report)
        emit(5, 100, f"分析完成！總耗時 {elapsed} 秒，報告已保存至本機資料庫。")
        return full_report

    def _generate_executive_synthesis(
        self,
        stock_data: StockDataBundle,
        past_output: PastAnalysisOutput,
        present_output: PresentAnalysisOutput,
        future_output: FutureAnalysisOutput,
        risk_output: RiskReviewOutput,
        llm_config: LLMCallConfig,
    ) -> str:
        system_prompt = (
            "你是總管協調官（Orchestrator Agent），請將過去基本面、現在新聞情緒、未來情境推演與風控反方審查的結論，"
            "濃縮為 1 段約 150~250 字的繁體中文『總管執行摘要（Executive Verdict）』。"
            "語氣客觀平衡、不構成投資建議，直接輸出純文字段落即可。"
        )
        summary_input = {
            "ticker": stock_data.ticker,
            "company_name": stock_data.company_name,
            "latest_close": stock_data.technicals.latest_close,
            "currency": stock_data.currency,
            "valuation_assessment": past_output.valuation_assessment,
            "sentiment_score": present_output.overall_sentiment_score,
            "sentiment_regime": present_output.sentiment_regime,
            "strategic_stance": future_output.strategic_stance,
            "overall_risk_level": risk_output.overall_risk_level,
            "stress_test_verdict": risk_output.stress_test_verdict,
            "adjusted_confidence_score": risk_output.adjusted_confidence_score,
        }
        try:
            resp = self.gateway.generate_text(
                system_prompt=system_prompt,
                user_prompt=json.dumps(summary_input, ensure_ascii=False, indent=2),
                config=llm_config,
            )
            if resp.text.strip():
                return resp.text.strip()
        except Exception:
            pass

        return (
            f"{stock_data.company_name}（{stock_data.ticker}）最新收盤價為 "
            f"{_fmt_num(stock_data.technicals.latest_close)} {stock_data.currency}。"
            f"歷史估值評估為「{past_output.valuation_assessment}」，近期新聞情緒分數為 "
            f"{present_output.overall_sentiment_score:+.2f}（{present_output.sentiment_regime}）。"
            f"綜合未來趨勢定調：{future_output.strategic_stance}；經風控審查後整體風險等級為 "
            f"「{risk_output.overall_risk_level}」，調整後信心指數 {risk_output.adjusted_confidence_score:.2f}。"
        )

    @staticmethod
    def _render_markdown_report(
        report_id: str,
        created_at: str,
        elapsed: float,
        models_used: Dict[str, str],
        executive_synthesis: str,
        stock_data: StockDataBundle,
        past_output: PastAnalysisOutput,
        present_output: PresentAnalysisOutput,
        future_output: FutureAnalysisOutput,
        risk_output: RiskReviewOutput,
    ) -> str:
        t = stock_data.technicals
        f = stock_data.fundamentals
        cur = stock_data.currency

        lines = [
            f"# {stock_data.company_name}（{stock_data.ticker}）Multi-Agent 股票趨勢研究報告",
            "",
            f"> **免責聲明**：本報告由本機 Multi-Agent 系統自動生成，僅供研究參考與情境推演，不構成任何投資買賣建議。",
            "",
            f"- **報告編號**：`{report_id}`",
            f"- **生成時間**：{created_at}（總耗時 `{elapsed}s`）",
            f"- **行情基準日**：{stock_data.data_as_of} ｜ **交易所 / 幣別**：{stock_data.exchange} / {cur}",
            "",
            "## 總管執行摘要（Orchestrator Verdict）",
            "",
            executive_synthesis,
            "",
            "| 核心指標 | 數值 / 判定 |",
            "|---|---|",
            f"| 最新收盤價 | {_fmt_num(t.latest_close)} {cur}（1D: {_fmt_num(t.change_1d_pct, '%')}） |",
            f"| 市值 / 產業 | {_fmt_market_cap(f.market_cap, cur)} / {f.sector}（{f.industry}） |",
            f"| 過去估值評價 | **{past_output.valuation_assessment}**（信心度 {past_output.confidence_score:.2f}） |",
            f"| 現在情緒分數 | **{present_output.overall_sentiment_score:+.2f}**（{present_output.sentiment_regime}） |",
            f"| 風控審查等級 | **{risk_output.overall_risk_level}**（調整後信心 {risk_output.adjusted_confidence_score:.2f}） |",
            "",
            "---",
            "",
            "## 1. 過去維度：歷史價量與基本面分析（Past Agent）",
            "",
            f"**分析區間**：{past_output.analysis_period}",
            "",
            "### 價格動能與技術指標",
            "| 指標 | 數值 | 指標 | 數值 |",
            "|---|---|---|---|",
            f"| 1M / 3M 報酬 | {_fmt_num(t.return_1m_pct, '%')} / {_fmt_num(t.return_3m_pct, '%')} | SMA 20 / 50 / 200 | {_fmt_num(t.sma_20)} / {_fmt_num(t.sma_50)} / {_fmt_num(t.sma_200)} |",
            f"| 6M / 1Y 報酬 | {_fmt_num(t.return_6m_pct, '%')} / {_fmt_num(t.return_1y_pct, '%')} | RSI (14) | {_fmt_num(t.rsi_14)} |",
            f"| 52 週高低點 | {_fmt_num(t.high_52w)} / {_fmt_num(t.low_52w)} | 年化波動 / 最大回撤 | {_fmt_num(t.annualized_volatility_pct, '%')} / {_fmt_num(t.max_drawdown_pct, '%')} |",
            f"| Trailing / Forward PE | {_fmt_num(f.trailing_pe)} / {_fmt_num(f.forward_pe)} | ROE / 淨利率 | {_fmt_num(f.roe_pct, '%')} / {_fmt_num(f.profit_margin_pct, '%')} |",
            "",
            f"- **歷史走勢總結**：{past_output.price_trend_summary}",
            f"- **估值合理性評估（{past_output.valuation_assessment}）**：{past_output.valuation_rationale}",
            "",
            "### 關鍵財務亮點",
        ]
        for item in past_output.key_financial_highlights:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("### 基本面優勢與弱點")
        for s in past_output.fundamental_strengths:
            lines.append(f"- **[優勢]** {s}")
        for w in past_output.fundamental_weaknesses:
            lines.append(f"- **[弱點]** {w}")
        if past_output.historical_catalysts_and_drawdowns:
            lines.append("")
            lines.append("### 歷史關鍵轉折與回撤觀察")
            for c in past_output.historical_catalysts_and_drawdowns:
                lines.append(f"- {c}")

        lines.extend(
            [
                "",
                "---",
                "",
                f"## 2. 現在維度：近 {present_output.lookback_days} 天即時新聞與情緒判讀（Present Agent）",
                "",
                f"- **整體情緒分數**：`{present_output.overall_sentiment_score:+.2f}`（{present_output.sentiment_regime}）",
                f"- **已過濾重複/無關雜訊數**：{present_output.noise_filtered_count} 則",
                f"- **即時情緒總結**：{present_output.executive_summary}",
                "",
                "### 主要市場催化劑",
            ]
        )
        for cat in present_output.dominant_catalysts:
            lines.append(f"- {cat}")

        if present_output.analyzed_news:
            lines.extend(
                [
                    "",
                    "### 重點新聞情緒拆解",
                    "| 時間 (UTC) | 來源 | 分類 | 情緒分數 | 標題與重點摘要 |",
                    "|---|---|---|---|---|",
                ]
            )
            for n in present_output.analyzed_news:
                safe_title = n.title.replace("|", "\\|")
                safe_summary = n.summary.replace("|", "\\|")
                title_md = f"[{safe_title}]({n.url})" if n.url else safe_title
                lines.append(
                    f"| {n.published_at} | {n.source} | {n.classification} | `{n.sentiment_score:+.2f}` ({n.sentiment_label}) | **{title_md}**<br>{safe_summary} |"
                )

        lines.extend(
            [
                "",
                "---",
                "",
                "## 3. 未來維度：趨勢情境推演（Future Strategist Agent）",
                "",
                f"- **策略定調**：{future_output.strategic_stance}",
                f"- **推演綜合邏輯**：{future_output.synthesis_rationale}",
                "",
            ]
        )

        for horizon_block in (future_output.short_term_1m, future_output.medium_term_1q):
            lines.extend(
                [
                    f"### {horizon_block.horizon_label}（{horizon_block.horizon}）情境矩陣",
                    "| 情境 | 機率 | 目標價格區間 | 預期報酬 | 核心驅動因子 | 情境失效觸發點 |",
                    "|---|---|---|---|---|---|",
                ]
            )
            for sc in horizon_block.scenarios:
                drivers = "；".join(sc.key_drivers).replace("|", "\\|")
                triggers = "；".join(sc.invalidation_triggers).replace("|", "\\|")
                lines.append(
                    f"| **{sc.scenario_name}** | {sc.probability_pct:.0f}% | {sc.target_price_range} | {sc.expected_return_pct} | {drivers} | {triggers} |"
                )
            if horizon_block.key_indicators_to_watch:
                lines.append("")
                lines.append(f"**{horizon_block.horizon} 關鍵觀察指標**：" + "、".join(horizon_block.key_indicators_to_watch))
            lines.append("")

        lines.extend(
            [
                "---",
                "",
                "## 4. 全維度把關：風控與反方審查（Risk & Devil's Advocate Agent）",
                "",
                f"- **整體風險等級**：**{risk_output.overall_risk_level}**",
                f"- **調整後信心指數**：`{risk_output.adjusted_confidence_score:.2f}`",
                f"- **壓力測試總評**：{risk_output.stress_test_verdict}",
                f"- **反方審查核心質疑**：{risk_output.devil_advocate_summary}",
                "",
            ]
        )

        if risk_output.blind_spots_detected:
            lines.append("### 偵測到的研究盲點")
            for b in risk_output.blind_spots_detected:
                lines.append(f"- {b}")
            lines.append("")

        if risk_output.overinterpreted_news_warnings:
            lines.append("### 單一新聞過度解讀 / 情緒偏誤警示")
            for o in risk_output.overinterpreted_news_warnings:
                lines.append(f"- {o}")
            lines.append("")

        if risk_output.risk_factors:
            lines.extend(
                [
                    "### 風險因子清冊",
                    "| 類別 | 嚴重度 | 風險標題 | 說明 | 觀察與避險對策 |",
                    "|---|---|---|---|---|",
                ]
            )
            for rf in risk_output.risk_factors:
                lines.append(
                    f"| {rf.category} | {rf.severity} | {rf.title.replace('|', '/')} | {rf.description.replace('|', '/')} | {rf.mitigation_or_watchpoint.replace('|', '/')} |"
                )

        lines.extend(
            [
                "",
                "---",
                "",
                "## 執行模型紀錄（Model Provenance）",
                "",
                "| Agent 角色 | 使用供應商與模型 |",
                "|---|---|",
            ]
        )
        for role, model_id in models_used.items():
            lines.append(f"| `{role}` | `{model_id}` |")

        return "\n".join(lines)
