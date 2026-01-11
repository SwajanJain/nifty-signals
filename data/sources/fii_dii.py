"""
FII/DII Flow Tracker - Track institutional money flows.

Critical insights:
- FII flows drive market direction in India
- DII provides counter-balance during FII selling
- Flow trends predict medium-term direction
- Large flows = high conviction moves

Smart money follows FII.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
import requests
from rich.console import Console

console = Console()


class FlowTrend(Enum):
    """Flow trend classification."""
    STRONG_INFLOW = "STRONG_INFLOW"
    INFLOW = "INFLOW"
    NEUTRAL = "NEUTRAL"
    OUTFLOW = "OUTFLOW"
    STRONG_OUTFLOW = "STRONG_OUTFLOW"


@dataclass
class DailyFlow:
    """Daily FII/DII flow data."""
    date: datetime
    fii_buy: float  # In Cr
    fii_sell: float
    fii_net: float
    dii_buy: float
    dii_sell: float
    dii_net: float
    total_net: float


@dataclass
class FlowAnalysis:
    """Complete flow analysis."""
    # Latest data
    latest_date: datetime
    fii_net_today: float
    dii_net_today: float
    total_net_today: float

    # Trends
    fii_5d_net: float
    fii_20d_net: float
    dii_5d_net: float
    dii_20d_net: float

    # Trend classification
    fii_trend: FlowTrend
    dii_trend: FlowTrend

    # Derived metrics
    fii_dii_ratio: float  # FII/DII net ratio
    flow_momentum: float  # Recent vs older flow
    institutional_conviction: str  # High/Medium/Low

    # Signals
    signals: List[str]
    score: int  # -5 to +5

    # Historical
    daily_flows: List[DailyFlow] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = []
        lines.append("=" * 60)
        lines.append("FII/DII FLOW ANALYSIS")
        lines.append("=" * 60)

        lines.append(f"\n[TODAY - {self.latest_date.strftime('%Y-%m-%d')}]")
        lines.append(f"FII Net: ₹{self.fii_net_today:,.0f} Cr")
        lines.append(f"DII Net: ₹{self.dii_net_today:,.0f} Cr")
        lines.append(f"Total: ₹{self.total_net_today:,.0f} Cr")

        lines.append(f"\n[TREND ANALYSIS]")
        lines.append(f"FII 5-Day: ₹{self.fii_5d_net:,.0f} Cr ({self.fii_trend.value})")
        lines.append(f"FII 20-Day: ₹{self.fii_20d_net:,.0f} Cr")
        lines.append(f"DII 5-Day: ₹{self.dii_5d_net:,.0f} Cr ({self.dii_trend.value})")
        lines.append(f"DII 20-Day: ₹{self.dii_20d_net:,.0f} Cr")

        lines.append(f"\n[SIGNALS]")
        for signal in self.signals:
            lines.append(f"  • {signal}")

        lines.append(f"\nFlow Score: {self.score:+d}")
        lines.append(f"Institutional Conviction: {self.institutional_conviction}")

        lines.append("=" * 60)
        return "\n".join(lines)


class FIIDIITracker:
    """
    Track FII/DII flows from NSE/NSDL.

    Data sources:
    - NSE daily FII/DII data
    - NSDL depositories data (more detailed)
    """

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        self._cache: Dict = {}
        self._cache_time: Optional[datetime] = None

    def fetch_nse_fii_dii(self, days: int = 30) -> List[DailyFlow]:
        """
        Fetch FII/DII data from NSE.

        Note: NSE API may require session/cookies.
        Falls back to cached/sample data if API fails.
        """
        try:
            url = "https://www.nseindia.com/api/fiidiiTradeReact"

            session = requests.Session()
            # Initialize session
            session.get("https://www.nseindia.com", headers=self.headers, timeout=10)

            response = session.get(url, headers=self.headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                return self._parse_nse_data(data)

        except Exception as e:
            console.print(f"[yellow]Could not fetch live FII/DII data: {e}[/yellow]")

        # Return sample data for development
        return self._get_sample_data(days)

    def _parse_nse_data(self, data: Dict) -> List[DailyFlow]:
        """Parse NSE FII/DII response."""
        flows = []

        try:
            for item in data:
                date_str = item.get('date', '')
                # Parse date
                try:
                    date = datetime.strptime(date_str, '%d-%b-%Y')
                except:
                    continue

                # FII data
                fii_buy = float(item.get('fii_buy_value', 0) or 0)
                fii_sell = float(item.get('fii_sell_value', 0) or 0)
                fii_net = fii_buy - fii_sell

                # DII data
                dii_buy = float(item.get('dii_buy_value', 0) or 0)
                dii_sell = float(item.get('dii_sell_value', 0) or 0)
                dii_net = dii_buy - dii_sell

                flows.append(DailyFlow(
                    date=date,
                    fii_buy=fii_buy,
                    fii_sell=fii_sell,
                    fii_net=fii_net,
                    dii_buy=dii_buy,
                    dii_sell=dii_sell,
                    dii_net=dii_net,
                    total_net=fii_net + dii_net
                ))

        except Exception as e:
            console.print(f"[yellow]Error parsing NSE data: {e}[/yellow]")

        return sorted(flows, key=lambda x: x.date, reverse=True)

    def _get_sample_data(self, days: int = 30) -> List[DailyFlow]:
        """Generate sample data for development/testing."""
        flows = []
        base_date = datetime.now()

        # Simulate realistic flow patterns
        np.random.seed(42)

        for i in range(days):
            date = base_date - timedelta(days=i)

            # Skip weekends
            if date.weekday() >= 5:
                continue

            # FII tends to have larger swings
            fii_net = np.random.normal(0, 1500)  # Mean 0, std 1500 Cr
            # DII often counters FII
            dii_net = -fii_net * 0.5 + np.random.normal(0, 800)

            fii_buy = max(0, 5000 + fii_net/2 + np.random.normal(0, 500))
            fii_sell = max(0, fii_buy - fii_net)
            dii_buy = max(0, 4000 + dii_net/2 + np.random.normal(0, 400))
            dii_sell = max(0, dii_buy - dii_net)

            flows.append(DailyFlow(
                date=date,
                fii_buy=fii_buy,
                fii_sell=fii_sell,
                fii_net=fii_net,
                dii_buy=dii_buy,
                dii_sell=dii_sell,
                dii_net=dii_net,
                total_net=fii_net + dii_net
            ))

        return sorted(flows, key=lambda x: x.date, reverse=True)

    def analyze_flows(self, days: int = 30) -> FlowAnalysis:
        """
        Analyze FII/DII flows and generate insights.

        Returns comprehensive flow analysis.
        """
        flows = self.fetch_nse_fii_dii(days)

        if not flows:
            return self._empty_analysis()

        # Latest day
        latest = flows[0]

        # Calculate rolling sums
        fii_5d = sum(f.fii_net for f in flows[:5])
        fii_20d = sum(f.fii_net for f in flows[:20])
        dii_5d = sum(f.dii_net for f in flows[:5])
        dii_20d = sum(f.dii_net for f in flows[:20])

        # Classify trends
        fii_trend = self._classify_trend(fii_5d, fii_20d)
        dii_trend = self._classify_trend(dii_5d, dii_20d)

        # FII/DII ratio
        if abs(dii_5d) > 100:
            fii_dii_ratio = fii_5d / abs(dii_5d)
        else:
            fii_dii_ratio = 0

        # Flow momentum (recent 5d vs previous 5d)
        fii_prev_5d = sum(f.fii_net for f in flows[5:10]) if len(flows) >= 10 else 0
        if abs(fii_prev_5d) > 100:
            flow_momentum = (fii_5d - fii_prev_5d) / abs(fii_prev_5d)
        else:
            flow_momentum = 0

        # Generate signals
        signals, score = self._generate_signals(
            latest, fii_5d, fii_20d, dii_5d, dii_20d, fii_trend, dii_trend
        )

        # Institutional conviction
        if abs(score) >= 3:
            conviction = "HIGH"
        elif abs(score) >= 1:
            conviction = "MEDIUM"
        else:
            conviction = "LOW"

        return FlowAnalysis(
            latest_date=latest.date,
            fii_net_today=latest.fii_net,
            dii_net_today=latest.dii_net,
            total_net_today=latest.total_net,
            fii_5d_net=fii_5d,
            fii_20d_net=fii_20d,
            dii_5d_net=dii_5d,
            dii_20d_net=dii_20d,
            fii_trend=fii_trend,
            dii_trend=dii_trend,
            fii_dii_ratio=fii_dii_ratio,
            flow_momentum=flow_momentum,
            institutional_conviction=conviction,
            signals=signals,
            score=score,
            daily_flows=flows
        )

    def _classify_trend(self, flow_5d: float, flow_20d: float) -> FlowTrend:
        """Classify flow trend."""
        if flow_5d > 5000:
            return FlowTrend.STRONG_INFLOW
        elif flow_5d > 1000:
            return FlowTrend.INFLOW
        elif flow_5d < -5000:
            return FlowTrend.STRONG_OUTFLOW
        elif flow_5d < -1000:
            return FlowTrend.OUTFLOW
        else:
            return FlowTrend.NEUTRAL

    def _generate_signals(
        self,
        latest: DailyFlow,
        fii_5d: float,
        fii_20d: float,
        dii_5d: float,
        dii_20d: float,
        fii_trend: FlowTrend,
        dii_trend: FlowTrend
    ) -> Tuple[List[str], int]:
        """Generate trading signals from flow analysis."""
        signals = []
        score = 0

        # FII trend signals
        if fii_trend == FlowTrend.STRONG_INFLOW:
            signals.append(f"FII STRONG INFLOW: ₹{fii_5d:,.0f} Cr in 5 days")
            score += 2
        elif fii_trend == FlowTrend.INFLOW:
            signals.append(f"FII buying: ₹{fii_5d:,.0f} Cr in 5 days")
            score += 1
        elif fii_trend == FlowTrend.STRONG_OUTFLOW:
            signals.append(f"FII HEAVY SELLING: ₹{abs(fii_5d):,.0f} Cr in 5 days")
            score -= 2
        elif fii_trend == FlowTrend.OUTFLOW:
            signals.append(f"FII selling: ₹{abs(fii_5d):,.0f} Cr in 5 days")
            score -= 1

        # DII counter-flow (bullish when DII absorbs FII selling)
        if fii_5d < -2000 and dii_5d > 1500:
            signals.append("DII absorbing FII selling - Support")
            score += 1

        # Large single-day moves
        if latest.fii_net > 2000:
            signals.append(f"Large FII buying today: ₹{latest.fii_net:,.0f} Cr")
            score += 1
        elif latest.fii_net < -2000:
            signals.append(f"Large FII selling today: ₹{abs(latest.fii_net):,.0f} Cr")
            score -= 1

        # Trend acceleration/deceleration
        if fii_5d > 0 and fii_5d > fii_20d * 0.5:
            signals.append("FII buying accelerating")
            score += 1
        elif fii_5d < 0 and fii_5d < fii_20d * 0.5:
            signals.append("FII selling accelerating")
            score -= 1

        # Monthly trend
        if fii_20d > 10000:
            signals.append(f"Strong monthly FII inflow: ₹{fii_20d:,.0f} Cr")
        elif fii_20d < -10000:
            signals.append(f"Strong monthly FII outflow: ₹{abs(fii_20d):,.0f} Cr")

        return signals, max(-5, min(5, score))

    def _empty_analysis(self) -> FlowAnalysis:
        """Return empty analysis when data unavailable."""
        return FlowAnalysis(
            latest_date=datetime.now(),
            fii_net_today=0,
            dii_net_today=0,
            total_net_today=0,
            fii_5d_net=0,
            fii_20d_net=0,
            dii_5d_net=0,
            dii_20d_net=0,
            fii_trend=FlowTrend.NEUTRAL,
            dii_trend=FlowTrend.NEUTRAL,
            fii_dii_ratio=0,
            flow_momentum=0,
            institutional_conviction="LOW",
            signals=["Data unavailable"],
            score=0
        )

    def get_flow_score(self) -> int:
        """Quick function to get flow score (-5 to +5)."""
        analysis = self.analyze_flows(10)
        return analysis.score

    def should_reduce_exposure(self) -> Tuple[bool, str]:
        """
        Check if FII flows suggest reducing exposure.

        Returns (should_reduce, reason)
        """
        analysis = self.analyze_flows(10)

        if analysis.fii_trend == FlowTrend.STRONG_OUTFLOW:
            return True, f"Heavy FII selling: ₹{abs(analysis.fii_5d_net):,.0f} Cr in 5 days"

        if analysis.fii_net_today < -3000:
            return True, f"Large FII selling today: ₹{abs(analysis.fii_net_today):,.0f} Cr"

        return False, ""


def get_quick_flow_summary() -> Dict:
    """Quick function to get flow summary for dashboard."""
    tracker = FIIDIITracker()
    analysis = tracker.analyze_flows(10)

    return {
        'fii_today': analysis.fii_net_today,
        'dii_today': analysis.dii_net_today,
        'fii_5d': analysis.fii_5d_net,
        'fii_trend': analysis.fii_trend.value,
        'score': analysis.score,
        'conviction': analysis.institutional_conviction,
        'signals': analysis.signals[:3]
    }
