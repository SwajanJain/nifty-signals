"""Fibonacci retracement and extension analysis."""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np


class FibonacciAnalysis:
    """Calculate Fibonacci levels for trading signals."""

    # Standard Fibonacci ratios
    RETRACEMENT_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    EXTENSION_LEVELS = [1.0, 1.272, 1.414, 1.618, 2.0, 2.618]

    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLCV DataFrame.

        Args:
            df: DataFrame with columns: open, high, low, close, volume
        """
        self.df = df.copy()
        self._find_swing_points()

    def _find_swing_points(self, lookback: int = 60):
        """Find significant swing high and low for Fibonacci calculation."""
        recent = self.df.tail(lookback)

        self.swing_high = recent['high'].max()
        self.swing_low = recent['low'].min()
        self.swing_high_idx = recent['high'].idxmax()
        self.swing_low_idx = recent['low'].idxmin()

        # Determine trend direction (which came first)
        self.is_uptrend = self.swing_low_idx < self.swing_high_idx

    def get_retracement_levels(self) -> Dict[float, float]:
        """
        Calculate Fibonacci retracement levels.

        Returns:
            Dict mapping ratio to price level
        """
        diff = self.swing_high - self.swing_low

        if self.is_uptrend:
            # Uptrend: measure retracement from high
            levels = {
                ratio: self.swing_high - (diff * ratio)
                for ratio in self.RETRACEMENT_LEVELS
            }
        else:
            # Downtrend: measure retracement from low
            levels = {
                ratio: self.swing_low + (diff * ratio)
                for ratio in self.RETRACEMENT_LEVELS
            }

        return levels

    def get_extension_levels(self) -> Dict[float, float]:
        """
        Calculate Fibonacci extension levels.

        Returns:
            Dict mapping ratio to price level
        """
        diff = self.swing_high - self.swing_low

        if self.is_uptrend:
            # Uptrend: extensions above swing high
            levels = {
                ratio: self.swing_low + (diff * ratio)
                for ratio in self.EXTENSION_LEVELS
            }
        else:
            # Downtrend: extensions below swing low
            levels = {
                ratio: self.swing_high - (diff * ratio)
                for ratio in self.EXTENSION_LEVELS
            }

        return levels

    def get_nearest_level(self) -> Tuple[float, float, str]:
        """
        Find the nearest Fibonacci level to current price.

        Returns:
            (level_ratio, level_price, level_type)
        """
        current_price = self.df['close'].iloc[-1]
        retracements = self.get_retracement_levels()

        nearest_ratio = None
        nearest_price = None
        min_distance = float('inf')

        for ratio, price in retracements.items():
            distance = abs(current_price - price)
            if distance < min_distance:
                min_distance = distance
                nearest_ratio = ratio
                nearest_price = price

        level_type = "support" if current_price > nearest_price else "resistance"

        return nearest_ratio, nearest_price, level_type

    def check_fib_level_test(self) -> Tuple[bool, str, int]:
        """
        Check if price is testing a key Fibonacci level.

        Returns:
            (is_testing, description, score)
        """
        current_price = self.df['close'].iloc[-1]
        retracements = self.get_retracement_levels()

        # Key levels that often act as S/R
        key_ratios = [0.382, 0.5, 0.618]

        for ratio in key_ratios:
            level = retracements[ratio]
            distance_pct = abs(current_price - level) / current_price * 100

            if distance_pct < 1.5:  # Within 1.5% of level
                if self.is_uptrend:
                    if current_price > level:
                        return True, f"Bouncing from {ratio:.1%} Fib support (₹{level:.2f})", 1
                    else:
                        return True, f"Testing {ratio:.1%} Fib support (₹{level:.2f})", 0
                else:
                    if current_price < level:
                        return True, f"Rejected at {ratio:.1%} Fib resistance (₹{level:.2f})", -1
                    else:
                        return True, f"Testing {ratio:.1%} Fib resistance (₹{level:.2f})", 0

        return False, "", 0

    def check_golden_ratio(self) -> Tuple[bool, str, int]:
        """
        Check for 0.618 (golden ratio) setups.

        Returns:
            (detected, description, score)
        """
        current_price = self.df['close'].iloc[-1]
        retracements = self.get_retracement_levels()

        golden_level = retracements[0.618]
        distance_pct = abs(current_price - golden_level) / current_price * 100

        if distance_pct < 2:
            if self.is_uptrend and current_price >= golden_level:
                return True, f"Golden ratio (61.8%) support held at ₹{golden_level:.2f}", 2
            elif not self.is_uptrend and current_price <= golden_level:
                return True, f"Golden ratio (61.8%) resistance holding at ₹{golden_level:.2f}", -2

        return False, "", 0

    def get_target_levels(self) -> Dict:
        """
        Get potential target levels based on Fibonacci extensions.

        Returns:
            Dict with target information
        """
        current_price = self.df['close'].iloc[-1]
        extensions = self.get_extension_levels()
        retracements = self.get_retracement_levels()

        if self.is_uptrend:
            # Targets are extension levels above current price
            targets = [
                {'ratio': r, 'price': p, 'distance_pct': (p - current_price) / current_price * 100}
                for r, p in extensions.items()
                if p > current_price
            ]
            # Stops are retracement levels below current price
            stops = [
                {'ratio': r, 'price': p, 'distance_pct': (current_price - p) / current_price * 100}
                for r, p in retracements.items()
                if p < current_price and r >= 0.382
            ]
        else:
            # Targets are extension levels below current price
            targets = [
                {'ratio': r, 'price': p, 'distance_pct': (current_price - p) / current_price * 100}
                for r, p in extensions.items()
                if p < current_price
            ]
            # Stops are retracement levels above current price
            stops = [
                {'ratio': r, 'price': p, 'distance_pct': (p - current_price) / current_price * 100}
                for r, p in retracements.items()
                if p > current_price and r >= 0.382
            ]

        return {
            'trend': 'uptrend' if self.is_uptrend else 'downtrend',
            'swing_high': self.swing_high,
            'swing_low': self.swing_low,
            'targets': sorted(targets, key=lambda x: abs(x['distance_pct']))[:3],
            'stops': sorted(stops, key=lambda x: x['distance_pct'])[:2],
        }

    def get_all_signals(self) -> Dict:
        """Get all Fibonacci-based signals."""
        patterns = []
        total_score = 0

        # Check Fibonacci level tests
        testing, desc, score = self.check_fib_level_test()
        if testing:
            patterns.append({'pattern': desc, 'score': score})
            total_score += score

        # Check golden ratio
        golden, desc, score = self.check_golden_ratio()
        if golden:
            patterns.append({'pattern': desc, 'score': score})
            total_score += score

        # Get levels info
        retracements = self.get_retracement_levels()
        extensions = self.get_extension_levels()
        targets = self.get_target_levels()

        return {
            'patterns': patterns,
            'total_score': total_score,
            'retracements': retracements,
            'extensions': extensions,
            'targets': targets,
            'description': patterns[0]['pattern'] if patterns else f"Trend: {'Up' if self.is_uptrend else 'Down'}, no Fib signal"
        }
