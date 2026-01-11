"""
Breakout Model - Captures new trends early.

Based on:
- Nicolas Darvas box method
- Mark Minervini's VCP (Volatility Contraction Pattern)
- Richard Wyckoff accumulation/distribution
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
from .ensemble import BaseModel, ModelSignal, SignalDirection


class BreakoutModel(BaseModel):
    """
    Breakout signal generation.

    Looks for:
    - Price breaking above resistance
    - Volume surge on breakout
    - Volatility contraction before breakout
    - Base formation patterns
    """

    def __init__(self, weight: float = 1.0):
        super().__init__("Breakout", weight)

        # Works best in bullish regimes
        self.regime_weights = {
            'STRONG_BULL': 1.4,
            'BULL': 1.2,
            'NEUTRAL': 0.9,
            'BEAR': 0.4,
            'STRONG_BEAR': 0.2,
            'CRASH': 0.0
        }

    def generate_signal(self, df: pd.DataFrame, regime: str = "NEUTRAL") -> ModelSignal:
        """Generate breakout signal."""
        if len(df) < 50:
            return self._neutral_signal("Insufficient data")

        reasons = []
        score = 0
        confidence = 0.5

        latest = df.iloc[-1]
        close = latest['close']
        high = latest['high']
        volume = latest['volume']

        # 1. Resistance breakout (20-day high)
        high_20 = df['high'].tail(20).max()
        high_50 = df['high'].tail(50).max()

        # Breaking 20-day high
        if high > high_20 and close > df['close'].iloc[-2]:
            score += 2
            reasons.append(f"Breaking 20-day high ({high_20:.2f})")

            # Even better if breaking 50-day high
            if high > high_50:
                score += 1
                reasons.append("Breaking 50-day high")

        # Breaking below lows is bearish breakout
        low_20 = df['low'].tail(20).min()
        if close < low_20:
            score -= 2
            reasons.append(f"Breaking below 20-day low ({low_20:.2f})")

        # 2. Volume confirmation
        vol_avg_20 = df['volume'].rolling(20).mean().iloc[-1]
        vol_ratio = volume / vol_avg_20 if vol_avg_20 > 0 else 1

        if vol_ratio > 2.0 and score > 0:
            score += 1.5
            reasons.append(f"Volume {vol_ratio:.1f}x average - strong confirmation")
            confidence += 0.1
        elif vol_ratio > 1.5 and score > 0:
            score += 0.5
            reasons.append(f"Volume {vol_ratio:.1f}x average")
        elif vol_ratio < 0.8 and score > 0:
            score -= 0.5
            reasons.append("Low volume breakout - suspicious")
            confidence -= 0.1

        # 3. Volatility contraction pattern (VCP)
        # ATR getting smaller = contraction
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        if atr is not None and len(atr) >= 20:
            recent_atr = atr.tail(5).mean()
            older_atr = atr.tail(20).head(15).mean()

            if recent_atr < older_atr * 0.7:
                score += 1
                reasons.append("Volatility contraction - potential breakout setup")

        # 4. Base formation (price consolidation)
        # Check if price has been in a tight range
        range_20 = df['high'].tail(20).max() - df['low'].tail(20).min()
        range_pct = (range_20 / close) * 100

        if range_pct < 10 and score > 0:
            score += 0.5
            reasons.append(f"Tight base formation ({range_pct:.1f}% range)")

        # 5. Price above key moving averages
        ema_20 = ta.ema(df['close'], length=20).iloc[-1]
        ema_50 = ta.ema(df['close'], length=50).iloc[-1]

        if close > ema_20 and close > ema_50:
            if score > 0:
                score += 0.5
                reasons.append("Breaking out above EMAs")
        elif close < ema_20 and close < ema_50:
            if score < 0:
                score -= 0.5

        # 6. Check for false breakout (close below high)
        if high > high_20 and close < high_20:
            score -= 1
            reasons.append("Warning: Potential false breakout (couldn't hold highs)")

        # 7. Gap up breakout (extra strength)
        prev_close = df['close'].iloc[-2]
        gap_pct = ((df['open'].iloc[-1] - prev_close) / prev_close) * 100

        if gap_pct > 1 and score > 0:
            score += 0.5
            reasons.append(f"Gap up {gap_pct:.1f}% - strong opening")

        # Confidence based on volume and price action
        confidence = min(0.9, 0.4 + (abs(score) / 6) * 0.4)

        if vol_ratio > 2:
            confidence = min(0.95, confidence + 0.1)

        # Determine direction
        if score >= 4:
            direction = SignalDirection.STRONG_BUY
        elif score >= 2:
            direction = SignalDirection.BUY
        elif score <= -3:
            direction = SignalDirection.STRONG_SELL
        elif score <= -1.5:
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
                'volume_ratio': vol_ratio,
                'high_20': high_20,
                'range_pct': range_pct
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
