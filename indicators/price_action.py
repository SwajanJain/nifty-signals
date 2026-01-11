"""Price action analysis - support/resistance, breakouts, trends."""

from typing import Dict, List, Tuple
import pandas as pd
import numpy as np


class PriceActionAnalyzer:
    """Analyze price action patterns and key levels."""

    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLCV DataFrame.

        Args:
            df: DataFrame with columns: open, high, low, close, volume
        """
        self.df = df.copy()
        self._find_support_resistance()

    def _find_support_resistance(self, lookback: int = 50):
        """Find support and resistance levels from recent data."""
        recent = self.df.tail(lookback)

        # Find local highs and lows
        self.resistance_levels = self._find_pivots(recent['high'], is_high=True)
        self.support_levels = self._find_pivots(recent['low'], is_high=False)

    def _find_pivots(self, series: pd.Series, is_high: bool, window: int = 5) -> List[float]:
        """
        Find pivot points in price data.

        Args:
            series: Price series (high or low)
            is_high: True for resistance, False for support
            window: Rolling window for comparison

        Returns:
            List of significant price levels
        """
        pivots = []

        for i in range(window, len(series) - window):
            if is_high:
                # Local maximum
                if series.iloc[i] == series.iloc[i-window:i+window+1].max():
                    pivots.append(series.iloc[i])
            else:
                # Local minimum
                if series.iloc[i] == series.iloc[i-window:i+window+1].min():
                    pivots.append(series.iloc[i])

        # Cluster nearby levels (within 1.5%)
        clustered = self._cluster_levels(pivots)
        return sorted(clustered, reverse=is_high)[:3]  # Top 3 levels

    def _cluster_levels(self, levels: List[float], threshold: float = 0.015) -> List[float]:
        """Cluster nearby price levels."""
        if not levels:
            return []

        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]

        for level in levels[1:]:
            if (level - current_cluster[-1]) / current_cluster[-1] <= threshold:
                current_cluster.append(level)
            else:
                clusters.append(np.mean(current_cluster))
                current_cluster = [level]

        clusters.append(np.mean(current_cluster))
        return clusters

    def get_nearest_support(self) -> Tuple[float, float]:
        """
        Get nearest support level below current price.

        Returns:
            (support_level, distance_percent)
        """
        current_price = self.df['close'].iloc[-1]

        supports_below = [s for s in self.support_levels if s < current_price]
        if not supports_below:
            return None, None

        nearest = max(supports_below)  # Highest support below current price
        distance_pct = (current_price - nearest) / current_price * 100

        return nearest, distance_pct

    def get_nearest_resistance(self) -> Tuple[float, float]:
        """
        Get nearest resistance level above current price.

        Returns:
            (resistance_level, distance_percent)
        """
        current_price = self.df['close'].iloc[-1]

        resistances_above = [r for r in self.resistance_levels if r > current_price]
        if not resistances_above:
            return None, None

        nearest = min(resistances_above)  # Lowest resistance above current price
        distance_pct = (nearest - current_price) / current_price * 100

        return nearest, distance_pct

    def check_breakout(self) -> Tuple[int, str]:
        """
        Check for breakout patterns.

        Returns:
            (score, description)
        """
        current_price = self.df['close'].iloc[-1]
        prev_close = self.df['close'].iloc[-2]
        volume_ratio = self.df['volume'].iloc[-1] / self.df['volume'].rolling(20).mean().iloc[-1]

        # Check for resistance breakout
        for resistance in self.resistance_levels:
            if prev_close < resistance <= current_price:
                if volume_ratio > 1.5:
                    return 2, f"Breakout above {resistance:.2f} with volume"
                return 1, f"Breakout above {resistance:.2f}"

        # Check for support breakdown
        for support in self.support_levels:
            if prev_close > support >= current_price:
                if volume_ratio > 1.5:
                    return -2, f"Breakdown below {support:.2f} with volume"
                return -1, f"Breakdown below {support:.2f}"

        return 0, "No breakout detected"

    def check_trend(self, lookback: int = 20) -> Tuple[int, str]:
        """
        Analyze trend using higher highs/higher lows pattern.

        Returns:
            (score, description)
        """
        recent = self.df.tail(lookback)

        # Calculate swing highs and lows
        highs = recent['high'].rolling(5).max()
        lows = recent['low'].rolling(5).min()

        # Check pattern
        recent_highs = highs.dropna().tail(3).values
        recent_lows = lows.dropna().tail(3).values

        if len(recent_highs) < 3 or len(recent_lows) < 3:
            return 0, "Insufficient data for trend analysis"

        higher_highs = recent_highs[-1] > recent_highs[-2] > recent_highs[-3]
        higher_lows = recent_lows[-1] > recent_lows[-2] > recent_lows[-3]
        lower_highs = recent_highs[-1] < recent_highs[-2] < recent_highs[-3]
        lower_lows = recent_lows[-1] < recent_lows[-2] < recent_lows[-3]

        if higher_highs and higher_lows:
            return 2, "Strong uptrend (HH, HL)"
        elif higher_lows:
            return 1, "Uptrend (Higher lows)"
        elif lower_highs and lower_lows:
            return -2, "Strong downtrend (LH, LL)"
        elif lower_highs:
            return -1, "Downtrend (Lower highs)"
        else:
            return 0, "Sideways/Ranging"

    def get_price_position(self) -> Tuple[int, str]:
        """
        Analyze current price position relative to S/R levels.

        Returns:
            (score, description)
        """
        current_price = self.df['close'].iloc[-1]
        support, support_dist = self.get_nearest_support()
        resistance, resistance_dist = self.get_nearest_resistance()

        if support is None and resistance is None:
            return 0, "No clear S/R levels"

        # Near support (within 2%)
        if support and support_dist and support_dist <= 2:
            return 1, f"Near support at {support:.2f} ({support_dist:.1f}% above)"

        # Near resistance (within 2%)
        if resistance and resistance_dist and resistance_dist <= 2:
            return -1, f"Near resistance at {resistance:.2f} ({resistance_dist:.1f}% below)"

        # Good risk/reward if closer to support
        if support_dist and resistance_dist:
            rr_ratio = resistance_dist / support_dist if support_dist > 0 else 0
            if rr_ratio > 2:
                return 1, f"Good R:R ({rr_ratio:.1f}:1)"
            elif rr_ratio < 0.5:
                return -1, f"Poor R:R ({rr_ratio:.1f}:1)"

        return 0, "Neutral position"

    def get_all_signals(self) -> Dict:
        """Get all price action signals."""
        breakout_score, breakout_desc = self.check_breakout()
        trend_score, trend_desc = self.check_trend()
        position_score, position_desc = self.get_price_position()

        support, support_dist = self.get_nearest_support()
        resistance, resistance_dist = self.get_nearest_resistance()

        return {
            'breakout': {'score': breakout_score, 'description': breakout_desc},
            'trend': {'score': trend_score, 'description': trend_desc},
            'position': {'score': position_score, 'description': position_desc},
            'support': support,
            'support_distance': support_dist,
            'resistance': resistance,
            'resistance_distance': resistance_dist,
            'total_score': breakout_score + trend_score + position_score,
        }
