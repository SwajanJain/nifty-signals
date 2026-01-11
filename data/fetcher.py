"""Stock data fetcher using yfinance."""

import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import pandas as pd
import yfinance as yf

from config import STOCKS_FILE, LOOKBACK_DAYS
from .cache import DataCache


class StockDataFetcher:
    """Fetches stock data from Yahoo Finance for NSE stocks."""

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self.cache = DataCache() if use_cache else None
        self._stocks = None

    @property
    def stocks(self) -> List[Dict]:
        """Load stock list from JSON file."""
        if self._stocks is None:
            with open(STOCKS_FILE, 'r') as f:
                data = json.load(f)
                self._stocks = data['nifty_100']
        return self._stocks

    def get_nse_symbol(self, symbol: str) -> str:
        """Convert symbol to NSE format for yfinance."""
        return f"{symbol}.NS"

    def fetch_stock_data(
        self,
        symbol: str,
        timeframe: str = "daily",
        lookback_days: int = LOOKBACK_DAYS
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical stock data.

        Args:
            symbol: Stock symbol (without .NS suffix)
            timeframe: 'daily' or 'weekly'
            lookback_days: Number of days to look back

        Returns:
            DataFrame with OHLCV data or None if fetch fails
        """
        # Check cache first
        if self.cache:
            cached = self.cache.get(symbol, timeframe)
            if cached is not None:
                return cached

        # Fetch from yfinance
        nse_symbol = self.get_nse_symbol(symbol)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        try:
            ticker = yf.Ticker(nse_symbol)

            if timeframe == "weekly":
                df = ticker.history(start=start_date, end=end_date, interval="1wk")
            else:
                df = ticker.history(start=start_date, end=end_date, interval="1d")

            if df.empty:
                return None

            # Clean up the DataFrame
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
            df.columns = ['open', 'high', 'low', 'close', 'volume']

            # Cache the data
            if self.cache:
                self.cache.set(symbol, timeframe, df)

            return df

        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return None

    def fetch_all_stocks(
        self,
        timeframe: str = "daily",
        symbols: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for all stocks or specified symbols.

        Args:
            timeframe: 'daily' or 'weekly'
            symbols: Optional list of symbols to fetch

        Returns:
            Dictionary of symbol -> DataFrame
        """
        if symbols is None:
            symbols = [s['symbol'] for s in self.stocks]

        results = {}
        for symbol in symbols:
            df = self.fetch_stock_data(symbol, timeframe)
            if df is not None:
                results[symbol] = df

        return results

    def get_stock_info(self, symbol: str) -> Dict:
        """Get basic info about a stock."""
        for stock in self.stocks:
            if stock['symbol'] == symbol:
                return stock
        return {'symbol': symbol, 'name': symbol}
