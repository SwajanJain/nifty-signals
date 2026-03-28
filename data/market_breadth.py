"""
Market Breadth Calculator - FREE (Uses Existing Data)

Calculates breadth metrics from NIFTY 50/100 constituent data
that you already fetch via yfinance. NO additional API needed!

Simons Gate: "Confirms if move is broad-based or narrow"

Metrics:
- % stocks above EMA20/50/200
- Advance/Decline ratio
- New Highs vs New Lows
- Breadth thrust indicators
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Dict, List, Optional
from pathlib import Path
import yfinance as yf
from datetime import datetime

# NIFTY 50 symbols (sample - you have full list in config)
NIFTY50_SAMPLE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "ITC.NS",
    "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "WIPRO.NS",
]


class MarketBreadthCalculator:
    """
    Calculate market breadth from constituent data.

    Simons: "Breadth confirms if the move is genuine or narrow"
    """

    def __init__(self, symbols: Optional[List[str]] = None):
        """
        Initialize with list of symbols.

        Args:
            symbols: List of NSE symbols with .NS suffix
        """
        self.symbols = symbols or NIFTY50_SAMPLE

    def fetch_constituent_data(self, period: str = "3mo") -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for all constituents.

        Args:
            period: yfinance period string

        Returns:
            Dict of symbol -> DataFrame
        """
        data = {}
        print(f"Fetching data for {len(self.symbols)} symbols...")

        for symbol in self.symbols:
            try:
                df = yf.download(symbol, period=period, progress=False)
                if len(df) > 50:  # Need enough data for EMAs
                    # Ensure lowercase columns
                    df.columns = [c.lower() for c in df.columns]
                    data[symbol] = df
            except Exception as e:
                print(f"Failed to fetch {symbol}: {e}")

        print(f"Successfully fetched {len(data)} symbols")
        return data

    def calculate_breadth(self, data: Dict[str, pd.DataFrame]) -> Dict:
        """
        Calculate all breadth metrics.

        Args:
            data: Dict of symbol -> OHLCV DataFrame

        Returns:
            Comprehensive breadth analysis
        """
        if not data:
            return {"status": "NO_DATA"}

        total = len(data)

        # Calculate metrics for each stock
        above_ema20 = 0
        above_ema50 = 0
        above_ema200 = 0
        advancing = 0
        declining = 0
        new_highs_20d = 0
        new_lows_20d = 0

        stock_details = []

        for symbol, df in data.items():
            try:
                close = df['close'].iloc[-1]
                prev_close = df['close'].iloc[-2]

                # Calculate EMAs
                ema20 = ta.ema(df['close'], length=20)
                ema50 = ta.ema(df['close'], length=50)
                ema200 = ta.ema(df['close'], length=200) if len(df) >= 200 else None

                # Above EMAs
                if ema20 is not None and close > ema20.iloc[-1]:
                    above_ema20 += 1
                if ema50 is not None and close > ema50.iloc[-1]:
                    above_ema50 += 1
                if ema200 is not None and close > ema200.iloc[-1]:
                    above_ema200 += 1

                # Advance/Decline
                if close > prev_close:
                    advancing += 1
                elif close < prev_close:
                    declining += 1

                # 20-day highs/lows
                high_20d = df['high'].tail(20).max()
                low_20d = df['low'].tail(20).min()

                if close >= high_20d * 0.99:  # Within 1% of high
                    new_highs_20d += 1
                if close <= low_20d * 1.01:  # Within 1% of low
                    new_lows_20d += 1

                stock_details.append({
                    "symbol": symbol.replace(".NS", ""),
                    "close": close,
                    "above_ema20": close > ema20.iloc[-1] if ema20 is not None else False,
                    "above_ema50": close > ema50.iloc[-1] if ema50 is not None else False,
                    "change_pct": (close - prev_close) / prev_close * 100,
                })

            except Exception as e:
                continue

        # Calculate percentages
        pct_above_ema20 = (above_ema20 / total) * 100
        pct_above_ema50 = (above_ema50 / total) * 100
        pct_above_ema200 = (above_ema200 / total) * 100 if above_ema200 > 0 else 0

        # Advance/Decline ratio
        ad_ratio = advancing / declining if declining > 0 else advancing

        # Breadth thrust (McClellan-style)
        # Strong thrust: >80% above EMA20
        # Weak: <40% above EMA20
        if pct_above_ema20 > 80:
            breadth_thrust = "STRONG_BULLISH"
        elif pct_above_ema20 > 60:
            breadth_thrust = "BULLISH"
        elif pct_above_ema20 > 40:
            breadth_thrust = "NEUTRAL"
        elif pct_above_ema20 > 20:
            breadth_thrust = "BEARISH"
        else:
            breadth_thrust = "STRONG_BEARISH"

        # Overall breadth signal
        if pct_above_ema50 > 70 and ad_ratio > 2:
            breadth_signal = "STRONGLY_BULLISH"
            simons_gate = True
        elif pct_above_ema50 > 50 and ad_ratio > 1:
            breadth_signal = "BULLISH"
            simons_gate = True
        elif pct_above_ema50 > 30:
            breadth_signal = "NEUTRAL"
            simons_gate = True
        else:
            breadth_signal = "BEARISH"
            simons_gate = False

        # Calculate breadth multiplier for position sizing
        if breadth_signal == "STRONGLY_BULLISH":
            breadth_multiplier = 1.2
        elif breadth_signal == "BULLISH":
            breadth_multiplier = 1.0
        elif breadth_signal == "NEUTRAL":
            breadth_multiplier = 0.8
        else:
            breadth_multiplier = 0.5

        return {
            "status": "OK",
            "timestamp": datetime.now().isoformat(),
            "total_stocks": total,
            "metrics": {
                "above_ema20": above_ema20,
                "above_ema50": above_ema50,
                "above_ema200": above_ema200,
                "pct_above_ema20": round(pct_above_ema20, 1),
                "pct_above_ema50": round(pct_above_ema50, 1),
                "pct_above_ema200": round(pct_above_ema200, 1),
                "advancing": advancing,
                "declining": declining,
                "unchanged": total - advancing - declining,
                "ad_ratio": round(ad_ratio, 2),
                "new_highs_20d": new_highs_20d,
                "new_lows_20d": new_lows_20d,
            },
            "analysis": {
                "breadth_thrust": breadth_thrust,
                "breadth_signal": breadth_signal,
                "interpretation": self._interpret_breadth(pct_above_ema50, ad_ratio, breadth_thrust),
            },
            "signal_impact": {
                "breadth_multiplier": breadth_multiplier,
                "simons_gate": simons_gate,
                "recommendation": self._get_recommendation(breadth_signal, pct_above_ema50),
            },
        }

    def _interpret_breadth(self, pct_ema50: float, ad_ratio: float, thrust: str) -> str:
        """Generate human-readable interpretation."""
        parts = []

        if pct_ema50 > 70:
            parts.append("Broad-based rally - most stocks participating")
        elif pct_ema50 > 50:
            parts.append("Healthy breadth - majority above key MA")
        elif pct_ema50 > 30:
            parts.append("Mixed breadth - selective participation")
        else:
            parts.append("Weak breadth - few stocks holding up")

        if ad_ratio > 2:
            parts.append("Strong advance/decline confirms momentum")
        elif ad_ratio < 0.5:
            parts.append("Weak advance/decline suggests distribution")

        if thrust == "STRONG_BULLISH":
            parts.append("Breadth thrust detected - bullish signal")

        return "; ".join(parts)

    def _get_recommendation(self, signal: str, pct_ema50: float) -> str:
        """Generate actionable recommendation."""
        if signal == "STRONGLY_BULLISH":
            return "FULL SIZE: Broad participation supports aggressive positioning"
        elif signal == "BULLISH":
            return "NORMAL SIZE: Healthy breadth supports standard positioning"
        elif signal == "NEUTRAL":
            return "REDUCED SIZE: Mixed breadth suggests caution"
        else:
            return "MINIMAL SIZE: Weak breadth - avoid new longs or reduce existing"


def calculate_market_breadth(symbols: Optional[List[str]] = None) -> Dict:
    """
    Main function to calculate market breadth.

    Args:
        symbols: Optional list of NSE symbols (with .NS suffix)

    Returns:
        Complete breadth analysis
    """
    calculator = MarketBreadthCalculator(symbols)
    data = calculator.fetch_constituent_data()
    return calculator.calculate_breadth(data)


def calculate_breadth_from_existing(data: Dict[str, pd.DataFrame]) -> Dict:
    """
    Calculate breadth from already-fetched data.

    Use this if you've already fetched stock data in your pipeline.
    """
    calculator = MarketBreadthCalculator()
    return calculator.calculate_breadth(data)


if __name__ == "__main__":
    print("=" * 60)
    print("MARKET BREADTH CALCULATOR TEST")
    print("=" * 60)

    result = calculate_market_breadth()

    print(f"\nStatus: {result.get('status')}")
    print(f"Stocks analyzed: {result.get('total_stocks')}")

    metrics = result.get('metrics', {})
    print(f"\n% Above EMA20: {metrics.get('pct_above_ema20')}%")
    print(f"% Above EMA50: {metrics.get('pct_above_ema50')}%")
    print(f"% Above EMA200: {metrics.get('pct_above_ema200')}%")
    print(f"\nAdvancing: {metrics.get('advancing')}")
    print(f"Declining: {metrics.get('declining')}")
    print(f"A/D Ratio: {metrics.get('ad_ratio')}")
    print(f"\nNew 20d Highs: {metrics.get('new_highs_20d')}")
    print(f"New 20d Lows: {metrics.get('new_lows_20d')}")

    analysis = result.get('analysis', {})
    print(f"\nBreadth Thrust: {analysis.get('breadth_thrust')}")
    print(f"Breadth Signal: {analysis.get('breadth_signal')}")
    print(f"\nInterpretation: {analysis.get('interpretation')}")

    impact = result.get('signal_impact', {})
    print(f"\nBreadth Multiplier: {impact.get('breadth_multiplier')}")
    print(f"Simons Gate: {'PASS' if impact.get('simons_gate') else 'FAIL'}")
    print(f"\nRecommendation: {impact.get('recommendation')}")
