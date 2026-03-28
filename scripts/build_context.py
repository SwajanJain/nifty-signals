#!/usr/bin/env python3
"""
Stage B: Build Market Context

Analyzes market regime, global context, and sector strength.
Outputs: market_context.json

HARD KILL SWITCH: If regime == CRASH or VIX > max → should_trade = false
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.reliable_fetcher import get_reliable_fetcher


def load_config() -> dict:
    """Load trading configuration."""
    config_path = PROJECT_ROOT / "config" / "trading_config.json"
    with open(config_path) as f:
        return json.load(f)


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def calculate_regime(nifty_data: dict, vix: float) -> str:
    """
    Calculate market regime based on Nifty trend and VIX.

    Returns:
        regime_name (str)
    """
    if nifty_data is None:
        return "NEUTRAL"

    nifty_change = nifty_data.get('change_pct', 0)
    nifty_above_ema20 = nifty_data.get('above_ema20', True)
    nifty_above_ema50 = nifty_data.get('above_ema50', True)
    nifty_above_ema200 = nifty_data.get('above_ema200', True)

    # Determine regime
    if vix > 35:
        regime = "CRASH"
    elif vix > 25 and not nifty_above_ema50:
        regime = "STRONG_BEAR"
    elif not nifty_above_ema200:
        regime = "BEAR"
    elif nifty_above_ema200 and not nifty_above_ema50:
        regime = "NEUTRAL"
    elif nifty_above_ema50 and nifty_above_ema20:
        if nifty_change > 1:
            regime = "STRONG_BULL"
        else:
            regime = "BULL"
    else:
        regime = "NEUTRAL"

    return regime


def get_sector_data(fetcher) -> dict:
    """Get sector ETF/index data for relative strength."""
    # Sector proxies using Nifty sector indices
    sector_symbols = {
        'NIFTY_IT': '^CNXIT',
        'NIFTY_BANK': '^NSEBANK',
        'NIFTY_PHARMA': '^CNXPHARMA',
        'NIFTY_AUTO': '^CNXAUTO',
        'NIFTY_METAL': '^CNXMETAL',
        'NIFTY_REALTY': '^CNXREALTY',
        'NIFTY_FMCG': '^CNXFMCG',
        'NIFTY_ENERGY': '^CNXENERGY',
    }

    sector_performance = {}

    for sector_name, symbol in sector_symbols.items():
        try:
            data = fetcher.yfinance.get_global_index(symbol)
            if data.is_valid and len(data.df) >= 2:
                current = float(data.df['close'].iloc[-1])
                prev = float(data.df['close'].iloc[-2])
                change_pct = ((current - prev) / prev) * 100

                # Calculate 5-day momentum
                if len(data.df) >= 6:
                    five_days_ago = float(data.df['close'].iloc[-6])
                    momentum_5d = ((current - five_days_ago) / five_days_ago) * 100
                else:
                    momentum_5d = change_pct

                sector_performance[sector_name] = {
                    'change_1d': round(change_pct, 2),
                    'momentum_5d': round(momentum_5d, 2),
                    'score': round(momentum_5d * 0.7 + change_pct * 0.3, 2)
                }
        except Exception:
            pass

    # Rank sectors by score
    if sector_performance:
        sorted_sectors = sorted(
            sector_performance.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        for rank, (sector, data) in enumerate(sorted_sectors, 1):
            sector_performance[sector]['rank'] = rank

    return sector_performance


def build_context(run_dir: Path) -> dict:
    """
    Build market context including regime, VIX, and sector strength.

    Returns:
        market_context dict with should_trade flag
    """
    config = load_config()
    fetcher = get_reliable_fetcher()

    # Optional pinned artifacts from earlier stages
    internals = _load_json(run_dir / "internals.json") or {}
    sector_strength = _load_json(run_dir / "sector_strength.json") or {}

    # Get global context
    global_result = fetcher.get_global_context()
    global_data = global_result.data

    vix = global_data.get('vix')
    sp500_change = global_data.get('sp500_change')
    nifty_close = global_data.get('nifty_close')
    nifty_change = global_data.get('nifty_change')

    # Get Nifty 50 data for regime calculation
    nifty_data = None
    try:
        nifty_result = fetcher.yfinance.get_global_index('^NSEI', period='2y')
        if nifty_result.is_valid and len(nifty_result.df) >= 200:
            df = nifty_result.df
            current = float(df['close'].iloc[-1])
            ema20 = df['close'].ewm(span=20).mean().iloc[-1]
            ema50 = df['close'].ewm(span=50).mean().iloc[-1]
            ema200 = df['close'].ewm(span=200).mean().iloc[-1]

            nifty_data = {
                'close': current,
                'change_pct': nifty_change if nifty_change is not None else 0,
                'above_ema20': bool(current > ema20),
                'above_ema50': bool(current > ema50),
                'above_ema200': bool(current > ema200),
                'ema20': round(float(ema20), 2),
                'ema50': round(float(ema50), 2),
                'ema200': round(float(ema200), 2)
            }
    except Exception as e:
        print(f"Warning: Could not get Nifty data: {e}")

    # Calculate regime (fail-closed if key context is missing)
    context_ok = (vix is not None) and (nifty_data is not None)
    if context_ok:
        regime = calculate_regime(nifty_data, float(vix))
        regime_multiplier = float(config['regime_multipliers'].get(regime, 0.5))
    else:
        regime = "UNKNOWN"
        regime_multiplier = 0.0

    # Breadth / internals multiplier (pinned from snapshots; fail-conservative if missing)
    breadth = (internals.get("breadth") or {}) if isinstance(internals, dict) else {}
    breadth_state = breadth.get("state") or "UNKNOWN"
    breadth_multiplier = float(breadth.get("multiplier", 0.8 if breadth_state == "UNKNOWN" else 0.8))

    # Sector strength data (prefer snapshot-based artifact; fallback to live index proxies)
    sector_ranks = {}
    sector_rows = []
    avoid_sectors = []
    if isinstance(sector_strength, dict) and sector_strength.get("sectors"):
        sector_rows = sector_strength.get("sectors") or []
        sector_ranks = {s.get("sector"): int(s.get("rank")) for s in sector_rows if s.get("sector")}
        avoid_sectors = (sector_strength.get("summary") or {}).get("avoid_sectors") or []
    else:
        sector_performance = get_sector_data(fetcher)
        sector_ranks = {
            sector: data['rank']
            for sector, data in sector_performance.items()
            if 'rank' in data
        }
        # Convert the dict into list rows for consistent output shape
        sector_rows = [
            {
                "sector": sector.replace("NIFTY_", "").title(),
                "rank": data.get("rank"),
                "weekly_return": data.get("momentum_5d"),
                "monthly_return": None,
                "rs_score": None,
                "strength": None,
                "score": data.get("score"),
            }
            for sector, data in sector_performance.items()
        ]
        sector_rows.sort(key=lambda r: r.get("rank", 999))

    # Determine should_trade based on kill switches
    kill_switches = config['kill_switches']
    should_trade = True
    kill_reason = None

    if vix is None:
        should_trade = False
        kill_reason = "VIX unavailable (fail-closed)"
    elif nifty_data is None:
        should_trade = False
        kill_reason = "Nifty regime data unavailable (fail-closed)"
    elif float(vix) > kill_switches['vix_max']:
        should_trade = False
        kill_reason = f"VIX ({float(vix):.1f}) exceeds maximum ({kill_switches['vix_max']})"
    elif regime in kill_switches['regime_no_trade']:
        should_trade = False
        kill_reason = f"Regime is {regime} - no trading allowed"
    elif regime_multiplier == 0:
        should_trade = False
        kill_reason = f"Regime multiplier is 0 for {regime}"

    # Additional breadth-aware safety (do not overtrade in risk-off internals)
    if should_trade and breadth_state == "RISK_OFF":
        # Conservative: if internals are risk-off and Nifty isn't clearly above EMA200, stand down.
        nifty_above_200 = bool((nifty_data or {}).get("above_ema200", False))
        if (vix is not None and float(vix) >= 20) or (not nifty_above_200):
            should_trade = False
            kill_reason = "Breadth is RISK_OFF (stand down)"

    # Determine market sentiment
    if vix is None or nifty_change is None:
        sentiment = "UNKNOWN"
    elif float(vix) < 15 and nifty_change > 0.5:
        sentiment = "RISK_ON"
    elif float(vix) > 25:
        sentiment = "FEAR"
    elif nifty_change < -1:
        sentiment = "BEARISH"
    elif nifty_change > 1:
        sentiment = "BULLISH"
    else:
        sentiment = "NEUTRAL"

    market_context = {
        'build_timestamp': datetime.now().isoformat(),
        'regime': regime,
        'regime_multiplier': regime_multiplier,
        'breadth_multiplier': round(float(breadth_multiplier), 3),
        'position_size_multiplier': round(float(regime_multiplier * breadth_multiplier), 3),
        'should_trade': should_trade,
        'kill_reason': kill_reason,
        'vix': round(float(vix), 2) if vix is not None else None,
        'vix_level': 'UNKNOWN' if vix is None else ('LOW' if float(vix) < 15 else ('HIGH' if float(vix) > 25 else 'NORMAL')),
        'sentiment': sentiment,
        'global': {
            'sp500_change': round(float(sp500_change), 2) if sp500_change is not None else None,
            'dxy': global_data.get('dxy'),
            'global_sentiment': global_data.get('global_sentiment', 'UNKNOWN'),
            'global_context_quality': getattr(global_result.quality, 'value', None)
        },
        'nifty': nifty_data,
        'breadth': breadth if breadth else None,
        'sectors': sector_rows,
        'avoid_sectors': avoid_sectors,
        'sector_ranks': sector_ranks,
        'config_used': {
            'vix_max': kill_switches['vix_max'],
            'regime_no_trade': kill_switches['regime_no_trade']
        }
    }

    # Save to run directory
    output_path = run_dir / "market_context.json"
    with open(output_path, 'w') as f:
        json.dump(market_context, f, indent=2)

    print(f"\nMarket Context Summary:")
    print(f"  Regime: {regime} (multiplier: {regime_multiplier})")
    vix_str = f"{float(vix):.1f}" if vix is not None else "N/A"
    print(f"  VIX: {vix_str} ({market_context['vix_level']})")
    print(f"  Sentiment: {sentiment}")
    print(f"  Should Trade: {should_trade}")

    if not should_trade:
        print(f"\n  HARD STOP: {kill_reason}")

    if sector_rows:
        print(f"\n  Top Sectors:")
        for s in sector_rows[:3]:
            if isinstance(s, dict):
                print(f"    {s.get('rank', '-')}. {s.get('sector')}: RS {s.get('rs_score')} | 1M {s.get('monthly_return')}")

    return market_context


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python build_context.py <run_dir>")
        print("Example: python build_context.py journal/runs/2026-01-17_0830")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    result = build_context(run_dir)

    # Exit with error code if should not trade
    if not result['should_trade']:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
