"""
pandas_ta compatibility shim.
Implements the subset of pandas_ta functions used by nifty-signals
using pure numpy/pandas calculations.
"""

import numpy as np
import pandas as pd


def ema(close, length=20, **kwargs):
    """Exponential Moving Average."""
    return close.ewm(span=length, adjust=False).mean()


def sma(close, length=20, **kwargs):
    """Simple Moving Average."""
    return close.rolling(window=length).mean()


def rsi(close, length=14, **kwargs):
    """Relative Strength Index."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    result.name = f"RSI_{length}"
    return result


def macd(close, fast=12, slow=26, signal=9, **kwargs):
    """MACD - Moving Average Convergence Divergence."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    result = pd.DataFrame({
        f"MACD_{fast}_{slow}_{signal}": macd_line,
        f"MACDh_{fast}_{slow}_{signal}": histogram,
        f"MACDs_{fast}_{slow}_{signal}": signal_line,
    })
    return result


def bbands(close, length=20, std=2.0, **kwargs):
    """Bollinger Bands."""
    mid = close.rolling(window=length).mean()
    std_dev = close.rolling(window=length).std()
    upper = mid + std * std_dev
    lower = mid - std * std_dev
    bandwidth = (upper - lower) / mid
    percent = (close - lower) / (upper - lower)

    result = pd.DataFrame({
        f"BBL_{length}_{std}": lower,
        f"BBM_{length}_{std}": mid,
        f"BBU_{length}_{std}": upper,
        f"BBB_{length}_{std}": bandwidth,
        f"BBP_{length}_{std}": percent,
    })
    return result


def atr(high, low, close, length=14, **kwargs):
    """Average True Range."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    result = tr.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    result.name = f"ATR_{length}"
    return result


def adx(high, low, close, length=14, **kwargs):
    """Average Directional Index."""
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    plus_dm = high - prev_high
    minus_dm = prev_low - low

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    _atr = atr(high, low, close, length=length)

    plus_di = 100 * (plus_dm.ewm(alpha=1 / length, min_periods=length, adjust=False).mean() / _atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / length, min_periods=length, adjust=False).mean() / _atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx_val = dx.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()

    result = pd.DataFrame({
        f"ADX_{length}": adx_val,
        f"DMP_{length}": plus_di,
        f"DMN_{length}": minus_di,
    })
    return result


def stoch(high, low, close, k=14, d=3, smooth_k=3, **kwargs):
    """Stochastic Oscillator."""
    lowest_low = low.rolling(window=k).min()
    highest_high = high.rolling(window=k).max()

    stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    stoch_k = stoch_k.rolling(window=smooth_k).mean()
    stoch_d = stoch_k.rolling(window=d).mean()

    result = pd.DataFrame({
        f"STOCHk_{k}_{d}_{smooth_k}": stoch_k,
        f"STOCHd_{k}_{d}_{smooth_k}": stoch_d,
    })
    return result


def supertrend(high, low, close, length=10, multiplier=3.0, **kwargs):
    """Supertrend indicator."""
    _atr = atr(high, low, close, length=length)
    hl2 = (high + low) / 2

    upper_band = hl2 + multiplier * _atr
    lower_band = hl2 - multiplier * _atr

    supertrend_vals = pd.Series(np.nan, index=close.index)
    direction = pd.Series(1, index=close.index)

    for i in range(length, len(close)):
        if np.isnan(upper_band.iloc[i]):
            continue

        if i == length:
            supertrend_vals.iloc[i] = upper_band.iloc[i]
            direction.iloc[i] = -1
            continue

        prev_st = supertrend_vals.iloc[i - 1]
        if np.isnan(prev_st):
            supertrend_vals.iloc[i] = upper_band.iloc[i]
            direction.iloc[i] = -1
            continue

        if direction.iloc[i - 1] == 1:  # was bullish
            if close.iloc[i] < prev_st:
                supertrend_vals.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend_vals.iloc[i] = max(lower_band.iloc[i], prev_st)
                direction.iloc[i] = 1
        else:  # was bearish
            if close.iloc[i] > prev_st:
                supertrend_vals.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
            else:
                supertrend_vals.iloc[i] = min(upper_band.iloc[i], prev_st)
                direction.iloc[i] = -1

    result = pd.DataFrame({
        f"SUPERT_{length}_{multiplier}": supertrend_vals,
        f"SUPERTd_{length}_{multiplier}": direction,
        f"SUPERTl_{length}_{multiplier}": lower_band,
        f"SUPERTs_{length}_{multiplier}": upper_band,
    })
    return result
