"""NR4 / NR7 Narrow Range Scanner.

Narrow range days predict imminent breakouts:
  NR4 — today's range is the narrowest of the last 4 days
  NR7 — today's range is the narrowest of the last 7 days
  Inside Bar (IB) — today's high < yesterday's high AND today's low > yesterday's low

NR7 + Inside Bar is the strongest pre-breakout signal.
Entry is a break of today's high (long) or low (short).
"""

from typing import Dict
import pandas as pd


class NarrowRangeDetector:
    """Detect NR4, NR7, and inside-bar patterns."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._valid = len(df) >= 8  # need at least 7 prior bars + today

    def detect(self) -> Dict:
        """Detect narrow range patterns on the latest bar."""
        if not self._valid:
            return self._empty()

        ranges = self.df['high'] - self.df['low']
        latest_range = ranges.iloc[-1]

        # NR4: today is narrowest of last 4
        nr4 = bool(latest_range <= ranges.iloc[-4:].min())

        # NR7: today is narrowest of last 7
        nr7 = bool(latest_range <= ranges.iloc[-7:].min())

        # Inside bar: today contained within yesterday's range
        inside_bar = bool(
            self.df['high'].iloc[-1] < self.df['high'].iloc[-2] and
            self.df['low'].iloc[-1] > self.df['low'].iloc[-2]
        )

        nr7_ib = nr7 and inside_bar  # strongest combo

        close = self.df['close'].iloc[-1]
        range_pct = (latest_range / close * 100) if close > 0 else 0

        # Classify signal strength
        if nr7_ib:
            signal = 'STRONG'
        elif nr7:
            signal = 'MODERATE'
        elif nr4 and inside_bar:
            signal = 'MODERATE'
        elif nr4:
            signal = 'MILD'
        else:
            signal = 'NONE'

        return {
            'nr4': nr4,
            'nr7': nr7,
            'inside_bar': inside_bar,
            'nr7_ib': nr7_ib,
            'range_pct': round(range_pct, 2),
            'signal': signal,
            'entry_long': round(self.df['high'].iloc[-1], 2),
            'entry_short': round(self.df['low'].iloc[-1], 2),
        }

    def _empty(self) -> Dict:
        return {
            'nr4': False, 'nr7': False, 'inside_bar': False,
            'nr7_ib': False, 'range_pct': 0, 'signal': 'NONE',
            'entry_long': 0, 'entry_short': 0,
        }

    # ------------------------------------------------------------------
    # Standard pipeline interface
    # ------------------------------------------------------------------
    def get_all_signals(self) -> Dict:
        result = self.detect()

        signals = []
        total_score = 0

        if result['nr7_ib']:
            signals.append(f"NR7 + Inside Bar (range {result['range_pct']:.1f}%) "
                           f"— break above ₹{result['entry_long']}")
            total_score += 2
        elif result['nr7']:
            signals.append(f"NR7 (range {result['range_pct']:.1f}%) "
                           f"— break above ₹{result['entry_long']}")
            total_score += 1
        elif result['nr4'] and result['inside_bar']:
            signals.append(f"NR4 + Inside Bar (range {result['range_pct']:.1f}%)")
            total_score += 1
        elif result['nr4']:
            signals.append(f"NR4 (range {result['range_pct']:.1f}%)")
            # NR4 alone is mild — no score bonus

        return {
            'total_score': total_score,
            'signals': signals,
            'details': result,
        }
