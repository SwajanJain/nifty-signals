"""O'Neil RS Rating — Weighted relative price-performance rating (1-99).

Implements William O'Neil's Relative Strength rating as used in IBD:

  RS Rating = 0.40 * Q1_return + 0.20 * Q2_return + 0.20 * Q3_return + 0.20 * Q4_return

where Q1 is the most recent quarter and Q4 the oldest.  The raw weighted
return is then percentile-ranked against a universe to produce a 1-99 score
(99 = strongest relative performer).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class RSRatingResult:
    """O'Neil RS Rating for a single stock."""

    symbol: str
    rs_rating: int  # 1-99 (99 = strongest)
    raw_score: float  # weighted return (%)
    quarterly_returns: List[float] = field(default_factory=list)
    # [Q1, Q2, Q3, Q4] % returns — most recent first
    interpretation: str = ""
    # "LEADER" >= 80, "ABOVE_AVG" >= 60, "AVERAGE" >= 40, "LAGGARD" < 40


def _interpret(rs_rating: int) -> str:
    """Human-readable interpretation of the RS rating."""
    if rs_rating >= 80:
        return "LEADER"
    elif rs_rating >= 60:
        return "ABOVE_AVG"
    elif rs_rating >= 40:
        return "AVERAGE"
    else:
        return "LAGGARD"


# Quarter weights (Q1 = most recent → heaviest)
_Q_WEIGHTS = [0.40, 0.20, 0.20, 0.20]

# Trading days per quarter (approximate)
_TRADING_DAYS_PER_QUARTER = 63


class RSRating:
    """Compute O'Neil-style RS Rating for individual stocks or a universe.

    Requires roughly 12 months (~252 trading days) of daily close data for
    a full four-quarter calculation.  If fewer data points are available the
    calculation uses as many complete quarters as possible.
    """

    def _quarterly_returns(self, close: pd.Series) -> List[float]:
        """Split the close series into 4 quarters and compute % returns.

        Returns a list [Q1, Q2, Q3, Q4] where Q1 is the most recent quarter.
        If the series is shorter than 4 quarters the missing quarters are
        filled with 0.0.
        """
        n = len(close)
        q_len = _TRADING_DAYS_PER_QUARTER
        returns: List[float] = []

        for i in range(4):
            end_idx = n - i * q_len
            start_idx = end_idx - q_len
            if start_idx < 0 or end_idx <= 0:
                returns.append(0.0)
                continue
            start_price = close.iloc[start_idx]
            end_price = close.iloc[end_idx - 1]
            if start_price > 0:
                pct = (end_price - start_price) / start_price * 100
            else:
                pct = 0.0
            returns.append(round(pct, 2))

        return returns  # [Q1, Q2, Q3, Q4]

    def _weighted_score(self, quarterly_returns: List[float]) -> float:
        """Compute the O'Neil weighted return from quarterly returns."""
        score = 0.0
        for ret, weight in zip(quarterly_returns, _Q_WEIGHTS):
            score += ret * weight
        return round(score, 4)

    def _estimate_percentile(self, raw_score: float) -> int:
        """Estimate a percentile when no universe is available.

        Uses a heuristic mapping of absolute weighted returns to a 1-99 scale.
        This is a rough approximation; the true RS rating requires ranking
        against a broad universe (see ``rank_universe``).

        Mapping (approximate for Indian mid/large caps):
          raw_score >= 60  →  95
          raw_score >= 40  →  85
          raw_score >= 25  →  75
          raw_score >= 15  →  65
          raw_score >= 5   →  55
          raw_score >= 0   →  45
          raw_score >= -10 →  35
          raw_score >= -20 →  25
          raw_score >= -35 →  15
          raw_score <  -35 →  5
        """
        thresholds = [
            (60, 95),
            (40, 85),
            (25, 75),
            (15, 65),
            (5, 55),
            (0, 45),
            (-10, 35),
            (-20, 25),
            (-35, 15),
        ]
        for threshold, rating in thresholds:
            if raw_score >= threshold:
                return rating
        return 5

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(
        self,
        df: pd.DataFrame,
        symbol: str,
    ) -> RSRatingResult:
        """Compute RS Rating for a single stock (standalone, no universe).

        Parameters
        ----------
        df : DataFrame with a 'close' column and at least ~63 rows
             (one quarter).  Ideally ~252 rows (one year).
        symbol : Ticker label.

        Returns
        -------
        RSRatingResult with an estimated rs_rating (approximate without a
        full universe for percentile ranking).
        """
        if df is None or len(df) < _TRADING_DAYS_PER_QUARTER:
            return RSRatingResult(
                symbol=symbol,
                rs_rating=50,
                raw_score=0.0,
                quarterly_returns=[],
                interpretation="AVERAGE",
            )

        close = df["close"]
        q_returns = self._quarterly_returns(close)
        raw = self._weighted_score(q_returns)
        estimated_rating = self._estimate_percentile(raw)
        interpretation = _interpret(estimated_rating)

        return RSRatingResult(
            symbol=symbol,
            rs_rating=estimated_rating,
            raw_score=raw,
            quarterly_returns=q_returns,
            interpretation=interpretation,
        )

    def rank_universe(
        self,
        dfs: Dict[str, pd.DataFrame],
    ) -> List[RSRatingResult]:
        """Compute RS Ratings for a universe with true percentile ranking.

        Parameters
        ----------
        dfs : {symbol: DataFrame} — each DataFrame must have a 'close'
              column with ~252 rows of daily data.

        Returns
        -------
        List of RSRatingResult sorted by rs_rating descending (leaders first).
        """
        # Phase 1: compute raw scores
        raw_results: List[dict] = []
        for symbol, df in dfs.items():
            if df is None or len(df) < _TRADING_DAYS_PER_QUARTER:
                continue
            close = df["close"]
            q_returns = self._quarterly_returns(close)
            raw = self._weighted_score(q_returns)
            raw_results.append({
                "symbol": symbol,
                "raw_score": raw,
                "quarterly_returns": q_returns,
            })

        if not raw_results:
            return []

        # Phase 2: percentile rank
        scores = np.array([r["raw_score"] for r in raw_results])

        results: List[RSRatingResult] = []
        for entry in raw_results:
            # Percentile: fraction of universe this stock beats
            percentile = (scores < entry["raw_score"]).sum() / len(scores) * 100
            # Clamp to 1-99
            rs_rating = max(1, min(99, int(round(percentile))))
            interpretation = _interpret(rs_rating)

            results.append(RSRatingResult(
                symbol=entry["symbol"],
                rs_rating=rs_rating,
                raw_score=entry["raw_score"],
                quarterly_returns=entry["quarterly_returns"],
                interpretation=interpretation,
            ))

        results.sort(key=lambda r: r.rs_rating, reverse=True)
        return results
