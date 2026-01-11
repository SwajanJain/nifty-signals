"""Multi-Timeframe Analysis - Weekly + Daily alignment."""

from typing import Dict, Tuple, Optional
from enum import Enum
import pandas as pd
import numpy as np
import pandas_ta as ta


class TimeframeTrend(Enum):
    """Trend direction for a timeframe."""
    STRONG_UP = "STRONG_UP"
    UP = "UP"
    NEUTRAL = "NEUTRAL"
    DOWN = "DOWN"
    STRONG_DOWN = "STRONG_DOWN"


class MultiTimeframeAnalyzer:
    """Analyze multiple timeframes for signal alignment."""

    def __init__(self, daily_df: pd.DataFrame, weekly_df: pd.DataFrame):
        """
        Initialize with daily and weekly data.

        Args:
            daily_df: Daily OHLCV DataFrame
            weekly_df: Weekly OHLCV DataFrame
        """
        self.daily = daily_df.copy()
        self.weekly = weekly_df.copy()
        self._calculate_indicators()

    def _calculate_indicators(self):
        """Calculate trend indicators for both timeframes."""
        for df in [self.daily, self.weekly]:
            if len(df) < 50:
                continue

            # EMAs
            df['ema_10'] = ta.ema(df['close'], length=10)
            df['ema_20'] = ta.ema(df['close'], length=20)
            df['ema_50'] = ta.ema(df['close'], length=50)

            # RSI
            df['rsi'] = ta.rsi(df['close'], length=14)

            # MACD
            macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
            macd_col = [c for c in macd.columns if c.startswith('MACD_')][0]
            hist_col = [c for c in macd.columns if c.startswith('MACDh_')][0]
            df['macd'] = macd[macd_col]
            df['macd_hist'] = macd[hist_col]

            # ADX
            adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
            adx_col = [c for c in adx_data.columns if c.startswith('ADX_')][0]
            dmp_col = [c for c in adx_data.columns if c.startswith('DMP_')][0]
            dmn_col = [c for c in adx_data.columns if c.startswith('DMN_')][0]
            df['adx'] = adx_data[adx_col]
            df['plus_di'] = adx_data[dmp_col]
            df['minus_di'] = adx_data[dmn_col]

    def analyze_timeframe(self, df: pd.DataFrame, name: str) -> Dict:
        """
        Analyze a single timeframe.

        Args:
            df: OHLCV DataFrame with indicators
            name: 'daily' or 'weekly'

        Returns:
            Dict with trend analysis
        """
        if len(df) < 50:
            return {
                'timeframe': name,
                'trend': TimeframeTrend.NEUTRAL,
                'score': 0,
                'signals': ['Insufficient data']
            }

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        score = 0
        signals = []

        # EMA alignment
        if latest['close'] > latest['ema_20'] > latest['ema_50']:
            score += 2
            signals.append("Price > EMA20 > EMA50 (Bullish alignment)")
        elif latest['close'] < latest['ema_20'] < latest['ema_50']:
            score -= 2
            signals.append("Price < EMA20 < EMA50 (Bearish alignment)")
        elif latest['close'] > latest['ema_20']:
            score += 1
            signals.append("Price > EMA20")
        else:
            score -= 1
            signals.append("Price < EMA20")

        # MACD
        if latest['macd_hist'] > 0:
            if latest['macd_hist'] > prev['macd_hist']:
                score += 1
                signals.append("MACD histogram rising (Bullish momentum)")
            else:
                signals.append("MACD histogram positive but falling")
        else:
            if latest['macd_hist'] < prev['macd_hist']:
                score -= 1
                signals.append("MACD histogram falling (Bearish momentum)")
            else:
                signals.append("MACD histogram negative but rising")

        # RSI
        rsi = latest['rsi']
        if rsi > 60:
            score += 1
            signals.append(f"RSI {rsi:.1f} (Bullish)")
        elif rsi < 40:
            score -= 1
            signals.append(f"RSI {rsi:.1f} (Bearish)")
        else:
            signals.append(f"RSI {rsi:.1f} (Neutral)")

        # ADX trend strength
        adx = latest['adx']
        plus_di = latest['plus_di']
        minus_di = latest['minus_di']

        if adx > 25:
            if plus_di > minus_di:
                score += 1
                signals.append(f"ADX {adx:.1f} Strong uptrend (+DI > -DI)")
            else:
                score -= 1
                signals.append(f"ADX {adx:.1f} Strong downtrend (-DI > +DI)")
        else:
            signals.append(f"ADX {adx:.1f} (Weak trend)")

        # Higher highs / Lower lows check (last 10 bars)
        recent = df.tail(10)
        hh = recent['high'].iloc[-1] > recent['high'].iloc[:-1].max()
        hl = recent['low'].iloc[-1] > recent['low'].iloc[:-1].min()
        lh = recent['high'].iloc[-1] < recent['high'].iloc[:-1].max()
        ll = recent['low'].iloc[-1] < recent['low'].iloc[:-1].min()

        if hh and hl:
            score += 1
            signals.append("Making higher highs & higher lows")
        elif lh and ll:
            score -= 1
            signals.append("Making lower highs & lower lows")

        # Determine trend
        if score >= 4:
            trend = TimeframeTrend.STRONG_UP
        elif score >= 2:
            trend = TimeframeTrend.UP
        elif score <= -4:
            trend = TimeframeTrend.STRONG_DOWN
        elif score <= -2:
            trend = TimeframeTrend.DOWN
        else:
            trend = TimeframeTrend.NEUTRAL

        return {
            'timeframe': name,
            'trend': trend,
            'trend_name': trend.value,
            'score': score,
            'signals': signals,
            'close': latest['close'],
            'ema_20': latest['ema_20'],
            'ema_50': latest['ema_50'],
            'rsi': rsi,
            'adx': adx
        }

    def get_alignment(self) -> Dict:
        """
        Check alignment between weekly and daily timeframes.

        Returns:
            Dict with alignment analysis and trading recommendation
        """
        weekly_analysis = self.analyze_timeframe(self.weekly, 'weekly')
        daily_analysis = self.analyze_timeframe(self.daily, 'daily')

        weekly_trend = weekly_analysis['trend']
        daily_trend = daily_analysis['trend']

        # Alignment scoring
        alignment_score = 0
        alignment_signals = []

        # Perfect alignment
        if weekly_trend in [TimeframeTrend.STRONG_UP, TimeframeTrend.UP]:
            if daily_trend in [TimeframeTrend.STRONG_UP, TimeframeTrend.UP]:
                alignment_score = 2
                alignment_signals.append("✅ ALIGNED: Weekly UP + Daily UP")
            elif daily_trend == TimeframeTrend.NEUTRAL:
                alignment_score = 1
                alignment_signals.append("⚠️ PARTIAL: Weekly UP, Daily consolidating")
            else:
                alignment_score = -1
                alignment_signals.append("❌ CONFLICT: Weekly UP but Daily DOWN")

        elif weekly_trend in [TimeframeTrend.STRONG_DOWN, TimeframeTrend.DOWN]:
            if daily_trend in [TimeframeTrend.STRONG_DOWN, TimeframeTrend.DOWN]:
                alignment_score = -2
                alignment_signals.append("✅ ALIGNED: Weekly DOWN + Daily DOWN (Avoid longs)")
            elif daily_trend == TimeframeTrend.NEUTRAL:
                alignment_score = -1
                alignment_signals.append("⚠️ Weekly DOWN, Daily consolidating")
            else:
                alignment_score = 0
                alignment_signals.append("❌ CONFLICT: Weekly DOWN but Daily UP (Counter-trend)")

        else:  # Weekly neutral
            if daily_trend in [TimeframeTrend.STRONG_UP, TimeframeTrend.UP]:
                alignment_score = 1
                alignment_signals.append("⚠️ Weekly NEUTRAL, Daily UP (Range breakout?)")
            elif daily_trend in [TimeframeTrend.STRONG_DOWN, TimeframeTrend.DOWN]:
                alignment_score = -1
                alignment_signals.append("⚠️ Weekly NEUTRAL, Daily DOWN")
            else:
                alignment_score = 0
                alignment_signals.append("⚠️ Both timeframes NEUTRAL (Choppy)")

        # Trading recommendation
        if alignment_score >= 2:
            recommendation = "STRONG_BUY_ZONE"
            should_buy = True
            confidence = "HIGH"
        elif alignment_score == 1:
            recommendation = "BUY_ZONE"
            should_buy = True
            confidence = "MEDIUM"
        elif alignment_score == 0:
            recommendation = "NEUTRAL_ZONE"
            should_buy = False
            confidence = "LOW"
        elif alignment_score == -1:
            recommendation = "AVOID_LONGS"
            should_buy = False
            confidence = "MEDIUM"
        else:
            recommendation = "SELL_ZONE"
            should_buy = False
            confidence = "HIGH"

        return {
            'weekly': weekly_analysis,
            'daily': daily_analysis,
            'alignment_score': alignment_score,
            'alignment_signals': alignment_signals,
            'recommendation': recommendation,
            'should_take_long': should_buy,
            'confidence': confidence,
            'summary': f"Weekly: {weekly_trend.value} | Daily: {daily_trend.value} | Alignment: {alignment_score}"
        }

    def get_optimal_entry(self) -> Dict:
        """
        Determine optimal entry based on timeframe alignment.

        Returns:
            Dict with entry recommendations
        """
        alignment = self.get_alignment()
        daily = self.daily

        entry_type = "NONE"
        entry_notes = []

        if not alignment['should_take_long']:
            return {
                'entry_type': 'NO_ENTRY',
                'reason': 'Timeframes not aligned for longs',
                'alignment': alignment
            }

        # Check for pullback entry in uptrend
        latest = daily.iloc[-1]
        ema_20 = latest['ema_20']
        close = latest['close']

        # Price at or near EMA20 in uptrend = pullback entry
        distance_to_ema = (close - ema_20) / ema_20 * 100

        if alignment['alignment_score'] >= 1:
            if distance_to_ema <= 1:
                entry_type = "PULLBACK_ENTRY"
                entry_notes.append(f"Price near EMA20 ({distance_to_ema:.1f}% away)")
                entry_notes.append("Ideal pullback entry in uptrend")
            elif distance_to_ema > 3:
                entry_type = "EXTENDED"
                entry_notes.append(f"Price extended {distance_to_ema:.1f}% above EMA20")
                entry_notes.append("Wait for pullback or use smaller size")
            else:
                entry_type = "BREAKOUT_ENTRY"
                entry_notes.append("Momentum entry - use tight stop")

        return {
            'entry_type': entry_type,
            'distance_to_ema20': distance_to_ema,
            'notes': entry_notes,
            'alignment': alignment
        }
