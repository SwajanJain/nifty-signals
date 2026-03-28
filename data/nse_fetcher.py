"""NSE Direct Data Fetcher — uses jugaad-data.

Primary data source for Indian stocks — fetches directly from NSE bhavcopy.
Falls back gracefully if jugaad-data is not installed or NSE blocks requests.
"""

import logging
from datetime import date, timedelta, datetime
from typing import Optional

import pandas as pd

from .models import DataQuality, OHLCVData

logger = logging.getLogger(__name__)


class NSEDataFetcher:
    """Fetch OHLCV data directly from NSE via jugaad-data."""

    def __init__(self):
        self._available: Optional[bool] = None
        self._live = None

    @property
    def available(self) -> bool:
        """Lazy check — try import once and cache result."""
        if self._available is None:
            try:
                from jugaad_data.nse import stock_df  # noqa: F401
                self._available = True
            except ImportError:
                logger.info("jugaad-data not installed — NSE fetcher disabled")
                self._available = False
        return self._available

    def get_historical_data(self, symbol: str, days: int = 365) -> Optional[OHLCVData]:
        """Fetch historical OHLCV from NSE bhavcopy.

        Returns OHLCVData with DataFrame columns: open, high, low, close, volume
        (matching yfinance convention for compatibility).
        """
        if not self.available:
            return None

        try:
            from jugaad_data.nse import stock_df

            to_date = date.today()
            from_date = to_date - timedelta(days=days)

            df = stock_df(symbol=symbol, from_date=from_date,
                          to_date=to_date, series="EQ")

            if df is None or df.empty:
                logger.warning(f"NSE: No data for {symbol}")
                return None

            # Normalize columns to lowercase standard
            col_map = {}
            for c in df.columns:
                cl = c.strip().lower().replace(' ', '_')
                if cl in ('open', 'high', 'low', 'close', 'volume',
                          'prev_close', 'ltp', 'vwap', 'no_of_trades'):
                    col_map[c] = cl

            df = df.rename(columns=col_map)

            # Ensure required columns exist
            required = ['open', 'high', 'low', 'close']
            for col in required:
                if col not in df.columns:
                    logger.warning(f"NSE: Missing column '{col}' for {symbol}")
                    return None

            # Volume might be named differently
            if 'volume' not in df.columns:
                # jugaad-data uses 'NO OF TRADES' or 'TOTAL TRADED QUANTITY'
                for alt in ['no_of_trades', 'total_traded_quantity']:
                    if alt in df.columns:
                        df['volume'] = df[alt]
                        break
                if 'volume' not in df.columns:
                    df['volume'] = 0

            # Set date as index
            if 'DATE' in df.columns:
                df['DATE'] = pd.to_datetime(df['DATE'])
                df = df.set_index('DATE')
            elif 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')

            df = df.sort_index()

            # Keep only standard columns
            df = df[['open', 'high', 'low', 'close', 'volume']].copy()
            df['volume'] = df['volume'].fillna(0).astype(float)

            quality = DataQuality.EXCELLENT if len(df) >= days * 0.6 else DataQuality.GOOD

            return OHLCVData(
                symbol=symbol,
                df=df,
                quality=quality,
                source="nse_jugaad",
                fetched_at=datetime.now(),
            )

        except Exception as e:
            logger.warning(f"NSE fetch failed for {symbol}: {e}")
            return None

    def get_index_data(self, index: str = "NIFTY 50", days: int = 365) -> Optional[OHLCVData]:
        """Fetch index historical data."""
        if not self.available:
            return None

        try:
            from jugaad_data.nse import index_df

            to_date = date.today()
            from_date = to_date - timedelta(days=days)

            df = index_df(index=index, from_date=from_date, to_date=to_date)

            if df is None or df.empty:
                return None

            # Normalize
            col_map = {}
            for c in df.columns:
                cl = c.strip().lower().replace(' ', '_')
                if cl in ('open', 'high', 'low', 'close', 'volume'):
                    col_map[c] = cl
            df = df.rename(columns=col_map)

            for col in ['open', 'high', 'low', 'close']:
                if col not in df.columns:
                    return None

            if 'volume' not in df.columns:
                df['volume'] = 0

            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.set_index('Date')

            df = df.sort_index()
            df = df[['open', 'high', 'low', 'close', 'volume']].copy()

            return OHLCVData(symbol=index, df=df, quality=DataQuality.GOOD,
                             source="nse_jugaad")

        except Exception as e:
            logger.warning(f"NSE index fetch failed for {index}: {e}")
            return None

    def get_live_quote(self, symbol: str) -> Optional[dict]:
        """Fetch real-time quote from NSE."""
        if not self.available:
            return None

        try:
            from jugaad_data.nse import NSELive
            if self._live is None:
                self._live = NSELive()
            data = self._live.stock_quote(symbol)
            return data
        except Exception as e:
            logger.warning(f"NSE live quote failed for {symbol}: {e}")
            return None
