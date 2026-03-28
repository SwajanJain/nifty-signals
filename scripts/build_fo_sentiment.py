#!/usr/bin/env python3
"""
Stage A6: Build F&O Sentiment Data

Fetches and pins derivatives market data for forward-looking analysis:
- Put-Call Ratio (PCR) - options market sentiment
- Max Pain - price level where options writers profit most
- Open Interest (OI) buildup analysis
- Implied Volatility (IV) context

Why this matters:
- Options market is forward-looking (smart money positioning)
- PCR > 1.2 often bullish (put writers confident)
- Max Pain acts as a magnet near expiry
- OI buildup direction indicates institutional positioning

Data Sources:
- NSE India (primary)
- Sensibull/Opstra-style calculation (fallback)

Outputs (to run_dir):
- fo_sentiment.json
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import warnings

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import requests
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
        json.dump(payload, f, indent=2, default=str)


def _get_nse_session() -> requests.Session:
    """Create a session with NSE cookies."""
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    session.headers.update(headers)

    try:
        # Get cookies from main page
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        pass

    return session


def _fetch_nifty_option_chain() -> Optional[Dict[str, Any]]:
    """
    Fetch NIFTY option chain from NSE.

    Returns option chain data with strikes, OI, and premiums.
    """
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"

    try:
        session = _get_nse_session()
        session.headers["Referer"] = "https://www.nseindia.com/option-chain"

        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return None

        data = response.json()
        if not data or "records" not in data:
            return None

        return data

    except Exception as e:
        print(f"NIFTY option chain fetch failed: {e}")
        return None


def _calculate_pcr(option_data: Dict) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate Put-Call Ratio from option chain.

    Returns (PCR value, detailed breakdown)
    """
    if not option_data or "records" not in option_data:
        return 1.0, {"status": "UNAVAILABLE"}

    records = option_data["records"]
    data = records.get("data", [])

    total_put_oi = 0
    total_call_oi = 0
    total_put_volume = 0
    total_call_volume = 0

    for strike_data in data:
        if "PE" in strike_data:
            pe = strike_data["PE"]
            total_put_oi += pe.get("openInterest", 0) or 0
            total_put_volume += pe.get("totalTradedVolume", 0) or 0

        if "CE" in strike_data:
            ce = strike_data["CE"]
            total_call_oi += ce.get("openInterest", 0) or 0
            total_call_volume += ce.get("totalTradedVolume", 0) or 0

    # Calculate PCR (OI-based is more reliable than volume-based)
    pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
    pcr_volume = total_put_volume / total_call_volume if total_call_volume > 0 else 1.0

    breakdown = {
        "put_oi": total_put_oi,
        "call_oi": total_call_oi,
        "put_volume": total_put_volume,
        "call_volume": total_call_volume,
        "pcr_oi": round(pcr_oi, 3),
        "pcr_volume": round(pcr_volume, 3),
    }

    return pcr_oi, breakdown


def _calculate_max_pain(option_data: Dict) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate Max Pain - the strike price where option writers profit most.

    Max Pain = Strike where (Call Pain + Put Pain) is minimum
    """
    if not option_data or "records" not in option_data:
        return 0, {"status": "UNAVAILABLE"}

    records = option_data["records"]
    data = records.get("data", [])

    # Build strike-level OI data
    strikes = {}
    for strike_data in data:
        strike = strike_data.get("strikePrice")
        if not strike:
            continue

        call_oi = 0
        put_oi = 0

        if "CE" in strike_data:
            call_oi = strike_data["CE"].get("openInterest", 0) or 0

        if "PE" in strike_data:
            put_oi = strike_data["PE"].get("openInterest", 0) or 0

        strikes[strike] = {"call_oi": call_oi, "put_oi": put_oi}

    if not strikes:
        return 0, {"status": "NO_DATA"}

    # Calculate pain at each strike
    strike_prices = sorted(strikes.keys())
    min_pain = float("inf")
    max_pain_strike = strike_prices[len(strike_prices) // 2]

    pain_analysis = []

    for test_strike in strike_prices:
        total_pain = 0

        for strike, oi in strikes.items():
            # Call writers' pain (if price > strike)
            if test_strike > strike:
                call_pain = (test_strike - strike) * oi["call_oi"]
            else:
                call_pain = 0

            # Put writers' pain (if price < strike)
            if test_strike < strike:
                put_pain = (strike - test_strike) * oi["put_oi"]
            else:
                put_pain = 0

            total_pain += call_pain + put_pain

        pain_analysis.append({"strike": test_strike, "total_pain": total_pain})

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_strike

    # Find top 3 pain levels for context
    pain_analysis.sort(key=lambda x: x["total_pain"])
    top_strikes = [p["strike"] for p in pain_analysis[:3]]

    breakdown = {
        "max_pain": max_pain_strike,
        "pain_value": min_pain,
        "nearby_pain_strikes": top_strikes,
        "total_strikes_analyzed": len(strike_prices),
    }

    return max_pain_strike, breakdown


def _analyze_oi_buildup(option_data: Dict, spot_price: float) -> Dict[str, Any]:
    """
    Analyze OI buildup to determine institutional positioning.

    - Long Buildup: Price up + OI up = Bullish
    - Short Buildup: Price down + OI up = Bearish
    - Short Covering: Price up + OI down = Weak rally
    - Long Unwinding: Price down + OI down = Weak decline
    """
    if not option_data or "records" not in option_data:
        return {"status": "UNAVAILABLE"}

    records = option_data["records"]

    # Get totals
    underlying = records.get("underlyingValue", spot_price)
    timestamp = records.get("timestamp", "")

    # Analyze OI changes at key strikes (ATM and nearby)
    data = records.get("data", [])

    # Find ATM strike
    atm_strike = round(underlying / 50) * 50  # NIFTY has 50-point strikes

    # Get OI at ATM and nearby strikes
    atm_analysis = {"strike": atm_strike, "call_oi": 0, "put_oi": 0}
    itm_puts = []
    otm_calls = []

    for strike_data in data:
        strike = strike_data.get("strikePrice", 0)

        call_oi = 0
        put_oi = 0

        if "CE" in strike_data:
            call_oi = strike_data["CE"].get("openInterest", 0) or 0
            call_change = strike_data["CE"].get("changeinOpenInterest", 0) or 0

        if "PE" in strike_data:
            put_oi = strike_data["PE"].get("openInterest", 0) or 0
            put_change = strike_data["PE"].get("changeinOpenInterest", 0) or 0

        if strike == atm_strike:
            atm_analysis = {
                "strike": strike,
                "call_oi": call_oi,
                "put_oi": put_oi,
                "call_change": call_change,
                "put_change": put_change,
            }

        # Track ITM puts (support) and OTM calls (resistance)
        if strike < underlying and put_oi > 100000:
            itm_puts.append({"strike": strike, "oi": put_oi})

        if strike > underlying and call_oi > 100000:
            otm_calls.append({"strike": strike, "oi": call_oi})

    # Sort to find key levels
    itm_puts.sort(key=lambda x: x["oi"], reverse=True)
    otm_calls.sort(key=lambda x: x["oi"], reverse=True)

    # Major support = highest put OI below spot
    # Major resistance = highest call OI above spot
    support_level = itm_puts[0]["strike"] if itm_puts else atm_strike - 200
    resistance_level = otm_calls[0]["strike"] if otm_calls else atm_strike + 200

    # Determine bias
    atm_pcr = atm_analysis["put_oi"] / atm_analysis["call_oi"] if atm_analysis["call_oi"] > 0 else 1.0

    if atm_pcr > 1.2:
        bias = "BULLISH"
        bias_reasoning = "High put writing at ATM suggests support"
    elif atm_pcr < 0.8:
        bias = "BEARISH"
        bias_reasoning = "High call writing at ATM suggests resistance"
    else:
        bias = "NEUTRAL"
        bias_reasoning = "Balanced OI at ATM"

    return {
        "underlying": underlying,
        "atm_strike": atm_strike,
        "atm_analysis": atm_analysis,
        "atm_pcr": round(atm_pcr, 3),
        "bias": bias,
        "bias_reasoning": bias_reasoning,
        "support_level": support_level,
        "resistance_level": resistance_level,
        "top_put_strikes": [p["strike"] for p in itm_puts[:3]],
        "top_call_strikes": [c["strike"] for c in otm_calls[:3]],
    }


def _get_iv_context(option_data: Dict) -> Dict[str, Any]:
    """
    Extract implied volatility context.
    """
    if not option_data or "records" not in option_data:
        return {"status": "UNAVAILABLE"}

    records = option_data["records"]
    data = records.get("data", [])

    # Collect IV from ATM options
    underlying = records.get("underlyingValue", 0)
    atm_strike = round(underlying / 50) * 50

    iv_values = []

    for strike_data in data:
        strike = strike_data.get("strikePrice", 0)

        # Look at strikes within 2% of ATM
        if abs(strike - atm_strike) / atm_strike > 0.02:
            continue

        if "CE" in strike_data:
            iv = strike_data["CE"].get("impliedVolatility", 0)
            if iv and iv > 0:
                iv_values.append(iv)

        if "PE" in strike_data:
            iv = strike_data["PE"].get("impliedVolatility", 0)
            if iv and iv > 0:
                iv_values.append(iv)

    if not iv_values:
        return {"status": "NO_IV_DATA"}

    avg_iv = np.mean(iv_values)

    # IV interpretation (based on typical NIFTY IV ranges)
    if avg_iv < 12:
        iv_regime = "LOW"
        iv_interpretation = "Low IV - calm market, good for directional trades"
    elif avg_iv < 18:
        iv_regime = "NORMAL"
        iv_interpretation = "Normal IV - standard conditions"
    elif avg_iv < 25:
        iv_regime = "ELEVATED"
        iv_interpretation = "Elevated IV - uncertainty, consider smaller size"
    else:
        iv_regime = "HIGH"
        iv_interpretation = "High IV - fear in market, options expensive"

    return {
        "avg_iv": round(avg_iv, 2),
        "iv_regime": iv_regime,
        "iv_interpretation": iv_interpretation,
        "iv_values_sampled": len(iv_values),
    }


def _calculate_sentiment_score(
    pcr: float,
    max_pain: float,
    spot: float,
    oi_analysis: Dict,
    iv_context: Dict,
) -> Dict[str, Any]:
    """
    Calculate overall F&O sentiment score (-5 to +5).
    """
    score = 0
    factors = []

    # PCR contribution (-2 to +2)
    if pcr > 1.3:
        pcr_score = 2
        factors.append("High PCR (+2): Strong put writing, bullish")
    elif pcr > 1.1:
        pcr_score = 1
        factors.append("Elevated PCR (+1): Mild bullish sentiment")
    elif pcr > 0.9:
        pcr_score = 0
        factors.append("Neutral PCR (0): Balanced positioning")
    elif pcr > 0.7:
        pcr_score = -1
        factors.append("Low PCR (-1): Mild bearish sentiment")
    else:
        pcr_score = -2
        factors.append("Very low PCR (-2): Heavy call writing, bearish")
    score += pcr_score

    # Max Pain distance contribution (-1 to +1)
    if max_pain > 0 and spot > 0:
        distance_pct = ((max_pain - spot) / spot) * 100
        if distance_pct > 1:
            mp_score = 1
            factors.append(f"Below max pain (+1): Price may drift up to {max_pain}")
        elif distance_pct < -1:
            mp_score = -1
            factors.append(f"Above max pain (-1): Price may drift down to {max_pain}")
        else:
            mp_score = 0
            factors.append(f"Near max pain (0): At equilibrium {max_pain}")
        score += mp_score

    # OI bias contribution (-1 to +1)
    oi_bias = oi_analysis.get("bias", "NEUTRAL")
    if oi_bias == "BULLISH":
        score += 1
        factors.append("OI bias bullish (+1): Put support building")
    elif oi_bias == "BEARISH":
        score -= 1
        factors.append("OI bias bearish (-1): Call resistance building")

    # IV contribution (-1 to +1)
    iv_regime = iv_context.get("iv_regime", "NORMAL")
    if iv_regime == "LOW":
        score += 1
        factors.append("Low IV (+1): Calm market, directional opportunity")
    elif iv_regime == "HIGH":
        score -= 1
        factors.append("High IV (-1): Fear/uncertainty, reduce size")

    # Map to sentiment label
    if score >= 3:
        sentiment = "STRONGLY_BULLISH"
    elif score >= 1:
        sentiment = "BULLISH"
    elif score >= -1:
        sentiment = "NEUTRAL"
    elif score >= -3:
        sentiment = "BEARISH"
    else:
        sentiment = "STRONGLY_BEARISH"

    # Calculate conviction multiplier
    if sentiment in ("STRONGLY_BULLISH", "BULLISH"):
        fo_multiplier = 1.0 + (score * 0.05)  # Up to 1.25x
    elif sentiment in ("BEARISH", "STRONGLY_BEARISH"):
        fo_multiplier = 1.0 + (score * 0.1)  # Down to 0.5x
    else:
        fo_multiplier = 1.0

    fo_multiplier = max(0.5, min(1.25, fo_multiplier))

    return {
        "score": score,
        "sentiment": sentiment,
        "fo_multiplier": round(fo_multiplier, 2),
        "factors": factors,
    }


def build_fo_sentiment(run_dir: Path) -> dict:
    """
    Build F&O sentiment data artifact.

    Returns comprehensive derivatives market analysis.
    """
    print("Fetching F&O sentiment data...")

    # Fetch NIFTY option chain
    option_data = _fetch_nifty_option_chain()

    if option_data:
        records = option_data.get("records", {})
        spot_price = records.get("underlyingValue", 0)
        expiry_date = records.get("expiryDate", "")

        # Calculate all metrics
        pcr, pcr_breakdown = _calculate_pcr(option_data)
        max_pain, max_pain_breakdown = _calculate_max_pain(option_data)
        oi_analysis = _analyze_oi_buildup(option_data, spot_price)
        iv_context = _get_iv_context(option_data)
        sentiment = _calculate_sentiment_score(pcr, max_pain, spot_price, oi_analysis, iv_context)

        output = {
            "build_timestamp": datetime.now().isoformat(),
            "status": "OK",
            "index": "NIFTY",
            "spot_price": spot_price,
            "expiry_date": expiry_date,
            "pcr": {
                "value": round(pcr, 3),
                "interpretation": _interpret_pcr(pcr),
                "breakdown": pcr_breakdown,
            },
            "max_pain": {
                "strike": max_pain,
                "distance_from_spot": round(max_pain - spot_price, 2) if spot_price else 0,
                "distance_pct": round(((max_pain - spot_price) / spot_price) * 100, 2) if spot_price else 0,
                "breakdown": max_pain_breakdown,
            },
            "oi_analysis": oi_analysis,
            "iv_context": iv_context,
            "sentiment": sentiment,
            "signal_impact": {
                "fo_multiplier": sentiment["fo_multiplier"],
                "fo_sentiment": sentiment["sentiment"],
                "key_levels": {
                    "support": oi_analysis.get("support_level"),
                    "resistance": oi_analysis.get("resistance_level"),
                    "max_pain": max_pain,
                },
            },
        }
    else:
        # Fallback when data unavailable
        output = {
            "build_timestamp": datetime.now().isoformat(),
            "status": "FETCH_FAILED",
            "index": "NIFTY",
            "pcr": {"value": 1.0, "interpretation": "Data unavailable"},
            "max_pain": {"strike": 0, "distance_from_spot": 0},
            "oi_analysis": {"status": "UNAVAILABLE"},
            "iv_context": {"status": "UNAVAILABLE"},
            "sentiment": {
                "score": 0,
                "sentiment": "UNKNOWN",
                "fo_multiplier": 1.0,
                "factors": ["F&O data unavailable - using neutral assumptions"],
            },
            "signal_impact": {
                "fo_multiplier": 1.0,
                "fo_sentiment": "UNKNOWN",
            },
        }

    # Write output
    out_path = run_dir / "fo_sentiment.json"
    _write_json(out_path, output)

    print(f"Wrote: {out_path}")
    if output["status"] == "OK":
        print(f"PCR: {output['pcr']['value']:.3f} ({output['pcr']['interpretation']})")
        print(f"Max Pain: {output['max_pain']['strike']} ({output['max_pain']['distance_pct']:+.1f}% from spot)")
        print(f"Sentiment: {output['sentiment']['sentiment']} (score: {output['sentiment']['score']:+d})")

    return output


def _interpret_pcr(pcr: float) -> str:
    """Generate PCR interpretation."""
    if pcr > 1.5:
        return "Very high - extreme bullish (contrarian caution)"
    elif pcr > 1.2:
        return "High - bullish (put writers confident)"
    elif pcr > 1.0:
        return "Above parity - mildly bullish"
    elif pcr > 0.8:
        return "Below parity - mildly bearish"
    elif pcr > 0.6:
        return "Low - bearish (call writers dominant)"
    else:
        return "Very low - extreme bearish (contrarian opportunity)"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python build_fo_sentiment.py <run_dir>")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    build_fo_sentiment(run_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
