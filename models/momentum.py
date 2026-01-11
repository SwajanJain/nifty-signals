"""
Momentum Model - Buys strength, sells weakness.

Based on:
- William O'Neil's momentum principles
- Minervini's SEPA methodology
- Relative strength concepts
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
from .ensemble import BaseModel, ModelSignal, SignalDirection


class MomentumModel(BaseModel):
    """
    Momentum-based signal generation.

    Looks for:
    - Price making new highs
    - Strong relative strength
    - Increasing volume on up days
    - RSI in bullish range
    """

    def __init__(self, weight: float = 1.0):
        super().__init__("Momentum", weight)

        # Regime adjustments - momentum works best in trends
        self.regime_weights = {
            'STRONG_BULL': 1.3,
            'BULL': 1.2,
            'NEUTRAL': 1.0,
            'BEAR': 0.6,
            'STRONG_BEAR': 0.3,
            'CRASH': 0.0
        }

    def generate_signal(self, df: pd.DataFrame, regime: str = "NEUTRAL") -> ModelSignal:
        """Generate momentum signal."""
        if len(df) < 50:
            return self._neutral_signal("Insufficient data")

        reasons = []
        score = 0
        confidence = 0.5

        latest = df.iloc[-1]
        close = latest['close']

        # 1. Price vs 52-week high
        high_52w = df['high'].tail(252).max() if len(df) >= 252 else df['high'].max()
        pct_from_high = (close / high_52w - 1) * 100

        if pct_from_high > -5:
            score += 2
            reasons.append(f"Within 5% of 52W high ({pct_from_high:.1f}%)")
        elif pct_from_high > -15:
            score += 1
            reasons.append(f"Within 15% of 52W high")
        elif pct_from_high < -30:
            score -= 1
            reasons.append(f"More than 30% from high - weak momentum")

        # 2. RSI momentum
        rsi = ta.rsi(df['close'], length=14).iloc[-1]
        if rsi > 60 and rsi < 80:
            score += 1
            reasons.append(f"RSI {rsi:.0f} - bullish momentum")
        elif rsi > 50:
            score += 0.5
        elif rsi < 40:
            score -= 1
            reasons.append(f"RSI {rsi:.0f} - weak momentum")

        # 3. Price vs moving averages
        ema_20 = ta.ema(df['close'], length=20).iloc[-1]
        ema_50 = ta.ema(df['close'], length=50).iloc[-1]

        if close > ema_20 > ema_50:
            score += 1.5
            reasons.append("Price > EMA20 > EMA50 - uptrend")
        elif close > ema_20:
            score += 0.5
        elif close < ema_20 < ema_50:
            score -= 1.5
            reasons.append("Price < EMA20 < EMA50 - downtrend")

        # 4. Rate of change (momentum indicator)
        roc_10 = ((close / df['close'].iloc[-11]) - 1) * 100 if len(df) > 10 else 0
        roc_20 = ((close / df['close'].iloc[-21]) - 1) * 100 if len(df) > 20 else 0

        if roc_10 > 5 and roc_20 > 10:
            score += 1.5
            reasons.append(f"Strong momentum: 10D {roc_10:.1f}%, 20D {roc_20:.1f}%")
        elif roc_10 > 0 and roc_20 > 0:
            score += 0.5
        elif roc_10 < -5:
            score -= 1

        # 5. Volume confirmation
        vol_sma = df['volume'].rolling(20).mean().iloc[-1]
        recent_up_vol = df.tail(5)[df['close'].diff() > 0]['volume'].mean()
        recent_down_vol = df.tail(5)[df['close'].diff() <= 0]['volume'].mean()

        if recent_up_vol > recent_down_vol * 1.5:
            score += 1
            reasons.append("Volume confirms upward momentum")
        elif recent_down_vol > recent_up_vol * 1.5:
            score -= 1

        # Calculate confidence based on conviction of signals
        max_score = 7  # Maximum possible positive score
        confidence = min(0.9, 0.4 + (abs(score) / max_score) * 0.5)

        # Determine direction
        if score >= 4:
            direction = SignalDirection.STRONG_BUY
        elif score >= 2:
            direction = SignalDirection.BUY
        elif score <= -4:
            direction = SignalDirection.STRONG_SELL
        elif score <= -2:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.NEUTRAL

        return ModelSignal(
            model_name=self.name,
            direction=direction,
            confidence=confidence,
            weight=self.weight,
            reasons=reasons,
            metadata={
                'raw_score': score,
                'rsi': rsi,
                'roc_10': roc_10,
                'pct_from_high': pct_from_high
            }
        )

    def _neutral_signal(self, reason: str) -> ModelSignal:
        return ModelSignal(
            model_name=self.name,
            direction=SignalDirection.NEUTRAL,
            confidence=0.3,
            weight=self.weight,
            reasons=[reason]
        )
