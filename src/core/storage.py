"""Local SQLite persistence for stock/news caching and historical analysis reports."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from src.core.config_manager import get_data_dir
from src.core.schemas import FullAnalysisReport, NewsItem, StockDataBundle


class LocalStorage:
    """Thread-safe local SQLite storage in data/app_cache.db."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (get_data_dir() / "app_cache.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS stock_cache (
                    cache_key TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    history_years INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS news_cache (
                    cache_key TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    lookback_days INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_reports (
                    report_id TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    overall_risk_level TEXT NOT NULL,
                    overall_sentiment_score REAL NOT NULL,
                    markdown_report TEXT NOT NULL,
                    report_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_reports_created
                ON analysis_reports (created_at DESC);
                """
            )

    @staticmethod
    def _is_fresh(fetched_at_iso: str, ttl_minutes: int) -> bool:
        if ttl_minutes <= 0:
            return False
        try:
            fetched_dt = datetime.fromisoformat(fetched_at_iso)
            if fetched_dt.tzinfo is None:
                fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            return (now_dt - fetched_dt) < timedelta(minutes=ttl_minutes)
        except Exception:
            return False

    def get_cached_stock_data(
        self, ticker: str, history_years: int, ttl_minutes: int
    ) -> Optional[StockDataBundle]:
        cache_key = f"{ticker.upper()}::{history_years}"
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json, fetched_at FROM stock_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if not row or not self._is_fresh(row["fetched_at"], ttl_minutes):
            return None
        try:
            return StockDataBundle.model_validate_json(row["payload_json"])
        except Exception:
            return None

    def save_stock_data(self, bundle: StockDataBundle) -> None:
        cache_key = f"{bundle.ticker.upper()}::{bundle.history_years}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO stock_cache (cache_key, ticker, history_years, payload_json, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    fetched_at = excluded.fetched_at
                """,
                (cache_key, bundle.ticker.upper(), bundle.history_years, bundle.model_dump_json(), now_iso),
            )

    def get_cached_news(
        self, ticker: str, lookback_days: int, ttl_minutes: int
    ) -> Optional[List[NewsItem]]:
        cache_key = f"{ticker.upper()}::{lookback_days}"
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json, fetched_at FROM news_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if not row or not self._is_fresh(row["fetched_at"], ttl_minutes):
            return None
        try:
            raw_list = json.loads(row["payload_json"])
            return [NewsItem.model_validate(item) for item in raw_list]
        except Exception:
            return None

    def save_news(self, ticker: str, lookback_days: int, items: List[NewsItem]) -> None:
        cache_key = f"{ticker.upper()}::{lookback_days}"
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = json.dumps([item.model_dump(mode="json") for item in items], ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO news_cache (cache_key, ticker, lookback_days, payload_json, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    fetched_at = excluded.fetched_at
                """,
                (cache_key, ticker.upper(), lookback_days, payload, now_iso),
            )

    def save_report(self, report: FullAnalysisReport) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analysis_reports (
                    report_id, ticker, company_name, created_at,
                    overall_risk_level, overall_sentiment_score,
                    markdown_report, report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                    markdown_report = excluded.markdown_report,
                    report_json = excluded.report_json
                """,
                (
                    report.report_id,
                    report.ticker,
                    report.company_name,
                    report.created_at,
                    report.risk_review.overall_risk_level,
                    report.present_analysis.overall_sentiment_score,
                    report.markdown_report,
                    report.model_dump_json(),
                ),
            )

    def list_reports(self, limit: int = 50) -> List[Dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT report_id, ticker, company_name, created_at,
                       overall_risk_level, overall_sentiment_score
                FROM analysis_reports
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def load_report(self, report_id: str) -> Optional[FullAnalysisReport]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT report_json FROM analysis_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        if not row:
            return None
        try:
            return FullAnalysisReport.model_validate_json(row["report_json"])
        except Exception:
            return None

    def delete_report(self, report_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM analysis_reports WHERE report_id = ?", (report_id,))

    def clear_api_caches(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM stock_cache")
            conn.execute("DELETE FROM news_cache")
