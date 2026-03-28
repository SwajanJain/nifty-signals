#!/usr/bin/env python3
"""
Stage F0: Review Run (Pinned Summary)

Produces a deterministic-ish run summary artifact (review.json) from already pinned inputs.
This is not a trading decision step; it helps with monitoring and continuous improvement.

Inputs (from run_dir):
- data_health.json
- market_context.json
- candidates.json
- decision.json (if present)

Outputs (to run_dir):
- review.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _categorize_skip(reason: str) -> str:
    r = (reason or "").lower()
    if r.startswith("stale data"):
        return "data_stale"
    if r.startswith("missing/invalid snapshot"):
        return "data_missing"
    if r.startswith("low liquidity"):
        return "liquidity"
    if r.startswith("earnings"):
        return "earnings"
    if r.startswith("fundamentals"):
        return "fundamentals"
    if "mtf" in r:
        return "mtf"
    if "sector" in r:
        return "sector"
    if "below 200 ema" in r:
        return "trend_filter"
    if r.startswith("low conviction"):
        return "conviction"
    if "r:r" in r or "rr" in r:
        return "rr"
    if "overbought" in r:
        return "overbought"
    if r.startswith("not a long signal"):
        return "signal_direction"
    return "other"


def review_run(run_dir: Path) -> dict:
    data_health = _load_json(run_dir / "data_health.json") or {}
    market_context = _load_json(run_dir / "market_context.json") or {}
    candidates_data = _load_json(run_dir / "candidates.json") or {}
    decision = _load_json(run_dir / "decision.json") or {}

    candidates = candidates_data.get("candidates", []) or []
    summary = candidates_data.get("summary", {}) or {}

    skip_category_counts: Dict[str, int] = {}
    skip_reason_counts: Dict[str, int] = {}

    for c in candidates:
        for reason in (c.get("skip_reasons") or []):
            skip_reason_counts[reason] = skip_reason_counts.get(reason, 0) + 1
            cat = _categorize_skip(reason)
            skip_category_counts[cat] = skip_category_counts.get(cat, 0) + 1

    # Top candidates regardless of skip (for diagnosing why we missed trades)
    top_by_conv = sorted(
        candidates,
        key=lambda x: (x.get("conviction", 0), (x.get("setup") or {}).get("rr_ratio", 0)),
        reverse=True,
    )[:10]
    top_snapshot = []
    for c in top_by_conv:
        top_snapshot.append(
            {
                "symbol": c.get("symbol"),
                "signal": c.get("signal"),
                "conviction": c.get("conviction"),
                "grade": c.get("grade"),
                "sector": c.get("sector"),
                "should_skip": c.get("should_skip"),
                "skip_reasons": c.get("skip_reasons") or [],
            }
        )

    out = {
        "build_timestamp": datetime.now().isoformat(),
        "run_id": run_dir.name,
        "asof_date": data_health.get("last_trading_day"),
        "pipeline_decision": {
            "action": decision.get("action"),
            "symbol": decision.get("symbol"),
            "conviction": decision.get("conviction"),
            "grade": decision.get("grade"),
            "reason": decision.get("reason"),
        },
        "market_context": {
            "regime": market_context.get("regime"),
            "should_trade": market_context.get("should_trade"),
            "vix": market_context.get("vix"),
            "breadth_state": (market_context.get("breadth") or {}).get("state") if isinstance(market_context.get("breadth"), dict) else None,
            "position_size_multiplier": market_context.get("position_size_multiplier"),
        },
        "scan_summary": summary,
        "skip_categories": dict(sorted(skip_category_counts.items(), key=lambda kv: kv[1], reverse=True)),
        "skip_reasons_top": dict(sorted(skip_reason_counts.items(), key=lambda kv: kv[1], reverse=True)[:20]),
        "top_candidates_by_conviction": top_snapshot,
    }

    out_path = run_dir / "review.json"
    _write_json(out_path, out)
    print(f"Wrote: {out_path}")
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python review_run.py <run_dir>")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    review_run(run_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()

