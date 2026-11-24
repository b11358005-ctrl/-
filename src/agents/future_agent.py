"""Future Dimension Agent: Short-term (1M) & Medium-term (1Q) Bull/Base/Bear scenario modeling."""

from __future__ import annotations

import json

from src.core.llm_gateway import LLMCallConfig, LLMGateway
from src.core.schemas import (
    FutureAnalysisOutput,
    PastAnalysisOutput,
    PresentAnalysisOutput,
    StockDataBundle,
)


class FutureStrategistAgent:
    """Synthesizes past valuation baselines and present catalysts into 1M & 1Q scenario forecasts."""

    def __init__(self, gateway: LLMGateway) -> None:
        self.gateway = gateway

    def run(
        self,
        stock_data: StockDataBundle,
        past_output: PastAnalysisOutput,
        present_output: PresentAnalysisOutput,
        llm_config: LLMCallConfig,
        report_language: str = "zh-TW",
    ) -> FutureAnalysisOutput:
        system_prompt = (
            "你是一位首席量化與總經趨勢策略師（Future Strategist Agent）。\n"
            "你的職責是將『過去的估值與技術面基準（Past）』與『現在的即時新聞與市場情緒催化劑（Present）』進行結構化結合，"
            "推演未來 1 個月（short_term_1m，horizon='1M'）與未來 1 季（medium_term_1q，horizon='1Q'）的三種情境：\n"
            "- Bull（樂觀情境）\n"
            "- Base（基準情境）\n"
            "- Bear（悲觀情境）\n"
            "每個時間維度內三種情境的 probability_pct 加總必須等於 100。\n"
            "請提供具體的目標價格區間（標明幣別）、相對於最新收盤價的預期報酬率區間、核心驅動因子與情境失效觸發條件（invalidation_triggers），"
            "並列出接下來最應追蹤的關鍵觀察指標。\n"
            f"請使用 {report_language}（繁體中文）撰寫，避免過度武斷或單一方向喊單，保持專業客觀情境分析。"
        )

        context_bundle = {
            "ticker": stock_data.ticker,
            "company_name": stock_data.company_name,
            "currency": stock_data.currency,
            "latest_close": stock_data.technicals.latest_close,
            "high_52w": stock_data.technicals.high_52w,
            "low_52w": stock_data.technicals.low_52w,
            "past_analysis": past_output.model_dump(mode="json"),
            "present_analysis": {
                "overall_sentiment_score": present_output.overall_sentiment_score,
                "sentiment_regime": present_output.sentiment_regime,
                "dominant_catalysts": present_output.dominant_catalysts,
                "executive_summary": present_output.executive_summary,
                "top_news_highlights": [
                    {
                        "title": n.title,
                        "published_at": n.published_at,
                        "sentiment_score": n.sentiment_score,
                        "classification": n.classification,
                        "summary": n.summary,
                    }
                    for n in present_output.analyzed_news[:8]
                ],
            },
        }

        user_prompt = (
            "請根據以下過去基本面與現在即時情緒輸入，進行未來 1 個月與 1 季的三情境推演：\n\n"
            f"{json.dumps(context_bundle, ensure_ascii=False, indent=2)}\n\n"
            "請產出嚴格符合 FutureAnalysisOutput Schema 的 JSON。"
        )

        result = self.gateway.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_cls=FutureAnalysisOutput,
            config=llm_config,
        )
        result.ticker = stock_data.ticker
        result.short_term_1m.horizon = "1M"
        result.medium_term_1q.horizon = "1Q"
        return result
