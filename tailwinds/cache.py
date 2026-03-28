"""SQLite cache for tailwind news data."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from config import CACHE_DIR, TAILWIND_NEWS_CACHE_EXPIRY_HOURS


TAILWIND_CACHE_DB = CACHE_DIR / "tailwind_cache.db"


class TailwindCache:
    """SQLite-backed cache for news and tailwind scores."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or TAILWIND_CACHE_DB
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS news_cache (
                    source TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sector_scores (
                    sector TEXT PRIMARY KEY,
                    score_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def _is_expired(self, updated_at_str: str) -> bool:
        updated_at = datetime.fromisoformat(updated_at_str)
        return datetime.now() - updated_at > timedelta(
            hours=TAILWIND_NEWS_CACHE_EXPIRY_HOURS
        )

    # --- News cache ---

    def get_news(self, source: str) -> Optional[List[Dict]]:
        """Get cached news items for a source if not expired."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data_json, updated_at FROM news_cache WHERE source = ?",
                (source,),
            ).fetchone()

        if row is None or self._is_expired(row[1]):
            return None
        return json.loads(row[0])

    def set_news(self, source: str, items: List[Dict]):
        """Cache news items for a source."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO news_cache (source, data_json, updated_at)
                   VALUES (?, ?, ?)""",
                (source, json.dumps(items, default=str), datetime.now().isoformat()),
            )

    def get_all_news(self) -> List[Dict]:
        """Get all non-expired cached news items."""
        result = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT data_json, updated_at FROM news_cache"
            ).fetchall()

        for data_json, updated_at in rows:
            if not self._is_expired(updated_at):
                result.extend(json.loads(data_json))
        return result

    # --- Sector scores ---

    def get_sector_score(self, sector: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT score_json, updated_at FROM sector_scores WHERE sector = ?",
                (sector,),
            ).fetchone()

        if row is None or self._is_expired(row[1]):
            return None
        return json.loads(row[0])

    def set_sector_score(self, sector: str, score_dict: Dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO sector_scores (sector, score_json, updated_at)
                   VALUES (?, ?, ?)""",
                (sector, json.dumps(score_dict, default=str), datetime.now().isoformat()),
            )

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM news_cache")
            conn.execute("DELETE FROM sector_scores")
