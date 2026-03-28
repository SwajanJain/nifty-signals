"""Central Pivot Range (CPR) Calculator.

CPR is the most popular swing/intraday level system among Indian traders.
  P  = (H + L + C) / 3
  BC = (H + L) / 2
  TC = (P - BC) + P  =  2*P - BC

Width tells you whether the day/week will be trending or rangebound:
  Narrow CPR (<0.5%)  → strong trending day expected
  Wide CPR   (>1.5%)  → rangebound day expected

Virgin CPR = a CPR level that was never tested in the session it was
calculated for.  These act as strong support/resistance when retested later.
"""

from dataclasses import dataclass
from typing import Dict, Optional
import pandas as pd
import numpy as np


@dataclass
class CPRLevels:
    """CPR level set with support/resistance."""
    pivot: float = 0.0
    top_cpr: float = 0.0       # TC
    bottom_cpr: float = 0.0    # BC
    r1: float = 0.0
    r2: float = 0.0
    r3: float = 0.0
    s1: float = 0.0
    s2: float = 0.0
    s3: float = 0.0
    width_pct: float = 0.0     # |TC - BC| / P * 100
    trend: str = 'NEUTRAL'     # BULLISH / BEARISH / NEUTRAL
    is_narrow: bool = False    # width < 0.5%
    is_virgin: bool = False    # untested in prior session


def _compute_cpr(high: float, low: float, close: float,
                 current_price: float = 0.0) -> CPRLevels:
    """Compute CPR and pivot levels from a single bar's HLC."""
    pivot = (high + low + close) / 3
    bc = (high + low) / 2
    tc = 2 * pivot - bc  # (P - BC) + P

    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)

    width_pct = abs(tc - bc) / pivot * 100 if pivot > 0 else 0

    if current_price > 0:
        if current_price > tc:
            trend = 'BULLISH'
        elif current_price < bc:
            trend = 'BEARISH'
        else:
            trend = 'NEUTRAL'
    else:
        trend = 'NEUTRAL'

    return CPRLevels(
        pivot=round(pivot, 2),
        top_cpr=round(tc, 2),
        bottom_cpr=round(bc, 2),
        r1=round(r1, 2), r2=round(r2, 2), r3=round(r3, 2),
        s1=round(s1, 2), s2=round(s2, 2), s3=round(s3, 2),
        width_pct=round(width_pct, 2),
        trend=trend,
        is_narrow=width_pct < 0.5,
    )


class CPRCalculator:
    """Calculate daily and weekly CPR from OHLCV data."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._valid = len(df) >= 6  # need a few days minimum

    def calculate_daily_cpr(self) -> CPRLevels:
        """CPR for today based on yesterday's HLC."""
        if not self._valid:
            return CPRLevels()

        prev = self.df.iloc[-2]
        current_price = self.df['close'].iloc[-1]
        return _compute_cpr(prev['high'], prev['low'], prev['close'], current_price)

    def calculate_weekly_cpr(self) -> CPRLevels:
        """CPR for the current week based on last week's HLC.

        Groups the DataFrame by ISO week and uses the prior complete week.
        """
        if not self._valid or len(self.df) < 10:
            return CPRLevels()

        df = self.df.copy()
        df['week'] = df.index.isocalendar().week if hasattr(df.index, 'isocalendar') else pd.to_datetime(df.index).isocalendar().week

        weeks = df['week'].unique()
        if len(weeks) < 2:
            return CPRLevels()

        # Get last complete week (not current partial week)
        last_complete_week = weeks[-2]
        week_data = df[df['week'] == last_complete_week]

        if week_data.empty:
            return CPRLevels()

        w_high = week_data['high'].max()
        w_low = week_data['low'].min()
        w_close = week_data['close'].iloc[-1]
        current_price = self.df['close'].iloc[-1]

        cpr = _compute_cpr(w_high, w_low, w_close, current_price)
        return cpr

    def _check_virgin(self, cpr: CPRLevels, session_df: pd.DataFrame) -> bool:
        """Check if the CPR range was tested (touched) during the session."""
        if session_df.empty:
            return True  # no data = treat as untested

        tc, bc = max(cpr.top_cpr, cpr.bottom_cpr), min(cpr.top_cpr, cpr.bottom_cpr)

        for _, row in session_df.iterrows():
            # If the bar's range overlaps the CPR band, it was tested
            if row['low'] <= tc and row['high'] >= bc:
                return False
        return True

    # ------------------------------------------------------------------
    # Standard pipeline interface
    # ------------------------------------------------------------------
    def get_all_signals(self) -> Dict:
        daily = self.calculate_daily_cpr()
        weekly = self.calculate_weekly_cpr()

        signals = []
        total_score = 0

        current = self.df['close'].iloc[-1] if self._valid else 0

        # Daily CPR analysis
        if daily.pivot > 0:
            if daily.is_narrow:
                signals.append(f"Narrow daily CPR ({daily.width_pct:.2f}%) — trending day expected")
                total_score += 1

            if daily.trend == 'BULLISH':
                signals.append(f"Price above daily CPR (TC ₹{daily.top_cpr})")
                total_score += 1
            elif daily.trend == 'BEARISH':
                signals.append(f"Price below daily CPR (BC ₹{daily.bottom_cpr})")
                total_score -= 1

        # Weekly CPR analysis
        if weekly.pivot > 0:
            if weekly.trend == 'BULLISH':
                signals.append(f"Price above weekly CPR (TC ₹{weekly.top_cpr})")
                total_score += 1
            elif weekly.trend == 'BEARISH':
                signals.append(f"Price below weekly CPR (BC ₹{weekly.bottom_cpr})")
                total_score -= 1

            if weekly.is_narrow:
                signals.append(f"Narrow weekly CPR ({weekly.width_pct:.2f}%) — strong trend week")

        # Near key levels (within 1%)
        if daily.pivot > 0 and current > 0:
            for level_name, level_val in [('R1', daily.r1), ('R2', daily.r2),
                                           ('S1', daily.s1), ('S2', daily.s2)]:
                proximity = abs(current - level_val) / current * 100
                if proximity < 1.0:
                    signals.append(f"Near {level_name} ₹{level_val}")

        return {
            'total_score': total_score,
            'signals': signals,
            'details': {
                'daily_cpr': {
                    'pivot': daily.pivot, 'tc': daily.top_cpr, 'bc': daily.bottom_cpr,
                    'r1': daily.r1, 'r2': daily.r2, 'r3': daily.r3,
                    's1': daily.s1, 's2': daily.s2, 's3': daily.s3,
                    'width_pct': daily.width_pct, 'trend': daily.trend,
                    'is_narrow': daily.is_narrow,
                },
                'weekly_cpr': {
                    'pivot': weekly.pivot, 'tc': weekly.top_cpr, 'bc': weekly.bottom_cpr,
                    'r1': weekly.r1, 'r2': weekly.r2,
                    's1': weekly.s1, 's2': weekly.s2,
                    'width_pct': weekly.width_pct, 'trend': weekly.trend,
                    'is_narrow': weekly.is_narrow,
                },
            },
        }
