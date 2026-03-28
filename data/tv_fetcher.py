"""TradingView Data Fetcher — multi-timeframe data via tvDatafeed.

Provides reliable multi-timeframe data (5m to monthly) from TradingView.
No authentication required for basic daily/weekly usage.

Falls back gracefully if tvDatafeed is not installed.
"""

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from .models import DataQuality, OHLCVData

logger = logging.getLogger(__name__)


class TradingViewFetcher:
    """Fetch OHLCV data from TradingView."""

    def __init__(self):
        self._available: Optional[bool] = None
        self._tv = None

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                from tvDatafeed import TvDatafeed  # noqa: F401
                self._available = True
            except ImportError:
                logger.info("tvDatafeed not installed — TV fetcher disabled")
                self._available = False
        return self._available

    def _get_tv(self):
        if self._tv is None and self.available:
            from tvDatafeed import TvDatafeed
            self._tv = TvDatafeed()  # no auth for basic usage
        return self._tv

    def _get_interval(self, interval: str):
        from tvDatafeed import Interval
        mapping = {
            '5m': Interval.in_5_minute,
            '15m': Interval.in_15_minute,
            '1h': Interval.in_1_hour,
            '4h': Interval.in_4_hour,
            'D': Interval.in_daily,
            'W': Interval.in_weekly,
            'M': Interval.in_monthly,
        }
        return mapping.get(interval, Interval.in_daily)

    def get_historical_data(self, symbol: str, interval: str = 'D',
                            bars: int = 500, exchange: str = 'NSE') -> Optional[OHLCVData]:
        """Fetch historical data from TradingView.

        Args:
            symbol: Stock symbol (e.g., 'RELIANCE')
            interval: Timeframe — '5m', '15m', '1h', '4h', 'D', 'W', 'M'
            bars: Number of bars to fetch
            exchange: Exchange — 'NSE', 'BSE'

        Returns:
            OHLCVData with standard columns or None.
        """
        if not self.available:
            return None

        try:
            tv = self._get_tv()
            if tv is None:
                return None

            iv = self._get_interval(interval)
            df = tv.get_hist(symbol=symbol, exchange=exchange,
                             interval=iv, n_bars=bars)

            if df is None or df.empty:
                logger.warning(f"TV: No data for {symbol} ({interval})")
                return None

            # tvDatafeed returns: symbol, open, high, low, close, volume
            # with DatetimeIndex
            col_map = {}
            for c in df.columns:
                cl = c.strip().lower()
                if cl in ('open', 'high', 'low', 'close', 'volume'):
                    col_map[c] = cl
            df = df.rename(columns=col_map)

            for col in ['open', 'high', 'low', 'close']:
                if col not in df.columns:
                    return None

            if 'volume' not in df.columns:
                df['volume'] = 0

            # Drop the 'symbol' column if present
            if 'symbol' in df.columns:
                df = df.drop(columns=['symbol'])

            df = df[['open', 'high', 'low', 'close', 'volume']].copy()
            df['volume'] = df['volume'].fillna(0).astype(float)
            df = df.sort_index()

            return OHLCVData(
                symbol=symbol,
                df=df,
                quality=DataQuality.GOOD,
                source=f"tradingview_{interval}",
                fetched_at=datetime.now(),
            )

        except Exception as e:
            logger.warning(f"TV fetch failed for {symbol} ({interval}): {e}")
            return None
