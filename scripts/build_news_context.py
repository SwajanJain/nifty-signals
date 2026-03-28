#!/usr/bin/env python3
"""
Stage A7: Build News & Events Context

Aggregates market-moving news and events for intelligent analysis:
- Macro events (RBI, Fed, Budget, Elections)
- Corporate actions (Results, Dividends, Splits, Bonus)
- Sector-specific news
- Stock-specific catalysts

Why this matters:
- News can invalidate technical setups
- Earnings in 2 days = binary event risk
- Policy changes affect sector rotation
- Global events impact sentiment

Data Sources:
- Economic calendar (investing.com, trading economics)
- Corporate actions calendar (BSE/NSE)
- News aggregation (RSS feeds, Google News)

Outputs (to run_dir):
- news_context.json
"""

import json
import sys
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import warnings

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import requests
from bs4 import BeautifulSoup
import feedparser

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
        json.dump(payload, f, indent=2, default=str)


# ============================================================================
# MACRO EVENTS
# ============================================================================

# Pre-defined important events (updated periodically)
KNOWN_MACRO_EVENTS = [
    # RBI events
    {"event": "RBI MPC Meeting", "recurring": "bi-monthly", "impact": "HIGH", "affects": ["Banks", "NBFC", "Real Estate"]},
    {"event": "RBI Credit Policy", "recurring": "quarterly", "impact": "HIGH", "affects": ["Banks", "NBFC"]},

    # US Fed events
    {"event": "US Fed FOMC Meeting", "recurring": "6-weekly", "impact": "HIGH", "affects": ["IT", "Pharma", "All"]},
    {"event": "US Jobs Report", "recurring": "monthly", "impact": "MEDIUM", "affects": ["IT", "All"]},
    {"event": "US CPI Data", "recurring": "monthly", "impact": "MEDIUM", "affects": ["All"]},

    # India specific
    {"event": "India CPI Inflation", "recurring": "monthly", "impact": "MEDIUM", "affects": ["FMCG", "All"]},
    {"event": "India IIP Data", "recurring": "monthly", "impact": "LOW", "affects": ["Auto", "Capital Goods"]},
    {"event": "India GDP Data", "recurring": "quarterly", "impact": "MEDIUM", "affects": ["All"]},
    {"event": "GST Collection Data", "recurring": "monthly", "impact": "LOW", "affects": ["All"]},

    # Market events
    {"event": "F&O Expiry", "recurring": "weekly/monthly", "impact": "MEDIUM", "affects": ["All"]},
    {"event": "MSCI Rebalancing", "recurring": "quarterly", "impact": "HIGH", "affects": ["FII heavy stocks"]},
]


def _fetch_economic_calendar() -> List[Dict[str, Any]]:
    """
    Fetch upcoming economic events.

    Returns list of events with dates and impact levels.
    """
    events = []
    today = datetime.now().date()

    # Calculate next F&O expiry (last Thursday of month for monthly)
    # Weekly expiry is every Thursday
    days_until_thursday = (3 - today.weekday()) % 7
    if days_until_thursday == 0:
        next_weekly_expiry = today
    else:
        next_weekly_expiry = today + timedelta(days=days_until_thursday)

    events.append({
        "event": "Weekly F&O Expiry",
        "date": next_weekly_expiry.isoformat(),
        "days_away": (next_weekly_expiry - today).days,
        "impact": "MEDIUM",
        "affects": ["All F&O stocks"],
        "note": "Increased volatility expected near expiry"
    })

    # Try to fetch from investing.com or similar
    try:
        url = "https://www.investing.com/economic-calendar/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Note: This is a simplified fetch - real implementation would parse the calendar
        # For now, we'll use known events

    except Exception as e:
        print(f"Economic calendar fetch failed: {e}")

    # Add RBI MPC (typically bi-monthly)
    # This is a placeholder - real dates would be fetched or configured
    events.append({
        "event": "RBI MPC Decision (Tentative)",
        "date": (today + timedelta(days=30)).isoformat(),
        "days_away": 30,
        "impact": "HIGH",
        "affects": ["Banks", "NBFC", "Real Estate"],
        "note": "Interest rate decision - check actual date"
    })

    return events


def _get_earnings_calendar(symbols: List[str], symbol_meta: Optional[dict]) -> List[Dict[str, Any]]:
    """
    Extract upcoming earnings from symbol_meta (pinned in Stage A2).
    """
    earnings = []
    today = datetime.now().date()

    if not symbol_meta:
        return earnings

    symbols_data = symbol_meta.get("symbols", {})

    for symbol in symbols:
        meta = symbols_data.get(symbol, {})
        earnings_info = meta.get("earnings", {})

        earnings_date = earnings_info.get("date")
        if earnings_date:
            try:
                earn_date = datetime.fromisoformat(earnings_date).date()
                days_away = (earn_date - today).days

                if 0 <= days_away <= 30:  # Only show next 30 days
                    status = earnings_info.get("status", "UNKNOWN")

                    earnings.append({
                        "symbol": symbol,
                        "date": earnings_date,
                        "days_away": days_away,
                        "status": status,
                        "impact": "HIGH" if days_away <= 3 else "MEDIUM",
                        "note": f"Earnings in {days_away} days" + (" - AVOID" if status == "BLOCK" else "")
                    })
            except Exception:
                pass

    # Sort by date
    earnings.sort(key=lambda x: x["days_away"])

    return earnings


def _fetch_sector_news() -> Dict[str, List[str]]:
    """
    Fetch sector-specific news headlines.

    Returns dict of sector -> list of headlines.
    """
    sector_news = {
        "IT": [],
        "Banks": [],
        "Pharma": [],
        "Auto": [],
        "FMCG": [],
        "Energy": [],
        "Metals": [],
        "Realty": [],
        "Infra": [],
    }

    # RSS feeds for financial news
    rss_feeds = [
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.moneycontrol.com/rss/latestnews.xml",
    ]

    try:
        for feed_url in rss_feeds:
            try:
                feed = feedparser.parse(feed_url)

                for entry in feed.entries[:20]:  # Last 20 entries
                    title = entry.get("title", "").lower()
                    summary = entry.get("summary", "").lower()
                    combined = title + " " + summary

                    # Classify by sector keywords
                    if any(kw in combined for kw in ["tcs", "infosys", "wipro", "hcl", "tech mahindra", "it sector", "software"]):
                        sector_news["IT"].append(entry.get("title", ""))

                    if any(kw in combined for kw in ["hdfc bank", "icici bank", "sbi", "axis bank", "kotak", "banking", "rbi", "npa"]):
                        sector_news["Banks"].append(entry.get("title", ""))

                    if any(kw in combined for kw in ["sun pharma", "cipla", "dr reddy", "pharma", "fda", "drug"]):
                        sector_news["Pharma"].append(entry.get("title", ""))

                    if any(kw in combined for kw in ["tata motors", "maruti", "bajaj auto", "hero", "auto", "ev", "vehicle"]):
                        sector_news["Auto"].append(entry.get("title", ""))

                    if any(kw in combined for kw in ["reliance", "ongc", "oil", "gas", "energy", "power"]):
                        sector_news["Energy"].append(entry.get("title", ""))

                    if any(kw in combined for kw in ["tata steel", "jsw", "hindalco", "vedanta", "metal", "steel", "aluminium"]):
                        sector_news["Metals"].append(entry.get("title", ""))

            except Exception as e:
                continue

    except Exception as e:
        print(f"Sector news fetch failed: {e}")

    # Limit to top 3 per sector
    for sector in sector_news:
        sector_news[sector] = sector_news[sector][:3]

    return sector_news


def _fetch_stock_specific_news(symbols: List[str]) -> Dict[str, List[str]]:
    """
    Fetch news for specific stocks in watchlist.
    """
    stock_news = {}

    # Focus on top symbols (to avoid too many requests)
    priority_symbols = symbols[:20] if len(symbols) > 20 else symbols

    try:
        for symbol in priority_symbols:
            # Clean symbol for search
            search_term = symbol.replace(".NS", "").replace("&", "").strip()

            try:
                # Google News RSS (simplified)
                url = f"https://news.google.com/rss/search?q={search_term}+stock+india&hl=en-IN&gl=IN&ceid=IN:en"
                feed = feedparser.parse(url)

                headlines = []
                for entry in feed.entries[:3]:
                    title = entry.get("title", "")
                    if title:
                        # Clean up title (remove source suffix)
                        title = re.sub(r'\s*-\s*[^-]+$', '', title)
                        headlines.append(title[:100])  # Limit length

                if headlines:
                    stock_news[symbol] = headlines

            except Exception:
                continue

    except Exception as e:
        print(f"Stock news fetch failed: {e}")

    return stock_news


def _assess_news_risk(
    macro_events: List[Dict],
    earnings: List[Dict],
    sector_news: Dict[str, List[str]],
) -> Dict[str, Any]:
    """
    Assess overall news/event risk level.
    """
    risk_score = 0
    risk_factors = []

    # Check for high-impact macro events in next 3 days
    near_term_events = [e for e in macro_events if e.get("days_away", 999) <= 3 and e.get("impact") == "HIGH"]
    if near_term_events:
        risk_score += 2
        risk_factors.append(f"High-impact event in 3 days: {near_term_events[0]['event']}")

    # Check for earnings
    near_term_earnings = [e for e in earnings if e.get("days_away", 999) <= 3]
    if len(near_term_earnings) >= 5:
        risk_score += 1
        risk_factors.append(f"{len(near_term_earnings)} stocks reporting earnings in 3 days")

    # F&O expiry check
    expiry_events = [e for e in macro_events if "expiry" in e.get("event", "").lower() and e.get("days_away", 999) <= 1]
    if expiry_events:
        risk_score += 1
        risk_factors.append("F&O expiry imminent - expect volatility")

    # Risk level classification
    if risk_score >= 3:
        risk_level = "HIGH"
        risk_multiplier = 0.7
        recommendation = "Reduce position sizes due to event risk"
    elif risk_score >= 2:
        risk_level = "ELEVATED"
        risk_multiplier = 0.85
        recommendation = "Exercise caution - events ahead"
    elif risk_score >= 1:
        risk_level = "MODERATE"
        risk_multiplier = 0.95
        recommendation = "Normal trading with awareness of events"
    else:
        risk_level = "LOW"
        risk_multiplier = 1.0
        recommendation = "No significant event risk detected"

    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_multiplier": risk_multiplier,
        "risk_factors": risk_factors,
        "recommendation": recommendation,
    }


def build_news_context(run_dir: Path) -> dict:
    """
    Build news and events context artifact.
    """
    print("Building news and events context...")

    # Load symbol meta for earnings info
    symbol_meta_path = run_dir / "symbol_meta.json"
    symbol_meta = None
    if symbol_meta_path.exists():
        try:
            symbol_meta = _load_json(symbol_meta_path)
        except Exception:
            pass

    # Get symbols
    symbols = get_nifty100_symbols() or []

    # Fetch all components
    print("  Fetching economic calendar...")
    macro_events = _fetch_economic_calendar()

    print("  Extracting earnings calendar...")
    earnings = _get_earnings_calendar(symbols, symbol_meta)

    print("  Fetching sector news...")
    sector_news = _fetch_sector_news()

    print("  Fetching stock-specific news...")
    # Get candidates to prioritize news fetch
    candidates_path = run_dir / "candidates.json"
    priority_symbols = symbols[:10]
    if candidates_path.exists():
        try:
            candidates_data = _load_json(candidates_path)
            top_candidates = [c["symbol"] for c in candidates_data.get("candidates", [])[:10] if not c.get("should_skip")]
            if top_candidates:
                priority_symbols = top_candidates
        except Exception:
            pass

    stock_news = _fetch_stock_specific_news(priority_symbols)

    # Assess risk
    risk_assessment = _assess_news_risk(macro_events, earnings, sector_news)

    # Build output
    output = {
        "build_timestamp": datetime.now().isoformat(),
        "status": "OK",

        "macro_events": {
            "upcoming": macro_events[:10],
            "high_impact_next_7d": [e for e in macro_events if e.get("days_away", 999) <= 7 and e.get("impact") == "HIGH"],
        },

        "earnings_calendar": {
            "next_3_days": [e for e in earnings if e.get("days_away", 999) <= 3],
            "next_7_days": [e for e in earnings if e.get("days_away", 999) <= 7],
            "blocked_symbols": [e["symbol"] for e in earnings if e.get("status") == "BLOCK"],
        },

        "sector_news": sector_news,

        "stock_news": stock_news,

        "risk_assessment": risk_assessment,

        "signal_impact": {
            "news_multiplier": risk_assessment["risk_multiplier"],
            "avoid_symbols": [e["symbol"] for e in earnings if e.get("days_away", 999) <= 3],
            "caution_sectors": [],  # Would be populated based on negative sector news
        },
    }

    # Identify caution sectors based on negative news keywords
    negative_keywords = ["fall", "drop", "crash", "warning", "downgrade", "concern", "risk", "weak"]
    for sector, headlines in sector_news.items():
        if headlines:
            combined = " ".join(headlines).lower()
            negative_count = sum(1 for kw in negative_keywords if kw in combined)
            if negative_count >= 2:
                output["signal_impact"]["caution_sectors"].append(sector)

    # Write output
    out_path = run_dir / "news_context.json"
    _write_json(out_path, output)

    print(f"Wrote: {out_path}")
    print(f"Event Risk: {risk_assessment['risk_level']} (multiplier: {risk_assessment['risk_multiplier']})")
    print(f"Earnings in 3 days: {len(output['earnings_calendar']['next_3_days'])} stocks")

    return output


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python build_news_context.py <run_dir>")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    build_news_context(run_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
