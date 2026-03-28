"""
Robust FII/DII Data Fetcher - Multiple Sources with Fallback

Sources (in priority order):
1. NSE Direct API (official, may fail due to anti-bot)
2. NSDL FPI Data (official, daily publication)
3. Screener.in (reliable, free)
4. Fallback to conservative estimates

This solves the Druckenmiller Gate requirement:
"Never trade without knowing what big money is doing"
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import warnings

warnings.filterwarnings("ignore")

import requests
import pandas as pd
from bs4 import BeautifulSoup

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


class FIIDIIFetcher:
    """
    Multi-source FII/DII data fetcher with automatic fallback.

    Druckenmiller: "Follow the big money"
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.cache_dir = PROJECT_ROOT / ".cache"
        self.cache_dir.mkdir(exist_ok=True)

    def fetch_from_nse(self) -> Optional[Dict]:
        """
        Source 1: NSE Direct API

        Official source but has aggressive anti-bot protection.
        """
        try:
            # First get cookies from main page
            self.session.get("https://www.nseindia.com", timeout=10)

            # Then fetch FII/DII data
            url = "https://www.nseindia.com/api/fiidiiTradeReact"
            self.session.headers["Referer"] = "https://www.nseindia.com/reports-indices-current-market-statistics"

            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return None

            data = response.json()
            if not data or not isinstance(data, list):
                return None

            result = {"source": "NSE_DIRECT", "timestamp": datetime.now().isoformat()}

            for record in data:
                category = record.get("category", "").upper()
                if "FII" in category or "FPI" in category:
                    result["fii"] = {
                        "buy": self._parse_number(record.get("buyValue", 0)),
                        "sell": self._parse_number(record.get("sellValue", 0)),
                        "net": self._parse_number(record.get("netValue", 0)),
                        "date": record.get("date"),
                    }
                elif "DII" in category:
                    result["dii"] = {
                        "buy": self._parse_number(record.get("buyValue", 0)),
                        "sell": self._parse_number(record.get("sellValue", 0)),
                        "net": self._parse_number(record.get("netValue", 0)),
                        "date": record.get("date"),
                    }

            if "fii" in result:
                return result
            return None

        except Exception as e:
            print(f"NSE fetch failed: {e}")
            return None

    def fetch_from_screener(self) -> Optional[Dict]:
        """
        Source 2: Screener.in

        Reliable free source with historical data.
        """
        try:
            url = "https://www.screener.in/api/fii/"
            response = self.session.get(url, timeout=15)

            if response.status_code != 200:
                return None

            data = response.json()
            if not data:
                return None

            # Get latest entry
            if isinstance(data, list) and len(data) > 0:
                latest = data[0]

                return {
                    "source": "SCREENER",
                    "timestamp": datetime.now().isoformat(),
                    "fii": {
                        "buy": latest.get("fii_buy", 0),
                        "sell": latest.get("fii_sell", 0),
                        "net": latest.get("fii_net", 0),
                        "date": latest.get("date"),
                    },
                    "dii": {
                        "buy": latest.get("dii_buy", 0),
                        "sell": latest.get("dii_sell", 0),
                        "net": latest.get("dii_net", 0),
                        "date": latest.get("date"),
                    },
                    "historical_5d": data[:5] if len(data) >= 5 else data,
                }

            return None

        except Exception as e:
            print(f"Screener fetch failed: {e}")
            return None

    def fetch_from_moneycontrol(self) -> Optional[Dict]:
        """
        Source 3: MoneyControl

        Scrapes the FII/DII page for latest data.
        """
        try:
            url = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/data.html"
            response = self.session.get(url, timeout=15)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the data table
            tables = soup.find_all('table')

            # Parse FII/DII values from table
            # This is a simplified parser - adjust based on actual HTML
            fii_net = 0
            dii_net = 0

            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 4:
                        text = cells[0].get_text().strip().upper()
                        if 'FII' in text or 'FPI' in text:
                            try:
                                fii_net = self._parse_number(cells[-1].get_text())
                            except:
                                pass
                        elif 'DII' in text:
                            try:
                                dii_net = self._parse_number(cells[-1].get_text())
                            except:
                                pass

            if fii_net != 0 or dii_net != 0:
                return {
                    "source": "MONEYCONTROL",
                    "timestamp": datetime.now().isoformat(),
                    "fii": {"net": fii_net},
                    "dii": {"net": dii_net},
                }

            return None

        except Exception as e:
            print(f"MoneyControl fetch failed: {e}")
            return None

    def get_cached_data(self) -> Optional[Dict]:
        """
        Get last known good data from cache.
        """
        cache_file = self.cache_dir / "fii_dii_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    # Check if data is less than 2 days old
                    cache_time = datetime.fromisoformat(data.get("timestamp", "2020-01-01"))
                    if datetime.now() - cache_time < timedelta(days=2):
                        data["source"] = "CACHE"
                        return data
            except:
                pass
        return None

    def save_to_cache(self, data: Dict) -> None:
        """Save data to cache for fallback."""
        cache_file = self.cache_dir / "fii_dii_cache.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except:
            pass

    def fetch(self) -> Dict:
        """
        Fetch FII/DII data with automatic fallback.

        Priority:
        1. NSE Direct
        2. Screener.in
        3. MoneyControl
        4. Cache
        5. Conservative estimate
        """
        # Try sources in order
        sources = [
            ("NSE", self.fetch_from_nse),
            ("SCREENER", self.fetch_from_screener),
            ("MONEYCONTROL", self.fetch_from_moneycontrol),
        ]

        for name, fetch_func in sources:
            print(f"Trying {name}...")
            data = fetch_func()
            if data and "fii" in data:
                print(f"SUCCESS: {name}")
                self.save_to_cache(data)
                return self._calculate_metrics(data)

        # Try cache
        print("Trying cache...")
        cached = self.get_cached_data()
        if cached:
            print("SUCCESS: Using cached data")
            return self._calculate_metrics(cached)

        # Conservative fallback
        print("All sources failed - using conservative estimates")
        return self._conservative_fallback()

    def _calculate_metrics(self, data: Dict) -> Dict:
        """Calculate derived metrics from FII/DII data."""
        fii_net = data.get("fii", {}).get("net", 0)
        dii_net = data.get("dii", {}).get("net", 0)

        # Load historical data for 5-day trend
        fii_5d, dii_5d = self._load_history()

        # Trend classification
        if fii_net > 500:
            fii_trend = "STRONG_BUYING"
        elif fii_net > 0:
            fii_trend = "BUYING"
        elif fii_net > -500:
            fii_trend = "MILD_SELLING"
        elif fii_net > -2000:
            fii_trend = "SELLING"
        else:
            fii_trend = "HEAVY_SELLING"

        # DII absorption check (Druckenmiller insight)
        dii_absorbing = dii_net > 0 and fii_net < 0 and dii_net >= abs(fii_net) * 0.5

        # Calculate flow multiplier for position sizing
        if fii_net < -3000:
            flow_multiplier = 0.3
        elif fii_net < -2000 and not dii_absorbing:
            flow_multiplier = 0.5
        elif fii_net < -1000 and not dii_absorbing:
            flow_multiplier = 0.7
        elif dii_absorbing:
            flow_multiplier = 0.9
        else:
            flow_multiplier = 1.0

        # Consecutive selling days
        consecutive_selling = 0
        for val in fii_5d:
            if val < 0:
                consecutive_selling += 1
            else:
                break

        return {
            "status": "OK",
            "source": data.get("source"),
            "timestamp": data.get("timestamp"),
            "data_date": data.get("fii", {}).get("date"),
            "fii": {
                "net": fii_net,
                "trend": fii_trend,
                "5d_total": sum(fii_5d) if fii_5d else fii_net,
                "consecutive_selling_days": consecutive_selling,
            },
            "dii": {
                "net": dii_net,
                "absorbing_fii": dii_absorbing,
            },
            "signal_impact": {
                "flow_multiplier": flow_multiplier,
                "druckenmiller_gate": fii_trend != "HEAVY_SELLING",
                "recommendation": self._get_recommendation(fii_trend, dii_absorbing, flow_multiplier),
            },
        }

    def _conservative_fallback(self) -> Dict:
        """Return conservative estimates when all sources fail."""
        return {
            "status": "FALLBACK",
            "source": "CONSERVATIVE_ESTIMATE",
            "timestamp": datetime.now().isoformat(),
            "fii": {
                "net": 0,
                "trend": "UNKNOWN",
                "5d_total": 0,
                "consecutive_selling_days": 0,
            },
            "dii": {
                "net": 0,
                "absorbing_fii": False,
            },
            "signal_impact": {
                "flow_multiplier": 0.7,  # Conservative
                "druckenmiller_gate": False,  # Fail safe
                "recommendation": "FII/DII data unavailable - reduce position size by 30%",
            },
        }

    def _load_history(self) -> Tuple[list, list]:
        """Load historical FII/DII data."""
        history_file = self.cache_dir / "fii_dii_history.json"
        if history_file.exists():
            try:
                with open(history_file, "r") as f:
                    data = json.load(f)
                    return data.get("fii", [])[-5:], data.get("dii", [])[-5:]
            except:
                pass
        return [], []

    def _get_recommendation(self, fii_trend: str, dii_absorbing: bool, multiplier: float) -> str:
        """Generate actionable recommendation."""
        if fii_trend == "HEAVY_SELLING":
            return "CAUTION: Heavy FII selling - avoid new longs, protect existing positions"
        elif fii_trend == "SELLING" and not dii_absorbing:
            return "CAUTION: FII selling without DII absorption - reduce position size"
        elif dii_absorbing:
            return "NEUTRAL: DII absorbing FII selling - consolidation likely, not panic"
        elif fii_trend == "STRONG_BUYING":
            return "BULLISH: Strong FII buying - trend likely to continue"
        else:
            return "NORMAL: Neutral institutional flows"

    def _parse_number(self, s) -> float:
        """Parse Indian number format."""
        if not s or s == "-" or s == "NA":
            return 0.0
        s = str(s).strip()
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        s = s.replace(",", "").replace("₹", "").replace("Rs", "")
        try:
            return float(s)
        except:
            return 0.0


def fetch_fii_dii() -> Dict:
    """Main function to fetch FII/DII data."""
    fetcher = FIIDIIFetcher()
    return fetcher.fetch()


if __name__ == "__main__":
    print("=" * 60)
    print("FII/DII DATA FETCHER TEST")
    print("=" * 60)

    result = fetch_fii_dii()

    print(f"\nSource: {result.get('source')}")
    print(f"Status: {result.get('status')}")
    print(f"\nFII Net: {result.get('fii', {}).get('net', 0):+,.0f} Cr")
    print(f"FII Trend: {result.get('fii', {}).get('trend')}")
    print(f"\nDII Net: {result.get('dii', {}).get('net', 0):+,.0f} Cr")
    print(f"DII Absorbing: {result.get('dii', {}).get('absorbing_fii')}")
    print(f"\nFlow Multiplier: {result.get('signal_impact', {}).get('flow_multiplier')}")
    print(f"Druckenmiller Gate: {'PASS' if result.get('signal_impact', {}).get('druckenmiller_gate') else 'FAIL'}")
    print(f"\nRecommendation: {result.get('signal_impact', {}).get('recommendation')}")
