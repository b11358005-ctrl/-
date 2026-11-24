"""Risk & Devil's Advocate Agent: Stress testing, blind-spot detection, and overinterpretation checks."""

from __future__ import annotations

import json

from src.core.llm_gateway import LLMCallConfig, LLMGateway
from src.core.schemas import (
    FutureAnalysisOutput,
    PastAnalysisOutput,
    PresentAnalysisOutput,
    RiskReviewOutput,
    StockDataBundle,
)


class RiskDevilAdvocateAgent:
    """Challenges upstream assumptions to surface black swans, macro headwinds, and news bias."""

    def __init__(self, gateway: LLMGateway) -> None:
        self.gateway = gateway

    def run(
        self,
        stock_data: StockDataBundle,
        past_output: PastAnalysisOutput,
        present_output: PresentAnalysisOutput,
        future_output: FutureAnalysisOutput,
        llm_config: LLMCallConfig,
        report_language: str = "zh-TW",
    ) -> RiskReviewOutput:
        system_prompt = (
            "你是一位獨立且嚴格的機構風控長暨反方審查員（Risk & Devil's Advocate Agent）。\n"
            "你的唯一任務是『挑毛病與壓力測試』：批判性地審查 Past / Present / Future 三位分析師的推論，"
            "專注於揭露：\n"
            "1. 總體經濟逆風（利率、匯率、關稅、產業庫存循環）\n"
            "2. 估值陷阱或波動率與最大回撤風險\n"
            "3. 單一新聞過度解讀、意見型評論被誤當作事實（Fact vs. Opinion 混淆）或市場共識過度擁擠\n"
            "4. 潛在黑天鵝與極端下行情境\n"
            "5. 對推演結論給出壓力測試評語 stress_test_verdict 與調整後信心分數 adjusted_confidence_score（0.0~1.0）。\n"
            f"請使用 {report_language}（繁體中文）撰寫，立場必須保持獨立與審慎。"
        )

        review_bundle = {
            "ticker": stock_data.ticker,
            "company_name": stock_data.company_name,
            "annualized_volatility_pct": stock_data.technicals.annualized_volatility_pct,
            "max_drawdown_pct": stock_data.technicals.max_drawdown_pct,
            "debt_to_equity": stock_data.fundamentals.debt_to_equity,
            "trailing_pe": stock_data.fundamentals.trailing_pe,
            "past_analysis": past_output.model_dump(mode="json"),
            "present_analysis_summary": {
                "overall_sentiment_score": present_output.overall_sentiment_score,
                "sentiment_regime": present_output.sentiment_regime,
                "dominant_catalysts": present_output.dominant_catalysts,
                "executive_summary": present_output.executive_summary,
                "news_classifications": [
                    {
                        "title": n.title,
                        "classification": n.classification,
                        "sentiment_score": n.sentiment_score,
                    }
                    for n in present_output.analyzed_news
                ],
            },
            "future_analysis": future_output.model_dump(mode="json"),
        }

        user_prompt = (
            "請針對以下完整的多維度分析結果執行風控與反方審查：\n\n"
            f"{json.dumps(review_bundle, ensure_ascii=False, indent=2)}\n\n"
            "請產出嚴格符合 RiskReviewOutput Schema 的 JSON。"
        )

        result = self.gateway.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_cls=RiskReviewOutput,
            config=llm_config,
        )
        result.ticker = stock_data.ticker
        return result
