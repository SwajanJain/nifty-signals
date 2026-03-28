"""Pre-built Trading Strategies for Backtesting.

Three strategies ready for walk-forward validation:
  1. MinerviniSwing — Stage 2 uptrend entry, ATR stop, 2R target
  2. MomentumStrategy — RSI + EMA crossover
  3. MeanReversionStrategy — BB lower band + RSI oversold

Each strategy exposes a `signal_func(data, **params) -> DataFrame`
compatible with the WalkForwardBacktester, plus a `param_grid` dict
for optimization.

Optional backtesting.py integration via `run_bt_backtest()` if the
`backtesting` package is installed (AGPL — personal use only).
"""

from typing import Dict, List
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Strategy 1: Minervini Swing
# ---------------------------------------------------------------------------

def minervini_swing_signals(data: pd.DataFrame, *,
                            ema_fast: int = 20,
                            ema_slow: int = 50,
                            atr_mult: float = 2.0,
                            rr_ratio: float = 2.0) -> pd.DataFrame:
    """Stage 2 uptrend entry with ATR-based risk management.

    Entry: Close > EMA fast > EMA slow, price within 10% of 52w high
    Exit: Close drops below ATR trailing stop, or hits R:R target
    """
    df = data.copy()
    if 'date' not in df.columns:
        df['date'] = df.index

    close = df['close']
    high = df['high']
    low = df['low']

    ema_f = close.ewm(span=ema_fast, adjust=False).mean()
    ema_s = close.ewm(span=ema_slow, adjust=False).mean()

    # ATR
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    # 52-week high
    high_52w = high.rolling(252, min_periods=60).max()

    signals = pd.DataFrame({'date': df['date'], 'signal': 0})
    position = None

    for i in range(max(ema_slow, 60), len(df)):
        if position is None:
            # Entry conditions: Stage 2 uptrend
            stage2 = (
                close.iloc[i] > ema_f.iloc[i] > ema_s.iloc[i]
                and close.iloc[i] > high_52w.iloc[i] * 0.9  # within 10% of 52w high
                and ema_f.iloc[i] > ema_f.iloc[i - 5]  # EMA rising
            )
            if stage2:
                signals.iloc[i, 1] = 1
                stop = close.iloc[i] - atr_mult * atr.iloc[i]
                risk = close.iloc[i] - stop
                target = close.iloc[i] + rr_ratio * risk
                position = {'entry': close.iloc[i], 'stop': stop, 'target': target}
        else:
            # Exit: stop hit or target hit
            if close.iloc[i] <= position['stop'] or close.iloc[i] >= position['target']:
                signals.iloc[i, 1] = -1
                position = None
            else:
                # Trail stop
                new_stop = close.iloc[i] - atr_mult * atr.iloc[i]
                position['stop'] = max(position['stop'], new_stop)

    return signals


MINERVINI_PARAM_GRID = {
    'ema_fast': [10, 20],
    'ema_slow': [50],
    'atr_mult': [1.5, 2.0, 2.5],
    'rr_ratio': [2.0, 3.0],
}


# ---------------------------------------------------------------------------
# Strategy 2: Momentum (RSI + EMA Cross)
# ---------------------------------------------------------------------------

def momentum_signals(data: pd.DataFrame, *,
                     rsi_period: int = 14,
                     rsi_entry: int = 55,
                     rsi_exit: int = 70,
                     ema_period: int = 20) -> pd.DataFrame:
    """Momentum entry on RSI crossing above threshold with EMA confirmation.

    Entry: RSI crosses above rsi_entry, close > EMA
    Exit: RSI crosses above rsi_exit (overbought) or close drops below EMA
    """
    df = data.copy()
    if 'date' not in df.columns:
        df['date'] = df.index

    close = df['close']
    ema = close.ewm(span=ema_period, adjust=False).mean()

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(rsi_period).mean()
    avg_loss = loss.rolling(rsi_period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    signals = pd.DataFrame({'date': df['date'], 'signal': 0})
    position = False

    for i in range(rsi_period + 1, len(df)):
        if not position:
            if (rsi.iloc[i] > rsi_entry
                    and rsi.iloc[i - 1] <= rsi_entry
                    and close.iloc[i] > ema.iloc[i]):
                signals.iloc[i, 1] = 1
                position = True
        else:
            if rsi.iloc[i] > rsi_exit or close.iloc[i] < ema.iloc[i]:
                signals.iloc[i, 1] = -1
                position = False

    return signals


MOMENTUM_PARAM_GRID = {
    'rsi_period': [14],
    'rsi_entry': [50, 55, 60],
    'rsi_exit': [70, 75, 80],
    'ema_period': [10, 20],
}


# ---------------------------------------------------------------------------
# Strategy 3: Mean Reversion (BB + RSI Oversold)
# ---------------------------------------------------------------------------

def mean_reversion_signals(data: pd.DataFrame, *,
                           bb_period: int = 20,
                           bb_std: float = 2.0,
                           rsi_period: int = 14,
                           rsi_oversold: int = 30,
                           rsi_exit: int = 50) -> pd.DataFrame:
    """Mean reversion entry at Bollinger Band lower band + RSI oversold.

    Entry: Close touches lower BB and RSI < oversold
    Exit: Close crosses above middle BB or RSI > exit threshold
    """
    df = data.copy()
    if 'date' not in df.columns:
        df['date'] = df.index

    close = df['close']

    # Bollinger Bands
    sma = close.rolling(bb_period).mean()
    std = close.rolling(bb_period).std()
    lower = sma - bb_std * std
    upper = sma + bb_std * std

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(rsi_period).mean()
    avg_loss = loss.rolling(rsi_period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    signals = pd.DataFrame({'date': df['date'], 'signal': 0})
    position = False

    for i in range(max(bb_period, rsi_period) + 1, len(df)):
        if not position:
            if close.iloc[i] <= lower.iloc[i] and rsi.iloc[i] < rsi_oversold:
                signals.iloc[i, 1] = 1
                position = True
        else:
            if close.iloc[i] >= sma.iloc[i] or rsi.iloc[i] > rsi_exit:
                signals.iloc[i, 1] = -1
                position = False

    return signals


MEAN_REVERSION_PARAM_GRID = {
    'bb_period': [20],
    'bb_std': [1.5, 2.0, 2.5],
    'rsi_period': [14],
    'rsi_oversold': [25, 30, 35],
    'rsi_exit': [45, 50, 55],
}


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

STRATEGY_REGISTRY = {
    'swing': {
        'name': 'Minervini Swing',
        'func': minervini_swing_signals,
        'grid': MINERVINI_PARAM_GRID,
    },
    'momentum': {
        'name': 'RSI Momentum',
        'func': momentum_signals,
        'grid': MOMENTUM_PARAM_GRID,
    },
    'mean_reversion': {
        'name': 'BB Mean Reversion',
        'func': mean_reversion_signals,
        'grid': MEAN_REVERSION_PARAM_GRID,
    },
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_backtest(strategy_name: str, symbol: str,
                 days: int = 1000) -> Dict:
    """Run walk-forward backtest for a strategy on a symbol.

    Args:
        strategy_name: Key from STRATEGY_REGISTRY
        symbol: Stock symbol
        days: Number of days of data

    Returns:
        WalkForwardResult or dict with error
    """
    from data.fetcher import StockDataFetcher
    from backtest.walk_forward import WalkForwardBacktester, WindowType

    strategy = STRATEGY_REGISTRY.get(strategy_name)
    if not strategy:
        return {'error': f"Unknown strategy: {strategy_name}. Available: {list(STRATEGY_REGISTRY.keys())}"}

    fetcher = StockDataFetcher()
    df = fetcher.fetch_stock_data(symbol, "daily", lookback_days=days)
    if df is None or len(df) < 252:
        return {'error': f"Insufficient data for {symbol} (need 252+ days, got {len(df) if df is not None else 0})"}

    # Ensure 'date' column
    if 'date' not in df.columns:
        df = df.reset_index()
        if 'Date' in df.columns:
            df = df.rename(columns={'Date': 'date'})
        elif 'index' in df.columns:
            df = df.rename(columns={'index': 'date'})

    backtester = WalkForwardBacktester(
        window_type=WindowType.ROLLING,
        in_sample_months=12,
        out_sample_months=3,
        step_months=3,
    )

    result = backtester.run_backtest(
        strategy_name=strategy['name'],
        data=df,
        signal_func=strategy['func'],
        param_grid=strategy['grid'],
    )

    return result
