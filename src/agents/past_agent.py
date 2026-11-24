"""Past Dimension Agent: Historical price action, technicals, and fundamental valuation."""

from __future__ import annotations

import json

from src.core.llm_gateway import LLMCallConfig, LLMGateway
from src.core.schemas import PastAnalysisOutput, StockDataBundle


class HistoricalFundamentalAgent:
    """Analyzes 1-3 year historical prices, technical indicators, and financial fundamentals."""

    def __init__(self, gateway: LLMGateway) -> None:
        self.gateway = gateway

    def run(
        self,
        stock_data: StockDataBundle,
        llm_config: LLMCallConfig,
        report_language: str = "zh-TW",
    ) -> PastAnalysisOutput:
        system_prompt = (
            "你是一位資深買方基本面與技術面分析師（Historical & Fundamental Agent）。\n"
            "你的職責是根據提供的過去 1~3 年歷史股價數據、技術指標（均線、RSI、MACD、波動率、最大回撤）"
            "與財務基本面數據（本益比、EPS、ROE、營收獲利成長率、季報摘要），客觀評估該標的之歷史位階與估值合理性。\n"
            f"所有文字欄位請使用 {report_language}（繁體中文）撰寫，專業、精煉且嚴格根據提供的數字推論，禁止捏造未提供之財報數字。"
        )

        payload_json = json.dumps(stock_data.model_dump(mode="json"), ensure_ascii=False, indent=2)
        user_prompt = (
            f"請分析標的 {stock_data.ticker}（{stock_data.company_name}）過去 {stock_data.history_years} 年的歷史數據與基本面：\n\n"
            f"{payload_json}\n\n"
            "請產出 PastAnalysisOutput JSON，必須完整填寫：\n"
            "- analysis_period\n"
            "- price_trend_summary（均線排列、動能、波動與最大回撤評估）\n"
            "- valuation_assessment（Undervalued / Fair / Overvalued / Uncertain 四選一）\n"
            "- valuation_rationale\n"
            "- key_financial_highlights（3~5 點具體數據摘要）\n"
            "- historical_catalysts_and_drawdowns（過去區間的強弱勢結構與風險回撤觀察）\n"
            "- fundamental_strengths 與 fundamental_weaknesses\n"
            "- confidence_score（0.0 到 1.0，視數據完整度給分）"
        )

        result = self.gateway.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_cls=PastAnalysisOutput,
            config=llm_config,
        )
        result.ticker = stock_data.ticker
        return result
