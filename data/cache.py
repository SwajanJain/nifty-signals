"""SQLite-based caching layer for stock data."""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd

from config import CACHE_DIR, CACHE_EXPIRY_HOURS


class DataCache:
    """SQLite cache for stock price data."""

    def __init__(self):
        self.db_path = CACHE_DIR / "stock_cache.db"
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_data (
                symbol TEXT,
                timeframe TEXT,
                data TEXT,
                updated_at TIMESTAMP,
                PRIMARY KEY (symbol, timeframe)
            )
        """)
        conn.commit()
        conn.close()

    def get(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get cached data for a symbol if not expired."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT data, updated_at FROM stock_data WHERE symbol = ? AND timeframe = ?",
            (symbol, timeframe)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        data_json, updated_at = row
        updated_time = datetime.fromisoformat(updated_at)

        # Check if cache is expired
        if datetime.now() - updated_time > timedelta(hours=CACHE_EXPIRY_HOURS):
            return None

        # Convert JSON back to DataFrame
        data = json.loads(data_json)
        df = pd.DataFrame(data)
        df.index = pd.to_datetime(df.index)
        return df

    def set(self, symbol: str, timeframe: str, data: pd.DataFrame):
        """Cache data for a symbol."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Convert DataFrame to JSON
        data_json = data.to_json(date_format='iso')

        cursor.execute("""
            INSERT OR REPLACE INTO stock_data (symbol, timeframe, data, updated_at)
            VALUES (?, ?, ?, ?)
        """, (symbol, timeframe, data_json, datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def clear(self, symbol: Optional[str] = None):
        """Clear cache for a symbol or all symbols."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if symbol:
            cursor.execute("DELETE FROM stock_data WHERE symbol = ?", (symbol,))
        else:
            cursor.execute("DELETE FROM stock_data")

        conn.commit()
        conn.close()
