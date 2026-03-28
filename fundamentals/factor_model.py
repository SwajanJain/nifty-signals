"""Multi-Factor Scoring Model for Long-Term Investing.

Factors (each scored 0-100 as percentile within sector):
  1. Momentum — 12-1 month return (skip last month to avoid reversal)
  2. Value    — inverse PE, PB, earnings yield (lower = better)
  3. Quality  — ROE stability, ROCE consistency, low debt
  4. Growth   — Revenue/EPS CAGR, earnings acceleration
  5. Low Vol  — 1Y std dev, max drawdown (lower = better)

Scoring methodology (Jegadeesh & Titman / Automated-Fundamental-Analysis):
  - For each factor, compute sector-wide distribution
  - Remove outliers (>3 std dev)
  - Score each stock as percentile rank within sector
  - Inverse for "lower is better" metrics
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from fundamentals.models import FundamentalProfile


# ---------------------------------------------------------------------------
# Config (overridable from config.py)
# ---------------------------------------------------------------------------
try:
    from config import FACTOR_MODEL_CONFIG
except ImportError:
    FACTOR_MODEL_CONFIG = {}

_CFG = {
    'weights': {
        'momentum': 0.25,
        'value': 0.20,
        'quality': 0.25,
        'growth': 0.20,
        'low_vol': 0.10,
    },
}
_CFG.update(FACTOR_MODEL_CONFIG)


@dataclass
class FactorScores:
    """Factor scores for a single stock."""
    symbol: str = ""
    sector: str = ""
    momentum_score: float = 50.0     # 0-100 percentile
    value_score: float = 50.0
    quality_score: float = 50.0
    growth_score: float = 50.0
    low_vol_score: float = 50.0
    composite_score: float = 50.0    # weighted blend
    sector_rank: int = 0
    universe_rank: int = 0
    percentile: float = 50.0
    factor_details: Dict = field(default_factory=dict)


class FactorModel:
    """Multi-factor scoring system for long-term investing."""

    WEIGHTS = _CFG['weights']

    # ------------------------------------------------------------------
    # Sector-relative percentile scoring
    # ------------------------------------------------------------------
    @staticmethod
    def _percentile_rank(value: float, values: List[float],
                         lower_is_better: bool = False) -> float:
        """Score a value relative to a distribution (0-100 percentile).

        Outliers (>3σ) are removed before ranking.
        """
        if not values:
            return 50.0

        arr = np.array([v for v in values if v is not None and not np.isnan(v)])
        if len(arr) < 2:
            return 50.0

        # Remove outliers
        mean = np.mean(arr)
        std = np.std(arr)
        if std > 0:
            filtered = arr[np.abs(arr - mean) < 3 * std]
            if len(filtered) < 2:
                filtered = arr
        else:
            filtered = arr

        rank = np.sum(filtered <= value) / len(filtered) * 100
        return round(100 - rank if lower_is_better else rank, 1)

    # ------------------------------------------------------------------
    # Individual factor computations
    # ------------------------------------------------------------------
    def score_momentum_raw(self, df: pd.DataFrame) -> Dict:
        """Momentum factor raw values.

        12-1 month return (skip last month to avoid short-term reversal).
        Also includes 6M and 3M returns.
        """
        if df is None or len(df) < 252:
            return {'momentum_12_1': 0, 'ret_6m': 0, 'ret_3m': 0}

        close = df['close']
        ret_12m = (close.iloc[-1] / close.iloc[-252] - 1) * 100 if len(close) >= 252 else 0
        ret_1m = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else 0
        ret_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100 if len(close) >= 126 else 0
        ret_3m = (close.iloc[-1] / close.iloc[-63] - 1) * 100 if len(close) >= 63 else 0

        # 12-1 month: subtract last month to avoid reversal
        momentum_12_1 = ret_12m - ret_1m

        return {
            'momentum_12_1': round(momentum_12_1, 2),
            'ret_6m': round(ret_6m, 2),
            'ret_3m': round(ret_3m, 2),
        }

    def score_value_raw(self, profile: FundamentalProfile) -> Dict:
        """Value factor raw values. Lower PE/PB = better value."""
        return {
            'pe': profile.pe_ratio,
            'pb': profile.pb_ratio,
            'earnings_yield': round(100 / profile.pe_ratio, 2) if profile.pe_ratio > 0 else 0,
        }

    def score_quality_raw(self, profile: FundamentalProfile) -> Dict:
        """Quality factor raw values."""
        return {
            'roe': profile.roe,
            'roce': profile.roce,
            'debt_to_equity': profile.debt_to_equity,
            'no_loss_5y': profile.no_loss_years_5,
            'is_debt_free': getattr(profile, 'is_debt_free', False),
        }

    def score_growth_raw(self, profile: FundamentalProfile) -> Dict:
        """Growth factor raw values."""
        return {
            'revenue_growth_3y': profile.revenue_growth_3y,
            'profit_growth_3y': profile.profit_growth_3y,
            'eps_growth_3y': profile.eps_growth_3y,
        }

    def score_low_vol_raw(self, df: pd.DataFrame) -> Dict:
        """Low volatility factor raw values."""
        if df is None or len(df) < 60:
            return {'std_1y': 0, 'max_drawdown': 0}

        returns = df['close'].pct_change().dropna()

        std_1y = returns.tail(252).std() * np.sqrt(252) * 100 if len(returns) >= 252 else 0

        # Max drawdown
        cummax = df['close'].cummax()
        drawdown = (df['close'] - cummax) / cummax * 100
        max_dd = drawdown.min()

        return {
            'std_1y': round(std_1y, 2),
            'max_drawdown': round(max_dd, 2),
        }

    # ------------------------------------------------------------------
    # Universe scoring
    # ------------------------------------------------------------------
    def score_universe(self,
                       stock_data: Dict[str, Tuple[pd.DataFrame, FundamentalProfile]],
                       ) -> List[FactorScores]:
        """Score all stocks with sector-relative percentile ranking.

        Args:
            stock_data: {symbol: (price_df, FundamentalProfile)}

        Returns:
            List of FactorScores sorted by composite descending.
        """
        # Compute raw factor values for every stock
        raw: Dict[str, Dict] = {}
        for sym, (df, profile) in stock_data.items():
            raw[sym] = {
                'sector': profile.sector or 'Unknown',
                'momentum': self.score_momentum_raw(df),
                'value': self.score_value_raw(profile),
                'quality': self.score_quality_raw(profile),
                'growth': self.score_growth_raw(profile),
                'low_vol': self.score_low_vol_raw(df),
            }

        # Group by sector
        sectors: Dict[str, List[str]] = {}
        for sym, data in raw.items():
            sector = data['sector']
            sectors.setdefault(sector, []).append(sym)

        # Percentile-rank within sector
        results: List[FactorScores] = []

        for sector, syms in sectors.items():
            # Collect sector-wide distributions
            mom_vals = [raw[s]['momentum']['momentum_12_1'] for s in syms]
            pe_vals = [raw[s]['value']['pe'] for s in syms if raw[s]['value']['pe'] > 0]
            pb_vals = [raw[s]['value']['pb'] for s in syms if raw[s]['value']['pb'] > 0]
            roe_vals = [raw[s]['quality']['roe'] for s in syms]
            rev_g_vals = [raw[s]['growth']['revenue_growth_3y'] for s in syms]
            std_vals = [raw[s]['low_vol']['std_1y'] for s in syms]

            for sym in syms:
                r = raw[sym]

                mom_score = self._percentile_rank(r['momentum']['momentum_12_1'], mom_vals)
                val_pe = self._percentile_rank(r['value']['pe'], pe_vals, lower_is_better=True) if r['value']['pe'] > 0 else 50
                val_pb = self._percentile_rank(r['value']['pb'], pb_vals, lower_is_better=True) if r['value']['pb'] > 0 else 50
                val_score = (val_pe + val_pb) / 2

                qual_roe = self._percentile_rank(r['quality']['roe'], roe_vals)
                qual_debt = 80 if r['quality']['is_debt_free'] else (60 if r['quality']['debt_to_equity'] < 0.5 else 40)
                qual_score = qual_roe * 0.7 + qual_debt * 0.3

                growth_score = self._percentile_rank(r['growth']['revenue_growth_3y'], rev_g_vals)
                low_vol_score = self._percentile_rank(r['low_vol']['std_1y'], std_vals, lower_is_better=True)

                # Weighted composite
                composite = (
                    self.WEIGHTS['momentum'] * mom_score +
                    self.WEIGHTS['value'] * val_score +
                    self.WEIGHTS['quality'] * qual_score +
                    self.WEIGHTS['growth'] * growth_score +
                    self.WEIGHTS['low_vol'] * low_vol_score
                )

                results.append(FactorScores(
                    symbol=sym,
                    sector=sector,
                    momentum_score=round(mom_score, 1),
                    value_score=round(val_score, 1),
                    quality_score=round(qual_score, 1),
                    growth_score=round(growth_score, 1),
                    low_vol_score=round(low_vol_score, 1),
                    composite_score=round(composite, 1),
                    factor_details=r,
                ))

        # Sort by composite, assign universe rank
        results.sort(key=lambda x: x.composite_score, reverse=True)
        for i, fs in enumerate(results):
            fs.universe_rank = i + 1
            fs.percentile = round((1 - i / max(len(results), 1)) * 100, 1)

        # Assign sector rank
        sector_counts: Dict[str, int] = {}
        for fs in results:
            sector_counts.setdefault(fs.sector, 0)
            sector_counts[fs.sector] += 1
            fs.sector_rank = sector_counts[fs.sector]

        return results
