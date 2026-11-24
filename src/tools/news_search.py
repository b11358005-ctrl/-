"""Multi-source financial news search & cleaning tool (Tavily -> DuckDuckGo -> RSS/yfinance)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Set
from urllib.parse import quote_plus, urlparse, urlunparse

import feedparser
import httpx
import yfinance as yf
from bs4 import BeautifulSoup

from src.core.schemas import NewsItem


def _clean_html(text: str) -> str:
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", cleaned).strip()


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))


def _parse_datetime(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    try:
        dt = parsedate_to_datetime(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _normalize_title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", title.lower())[:48]


class NewsSearchTool:
    """Aggregates recent financial news from Tavily, DuckDuckGo, Google News RSS, and yfinance."""

    def search_news(
        self,
        ticker: str,
        company_name: str,
        market: str,
        lookback_days: int = 10,
        tavily_api_key: str = "",
        max_items: int = 20,
    ) -> List[NewsItem]:
        collected: List[NewsItem] = []

        # Build market-appropriate queries
        clean_company = re.sub(r"\b(Inc\.?|Corp\.?|Corporation|Ltd\.?|Co\.?,?)\b", "", company_name, flags=re.IGNORECASE).strip()
        base_label = clean_company or ticker
        if market == "TW":
            code = ticker.split(".")[0]
            queries = [
                f"{code} {base_label} 股票 財報 新聞",
                f"{ticker} {base_label} stock news",
            ]
        else:
            queries = [
                f"{ticker} {base_label} stock earnings news",
                f"{ticker} analyst outlook catalyst",
            ]

        # 1. Tavily Search API (if key provided)
        if tavily_api_key.strip():
            for q in queries[:2]:
                collected.extend(
                    self._fetch_tavily(
                        query=q,
                        api_key=tavily_api_key.strip(),
                        lookback_days=lookback_days,
                    )
                )

        # 2. DuckDuckGo Search (free fallback / supplement)
        if len(collected) < max_items:
            for q in queries[:2]:
                collected.extend(self._fetch_ddgs(query=q, lookback_days=lookback_days))

        # 3. Google News RSS (free reliable fallback, strong coverage for TW & US)
        if len(collected) < max_items:
            if market == "TW":
                code = ticker.split(".")[0]
                collected.extend(
                    self._fetch_google_rss(
                        query=f"{code} {base_label} 股價 OR 財報",
                        hl="zh-TW",
                        gl="TW",
                        ceid="TW:zh-Hant",
                    )
                )
            collected.extend(
                self._fetch_google_rss(
                    query=f"{ticker} {base_label} stock",
                    hl="en-US",
                    gl="US",
                    ceid="US:en",
                )
            )

        # 4. yfinance built-in news
        if len(collected) < max_items:
            collected.extend(self._fetch_yfinance_news(ticker))

        return self._deduplicate_and_filter(
            items=collected,
            lookback_days=lookback_days,
            max_items=max_items,
        )

    def _fetch_tavily(self, query: str, api_key: str, lookback_days: int) -> List[NewsItem]:
        results: List[NewsItem] = []
        payload = {
            "api_key": api_key,
            "query": query,
            "topic": "news",
            "days": max(1, min(lookback_days, 30)),
            "search_depth": "advanced",
            "max_results": 10,
            "include_raw_content": False,
        }
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post("https://api.tavily.com/search", json=payload)
            if resp.status_code >= 400:
                return results
            data = resp.json()
            for item in data.get("results") or []:
                url = str(item.get("url") or "")
                source = urlparse(url).netloc or "Tavily"
                results.append(
                    NewsItem(
                        title=_clean_html(str(item.get("title") or "")),
                        url=url,
                        source=source,
                        published_at=str(item.get("published_date") or datetime.now(timezone.utc).isoformat()),
                        snippet=_clean_html(str(item.get("content") or ""))[:600],
                        provider_origin="tavily",
                    )
                )
        except Exception:
            pass
        return results

    def _fetch_ddgs(self, query: str, lookback_days: int) -> List[NewsItem]:
        results: List[NewsItem] = []
        ddgs_cls = None
        try:
            from ddgs import DDGS  # type: ignore

            ddgs_cls = DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS  # type: ignore

                ddgs_cls = DDGS
            except ImportError:
                return results

        timelimit = "w" if lookback_days <= 7 else "m"
        try:
            with ddgs_cls() as ddgs:
                raw_news = list(ddgs.news(query, timelimit=timelimit, max_results=10))
                for item in raw_news:
                    url = str(item.get("url") or "")
                    results.append(
                        NewsItem(
                            title=_clean_html(str(item.get("title") or "")),
                            url=url,
                            source=str(item.get("source") or urlparse(url).netloc or "DuckDuckGo"),
                            published_at=str(item.get("date") or datetime.now(timezone.utc).isoformat()),
                            snippet=_clean_html(str(item.get("body") or ""))[:600],
                            provider_origin="duckduckgo",
                        )
                    )
        except Exception:
            pass
        return results

    def _fetch_google_rss(
        self,
        query: str,
        hl: str,
        gl: str,
        ceid: str,
    ) -> List[NewsItem]:
        results: List[NewsItem] = []
        encoded = quote_plus(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.get(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code >= 400:
                return results
            feed = feedparser.parse(resp.text)
            for entry in (feed.entries or [])[:12]:
                source_title = ""
                if hasattr(entry, "source") and isinstance(entry.source, dict):
                    source_title = str(entry.source.get("title") or "")
                title = _clean_html(str(getattr(entry, "title", "")))
                summary = _clean_html(str(getattr(entry, "summary", "")))
                results.append(
                    NewsItem(
                        title=title,
                        url=str(getattr(entry, "link", "")),
                        source=source_title or "Google News",
                        published_at=str(getattr(entry, "published", "") or datetime.now(timezone.utc).isoformat()),
                        snippet=summary[:500] if summary else title,
                        provider_origin="google_rss",
                    )
                )
        except Exception:
            pass
        return results

    def _fetch_yfinance_news(self, ticker: str) -> List[NewsItem]:
        results: List[NewsItem] = []
        try:
            raw_items = yf.Ticker(ticker).news or []
            for item in raw_items[:10]:
                # Support both older and newer yfinance news dict structures
                content = item.get("content") if isinstance(item.get("content"), dict) else item
                title = _clean_html(str(content.get("title") or ""))
                summary = _clean_html(str(content.get("summary") or content.get("description") or title))
                pub_date = content.get("pubDate") or content.get("providerPublishTime") or ""
                if isinstance(pub_date, (int, float)):
                    pub_str = datetime.fromtimestamp(pub_date, tz=timezone.utc).isoformat()
                else:
                    pub_str = str(pub_date or datetime.now(timezone.utc).isoformat())

                url = ""
                if isinstance(content.get("canonicalUrl"), dict):
                    url = str(content["canonicalUrl"].get("url") or "")
                elif isinstance(content.get("clickThroughUrl"), dict):
                    url = str(content["clickThroughUrl"].get("url") or "")
                else:
                    url = str(content.get("link") or "")

                provider = ""
                if isinstance(content.get("provider"), dict):
                    provider = str(content["provider"].get("displayName") or "")
                else:
                    provider = str(content.get("publisher") or "Yahoo Finance")

                if title:
                    results.append(
                        NewsItem(
                            title=title,
                            url=url,
                            source=provider or "Yahoo Finance",
                            published_at=pub_str,
                            snippet=summary[:600],
                            provider_origin="yfinance",
                        )
                    )
        except Exception:
            pass
        return results

    def _deduplicate_and_filter(
        self,
        items: List[NewsItem],
        lookback_days: int,
        max_items: int,
    ) -> List[NewsItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days + 1)
        seen_urls: Set[str] = set()
        seen_titles: Set[str] = set()
        cleaned: List[tuple[datetime, NewsItem]] = []

        for item in items:
            if not item.title or len(item.title) < 6:
                continue

            c_url = _canonical_url(item.url)
            t_key = _normalize_title_key(item.title)
            if (c_url and c_url in seen_urls) or (t_key and t_key in seen_titles):
                continue

            parsed_dt = _parse_datetime(item.published_at)
            if parsed_dt is not None and parsed_dt < cutoff:
                continue

            sort_dt = parsed_dt or datetime.now(timezone.utc)
            item.published_at = sort_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            if c_url:
                seen_urls.add(c_url)
            if t_key:
                seen_titles.add(t_key)
            cleaned.append((sort_dt, item))

        cleaned.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in cleaned[:max_items]]
