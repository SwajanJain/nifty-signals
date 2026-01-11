"""
Mean Reversion Model - Buys oversold, sells overbought.

Works best in:
- Ranging markets
- Pullbacks in uptrends
- Oversold bounces

Based on:
- Bollinger Band strategies
- RSI extremes
- Standard deviation analysis
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
from .ensemble import BaseModel, ModelSignal, SignalDirection


class MeanReversionModel(BaseModel):
    """
    Mean reversion signal generation.

    Looks for:
    - Price at Bollinger Band extremes
    - RSI oversold/overbought
    - Price stretched from moving average
    - Reversal candlestick patterns
    """

    def __init__(self, weight: float = 1.0):
        super().__init__("MeanReversion", weight)

        # Works better in ranging markets
        self.regime_weights = {
            'STRONG_BULL': 0.7,  # Counter-trend in strong trends is risky
            'BULL': 0.8,
            'NEUTRAL': 1.3,  # Best for ranging markets
            'BEAR': 0.8,
            'STRONG_BEAR': 0.5,
            'CRASH': 0.2  # Only for very oversold bounces
        }

    def generate_signal(self, df: pd.DataFrame, regime: str = "NEUTRAL") -> ModelSignal:
        """Generate mean reversion signal."""
        if len(df) < 30:
            return self._neutral_signal("Insufficient data")

        reasons = []
        score = 0
        confidence = 0.5

        latest = df.iloc[-1]
        close = latest['close']

        # 1. Bollinger Bands
        bb = ta.bbands(df['close'], length=20, std=2)
        if bb is not None and len(bb) > 0:
            bb_cols = bb.columns.tolist()
            bb_upper = bb[[c for c in bb_cols if 'BBU_' in c][0]].iloc[-1]
            bb_lower = bb[[c for c in bb_cols if 'BBL_' in c][0]].iloc[-1]
            bb_mid = bb[[c for c in bb_cols if 'BBM_' in c][0]].iloc[-1]

            # Position relative to bands
            bb_pct = (close - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

            if bb_pct < 0.1:
                score += 2
                reasons.append(f"At lower Bollinger Band - oversold")
            elif bb_pct < 0.2:
                score += 1
                reasons.append("Near lower BB")
            elif bb_pct > 0.9:
                score -= 2
                reasons.append("At upper Bollinger Band - overbought")
            elif bb_pct > 0.8:
                score -= 1

        # 2. RSI extremes
        rsi = ta.rsi(df['close'], length=14).iloc[-1]
        if rsi < 30:
            score += 2
            reasons.append(f"RSI {rsi:.0f} - deeply oversold")
            confidence += 0.1
        elif rsi < 40:
            score += 1
            reasons.append(f"RSI {rsi:.0f} - oversold zone")
        elif rsi > 70:
            score -= 2
            reasons.append(f"RSI {rsi:.0f} - overbought")
        elif rsi > 60:
            score -= 0.5

        # 3. Distance from 20 EMA
        ema_20 = ta.ema(df['close'], length=20).iloc[-1]
        distance_pct = ((close - ema_20) / ema_20) * 100

        if distance_pct < -5:
            score += 1.5
            reasons.append(f"Extended {abs(distance_pct):.1f}% below EMA20")
        elif distance_pct < -3:
            score += 0.5
        elif distance_pct > 5:
            score -= 1.5
            reasons.append(f"Extended {distance_pct:.1f}% above EMA20")
        elif distance_pct > 3:
            score -= 0.5

        # 4. Stochastic
        stoch = ta.stoch(df['high'], df['low'], df['close'])
        if stoch is not None and len(stoch) > 0:
            stoch_k = stoch[[c for c in stoch.columns if 'STOCHk_' in c][0]].iloc[-1]
            stoch_d = stoch[[c for c in stoch.columns if 'STOCHd_' in c][0]].iloc[-1]

            if stoch_k < 20 and stoch_d < 20:
                score += 1
                reasons.append("Stochastic oversold")
            elif stoch_k > 80 and stoch_d > 80:
                score -= 1

        # 5. Reversal pattern check (simple version)
        prev_close = df['close'].iloc[-2]
        prev_prev_close = df['close'].iloc[-3]

        # Bullish reversal: down, down, then up
        if prev_prev_close > prev_close and close > prev_close:
            if score > 0:  # Only if already showing oversold
                score += 0.5
                reasons.append("Potential bullish reversal forming")

        # Bearish reversal: up, up, then down
        if prev_prev_close < prev_close and close < prev_close:
            if score < 0:
                score -= 0.5

        # 6. Volume on reversal day
        if close > prev_close:
            today_vol = latest['volume']
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            if today_vol > avg_vol * 1.5 and score > 0:
                score += 0.5
                reasons.append("High volume on up day")

        # Confidence adjustment
        confidence = min(0.85, 0.4 + (abs(score) / 6) * 0.4)

        # In strong trend regimes, reduce confidence for counter-trend
        if regime in ['STRONG_BULL', 'STRONG_BEAR']:
            confidence *= 0.7

        # Determine direction
        if score >= 3:
            direction = SignalDirection.STRONG_BUY
        elif score >= 1.5:
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
                'rsi': rsi,
                'distance_from_ema': distance_pct
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
