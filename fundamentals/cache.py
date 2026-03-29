"""SQLite cache for fundamental data from screener.in."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from config import CACHE_DIR


FUNDAMENTAL_CACHE_DB = CACHE_DIR / "fundamental_cache.db"
CACHE_EXPIRY_HOURS = 168  # 7 days — quarterly financials change infrequently
# Price data within the cache goes stale faster than financials.
# Consumers should check 'price_data_stale' flag in returned data.
PRICE_STALENESS_HOURS = 24


class FundamentalCache:
    """SQLite-backed cache for fundamental data."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or FUNDAMENTAL_CACHE_DB
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raw_data (
                    symbol TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    symbol TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def _is_expired(self, updated_at_str: str) -> bool:
        updated_at = datetime.fromisoformat(updated_at_str)
        return datetime.now() - updated_at > timedelta(hours=CACHE_EXPIRY_HOURS)

    # --- Raw data ---

    def get_raw(self, symbol: str) -> Optional[Dict]:
        """Get cached raw data dict if not expired.

        Adds 'price_data_stale' flag if cache is older than PRICE_STALENESS_HOURS.
        Financials (quarterly/annual) are valid for the full CACHE_EXPIRY_HOURS,
        but price fields (current_price, market_cap) go stale faster.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data_json, updated_at FROM raw_data WHERE symbol = ?",
                (symbol,),
            ).fetchone()

        if row is None:
            return None
        if self._is_expired(row[1]):
            return None

        data = json.loads(row[0])
        updated_at = datetime.fromisoformat(row[1])
        age_hours = (datetime.now() - updated_at).total_seconds() / 3600
        data['price_data_stale'] = age_hours > PRICE_STALENESS_HOURS
        data['cache_age_hours'] = round(age_hours, 1)
        return data

    def set_raw(self, symbol: str, data: Dict):
        """Cache raw scraped data as dict."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO raw_data (symbol, data_json, updated_at)
                   VALUES (?, ?, ?)""",
                (symbol, json.dumps(data, default=str), datetime.now().isoformat()),
            )

    # --- Profiles ---

    def get_profile(self, symbol: str) -> Optional[Dict]:
        """Get cached profile dict if not expired."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT profile_json, updated_at FROM profiles WHERE symbol = ?",
                (symbol,),
            ).fetchone()

        if row is None:
            return None
        if self._is_expired(row[1]):
            return None
        return json.loads(row[0])

    def set_profile(self, symbol: str, profile_dict: Dict):
        """Cache computed profile as dict."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO profiles (symbol, profile_json, updated_at)
                   VALUES (?, ?, ?)""",
                (symbol, json.dumps(profile_dict, default=str), datetime.now().isoformat()),
            )

    def get_all_profiles(self) -> Dict[str, Dict]:
        """Get all non-expired cached profiles."""
        result = {}
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT symbol, profile_json, updated_at FROM profiles"
            ).fetchall()

        for symbol, profile_json, updated_at in rows:
            if not self._is_expired(updated_at):
                result[symbol] = json.loads(profile_json)
        return result

    def clear(self, symbol: Optional[str] = None):
        """Clear cache. If symbol given, clear only that stock."""
        with sqlite3.connect(self.db_path) as conn:
            if symbol:
                conn.execute("DELETE FROM raw_data WHERE symbol = ?", (symbol,))
                conn.execute("DELETE FROM profiles WHERE symbol = ?", (symbol,))
            else:
                conn.execute("DELETE FROM raw_data")
                conn.execute("DELETE FROM profiles")

    def get_stats(self) -> Dict:
        """Return cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            raw_count = conn.execute("SELECT COUNT(*) FROM raw_data").fetchone()[0]
            profile_count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
            oldest = conn.execute(
                "SELECT MIN(updated_at) FROM raw_data"
            ).fetchone()[0]
            newest = conn.execute(
                "SELECT MAX(updated_at) FROM raw_data"
            ).fetchone()[0]

        return {
            "raw_entries": raw_count,
            "profile_entries": profile_count,
            "oldest": oldest,
            "newest": newest,
        }
