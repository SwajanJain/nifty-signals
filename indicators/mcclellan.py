"""McClellan Oscillator & Summation Index.

Smoothed breadth momentum indicators:
  Oscillator = EMA19(A-D) - EMA39(A-D)
  Summation Index = cumulative sum of Oscillator

Positive oscillator = bullish breadth momentum.
Zero-line crosses = breadth thrust signals.
"""

from typing import Dict
import pandas as pd
import numpy as np


class McClellanCalculator:
    """Compute McClellan Oscillator and Summation Index from advance/decline data."""

    def __init__(self, advances: pd.Series, declines: pd.Series):
        """
        Args:
            advances: Time series of daily advancing issues
            declines: Time series of daily declining issues
        """
        self.ad_diff = advances - declines
        self._valid = len(self.ad_diff) >= 39

    def oscillator(self) -> pd.Series:
        """McClellan Oscillator = EMA19(A-D) - EMA39(A-D)."""
        if not self._valid:
            return pd.Series(dtype=float)
        ema19 = self.ad_diff.ewm(span=19, adjust=False).mean()
        ema39 = self.ad_diff.ewm(span=39, adjust=False).mean()
        return ema19 - ema39

    def summation_index(self) -> pd.Series:
        """Cumulative sum of the oscillator."""
        osc = self.oscillator()
        return osc.cumsum()

    def get_all_signals(self) -> Dict:
        """Return signals in the standard indicator format."""
        if not self._valid:
            return {'total_score': 0, 'signals': [], 'details': {}}

        osc = self.oscillator()
        if len(osc) < 2:
            return {'total_score': 0, 'signals': [], 'details': {}}

        latest = osc.iloc[-1]
        prev = osc.iloc[-2]
        summ = self.summation_index().iloc[-1]

        signals = []
        total_score = 0

        # Zero-line cross
        if prev <= 0 < latest:
            signals.append(f"McClellan crossed above zero ({latest:.0f})")
            total_score += 2
        elif prev >= 0 > latest:
            signals.append(f"McClellan crossed below zero ({latest:.0f})")
            total_score -= 2
        elif latest > 0:
            signals.append(f"McClellan positive ({latest:.0f})")
            total_score += 1
        elif latest < 0:
            signals.append(f"McClellan negative ({latest:.0f})")
            total_score -= 1

        # Breadth thrust: oscillator > +100 or < -100
        if latest > 100:
            signals.append("Breadth thrust (strongly bullish)")
            total_score += 1
        elif latest < -100:
            signals.append("Breadth washout (potential reversal)")

        return {
            'total_score': total_score,
            'signals': signals,
            'details': {
                'oscillator': round(float(latest), 1),
                'prev_oscillator': round(float(prev), 1),
                'summation_index': round(float(summ), 1),
                'zero_cross_up': bool(prev <= 0 < latest),
                'zero_cross_down': bool(prev >= 0 > latest),
            },
        }
