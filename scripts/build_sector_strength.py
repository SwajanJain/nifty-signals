#!/usr/bin/env python3
"""
Stage A4: Build Sector Strength (RS / Rotation) from Snapshots

Computes sector relative strength using ONLY the pinned OHLCV snapshots in the run folder.
This avoids per-run live sector index fetching and produces an auditable artifact that
Stage B/C/D can use for better signal quality.

Inputs (from run_dir):
- data_health.json
- data/daily/*.csv

Outputs (to run_dir):
- sector_strength.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import numpy as np
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import get_nifty100_symbols
from indicators.sector_strength import get_sector_for_stock


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


def _safe_rs(sector_ret: float, bench_ret: float) -> float:
    """RS score as ratio of (1+ret) vs benchmark (1+ret)."""
    denom = 1.0 + (bench_ret / 100.0)
    if denom <= 0:
        return 1.0
    return (1.0 + (sector_ret / 100.0)) / denom


def _strength_bucket(rs_score: float, mom_excess: float, pct_above_ema50: float) -> str:
    """
    Conservative bucket akin to the old report:
    - STRONG when RS clearly > 1 and participation is broad.
    """
    if rs_score >= 1.05 and mom_excess >= 2 and pct_above_ema50 >= 60:
        return "STRONG"
    if rs_score >= 1.01 and mom_excess >= 0 and pct_above_ema50 >= 50:
        return "MODERATE"
    if rs_score >= 0.98:
        return "WEAK"
    return "VERY_WEAK"


def build_sector_strength(run_dir: Path) -> dict:
    config = _load_json(PROJECT_ROOT / "config" / "trading_config.json")
    data_health = _load_json(run_dir / "data_health.json")
    asof_date = data_health.get("last_trading_day")

    tech = config.get("technical_params", {}) or {}
    ema50_span = int(tech.get("ema_medium", 50))

    symbols = get_nifty100_symbols() or []
    if not symbols:
        stocks_file = PROJECT_ROOT / "stocks.json"
        if stocks_file.exists():
            with open(stocks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            symbols = [s["symbol"] for s in data.get("nifty_100", [])]

    # Per-symbol metrics
    stock_metrics: Dict[str, Dict[str, Any]] = {}
    included: List[str] = []

    for symbol in symbols:
        df = _load_snapshot_df(run_dir, symbol)
        if df is None or len(df) < 80:
            continue

        last_date = df.index[-1].strftime("%Y-%m-%d")
        if asof_date and last_date != asof_date:
            continue

        close = df["close"].astype(float)
        px = float(close.iloc[-1])
        ret_5d = _pct_return(close, 5)
        ret_20d = _pct_return(close, 20)
        ret_60d = _pct_return(close, 60)

        ema50 = _ema_last(close, ema50_span)
        above_50 = bool(px > ema50) if not np.isnan(ema50) else False

        sector = get_sector_for_stock(symbol) or "Unknown"

        stock_metrics[symbol] = {
            "sector": sector,
            "price": round(px, 2),
            "last_date": last_date,
            "ret_5d": round(ret_5d, 3),
            "ret_20d": round(ret_20d, 3),
            "ret_60d": round(ret_60d, 3),
            "above_ema50": above_50,
        }
        included.append(symbol)

    # Benchmark: equal-weight universe 20d return (median is robust but less PM-like)
    universe_20d = float(np.mean([m["ret_20d"] for m in stock_metrics.values()])) if stock_metrics else 0.0
    universe_5d = float(np.mean([m["ret_5d"] for m in stock_metrics.values()])) if stock_metrics else 0.0

    # Aggregate by sector
    sectors: Dict[str, Dict[str, Any]] = {}
    for symbol, m in stock_metrics.items():
        sector = m["sector"]
        sectors.setdefault(sector, {"symbols": []})
        sectors[sector]["symbols"].append(symbol)

    sector_rows: List[Dict[str, Any]] = []
    for sector, info in sectors.items():
        members = info["symbols"]
        if not members:
            continue

        rets_5 = [stock_metrics[s]["ret_5d"] for s in members]
        rets_20 = [stock_metrics[s]["ret_20d"] for s in members]
        rets_60 = [stock_metrics[s]["ret_60d"] for s in members]
        pct_above_50 = (sum(1 for s in members if stock_metrics[s]["above_ema50"]) / len(members)) * 100

        sector_5d = float(np.mean(rets_5)) if rets_5 else 0.0
        sector_20d = float(np.mean(rets_20)) if rets_20 else 0.0
        sector_60d = float(np.mean(rets_60)) if rets_60 else 0.0

        rs_20d = _safe_rs(sector_20d, universe_20d)
        mom_excess = sector_20d - universe_20d

        # Per-stock RS for ranking within sector
        stock_rank = []
        for s in members:
            rs_stock = _safe_rs(float(stock_metrics[s]["ret_20d"]), universe_20d)
            stock_rank.append((s, rs_stock))
        stock_rank.sort(key=lambda x: x[1], reverse=True)

        top_stocks = [s for s, _ in stock_rank[:3]]
        lagging_stocks = [s for s, _ in stock_rank[-3:]] if len(stock_rank) >= 3 else [s for s, _ in stock_rank]

        strength = _strength_bucket(rs_20d, mom_excess, pct_above_50)

        sector_rows.append(
            {
                "sector": sector,
                "members": len(members),
                "weekly_return": round(sector_5d, 2),
                "monthly_return": round(sector_20d, 2),
                "quarterly_return": round(sector_60d, 2),
                "rs_score": round(float(rs_20d), 3),
                "momentum_excess": round(float(mom_excess), 2),
                "pct_above_ema50": round(float(pct_above_50), 1),
                "strength": strength,
                "top_stocks": top_stocks,
                "lagging_stocks": lagging_stocks,
            }
        )

    sector_rows.sort(key=lambda r: (r["rs_score"], r["monthly_return"]), reverse=True)
    for idx, row in enumerate(sector_rows, 1):
        row["rank"] = idx

    avoid_sectors = [r["sector"] for r in sector_rows if r["strength"] in ("VERY_WEAK",)]

    out = {
        "build_timestamp": datetime.now().isoformat(),
        "asof_date": asof_date,
        "benchmark": {
            "universe_return_5d": round(float(universe_5d), 2),
            "universe_return_20d": round(float(universe_20d), 2),
        },
        "summary": {
            "symbols_total": len(symbols),
            "symbols_included": len(included),
            "sectors_count": len(sector_rows),
            "avoid_sectors": avoid_sectors,
        },
        "sectors": sector_rows,
        # Keep per-symbol mapping for audit/debug
        "symbols": stock_metrics,
    }

    out_path = run_dir / "sector_strength.json"
    _write_json(out_path, out)

    print(f"Wrote: {out_path}")
    if sector_rows:
        top = sector_rows[0]
        print(
            f"Top sector: {top['sector']} (RS {top['rs_score']:.3f}, 1M {top['monthly_return']:+.1f}%)"
        )
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python build_sector_strength.py <run_dir>")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    if not (run_dir / "data_health.json").exists():
        print("Error: data_health.json not found. Run prepare_data.py first.")
        sys.exit(1)

    build_sector_strength(run_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()

