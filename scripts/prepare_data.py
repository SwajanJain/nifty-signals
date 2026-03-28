#!/usr/bin/env python3
"""
Stage A: Data Preparation

Validates data availability and freshness for all symbols.
Outputs: data_health.json

Also snapshots OHLCV locally into the run folder to make downstream
stages network-light and reproducible:
  journal/runs/<run_id>/data/daily/<SYMBOL>.csv

HARD KILL SWITCH: If price data is stale or unavailable → can_proceed = false
"""

import json
import sys
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.reliable_fetcher import get_reliable_fetcher, KNOWN_FAILURES
from config import get_nifty100_symbols


def load_config() -> dict:
    """Load trading configuration."""
    config_path = PROJECT_ROOT / "config" / "trading_config.json"
    with open(config_path) as f:
        return json.load(f)


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    if not filepath.exists():
        return ""
    with open(filepath, 'rb') as f:
        return f"sha256:{hashlib.sha256(f.read()).hexdigest()[:16]}"


def _snapshot_path(run_dir: Path, symbol: str) -> Path:
    return run_dir / "data" / "daily" / f"{symbol}.csv"


def _write_snapshot(run_dir: Path, symbol: str, df) -> Optional[Path]:
    """
    Persist OHLCV DataFrame for later stages.

    Returns the written path on success, else None.
    """
    try:
        target = _snapshot_path(run_dir, symbol)
        target.parent.mkdir(parents=True, exist_ok=True)

        out = df.copy()
        if hasattr(out.index, "tz") and getattr(out.index, "tz", None) is not None:
            out.index = out.index.tz_localize(None)

        out = out.sort_index()
        # Keep only the expected columns
        out = out[["open", "high", "low", "close", "volume"]]
        out.to_csv(target)
        return target
    except Exception:
        return None


def prepare_data(run_dir: Path) -> dict:
    """
    Prepare and validate data for all symbols.

    Returns:
        data_health dict with status and can_proceed flag
    """
    config = load_config()
    fetcher = get_reliable_fetcher()

    # Get all symbols
    symbols = get_nifty100_symbols()
    if not symbols:
        # Fallback to reading stocks.json directly
        stocks_file = PROJECT_ROOT / "stocks.json"
        if stocks_file.exists():
            with open(stocks_file) as f:
                data = json.load(f)
            symbols = [s['symbol'] for s in data.get('nifty_100', [])]

    # Track results
    symbols_available = []
    symbols_failed = []
    symbols_degraded = []
    price_data_info = {}
    snapshot_written = []
    snapshot_failed = []

    min_bars = config['data_quality']['min_bars_required']
    max_stale = config['data_quality']['max_stale_days']

    print(f"Checking data for {len(symbols)} symbols...")

    for symbol in symbols:
        # Skip known failures
        if symbol in KNOWN_FAILURES:
            symbols_failed.append(symbol)
            price_data_info[symbol] = {
                'status': 'known_failure',
                'bars': 0,
                'reason': 'No yfinance workaround available'
            }
            continue

        try:
            result = fetcher.get_historical_data(symbol, days=365)

            if not result.is_valid or len(result.df) == 0:
                symbols_failed.append(symbol)
                price_data_info[symbol] = {
                    'status': 'failed',
                    'bars': 0,
                    'reason': 'No data returned'
                }
                continue

            snapshot_path = _write_snapshot(run_dir, symbol, result.df)
            if snapshot_path:
                snapshot_written.append(symbol)
            else:
                snapshot_failed.append(symbol)

            # Check freshness
            last_date = result.df.index[-1]
            if hasattr(last_date, 'tz') and last_date.tz is not None:
                last_date = last_date.tz_localize(None)

            days_old = (datetime.now() - last_date.to_pydatetime()).days

            # Account for weekends
            weekday = datetime.now().weekday()
            if weekday == 0:  # Monday
                days_old = max(0, days_old - 2)
            elif weekday == 6:  # Sunday
                days_old = max(0, days_old - 1)

            bars = len(result.df)

            if days_old > max_stale:
                symbols_degraded.append(symbol)
                status = 'stale'
            elif bars < min_bars:
                symbols_degraded.append(symbol)
                status = 'insufficient_history'
            else:
                symbols_available.append(symbol)
                status = 'ok'

            price_data_info[symbol] = {
                'status': status,
                'bars': bars,
                'last_date': last_date.strftime('%Y-%m-%d'),
                'days_old': days_old,
                'quality': result.quality.value
            }

        except Exception as e:
            symbols_failed.append(symbol)
            price_data_info[symbol] = {
                'status': 'error',
                'bars': 0,
                'reason': str(e)
            }
            snapshot_failed.append(symbol)

    # Determine overall health
    total = len(symbols)
    available = len(symbols_available)
    failed = len(symbols_failed)
    degraded = len(symbols_degraded)

    # Calculate data quality score
    quality_score = (available / total) * 100 if total > 0 else 0

    # Determine if we can proceed
    # HARD KILL SWITCH: If less than 80% of data is available, stop
    can_proceed = quality_score >= 80 and available >= 50

    if not can_proceed:
        kill_reason = f"Data quality too low: {quality_score:.1f}% available ({available}/{total})"
    else:
        kill_reason = None

    # Get consensus "as-of" trading day (mode of last_date across available symbols)
    last_trading_day = None
    last_dates = [
        info.get("last_date")
        for sym, info in price_data_info.items()
        if sym in symbols_available and info.get("last_date")
    ]
    asof_date_counts = Counter(last_dates) if last_dates else Counter()
    if asof_date_counts:
        last_trading_day = asof_date_counts.most_common(1)[0][0]

    data_health = {
        'run_timestamp': datetime.now().isoformat(),
        'last_trading_day': last_trading_day,
        'asof_date_counts': dict(asof_date_counts.most_common(5)) if asof_date_counts else {},
        'total_symbols': total,
        'symbols_available': available,
        'symbols_degraded': degraded,
        'symbols_failed': failed,
        'quality_score': round(quality_score, 2),
        'can_proceed': can_proceed,
        'kill_reason': kill_reason,
        'failed_symbols': symbols_failed,
        'degraded_symbols': symbols_degraded,
        'snapshot': {
            'daily_dir': str((run_dir / "data" / "daily").resolve()),
            'written': len(snapshot_written),
            'write_failed': len(snapshot_failed),
            'failed_symbols': snapshot_failed[:50],
        },
        'config_used': {
            'min_bars_required': min_bars,
            'max_stale_days': max_stale
        }
    }

    # Save to run directory
    output_path = run_dir / "data_health.json"
    with open(output_path, 'w') as f:
        json.dump(data_health, f, indent=2)

    print(f"\nData Health Summary:")
    print(f"  Available: {available}/{total} ({quality_score:.1f}%)")
    print(f"  Degraded: {degraded}")
    print(f"  Failed: {failed}")
    print(f"  Can Proceed: {can_proceed}")

    if not can_proceed:
        print(f"\n  HARD STOP: {kill_reason}")

    return data_health


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python prepare_data.py <run_dir>")
        print("Example: python prepare_data.py journal/runs/2026-01-17_0830")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    run_dir.mkdir(parents=True, exist_ok=True)

    result = prepare_data(run_dir)

    # Exit with error code if cannot proceed
    if not result['can_proceed']:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
