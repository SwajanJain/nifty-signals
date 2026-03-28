"""
TrueData API Client

Professional-grade data source for Indian markets.
Replaces yfinance as primary data source.

API Endpoints:
- Market Data: history.truedata.in
- Corporate Data: corporate.truedata.in
- Auth: auth.truedata.in
"""

import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from io import StringIO

logger = logging.getLogger(__name__)


class DataQuality(Enum):
    """Data quality levels"""
    EXCELLENT = "excellent"  # Fresh, complete, verified
    GOOD = "good"            # Recent, mostly complete
    DEGRADED = "degraded"    # Stale or partial data
    UNUSABLE = "unusable"    # Missing or invalid


@dataclass
class TrueDataConfig:
    """TrueData API configuration"""
    username: str = ""
    password: str = ""

    # API endpoints
    auth_url: str = "https://auth.truedata.in/token"
    market_data_url: str = "https://history.truedata.in"
    corporate_url: str = "https://corporate.truedata.in"

    # Settings
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    token_refresh_buffer: int = 300  # Refresh token 5 min before expiry

    @classmethod
    def from_env(cls) -> 'TrueDataConfig':
        """Load config from environment variables"""
        return cls(
            username=os.getenv('TRUEDATA_USERNAME', ''),
            password=os.getenv('TRUEDATA_PASSWORD', ''),
        )

    @property
    def is_configured(self) -> bool:
        """Check if credentials are configured"""
        return bool(self.username and self.password)


@dataclass
class AuthToken:
    """Authentication token with expiry tracking"""
    access_token: str
    token_type: str
    expires_at: datetime

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid"""
        return datetime.now() < self.expires_at

    @property
    def needs_refresh(self) -> bool:
        """Check if token needs refresh soon"""
        buffer = timedelta(seconds=300)  # 5 minutes
        return datetime.now() > (self.expires_at - buffer)


@dataclass
class OHLCVData:
    """OHLCV data result"""
    symbol: str
    df: pd.DataFrame
    quality: DataQuality
    source: str = "truedata"
    fetched_at: datetime = field(default_factory=datetime.now)

    @property
    def is_valid(self) -> bool:
        return self.quality in [DataQuality.EXCELLENT, DataQuality.GOOD]

    @property
    def row_count(self) -> int:
        return len(self.df) if self.df is not None else 0


@dataclass
class FIIDIIData:
    """FII/DII flow data"""
    date: datetime
    fii_buy: float
    fii_sell: float
    fii_net: float
    dii_buy: float
    dii_sell: float
    dii_net: float
    segment: str  # cash or fo
    quality: DataQuality
    source: str = "truedata"
    is_synthetic: bool = False


@dataclass
class ShareholdingData:
    """Shareholding pattern data"""
    symbol: str
    promoter_holding: float
    promoter_pledge: float
    fii_holding: float
    dii_holding: float
    public_holding: float
    quarter: str
    quality: DataQuality


@dataclass
class EarningsData:
    """Earnings calendar data"""
    symbol: str
    result_date: datetime
    quarter: str
    nature: str  # standalone/consolidated
    quality: DataQuality


@dataclass
class FinancialRatios:
    """Financial ratios data"""
    symbol: str
    roe: Optional[float] = None
    roce: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    eps: Optional[float] = None
    book_value: Optional[float] = None
    quality: DataQuality = DataQuality.GOOD


class TrueDataAuth:
    """
    TrueData Authentication Handler

    Manages OAuth2 token lifecycle:
    - Initial authentication
    - Token refresh
    - Error handling
    """

    def __init__(self, config: TrueDataConfig):
        self.config = config
        self._token: Optional[AuthToken] = None

    def authenticate(self) -> bool:
        """
        Authenticate with TrueData API

        Returns:
            bool: True if authentication successful
        """
        if not self.config.is_configured:
            logger.warning("TrueData credentials not configured")
            return False

        try:
            response = requests.post(
                self.config.auth_url,
                data={
                    'username': self.config.username,
                    'password': self.config.password,
                    'grant_type': 'password'
                },
                timeout=self.config.timeout
            )

            if response.status_code == 200:
                data = response.json()

                # Calculate expiry (typically 24 hours, but check response)
                expires_in = data.get('expires_in', 86400)  # Default 24 hours
                expires_at = datetime.now() + timedelta(seconds=expires_in)

                self._token = AuthToken(
                    access_token=data['access_token'],
                    token_type=data.get('token_type', 'Bearer'),
                    expires_at=expires_at
                )

                logger.info("TrueData authentication successful")
                return True
            else:
                logger.error(f"TrueData auth failed: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"TrueData auth request failed: {e}")
            return False

    def get_token(self) -> Optional[str]:
        """
        Get valid access token, refreshing if needed

        Returns:
            str: Valid access token or None
        """
        if self._token is None or not self._token.is_valid:
            if not self.authenticate():
                return None
        elif self._token.needs_refresh:
            # Proactively refresh
            self.authenticate()

        return self._token.access_token if self._token else None

    def get_auth_header(self) -> Dict[str, str]:
        """Get authorization header for API requests"""
        token = self.get_token()
        if token:
            return {'Authorization': f'Bearer {token}'}
        return {}

    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated"""
        return self._token is not None and self._token.is_valid


class TrueDataMarketAPI:
    """
    TrueData Market Data API

    Endpoints:
    - getbars: Historical OHLCV
    - getlastnbars: Recent bars
    - getLTPBulk: Bulk LTP
    - getBhavCopy: EOD data
    - getindexcomponents: Index constituents
    - getSymbolOptionChain: Option chain
    - get52WeekHL: 52-week high/low
    - gettopngainers/losers: Gainers/Losers
    """

    def __init__(self, auth: TrueDataAuth, config: TrueDataConfig):
        self.auth = auth
        self.config = config
        self.base_url = config.market_data_url

    def _request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        response_format: str = 'csv'
    ) -> Tuple[Optional[Any], DataQuality]:
        """
        Make authenticated API request

        Args:
            endpoint: API endpoint path
            params: Query parameters
            response_format: 'csv' or 'json'

        Returns:
            Tuple of (data, quality)
        """
        params['response'] = response_format

        for attempt in range(self.config.max_retries):
            try:
                headers = self.auth.get_auth_header()
                if not headers:
                    logger.error("No auth token available")
                    return None, DataQuality.UNUSABLE

                url = f"{self.base_url}/{endpoint}"
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout
                )

                if response.status_code == 200:
                    if response_format == 'csv':
                        df = pd.read_csv(StringIO(response.text))
                        return df, DataQuality.EXCELLENT
                    else:
                        return response.json(), DataQuality.EXCELLENT

                elif response.status_code == 401:
                    # Token expired, re-authenticate
                    logger.warning("Token expired, re-authenticating...")
                    self.auth.authenticate()
                    continue

                else:
                    logger.error(f"API error: {response.status_code} - {response.text}")

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1})")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")

            if attempt < self.config.max_retries - 1:
                time.sleep(self.config.retry_delay * (attempt + 1))

        return None, DataQuality.UNUSABLE

    def get_historical_bars(
        self,
        symbol: str,
        interval: str = 'eod',  # eod, 1min, 5min, 15min, 30min, 60min
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        days: int = 365
    ) -> OHLCVData:
        """
        Get historical OHLCV bars

        Args:
            symbol: Stock symbol (e.g., 'RELIANCE')
            interval: Bar interval
            from_date: Start date
            to_date: End date
            days: Number of days if from_date not specified

        Returns:
            OHLCVData with DataFrame containing OHLCV
        """
        if to_date is None:
            to_date = datetime.now()
        if from_date is None:
            from_date = to_date - timedelta(days=days)

        # Format dates for TrueData API (YYMMDDTHH:MM:SS)
        from_str = from_date.strftime('%y%m%dT09:00:00')
        to_str = to_date.strftime('%y%m%dT18:30:00')

        params = {
            'symbol': symbol,
            'from': from_str,
            'to': to_str,
            'interval': interval
        }

        df, quality = self._request('getbars', params)

        if df is not None and not df.empty:
            # Standardize column names
            df = self._standardize_ohlcv(df)

            return OHLCVData(
                symbol=symbol,
                df=df,
                quality=quality,
                source='truedata'
            )

        return OHLCVData(
            symbol=symbol,
            df=pd.DataFrame(),
            quality=DataQuality.UNUSABLE,
            source='truedata'
        )

    def get_last_n_bars(
        self,
        symbol: str,
        n_bars: int = 100,
        interval: str = 'eod'
    ) -> OHLCVData:
        """Get last N bars for a symbol"""
        params = {
            'symbol': symbol,
            'nbars': n_bars,
            'interval': interval,
            'bidask': 0,
            'comp': 'false'
        }

        df, quality = self._request('getlastnbars', params)

        if df is not None and not df.empty:
            df = self._standardize_ohlcv(df)
            return OHLCVData(symbol=symbol, df=df, quality=quality)

        return OHLCVData(symbol=symbol, df=pd.DataFrame(), quality=DataQuality.UNUSABLE)

    def get_bulk_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get LTP for multiple symbols

        Args:
            symbols: List of stock symbols

        Returns:
            Dict mapping symbol to LTP
        """
        params = {
            'symbols': ','.join(symbols)
        }

        df, quality = self._request('getLTPBulk', params)

        if df is not None and not df.empty:
            # Convert to dict
            result = {}
            for _, row in df.iterrows():
                symbol = row.get('symbol') or row.get('Symbol')
                ltp = row.get('ltp') or row.get('LTP') or row.get('close')
                if symbol and ltp:
                    result[symbol] = float(ltp)
            return result

        return {}

    def get_bhavcopy(
        self,
        date: datetime,
        segment: str = 'EQ'  # EQ or FO
    ) -> pd.DataFrame:
        """
        Get bhavcopy (EOD data for all stocks)

        Returns DataFrame with:
        - Symbol, Open, High, Low, Close, Volume
        - Delivery %, Previous Close, Change %
        """
        date_str = date.strftime('%Y-%m-%d')

        params = {
            'segment': segment,
            'date': date_str
        }

        df, quality = self._request('getbhavcopy', params)

        return df if df is not None else pd.DataFrame()

    def get_index_components(self, index_name: str = 'NIFTY 100') -> List[str]:
        """
        Get constituents of an index

        Args:
            index_name: NIFTY 50, NIFTY 100, NIFTY BANK, etc.

        Returns:
            List of symbol names
        """
        params = {
            'indexname': index_name
        }

        df, quality = self._request('getindexcomponents', params)

        if df is not None and not df.empty:
            # Extract symbol column
            symbol_col = None
            for col in ['symbol', 'Symbol', 'SYMBOL']:
                if col in df.columns:
                    symbol_col = col
                    break

            if symbol_col:
                return df[symbol_col].tolist()

        return []

    def get_option_chain(
        self,
        symbol: str,
        expiry: str  # Format: YYMMDD (e.g., '260130')
    ) -> pd.DataFrame:
        """Get option chain for a symbol and expiry"""
        params = {
            'symbol': symbol,
            'expiry': expiry
        }

        df, quality = self._request('getSymbolOptionChain', params)
        return df if df is not None else pd.DataFrame()

    def get_52_week_hl(self, symbol: str) -> Dict[str, float]:
        """Get 52-week high and low"""
        params = {'symbol': symbol}

        df, quality = self._request('get52WeekHL', params)

        if df is not None and not df.empty:
            row = df.iloc[0]
            return {
                'high_52w': float(row.get('52WeekHigh', row.get('high', 0))),
                'low_52w': float(row.get('52WeekLow', row.get('low', 0)))
            }

        return {'high_52w': 0, 'low_52w': 0}

    def get_top_gainers(self, segment: str = 'NSEEQ', top_n: int = 50) -> pd.DataFrame:
        """Get top N gainers"""
        params = {
            'segment': segment,
            'topn': top_n
        }
        df, _ = self._request('gettopngainers', params)
        return df if df is not None else pd.DataFrame()

    def get_top_losers(self, segment: str = 'NSEEQ', top_n: int = 50) -> pd.DataFrame:
        """Get top N losers"""
        params = {
            'segment': segment,
            'topn': top_n
        }
        df, _ = self._request('gettopnlosers', params)
        return df if df is not None else pd.DataFrame()

    def get_corporate_actions(self, symbol: str) -> pd.DataFrame:
        """Get corporate actions (splits, bonuses, dividends)"""
        params = {'symbol': symbol}
        df, _ = self._request('getcorpaction', params)
        return df if df is not None else pd.DataFrame()

    def _standardize_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize OHLCV column names"""
        # Common column mappings
        column_map = {
            'time': 'datetime',
            'Time': 'datetime',
            'timestamp': 'datetime',
            'Timestamp': 'datetime',
            'date': 'datetime',
            'Date': 'datetime',
            'o': 'open',
            'Open': 'open',
            'OPEN': 'open',
            'h': 'high',
            'High': 'high',
            'HIGH': 'high',
            'l': 'low',
            'Low': 'low',
            'LOW': 'low',
            'c': 'close',
            'Close': 'close',
            'CLOSE': 'close',
            'v': 'volume',
            'Volume': 'volume',
            'VOLUME': 'volume',
            'vol': 'volume',
            'oi': 'open_interest',
            'OI': 'open_interest'
        }

        df = df.rename(columns=column_map)

        # Ensure datetime column
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')

        # Ensure numeric columns
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df


class TrueDataCorporateAPI:
    """
    TrueData Corporate Data API

    Endpoints:
    - getFIIDIIData: Institutional flows
    - getSHPListByCompany: Shareholding pattern
    - getResultList: Earnings calendar
    - getRatiosForSymbol: Financial ratios
    - getCorporateInfo: Company info
    - getAllResultsByCompany: Financial statements
    """

    def __init__(self, auth: TrueDataAuth, config: TrueDataConfig):
        self.auth = auth
        self.config = config
        self.base_url = config.corporate_url

    def _request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        response_format: str = 'json'
    ) -> Tuple[Optional[Any], DataQuality]:
        """Make authenticated API request"""
        params['response'] = response_format

        for attempt in range(self.config.max_retries):
            try:
                headers = self.auth.get_auth_header()
                if not headers:
                    return None, DataQuality.UNUSABLE

                url = f"{self.base_url}/{endpoint}"
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout
                )

                if response.status_code == 200:
                    if response_format == 'csv':
                        df = pd.read_csv(StringIO(response.text))
                        return df, DataQuality.EXCELLENT
                    else:
                        return response.json(), DataQuality.EXCELLENT

                elif response.status_code == 401:
                    self.auth.authenticate()
                    continue

                else:
                    logger.error(f"Corporate API error: {response.status_code}")

            except Exception as e:
                logger.error(f"Corporate API request failed: {e}")

            if attempt < self.config.max_retries - 1:
                time.sleep(self.config.retry_delay * (attempt + 1))

        return None, DataQuality.UNUSABLE

    def get_fii_dii_data(
        self,
        date: datetime,
        segment: str = 'cash'  # cash or fo
    ) -> FIIDIIData:
        """
        Get FII/DII flow data for a date

        Args:
            date: Date for data
            segment: 'cash' or 'fo'

        Returns:
            FIIDIIData with buy/sell/net values
        """
        date_str = date.strftime('%y%m%d')

        params = {
            'date': date_str,
            'segment': segment
        }

        data, quality = self._request('getfiidiidata', params, 'csv')

        if data is not None and isinstance(data, pd.DataFrame) and not data.empty:
            row = data.iloc[0]

            return FIIDIIData(
                date=date,
                fii_buy=float(row.get('FII_BUY', row.get('fii_buy', 0))),
                fii_sell=float(row.get('FII_SELL', row.get('fii_sell', 0))),
                fii_net=float(row.get('FII_NET', row.get('fii_net', 0))),
                dii_buy=float(row.get('DII_BUY', row.get('dii_buy', 0))),
                dii_sell=float(row.get('DII_SELL', row.get('dii_sell', 0))),
                dii_net=float(row.get('DII_NET', row.get('dii_net', 0))),
                segment=segment,
                quality=quality,
                is_synthetic=False
            )

        # Return empty data with unusable quality
        return FIIDIIData(
            date=date,
            fii_buy=0, fii_sell=0, fii_net=0,
            dii_buy=0, dii_sell=0, dii_net=0,
            segment=segment,
            quality=DataQuality.UNUSABLE,
            is_synthetic=True
        )

    def get_fii_dii_range(
        self,
        days: int = 5,
        segment: str = 'cash'
    ) -> List[FIIDIIData]:
        """Get FII/DII data for last N trading days"""
        results = []
        current_date = datetime.now()

        for i in range(days + 10):  # Extra days to account for holidays
            check_date = current_date - timedelta(days=i)

            # Skip weekends
            if check_date.weekday() >= 5:
                continue

            data = self.get_fii_dii_data(check_date, segment)

            if data.quality != DataQuality.UNUSABLE:
                results.append(data)

            if len(results) >= days:
                break

        return results

    def get_shareholding_pattern(self, symbol: str) -> ShareholdingData:
        """
        Get shareholding pattern for a company

        Returns promoter holding, pledge %, FII/DII holding
        """
        params = {'symbol': symbol}

        data, quality = self._request('getSHPListByCompany', params)

        if data and isinstance(data, list) and len(data) > 0:
            # Get most recent entry
            latest = data[0]

            return ShareholdingData(
                symbol=symbol,
                promoter_holding=float(latest.get('promoterHolding', 0)),
                promoter_pledge=float(latest.get('promoterPledge', 0)),
                fii_holding=float(latest.get('fiiHolding', 0)),
                dii_holding=float(latest.get('diiHolding', 0)),
                public_holding=float(latest.get('publicHolding', 0)),
                quarter=latest.get('quarter', 'Unknown'),
                quality=quality
            )

        return ShareholdingData(
            symbol=symbol,
            promoter_holding=0, promoter_pledge=0,
            fii_holding=0, dii_holding=0, public_holding=0,
            quarter='Unknown',
            quality=DataQuality.UNUSABLE
        )

    def get_earnings_calendar(
        self,
        date: datetime
    ) -> List[EarningsData]:
        """
        Get earnings results scheduled for a date

        Args:
            date: Date to check

        Returns:
            List of companies with earnings on that date
        """
        date_str = date.strftime('%Y-%m-%d')
        params = {'date': date_str}

        data, quality = self._request('getResultList', params)

        results = []
        if data and isinstance(data, list):
            for item in data:
                results.append(EarningsData(
                    symbol=item.get('symbol', ''),
                    result_date=date,
                    quarter=item.get('quarter', ''),
                    nature=item.get('nature', 'standalone'),
                    quality=quality
                ))

        return results

    def get_upcoming_earnings(
        self,
        symbol: str,
        days_ahead: int = 30
    ) -> Optional[EarningsData]:
        """Check if a stock has earnings in the next N days"""
        for i in range(days_ahead):
            check_date = datetime.now() + timedelta(days=i)

            # Skip weekends
            if check_date.weekday() >= 5:
                continue

            earnings = self.get_earnings_calendar(check_date)

            for e in earnings:
                if e.symbol.upper() == symbol.upper():
                    return e

        return None

    def get_financial_ratios(self, symbol: str) -> FinancialRatios:
        """
        Get financial ratios for a company

        Returns ROE, ROCE, D/E, P/E, P/B, etc.
        """
        params = {'symbol': symbol}

        data, quality = self._request('getratiosForsymbol', params)

        if data and isinstance(data, dict):
            return FinancialRatios(
                symbol=symbol,
                roe=data.get('roe'),
                roce=data.get('roce'),
                debt_to_equity=data.get('debtToEquity'),
                current_ratio=data.get('currentRatio'),
                pe_ratio=data.get('peRatio'),
                pb_ratio=data.get('pbRatio'),
                dividend_yield=data.get('dividendYield'),
                eps=data.get('eps'),
                book_value=data.get('bookValue'),
                quality=quality
            )

        return FinancialRatios(symbol=symbol, quality=DataQuality.UNUSABLE)

    def get_corporate_info(self, symbol: str) -> Dict[str, Any]:
        """Get corporate information for a company"""
        params = {'symbol': symbol}
        data, _ = self._request('getCorporateInfo', params)
        return data if data else {}

    def get_market_cap(self, symbols: List[str]) -> Dict[str, float]:
        """Get market cap for multiple symbols"""
        params = {'symbols': ','.join(symbols)}

        data, _ = self._request('getMarketCap', params, 'csv')

        if data is not None and isinstance(data, pd.DataFrame) and not data.empty:
            result = {}
            for _, row in data.iterrows():
                symbol = row.get('symbol') or row.get('Symbol')
                mcap = row.get('marketCap') or row.get('MarketCap')
                if symbol and mcap:
                    result[symbol] = float(mcap)
            return result

        return {}


class TrueDataClient:
    """
    Unified TrueData Client

    Combines Market Data and Corporate APIs
    Provides high-level methods for trading system
    """

    def __init__(self, config: Optional[TrueDataConfig] = None):
        self.config = config or TrueDataConfig.from_env()
        self.auth = TrueDataAuth(self.config)
        self.market = TrueDataMarketAPI(self.auth, self.config)
        self.corporate = TrueDataCorporateAPI(self.auth, self.config)

        self._is_initialized = False

    def initialize(self) -> bool:
        """
        Initialize client and authenticate

        Returns:
            bool: True if initialization successful
        """
        if not self.config.is_configured:
            logger.warning("TrueData not configured - credentials missing")
            return False

        if self.auth.authenticate():
            self._is_initialized = True
            logger.info("TrueData client initialized successfully")
            return True

        return False

    @property
    def is_available(self) -> bool:
        """Check if TrueData is available and authenticated"""
        return self._is_initialized and self.auth.is_authenticated

    # High-level convenience methods

    def get_stock_data(
        self,
        symbol: str,
        days: int = 365
    ) -> OHLCVData:
        """Get historical data for a stock"""
        return self.market.get_historical_bars(symbol, days=days)

    def get_nifty_100_symbols(self) -> List[str]:
        """Get current Nifty 100 constituents"""
        return self.market.get_index_components('NIFTY 100')

    def get_stock_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """
        Get comprehensive fundamentals for a stock

        Combines: ratios, shareholding, corporate info
        """
        ratios = self.corporate.get_financial_ratios(symbol)
        shareholding = self.corporate.get_shareholding_pattern(symbol)

        return {
            'symbol': symbol,
            'roe': ratios.roe,
            'roce': ratios.roce,
            'debt_to_equity': ratios.debt_to_equity,
            'pe_ratio': ratios.pe_ratio,
            'pb_ratio': ratios.pb_ratio,
            'eps': ratios.eps,
            'promoter_holding': shareholding.promoter_holding,
            'promoter_pledge': shareholding.promoter_pledge,
            'fii_holding': shareholding.fii_holding,
            'dii_holding': shareholding.dii_holding,
            'data_quality': min(ratios.quality.value, shareholding.quality.value)
        }

    def get_fii_dii_summary(self, days: int = 5) -> Dict[str, Any]:
        """
        Get FII/DII flow summary

        Returns:
            Dict with net flows, trend, and sentiment
        """
        flows = self.corporate.get_fii_dii_range(days)

        if not flows:
            return {
                'fii_net_total': 0,
                'dii_net_total': 0,
                'trend': 'UNKNOWN',
                'data_quality': 'UNUSABLE'
            }

        fii_net = sum(f.fii_net for f in flows)
        dii_net = sum(f.dii_net for f in flows)

        # Determine trend
        if fii_net > 1000:  # > 1000 Cr net buying
            trend = 'FII_BUYING'
        elif fii_net < -1000:
            trend = 'FII_SELLING'
        else:
            trend = 'NEUTRAL'

        return {
            'fii_net_total': fii_net,
            'dii_net_total': dii_net,
            'fii_daily_avg': fii_net / len(flows),
            'dii_daily_avg': dii_net / len(flows),
            'trend': trend,
            'days': len(flows),
            'data_quality': 'GOOD' if all(f.quality == DataQuality.EXCELLENT for f in flows) else 'DEGRADED'
        }

    def check_earnings_risk(
        self,
        symbol: str,
        days_buffer: int = 7
    ) -> Dict[str, Any]:
        """
        Check if stock has earnings coming up

        Returns:
            Dict with earnings info and risk assessment
        """
        earnings = self.corporate.get_upcoming_earnings(symbol, days_buffer)

        if earnings:
            days_to_earnings = (earnings.result_date - datetime.now()).days

            return {
                'has_earnings': True,
                'earnings_date': earnings.result_date,
                'days_to_earnings': days_to_earnings,
                'risk_level': 'HIGH' if days_to_earnings <= 3 else 'MEDIUM',
                'position_multiplier': 0.0 if days_to_earnings <= 3 else 0.5
            }

        return {
            'has_earnings': False,
            'earnings_date': None,
            'days_to_earnings': None,
            'risk_level': 'LOW',
            'position_multiplier': 1.0
        }


# Singleton instance for easy access
_client: Optional[TrueDataClient] = None


def get_truedata_client() -> TrueDataClient:
    """Get or create TrueData client singleton"""
    global _client
    if _client is None:
        _client = TrueDataClient()
    return _client
