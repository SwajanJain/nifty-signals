"""
Market Context Engine.

Aggregates all context layers:
- Global macro (US, Asia, Europe, commodities)
- Domestic (Nifty, VIX, FII/DII)
- Regime detection
- Sector strength

Inspired by global macro traders like Soros, Druckenmiller, Dalio.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
import yfinance as yf
from rich.console import Console

console = Console()


class RiskSentiment(Enum):
    """Global risk sentiment."""
    STRONG_RISK_ON = "STRONG_RISK_ON"
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"
    STRONG_RISK_OFF = "STRONG_RISK_OFF"


@dataclass
class GlobalMarketData:
    """Global market data snapshot."""
    # US Markets
    sp500_change: float = 0.0
    nasdaq_change: float = 0.0
    us_vix: float = 15.0
    us_10y_yield: float = 4.0

    # Asia
    nikkei_change: float = 0.0
    hang_seng_change: float = 0.0
    sgx_nifty_change: float = 0.0

    # Commodities
    crude_change: float = 0.0
    gold_change: float = 0.0

    # Currency
    dxy_change: float = 0.0
    usdinr_change: float = 0.0

    # Computed
    risk_score: float = 0.0
    sentiment: RiskSentiment = RiskSentiment.NEUTRAL

    def __post_init__(self):
        self.risk_score = self._calculate_risk_score()
        self.sentiment = self._determine_sentiment()

    def _calculate_risk_score(self) -> float:
        """
        Calculate overall risk score (-5 to +5).

        Positive = risk-on (good for longs)
        Negative = risk-off (be cautious)
        """
        score = 0

        # US market (most important)
        if self.sp500_change > 1:
            score += 1.5
        elif self.sp500_change > 0:
            score += 0.5
        elif self.sp500_change > -1:
            score -= 0.5
        else:
            score -= 1.5

        # US VIX
        if self.us_vix < 15:
            score += 1
        elif self.us_vix < 20:
            score += 0
        elif self.us_vix < 25:
            score -= 1
        else:
            score -= 2

        # Asia
        asia_avg = (self.nikkei_change + self.hang_seng_change) / 2
        if asia_avg > 0.5:
            score += 0.5
        elif asia_avg < -0.5:
            score -= 0.5

        # SGX Nifty (direct indication)
        if self.sgx_nifty_change > 0.5:
            score += 1
        elif self.sgx_nifty_change < -0.5:
            score -= 1

        # Crude (too high is bad for India)
        if self.crude_change > 2:
            score -= 0.5
        elif self.crude_change < -2:
            score += 0.5

        # DXY (strong dollar = bad for EM)
        if self.dxy_change > 0.5:
            score -= 0.5
        elif self.dxy_change < -0.5:
            score += 0.5

        return max(-5, min(5, score))

    def _determine_sentiment(self) -> RiskSentiment:
        """Determine overall sentiment."""
        if self.risk_score >= 3:
            return RiskSentiment.STRONG_RISK_ON
        elif self.risk_score >= 1:
            return RiskSentiment.RISK_ON
        elif self.risk_score <= -3:
            return RiskSentiment.STRONG_RISK_OFF
        elif self.risk_score <= -1:
            return RiskSentiment.RISK_OFF
        else:
            return RiskSentiment.NEUTRAL


@dataclass
class MarketContext:
    """Complete market context for trading decisions."""
    # Global
    global_data: GlobalMarketData

    # Domestic
    nifty_level: float = 0.0
    nifty_change_pct: float = 0.0
    india_vix: float = 12.0
    india_vix_change: float = 0.0

    # Flows (in Cr)
    fii_flow: float = 0.0
    dii_flow: float = 0.0

    # Regime
    regime: str = "NEUTRAL"
    regime_score: int = 0
    regime_multiplier: float = 0.5
    should_trade: bool = True

    # Sector
    top_sectors: List[str] = field(default_factory=list)
    weak_sectors: List[str] = field(default_factory=list)

    # Time context
    is_expiry_week: bool = False
    days_to_expiry: int = 0
    is_result_season: bool = False

    # Timestamp
    updated_at: datetime = field(default_factory=datetime.now)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = []
        lines.append("=" * 60)
        lines.append("MARKET CONTEXT")
        lines.append("=" * 60)

        lines.append(f"\n[GLOBAL]")
        lines.append(f"Sentiment: {self.global_data.sentiment.value}")
        lines.append(f"Risk Score: {self.global_data.risk_score:+.1f}")
        lines.append(f"US: S&P {self.global_data.sp500_change:+.1f}% | VIX {self.global_data.us_vix:.1f}")
        lines.append(f"Asia: Nikkei {self.global_data.nikkei_change:+.1f}% | HSI {self.global_data.hang_seng_change:+.1f}%")
        lines.append(f"SGX Nifty: {self.global_data.sgx_nifty_change:+.1f}%")
        lines.append(f"Crude: {self.global_data.crude_change:+.1f}% | DXY: {self.global_data.dxy_change:+.1f}%")

        lines.append(f"\n[DOMESTIC]")
        lines.append(f"Nifty: {self.nifty_level:,.0f} ({self.nifty_change_pct:+.1f}%)")
        lines.append(f"India VIX: {self.india_vix:.1f} ({self.india_vix_change:+.1f}%)")
        lines.append(f"FII: ₹{self.fii_flow:,.0f} Cr | DII: ₹{self.dii_flow:,.0f} Cr")

        lines.append(f"\n[REGIME]")
        lines.append(f"Regime: {self.regime} (Score: {self.regime_score:+d})")
        lines.append(f"Position Size: {self.regime_multiplier*100:.0f}% of normal")
        lines.append(f"Should Trade: {'YES' if self.should_trade else 'NO'}")

        lines.append(f"\n[SECTORS]")
        lines.append(f"Focus: {', '.join(self.top_sectors)}")
        lines.append(f"Avoid: {', '.join(self.weak_sectors)}")

        if self.is_expiry_week:
            lines.append(f"\n⚠️ EXPIRY WEEK - {self.days_to_expiry} days to expiry")

        lines.append(f"\nUpdated: {self.updated_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append("=" * 60)

        return "\n".join(lines)


class MarketContextBuilder:
    """
    Build complete market context.

    Fetches data from multiple sources and aggregates.
    """

    def __init__(self):
        self._cache: Dict = {}
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=15)

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if self._cache_time is None:
            return False
        return datetime.now() - self._cache_time < self._cache_duration

    def fetch_global_data(self) -> GlobalMarketData:
        """Fetch global market data."""
        console.print("[yellow]Fetching global market data...[/yellow]")

        data = {}

        # Tickers to fetch
        tickers = {
            'sp500': '^GSPC',
            'nasdaq': '^IXIC',
            'vix': '^VIX',
            'nikkei': '^N225',
            'hang_seng': '^HSI',
            'crude': 'CL=F',
            'gold': 'GC=F',
            'dxy': 'DX-Y.NYB',
            'usdinr': 'INR=X',
            'us10y': '^TNX'
        }

        for name, ticker in tickers.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")
                if len(hist) >= 2:
                    current = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    change_pct = ((current - prev) / prev) * 100
                    data[name] = {'current': current, 'change': change_pct}
                else:
                    data[name] = {'current': 0, 'change': 0}
            except Exception as e:
                data[name] = {'current': 0, 'change': 0}

        # SGX Nifty (proxy - use Nifty futures if available)
        sgx_change = 0
        try:
            nifty_fut = yf.Ticker("^NSEI")
            hist = nifty_fut.history(period="5d")
            if len(hist) >= 2:
                sgx_change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
        except:
            pass

        return GlobalMarketData(
            sp500_change=data['sp500']['change'],
            nasdaq_change=data['nasdaq']['change'],
            us_vix=data['vix']['current'],
            us_10y_yield=data['us10y']['current'],
            nikkei_change=data['nikkei']['change'],
            hang_seng_change=data['hang_seng']['change'],
            sgx_nifty_change=sgx_change,
            crude_change=data['crude']['change'],
            gold_change=data['gold']['change'],
            dxy_change=data['dxy']['change'],
            usdinr_change=data['usdinr']['change']
        )

    def fetch_domestic_data(self) -> Dict:
        """Fetch domestic market data."""
        console.print("[yellow]Fetching domestic market data...[/yellow]")

        result = {
            'nifty_level': 0,
            'nifty_change': 0,
            'india_vix': 12,
            'vix_change': 0
        }

        try:
            # Nifty 50
            nifty = yf.Ticker("^NSEI")
            hist = nifty.history(period="5d")
            if len(hist) >= 2:
                result['nifty_level'] = hist['Close'].iloc[-1]
                result['nifty_change'] = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
        except:
            pass

        try:
            # India VIX
            vix = yf.Ticker("^INDIAVIX")
            hist = vix.history(period="5d")
            if len(hist) >= 2:
                result['india_vix'] = hist['Close'].iloc[-1]
                result['vix_change'] = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
        except:
            pass

        return result

    def get_expiry_info(self) -> Tuple[bool, int]:
        """
        Check if it's expiry week and days to expiry.

        NSE expiry is last Thursday of the month.
        """
        today = datetime.now()

        # Find last Thursday of current month
        import calendar
        last_day = calendar.monthrange(today.year, today.month)[1]
        last_date = datetime(today.year, today.month, last_day)

        # Find last Thursday
        while last_date.weekday() != 3:  # Thursday = 3
            last_date -= timedelta(days=1)

        # Days to expiry
        days_to_expiry = (last_date - today).days

        # Is it expiry week (within 5 days)?
        is_expiry_week = 0 <= days_to_expiry <= 5

        return is_expiry_week, max(0, days_to_expiry)

    def build_context(
        self,
        regime_data: Optional[Dict] = None,
        sector_data: Optional[List] = None,
        fii_flow: float = 0,
        dii_flow: float = 0
    ) -> MarketContext:
        """
        Build complete market context.

        Args:
            regime_data: Pre-fetched regime data (optional)
            sector_data: Pre-fetched sector data (optional)
            fii_flow: FII flow in Cr (manual input or from API)
            dii_flow: DII flow in Cr (manual input or from API)

        Returns:
            Complete MarketContext
        """
        # Check cache
        if self._is_cache_valid() and 'context' in self._cache:
            return self._cache['context']

        # Fetch global data
        global_data = self.fetch_global_data()

        # Fetch domestic data
        domestic = self.fetch_domestic_data()

        # Get regime if not provided
        if regime_data is None:
            from indicators.market_regime import RegimeDetector
            try:
                detector = RegimeDetector()
                regime_data = detector.detect_regime()
            except:
                regime_data = {
                    'regime_name': 'NEUTRAL',
                    'total_score': 0,
                    'position_size_multiplier': 0.5,
                    'should_trade': True
                }

        # Get sector data if not provided
        top_sectors = []
        weak_sectors = []
        if sector_data:
            top_sectors = [s.sector for s in sector_data[:3]]
            weak_sectors = [s.sector for s in sector_data[-3:]]

        # Get expiry info
        is_expiry, days_to_expiry = self.get_expiry_info()

        # Build context
        context = MarketContext(
            global_data=global_data,
            nifty_level=domestic['nifty_level'],
            nifty_change_pct=domestic['nifty_change'],
            india_vix=domestic['india_vix'],
            india_vix_change=domestic['vix_change'],
            fii_flow=fii_flow,
            dii_flow=dii_flow,
            regime=regime_data.get('regime_name', 'NEUTRAL'),
            regime_score=regime_data.get('total_score', 0),
            regime_multiplier=regime_data.get('position_size_multiplier', 0.5),
            should_trade=regime_data.get('should_trade', True),
            top_sectors=top_sectors,
            weak_sectors=weak_sectors,
            is_expiry_week=is_expiry,
            days_to_expiry=days_to_expiry,
            is_result_season=self._is_result_season()
        )

        # Cache
        self._cache['context'] = context
        self._cache_time = datetime.now()

        return context

    def _is_result_season(self) -> bool:
        """Check if it's earnings season (rough approximation)."""
        month = datetime.now().month
        # Typically Jan, Apr, Jul, Oct are result seasons
        return month in [1, 4, 7, 10]


class LiquidityAnalyzer:
    """
    Analyze stock liquidity for position sizing.
    """

    def __init__(self, min_adv_cr: float = 10):
        """
        Initialize analyzer.

        Args:
            min_adv_cr: Minimum average daily value in Crores
        """
        self.min_adv = min_adv_cr * 1e7  # Convert to rupees

    def analyze_liquidity(
        self,
        df: pd.DataFrame,
        current_price: float,
        lookback: int = 20
    ) -> Dict:
        """
        Analyze stock liquidity.

        Returns:
            Dict with liquidity metrics
        """
        if len(df) < lookback:
            lookback = len(df)

        # Calculate ADV (Average Daily Value)
        recent = df.tail(lookback)
        avg_volume = recent['volume'].mean()
        avg_value = avg_volume * current_price

        # Volume trend
        recent_vol = df['volume'].tail(5).mean()
        older_vol = df['volume'].tail(20).head(15).mean()
        vol_trend = (recent_vol / older_vol - 1) * 100 if older_vol > 0 else 0

        # Liquidity score (0-100)
        if avg_value >= self.min_adv * 5:
            score = 100
        elif avg_value >= self.min_adv * 2:
            score = 80
        elif avg_value >= self.min_adv:
            score = 60
        elif avg_value >= self.min_adv * 0.5:
            score = 40
        else:
            score = 20

        return {
            'avg_daily_value': avg_value,
            'avg_daily_volume': avg_volume,
            'volume_trend': vol_trend,
            'liquidity_score': score,
            'meets_minimum': avg_value >= self.min_adv,
            'max_position_value': avg_value * 0.02  # Max 2% of ADV
        }

    def get_max_position(
        self,
        avg_daily_value: float,
        max_pct_of_adv: float = 0.02
    ) -> float:
        """
        Get maximum position value based on liquidity.

        Args:
            avg_daily_value: Average daily traded value
            max_pct_of_adv: Maximum percentage of ADV for position

        Returns:
            Maximum position value in rupees
        """
        return avg_daily_value * max_pct_of_adv
