#!/usr/bin/env python3
"""
Stage E: Enrich Report

Generates richer analysis data for the ALREADY-DECIDED stock.
This is for REPORTING purposes only - it does NOT change the decision.

Outputs:
- symbol/<SYMBOL>.json (detailed analysis for the picked stock)

This stage runs AFTER make_decision.py and only enriches
the presentation layer.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.reliable_fetcher import get_reliable_fetcher


def load_json(filepath: Path) -> dict:
    """Load JSON file."""
    with open(filepath) as f:
        return json.load(f)


def _load_snapshot_df(run_dir: Path, symbol: str):
    """Load OHLCV from the run snapshot if available."""
    path = run_dir / "data" / "daily" / f"{symbol}.csv"
    if not path.exists():
        return None
    try:
        import pandas as pd

        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        expected = {"open", "high", "low", "close", "volume"}
        if not expected.issubset(set(df.columns)):
            return None
        return df[["open", "high", "low", "close", "volume"]].sort_index()
    except Exception:
        return None


def get_support_resistance(df, num_levels: int = 3) -> dict:
    """Calculate support and resistance levels."""
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values

    current = float(closes[-1])

    # Find recent swing highs and lows
    resistance_levels = []
    support_levels = []

    # Use rolling window to find local maxima/minima
    window = 20
    for i in range(window, len(highs) - window):
        # Check if it's a local maximum
        if highs[i] == max(highs[i-window:i+window+1]):
            if highs[i] > current:
                resistance_levels.append(float(highs[i]))

        # Check if it's a local minimum
        if lows[i] == min(lows[i-window:i+window+1]):
            if lows[i] < current:
                support_levels.append(float(lows[i]))

    # Get unique levels and sort
    resistance_levels = sorted(set([round(r, 2) for r in resistance_levels]))[:num_levels]
    support_levels = sorted(set([round(s, 2) for s in support_levels]), reverse=True)[:num_levels]

    # Add moving averages as dynamic levels
    ema20 = float(df['close'].ewm(span=20).mean().iloc[-1])
    ema50 = float(df['close'].ewm(span=50).mean().iloc[-1])
    ema200 = float(df['close'].ewm(span=200).mean().iloc[-1])

    return {
        'resistance': resistance_levels,
        'support': support_levels,
        'dynamic': {
            'ema20': round(ema20, 2),
            'ema50': round(ema50, 2),
            'ema200': round(ema200, 2)
        }
    }


def get_volume_analysis(df) -> dict:
    """Analyze volume patterns."""
    volumes = df['volume'].values
    closes = df['close'].values

    avg_20 = float(df['volume'].rolling(20).mean().iloc[-1])
    avg_50 = float(df['volume'].rolling(50).mean().iloc[-1])
    current = float(volumes[-1])

    # Volume trend (compare last 5 days avg to 20-day avg)
    recent_avg = float(df['volume'].tail(5).mean())
    volume_trend = 'INCREASING' if recent_avg > avg_20 else 'DECREASING'

    # Check for volume spike
    volume_spike = current > avg_20 * 1.5

    # Price-volume correlation (last 10 days)
    if len(df) >= 10:
        price_changes = df['close'].pct_change().tail(10).values
        vol_changes = df['volume'].pct_change().tail(10).values
        # Simple check: are volume and price moving together?
        positive_days = sum(1 for p, v in zip(price_changes, vol_changes) if p > 0 and v > 0)
        correlation = 'CONFIRMING' if positive_days >= 6 else 'DIVERGING'
    else:
        correlation = 'UNKNOWN'

    return {
        'current': int(current),
        'avg_20d': int(avg_20),
        'avg_50d': int(avg_50),
        'ratio_vs_avg': round(current / avg_20 if avg_20 > 0 else 1, 2),
        'trend': volume_trend,
        'spike': volume_spike,
        'price_correlation': correlation
    }


def get_price_action(df) -> dict:
    """Analyze recent price action."""
    closes = df['close']
    opens = df['open']
    highs = df['high']
    lows = df['low']

    # Last 5 days pattern
    last_5 = []
    for i in range(-5, 0):
        o, h, l, c = opens.iloc[i], highs.iloc[i], lows.iloc[i], closes.iloc[i]
        body = c - o
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l

        if body > 0:
            candle_type = 'GREEN'
        elif body < 0:
            candle_type = 'RED'
        else:
            candle_type = 'DOJI'

        last_5.append({
            'type': candle_type,
            'body_pct': round(abs(body) / o * 100, 2) if o > 0 else 0,
            'upper_wick_pct': round(upper_wick / o * 100, 2) if o > 0 else 0,
            'lower_wick_pct': round(lower_wick / o * 100, 2) if o > 0 else 0
        })

    # Trend strength (count of green vs red in last 10 days)
    green_count = sum(1 for i in range(-10, 0) if closes.iloc[i] > opens.iloc[i])

    # Recent momentum
    change_5d = ((closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100) if len(df) >= 6 else 0
    change_10d = ((closes.iloc[-1] - closes.iloc[-11]) / closes.iloc[-11] * 100) if len(df) >= 11 else 0
    change_20d = ((closes.iloc[-1] - closes.iloc[-21]) / closes.iloc[-21] * 100) if len(df) >= 21 else 0

    return {
        'last_5_candles': last_5,
        'green_days_10d': green_count,
        'red_days_10d': 10 - green_count,
        'trend_bias': 'BULLISH' if green_count >= 6 else ('BEARISH' if green_count <= 4 else 'NEUTRAL'),
        'momentum': {
            'change_5d': round(change_5d, 2),
            'change_10d': round(change_10d, 2),
            'change_20d': round(change_20d, 2)
        }
    }


def enrich_symbol(run_dir: Path, symbol: str) -> dict:
    """
    Generate enriched analysis for a specific symbol.

    This does NOT affect the trading decision - only reporting.
    """
    fetcher = get_reliable_fetcher()

    # Load historical data from snapshot (preferred)
    df = _load_snapshot_df(run_dir, symbol)
    if df is None:
        # Fallback to network fetcher for dev only
        result = fetcher.get_historical_data(symbol, days=365)
        if not result.is_valid or len(result.df) < 50:
            return {
                'symbol': symbol,
                'error': 'Insufficient data for enrichment',
                'enriched': False
            }
        df = result.df

    # Get fundamentals
    fund_result = fetcher.get_fundamentals(symbol)
    fundamentals = fund_result.data if fund_result.is_usable else {}

    # Build enriched analysis
    enriched = {
        'symbol': symbol,
        'enriched': True,
        'enriched_at': datetime.now().isoformat(),

        'current_price': round(float(df['close'].iloc[-1]), 2),
        'prev_close': round(float(df['close'].iloc[-2]), 2),
        'change_pct': round(((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100), 2),

        'levels': get_support_resistance(df),
        'volume': get_volume_analysis(df),
        'price_action': get_price_action(df),

        'fundamentals': {
            'market_cap': fundamentals.get('market_cap'),
            'pe_ratio': fundamentals.get('pe_ratio'),
            'pb_ratio': fundamentals.get('pb_ratio'),
            'sector': fundamentals.get('sector'),
            'industry': fundamentals.get('industry'),
            '52_week_high': fundamentals.get('52_week_high'),
            '52_week_low': fundamentals.get('52_week_low'),
            'avg_volume': fundamentals.get('avg_volume'),
            'dividend_yield': fundamentals.get('dividend_yield')
        },

        'context': {
            'data_quality': 'snapshot' if _load_snapshot_df(run_dir, symbol) is not None else getattr(result.quality, 'value', 'unknown'),
            'bars_available': len(df),
            'last_date': df.index[-1].strftime('%Y-%m-%d')
        }
    }

    return enriched


def enrich_report(run_dir: Path) -> None:
    """
    Enrich report for the decided symbol.

    Reads decision.json and generates symbol/<SYMBOL>.json
    """
    decision_path = run_dir / "decision.json"
    decision = load_json(decision_path)

    if decision['action'] == 'NO_TRADE':
        print("No trade decision - skipping enrichment")
        return

    symbol = decision['symbol']
    print(f"Enriching report for {symbol}...")

    # Create symbol directory
    symbol_dir = run_dir / "symbol"
    symbol_dir.mkdir(exist_ok=True)

    # Enrich the main symbol
    enriched = enrich_symbol(run_dir, symbol)

    # Save enriched data
    output_path = symbol_dir / f"{symbol}.json"
    with open(output_path, 'w') as f:
        json.dump(enriched, f, indent=2)

    print(f"  Saved: {output_path}")

    # Also enrich alternatives (top 3)
    alternatives = decision.get('alternatives', [])
    for alt in alternatives[:3]:
        alt_symbol = alt['symbol']
        print(f"  Enriching alternative: {alt_symbol}")
        alt_enriched = enrich_symbol(run_dir, alt_symbol)
        alt_path = symbol_dir / f"{alt_symbol}.json"
        with open(alt_path, 'w') as f:
            json.dump(alt_enriched, f, indent=2)

    print(f"\nEnrichment complete.")
    print(f"  Main: {symbol}")
    print(f"  Alternatives: {[a['symbol'] for a in alternatives[:3]]}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python enrich_report.py <run_dir>")
        print("Example: python enrich_report.py journal/runs/2026-01-17_0830")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    # Check decision.json exists
    if not (run_dir / "decision.json").exists():
        print("Error: decision.json not found. Run make_decision.py first.")
        sys.exit(1)

    enrich_report(run_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
