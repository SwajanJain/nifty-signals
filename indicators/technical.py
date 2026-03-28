"""Technical indicators calculation."""

from typing import Dict, Tuple
import os
import pandas as pd

from config import CACHE_DIR

# pandas_ta uses numba with on-disk caching; ensure it has a writable cache dir.
_NUMBA_CACHE_DIR = CACHE_DIR / "numba"
_NUMBA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(_NUMBA_CACHE_DIR))

import pandas_ta as ta

from config import (
    RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    EMA_SHORT, EMA_MEDIUM, EMA_LONG,
    BOLLINGER_PERIOD, BOLLINGER_STD,
    VOLUME_MULTIPLIER
)


class TechnicalIndicators:
    """Calculate technical indicators for stock data."""

    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLCV DataFrame.

        Args:
            df: DataFrame with columns: open, high, low, close, volume
        """
        self.df = df.copy()
        self._calculate_all()

    def _calculate_all(self):
        """Calculate all technical indicators."""
        # RSI
        self.df['rsi'] = ta.rsi(self.df['close'], length=RSI_PERIOD)

        # MACD
        macd = ta.macd(self.df['close'], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        self.df['macd'] = macd[f'MACD_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}']
        self.df['macd_signal'] = macd[f'MACDs_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}']
        self.df['macd_hist'] = macd[f'MACDh_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}']

        # EMAs
        self.df['ema_short'] = ta.ema(self.df['close'], length=EMA_SHORT)
        self.df['ema_medium'] = ta.ema(self.df['close'], length=EMA_MEDIUM)
        self.df['ema_long'] = ta.ema(self.df['close'], length=EMA_LONG)

        # Bollinger Bands
        bbands = ta.bbands(self.df['close'], length=BOLLINGER_PERIOD, std=BOLLINGER_STD)
        # Find column names dynamically (pandas-ta uses varying formats)
        bb_cols = bbands.columns.tolist()
        bb_upper_col = [c for c in bb_cols if c.startswith('BBU_')][0]
        bb_middle_col = [c for c in bb_cols if c.startswith('BBM_')][0]
        bb_lower_col = [c for c in bb_cols if c.startswith('BBL_')][0]
        self.df['bb_upper'] = bbands[bb_upper_col]
        self.df['bb_middle'] = bbands[bb_middle_col]
        self.df['bb_lower'] = bbands[bb_lower_col]
        self.df['bb_width'] = (self.df['bb_upper'] - self.df['bb_lower']) / self.df['bb_middle']

        # Volume analysis
        self.df['volume_sma'] = ta.sma(self.df['volume'], length=20)
        self.df['volume_ratio'] = self.df['volume'] / self.df['volume_sma']

    def get_latest(self) -> Dict:
        """Get the latest indicator values."""
        latest = self.df.iloc[-1]
        prev = self.df.iloc[-2] if len(self.df) > 1 else latest

        return {
            'close': latest['close'],
            'rsi': latest['rsi'],
            'macd': latest['macd'],
            'macd_signal': latest['macd_signal'],
            'macd_hist': latest['macd_hist'],
            'macd_hist_prev': prev['macd_hist'],
            'ema_short': latest['ema_short'],
            'ema_medium': latest['ema_medium'],
            'ema_long': latest['ema_long'],
            'bb_upper': latest['bb_upper'],
            'bb_middle': latest['bb_middle'],
            'bb_lower': latest['bb_lower'],
            'bb_width': latest['bb_width'],
            'volume_ratio': latest['volume_ratio'],
        }

    def get_rsi_signal(self) -> Tuple[int, str]:
        """
        Get RSI signal.

        Returns:
            (score, description)
        """
        rsi = self.df['rsi'].iloc[-1]

        if pd.isna(rsi):
            return 0, "RSI: N/A"

        if rsi < RSI_OVERSOLD:
            return 2, f"RSI: {rsi:.1f} (Oversold - Bullish)"
        elif rsi > RSI_OVERBOUGHT:
            return -2, f"RSI: {rsi:.1f} (Overbought - Bearish)"
        elif rsi < 40:
            return 1, f"RSI: {rsi:.1f} (Approaching oversold)"
        elif rsi > 60:
            return -1, f"RSI: {rsi:.1f} (Approaching overbought)"
        else:
            return 0, f"RSI: {rsi:.1f} (Neutral)"

    def get_macd_signal(self) -> Tuple[int, str]:
        """
        Get MACD signal.

        Returns:
            (score, description)
        """
        if len(self.df) < 2:
            return 0, "MACD: Insufficient data"

        curr_hist = self.df['macd_hist'].iloc[-1]
        prev_hist = self.df['macd_hist'].iloc[-2]

        if pd.isna(curr_hist) or pd.isna(prev_hist):
            return 0, "MACD: N/A"

        # Bullish crossover
        if prev_hist < 0 and curr_hist >= 0:
            return 2, "MACD: Bullish crossover"
        # Bearish crossover
        elif prev_hist > 0 and curr_hist <= 0:
            return -2, "MACD: Bearish crossover"
        # Bullish momentum increasing
        elif curr_hist > 0 and curr_hist > prev_hist:
            return 1, "MACD: Bullish momentum"
        # Bearish momentum increasing
        elif curr_hist < 0 and curr_hist < prev_hist:
            return -1, "MACD: Bearish momentum"
        else:
            return 0, "MACD: Neutral"

    def get_ema_signal(self) -> Tuple[int, str]:
        """
        Get EMA crossover signals.

        Returns:
            (score, description)
        """
        latest = self.df.iloc[-1]
        close = latest['close']
        ema_short = latest['ema_short']
        ema_medium = latest['ema_medium']

        if pd.isna(ema_short) or pd.isna(ema_medium):
            return 0, "EMA: N/A"

        score = 0
        signals = []

        # Price vs EMAs
        if close > ema_short:
            score += 1
            signals.append("Price > EMA20")
        else:
            score -= 1
            signals.append("Price < EMA20")

        if close > ema_medium:
            score += 1
            signals.append("Price > EMA50")
        else:
            score -= 1
            signals.append("Price < EMA50")

        # EMA crossover
        if ema_short > ema_medium:
            score += 1
            signals.append("EMA20 > EMA50")
        else:
            score -= 1
            signals.append("EMA20 < EMA50")

        return score, f"EMA: {', '.join(signals)}"

    def get_bollinger_signal(self) -> Tuple[int, str]:
        """
        Get Bollinger Bands signal.

        Returns:
            (score, description)
        """
        latest = self.df.iloc[-1]
        close = latest['close']
        bb_upper = latest['bb_upper']
        bb_lower = latest['bb_lower']
        bb_width = latest['bb_width']

        if pd.isna(bb_upper) or pd.isna(bb_lower):
            return 0, "Bollinger: N/A"

        # Check for squeeze (low volatility - potential breakout)
        avg_width = self.df['bb_width'].rolling(50).mean().iloc[-1]
        is_squeeze = bb_width < avg_width * 0.8 if not pd.isna(avg_width) else False

        if close <= bb_lower:
            if is_squeeze:
                return 2, "Bollinger: At lower band (Squeeze - High potential)"
            return 1, "Bollinger: At lower band (Potential bounce)"
        elif close >= bb_upper:
            return -1, "Bollinger: At upper band (Potential pullback)"
        elif is_squeeze:
            return 1, "Bollinger: Squeeze forming (Breakout anticipated)"
        else:
            return 0, "Bollinger: Within bands (Neutral)"

    def get_volume_signal(self) -> Tuple[int, str]:
        """
        Get volume confirmation signal.

        Returns:
            (score, description)
        """
        volume_ratio = self.df['volume_ratio'].iloc[-1]

        if pd.isna(volume_ratio):
            return 0, "Volume: N/A"

        if volume_ratio >= VOLUME_MULTIPLIER:
            # High volume - confirms direction
            close_change = self.df['close'].pct_change().iloc[-1]
            if close_change > 0:
                return 1, f"Volume: {volume_ratio:.1f}x avg (Bullish confirmation)"
            else:
                return -1, f"Volume: {volume_ratio:.1f}x avg (Bearish confirmation)"
        else:
            return 0, f"Volume: {volume_ratio:.1f}x avg (Normal)"

    def get_all_signals(self) -> Dict:
        """Get all technical indicator signals."""
        rsi_score, rsi_desc = self.get_rsi_signal()
        macd_score, macd_desc = self.get_macd_signal()
        ema_score, ema_desc = self.get_ema_signal()
        bb_score, bb_desc = self.get_bollinger_signal()
        vol_score, vol_desc = self.get_volume_signal()

        return {
            'rsi': {'score': rsi_score, 'description': rsi_desc},
            'macd': {'score': macd_score, 'description': macd_desc},
            'ema': {'score': ema_score, 'description': ema_desc},
            'bollinger': {'score': bb_score, 'description': bb_desc},
            'volume': {'score': vol_score, 'description': vol_desc},
            'total_score': rsi_score + macd_score + ema_score + bb_score + vol_score,
        }
