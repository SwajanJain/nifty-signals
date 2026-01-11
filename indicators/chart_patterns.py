"""Chart pattern detection - triangles, H&S, double tops, flags, wedges."""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from scipy import stats


class ChartPatterns:
    """Detect chart patterns for trading signals."""

    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLCV DataFrame.

        Args:
            df: DataFrame with columns: open, high, low, close, volume
        """
        self.df = df.copy()
        self._find_pivots()

    def _find_pivots(self, lookback: int = 60, pivot_window: int = 5):
        """Find pivot highs and lows for pattern detection."""
        recent = self.df.tail(lookback)

        self.pivot_highs = []
        self.pivot_lows = []

        for i in range(pivot_window, len(recent) - pivot_window):
            # Pivot high
            if recent['high'].iloc[i] == recent['high'].iloc[i-pivot_window:i+pivot_window+1].max():
                self.pivot_highs.append({
                    'index': i,
                    'price': recent['high'].iloc[i],
                    'date': recent.index[i]
                })

            # Pivot low
            if recent['low'].iloc[i] == recent['low'].iloc[i-pivot_window:i+pivot_window+1].min():
                self.pivot_lows.append({
                    'index': i,
                    'price': recent['low'].iloc[i],
                    'date': recent.index[i]
                })

    def detect_double_top_bottom(self) -> Tuple[bool, str, int]:
        """
        Detect Double Top (bearish) or Double Bottom (bullish).

        Returns:
            (detected, description, score)
        """
        if len(self.pivot_highs) < 2 or len(self.pivot_lows) < 2:
            return False, "", 0

        # Check for Double Top (two similar highs)
        recent_highs = self.pivot_highs[-3:]
        if len(recent_highs) >= 2:
            h1, h2 = recent_highs[-2], recent_highs[-1]
            # Highs within 2% of each other
            if abs(h1['price'] - h2['price']) / h1['price'] < 0.02:
                current_price = self.df['close'].iloc[-1]
                # Confirm if price is below the neckline
                neckline = min([p['price'] for p in self.pivot_lows[-2:]])
                if current_price < neckline:
                    return True, f"Double Top confirmed at ₹{h1['price']:.2f}", -2

                # Pattern forming
                if current_price < h1['price'] * 0.98:
                    return True, f"Double Top forming at ₹{h1['price']:.2f}", -1

        # Check for Double Bottom (two similar lows)
        recent_lows = self.pivot_lows[-3:]
        if len(recent_lows) >= 2:
            l1, l2 = recent_lows[-2], recent_lows[-1]
            # Lows within 2% of each other
            if abs(l1['price'] - l2['price']) / l1['price'] < 0.02:
                current_price = self.df['close'].iloc[-1]
                # Confirm if price is above the neckline
                neckline = max([p['price'] for p in self.pivot_highs[-2:]])
                if current_price > neckline:
                    return True, f"Double Bottom confirmed at ₹{l1['price']:.2f}", 2

                # Pattern forming
                if current_price > l1['price'] * 1.02:
                    return True, f"Double Bottom forming at ₹{l1['price']:.2f}", 1

        return False, "", 0

    def detect_head_shoulders(self) -> Tuple[bool, str, int]:
        """
        Detect Head and Shoulders (bearish) or Inverse H&S (bullish).

        Returns:
            (detected, description, score)
        """
        if len(self.pivot_highs) < 3 or len(self.pivot_lows) < 2:
            return False, "", 0

        # Head and Shoulders (bearish)
        recent_highs = self.pivot_highs[-4:]
        if len(recent_highs) >= 3:
            left, head, right = recent_highs[-3], recent_highs[-2], recent_highs[-1]

            # Head is higher than shoulders, shoulders roughly equal
            if (head['price'] > left['price'] and
                head['price'] > right['price'] and
                abs(left['price'] - right['price']) / left['price'] < 0.03):

                current_price = self.df['close'].iloc[-1]
                neckline = min([p['price'] for p in self.pivot_lows[-3:]])

                if current_price < neckline:
                    return True, f"Head & Shoulders confirmed (Target: ₹{neckline - (head['price'] - neckline):.2f})", -3

                if current_price < right['price']:
                    return True, "Head & Shoulders forming (Watch neckline)", -1

        # Inverse Head and Shoulders (bullish)
        recent_lows = self.pivot_lows[-4:]
        if len(recent_lows) >= 3:
            left, head, right = recent_lows[-3], recent_lows[-2], recent_lows[-1]

            # Head is lower than shoulders, shoulders roughly equal
            if (head['price'] < left['price'] and
                head['price'] < right['price'] and
                abs(left['price'] - right['price']) / left['price'] < 0.03):

                current_price = self.df['close'].iloc[-1]
                neckline = max([p['price'] for p in self.pivot_highs[-3:]])

                if current_price > neckline:
                    return True, f"Inverse H&S confirmed (Target: ₹{neckline + (neckline - head['price']):.2f})", 3

                if current_price > right['price']:
                    return True, "Inverse H&S forming (Watch neckline)", 1

        return False, "", 0

    def detect_triangle(self) -> Tuple[bool, str, int]:
        """
        Detect Triangle patterns (ascending, descending, symmetric).

        Returns:
            (detected, description, score)
        """
        if len(self.pivot_highs) < 3 or len(self.pivot_lows) < 3:
            return False, "", 0

        # Get last few pivots
        highs = [(p['index'], p['price']) for p in self.pivot_highs[-4:]]
        lows = [(p['index'], p['price']) for p in self.pivot_lows[-4:]]

        if len(highs) < 2 or len(lows) < 2:
            return False, "", 0

        # Calculate trendlines using linear regression
        high_indices = [h[0] for h in highs]
        high_prices = [h[1] for h in highs]
        low_indices = [l[0] for l in lows]
        low_prices = [l[1] for l in lows]

        high_slope, _, _, _, _ = stats.linregress(high_indices, high_prices)
        low_slope, _, _, _, _ = stats.linregress(low_indices, low_prices)

        # Normalize slopes
        avg_price = self.df['close'].mean()
        high_slope_pct = high_slope / avg_price * 100
        low_slope_pct = low_slope / avg_price * 100

        current_price = self.df['close'].iloc[-1]

        # Ascending Triangle: flat highs, rising lows
        if abs(high_slope_pct) < 0.1 and low_slope_pct > 0.2:
            resistance = np.mean(high_prices)
            if current_price > resistance:
                return True, f"Ascending Triangle breakout above ₹{resistance:.2f}", 2
            return True, f"Ascending Triangle forming (Resistance: ₹{resistance:.2f})", 1

        # Descending Triangle: falling highs, flat lows
        if high_slope_pct < -0.2 and abs(low_slope_pct) < 0.1:
            support = np.mean(low_prices)
            if current_price < support:
                return True, f"Descending Triangle breakdown below ₹{support:.2f}", -2
            return True, f"Descending Triangle forming (Support: ₹{support:.2f})", -1

        # Symmetric Triangle: converging trendlines
        if high_slope_pct < -0.1 and low_slope_pct > 0.1:
            return True, "Symmetric Triangle forming (Breakout pending)", 0

        return False, "", 0

    def detect_flag_pennant(self) -> Tuple[bool, str, int]:
        """
        Detect Flag and Pennant patterns.

        Returns:
            (detected, description, score)
        """
        if len(self.df) < 20:
            return False, "", 0

        # Look for strong move followed by consolidation
        recent = self.df.tail(20)
        first_half = recent.head(10)
        second_half = recent.tail(10)

        # Calculate moves
        first_move = (first_half['close'].iloc[-1] - first_half['close'].iloc[0]) / first_half['close'].iloc[0]
        second_range = (second_half['high'].max() - second_half['low'].min()) / second_half['close'].mean()

        # Bull Flag: strong up move, tight consolidation
        if first_move > 0.05 and second_range < 0.03:
            current_price = self.df['close'].iloc[-1]
            flag_high = second_half['high'].max()
            if current_price > flag_high:
                return True, "Bull Flag breakout", 2
            return True, "Bull Flag forming (Consolidation after rally)", 1

        # Bear Flag: strong down move, tight consolidation
        if first_move < -0.05 and second_range < 0.03:
            current_price = self.df['close'].iloc[-1]
            flag_low = second_half['low'].min()
            if current_price < flag_low:
                return True, "Bear Flag breakdown", -2
            return True, "Bear Flag forming (Consolidation after drop)", -1

        return False, "", 0

    def detect_wedge(self) -> Tuple[bool, str, int]:
        """
        Detect Rising and Falling Wedge patterns.

        Returns:
            (detected, description, score)
        """
        if len(self.pivot_highs) < 3 or len(self.pivot_lows) < 3:
            return False, "", 0

        # Get recent pivots
        highs = [(p['index'], p['price']) for p in self.pivot_highs[-4:]]
        lows = [(p['index'], p['price']) for p in self.pivot_lows[-4:]]

        if len(highs) < 2 or len(lows) < 2:
            return False, "", 0

        high_indices = [h[0] for h in highs]
        high_prices = [h[1] for h in highs]
        low_indices = [l[0] for l in lows]
        low_prices = [l[1] for l in lows]

        high_slope, _, _, _, _ = stats.linregress(high_indices, high_prices)
        low_slope, _, _, _, _ = stats.linregress(low_indices, low_prices)

        avg_price = self.df['close'].mean()
        high_slope_pct = high_slope / avg_price * 100
        low_slope_pct = low_slope / avg_price * 100

        # Rising Wedge (bearish): both trendlines rising, converging
        if high_slope_pct > 0.1 and low_slope_pct > 0.1 and high_slope_pct < low_slope_pct:
            current_price = self.df['close'].iloc[-1]
            support = min(low_prices)
            if current_price < support:
                return True, "Rising Wedge breakdown (Bearish)", -2
            return True, "Rising Wedge forming (Bearish bias)", -1

        # Falling Wedge (bullish): both trendlines falling, converging
        if high_slope_pct < -0.1 and low_slope_pct < -0.1 and high_slope_pct > low_slope_pct:
            current_price = self.df['close'].iloc[-1]
            resistance = max(high_prices)
            if current_price > resistance:
                return True, "Falling Wedge breakout (Bullish)", 2
            return True, "Falling Wedge forming (Bullish bias)", 1

        return False, "", 0

    def get_all_patterns(self) -> Dict:
        """Get all detected chart patterns."""
        patterns = []
        total_score = 0

        # Check each pattern type
        checks = [
            self.detect_double_top_bottom,
            self.detect_head_shoulders,
            self.detect_triangle,
            self.detect_flag_pennant,
            self.detect_wedge,
        ]

        for check in checks:
            detected, description, score = check()
            if detected:
                patterns.append({
                    'pattern': description,
                    'score': score
                })
                total_score += score

        return {
            'patterns': patterns,
            'total_score': total_score,
            'description': patterns[0]['pattern'] if patterns else "No chart patterns detected"
        }
