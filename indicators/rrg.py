"""Relative Rotation Graph (RRG) — Sector rotation quadrant analysis.

Computes RS-Ratio and RS-Momentum to classify stocks/sectors into four
rotation quadrants: Leading, Weakening, Lagging, Improving.

Reference: Julius de Kempenaer's RRG methodology.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import pandas as pd
import numpy as np


@dataclass
class RRGPoint:
    """Single point on the Relative Rotation Graph."""

    symbol: str
    rs_ratio: float
    rs_momentum: float
    quadrant: str  # "Leading", "Weakening", "Lagging", "Improving"
    trail: List[Tuple[float, float]] = field(default_factory=list)
    # last 4 weeks of (rs_ratio, rs_momentum)


def _determine_quadrant(rs_ratio: float, rs_momentum: float) -> str:
    """Map RS-Ratio and RS-Momentum to a rotation quadrant."""
    if rs_ratio >= 100 and rs_momentum >= 100:
        return "Leading"
    elif rs_ratio >= 100 and rs_momentum < 100:
        return "Weakening"
    elif rs_ratio < 100 and rs_momentum < 100:
        return "Lagging"
    else:  # rs_ratio < 100 and rs_momentum >= 100
        return "Improving"


class RRGCalculator:
    """Compute Relative Rotation Graph coordinates for stocks vs a benchmark.

    Algorithm
    ---------
    1. RS  = stock_close / benchmark_close  (relative-strength line)
    2. RS-Ratio    = RS / SMA(RS, ratio_period) * 100   (normalised around 100)
    3. RS-Momentum = RS-Ratio / SMA(RS-Ratio, momentum_period) * 100

    The default periods (10) match the standard JdK methodology for weekly
    data.  For daily data you may want longer windows (e.g. 50).
    """

    def __init__(
        self,
        ratio_period: int = 10,
        momentum_period: int = 10,
        trail_length: int = 4,
    ):
        self.ratio_period = ratio_period
        self.momentum_period = momentum_period
        self.trail_length = trail_length

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def _compute_rs_series(
        self,
        stock_df: pd.DataFrame,
        benchmark_df: pd.DataFrame,
        lookback: int,
    ) -> Tuple[pd.Series, pd.Series]:
        """Return aligned RS-Ratio and RS-Momentum series.

        Both stock_df and benchmark_df must have a 'close' column with a
        DatetimeIndex.
        """
        # Align on common dates
        common_idx = stock_df.index.intersection(benchmark_df.index)
        if len(common_idx) < lookback:
            raise ValueError(
                f"Not enough overlapping data ({len(common_idx)} bars, "
                f"need {lookback})."
            )

        stock_close = stock_df.loc[common_idx, "close"].tail(lookback)
        bench_close = benchmark_df.loc[common_idx, "close"].tail(lookback)

        # Step 1: raw relative strength
        rs = stock_close / bench_close

        # Step 2: RS-Ratio = RS / SMA(RS, ratio_period) * 100
        rs_ratio = rs / rs.rolling(window=self.ratio_period).mean() * 100

        # Step 3: RS-Momentum = RS-Ratio / SMA(RS-Ratio, momentum_period) * 100
        rs_momentum = (
            rs_ratio / rs_ratio.rolling(window=self.momentum_period).mean() * 100
        )

        return rs_ratio, rs_momentum

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(
        self,
        stock_df: pd.DataFrame,
        benchmark_df: pd.DataFrame,
        symbol: str,
        lookback: int = 52,
    ) -> RRGPoint:
        """Compute RRG coordinates for a single stock.

        Parameters
        ----------
        stock_df : DataFrame with 'close' column (DatetimeIndex).
        benchmark_df : DataFrame with 'close' column (DatetimeIndex).
        symbol : Ticker label.
        lookback : Number of bars to use for computation.

        Returns
        -------
        RRGPoint with latest RS-Ratio, RS-Momentum, quadrant and trail.
        """
        min_bars = lookback
        if len(stock_df) < min_bars or len(benchmark_df) < min_bars:
            # Return a neutral point when data is insufficient
            return RRGPoint(
                symbol=symbol,
                rs_ratio=100.0,
                rs_momentum=100.0,
                quadrant="Lagging",
                trail=[],
            )

        try:
            rs_ratio, rs_momentum = self._compute_rs_series(
                stock_df, benchmark_df, lookback
            )
        except ValueError:
            return RRGPoint(
                symbol=symbol,
                rs_ratio=100.0,
                rs_momentum=100.0,
                quadrant="Lagging",
                trail=[],
            )

        # Drop NaN values produced by rolling windows
        valid = rs_ratio.dropna().index.intersection(rs_momentum.dropna().index)
        if len(valid) == 0:
            return RRGPoint(
                symbol=symbol,
                rs_ratio=100.0,
                rs_momentum=100.0,
                quadrant="Lagging",
                trail=[],
            )

        rs_ratio = rs_ratio.loc[valid]
        rs_momentum = rs_momentum.loc[valid]

        latest_ratio = float(rs_ratio.iloc[-1])
        latest_momentum = float(rs_momentum.iloc[-1])

        # Build trail (last trail_length weekly-equivalent points)
        # For daily data we sample every 5 bars; for weekly, every bar
        step = max(1, len(rs_ratio) // (self.trail_length * 5)) * 5
        trail_indices = list(range(len(rs_ratio) - 1, -1, -step))[
            : self.trail_length + 1
        ]
        trail_indices.reverse()
        trail: List[Tuple[float, float]] = [
            (float(rs_ratio.iloc[i]), float(rs_momentum.iloc[i]))
            for i in trail_indices
            if i < len(rs_ratio)
        ]

        quadrant = _determine_quadrant(latest_ratio, latest_momentum)

        return RRGPoint(
            symbol=symbol,
            rs_ratio=round(latest_ratio, 2),
            rs_momentum=round(latest_momentum, 2),
            quadrant=quadrant,
            trail=trail,
        )

    def calculate_universe(
        self,
        stock_dfs: Dict[str, pd.DataFrame],
        benchmark_df: pd.DataFrame,
        lookback: int = 52,
    ) -> List[RRGPoint]:
        """Compute RRG coordinates for a universe of stocks.

        Parameters
        ----------
        stock_dfs : {symbol: DataFrame} with 'close' columns.
        benchmark_df : Benchmark DataFrame with 'close' column.
        lookback : Number of bars per stock.

        Returns
        -------
        List of RRGPoint sorted by quadrant priority
        (Leading -> Improving -> Weakening -> Lagging).
        """
        results: List[RRGPoint] = []
        for symbol, df in stock_dfs.items():
            point = self.calculate(df, benchmark_df, symbol, lookback)
            results.append(point)

        # Sort: Leading first, then Improving, Weakening, Lagging
        quadrant_order = {
            "Leading": 0,
            "Improving": 1,
            "Weakening": 2,
            "Lagging": 3,
        }
        results.sort(key=lambda p: (quadrant_order.get(p.quadrant, 4), -p.rs_ratio))
        return results
