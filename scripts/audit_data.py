#!/usr/bin/env python3
"""Audit data availability for all Nifty 500 stocks.

Checks the screener.in cache for every stock and produces a CSV report
showing which stocks have data, which are missing, and data quality.

Usage:
    python3 scripts/audit_data.py              # Check cache only (fast)
    python3 scripts/audit_data.py --fetch      # Fetch missing stocks (slow)
"""

import csv
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CACHE_DIR, STOCKS_FILE

CACHE_DB = CACHE_DIR / "fundamental_cache.db"
OUTPUT_CSV = Path(__file__).parent.parent / "reports" / "data_audit.csv"


def load_universe():
    """Load all stocks from stocks.json."""
    with open(STOCKS_FILE) as f:
        data = json.load(f)

    nifty100_symbols = {s["symbol"] for s in data.get("nifty_100", [])}
    nifty500 = data.get("nifty_500", [])

    stocks = []
    for s in nifty500:
        stocks.append({
            "symbol": s["symbol"],
            "name": s.get("name", ""),
            "sector": s.get("sector", ""),
            "in_nifty100": s["symbol"] in nifty100_symbols,
        })
    return stocks


def check_cache():
    """Query the SQLite cache for all symbols and their status."""
    if not CACHE_DB.exists():
        return {}

    conn = sqlite3.connect(CACHE_DB)
    rows = conn.execute(
        "SELECT symbol, data_json, updated_at FROM raw_data"
    ).fetchall()
    conn.close()

    cache_data = {}
    for symbol, data_json, updated_at in rows:
        try:
            data = json.loads(data_json)
            # Determine data quality
            sections_present = 0
            for key in [
                "annual_pl", "quarterly_results", "balance_sheet",
                "cash_flow", "ratios", "shareholding",
            ]:
                val = data.get(key, [])
                if val and len(val) > 0:
                    sections_present += 1

            if sections_present >= 5:
                quality = "GOOD"
            elif sections_present >= 3:
                quality = "PARTIAL"
            elif sections_present >= 1:
                quality = "MINIMAL"
            else:
                quality = "EMPTY"

            cache_data[symbol] = {
                "cached": True,
                "updated_at": updated_at,
                "quality": quality,
                "sections": sections_present,
                "company_name": data.get("company_name", ""),
                "market_cap": data.get("market_cap", 0),
                "current_price": data.get("current_price", 0),
                "data_quality_flag": data.get("data_quality", ""),
            }
        except Exception as e:
            cache_data[symbol] = {
                "cached": True,
                "updated_at": updated_at,
                "quality": "ERROR",
                "sections": 0,
                "company_name": "",
                "market_cap": 0,
                "current_price": 0,
                "data_quality_flag": f"parse error: {e}",
            }

    return cache_data


def fetch_missing(symbols):
    """Attempt to fetch missing stocks from screener.in."""
    from fundamentals.screener_fetcher import ScreenerFetcher

    fetcher = ScreenerFetcher()
    results = {}
    total = len(symbols)

    for i, sym in enumerate(symbols):
        print(f"  [{i+1}/{total}] Fetching {sym}...", end=" ", flush=True)
        raw = fetcher.fetch_stock(sym, force_refresh=False)
        if raw:
            print("OK")
            results[sym] = "FETCHED"
        else:
            print("FAILED")
            results[sym] = "FAILED"

    return results


def main():
    do_fetch = "--fetch" in sys.argv

    print("Loading Nifty 500 universe...")
    stocks = load_universe()
    print(f"  Total stocks: {len(stocks)}")

    print("Checking screener.in cache...")
    cache = check_cache()
    print(f"  Cached stocks: {len(cache)}")

    # Cross-reference
    missing_symbols = []
    rows = []

    for s in stocks:
        sym = s["symbol"]
        cached = cache.get(sym)

        if cached:
            rows.append({
                "symbol": sym,
                "name": s["name"],
                "sector": s["sector"],
                "in_nifty100": "Y" if s["in_nifty100"] else "N",
                "has_data": "Y",
                "data_quality": cached["quality"],
                "sections_present": cached["sections"],
                "cached_at": cached["updated_at"][:10],
                "market_cap": cached["market_cap"],
                "current_price": cached["current_price"],
                "issue": "",
            })
        else:
            missing_symbols.append(sym)
            rows.append({
                "symbol": sym,
                "name": s["name"],
                "sector": s["sector"],
                "in_nifty100": "Y" if s["in_nifty100"] else "N",
                "has_data": "N",
                "data_quality": "MISSING",
                "sections_present": 0,
                "cached_at": "",
                "market_cap": 0,
                "current_price": 0,
                "issue": "Not in cache",
            })

    # Check for symbols in cache but NOT in stocks.json (orphans)
    stock_symbols = {s["symbol"] for s in stocks}
    orphans = [sym for sym in cache if sym not in stock_symbols]

    # Summary
    has_data = sum(1 for r in rows if r["has_data"] == "Y")
    missing = sum(1 for r in rows if r["has_data"] == "N")
    good = sum(1 for r in rows if r["data_quality"] == "GOOD")
    partial = sum(1 for r in rows if r["data_quality"] in ("PARTIAL", "MINIMAL"))
    empty = sum(1 for r in rows if r["data_quality"] == "EMPTY")
    nifty100_missing = [r for r in rows if r["in_nifty100"] == "Y" and r["has_data"] == "N"]

    print(f"\n{'='*60}")
    print(f"DATA AUDIT SUMMARY")
    print(f"{'='*60}")
    print(f"  Universe:        {len(stocks)} stocks")
    print(f"  Has data:        {has_data} ({has_data*100/len(stocks):.1f}%)")
    print(f"  Missing:         {missing} ({missing*100/len(stocks):.1f}%)")
    print(f"  Quality GOOD:    {good}")
    print(f"  Quality PARTIAL: {partial}")
    print(f"  Quality EMPTY:   {empty}")
    print(f"  Orphans in cache:{len(orphans)}")
    print()

    if nifty100_missing:
        print(f"  NIFTY 100 MISSING ({len(nifty100_missing)}):")
        for r in nifty100_missing:
            print(f"    - {r['symbol']} ({r['name']})")
        print()

    if missing_symbols:
        print(f"  ALL MISSING SYMBOLS ({len(missing_symbols)}):")
        for sym in missing_symbols:
            name = next((s["name"] for s in stocks if s["symbol"] == sym), "")
            print(f"    - {sym} ({name})")
        print()

    if orphans:
        print(f"  ORPHANS (in cache but not in stocks.json): {', '.join(orphans[:10])}")
        if len(orphans) > 10:
            print(f"    ... and {len(orphans)-10} more")
        print()

    # Optionally fetch missing
    if do_fetch and missing_symbols:
        print(f"Fetching {len(missing_symbols)} missing stocks...")
        fetch_results = fetch_missing(missing_symbols)
        for r in rows:
            if r["symbol"] in fetch_results:
                if fetch_results[r["symbol"]] == "FETCHED":
                    r["has_data"] = "Y"
                    r["issue"] = "Fetched now"
                    r["data_quality"] = "NEWLY_FETCHED"
                else:
                    r["issue"] = "Fetch failed"

        # Recount
        newly_fetched = sum(1 for v in fetch_results.values() if v == "FETCHED")
        still_missing = sum(1 for v in fetch_results.values() if v == "FAILED")
        print(f"\n  Newly fetched: {newly_fetched}")
        print(f"  Still missing: {still_missing}")

    # Write CSV
    OUTPUT_CSV.parent.mkdir(exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "symbol", "name", "sector", "in_nifty100", "has_data",
            "data_quality", "sections_present", "cached_at",
            "market_cap", "current_price", "issue",
        ])
        writer.writeheader()
        # Sort: missing first, then by symbol
        rows.sort(key=lambda r: (r["has_data"], r["symbol"]))
        writer.writerows(rows)

    print(f"CSV written to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
