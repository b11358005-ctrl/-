"""Present Dimension Agent: Live financial news filtering, sentiment scoring, and fact/opinion classification."""

from __future__ import annotations

import json
from typing import List

from src.core.llm_gateway import LLMCallConfig, LLMGateway
from src.core.schemas import NewsItem, PresentAnalysisOutput


class NewsSentimentAgent:
    """Evaluates recent financial news for relevance, fact vs. opinion, and [-1.0, +1.0] sentiment."""

    def __init__(self, gateway: LLMGateway) -> None:
        self.gateway = gateway

    def run(
        self,
        ticker: str,
        company_name: str,
        lookback_days: int,
        raw_news: List[NewsItem],
        llm_config: LLMCallConfig,
        report_language: str = "zh-TW",
    ) -> PresentAnalysisOutput:
        if not raw_news:
            return PresentAnalysisOutput(
                ticker=ticker,
                lookback_days=lookback_days,
                overall_sentiment_score=0.0,
                sentiment_regime="Neutral",
                dominant_catalysts=["近期搜尋管道未取得顯著即時財經新聞，建議確認網路連線或設定 Tavily Search API Key。"],
                noise_filtered_count=0,
                analyzed_news=[],
                executive_summary="近期新聞樣本不足，市場即時情緒暫時判定為中性。",
            )

        system_prompt = (
            "你是一位華爾街即時財經新聞與市場情緒分析師（News & Sentiment Agent）。\n"
            "你的職責是檢視近 7~14 天蒐集到的財經新聞清單，過濾重複或無關雜訊，保留每則新聞的發布時間戳記與 URL，"
            "並針對每則高相關新聞進行：\n"
            "1. 多空情緒打分 sentiment_score（介於 -1.0 極度利空 與 +1.0 極度利多 之間）\n"
            "2. 情緒標籤 sentiment_label（Bullish / Neutral / Bearish）\n"
            "3. 性質分類 classification（Fact 客觀財報或事件事實 / Opinion 市場評論或目標價觀點 / Mixed 混合）\n"
            "4. 相關性分數 relevance_score（0.0 到 1.0）\n"
            f"所有摘要與總結請使用 {report_language}（繁體中文），嚴禁竄改原始新聞的時間戳記與 URL。"
        )

        news_payload = json.dumps(
            [item.model_dump(mode="json") for item in raw_news],
            ensure_ascii=False,
            indent=2,
        )
        user_prompt = (
            f"標的：{ticker}（{company_name}）\n"
            f"回溯天數：近 {lookback_days} 天\n"
            f"原始新聞共 {len(raw_news)} 則：\n\n"
            f"{news_payload}\n\n"
            "請剔除與該標的完全無關或過度重複的雜訊（並將剔除數量記錄於 noise_filtered_count），"
            "對保留的關鍵新聞（最多 12 則）逐一評分，最後給出整體情緒分數 overall_sentiment_score、"
            "情緒區間 sentiment_regime、主要催化劑 dominant_catalysts 與即時新聞執行摘要 executive_summary。"
        )

        result = self.gateway.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_cls=PresentAnalysisOutput,
            config=llm_config,
        )
        result.ticker = ticker
        result.lookback_days = lookback_days
        return result
