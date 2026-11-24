"""Pydantic v2 data contracts passed strictly between tools, agents, and UI."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class StockValidationResult(BaseModel):
    raw_input: str
    normalized_ticker: str
    company_name: str = ""
    exchange: str = ""
    currency: str = "USD"
    market: Literal["US", "TW", "OTHER"] = "OTHER"
    is_valid: bool = False
    error_message: str = ""


class TechnicalIndicators(BaseModel):
    latest_close: Optional[float] = None
    previous_close: Optional[float] = None
    change_1d_pct: Optional[float] = None
    return_1m_pct: Optional[float] = None
    return_3m_pct: Optional[float] = None
    return_6m_pct: Optional[float] = None
    return_1y_pct: Optional[float] = None
    return_period_pct: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    annualized_volatility_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    avg_volume_20d: Optional[float] = None


class FundamentalMetrics(BaseModel):
    sector: str = "N/A"
    industry: str = "N/A"
    market_cap: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    price_to_book: Optional[float] = None
    trailing_eps: Optional[float] = None
    forward_eps: Optional[float] = None
    roe_pct: Optional[float] = None
    profit_margin_pct: Optional[float] = None
    revenue_growth_pct: Optional[float] = None
    earnings_growth_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None
    dividend_yield_pct: Optional[float] = None
    business_summary: str = ""
    recent_financials_summary: List[str] = Field(default_factory=list)


class StockDataBundle(BaseModel):
    ticker: str
    company_name: str
    exchange: str
    currency: str
    market: Literal["US", "TW", "OTHER"]
    history_years: int
    data_as_of: str
    technicals: TechnicalIndicators
    fundamentals: FundamentalMetrics
    monthly_price_checkpoints: List[Dict[str, object]] = Field(default_factory=list)


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: str
    snippet: str
    provider_origin: str = "unknown"


class PastAnalysisOutput(BaseModel):
    ticker: str
    analysis_period: str = Field(description="例如：過去 2 年歷史區間")
    price_trend_summary: str = Field(description="歷史股價走勢、均線結構與動能總結")
    valuation_assessment: Literal["Undervalued", "Fair", "Overvalued", "Uncertain"]
    valuation_rationale: str = Field(description="本益比、股價淨值比與獲利成長對比評估")
    key_financial_highlights: List[str] = Field(default_factory=list)
    historical_catalysts_and_drawdowns: List[str] = Field(default_factory=list)
    fundamental_strengths: List[str] = Field(default_factory=list)
    fundamental_weaknesses: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)


class AnalyzedNewsItem(BaseModel):
    title: str
    source: str
    published_at: str
    url: str
    summary: str
    sentiment_score: float = Field(ge=-1.0, le=1.0, description="-1.0 極度利空 到 +1.0 極度利多")
    sentiment_label: Literal["Bullish", "Neutral", "Bearish"]
    classification: Literal["Fact", "Opinion", "Mixed"]
    relevance_score: float = Field(ge=0.0, le=1.0)


class PresentAnalysisOutput(BaseModel):
    ticker: str
    lookback_days: int
    overall_sentiment_score: float = Field(ge=-1.0, le=1.0)
    sentiment_regime: Literal["Strongly Bullish", "Moderately Bullish", "Neutral", "Moderately Bearish", "Strongly Bearish"]
    dominant_catalysts: List[str] = Field(default_factory=list)
    noise_filtered_count: int = Field(ge=0, default=0)
    analyzed_news: List[AnalyzedNewsItem] = Field(default_factory=list)
    executive_summary: str


class ScenarioForecast(BaseModel):
    scenario_name: Literal["Bull", "Base", "Bear"]
    probability_pct: float = Field(ge=0.0, le=100.0)
    target_price_range: str = Field(description="預估價格區間（含幣別）")
    expected_return_pct: str = Field(description="相對於現價之潛在報酬率區間")
    key_drivers: List[str] = Field(default_factory=list)
    invalidation_triggers: List[str] = Field(default_factory=list)


class HorizonForecast(BaseModel):
    horizon: Literal["1M", "1Q"]
    horizon_label: str
    scenarios: List[ScenarioForecast] = Field(default_factory=list)
    key_indicators_to_watch: List[str] = Field(default_factory=list)


class FutureAnalysisOutput(BaseModel):
    ticker: str
    short_term_1m: HorizonForecast
    medium_term_1q: HorizonForecast
    synthesis_rationale: str = Field(description="結合過去估值基準與現在催化劑之綜合推演邏輯")
    strategic_stance: str = Field(description="整體趨勢定調（非投資建議，僅供情境研判）")


class RiskFactor(BaseModel):
    category: Literal["Macro", "CompanySpecific", "Valuation", "SentimentBias", "BlackSwan"]
    severity: Literal["High", "Medium", "Low"]
    title: str
    description: str
    mitigation_or_watchpoint: str


class RiskReviewOutput(BaseModel):
    ticker: str
    overall_risk_level: Literal["Low", "Moderate", "Elevated", "High", "Extreme"]
    stress_test_verdict: str = Field(description="對 FutureAgent 結論進行壓力測試後的總評")
    blind_spots_detected: List[str] = Field(default_factory=list)
    overinterpreted_news_warnings: List[str] = Field(default_factory=list)
    risk_factors: List[RiskFactor] = Field(default_factory=list)
    devil_advocate_summary: str = Field(description="反方審查員的核心質疑觀點")
    adjusted_confidence_score: float = Field(ge=0.0, le=1.0)


class FullAnalysisReport(BaseModel):
    report_id: str
    ticker: str
    company_name: str
    currency: str
    created_at: str
    history_years: int
    news_lookback_days: int
    stock_data: StockDataBundle
    past_analysis: PastAnalysisOutput
    present_analysis: PresentAnalysisOutput
    future_analysis: FutureAnalysisOutput
    risk_review: RiskReviewOutput
    markdown_report: str
    models_used: Dict[str, str] = Field(default_factory=dict)
    execution_time_seconds: float = 0.0
