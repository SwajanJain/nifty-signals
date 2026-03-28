"""Divergence detection between price and indicators."""

from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
import pandas_ta as ta

from config import RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL


class DivergenceDetector:
    """Detect bullish and bearish divergences."""

    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLCV DataFrame.

        Args:
            df: DataFrame with columns: open, high, low, close, volume
        """
        self.df = df.copy()
        self._calculate_indicators()
        self._find_pivots()

    def _calculate_indicators(self):
        """Calculate RSI and MACD for divergence detection."""
        self.df['rsi'] = ta.rsi(self.df['close'], length=RSI_PERIOD)

        macd = ta.macd(self.df['close'], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        macd_col = [c for c in macd.columns if c.startswith('MACD_')][0]
        self.df['macd'] = macd[macd_col]

    def _find_pivots(self, lookback: int = 30, window: int = 5):
        """Find pivot points in price and indicators."""
        recent = self.df.tail(lookback)

        self.price_highs = []
        self.price_lows = []
        self.rsi_highs = []
        self.rsi_lows = []
        self.macd_highs = []
        self.macd_lows = []

        for i in range(window, len(recent) - window):
            idx = recent.index[i]

            # Price pivots
            if recent['high'].iloc[i] == recent['high'].iloc[i-window:i+window+1].max():
                self.price_highs.append({'idx': i, 'date': idx, 'price': recent['high'].iloc[i]})
            if recent['low'].iloc[i] == recent['low'].iloc[i-window:i+window+1].min():
                self.price_lows.append({'idx': i, 'date': idx, 'price': recent['low'].iloc[i]})

            # RSI pivots
            rsi_val = recent['rsi'].iloc[i]
            if pd.notna(rsi_val):
                rsi_window = recent['rsi'].iloc[i-window:i+window+1].dropna()
                if len(rsi_window) > 0:
                    if rsi_val == rsi_window.max():
                        self.rsi_highs.append({'idx': i, 'date': idx, 'value': rsi_val})
                    if rsi_val == rsi_window.min():
                        self.rsi_lows.append({'idx': i, 'date': idx, 'value': rsi_val})

            # MACD pivots
            macd_val = recent['macd'].iloc[i]
            if pd.notna(macd_val):
                macd_window = recent['macd'].iloc[i-window:i+window+1].dropna()
                if len(macd_window) > 0:
                    if macd_val == macd_window.max():
                        self.macd_highs.append({'idx': i, 'date': idx, 'value': macd_val})
                    if macd_val == macd_window.min():
                        self.macd_lows.append({'idx': i, 'date': idx, 'value': macd_val})

    def detect_rsi_divergence(self) -> Tuple[bool, str, int]:
        """
        Detect RSI divergence.

        Bullish: Price makes lower low, RSI makes higher low
        Bearish: Price makes higher high, RSI makes lower high

        Returns:
            (detected, description, score)
        """
        # Bullish divergence (check lows)
        if len(self.price_lows) >= 2 and len(self.rsi_lows) >= 2:
            p1, p2 = self.price_lows[-2], self.price_lows[-1]
            r1, r2 = self.rsi_lows[-2], self.rsi_lows[-1]

            # Price lower low, RSI higher low
            if p2['price'] < p1['price'] and r2['value'] > r1['value']:
                return True, f"Bullish RSI Divergence (RSI rising while price falling)", 2

        # Bearish divergence (check highs)
        if len(self.price_highs) >= 2 and len(self.rsi_highs) >= 2:
            p1, p2 = self.price_highs[-2], self.price_highs[-1]
            r1, r2 = self.rsi_highs[-2], self.rsi_highs[-1]

            # Price higher high, RSI lower high
            if p2['price'] > p1['price'] and r2['value'] < r1['value']:
                return True, f"Bearish RSI Divergence (RSI falling while price rising)", -2

        return False, "", 0

    def detect_macd_divergence(self) -> Tuple[bool, str, int]:
        """
        Detect MACD divergence.

        Bullish: Price makes lower low, MACD makes higher low
        Bearish: Price makes higher high, MACD makes lower high

        Returns:
            (detected, description, score)
        """
        # Bullish divergence (check lows)
        if len(self.price_lows) >= 2 and len(self.macd_lows) >= 2:
            p1, p2 = self.price_lows[-2], self.price_lows[-1]
            m1, m2 = self.macd_lows[-2], self.macd_lows[-1]

            # Price lower low, MACD higher low
            if p2['price'] < p1['price'] and m2['value'] > m1['value']:
                return True, f"Bullish MACD Divergence (Momentum strengthening)", 2

        # Bearish divergence (check highs)
        if len(self.price_highs) >= 2 and len(self.macd_highs) >= 2:
            p1, p2 = self.price_highs[-2], self.price_highs[-1]
            m1, m2 = self.macd_highs[-2], self.macd_highs[-1]

            # Price higher high, MACD lower high
            if p2['price'] > p1['price'] and m2['value'] < m1['value']:
                return True, f"Bearish MACD Divergence (Momentum weakening)", -2

        return False, "", 0

    def detect_hidden_divergence(self) -> Tuple[bool, str, int]:
        """
        Detect hidden divergence (trend continuation signal).

        Hidden Bullish: Price makes higher low, RSI makes lower low (uptrend continuation)
        Hidden Bearish: Price makes lower high, RSI makes higher high (downtrend continuation)

        Returns:
            (detected, description, score)
        """
        # Hidden Bullish (uptrend continuation)
        if len(self.price_lows) >= 2 and len(self.rsi_lows) >= 2:
            p1, p2 = self.price_lows[-2], self.price_lows[-1]
            r1, r2 = self.rsi_lows[-2], self.rsi_lows[-1]

            # Price higher low, RSI lower low
            if p2['price'] > p1['price'] and r2['value'] < r1['value']:
                return True, "Hidden Bullish Divergence (Uptrend continuation)", 1

        # Hidden Bearish (downtrend continuation)
        if len(self.price_highs) >= 2 and len(self.rsi_highs) >= 2:
            p1, p2 = self.price_highs[-2], self.price_highs[-1]
            r1, r2 = self.rsi_highs[-2], self.rsi_highs[-1]

            # Price lower high, RSI higher high
            if p2['price'] < p1['price'] and r2['value'] > r1['value']:
                return True, "Hidden Bearish Divergence (Downtrend continuation)", -1

        return False, "", 0

    def detect_rsi_trendline_break(self) -> Tuple[bool, str, int]:
        """Detect RSI trendline break.

        Draws a trendline between two RSI pivot highs (for downtrend) or
        two RSI pivot lows (for uptrend).  If the latest RSI crosses above
        a descending trendline → bullish break.  If it crosses below an
        ascending trendline → bearish break.

        Returns:
            (detected, description, score)
        """
        latest_rsi = self.df['rsi'].iloc[-1] if pd.notna(self.df['rsi'].iloc[-1]) else None
        if latest_rsi is None:
            return False, "", 0

        # Bullish: RSI breaks above a descending trendline
        # (line connecting two successive lower RSI highs)
        if len(self.rsi_highs) >= 2:
            r1, r2 = self.rsi_highs[-2], self.rsi_highs[-1]
            if r2['value'] < r1['value']:  # descending trendline
                # Interpolate where the trendline would be NOW
                slope = (r2['value'] - r1['value']) / max(r2['idx'] - r1['idx'], 1)
                bars_since_r2 = (len(self.df.tail(30)) - 1) - r2['idx']
                projected = r2['value'] + slope * bars_since_r2
                if latest_rsi > projected and projected > 0:
                    return True, f"RSI broke above descending trendline ({latest_rsi:.0f} > {projected:.0f})", 1

        # Bearish: RSI breaks below an ascending trendline
        if len(self.rsi_lows) >= 2:
            r1, r2 = self.rsi_lows[-2], self.rsi_lows[-1]
            if r2['value'] > r1['value']:  # ascending trendline
                slope = (r2['value'] - r1['value']) / max(r2['idx'] - r1['idx'], 1)
                bars_since_r2 = (len(self.df.tail(30)) - 1) - r2['idx']
                projected = r2['value'] + slope * bars_since_r2
                if latest_rsi < projected:
                    return True, f"RSI broke below ascending trendline ({latest_rsi:.0f} < {projected:.0f})", -1

        return False, "", 0

    def get_all_divergences(self) -> Dict:
        """Get all detected divergences."""
        patterns = []
        total_score = 0

        # Check RSI divergence
        detected, desc, score = self.detect_rsi_divergence()
        if detected:
            patterns.append({'pattern': desc, 'score': score})
            total_score += score

        # Check MACD divergence
        detected, desc, score = self.detect_macd_divergence()
        if detected:
            patterns.append({'pattern': desc, 'score': score})
            total_score += score

        # Check hidden divergence
        detected, desc, score = self.detect_hidden_divergence()
        if detected:
            patterns.append({'pattern': desc, 'score': score})
            total_score += score

        # Check RSI trendline break
        detected, desc, score = self.detect_rsi_trendline_break()
        if detected:
            patterns.append({'pattern': desc, 'score': score})
            total_score += score

        return {
            'patterns': patterns,
            'total_score': total_score,
            'description': patterns[0]['pattern'] if patterns else "No divergence detected"
        }
