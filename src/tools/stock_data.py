"""Stock historical price, technical indicator, and fundamental data tool via yfinance."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

from src.core.schemas import (
    FundamentalMetrics,
    StockDataBundle,
    StockValidationResult,
    TechnicalIndicators,
)


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


def _safe_pct(val: Any, already_percent: bool = False) -> Optional[float]:
    f = _safe_float(val)
    if f is None:
        return None
    return round(f if already_percent else f * 100.0, 2)


def _detect_market(ticker: str) -> str:
    upper = ticker.upper()
    if upper.endswith(".TW") or upper.endswith(".TWO"):
        return "TW"
    if "." not in upper:
        return "US"
    return "OTHER"


def _candidate_tickers(raw_input: str) -> List[str]:
    cleaned = raw_input.strip().upper()
    if not cleaned:
        return []
    # Taiwan stock codes (e.g. 2330, 0050, 00631L, 6488) without suffix
    if re.fullmatch(r"\d{4,6}[A-Z]?", cleaned):
        return [f"{cleaned}.TW", f"{cleaned}.TWO"]
    return [cleaned]


class StockDataTool:
    """Fetches and normalizes multi-year stock history and fundamentals."""

    def validate_ticker(self, raw_input: str) -> StockValidationResult:
        candidates = _candidate_tickers(raw_input)
        if not candidates:
            return StockValidationResult(
                raw_input=raw_input,
                normalized_ticker="",
                is_valid=False,
                error_message="請輸入有效的股票代碼（例如 NVDA 或 2330.TW）。",
            )

        last_err = ""
        for candidate in candidates:
            try:
                ticker_obj = yf.Ticker(candidate)
                hist = ticker_obj.history(period="1mo", interval="1d")
                if hist is not None and not hist.empty:
                    info: Dict[str, Any] = {}
                    try:
                        info = ticker_obj.info or {}
                    except Exception:
                        info = {}

                    company_name = (
                        info.get("longName")
                        or info.get("shortName")
                        or candidate
                    )
                    currency = info.get("currency") or ("TWD" if candidate.endswith((".TW", ".TWO")) else "USD")
                    exchange = info.get("exchange") or ("TWSE" if candidate.endswith(".TW") else "TPEx" if candidate.endswith(".TWO") else "")
                    market = _detect_market(candidate)
                    return StockValidationResult(
                        raw_input=raw_input,
                        normalized_ticker=candidate,
                        company_name=str(company_name),
                        exchange=str(exchange),
                        currency=str(currency),
                        market=market,  # type: ignore[arg-type]
                        is_valid=True,
                    )
            except Exception as exc:
                last_err = str(exc)

        return StockValidationResult(
            raw_input=raw_input,
            normalized_ticker=candidates[0],
            is_valid=False,
            error_message=f"找不到股票代碼 '{raw_input}' 的交易資料。{(' 原因：' + last_err) if last_err else ''}",
        )

    def fetch_stock_bundle(
        self,
        validation: StockValidationResult,
        history_years: int = 2,
    ) -> StockDataBundle:
        ticker = validation.normalized_ticker
        ticker_obj = yf.Ticker(ticker)
        period_str = f"{max(1, min(history_years, 5))}y"

        hist = ticker_obj.history(period=period_str, interval="1d", auto_adjust=True)
        if hist is None or hist.empty:
            raise ValueError(f"無法取得 {ticker} 過去 {history_years} 年歷史股價資料。")

        hist = hist.dropna(subset=["Close"]).copy()
        close = hist["Close"].astype(float)
        volume = hist["Volume"].astype(float) if "Volume" in hist.columns else pd.Series(dtype=float)

        latest_close = float(close.iloc[-1])
        previous_close = float(close.iloc[-2]) if len(close) >= 2 else latest_close
        change_1d_pct = ((latest_close / previous_close) - 1.0) * 100.0 if previous_close else 0.0

        def _lookback_return(trading_days: int) -> Optional[float]:
            if len(close) <= trading_days:
                return None
            base = float(close.iloc[-1 - trading_days])
            if base == 0:
                return None
            return round(((latest_close / base) - 1.0) * 100.0, 2)

        return_period_pct = None
        if len(close) >= 2 and float(close.iloc[0]) != 0:
            return_period_pct = round(((latest_close / float(close.iloc[0])) - 1.0) * 100.0, 2)

        sma_20 = _safe_float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
        sma_50 = _safe_float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
        sma_200 = _safe_float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

        # RSI 14
        rsi_14 = None
        if len(close) >= 15:
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            last_gain = float(gain.iloc[-1])
            last_loss = float(loss.iloc[-1])
            if last_loss == 0:
                rsi_14 = 100.0 if last_gain > 0 else 50.0
            else:
                rs = last_gain / last_loss
                rsi_14 = round(100.0 - (100.0 / (1.0 + rs)), 2)

        # MACD (12, 26, 9)
        macd_val = None
        macd_sig = None
        if len(close) >= 35:
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_series = ema12 - ema26
            signal_series = macd_series.ewm(span=9, adjust=False).mean()
            macd_val = _safe_float(macd_series.iloc[-1])
            macd_sig = _safe_float(signal_series.iloc[-1])

        # Annualized volatility & Max Drawdown
        daily_ret = close.pct_change().dropna()
        ann_vol = round(float(daily_ret.std() * math.sqrt(252) * 100.0), 2) if len(daily_ret) >= 10 else None
        running_max = close.cummax()
        drawdown = (close / running_max) - 1.0
        max_dd = round(float(drawdown.min() * 100.0), 2) if not drawdown.empty else None

        recent_252 = close.iloc[-252:] if len(close) >= 252 else close
        high_52w = _safe_float(recent_252.max())
        low_52w = _safe_float(recent_252.min())
        avg_vol_20d = _safe_float(volume.tail(20).mean()) if len(volume) >= 1 else None

        technicals = TechnicalIndicators(
            latest_close=_safe_float(latest_close),
            previous_close=_safe_float(previous_close),
            change_1d_pct=round(change_1d_pct, 2),
            return_1m_pct=_lookback_return(21),
            return_3m_pct=_lookback_return(63),
            return_6m_pct=_lookback_return(126),
            return_1y_pct=_lookback_return(252),
            return_period_pct=return_period_pct,
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            rsi_14=rsi_14,
            macd=macd_val,
            macd_signal=macd_sig,
            annualized_volatility_pct=ann_vol,
            max_drawdown_pct=max_dd,
            high_52w=high_52w,
            low_52w=low_52w,
            avg_volume_20d=avg_vol_20d,
        )

        # Fundamentals
        info: Dict[str, Any] = {}
        try:
            info = ticker_obj.info or {}
        except Exception:
            info = {}

        recent_fin_lines: List[str] = []
        try:
            q_fin = ticker_obj.quarterly_income_stmt
            if q_fin is not None and not q_fin.empty:
                for col in list(q_fin.columns)[:4]:
                    col_label = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
                    rev = None
                    net_inc = None
                    for key in ("Total Revenue", "Operating Revenue"):
                        if key in q_fin.index:
                            rev = _safe_float(q_fin.loc[key, col])
                            break
                    for key in ("Net Income", "Net Income Common Stockholders"):
                        if key in q_fin.index:
                            net_inc = _safe_float(q_fin.loc[key, col])
                            break
                    if rev is not None or net_inc is not None:
                        rev_str = f"{rev:,.0f}" if rev is not None else "N/A"
                        ni_str = f"{net_inc:,.0f}" if net_inc is not None else "N/A"
                        recent_fin_lines.append(f"季報 {col_label}: 營收 {rev_str}, 淨利 {ni_str}")
        except Exception:
            pass

        raw_div = info.get("dividendYield")
        # yfinance dividendYield can be fraction (0.025) or already percentage depending on version
        div_pct = None
        if raw_div is not None:
            f_div = _safe_float(raw_div)
            if f_div is not None:
                div_pct = round(f_div if f_div > 1.0 else f_div * 100.0, 2)

        summary_text = str(info.get("longBusinessSummary") or "").strip()
        if len(summary_text) > 700:
            summary_text = summary_text[:700] + "..."

        fundamentals = FundamentalMetrics(
            sector=str(info.get("sector") or "N/A"),
            industry=str(info.get("industry") or "N/A"),
            market_cap=_safe_float(info.get("marketCap")),
            trailing_pe=_safe_float(info.get("trailingPE")),
            forward_pe=_safe_float(info.get("forwardPE")),
            price_to_book=_safe_float(info.get("priceToBook")),
            trailing_eps=_safe_float(info.get("trailingEps")),
            forward_eps=_safe_float(info.get("forwardEps")),
            roe_pct=_safe_pct(info.get("returnOnEquity")),
            profit_margin_pct=_safe_pct(info.get("profitMargins")),
            revenue_growth_pct=_safe_pct(info.get("revenueGrowth")),
            earnings_growth_pct=_safe_pct(info.get("earningsGrowth")),
            debt_to_equity=_safe_float(info.get("debtToEquity")),
            dividend_yield_pct=div_pct,
            business_summary=summary_text,
            recent_financials_summary=recent_fin_lines,
        )

        # Monthly price checkpoints for concise historical trajectory context
        monthly_df = hist.resample("ME").last() if hasattr(hist.index, "tz") else hist
        checkpoints: List[Dict[str, object]] = []
        for idx, row in monthly_df.tail(24).iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            checkpoints.append(
                {
                    "date": date_str,
                    "close": _safe_float(row["Close"]),
                }
            )

        last_idx = hist.index[-1]
        data_as_of = last_idx.strftime("%Y-%m-%d") if hasattr(last_idx, "strftime") else datetime.now(timezone.utc).strftime("%Y-%m-%d")

        return StockDataBundle(
            ticker=ticker,
            company_name=str(info.get("longName") or info.get("shortName") or validation.company_name or ticker),
            exchange=str(info.get("exchange") or validation.exchange),
            currency=str(info.get("currency") or validation.currency),
            market=validation.market,
            history_years=history_years,
            data_as_of=data_as_of,
            technicals=technicals,
            fundamentals=fundamentals,
            monthly_price_checkpoints=checkpoints,
        )
