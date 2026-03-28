#!/usr/bin/env python3
"""
Stage A5: Build FII/DII Flow Data

Fetches and pins institutional flow data critical for Indian market analysis:
- FII (Foreign Institutional Investor) cash market flows
- DII (Domestic Institutional Investor) cash market flows
- Net flow trends and severity assessment

Why this matters:
- FII flows drive ~70% of Indian market volatility
- FII selling > ₹2000 Cr is often a regime warning
- DII absorption of FII selling indicates consolidation, not crash

Data Sources:
- NSE India (primary)
- Money Control (fallback)

Outputs (to run_dir):
- flow_data.json
"""

import json
import sys
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import warnings

# Suppress SSL warnings for some financial sites
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import requests
import numpy as np
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def _parse_indian_number(s: str) -> float:
    """Parse Indian number format (handles commas, negative in parentheses)."""
    if not s or s == "-" or s == "NA":
        return 0.0
    s = str(s).strip()
    # Handle parentheses for negative
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    # Remove commas
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _fetch_nse_fii_dii() -> Optional[Dict[str, Any]]:
    """
    Fetch FII/DII data from NSE India.

    Returns dict with fii_buy, fii_sell, dii_buy, dii_sell in Cr.
    """
    url = "https://www.nseindia.com/api/fiidiiTradeReact"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/reports-indices-current-market-statistics",
    }

    try:
        # NSE requires a session with cookies
        session = requests.Session()
        # First hit the main page to get cookies
        session.get("https://www.nseindia.com", headers=headers, timeout=10)

        response = session.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        data = response.json()

        # NSE returns a list of records
        if not data or not isinstance(data, list):
            return None

        # Find today's or latest FII/DII data
        fii_data = None
        dii_data = None

        for record in data:
            category = record.get("category", "").upper()
            if "FII" in category or "FPI" in category:
                fii_data = record
            elif "DII" in category:
                dii_data = record

        if not fii_data and not dii_data:
            return None

        result = {"source": "NSE", "fetch_time": datetime.now().isoformat()}

        if fii_data:
            result["fii"] = {
                "buy": _parse_indian_number(fii_data.get("buyValue", 0)),
                "sell": _parse_indian_number(fii_data.get("sellValue", 0)),
                "net": _parse_indian_number(fii_data.get("netValue", 0)),
                "date": fii_data.get("date"),
            }

        if dii_data:
            result["dii"] = {
                "buy": _parse_indian_number(dii_data.get("buyValue", 0)),
                "sell": _parse_indian_number(dii_data.get("sellValue", 0)),
                "net": _parse_indian_number(dii_data.get("netValue", 0)),
                "date": dii_data.get("date"),
            }

        return result

    except Exception as e:
        print(f"NSE fetch failed: {e}")
        return None


def _fetch_moneycontrol_fii_dii() -> Optional[Dict[str, Any]]:
    """
    Fallback: Fetch FII/DII data from Money Control.
    """
    url = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/data.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        # Parse the HTML to extract FII/DII data
        # This is a simplified parser - may need adjustment based on actual HTML structure
        html = response.text

        # Look for FII/DII values in the response
        # This is a basic implementation - would need proper HTML parsing in production
        result = {
            "source": "MoneyControl",
            "fetch_time": datetime.now().isoformat(),
            "raw_available": True,
            "note": "Fallback source - may have different data timing"
        }

        return result

    except Exception as e:
        print(f"MoneyControl fetch failed: {e}")
        return None


def _calculate_flow_metrics(
    fii_net: float,
    dii_net: float,
    fii_5d_history: List[float],
    dii_5d_history: List[float],
) -> Dict[str, Any]:
    """
    Calculate derived flow metrics.
    """
    # 5-day averages
    fii_5d_avg = np.mean(fii_5d_history) if fii_5d_history else fii_net
    dii_5d_avg = np.mean(dii_5d_history) if dii_5d_history else dii_net

    # Trend classification
    if fii_net > 500:
        fii_trend = "STRONG_INFLOW"
    elif fii_net > 0:
        fii_trend = "INFLOW"
    elif fii_net > -500:
        fii_trend = "MILD_OUTFLOW"
    elif fii_net > -2000:
        fii_trend = "OUTFLOW"
    else:
        fii_trend = "HEAVY_OUTFLOW"

    if dii_net > 500:
        dii_trend = "STRONG_INFLOW"
    elif dii_net > 0:
        dii_trend = "INFLOW"
    elif dii_net > -500:
        dii_trend = "MILD_OUTFLOW"
    else:
        dii_trend = "OUTFLOW"

    # DII absorption check
    dii_absorbing = dii_net > 0 and fii_net < 0 and dii_net >= abs(fii_net) * 0.5

    # Severity assessment (based on historical context)
    # These thresholds are based on typical Indian market flow patterns
    if fii_net < -3000:
        fii_severity = "EXTREME"
        fii_percentile = 95
    elif fii_net < -2000:
        fii_severity = "HIGH"
        fii_percentile = 85
    elif fii_net < -1000:
        fii_severity = "MODERATE"
        fii_percentile = 70
    elif fii_net < 0:
        fii_severity = "LOW"
        fii_percentile = 50
    else:
        fii_severity = "NONE"
        fii_percentile = 30

    # Net market impact
    total_net = fii_net + dii_net
    if total_net > 1000:
        net_impact = "STRONG_POSITIVE"
    elif total_net > 0:
        net_impact = "POSITIVE"
    elif total_net > -500:
        net_impact = "NEUTRAL"
    elif total_net > -1500:
        net_impact = "NEGATIVE"
    else:
        net_impact = "STRONG_NEGATIVE"

    # Conviction multiplier for position sizing
    if fii_severity == "EXTREME":
        flow_multiplier = 0.3
    elif fii_severity == "HIGH" and not dii_absorbing:
        flow_multiplier = 0.5
    elif fii_severity == "MODERATE" and not dii_absorbing:
        flow_multiplier = 0.7
    elif dii_absorbing:
        flow_multiplier = 0.9
    else:
        flow_multiplier = 1.0

    return {
        "fii": {
            "net": round(fii_net, 2),
            "5d_avg": round(fii_5d_avg, 2),
            "trend": fii_trend,
            "severity": fii_severity,
            "percentile_estimate": fii_percentile,
        },
        "dii": {
            "net": round(dii_net, 2),
            "5d_avg": round(dii_5d_avg, 2),
            "trend": dii_trend,
            "absorbing_fii": dii_absorbing,
        },
        "combined": {
            "total_net": round(total_net, 2),
            "net_impact": net_impact,
            "flow_multiplier": round(flow_multiplier, 2),
        },
    }


def _load_flow_cache() -> Tuple[List[float], List[float]]:
    """Load historical flow data from cache for 5-day calculations."""
    cache_path = PROJECT_ROOT / ".cache" / "flow_history.json"
    if not cache_path.exists():
        return [], []

    try:
        data = _load_json(cache_path)
        fii_history = data.get("fii_history", [])[-5:]
        dii_history = data.get("dii_history", [])[-5:]
        return fii_history, dii_history
    except Exception:
        return [], []


def _update_flow_cache(fii_net: float, dii_net: float) -> None:
    """Update flow history cache."""
    cache_path = PROJECT_ROOT / ".cache" / "flow_history.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    fii_history, dii_history = _load_flow_cache()

    # Append today's data
    fii_history.append(fii_net)
    dii_history.append(dii_net)

    # Keep only last 20 days
    fii_history = fii_history[-20:]
    dii_history = dii_history[-20:]

    _write_json(cache_path, {
        "fii_history": fii_history,
        "dii_history": dii_history,
        "last_updated": datetime.now().isoformat(),
    })


def build_flow_data(run_dir: Path) -> dict:
    """
    Build FII/DII flow data artifact.

    Returns dict with flow metrics and conviction impact.
    """
    print("Fetching FII/DII flow data...")

    # Try NSE first
    raw_data = _fetch_nse_fii_dii()

    # Fallback to MoneyControl if NSE fails
    if not raw_data:
        print("NSE fetch failed, trying MoneyControl...")
        raw_data = _fetch_moneycontrol_fii_dii()

    # Load historical data for 5-day metrics
    fii_history, dii_history = _load_flow_cache()

    # Build output
    if raw_data and "fii" in raw_data:
        fii_net = raw_data["fii"].get("net", 0)
        dii_net = raw_data.get("dii", {}).get("net", 0)

        # Update cache
        _update_flow_cache(fii_net, dii_net)

        # Calculate metrics
        metrics = _calculate_flow_metrics(fii_net, dii_net, fii_history, dii_history)

        output = {
            "build_timestamp": datetime.now().isoformat(),
            "source": raw_data.get("source", "Unknown"),
            "data_date": raw_data.get("fii", {}).get("date"),
            "status": "OK",
            "raw": {
                "fii": raw_data.get("fii"),
                "dii": raw_data.get("dii"),
            },
            "metrics": metrics,
            "signal_impact": {
                "flow_multiplier": metrics["combined"]["flow_multiplier"],
                "should_reduce_size": metrics["combined"]["flow_multiplier"] < 1.0,
                "reasoning": _generate_flow_reasoning(metrics),
            },
        }
    else:
        # Failed to fetch - use conservative defaults
        output = {
            "build_timestamp": datetime.now().isoformat(),
            "source": "UNAVAILABLE",
            "status": "FETCH_FAILED",
            "raw": None,
            "metrics": {
                "fii": {"net": 0, "trend": "UNKNOWN", "severity": "UNKNOWN"},
                "dii": {"net": 0, "trend": "UNKNOWN", "absorbing_fii": False},
                "combined": {
                    "total_net": 0,
                    "net_impact": "UNKNOWN",
                    "flow_multiplier": 0.8,  # Conservative default
                },
            },
            "signal_impact": {
                "flow_multiplier": 0.8,
                "should_reduce_size": True,
                "reasoning": "FII/DII data unavailable - using conservative position sizing",
            },
        }

    # Write output
    out_path = run_dir / "flow_data.json"
    _write_json(out_path, output)

    print(f"Wrote: {out_path}")
    if output["status"] == "OK":
        metrics = output["metrics"]
        print(f"FII: {metrics['fii']['net']:+,.0f} Cr ({metrics['fii']['trend']})")
        print(f"DII: {metrics['dii']['net']:+,.0f} Cr ({metrics['dii']['trend']})")
        print(f"Flow Multiplier: {metrics['combined']['flow_multiplier']}")

    return output


def _generate_flow_reasoning(metrics: dict) -> str:
    """Generate human-readable reasoning for flow impact."""
    fii = metrics["fii"]
    dii = metrics["dii"]
    combined = metrics["combined"]

    parts = []

    # FII assessment
    if fii["severity"] == "EXTREME":
        parts.append(f"ALERT: Heavy FII selling ({fii['net']:+,.0f} Cr) - extreme caution advised")
    elif fii["severity"] == "HIGH":
        parts.append(f"FII selling elevated ({fii['net']:+,.0f} Cr)")
    elif fii["trend"] == "STRONG_INFLOW":
        parts.append(f"FII strongly bullish ({fii['net']:+,.0f} Cr)")

    # DII absorption
    if dii["absorbing_fii"]:
        parts.append("DII absorbing FII selling - suggests consolidation, not panic")

    # Net impact
    if combined["net_impact"] == "STRONG_POSITIVE":
        parts.append("Net flows strongly positive - bullish institutional sentiment")
    elif combined["net_impact"] == "STRONG_NEGATIVE":
        parts.append("Net flows strongly negative - defensive stance recommended")

    if not parts:
        parts.append("Institutional flows neutral")

    return "; ".join(parts)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python build_flow_data.py <run_dir>")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    build_flow_data(run_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
