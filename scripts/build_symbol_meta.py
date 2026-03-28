#!/usr/bin/env python3
"""
Stage A2: Build Symbol Meta (Pinned)

Fetch and pin slow-moving, non-OHLCV context used for PM-grade gating:
- Earnings proximity (event risk)
- Basic fundamentals quality grade (risk multiplier)

Why a separate stage?
- Stage D (decision) must remain network-free and deterministic.
- This stage may be slow and network-heavy; output is pinned per run.

Outputs (in run_dir):
- symbol_meta.json

Also maintains a local cache (best-effort, to reduce repeated calls):
- .cache/symbol_meta/<SYMBOL>.json
"""

import json
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import get_nifty100_symbols
from data.reliable_fetcher import get_yfinance_symbol, KNOWN_FAILURES


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def _parse_run_datetime(data_health: dict) -> datetime:
    ts = data_health.get("run_timestamp")
    if ts:
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            pass
    return datetime.now()


def _cache_dir() -> Path:
    d = PROJECT_ROOT / ".cache" / "symbol_meta"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(symbol: str) -> Path:
    return _cache_dir() / f"{symbol}.json"


def _is_cache_fresh(payload: dict, max_age_days: int) -> bool:
    fetched_at = payload.get("fetched_at")
    if not fetched_at:
        return False
    try:
        dt = datetime.fromisoformat(fetched_at)
    except Exception:
        return False
    return (datetime.now() - dt) <= timedelta(days=max_age_days)


def _extract_next_earnings_date(ticker: yf.Ticker) -> Optional[date]:
    """
    Best-effort extraction from yfinance.
    Returns a date or None if unavailable.
    """
    # 1) calendar (varies wildly by ticker)
    try:
        cal = ticker.calendar
        if isinstance(cal, pd.DataFrame) and not cal.empty:
            # common shape: index contains "Earnings Date" and value may be Timestamp or list-like
            for key in ("Earnings Date", "EarningsDate", "Earnings"):
                if key in cal.index:
                    row = cal.loc[key]
                    # first non-null cell
                    for v in row.values:
                        if pd.isna(v):
                            continue
                        if isinstance(v, (pd.Timestamp, datetime)):
                            return pd.Timestamp(v).date()
                        if isinstance(v, (list, tuple)) and v:
                            vv = v[0]
                            if isinstance(vv, (pd.Timestamp, datetime)):
                                return pd.Timestamp(vv).date()
            # some calendars store keys as columns instead
            for col in cal.columns:
                if "earn" in str(col).lower():
                    series = cal[col].dropna()
                    if len(series) > 0:
                        v = series.iloc[0]
                        if isinstance(v, (pd.Timestamp, datetime)):
                            return pd.Timestamp(v).date()
    except Exception:
        pass

    # 2) earnings dates API (can be rate-limited / missing)
    try:
        df = ticker.get_earnings_dates(limit=8)
        if isinstance(df, pd.DataFrame) and not df.empty:
            idx = df.index
            if isinstance(idx, pd.DatetimeIndex) and len(idx) > 0:
                # pick the first date >= today (else the latest)
                today = datetime.now().date()
                future = [d.date() for d in idx if d.date() >= today]
                if future:
                    return future[0]
                return idx[-1].date()
    except Exception:
        pass

    return None


def _score_fundamentals(info: Dict[str, Any], thresholds: dict) -> Tuple[str, float, Dict[str, Any]]:
    """
    Conservative fundamentals grading from yfinance info.
    Returns: (grade, multiplier, details)
    """
    # Pull values (many tickers will have missing fields)
    roe = info.get("returnOnEquity")
    debt_to_equity = info.get("debtToEquity")
    free_cashflow = info.get("freeCashflow")
    profit_margins = info.get("profitMargins")

    red = []
    green = []

    # ROE (usually ratio like 0.12)
    if isinstance(roe, (int, float)):
        if roe >= float(thresholds.get("roe_good", 0.10)):
            green.append(f"ROE {roe:.2f} >= {thresholds.get('roe_good', 0.10)}")
        elif roe <= float(thresholds.get("roe_bad", 0.05)):
            red.append(f"ROE {roe:.2f} <= {thresholds.get('roe_bad', 0.05)}")

    # Debt/Equity (often reported as percentage; treat > 200 ~ 2.0x as high)
    if isinstance(debt_to_equity, (int, float)):
        if debt_to_equity <= float(thresholds.get("de_ratio_good", 100.0)):
            green.append(f"D/E {debt_to_equity:.0f} <= {thresholds.get('de_ratio_good', 100.0)}")
        elif debt_to_equity >= float(thresholds.get("de_ratio_bad", 250.0)):
            red.append(f"D/E {debt_to_equity:.0f} >= {thresholds.get('de_ratio_bad', 250.0)}")

    # Profit margins (ratio like 0.12)
    if isinstance(profit_margins, (int, float)):
        if profit_margins >= float(thresholds.get("margin_good", 0.08)):
            green.append(f"Margins {profit_margins:.2f} >= {thresholds.get('margin_good', 0.08)}")
        elif profit_margins <= float(thresholds.get("margin_bad", 0.03)):
            red.append(f"Margins {profit_margins:.2f} <= {thresholds.get('margin_bad', 0.03)}")

    # Free cashflow (absolute INR; negative is a red flag)
    if isinstance(free_cashflow, (int, float)):
        if free_cashflow > 0:
            green.append("Free cashflow positive")
        else:
            red.append("Free cashflow negative")

    # Grade mapping (conservative)
    if len(red) >= 2:
        grade = "D"
    elif len(red) == 1:
        grade = "C"
    elif len(green) >= 2:
        grade = "A"
    else:
        grade = "B" if len(green) >= 1 else "C"

    return grade, 0.0, {"green": green, "red": red}


def _event_multiplier(days_to: Optional[int], cfg: dict) -> Tuple[str, float, str]:
    """
    Earnings proximity rule:
    - within blackout_days: BLOCK (0.0)
    - within reduce_days: REDUCE (0.5)
    - within caution_days: CAUTION (0.7)
    - unknown: UNKNOWN (unknown multiplier)
    - else: CLEAR (1.0)
    """
    blackout = int(cfg.get("earnings_blackout_days", 3))
    reduce_days = int(cfg.get("earnings_reduce_days", 7))
    caution_days = int(cfg.get("earnings_caution_days", 14))
    unknown_mult = float(cfg.get("unknown_earnings_multiplier", 0.7))

    if days_to is None:
        return "UNKNOWN", unknown_mult, "Earnings date unavailable"
    if days_to <= blackout:
        return "BLOCK", 0.0, f"Earnings within {blackout} days"
    if days_to <= reduce_days:
        return "REDUCE", 0.5, f"Earnings within {reduce_days} days"
    if days_to <= caution_days:
        return "CAUTION", 0.7, f"Earnings within {caution_days} days"
    return "CLEAR", 1.0, "No near-term earnings risk detected"


def build_symbol_meta(run_dir: Path) -> dict:
    config = _load_json(PROJECT_ROOT / "config" / "trading_config.json")
    data_health = _load_json(run_dir / "data_health.json")
    run_dt = _parse_run_datetime(data_health)
    run_day = run_dt.date()

    meta_cfg = config.get("symbol_meta", {}) or {}
    cache_days = int(meta_cfg.get("cache_max_age_days", 7))

    fundamentals_cfg = config.get("fundamentals", {}) or {}
    fundamentals_enabled = bool(fundamentals_cfg.get("enabled", True))
    fundamentals_thresholds = fundamentals_cfg.get("thresholds", {}) or {}
    fundamentals_unknown_mult = float(fundamentals_cfg.get("unknown_multiplier", 0.8))
    fundamentals_grade_mult = fundamentals_cfg.get("grade_multipliers", {}) or {
        "A": 1.0,
        "B": 0.9,
        "C": 0.7,
        "D": 0.0,
    }

    event_cfg = config.get("event_risk", {}) or {}

    symbols = get_nifty100_symbols() or []
    if not symbols:
        stocks_file = PROJECT_ROOT / "stocks.json"
        if stocks_file.exists():
            with open(stocks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            symbols = [s["symbol"] for s in data.get("nifty_100", [])]

    out: Dict[str, Any] = {
        "run_date": run_day.isoformat(),
        "symbols": {},
        "summary": {
            "total": len(symbols),
            "fetched": 0,
            "cached": 0,
            "failed": 0,
            "earnings_block": 0,
            "fundamentals_d": 0,
        },
    }

    print(f"Building symbol meta for {len(symbols)} symbols (cache max age: {cache_days} days)...")

    for symbol in symbols:
        if symbol in KNOWN_FAILURES:
            out["symbols"][symbol] = {
                "symbol": symbol,
                "yf_ticker": None,
                "status": "KNOWN_FAILURE",
                "earnings": {"status": "UNKNOWN", "multiplier": 0.7, "reason": "Known yfinance failure"},
                "fundamentals": {"status": "UNKNOWN", "grade": None, "multiplier": fundamentals_unknown_mult},
            }
            out["summary"]["failed"] += 1
            continue

        cached_payload: Optional[dict] = None
        cache_path = _cache_path(symbol)
        if cache_path.exists():
            try:
                cached_payload = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                cached_payload = None

        if cached_payload and _is_cache_fresh(cached_payload, cache_days):
            payload = cached_payload
            out["summary"]["cached"] += 1
        else:
            yf_symbol = get_yfinance_symbol(symbol)
            payload = {"symbol": symbol, "yf_ticker": yf_symbol, "fetched_at": datetime.now().isoformat()}
            try:
                ticker = yf.Ticker(yf_symbol)
                info = ticker.info or {}

                earnings_date = _extract_next_earnings_date(ticker)
                days_to = (earnings_date - run_day).days if earnings_date else None
                e_status, e_mult, e_reason = _event_multiplier(days_to, event_cfg)

                fundamentals = {"status": "DISABLED", "grade": None, "multiplier": 1.0, "details": {}}
                if fundamentals_enabled:
                    grade, _, details = _score_fundamentals(info, fundamentals_thresholds)
                    fundamentals = {
                        "status": "OK" if info else "UNKNOWN",
                        "grade": grade if info else None,
                        "multiplier": float(fundamentals_grade_mult.get(grade, fundamentals_unknown_mult)) if info else fundamentals_unknown_mult,
                        "details": details,
                        "fields": {
                            "marketCap": info.get("marketCap"),
                            "trailingPE": info.get("trailingPE"),
                            "returnOnEquity": info.get("returnOnEquity"),
                            "debtToEquity": info.get("debtToEquity"),
                            "profitMargins": info.get("profitMargins"),
                            "freeCashflow": info.get("freeCashflow"),
                        },
                    }

                payload.update(
                    {
                        "earnings": {
                            "date": earnings_date.isoformat() if earnings_date else None,
                            "days_to": days_to,
                            "status": e_status,
                            "multiplier": float(e_mult),
                            "reason": e_reason,
                        },
                        "fundamentals": fundamentals,
                    }
                )

                out["summary"]["fetched"] += 1
            except Exception as e:
                payload["status"] = "ERROR"
                payload["error"] = str(e)
                payload["earnings"] = {"status": "UNKNOWN", "multiplier": 0.7, "reason": "Meta fetch failed"}
                payload["fundamentals"] = {"status": "UNKNOWN", "grade": None, "multiplier": fundamentals_unknown_mult}
                out["summary"]["failed"] += 1

            # Write/update cache best-effort
            try:
                _write_json(cache_path, payload)
            except Exception:
                pass

        # Tally summary
        e = payload.get("earnings", {}) or {}
        f = payload.get("fundamentals", {}) or {}
        if e.get("status") == "BLOCK":
            out["summary"]["earnings_block"] += 1
        if f.get("grade") == "D":
            out["summary"]["fundamentals_d"] += 1

        out["symbols"][symbol] = payload

    out_path = run_dir / "symbol_meta.json"
    _write_json(out_path, out)
    print(f"Wrote: {out_path}")
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python build_symbol_meta.py <run_dir>")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    if not (run_dir / "data_health.json").exists():
        print("Error: data_health.json not found. Run prepare_data.py first.")
        sys.exit(1)

    build_symbol_meta(run_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()

