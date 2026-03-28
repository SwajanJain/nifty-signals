"""TTM Squeeze Indicator — John Carter.

Identifies periods of extreme volatility compression (Bollinger Bands inside
Keltner Channels) that precede explosive directional moves.

Components:
  1. Squeeze dots: BB inside KC → squeeze ON (low volatility coiling)
  2. Momentum histogram: linear regression of (close − midline) → direction

Signals:
  - Squeeze ON + momentum turning positive → FIRE_LONG
  - Squeeze ON + momentum turning negative → FIRE_SHORT
  - Squeeze has been ON for 6+ bars → high probability move imminent
"""

from dataclasses import dataclass
from typing import Dict
import pandas as pd
import numpy as np
import pandas_ta as ta
from scipy.stats import linregress


# ---------------------------------------------------------------------------
# Config defaults (overridable via config.py TTM_SQUEEZE_CONFIG)
# ---------------------------------------------------------------------------
try:
    from config import TTM_SQUEEZE_CONFIG
except ImportError:
    TTM_SQUEEZE_CONFIG = {}

_CFG = {
    'bb_length': 20,
    'bb_mult': 2.0,
    'kc_length': 20,
    'kc_mult': 1.5,
    'min_squeeze_bars': 6,
    'momentum_lookback': 20,
}
_CFG.update(TTM_SQUEEZE_CONFIG)


@dataclass
class SqueezeSignal:
    """Result of TTM Squeeze analysis."""
    is_squeezing: bool = False       # BB inside KC right now
    squeeze_bars: int = 0            # Consecutive bars in squeeze
    momentum: float = 0.0            # Current momentum value
    momentum_rising: bool = False    # Histogram increasing
    momentum_color: str = 'gray'     # green / red / lime / maroon / gray
    signal: str = 'NO_SQUEEZE'       # FIRE_LONG, FIRE_SHORT, SQUEEZING, NO_SQUEEZE
    score: int = 0                   # 0-100 quality


class TTMSqueeze:
    """TTM Squeeze indicator for a single stock."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._valid = len(df) >= _CFG['bb_length'] + 10
        if self._valid:
            self._compute()

    # ------------------------------------------------------------------
    def _compute(self):
        bb_len = _CFG['bb_length']
        bb_m = _CFG['bb_mult']
        kc_len = _CFG['kc_length']
        kc_m = _CFG['kc_mult']

        close = self.df['close']

        # --- Bollinger Bands ---
        bb_mid = close.rolling(bb_len).mean()
        bb_std = close.rolling(bb_len).std()
        self.df['bb_upper'] = bb_mid + bb_m * bb_std
        self.df['bb_lower'] = bb_mid - bb_m * bb_std

        # --- Keltner Channels ---
        kc_mid = close.rolling(kc_len).mean()
        atr = ta.atr(self.df['high'], self.df['low'], close, length=kc_len)
        self.df['kc_upper'] = kc_mid + kc_m * atr
        self.df['kc_lower'] = kc_mid - kc_m * atr

        # --- Squeeze detection (BB inside KC) ---
        self.df['squeeze'] = (
            (self.df['bb_lower'] > self.df['kc_lower']) &
            (self.df['bb_upper'] < self.df['kc_upper'])
        )

        # --- Momentum: linear regression of delta ---
        # delta = close − average(KC mid, BB mid)
        avg_mid = (kc_mid + bb_mid) / 2
        delta = close - avg_mid
        mom_lookback = _CFG['momentum_lookback']

        momentum_vals = []
        for i in range(len(delta)):
            if i < mom_lookback - 1 or pd.isna(delta.iloc[i]):
                momentum_vals.append(np.nan)
            else:
                window = delta.iloc[i - mom_lookback + 1: i + 1].dropna()
                if len(window) < mom_lookback // 2:
                    momentum_vals.append(np.nan)
                else:
                    x = np.arange(len(window))
                    slope, intercept, _, _, _ = linregress(x, window.values)
                    # Momentum = last fitted value (current regression estimate)
                    momentum_vals.append(intercept + slope * (len(window) - 1))

        self.df['momentum'] = momentum_vals

    # ------------------------------------------------------------------
    def analyze(self) -> SqueezeSignal:
        """Produce the squeeze signal for the latest bar."""
        if not self._valid:
            return SqueezeSignal()

        latest = self.df.iloc[-1]
        prev = self.df.iloc[-2] if len(self.df) > 1 else latest

        is_squeezing = bool(latest.get('squeeze', False))

        # Count consecutive squeeze bars
        squeeze_bars = 0
        for i in range(len(self.df) - 1, -1, -1):
            if self.df['squeeze'].iloc[i]:
                squeeze_bars += 1
            else:
                break

        mom = latest.get('momentum', np.nan)
        prev_mom = prev.get('momentum', np.nan)
        if pd.isna(mom):
            mom = 0.0
        if pd.isna(prev_mom):
            prev_mom = 0.0

        momentum_rising = mom > prev_mom

        # Color scheme (matches TradingView convention)
        if mom > 0 and momentum_rising:
            color = 'lime'        # positive and increasing
        elif mom > 0:
            color = 'green'       # positive but decreasing (fading)
        elif mom < 0 and not momentum_rising:
            color = 'maroon'      # negative and decreasing (bearish momentum building)
        elif mom < 0:
            color = 'red'         # negative but increasing (bear fading)
        else:
            color = 'gray'

        # --- Signal classification ---
        # "Fire" = squeeze just released (was squeezing, now isn't)
        was_squeezing = bool(prev.get('squeeze', False))
        squeeze_fired = was_squeezing and not is_squeezing

        if squeeze_fired and mom > 0:
            signal = 'FIRE_LONG'
        elif squeeze_fired and mom < 0:
            signal = 'FIRE_SHORT'
        elif is_squeezing:
            signal = 'SQUEEZING'
        else:
            signal = 'NO_SQUEEZE'

        # --- Scoring ---
        score = 0
        if is_squeezing:
            score += 20
            if squeeze_bars >= _CFG['min_squeeze_bars']:
                score += 20  # prolonged squeeze = higher probability
            elif squeeze_bars >= 3:
                score += 10
        if squeeze_fired:
            score += 30  # squeeze just fired = highest priority
        if mom > 0 and momentum_rising:
            score += 15
        elif mom > 0:
            score += 10
        if signal == 'FIRE_LONG':
            score += 15  # bonus for bullish fire

        return SqueezeSignal(
            is_squeezing=is_squeezing,
            squeeze_bars=squeeze_bars,
            momentum=round(float(mom), 2),
            momentum_rising=momentum_rising,
            momentum_color=color,
            signal=signal,
            score=min(100, score),
        )

    # ------------------------------------------------------------------
    # Standard pipeline interface
    # ------------------------------------------------------------------
    def get_all_signals(self) -> Dict:
        """Return signals in the standard indicator format."""
        sq = self.analyze()

        signals = []
        total_score = 0

        if sq.signal == 'FIRE_LONG':
            signals.append(f"TTM Squeeze FIRED LONG (momentum {sq.momentum:+.1f})")
            total_score += 3
        elif sq.signal == 'FIRE_SHORT':
            signals.append(f"TTM Squeeze FIRED SHORT (momentum {sq.momentum:+.1f})")
            total_score -= 2
        elif sq.signal == 'SQUEEZING':
            direction = "bullish" if sq.momentum > 0 else "bearish" if sq.momentum < 0 else "neutral"
            signals.append(f"TTM Squeeze ON ({sq.squeeze_bars} bars, {direction} momentum)")
            if sq.momentum > 0 and sq.momentum_rising:
                total_score += 2
            elif sq.momentum > 0:
                total_score += 1
            elif sq.momentum < 0 and not sq.momentum_rising:
                total_score -= 1

        return {
            'total_score': total_score,
            'signals': signals,
            'details': {
                'is_squeezing': sq.is_squeezing,
                'squeeze_bars': sq.squeeze_bars,
                'squeeze_fired': sq.signal.startswith('FIRE'),
                'momentum': sq.momentum,
                'momentum_rising': sq.momentum_rising,
                'momentum_color': sq.momentum_color,
                'signal': sq.signal,
                'squeeze_score': sq.score,
            },
        }
