"""
Trend Following Model - Rides established trends.

Based on:
- Ed Seykota's trend following principles
- Turtle Trading rules
- Moving average crossovers
- ADX trend strength
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
from .ensemble import BaseModel, ModelSignal, SignalDirection


class TrendFollowingModel(BaseModel):
    """
    Trend following signal generation.

    Looks for:
    - Strong established trends (ADX > 25)
    - Moving average alignment
    - Higher highs and higher lows
    - Price holding above key levels
    """

    def __init__(self, weight: float = 1.0):
        super().__init__("TrendFollowing", weight)

        # Works best in trending markets
        self.regime_weights = {
            'STRONG_BULL': 1.3,
            'BULL': 1.2,
            'NEUTRAL': 0.8,  # Trends are less reliable
            'BEAR': 0.9,
            'STRONG_BEAR': 0.7,
            'CRASH': 0.1
        }

    def generate_signal(self, df: pd.DataFrame, regime: str = "NEUTRAL") -> ModelSignal:
        """Generate trend following signal."""
        if len(df) < 50:
            return self._neutral_signal("Insufficient data")

        reasons = []
        score = 0
        confidence = 0.5

        latest = df.iloc[-1]
        close = latest['close']

        # 1. ADX trend strength
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx_data is not None:
            adx = adx_data[[c for c in adx_data.columns if 'ADX_' in c][0]].iloc[-1]
            plus_di = adx_data[[c for c in adx_data.columns if 'DMP_' in c][0]].iloc[-1]
            minus_di = adx_data[[c for c in adx_data.columns if 'DMN_' in c][0]].iloc[-1]

            if adx > 25:
                if plus_di > minus_di:
                    score += 2
                    reasons.append(f"Strong uptrend: ADX {adx:.0f}, +DI > -DI")
                else:
                    score -= 2
                    reasons.append(f"Strong downtrend: ADX {adx:.0f}, -DI > +DI")

                confidence += 0.1
            elif adx < 20:
                reasons.append(f"Weak trend: ADX {adx:.0f}")
                confidence -= 0.1

        # 2. Moving average alignment
        ema_10 = ta.ema(df['close'], length=10).iloc[-1]
        ema_20 = ta.ema(df['close'], length=20).iloc[-1]
        ema_50 = ta.ema(df['close'], length=50).iloc[-1]
        sma_200 = ta.sma(df['close'], length=200).iloc[-1] if len(df) >= 200 else ema_50

        # Perfect bullish alignment
        if close > ema_10 > ema_20 > ema_50:
            score += 2
            reasons.append("Perfect EMA alignment (10 > 20 > 50)")
        elif close > ema_20 > ema_50:
            score += 1
            reasons.append("Bullish EMA alignment (20 > 50)")
        elif close < ema_10 < ema_20 < ema_50:
            score -= 2
            reasons.append("Bearish EMA alignment")
        elif close < ema_20 < ema_50:
            score -= 1

        # 3. Price above/below 200 SMA (long-term trend)
        if len(df) >= 200:
            if close > sma_200:
                score += 1
                reasons.append("Above 200 SMA - long-term uptrend")
            else:
                score -= 1
                reasons.append("Below 200 SMA - long-term downtrend")

        # 4. Higher highs and higher lows
        recent_10 = df.tail(10)
        highs = recent_10['high'].values
        lows = recent_10['low'].values

        # Check for HH/HL pattern
        mid_high = highs[4:6].max()
        recent_high = highs[8:10].max()
        mid_low = lows[4:6].min()
        recent_low = lows[8:10].min()

        if recent_high > mid_high and recent_low > mid_low:
            score += 1
            reasons.append("Higher highs and higher lows")
        elif recent_high < mid_high and recent_low < mid_low:
            score -= 1
            reasons.append("Lower highs and lower lows")

        # 5. MACD alignment
        macd = ta.macd(df['close'])
        if macd is not None:
            macd_line = macd[[c for c in macd.columns if 'MACD_' in c][0]].iloc[-1]
            signal_line = macd[[c for c in macd.columns if 'MACDs_' in c][0]].iloc[-1]
            hist = macd[[c for c in macd.columns if 'MACDh_' in c][0]].iloc[-1]
            prev_hist = macd[[c for c in macd.columns if 'MACDh_' in c][0]].iloc[-2]

            if macd_line > signal_line and hist > 0:
                if hist > prev_hist:
                    score += 1
                    reasons.append("MACD bullish and rising")
                else:
                    score += 0.5
                    reasons.append("MACD bullish")
            elif macd_line < signal_line and hist < 0:
                if hist < prev_hist:
                    score -= 1
                    reasons.append("MACD bearish and falling")
                else:
                    score -= 0.5

        # 6. Supertrend
        try:
            supertrend = ta.supertrend(df['high'], df['low'], df['close'], length=10, multiplier=3)
            if supertrend is not None:
                st_col = [c for c in supertrend.columns if 'SUPERTd_' in c][0]
                st_dir = supertrend[st_col].iloc[-1]

                if st_dir == 1:
                    score += 0.5
                    reasons.append("Supertrend bullish")
                else:
                    score -= 0.5
        except:
            pass

        # 7. Price holding above key EMA in pullback
        distance_from_20 = ((close - ema_20) / ema_20) * 100

        if 0 < distance_from_20 < 2 and score > 0:
            score += 0.5
            reasons.append("Pullback to EMA20 - potential entry")

        # Confidence based on trend strength
        confidence = min(0.9, 0.4 + (abs(score) / 7) * 0.5)

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
                'adx': adx if 'adx' in locals() else 0,
                'ema_alignment': 'bullish' if close > ema_20 > ema_50 else 'bearish'
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
