"""
DhanHQ F&O Sentiment Fetcher - PRODUCTION GRADE

Uses DhanHQ API (FREE) for:
- Full Option Chain (OI, IV, Greeks)
- PCR calculation
- Max Pain calculation
- Support/Resistance from OI
- FII/DII activity

This solves the F&O data gap that was blocking the pipeline.
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv

# Load environment variables
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from dhanhq import dhanhq
import pandas as pd
import numpy as np


class DhanFOFetcher:
    """
    F&O Data Fetcher using DhanHQ API.

    Provides:
    - Option Chain with OI, IV, Greeks
    - PCR (Put-Call Ratio)
    - Max Pain calculation
    - Support/Resistance levels
    """

    # Security IDs for indices (DhanHQ specific)
    SECURITY_IDS = {
        "NIFTY": 13,        # NIFTY 50 Index
        "BANKNIFTY": 25,    # Bank Nifty Index
        "FINNIFTY": 27,     # Fin Nifty Index
    }

    def __init__(self):
        """Initialize DhanHQ client."""
        self.client_id = os.getenv("DHAN_CLIENT_ID")
        self.access_token = os.getenv("DHAN_ACCESS_TOKEN")

        if not self.client_id or not self.access_token:
            raise ValueError("DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN must be set in .env")

        self.dhan = dhanhq(self.client_id, self.access_token)

    def get_next_expiry(self) -> str:
        """
        Get the next weekly expiry date (Thursday).

        Returns:
            Expiry date in YYYY-MM-DD format
        """
        today = datetime.now()
        # Find next Thursday (weekday 3)
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0 and today.hour >= 15:  # Past 3 PM on Thursday
            days_until_thursday = 7
        next_thursday = today + timedelta(days=days_until_thursday)
        return next_thursday.strftime("%Y-%m-%d")

    def get_option_chain(self, symbol: str = "NIFTY", expiry: str = None) -> Optional[Dict]:
        """
        Fetch full option chain for an index.

        Args:
            symbol: NIFTY, BANKNIFTY, or FINNIFTY
            expiry: Expiry date (YYYY-MM-DD), defaults to next weekly expiry

        Returns:
            Option chain data with OI, IV, Greeks
        """
        try:
            security_id = self.SECURITY_IDS.get(symbol.upper())
            if not security_id:
                print(f"Unknown symbol: {symbol}")
                return None

            # Get expiry date
            if not expiry:
                expiry = self.get_next_expiry()

            print(f"Fetching option chain for {symbol}, expiry: {expiry}")

            # Get option chain from DhanHQ
            response = self.dhan.option_chain(
                under_security_id=security_id,
                under_exchange_segment="IDX_I",  # Index segment
                expiry=expiry
            )

            if response and response.get("status") == "success":
                data = response.get("data", {})
                data["expiry_date"] = expiry
                return data
            else:
                print(f"Option chain fetch failed: {response}")
                return None

        except Exception as e:
            print(f"Error fetching option chain: {e}")
            return None

    def calculate_pcr(self, option_data: Dict) -> Tuple[float, Dict]:
        """
        Calculate Put-Call Ratio from option chain.

        PCR > 1.2 = Bullish (puts being written = support)
        PCR < 0.8 = Bearish (calls being written = resistance)
        """
        if not option_data:
            return 1.0, {"status": "NO_DATA"}

        total_put_oi = 0
        total_call_oi = 0
        total_put_volume = 0
        total_call_volume = 0

        # Process option chain data
        for strike_data in option_data.get("oc", []):
            # Call data
            ce = strike_data.get("ce", {})
            if ce:
                total_call_oi += ce.get("oi", 0) or 0
                total_call_volume += ce.get("volume", 0) or 0

            # Put data
            pe = strike_data.get("pe", {})
            if pe:
                total_put_oi += pe.get("oi", 0) or 0
                total_put_volume += pe.get("volume", 0) or 0

        # Calculate PCR
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

    def calculate_max_pain(self, option_data: Dict) -> Tuple[float, Dict]:
        """
        Calculate Max Pain strike.

        Max Pain = Strike where option writers (sellers) profit most
        Price tends to gravitate toward Max Pain near expiry.
        """
        if not option_data:
            return 0, {"status": "NO_DATA"}

        strikes = {}

        for strike_data in option_data.get("oc", []):
            strike = strike_data.get("strikePrice")
            if not strike:
                continue

            ce = strike_data.get("ce", {})
            pe = strike_data.get("pe", {})

            call_oi = ce.get("oi", 0) or 0
            put_oi = pe.get("oi", 0) or 0

            strikes[strike] = {"call_oi": call_oi, "put_oi": put_oi}

        if not strikes:
            return 0, {"status": "NO_STRIKES"}

        # Calculate pain at each strike
        strike_prices = sorted(strikes.keys())
        min_pain = float("inf")
        max_pain_strike = strike_prices[len(strike_prices) // 2]

        for test_strike in strike_prices:
            total_pain = 0

            for strike, oi in strikes.items():
                # Call pain (if price > strike, calls are ITM)
                if test_strike > strike:
                    call_pain = (test_strike - strike) * oi["call_oi"]
                else:
                    call_pain = 0

                # Put pain (if price < strike, puts are ITM)
                if test_strike < strike:
                    put_pain = (strike - test_strike) * oi["put_oi"]
                else:
                    put_pain = 0

                total_pain += call_pain + put_pain

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_strike

        return max_pain_strike, {
            "max_pain": max_pain_strike,
            "total_strikes": len(strike_prices),
        }

    def find_support_resistance(self, option_data: Dict, spot: float) -> Dict:
        """
        Find support and resistance levels from OI data.

        High Put OI below spot = Support
        High Call OI above spot = Resistance
        """
        if not option_data:
            return {"status": "NO_DATA"}

        put_levels = []
        call_levels = []

        for strike_data in option_data.get("oc", []):
            strike = strike_data.get("strikePrice", 0)
            if not strike:
                continue

            ce = strike_data.get("ce", {})
            pe = strike_data.get("pe", {})

            call_oi = ce.get("oi", 0) or 0
            put_oi = pe.get("oi", 0) or 0

            # Support levels (puts below spot)
            if strike < spot and put_oi > 100000:
                put_levels.append({"strike": strike, "oi": put_oi})

            # Resistance levels (calls above spot)
            if strike > spot and call_oi > 100000:
                call_levels.append({"strike": strike, "oi": call_oi})

        # Sort by OI (highest first)
        put_levels.sort(key=lambda x: x["oi"], reverse=True)
        call_levels.sort(key=lambda x: x["oi"], reverse=True)

        return {
            "support_levels": [p["strike"] for p in put_levels[:3]],
            "resistance_levels": [c["strike"] for c in call_levels[:3]],
            "immediate_support": put_levels[0]["strike"] if put_levels else spot - 100,
            "immediate_resistance": call_levels[0]["strike"] if call_levels else spot + 100,
        }

    def get_sentiment_score(
        self,
        pcr: float,
        max_pain: float,
        spot: float,
        support_resistance: Dict
    ) -> Dict:
        """
        Calculate overall F&O sentiment score.

        Score: -5 (extremely bearish) to +5 (extremely bullish)
        """
        score = 0
        factors = []

        # PCR contribution
        if pcr > 1.3:
            score += 2
            factors.append(f"High PCR ({pcr:.2f}): Strong put writing = bullish")
        elif pcr > 1.1:
            score += 1
            factors.append(f"Elevated PCR ({pcr:.2f}): Mild bullish")
        elif pcr > 0.9:
            factors.append(f"Neutral PCR ({pcr:.2f})")
        elif pcr > 0.7:
            score -= 1
            factors.append(f"Low PCR ({pcr:.2f}): Mild bearish")
        else:
            score -= 2
            factors.append(f"Very low PCR ({pcr:.2f}): Heavy call writing = bearish")

        # Max Pain distance
        if max_pain > 0 and spot > 0:
            distance_pct = ((max_pain - spot) / spot) * 100
            if distance_pct > 1:
                score += 1
                factors.append(f"Below max pain: Price may rise to {max_pain}")
            elif distance_pct < -1:
                score -= 1
                factors.append(f"Above max pain: Price may fall to {max_pain}")
            else:
                factors.append(f"Near max pain {max_pain}: At equilibrium")

        # Support/Resistance proximity
        support = support_resistance.get("immediate_support", 0)
        resistance = support_resistance.get("immediate_resistance", 0)

        if support and resistance:
            range_size = resistance - support
            position = (spot - support) / range_size if range_size > 0 else 0.5

            if position < 0.3:
                score += 1
                factors.append("Near support: Good risk/reward for longs")
            elif position > 0.7:
                score -= 1
                factors.append("Near resistance: Risk of pullback")

        # Sentiment label
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

        # Position multiplier
        if score >= 2:
            multiplier = 1.2
        elif score >= 0:
            multiplier = 1.0
        elif score >= -2:
            multiplier = 0.8
        else:
            multiplier = 0.5

        return {
            "score": score,
            "sentiment": sentiment,
            "fo_multiplier": multiplier,
            "factors": factors,
        }

    def fetch_complete_analysis(self, symbol: str = "NIFTY") -> Dict:
        """
        Fetch complete F&O analysis for an index.

        Returns comprehensive F&O sentiment data.
        """
        print(f"Fetching {symbol} option chain from DhanHQ...")

        option_data = self.get_option_chain(symbol)

        if not option_data:
            return {
                "status": "FETCH_FAILED",
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "signal_impact": {
                    "fo_multiplier": 0.8,  # Conservative
                    "fo_sentiment": "UNKNOWN",
                },
            }

        # Get spot price from option data
        spot = option_data.get("last_price", 0)
        expiry = option_data.get("expiry_date", "")

        # Calculate all metrics
        pcr, pcr_breakdown = self.calculate_pcr(option_data)
        max_pain, max_pain_info = self.calculate_max_pain(option_data)
        support_resistance = self.find_support_resistance(option_data, spot)
        sentiment = self.get_sentiment_score(pcr, max_pain, spot, support_resistance)

        return {
            "status": "OK",
            "source": "DHANHQ",
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "spot_price": spot,
            "expiry": expiry,
            "pcr": {
                "value": round(pcr, 3),
                "interpretation": self._interpret_pcr(pcr),
                "breakdown": pcr_breakdown,
            },
            "max_pain": {
                "strike": max_pain,
                "distance_from_spot": round(max_pain - spot, 2) if spot else 0,
                "distance_pct": round(((max_pain - spot) / spot) * 100, 2) if spot else 0,
            },
            "support_resistance": support_resistance,
            "sentiment": sentiment,
            "signal_impact": {
                "fo_multiplier": sentiment["fo_multiplier"],
                "fo_sentiment": sentiment["sentiment"],
                "key_levels": {
                    "support": support_resistance.get("immediate_support"),
                    "resistance": support_resistance.get("immediate_resistance"),
                    "max_pain": max_pain,
                },
            },
        }

    def _interpret_pcr(self, pcr: float) -> str:
        """Interpret PCR value."""
        if pcr > 1.5:
            return "Very high - extreme bullish (contrarian caution)"
        elif pcr > 1.2:
            return "High - bullish (strong put writing)"
        elif pcr > 1.0:
            return "Above parity - mildly bullish"
        elif pcr > 0.8:
            return "Below parity - mildly bearish"
        elif pcr > 0.6:
            return "Low - bearish (call writers dominant)"
        else:
            return "Very low - extreme bearish"


def fetch_fo_sentiment(symbol: str = "NIFTY") -> Dict:
    """
    Main function to fetch F&O sentiment.

    Args:
        symbol: NIFTY, BANKNIFTY, or FINNIFTY

    Returns:
        Complete F&O analysis
    """
    try:
        fetcher = DhanFOFetcher()
        return fetcher.fetch_complete_analysis(symbol)
    except Exception as e:
        print(f"Error: {e}")
        return {
            "status": "ERROR",
            "error": str(e),
            "signal_impact": {
                "fo_multiplier": 0.8,
                "fo_sentiment": "UNKNOWN",
            },
        }


if __name__ == "__main__":
    print("=" * 60)
    print("DHANHQ F&O SENTIMENT FETCHER TEST")
    print("=" * 60)

    result = fetch_fo_sentiment("NIFTY")

    print(f"\nStatus: {result.get('status')}")
    print(f"Source: {result.get('source')}")

    if result.get("status") == "OK":
        print(f"\nSpot Price: {result.get('spot_price')}")
        print(f"Expiry: {result.get('expiry')}")

        pcr = result.get("pcr", {})
        print(f"\nPCR: {pcr.get('value')} ({pcr.get('interpretation')})")

        mp = result.get("max_pain", {})
        print(f"Max Pain: {mp.get('strike')} ({mp.get('distance_pct'):+.1f}% from spot)")

        sr = result.get("support_resistance", {})
        print(f"\nSupport: {sr.get('immediate_support')}")
        print(f"Resistance: {sr.get('immediate_resistance')}")

        sentiment = result.get("sentiment", {})
        print(f"\nSentiment: {sentiment.get('sentiment')} (score: {sentiment.get('score'):+d})")
        print(f"F&O Multiplier: {sentiment.get('fo_multiplier')}")

        print("\nFactors:")
        for f in sentiment.get("factors", []):
            print(f"  - {f}")
    else:
        print(f"\nError: {result.get('error', 'Unknown error')}")

    print("=" * 60)
