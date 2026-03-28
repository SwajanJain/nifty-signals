"""
Reliable Data Fetcher (yfinance-only)

Simplified data fetching using Yahoo Finance for Indian stocks.
Includes symbol mappings for stocks that need alternative tickers.

Key Principle: FAIL-CLOSED
- If data is stale/missing -> return DataQuality.DEGRADED, not fake data
- Position sizing adjusts based on data quality
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging
import yfinance as yf

from .models import DataQuality, OHLCVData, DataResult, SystemDataHealth

logger = logging.getLogger(__name__)


# =============================================================================
# Symbol Mappings for Problematic Stocks
# =============================================================================
# Some NSE stocks have different yfinance tickers or work better with BSE suffix

SYMBOL_MAPPINGS = {
    # Format: 'NIFTY_SYMBOL': 'yfinance_ticker'
    'ABB': 'ABB.BO',              # Works on BSE, not NSE
    'MCDOWELL-N': 'UNITDSPR.NS',  # United Spirits alternative symbol
    # Note: TATAMOTORS and ZOMATO have no working alternative in yfinance
}

# Stocks that are known to fail with no workaround
KNOWN_FAILURES = ['TATAMOTORS', 'ZOMATO']


def get_yfinance_symbol(symbol: str) -> str:
    """
    Convert Nifty symbol to yfinance-compatible ticker.

    Args:
        symbol: Stock symbol (e.g., 'RELIANCE', 'ABB')

    Returns:
        yfinance ticker with proper suffix
    """
    # Check if there's a special mapping
    if symbol in SYMBOL_MAPPINGS:
        return SYMBOL_MAPPINGS[symbol]

    # Default: add .NS suffix for NSE
    if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
        return f"{symbol}.NS"

    return symbol


class YFinanceFetcher:
    """
    Yahoo Finance data fetcher for Indian stocks.

    Features:
    - Automatic symbol mapping for problematic stocks
    - Data quality assessment based on freshness
    - Global index support (VIX, S&P 500, etc.)
    """

    def __init__(self):
        self.cache: Dict[str, OHLCVData] = {}
        self.cache_expiry = timedelta(hours=4)

    def get_historical_data(
        self,
        symbol: str,
        days: int = 365,
        use_cache: bool = True
    ) -> OHLCVData:
        """
        Get historical OHLCV data for a stock.

        Args:
            symbol: Stock symbol (e.g., 'RELIANCE')
            days: Number of days of history (default: 365 for EMA 200)
            use_cache: Whether to use cached data

        Returns:
            OHLCVData with DataFrame and quality indicator
        """
        # Check for known failures
        if symbol in KNOWN_FAILURES:
            logger.warning(f"{symbol} has no working yfinance ticker - skipping")
            return OHLCVData(
                symbol=symbol,
                df=pd.DataFrame(),
                quality=DataQuality.UNUSABLE,
                source='yfinance'
            )

        # Check cache
        cache_key = f"{symbol}_{days}"
        if use_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            age = datetime.now() - cached.fetched_at
            if age < self.cache_expiry:
                return cached

        try:
            # Get yfinance-compatible symbol
            yf_symbol = get_yfinance_symbol(symbol)

            ticker = yf.Ticker(yf_symbol)

            # Convert days to period string
            if days <= 7:
                period = "1wk"
            elif days <= 30:
                period = "1mo"
            elif days <= 90:
                period = "3mo"
            elif days <= 180:
                period = "6mo"
            elif days <= 365:
                period = "1y"
            elif days <= 730:
                period = "2y"
            else:
                period = "5y"

            df = ticker.history(period=period, interval='1d')

            if df.empty:
                logger.warning(f"No data returned for {symbol} ({yf_symbol})")
                return OHLCVData(
                    symbol=symbol,
                    df=pd.DataFrame(),
                    quality=DataQuality.UNUSABLE,
                    source='yfinance'
                )

            # Standardize columns
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })

            # Keep only OHLCV columns
            df = df[['open', 'high', 'low', 'close', 'volume']]

            # Assess data quality based on freshness
            quality = self._assess_quality(df)

            result = OHLCVData(
                symbol=symbol,
                df=df,
                quality=quality,
                source='yfinance'
            )

            # Cache the result
            self.cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"yfinance error for {symbol}: {e}")
            return OHLCVData(
                symbol=symbol,
                df=pd.DataFrame(),
                quality=DataQuality.UNUSABLE,
                source='yfinance'
            )

    def _assess_quality(self, df: pd.DataFrame) -> DataQuality:
        """Assess data quality based on freshness and completeness."""
        if len(df) == 0:
            return DataQuality.UNUSABLE

        last_date = df.index[-1]

        # Handle timezone-aware datetime
        if hasattr(last_date, 'tz') and last_date.tz is not None:
            last_date = last_date.tz_localize(None)

        days_old = (datetime.now() - last_date.to_pydatetime()).days

        # Account for weekends - if today is Monday, Friday's data is fine
        weekday = datetime.now().weekday()
        if weekday == 0:  # Monday
            days_old -= 2
        elif weekday == 6:  # Sunday
            days_old -= 1

        if days_old > 5:
            return DataQuality.DEGRADED
        elif days_old > 2:
            return DataQuality.GOOD
        else:
            return DataQuality.EXCELLENT

    def get_global_index(self, symbol: str, period: str = "1mo") -> OHLCVData:
        """
        Get global index data (VIX, S&P 500, DXY, etc.)

        Args:
            symbol: Index symbol (e.g., '^VIX', '^GSPC')
            period: yfinance period string (default: '1mo')

        Returns:
            OHLCVData with index data
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval='1d')

            if df.empty:
                return OHLCVData(
                    symbol=symbol,
                    df=pd.DataFrame(),
                    quality=DataQuality.UNUSABLE,
                    source='yfinance'
                )

            df = df.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            })

            return OHLCVData(
                symbol=symbol,
                df=df[['open', 'high', 'low', 'close', 'volume']],
                quality=DataQuality.GOOD,
                source='yfinance'
            )

        except Exception as e:
            logger.error(f"yfinance global index error for {symbol}: {e}")
            return OHLCVData(
                symbol=symbol,
                df=pd.DataFrame(),
                quality=DataQuality.UNUSABLE,
                source='yfinance'
            )

    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """Get stock info (fundamentals, market cap, etc.)"""
        try:
            yf_symbol = get_yfinance_symbol(symbol)
            ticker = yf.Ticker(yf_symbol)
            return ticker.info or {}
        except Exception as e:
            logger.error(f"yfinance info error for {symbol}: {e}")
            return {}

    def get_bulk_data(
        self,
        symbols: List[str],
        days: int = 365
    ) -> Dict[str, OHLCVData]:
        """
        Get historical data for multiple symbols.

        Args:
            symbols: List of stock symbols
            days: Number of days of history

        Returns:
            Dict mapping symbol to OHLCVData
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.get_historical_data(symbol, days)
        return results

    def get_latest_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get latest prices for multiple symbols.

        Args:
            symbols: List of stock symbols

        Returns:
            Dict mapping symbol to latest close price
        """
        prices = {}
        for symbol in symbols:
            data = self.get_historical_data(symbol, days=5)
            if data.is_valid and len(data.df) > 0:
                prices[symbol] = float(data.df['close'].iloc[-1])
        return prices


class ReliableDataFetcher:
    """
    Main data fetcher interface.

    Tries NSE (jugaad-data) first, then falls back to yfinance.
    NSE is faster and more reliable for Indian stocks.

    Key Principle: FAIL-CLOSED
    - Unknown/stale data returns DEGRADED quality
    - Position sizing adjusts based on quality
    - Never use synthetic data without flagging
    """

    def __init__(self):
        self.yfinance = YFinanceFetcher()
        self._yfinance_available = True
        self._nse = None
        self._nse_checked = False

    def _get_nse(self):
        """Lazy-init NSE fetcher. Only try once."""
        if not self._nse_checked:
            self._nse_checked = True
            try:
                from .nse_fetcher import NSEDataFetcher
                nse = NSEDataFetcher()
                if nse.available:
                    self._nse = nse
                    logger.info("NSE data source available — using as primary")
                else:
                    logger.info("NSE data source unavailable — using yfinance only")
            except Exception as e:
                logger.info(f"NSE fetcher init failed: {e}")
        return self._nse

    @property
    def primary_source(self) -> str:
        nse = self._get_nse()
        return "nse" if nse else "yfinance"

    def get_historical_data(
        self,
        symbol: str,
        days: int = 365
    ) -> OHLCVData:
        """
        Get historical OHLCV data.

        Tries NSE first (jugaad-data), falls back to yfinance.

        Args:
            symbol: Stock symbol (e.g., 'RELIANCE')
            days: Number of days of history

        Returns:
            OHLCVData with quality indicator
        """
        # Try NSE first
        nse = self._get_nse()
        if nse:
            result = nse.get_historical_data(symbol, days)
            if result and result.is_valid:
                return result

        # Fall back to yfinance
        return self.yfinance.get_historical_data(symbol, days)

    def get_bulk_data(
        self,
        symbols: List[str],
        days: int = 365
    ) -> Dict[str, OHLCVData]:
        """Get historical data for multiple symbols."""
        return self.yfinance.get_bulk_data(symbols, days)

    def get_latest_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get latest prices for multiple symbols."""
        return self.yfinance.get_latest_prices(symbols)

    def get_fundamentals(self, symbol: str) -> DataResult:
        """
        Get fundamental data for a stock.

        Returns:
            DataResult with fundamentals dict
        """
        try:
            info = self.yfinance.get_stock_info(symbol)

            fundamentals = {
                'symbol': symbol,
                'roe': info.get('returnOnEquity'),
                'roce': None,  # Not available in yfinance
                'debt_to_equity': info.get('debtToEquity'),
                'pe_ratio': info.get('trailingPE'),
                'pb_ratio': info.get('priceToBook'),
                'eps': info.get('trailingEps'),
                'market_cap': info.get('marketCap'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                '52_week_high': info.get('fiftyTwoWeekHigh'),
                '52_week_low': info.get('fiftyTwoWeekLow'),
                'avg_volume': info.get('averageVolume'),
                'dividend_yield': info.get('dividendYield'),
            }

            # Determine quality based on data availability
            has_key_data = info.get('trailingPE') is not None
            quality = DataQuality.GOOD if has_key_data else DataQuality.DEGRADED

            return DataResult(
                data=fundamentals,
                quality=quality,
                source='yfinance',
                warnings=['Limited fundamentals - some data unavailable'] if not has_key_data else []
            )

        except Exception as e:
            logger.error(f"yfinance fundamentals error for {symbol}: {e}")

        return DataResult(
            data={'symbol': symbol},
            quality=DataQuality.UNUSABLE,
            source='yfinance',
            warnings=['Fundamentals data unavailable']
        )

    def get_global_context(self) -> DataResult:
        """
        Get global market context (VIX, S&P 500, etc.)

        Returns:
            DataResult with global market indicators
        """
        try:
            # Get VIX
            vix_data = self.yfinance.get_global_index('^VIX')
            vix = float(vix_data.df['close'].iloc[-1]) if vix_data.is_valid else None

            # Get S&P 500
            sp500_data = self.yfinance.get_global_index('^GSPC')
            if sp500_data.is_valid and len(sp500_data.df) >= 2:
                sp500_close = float(sp500_data.df['close'].iloc[-1])
                sp500_prev = float(sp500_data.df['close'].iloc[-2])
                sp500_change = ((sp500_close - sp500_prev) / sp500_prev) * 100
            else:
                sp500_close = None
                sp500_change = None

            # Get DXY (US Dollar Index)
            dxy_data = self.yfinance.get_global_index('DX-Y.NYB')
            dxy = float(dxy_data.df['close'].iloc[-1]) if dxy_data.is_valid else None

            # Get Nifty 50
            nifty_data = self.yfinance.get_global_index('^NSEI')
            if nifty_data.is_valid and len(nifty_data.df) >= 2:
                nifty_close = float(nifty_data.df['close'].iloc[-1])
                nifty_prev = float(nifty_data.df['close'].iloc[-2])
                nifty_change = ((nifty_close - nifty_prev) / nifty_prev) * 100
            else:
                nifty_close = None
                nifty_change = None

            context = {
                'vix': vix,
                'vix_level': 'LOW' if vix and vix < 15 else ('HIGH' if vix and vix > 25 else 'NORMAL'),
                'sp500_change': sp500_change,
                'sp500_close': sp500_close,
                'dxy': dxy,
                'nifty_close': nifty_close,
                'nifty_change': nifty_change,
                'global_sentiment': self._assess_global_sentiment(vix, sp500_change)
            }

            quality = DataQuality.GOOD if vix is not None else DataQuality.DEGRADED

            return DataResult(
                data=context,
                quality=quality,
                source='yfinance'
            )

        except Exception as e:
            logger.error(f"Global context error: {e}")
            return DataResult(
                data={},
                quality=DataQuality.UNUSABLE,
                source='yfinance',
                warnings=['Global context unavailable']
            )

    def _assess_global_sentiment(
        self,
        vix: Optional[float],
        sp500_change: Optional[float]
    ) -> str:
        """Assess global sentiment from VIX and S&P change."""
        if vix is None or sp500_change is None:
            return 'UNKNOWN'

        if vix > 30:
            return 'FEAR'
        elif vix > 20 and sp500_change < -1:
            return 'CAUTIOUS'
        elif vix < 15 and sp500_change > 0.5:
            return 'RISK_ON'
        elif sp500_change > 1:
            return 'BULLISH'
        elif sp500_change < -1:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

    def get_nifty_100_symbols(self) -> List[str]:
        """Get current Nifty 100 constituents from config."""
        from config import get_nifty100_symbols
        return get_nifty100_symbols()

    def get_system_health(self) -> SystemDataHealth:
        """
        Get overall system data health.

        Used to determine if trading should proceed
        and at what position size.
        """
        warnings = []

        # Check price data availability with a test symbol
        test_symbol = 'RELIANCE'
        price_data = self.get_historical_data(test_symbol, days=5)
        price_quality = price_data.quality

        # Check fundamentals
        fundamentals = self.get_fundamentals(test_symbol)
        fundamentals_quality = fundamentals.quality

        # Determine overall quality
        if price_quality == DataQuality.EXCELLENT:
            overall = DataQuality.EXCELLENT
        elif price_quality == DataQuality.GOOD:
            overall = DataQuality.GOOD
        elif price_quality == DataQuality.DEGRADED:
            overall = DataQuality.DEGRADED
        else:
            overall = DataQuality.UNUSABLE

        # Determine position size multiplier
        if overall == DataQuality.EXCELLENT:
            multiplier = 1.0
        elif overall == DataQuality.GOOD:
            multiplier = 0.9
        elif overall == DataQuality.DEGRADED:
            multiplier = 0.5
            warnings.append("Data quality degraded - reducing position sizes by 50%")
        else:
            multiplier = 0.0
            warnings.append("Data quality unusable - no trades allowed")

        # Determine if trading allowed
        allow_trading = overall != DataQuality.UNUSABLE

        return SystemDataHealth(
            price_data=price_quality,
            fundamentals_data=fundamentals_quality,
            overall=overall,
            yfinance_available=self._yfinance_available,
            position_size_multiplier=multiplier,
            allow_trading=allow_trading,
            warnings=warnings
        )


# Singleton instance
_fetcher: Optional[ReliableDataFetcher] = None


def get_reliable_fetcher() -> ReliableDataFetcher:
    """Get or create reliable data fetcher singleton."""
    global _fetcher
    if _fetcher is None:
        _fetcher = ReliableDataFetcher()
    return _fetcher
