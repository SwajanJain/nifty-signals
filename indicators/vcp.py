"""Volatility Contraction Pattern (VCP) Scanner — Minervini.

Detects stocks forming progressively tighter bases before breakout.
The VCP is characterized by:
- Stock in Stage 2 uptrend (price > 50 EMA > 200 EMA)
- 2-6 contractions where each pullback is smaller than the previous
- Volume declining during base formation
- Price near pivot (breakout) level
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import pandas_ta as ta

from config import EMA_MEDIUM, EMA_LONG


# ---------------------------------------------------------------------------
# Configuration defaults (overridable from config.py VCP_CONFIG)
# ---------------------------------------------------------------------------
try:
    from config import VCP_CONFIG
except ImportError:
    VCP_CONFIG = {}

_CFG = {
    'min_contractions': 2,
    'max_base_days': 65,
    'first_pullback_min_pct': 10,
    'first_pullback_max_pct': 40,
    'contraction_ratio': 0.65,       # each pullback < 65% of previous
    'volume_decline_min': 0.25,      # volume must drop 25%+ across base
    'pivot_proximity_pct': 5.0,      # within 5% of pivot to score "ready"
    'swing_window': 5,               # bars on each side for pivot detection
}
_CFG.update(VCP_CONFIG)


@dataclass
class VCPPattern:
    """Describes a detected VCP pattern."""
    symbol: str = ""
    contractions: int = 0                # Number of contractions detected
    pullbacks: List[float] = field(default_factory=list)   # Pullback %s
    volume_declining: bool = False       # Volume decreasing across base
    pivot_price: float = 0.0             # Breakout level (highest high in base)
    current_contraction_pct: float = 0.0 # Latest contraction depth
    stage_2: bool = False                # In Stage 2 uptrend
    base_length_days: int = 0            # How many days the base spans
    score: int = 0                       # 0-100 composite


class VCPScanner:
    """Scan a single stock's DataFrame for VCP pattern."""

    def __init__(self, df: pd.DataFrame):
        if len(df) < 60:
            self.df = df.copy()
            self._valid = False
            return

        self.df = df.copy()
        self._valid = True

        # Pre-compute EMAs
        self.df['ema50'] = ta.ema(self.df['close'], length=EMA_MEDIUM)
        self.df['ema200'] = ta.ema(self.df['close'], length=EMA_LONG)
        self.df['vol_sma20'] = ta.sma(self.df['volume'].astype(float), length=20)

    # ------------------------------------------------------------------
    # Swing-point detection (reuses pattern from divergence.py)
    # ------------------------------------------------------------------
    def _find_swing_points(self, lookback: int = 0) -> Tuple[List[dict], List[dict]]:
        """Find swing highs and swing lows in the recent base area."""
        max_base = _CFG['max_base_days']
        window = _CFG['swing_window']
        segment = self.df.tail(max_base)

        highs: List[dict] = []
        lows: List[dict] = []

        for i in range(window, len(segment) - window):
            h = segment['high'].iloc[i]
            l = segment['low'].iloc[i]

            local_highs = segment['high'].iloc[i - window: i + window + 1]
            local_lows = segment['low'].iloc[i - window: i + window + 1]

            if h == local_highs.max():
                highs.append({'idx': i, 'price': h, 'bar': len(self.df) - len(segment) + i})
            if l == local_lows.min():
                lows.append({'idx': i, 'price': l, 'bar': len(self.df) - len(segment) + i})

        return highs, lows

    # ------------------------------------------------------------------
    # Contraction detection
    # ------------------------------------------------------------------
    def _detect_contractions(self, highs: List[dict], lows: List[dict]) -> List[float]:
        """Identify progressively smaller pullbacks from swing points.

        A contraction is measured as the % drop from a swing high to the
        subsequent swing low.
        """
        if len(highs) < 2 or len(lows) < 1:
            return []

        pullbacks: List[float] = []

        for i, sh in enumerate(highs):
            # Find the first swing low AFTER this swing high
            following_lows = [sl for sl in lows if sl['idx'] > sh['idx']]
            if not following_lows:
                continue
            sl = following_lows[0]
            if sh['price'] > 0:
                pullback_pct = (sh['price'] - sl['price']) / sh['price'] * 100
                if pullback_pct > 0:
                    pullbacks.append(round(pullback_pct, 1))

        return pullbacks

    def _pullbacks_contracting(self, pullbacks: List[float]) -> Tuple[int, List[float]]:
        """Return the count and list of qualifying contracting pullbacks."""
        if len(pullbacks) < 2:
            return 0, []

        ratio = _CFG['contraction_ratio']
        qualifying: List[float] = [pullbacks[0]]

        for i in range(1, len(pullbacks)):
            if pullbacks[i] < pullbacks[i - 1] * ratio:
                qualifying.append(pullbacks[i])
            elif pullbacks[i] < pullbacks[i - 1]:
                # Still smaller, just not dramatic enough — keep going
                qualifying.append(pullbacks[i])
            else:
                break  # no longer contracting

        count = len(qualifying) if len(qualifying) >= _CFG['min_contractions'] else 0
        return count, qualifying

    # ------------------------------------------------------------------
    # Volume profile
    # ------------------------------------------------------------------
    def _check_volume_declining(self) -> bool:
        """Volume in recent base should be declining relative to start."""
        max_base = _CFG['max_base_days']
        segment = self.df.tail(max_base)
        if len(segment) < 20:
            return False

        first_half_vol = segment['volume'].iloc[:len(segment) // 2].mean()
        second_half_vol = segment['volume'].iloc[len(segment) // 2:].mean()

        if first_half_vol == 0:
            return False

        decline = 1 - (second_half_vol / first_half_vol)
        return decline >= _CFG['volume_decline_min']

    # ------------------------------------------------------------------
    # Stage 2 check
    # ------------------------------------------------------------------
    def _check_stage2(self) -> bool:
        """Stage 2 uptrend: price > 50 EMA > 200 EMA."""
        latest = self.df.iloc[-1]
        ema50 = latest.get('ema50')
        ema200 = latest.get('ema200')

        if pd.isna(ema50) or pd.isna(ema200):
            return False

        return latest['close'] > ema50 > ema200

    # ------------------------------------------------------------------
    # Main detection
    # ------------------------------------------------------------------
    def detect_vcp(self) -> Optional[VCPPattern]:
        """Detect a VCP pattern. Returns VCPPattern or None."""
        if not self._valid:
            return None

        stage_2 = self._check_stage2()
        highs, lows = self._find_swing_points()
        raw_pullbacks = self._detect_contractions(highs, lows)
        count, qualifying = self._pullbacks_contracting(raw_pullbacks)

        if count < _CFG['min_contractions']:
            return None

        volume_declining = self._check_volume_declining()

        # Pivot = highest high in the base
        max_base = _CFG['max_base_days']
        pivot_price = self.df['high'].tail(max_base).max()
        current_price = self.df['close'].iloc[-1]
        latest_contraction = qualifying[-1] if qualifying else 0

        # Base length = distance from first swing high to now
        base_start_bar = highs[0]['bar'] if highs else len(self.df) - max_base
        base_length = len(self.df) - 1 - base_start_bar

        # ---- Scoring (0-100) ----
        score = 0

        # Stage 2 confirmed
        if stage_2:
            score += 20

        # Contractions (more = better pattern)
        if count >= 4:
            score += 25
        elif count >= 3:
            score += 20
        elif count >= 2:
            score += 15

        # Volume declining
        if volume_declining:
            score += 20

        # Tight latest contraction (< 10% = very tight)
        if latest_contraction < 5:
            score += 20
        elif latest_contraction < 10:
            score += 15
        elif latest_contraction < 15:
            score += 10

        # Price near pivot (ready to break out)
        proximity = (pivot_price - current_price) / pivot_price * 100 if pivot_price > 0 else 99
        if proximity < 2:
            score += 15
        elif proximity < _CFG['pivot_proximity_pct']:
            score += 10

        return VCPPattern(
            contractions=count,
            pullbacks=qualifying,
            volume_declining=volume_declining,
            pivot_price=round(pivot_price, 2),
            current_contraction_pct=round(latest_contraction, 1),
            stage_2=stage_2,
            base_length_days=base_length,
            score=min(100, score),
        )

    # ------------------------------------------------------------------
    # Standard interface for pipeline integration
    # ------------------------------------------------------------------
    def get_all_signals(self) -> Dict:
        """Return signals in the standard indicator format."""
        pattern = self.detect_vcp()

        if pattern is None:
            return {
                'total_score': 0,
                'signals': [],
                'details': {'vcp_detected': False},
            }

        signals = []
        total_score = 0

        if pattern.score >= 70:
            signals.append(f"Strong VCP: {pattern.contractions} contractions, "
                           f"latest {pattern.current_contraction_pct}%, "
                           f"pivot ₹{pattern.pivot_price}")
            total_score += 3
        elif pattern.score >= 50:
            signals.append(f"VCP forming: {pattern.contractions} contractions, "
                           f"latest {pattern.current_contraction_pct}%")
            total_score += 2
        elif pattern.score >= 30:
            signals.append(f"Possible VCP: {pattern.contractions} contractions")
            total_score += 1

        if not pattern.stage_2:
            signals.append("Warning: Not in Stage 2 uptrend")
            total_score -= 1

        return {
            'total_score': max(0, total_score),
            'signals': signals,
            'details': {
                'vcp_detected': True,
                'contractions': pattern.contractions,
                'pullbacks': pattern.pullbacks,
                'volume_declining': pattern.volume_declining,
                'pivot_price': pattern.pivot_price,
                'latest_contraction_pct': pattern.current_contraction_pct,
                'stage_2': pattern.stage_2,
                'base_days': pattern.base_length_days,
                'vcp_score': pattern.score,
            },
        }
