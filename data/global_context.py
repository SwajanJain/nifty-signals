"""
Global Market Context Fetcher

Paul Tudor Jones principle: "Markets are connected."

Fetches:
- US indices (S&P 500, Nasdaq, Dow)
- Dollar index and USD/INR
- Crude oil and Gold
- Asian indices (when available)

This data is CRITICAL for Indian market trading.
"""

import yfinance as yf
import pandas as pd
from typing import Dict, Optional
from datetime import datetime, timedelta


class GlobalContextFetcher:
    """
    Fetch global market context before Indian market opens.

    PTJ: "Defense first. Know what's happening globally."
    """

    def __init__(self):
        self.symbols = {
            # US Indices
            'sp500': '^GSPC',
            'nasdaq': '^IXIC',
            'dow': '^DJI',
            'vix': '^VIX',

            # Currencies
            'dxy': 'DX-Y.NYB',      # Dollar Index
            'usdinr': 'USDINR=X',   # USD/INR

            # Commodities
            'crude': 'CL=F',        # WTI Crude
            'gold': 'GC=F',         # Gold

            # Asian (may not always be available)
            'nikkei': '^N225',
            'hangseng': '^HSI',
        }

    def fetch_all(self) -> Dict:
        """
        Fetch all global context data.

        Returns comprehensive global context with risk assessment.
        """
        context = {
            'status': 'OK',
            'timestamp': datetime.now().isoformat(),
            'markets': {},
            'risk_factors': [],
            'risk_sentiment': 'NEUTRAL'
        }

        risk_score = 0  # Higher = more risk-off

        for name, symbol in self.symbols.items():
            try:
                data = self._fetch_symbol(symbol)
                if data:
                    context['markets'][name] = data

                    # Assess risk contribution
                    risk_score += self._assess_risk(name, data)
            except Exception as e:
                context['markets'][name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }

        # Determine overall risk sentiment
        if risk_score >= 4:
            context['risk_sentiment'] = 'RISK_OFF'
            context['risk_factors'].append("Multiple global risk factors triggered")
        elif risk_score >= 2:
            context['risk_sentiment'] = 'CAUTIOUS'
        elif risk_score <= -2:
            context['risk_sentiment'] = 'RISK_ON'
        else:
            context['risk_sentiment'] = 'NEUTRAL'

        context['risk_score'] = risk_score

        # Add summary for quick reference
        context['summary'] = self._generate_summary(context)

        return context

    def _fetch_symbol(self, symbol: str) -> Optional[Dict]:
        """Fetch data for a single symbol."""
        try:
            df = yf.download(symbol, period='5d', progress=False)

            if len(df) < 2:
                return None

            current = df['Close'].iloc[-1]
            previous = df['Close'].iloc[-2]
            first = df['Close'].iloc[0]

            change_1d = (current - previous) / previous * 100
            change_5d = (current - first) / first * 100

            return {
                'price': round(float(current), 2),
                'change_1d': round(float(change_1d), 2),
                'change_5d': round(float(change_5d), 2),
                'trend_5d': 'UP' if change_5d > 1 else 'DOWN' if change_5d < -1 else 'FLAT',
                'status': 'OK'
            }
        except Exception as e:
            return None

    def _assess_risk(self, name: str, data: Dict) -> int:
        """
        Assess risk contribution from a single market.

        Returns: -2 to +2 (negative = risk-on, positive = risk-off)
        """
        if data.get('status') != 'OK':
            return 0

        change = data.get('change_1d', 0)
        score = 0

        if name == 'sp500':
            # S&P drop is risk-off
            if change < -2:
                score += 2
            elif change < -1:
                score += 1
            elif change > 1:
                score -= 1

        elif name == 'vix':
            # VIX spike is risk-off
            price = data.get('price', 15)
            if price > 25:
                score += 2
            elif price > 20:
                score += 1
            elif price < 12:
                score -= 1

        elif name == 'crude':
            # Crude spike is bad for India (imports 85%)
            if change > 5:
                score += 2
            elif change > 3:
                score += 1
            elif change < -3:
                score -= 1

        elif name == 'usdinr':
            # INR depreciation is risk-off (FII outflow)
            if change > 1:
                score += 2
            elif change > 0.5:
                score += 1
            elif change < -0.5:
                score -= 1

        elif name == 'dxy':
            # Strong dollar is bad for EMs
            if change > 1:
                score += 1
            elif change < -1:
                score -= 1

        elif name == 'gold':
            # Gold up = safe haven demand = risk-off
            if change > 2:
                score += 1

        return score

    def _generate_summary(self, context: Dict) -> str:
        """Generate a human-readable summary."""
        markets = context.get('markets', {})

        sp500 = markets.get('sp500', {}).get('change_1d', 'N/A')
        vix = markets.get('vix', {}).get('price', 'N/A')
        crude = markets.get('crude', {}).get('change_1d', 'N/A')
        usdinr = markets.get('usdinr', {}).get('change_1d', 'N/A')

        sentiment = context.get('risk_sentiment', 'UNKNOWN')

        return (
            f"Global: {sentiment} | "
            f"S&P: {sp500:+.1f}% | " if isinstance(sp500, float) else f"S&P: N/A | "
            f"VIX: {vix:.1f} | " if isinstance(vix, float) else f"VIX: N/A | "
            f"Crude: {crude:+.1f}% | " if isinstance(crude, float) else f"Crude: N/A | "
            f"USDINR: {usdinr:+.2f}%" if isinstance(usdinr, float) else f"USDINR: N/A"
        )

    def get_risk_assessment(self) -> Dict:
        """
        Get a simplified risk assessment for quick decisions.

        PTJ: "Know the global context before trading."
        """
        context = self.fetch_all()

        markets = context.get('markets', {})

        # Extract key metrics
        sp500_change = markets.get('sp500', {}).get('change_1d', 0)
        vix_level = markets.get('vix', {}).get('price', 15)
        crude_change = markets.get('crude', {}).get('change_1d', 0)
        usdinr_change = markets.get('usdinr', {}).get('change_1d', 0)

        # Build risk factors list
        risk_factors = []

        if sp500_change < -2:
            risk_factors.append(f"US sell-off ({sp500_change:.1f}%)")
        if vix_level > 20:
            risk_factors.append(f"VIX elevated ({vix_level:.1f})")
        if crude_change > 3:
            risk_factors.append(f"Crude spike ({crude_change:.1f}%)")
        if usdinr_change > 0.5:
            risk_factors.append(f"INR weakness ({usdinr_change:.2f}%)")

        # Recommendation
        if len(risk_factors) >= 3:
            recommendation = "NO_TRADE"
            position_multiplier = 0
        elif len(risk_factors) >= 2:
            recommendation = "REDUCE_SIZE"
            position_multiplier = 0.5
        elif len(risk_factors) >= 1:
            recommendation = "CAUTION"
            position_multiplier = 0.8
        else:
            recommendation = "NORMAL"
            position_multiplier = 1.0

        return {
            'status': 'OK',
            'risk_sentiment': context.get('risk_sentiment'),
            'risk_score': context.get('risk_score'),
            'risk_factors': risk_factors,
            'recommendation': recommendation,
            'position_multiplier': position_multiplier,
            'sp500': markets.get('sp500', {}),
            'vix': markets.get('vix', {}),
            'crude': markets.get('crude', {}),
            'usdinr': markets.get('usdinr', {}),
            'summary': context.get('summary')
        }


def build_global_context() -> Dict:
    """
    Main function to build global context.

    Call this before Indian market opens (8:30-9:00 AM IST).
    """
    fetcher = GlobalContextFetcher()
    return fetcher.get_risk_assessment()


if __name__ == "__main__":
    # Test the fetcher
    print("Fetching global context...")
    context = build_global_context()

    print("\n" + "=" * 60)
    print("GLOBAL MARKET CONTEXT (PTJ Gate)")
    print("=" * 60)

    print(f"\nRisk Sentiment: {context.get('risk_sentiment')}")
    print(f"Risk Score: {context.get('risk_score')}")
    print(f"Position Multiplier: {context.get('position_multiplier')}")

    sp500 = context.get('sp500', {})
    vix = context.get('vix', {})
    crude = context.get('crude', {})
    usdinr = context.get('usdinr', {})

    if sp500.get('price'):
        print(f"\nS&P 500: {sp500.get('price')} ({sp500.get('change_1d', 0):+.1f}%)")
    if vix.get('price'):
        print(f"VIX: {vix.get('price')}")
    if crude.get('price'):
        print(f"Crude: {crude.get('price')} ({crude.get('change_1d', 0):+.1f}%)")
    if usdinr.get('price'):
        print(f"USD/INR: {usdinr.get('price')} ({usdinr.get('change_1d', 0):+.2f}%)")

    if context.get('risk_factors'):
        print(f"\nRisk Factors:")
        for factor in context.get('risk_factors', []):
            print(f"  - {factor}")

    print(f"\nRecommendation: {context.get('recommendation')}")
    print("=" * 60)
