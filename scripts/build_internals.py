#!/usr/bin/env python3
"""
Stage A3: Build Market Internals (Breadth)

Computes market breadth/internals from the pinned OHLCV snapshot written in Stage A.
This is designed to restore "institutional morning checklist" quality without
reintroducing discretionary LLM decisions.

Inputs (from run_dir):
- data_health.json
- data/daily/*.csv

Outputs (to run_dir):
- internals.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import get_nifty100_symbols


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _load_snapshot_df(run_dir: Path, symbol: str) -> Optional[pd.DataFrame]:
    path = run_dir / "data" / "daily" / f"{symbol}.csv"
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        expected = {"open", "high", "low", "close", "volume"}
        if not expected.issubset(set(df.columns)):
            return None
        df = df[["open", "high", "low", "close", "volume"]].sort_index()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return None


def _pct_return(close: pd.Series, periods: int) -> float:
    if close is None or len(close) <= periods:
        return 0.0
    prior = float(close.iloc[-(periods + 1)])
    latest = float(close.iloc[-1])
    if prior <= 0:
        return 0.0
    return ((latest / prior) - 1) * 100


def _ema_last(close: pd.Series, span: int) -> float:
    if close is None or len(close) < span:
        return float("nan")
    return float(close.ewm(span=span).mean().iloc[-1])


def _breadth_state(
    pct_above_ema50: float,
    adv_dec_ratio: float,
    new_highs_20d: int,
    new_lows_20d: int,
) -> str:
    """
    Conservative breadth regime classification.
    """
    if pct_above_ema50 >= 60 and adv_dec_ratio >= 1.2 and new_highs_20d >= new_lows_20d:
        return "RISK_ON"
    if pct_above_ema50 <= 40 and adv_dec_ratio <= 0.8 and new_lows_20d > new_highs_20d:
        return "RISK_OFF"
    return "NEUTRAL"


def _breadth_multiplier(state: str) -> float:
    return {"RISK_ON": 1.0, "NEUTRAL": 0.8, "RISK_OFF": 0.5}.get(state, 0.8)


def build_internals(run_dir: Path) -> dict:
    config_path = PROJECT_ROOT / "config" / "trading_config.json"
    config = _load_json(config_path)
    data_health = _load_json(run_dir / "data_health.json")

    tech = config.get("technical_params", {}) or {}
    ema20_span = int(tech.get("ema_fast", 20))
    ema50_span = int(tech.get("ema_medium", 50))
    ema200_span = int(tech.get("ema_slow", 200))

    symbols = get_nifty100_symbols() or []
    if not symbols:
        stocks_file = PROJECT_ROOT / "stocks.json"
        if stocks_file.exists():
            with open(stocks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            symbols = [s["symbol"] for s in data.get("nifty_100", [])]

    asof_date = data_health.get("last_trading_day")

    per_symbol: Dict[str, Dict[str, Any]] = {}
    daily_returns = {}

    above_ema20 = 0
    above_ema50 = 0
    above_ema200 = 0
    new_highs_20d = 0
    new_lows_20d = 0
    new_highs_52w = 0
    new_lows_52w = 0

    adv = 0
    dec = 0
    flat = 0

    included = 0

    for symbol in symbols:
        df = _load_snapshot_df(run_dir, symbol)
        if df is None or len(df) < max(ema200_span, 60):
            continue

        last_date = df.index[-1].strftime("%Y-%m-%d")
        if asof_date and last_date != asof_date:
            # Stale vs consensus; exclude from breadth so internals match the run
            continue

        close = df["close"].astype(float)
        if len(close) < 2:
            continue

        ret_1d = (float(close.iloc[-1]) / float(close.iloc[-2]) - 1.0) * 100.0
        ret_5d = _pct_return(close, 5)
        ret_20d = _pct_return(close, 20)

        ema20 = _ema_last(close, ema20_span)
        ema50 = _ema_last(close, ema50_span)
        ema200 = _ema_last(close, ema200_span)

        px = float(close.iloc[-1])
        is_above_ema20 = bool(px > ema20) if not np.isnan(ema20) else False
        is_above_ema50 = bool(px > ema50) if not np.isnan(ema50) else False
        is_above_ema200 = bool(px > ema200) if not np.isnan(ema200) else False

        look20 = close.tail(20)
        look252 = close.tail(252) if len(close) >= 252 else close
        is_20d_high = bool(px >= float(look20.max())) if len(look20) else False
        is_20d_low = bool(px <= float(look20.min())) if len(look20) else False
        is_52w_high = bool(px >= float(look252.max())) if len(look252) else False
        is_52w_low = bool(px <= float(look252.min())) if len(look252) else False

        if ret_1d > 0:
            adv += 1
        elif ret_1d < 0:
            dec += 1
        else:
            flat += 1

        above_ema20 += 1 if is_above_ema20 else 0
        above_ema50 += 1 if is_above_ema50 else 0
        above_ema200 += 1 if is_above_ema200 else 0

        new_highs_20d += 1 if is_20d_high else 0
        new_lows_20d += 1 if is_20d_low else 0
        new_highs_52w += 1 if is_52w_high else 0
        new_lows_52w += 1 if is_52w_low else 0

        included += 1
        per_symbol[symbol] = {
            "last_date": last_date,
            "ret_1d": round(ret_1d, 3),
            "ret_5d": round(ret_5d, 3),
            "ret_20d": round(ret_20d, 3),
            "above_ema20": is_above_ema20,
            "above_ema50": is_above_ema50,
            "above_ema200": is_above_ema200,
            "new_high_20d": is_20d_high,
            "new_low_20d": is_20d_low,
            "new_high_52w": is_52w_high,
            "new_low_52w": is_52w_low,
        }

        # Collect returns series for last 15 sessions for "up days last 10" metric
        r = close.pct_change() * 100.0
        daily_returns[symbol] = r.tail(15)

    adv_dec_ratio = (adv / max(1, dec)) if included else 0.0
    pct_ema20 = (above_ema20 / included) * 100 if included else 0.0
    pct_ema50 = (above_ema50 / included) * 100 if included else 0.0
    pct_ema200 = (above_ema200 / included) * 100 if included else 0.0

    # Up days in the last 10 sessions based on median cross-sectional return
    up_days_10 = None
    down_days_10 = None
    breadth_series = None
    if daily_returns:
        df_ret = pd.DataFrame(daily_returns).sort_index()
        median_ret = df_ret.median(axis=1, skipna=True)
        last10 = median_ret.dropna().tail(10)
        if len(last10) > 0:
            up_days_10 = int((last10 > 0).sum())
            down_days_10 = int((last10 < 0).sum())
            breadth_series = {idx.strftime("%Y-%m-%d"): round(float(val), 3) for idx, val in last10.items()}

    state = _breadth_state(pct_ema50, adv_dec_ratio, new_highs_20d, new_lows_20d)
    multiplier = _breadth_multiplier(state)

    notes: List[str] = []
    notes.append(f"Adv/Dec: {adv}/{dec} (ratio {adv_dec_ratio:.2f})")
    notes.append(f"% above EMA50: {pct_ema50:.0f}%")
    notes.append(f"20d highs/lows: {new_highs_20d}/{new_lows_20d}")
    if up_days_10 is not None:
        notes.append(f"Up days (median return) last 10: {up_days_10}/10")

    out = {
        "build_timestamp": datetime.now().isoformat(),
        "asof_date": asof_date,
        "universe": {
            "symbols_total": len(symbols),
            "symbols_included": included,
        },
        "breadth": {
            "advancers": adv,
            "decliners": dec,
            "unchanged": flat,
            "adv_dec_ratio": round(float(adv_dec_ratio), 3),
            "pct_above_ema20": round(float(pct_ema20), 2),
            "pct_above_ema50": round(float(pct_ema50), 2),
            "pct_above_ema200": round(float(pct_ema200), 2),
            "new_highs_20d": int(new_highs_20d),
            "new_lows_20d": int(new_lows_20d),
            "new_highs_52w": int(new_highs_52w),
            "new_lows_52w": int(new_lows_52w),
            "up_days_last_10": up_days_10,
            "down_days_last_10": down_days_10,
            "median_return_last_10": breadth_series,
            "state": state,
            "multiplier": round(float(multiplier), 3),
            "notes": notes,
        },
        # Keep per-symbol details for audit/debug; can be dropped later if size becomes an issue.
        "symbols": per_symbol,
    }

    out_path = run_dir / "internals.json"
    _write_json(out_path, out)
    print(f"Wrote: {out_path}")
    print(f"Breadth: {state} (multiplier {multiplier:.2f}) | %>EMA50: {pct_ema50:.0f}% | Adv/Dec: {adv}/{dec}")
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python build_internals.py <run_dir>")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    if not (run_dir / "data_health.json").exists():
        print("Error: data_health.json not found. Run prepare_data.py first.")
        sys.exit(1)

    build_internals(run_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()

