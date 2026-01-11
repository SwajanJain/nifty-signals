"""ADX and trend strength indicators."""

from typing import Dict, Tuple
import pandas as pd
import numpy as np
import pandas_ta as ta


class TrendStrength:
    """Analyze trend strength using ADX and related indicators."""

    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLCV DataFrame.

        Args:
            df: DataFrame with columns: open, high, low, close, volume
        """
        self.df = df.copy()
        self._calculate_adx()

    def _calculate_adx(self, period: int = 14):
        """Calculate ADX, +DI, and -DI."""
        adx_data = ta.adx(self.df['high'], self.df['low'], self.df['close'], length=period)

        # Find column names dynamically
        adx_cols = adx_data.columns.tolist()
        adx_col = [c for c in adx_cols if c.startswith('ADX_')][0]
        dmp_col = [c for c in adx_cols if c.startswith('DMP_')][0]
        dmn_col = [c for c in adx_cols if c.startswith('DMN_')][0]

        self.df['adx'] = adx_data[adx_col]
        self.df['plus_di'] = adx_data[dmp_col]
        self.df['minus_di'] = adx_data[dmn_col]

    def get_trend_strength(self) -> Tuple[str, float]:
        """
        Get current trend strength classification.

        Returns:
            (strength_description, adx_value)
        """
        adx = self.df['adx'].iloc[-1]

        if pd.isna(adx):
            return "Unknown", 0

        if adx < 20:
            return "Weak/No Trend", adx
        elif adx < 25:
            return "Emerging Trend", adx
        elif adx < 50:
            return "Strong Trend", adx
        elif adx < 75:
            return "Very Strong Trend", adx
        else:
            return "Extremely Strong Trend", adx

    def get_trend_direction(self) -> Tuple[str, int]:
        """
        Get trend direction from DI crossover.

        Returns:
            (direction, score)
        """
        plus_di = self.df['plus_di'].iloc[-1]
        minus_di = self.df['minus_di'].iloc[-1]
        adx = self.df['adx'].iloc[-1]

        if pd.isna(plus_di) or pd.isna(minus_di):
            return "Unknown", 0

        # Check for DI crossover
        if len(self.df) > 1:
            prev_plus = self.df['plus_di'].iloc[-2]
            prev_minus = self.df['minus_di'].iloc[-2]

            # Bullish crossover
            if prev_plus < prev_minus and plus_di > minus_di:
                return "Bullish Crossover (+DI crossed above -DI)", 2

            # Bearish crossover
            if prev_plus > prev_minus and plus_di < minus_di:
                return "Bearish Crossover (-DI crossed above +DI)", -2

        # Current position
        if plus_di > minus_di:
            if adx > 25:
                return "Bullish Trend (Strong)", 1
            return "Bullish Bias (Weak)", 0
        else:
            if adx > 25:
                return "Bearish Trend (Strong)", -1
            return "Bearish Bias (Weak)", 0

    def check_trend_exhaustion(self) -> Tuple[bool, str, int]:
        """
        Check for trend exhaustion signals.

        Returns:
            (detected, description, score)
        """
        if len(self.df) < 5:
            return False, "", 0

        adx = self.df['adx'].iloc[-1]
        adx_prev = self.df['adx'].iloc[-5:-1].mean()

        if pd.isna(adx) or pd.isna(adx_prev):
            return False, "", 0

        plus_di = self.df['plus_di'].iloc[-1]
        minus_di = self.df['minus_di'].iloc[-1]

        # ADX falling from high levels (trend exhaustion)
        if adx > 40 and adx < adx_prev:
            if plus_di > minus_di:
                return True, "Uptrend exhaustion (ADX declining from high)", -1
            else:
                return True, "Downtrend exhaustion (ADX declining from high)", 1

        # ADX rising from low levels (new trend emerging)
        if adx < 25 and adx > adx_prev * 1.1:
            if plus_di > minus_di:
                return True, "New uptrend emerging (ADX rising)", 1
            else:
                return True, "New downtrend emerging (ADX rising)", -1

        return False, "", 0

    def check_di_extreme(self) -> Tuple[bool, str, int]:
        """
        Check for extreme DI readings.

        Returns:
            (detected, description, score)
        """
        plus_di = self.df['plus_di'].iloc[-1]
        minus_di = self.df['minus_di'].iloc[-1]

        if pd.isna(plus_di) or pd.isna(minus_di):
            return False, "", 0

        # Calculate historical DI percentiles
        plus_percentile = (self.df['plus_di'] < plus_di).mean() * 100
        minus_percentile = (self.df['minus_di'] < minus_di).mean() * 100

        # Extreme bullish (+DI very high)
        if plus_percentile > 90:
            return True, "Extreme bullish momentum (+DI at 90th percentile)", 1

        # Extreme bearish (-DI very high)
        if minus_percentile > 90:
            return True, "Extreme bearish momentum (-DI at 90th percentile)", -1

        return False, "", 0

    def get_all_signals(self) -> Dict:
        """Get all ADX-based signals."""
        patterns = []
        total_score = 0

        # Trend direction
        direction, score = self.get_trend_direction()
        if score != 0:
            patterns.append({'pattern': direction, 'score': score})
            total_score += score

        # Trend exhaustion
        detected, desc, score = self.check_trend_exhaustion()
        if detected:
            patterns.append({'pattern': desc, 'score': score})
            total_score += score

        # DI extremes
        detected, desc, score = self.check_di_extreme()
        if detected:
            patterns.append({'pattern': desc, 'score': score})
            total_score += score

        # Get values
        strength, adx_value = self.get_trend_strength()
        plus_di = self.df['plus_di'].iloc[-1]
        minus_di = self.df['minus_di'].iloc[-1]

        return {
            'patterns': patterns,
            'total_score': total_score,
            'adx': adx_value,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'trend_strength': strength,
            'description': f"ADX: {adx_value:.1f} ({strength})" if not pd.isna(adx_value) else "ADX: N/A"
        }
