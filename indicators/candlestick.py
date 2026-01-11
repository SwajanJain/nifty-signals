"""Candlestick pattern recognition."""

from typing import Dict, List, Tuple
import pandas as pd
import numpy as np


class CandlestickPatterns:
    """Detect candlestick patterns for trading signals."""

    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLCV DataFrame.

        Args:
            df: DataFrame with columns: open, high, low, close, volume
        """
        self.df = df.copy()
        self._calculate_candle_properties()

    def _calculate_candle_properties(self):
        """Calculate candle body and wick properties."""
        self.df['body'] = self.df['close'] - self.df['open']
        self.df['body_abs'] = abs(self.df['body'])
        self.df['upper_wick'] = self.df['high'] - self.df[['open', 'close']].max(axis=1)
        self.df['lower_wick'] = self.df[['open', 'close']].min(axis=1) - self.df['low']
        self.df['range'] = self.df['high'] - self.df['low']
        self.df['body_pct'] = self.df['body_abs'] / self.df['range'].replace(0, np.nan)

        # Average body size for comparison
        self.df['avg_body'] = self.df['body_abs'].rolling(20).mean()

    def _is_bullish(self, idx: int) -> bool:
        """Check if candle is bullish."""
        return self.df['close'].iloc[idx] > self.df['open'].iloc[idx]

    def _is_bearish(self, idx: int) -> bool:
        """Check if candle is bearish."""
        return self.df['close'].iloc[idx] < self.df['open'].iloc[idx]

    def detect_doji(self) -> Tuple[bool, str]:
        """
        Detect Doji pattern (indecision).
        Body is very small relative to range.
        """
        latest = self.df.iloc[-1]

        if pd.isna(latest['body_pct']):
            return False, ""

        # Doji: body less than 10% of range
        if latest['body_pct'] < 0.1 and latest['range'] > 0:
            # Determine type
            if latest['upper_wick'] > latest['lower_wick'] * 2:
                return True, "Gravestone Doji (Bearish)"
            elif latest['lower_wick'] > latest['upper_wick'] * 2:
                return True, "Dragonfly Doji (Bullish)"
            else:
                return True, "Doji (Indecision)"

        return False, ""

    def detect_hammer(self) -> Tuple[bool, str]:
        """
        Detect Hammer (bullish) or Hanging Man (bearish).
        Small body at top, long lower wick.
        """
        latest = self.df.iloc[-1]

        if latest['range'] == 0:
            return False, ""

        # Long lower wick (at least 2x body)
        # Small upper wick
        if (latest['lower_wick'] >= latest['body_abs'] * 2 and
            latest['upper_wick'] < latest['body_abs'] * 0.5):

            # Check trend context
            prev_closes = self.df['close'].iloc[-6:-1]
            in_downtrend = prev_closes.iloc[-1] < prev_closes.iloc[0]

            if in_downtrend:
                return True, "Hammer (Bullish reversal)"
            else:
                return True, "Hanging Man (Bearish reversal)"

        return False, ""

    def detect_shooting_star(self) -> Tuple[bool, str]:
        """
        Detect Shooting Star (bearish) or Inverted Hammer (bullish).
        Small body at bottom, long upper wick.
        """
        latest = self.df.iloc[-1]

        if latest['range'] == 0:
            return False, ""

        # Long upper wick (at least 2x body)
        # Small lower wick
        if (latest['upper_wick'] >= latest['body_abs'] * 2 and
            latest['lower_wick'] < latest['body_abs'] * 0.5):

            # Check trend context
            prev_closes = self.df['close'].iloc[-6:-1]
            in_uptrend = prev_closes.iloc[-1] > prev_closes.iloc[0]

            if in_uptrend:
                return True, "Shooting Star (Bearish reversal)"
            else:
                return True, "Inverted Hammer (Bullish reversal)"

        return False, ""

    def detect_engulfing(self) -> Tuple[bool, str]:
        """
        Detect Bullish or Bearish Engulfing pattern.
        Current candle completely engulfs previous candle's body.
        """
        if len(self.df) < 2:
            return False, ""

        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        # Bullish Engulfing
        if (self._is_bearish(-2) and self._is_bullish(-1) and
            curr['open'] < prev['close'] and curr['close'] > prev['open'] and
            curr['body_abs'] > prev['body_abs']):
            return True, "Bullish Engulfing (Strong reversal)"

        # Bearish Engulfing
        if (self._is_bullish(-2) and self._is_bearish(-1) and
            curr['open'] > prev['close'] and curr['close'] < prev['open'] and
            curr['body_abs'] > prev['body_abs']):
            return True, "Bearish Engulfing (Strong reversal)"

        return False, ""

    def detect_morning_evening_star(self) -> Tuple[bool, str]:
        """
        Detect Morning Star (bullish) or Evening Star (bearish).
        Three-candle reversal pattern.
        """
        if len(self.df) < 3:
            return False, ""

        first = self.df.iloc[-3]
        second = self.df.iloc[-2]
        third = self.df.iloc[-1]

        # Morning Star: bearish, small body (gap down), bullish (closes above midpoint of first)
        if (self._is_bearish(-3) and
            second['body_abs'] < first['body_abs'] * 0.3 and
            self._is_bullish(-1) and
            third['close'] > (first['open'] + first['close']) / 2):
            return True, "Morning Star (Bullish reversal)"

        # Evening Star: bullish, small body (gap up), bearish (closes below midpoint of first)
        if (self._is_bullish(-3) and
            second['body_abs'] < first['body_abs'] * 0.3 and
            self._is_bearish(-1) and
            third['close'] < (first['open'] + first['close']) / 2):
            return True, "Evening Star (Bearish reversal)"

        return False, ""

    def detect_three_soldiers_crows(self) -> Tuple[bool, str]:
        """
        Detect Three White Soldiers (bullish) or Three Black Crows (bearish).
        Three consecutive strong candles in same direction.
        """
        if len(self.df) < 3:
            return False, ""

        last3 = self.df.iloc[-3:]
        avg_body = self.df['avg_body'].iloc[-1]

        if pd.isna(avg_body):
            return False, ""

        # Three White Soldiers: 3 bullish candles, each closing higher
        all_bullish = all(last3['close'] > last3['open'])
        closes_rising = last3['close'].is_monotonic_increasing
        strong_bodies = all(last3['body_abs'] > avg_body * 0.5)

        if all_bullish and closes_rising and strong_bodies:
            return True, "Three White Soldiers (Strong bullish)"

        # Three Black Crows: 3 bearish candles, each closing lower
        all_bearish = all(last3['close'] < last3['open'])
        closes_falling = last3['close'].is_monotonic_decreasing

        if all_bearish and closes_falling and strong_bodies:
            return True, "Three Black Crows (Strong bearish)"

        return False, ""

    def detect_marubozu(self) -> Tuple[bool, str]:
        """
        Detect Marubozu (strong momentum candle).
        Very small or no wicks, large body.
        """
        latest = self.df.iloc[-1]
        avg_body = self.df['avg_body'].iloc[-1]

        if pd.isna(avg_body) or latest['range'] == 0:
            return False, ""

        # Large body with small wicks
        if (latest['body_abs'] > avg_body * 1.5 and
            latest['upper_wick'] < latest['body_abs'] * 0.1 and
            latest['lower_wick'] < latest['body_abs'] * 0.1):

            if self._is_bullish(-1):
                return True, "Bullish Marubozu (Strong momentum)"
            else:
                return True, "Bearish Marubozu (Strong momentum)"

        return False, ""

    def get_all_patterns(self) -> Dict:
        """Get all detected candlestick patterns."""
        patterns = []
        total_score = 0

        # Check each pattern
        checks = [
            self.detect_doji,
            self.detect_hammer,
            self.detect_shooting_star,
            self.detect_engulfing,
            self.detect_morning_evening_star,
            self.detect_three_soldiers_crows,
            self.detect_marubozu,
        ]

        for check in checks:
            detected, description = check()
            if detected:
                # Score based on pattern type
                if "Bullish" in description or "bullish" in description:
                    if "Strong" in description or "Engulfing" in description:
                        score = 2
                    else:
                        score = 1
                elif "Bearish" in description or "bearish" in description:
                    if "Strong" in description or "Engulfing" in description:
                        score = -2
                    else:
                        score = -1
                else:
                    score = 0  # Indecision patterns

                patterns.append({
                    'pattern': description,
                    'score': score
                })
                total_score += score

        return {
            'patterns': patterns,
            'total_score': total_score,
            'description': patterns[0]['pattern'] if patterns else "No patterns detected"
        }
