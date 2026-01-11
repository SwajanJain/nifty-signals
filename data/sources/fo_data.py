"""
F&O Data Module - Option Chain Analysis for Indian Markets.

Critical for understanding:
- Smart money positioning (OI analysis)
- Market sentiment (PCR)
- Key levels (Max Pain, high OI strikes)
- Directional bias from FII F&O positions

This is one of the most important edge-generators in Indian markets.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
import requests
import json
from rich.console import Console

console = Console()


class OISentiment(Enum):
    """Sentiment based on OI analysis."""
    STRONG_BULLISH = "STRONG_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    STRONG_BEARISH = "STRONG_BEARISH"


@dataclass
class OptionData:
    """Single option contract data."""
    strike_price: float
    expiry_date: str
    option_type: str  # CE or PE
    open_interest: int
    change_in_oi: int
    volume: int
    ltp: float
    iv: float
    bid: float
    ask: float


@dataclass
class OptionChainAnalysis:
    """Complete option chain analysis."""
    symbol: str
    spot_price: float
    timestamp: datetime

    # PCR metrics
    pcr_oi: float  # Put-Call Ratio by OI
    pcr_volume: float  # Put-Call Ratio by Volume
    pcr_change: float  # Change in PCR

    # Max Pain
    max_pain: float
    max_pain_distance: float  # % distance from spot

    # Key levels from OI
    highest_call_oi_strike: float
    highest_put_oi_strike: float
    immediate_resistance: float  # Nearest high call OI above spot
    immediate_support: float  # Nearest high put OI below spot

    # OI buildup
    call_oi_buildup: int  # Net change in call OI
    put_oi_buildup: int  # Net change in put OI
    oi_interpretation: str

    # Sentiment
    sentiment: OISentiment
    sentiment_score: int  # -5 to +5

    # IV metrics
    iv_percentile: float  # Current IV vs historical
    iv_skew: float  # Put IV - Call IV (positive = fear)

    # Raw data
    call_data: List[OptionData] = field(default_factory=list)
    put_data: List[OptionData] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"F&O ANALYSIS: {self.symbol}")
        lines.append("=" * 60)

        lines.append(f"\nSpot: ₹{self.spot_price:,.2f}")
        lines.append(f"Sentiment: {self.sentiment.value} (Score: {self.sentiment_score:+d})")

        lines.append(f"\n[PCR Analysis]")
        lines.append(f"PCR (OI): {self.pcr_oi:.2f}")
        lines.append(f"PCR (Volume): {self.pcr_volume:.2f}")

        lines.append(f"\n[Max Pain]")
        lines.append(f"Max Pain: ₹{self.max_pain:,.0f} ({self.max_pain_distance:+.1f}% from spot)")

        lines.append(f"\n[Key Levels from OI]")
        lines.append(f"Resistance: ₹{self.immediate_resistance:,.0f} (Highest Call OI: ₹{self.highest_call_oi_strike:,.0f})")
        lines.append(f"Support: ₹{self.immediate_support:,.0f} (Highest Put OI: ₹{self.highest_put_oi_strike:,.0f})")

        lines.append(f"\n[OI Buildup]")
        lines.append(f"Call OI Change: {self.call_oi_buildup:+,}")
        lines.append(f"Put OI Change: {self.put_oi_buildup:+,}")
        lines.append(f"Interpretation: {self.oi_interpretation}")

        lines.append(f"\n[Volatility]")
        lines.append(f"IV Percentile: {self.iv_percentile:.0f}%")
        lines.append(f"IV Skew: {self.iv_skew:+.1f}%")

        lines.append("=" * 60)
        return "\n".join(lines)


class FODataFetcher:
    """
    Fetch F&O data from NSE.

    Uses NSE's public APIs with proper headers to avoid blocking.
    """

    def __init__(self):
        self.base_url = "https://www.nseindia.com"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.nseindia.com/option-chain',
        }
        self._initialized = False

    def _init_session(self):
        """Initialize session with NSE cookies."""
        if self._initialized:
            return

        try:
            # First request to get cookies
            self.session.get(
                f"{self.base_url}/option-chain",
                headers=self.headers,
                timeout=10
            )
            self._initialized = True
        except Exception as e:
            console.print(f"[yellow]Warning: Could not initialize NSE session: {e}[/yellow]")

    def fetch_option_chain(self, symbol: str = "NIFTY") -> Optional[Dict]:
        """
        Fetch option chain data from NSE.

        Args:
            symbol: Index or stock symbol (NIFTY, BANKNIFTY, or stock)

        Returns:
            Raw option chain data or None
        """
        self._init_session()

        try:
            if symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
                url = f"{self.base_url}/api/option-chain-indices?symbol={symbol}"
            else:
                url = f"{self.base_url}/api/option-chain-equities?symbol={symbol}"

            response = self.session.get(url, headers=self.headers, timeout=15)

            if response.status_code == 200:
                return response.json()
            else:
                console.print(f"[red]Error fetching option chain: {response.status_code}[/red]")
                return None

        except Exception as e:
            console.print(f"[red]Exception fetching option chain: {e}[/red]")
            return None

    def analyze_option_chain(self, symbol: str = "NIFTY") -> Optional[OptionChainAnalysis]:
        """
        Fetch and analyze option chain.

        Args:
            symbol: Symbol to analyze

        Returns:
            OptionChainAnalysis or None
        """
        data = self.fetch_option_chain(symbol)

        if data is None:
            return self._get_fallback_analysis(symbol)

        try:
            records = data.get('records', {})
            option_data = records.get('data', [])
            spot_price = records.get('underlyingValue', 0)

            if not option_data or spot_price == 0:
                return self._get_fallback_analysis(symbol)

            # Parse option data
            calls = []
            puts = []
            call_oi_total = 0
            put_oi_total = 0
            call_oi_change = 0
            put_oi_change = 0
            call_volume = 0
            put_volume = 0

            for row in option_data:
                strike = row.get('strikePrice', 0)

                # Call data
                ce = row.get('CE', {})
                if ce:
                    call_oi = ce.get('openInterest', 0)
                    call_oi_chg = ce.get('changeinOpenInterest', 0)
                    call_vol = ce.get('totalTradedVolume', 0)

                    call_oi_total += call_oi
                    call_oi_change += call_oi_chg
                    call_volume += call_vol

                    calls.append({
                        'strike': strike,
                        'oi': call_oi,
                        'oi_change': call_oi_chg,
                        'volume': call_vol,
                        'ltp': ce.get('lastPrice', 0),
                        'iv': ce.get('impliedVolatility', 0)
                    })

                # Put data
                pe = row.get('PE', {})
                if pe:
                    put_oi = pe.get('openInterest', 0)
                    put_oi_chg = pe.get('changeinOpenInterest', 0)
                    put_vol = pe.get('totalTradedVolume', 0)

                    put_oi_total += put_oi
                    put_oi_change += put_oi_chg
                    put_volume += put_vol

                    puts.append({
                        'strike': strike,
                        'oi': put_oi,
                        'oi_change': put_oi_chg,
                        'volume': put_vol,
                        'ltp': pe.get('lastPrice', 0),
                        'iv': pe.get('impliedVolatility', 0)
                    })

            # Calculate PCR
            pcr_oi = put_oi_total / call_oi_total if call_oi_total > 0 else 1
            pcr_volume = put_volume / call_volume if call_volume > 0 else 1

            # Find highest OI strikes
            calls_df = pd.DataFrame(calls)
            puts_df = pd.DataFrame(puts)

            highest_call_oi_strike = calls_df.loc[calls_df['oi'].idxmax(), 'strike'] if len(calls_df) > 0 else spot_price
            highest_put_oi_strike = puts_df.loc[puts_df['oi'].idxmax(), 'strike'] if len(puts_df) > 0 else spot_price

            # Find immediate support/resistance
            calls_above_spot = calls_df[calls_df['strike'] > spot_price].sort_values('strike')
            puts_below_spot = puts_df[puts_df['strike'] < spot_price].sort_values('strike', ascending=False)

            # Immediate resistance = nearest strike with significant call OI
            if len(calls_above_spot) > 0:
                high_oi_calls = calls_above_spot[calls_above_spot['oi'] > calls_above_spot['oi'].quantile(0.7)]
                immediate_resistance = high_oi_calls['strike'].iloc[0] if len(high_oi_calls) > 0 else calls_above_spot['strike'].iloc[0]
            else:
                immediate_resistance = spot_price * 1.02

            # Immediate support = nearest strike with significant put OI
            if len(puts_below_spot) > 0:
                high_oi_puts = puts_below_spot[puts_below_spot['oi'] > puts_below_spot['oi'].quantile(0.7)]
                immediate_support = high_oi_puts['strike'].iloc[0] if len(high_oi_puts) > 0 else puts_below_spot['strike'].iloc[0]
            else:
                immediate_support = spot_price * 0.98

            # Calculate Max Pain
            max_pain = self._calculate_max_pain(calls_df, puts_df, spot_price)
            max_pain_distance = ((max_pain - spot_price) / spot_price) * 100

            # OI interpretation
            oi_interpretation = self._interpret_oi_changes(call_oi_change, put_oi_change, spot_price)

            # Calculate sentiment
            sentiment, sentiment_score = self._calculate_sentiment(
                pcr_oi, pcr_volume, call_oi_change, put_oi_change,
                spot_price, highest_call_oi_strike, highest_put_oi_strike
            )

            # IV analysis
            avg_call_iv = calls_df['iv'].mean() if len(calls_df) > 0 else 15
            avg_put_iv = puts_df['iv'].mean() if len(puts_df) > 0 else 15
            iv_skew = avg_put_iv - avg_call_iv

            return OptionChainAnalysis(
                symbol=symbol,
                spot_price=spot_price,
                timestamp=datetime.now(),
                pcr_oi=pcr_oi,
                pcr_volume=pcr_volume,
                pcr_change=0,  # Would need historical data
                max_pain=max_pain,
                max_pain_distance=max_pain_distance,
                highest_call_oi_strike=highest_call_oi_strike,
                highest_put_oi_strike=highest_put_oi_strike,
                immediate_resistance=immediate_resistance,
                immediate_support=immediate_support,
                call_oi_buildup=call_oi_change,
                put_oi_buildup=put_oi_change,
                oi_interpretation=oi_interpretation,
                sentiment=sentiment,
                sentiment_score=sentiment_score,
                iv_percentile=50,  # Would need historical IV data
                iv_skew=iv_skew
            )

        except Exception as e:
            console.print(f"[red]Error analyzing option chain: {e}[/red]")
            return self._get_fallback_analysis(symbol)

    def _calculate_max_pain(
        self,
        calls_df: pd.DataFrame,
        puts_df: pd.DataFrame,
        spot_price: float
    ) -> float:
        """
        Calculate Max Pain - the strike where option writers lose minimum.

        Max Pain theory: Market tends to gravitate towards the strike where
        maximum number of options expire worthless.
        """
        if len(calls_df) == 0 or len(puts_df) == 0:
            return spot_price

        strikes = sorted(set(calls_df['strike'].tolist() + puts_df['strike'].tolist()))

        min_pain = float('inf')
        max_pain_strike = spot_price

        for strike in strikes:
            # Calculate pain for call writers if price settles at this strike
            call_pain = 0
            for _, row in calls_df.iterrows():
                if strike > row['strike']:
                    # Call is ITM, loss for writer
                    call_pain += (strike - row['strike']) * row['oi']

            # Calculate pain for put writers if price settles at this strike
            put_pain = 0
            for _, row in puts_df.iterrows():
                if strike < row['strike']:
                    # Put is ITM, loss for writer
                    put_pain += (row['strike'] - strike) * row['oi']

            total_pain = call_pain + put_pain

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = strike

        return max_pain_strike

    def _interpret_oi_changes(
        self,
        call_oi_change: int,
        put_oi_change: int,
        spot_price: float
    ) -> str:
        """Interpret OI changes to understand market positioning."""
        # Long buildup: Price up + OI up
        # Short buildup: Price down + OI up
        # Long unwinding: Price down + OI down
        # Short covering: Price up + OI down

        if call_oi_change > 0 and put_oi_change > 0:
            if call_oi_change > put_oi_change:
                return "Call writing dominant - Resistance building"
            else:
                return "Put writing dominant - Support building"
        elif call_oi_change > 0 and put_oi_change < 0:
            return "Bearish: Call writing + Put unwinding"
        elif call_oi_change < 0 and put_oi_change > 0:
            return "Bullish: Call unwinding + Put writing"
        elif call_oi_change < 0 and put_oi_change < 0:
            if abs(call_oi_change) > abs(put_oi_change):
                return "Short covering - Bullish"
            else:
                return "Long unwinding - Bearish"
        else:
            return "Mixed signals"

    def _calculate_sentiment(
        self,
        pcr_oi: float,
        pcr_volume: float,
        call_oi_change: int,
        put_oi_change: int,
        spot_price: float,
        highest_call_oi: float,
        highest_put_oi: float
    ) -> Tuple[OISentiment, int]:
        """Calculate overall sentiment from F&O data."""
        score = 0

        # PCR analysis
        # PCR > 1.2 = Bullish (more puts = hedging/support)
        # PCR < 0.8 = Bearish (more calls = resistance)
        if pcr_oi > 1.3:
            score += 2
        elif pcr_oi > 1.1:
            score += 1
        elif pcr_oi < 0.7:
            score -= 2
        elif pcr_oi < 0.9:
            score -= 1

        # OI change analysis
        net_oi_change = put_oi_change - call_oi_change
        if net_oi_change > 100000:  # Significant put writing
            score += 2
        elif net_oi_change > 50000:
            score += 1
        elif net_oi_change < -100000:  # Significant call writing
            score -= 2
        elif net_oi_change < -50000:
            score -= 1

        # Distance from max OI strikes
        call_distance = (highest_call_oi - spot_price) / spot_price * 100
        put_distance = (spot_price - highest_put_oi) / spot_price * 100

        # If closer to put support than call resistance = bullish
        if put_distance < call_distance * 0.7:
            score += 1
        elif call_distance < put_distance * 0.7:
            score -= 1

        # Determine sentiment
        if score >= 3:
            sentiment = OISentiment.STRONG_BULLISH
        elif score >= 1:
            sentiment = OISentiment.BULLISH
        elif score <= -3:
            sentiment = OISentiment.STRONG_BEARISH
        elif score <= -1:
            sentiment = OISentiment.BEARISH
        else:
            sentiment = OISentiment.NEUTRAL

        return sentiment, score

    def _get_fallback_analysis(self, symbol: str) -> OptionChainAnalysis:
        """Return fallback analysis when data unavailable."""
        # Use approximate values based on typical market
        spot = 24000 if symbol == "NIFTY" else 50000 if symbol == "BANKNIFTY" else 1000

        return OptionChainAnalysis(
            symbol=symbol,
            spot_price=spot,
            timestamp=datetime.now(),
            pcr_oi=1.0,
            pcr_volume=1.0,
            pcr_change=0,
            max_pain=spot,
            max_pain_distance=0,
            highest_call_oi_strike=spot * 1.02,
            highest_put_oi_strike=spot * 0.98,
            immediate_resistance=spot * 1.01,
            immediate_support=spot * 0.99,
            call_oi_buildup=0,
            put_oi_buildup=0,
            oi_interpretation="Data unavailable - using fallback",
            sentiment=OISentiment.NEUTRAL,
            sentiment_score=0,
            iv_percentile=50,
            iv_skew=0
        )

    def get_stock_fo_data(self, symbol: str) -> Optional[Dict]:
        """
        Get F&O data for a specific stock.

        Returns simplified analysis for stock options.
        """
        analysis = self.analyze_option_chain(symbol)

        if analysis is None:
            return None

        return {
            'symbol': symbol,
            'spot_price': analysis.spot_price,
            'pcr': analysis.pcr_oi,
            'max_pain': analysis.max_pain,
            'support': analysis.immediate_support,
            'resistance': analysis.immediate_resistance,
            'sentiment': analysis.sentiment.value,
            'sentiment_score': analysis.sentiment_score,
            'oi_interpretation': analysis.oi_interpretation
        }


def get_nifty_fo_levels() -> Dict:
    """Quick function to get Nifty F&O levels."""
    fetcher = FODataFetcher()
    analysis = fetcher.analyze_option_chain("NIFTY")

    if analysis:
        return {
            'spot': analysis.spot_price,
            'max_pain': analysis.max_pain,
            'pcr': analysis.pcr_oi,
            'resistance': analysis.immediate_resistance,
            'support': analysis.immediate_support,
            'sentiment': analysis.sentiment.value,
            'call_resistance': analysis.highest_call_oi_strike,
            'put_support': analysis.highest_put_oi_strike
        }
    return {}
