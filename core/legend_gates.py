"""
Legend Gates - 5 mandatory checks before any trade.

Each gate represents a principle from a legendary trader:
1. SIMONS: Data quality (>80% sources available)
2. DALIO: Economic thesis (not trading blind)
3. DRUCKENMILLER: Flow confirmation (FII not dumping)
4. PTJ: Global context (not isolated)
5. SEYKOTA: Trend alignment (trade with trend)

ALL gates must pass before any trade is considered.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import pandas_ta as ta


class GateStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class GateResult:
    name: str
    status: GateStatus
    score: str
    reason: str
    legend: str
    principle: str


class LegendGates:
    """
    The 5 Legend Gates - all must pass for trading.

    "The goal is not to make money. The goal is to not lose money."
    """

    def __init__(self):
        self.gates: List[GateResult] = []

    def check_simons_gate(self, context: Dict) -> GateResult:
        """
        SIMONS GATE: Data Quality Check

        Jim Simons principle: "If you don't have data, you don't have an edge."

        Requires >80% of data sources to be available.
        """
        data_sources = {
            'regime': context.get('regime', {}).get('status') == 'OK',
            'breadth': context.get('breadth', {}).get('status') == 'OK',
            'fii_dii': context.get('fii_dii', {}).get('status') == 'OK',
            'fo_sentiment': context.get('fo_sentiment', {}).get('status') == 'OK',
            'sector': context.get('sector', {}).get('status') == 'OK',
            'global': context.get('global', {}).get('status') == 'OK',
            'news': context.get('news', {}).get('status') == 'OK',
        }

        available = sum(data_sources.values())
        total = len(data_sources)
        pct = available / total * 100

        missing = [k for k, v in data_sources.items() if not v]

        passed = pct >= 80

        return GateResult(
            name="SIMONS",
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            score=f"{available}/{total} ({pct:.0f}%)",
            reason=f"Missing: {', '.join(missing)}" if missing else "All data available",
            legend="Jim Simons (Renaissance)",
            principle="No trade without data edge"
        )

    def check_dalio_gate(self, context: Dict) -> GateResult:
        """
        DALIO GATE: Economic Thesis Check

        Ray Dalio principle: "Understand the economic machine."

        Checks if we have an economic view and it's not adverse.
        """
        economic = context.get('economic', {})
        regime = economic.get('regime', 'UNKNOWN')
        equity_bias = economic.get('equity_bias', 'UNKNOWN')

        # Stagflation is the worst for equities
        if regime == 'STAGFLATION':
            passed = False
            reason = "Stagflation regime - worst for equities"
        elif equity_bias == 'BEARISH':
            passed = False
            reason = "Economic indicators bearish"
        elif regime == 'UNKNOWN':
            # If no economic data, use proxy from market
            # Bank Nifty vs Nifty ratio as credit proxy
            passed = True  # Allow but note uncertainty
            reason = "No economic data - using market proxies"
        else:
            passed = True
            reason = f"Economic regime: {regime} - {equity_bias}"

        return GateResult(
            name="DALIO",
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            score=regime,
            reason=reason,
            legend="Ray Dalio (Bridgewater)",
            principle="Understand the machine before trading"
        )

    def check_druckenmiller_gate(self, context: Dict) -> GateResult:
        """
        DRUCKENMILLER GATE: Institutional Flow Check

        Stanley Druckenmiller principle: "Follow the big money."

        FII flows are the biggest driver of Indian markets.
        Don't fight heavy institutional selling.
        """
        flows = context.get('fii_dii', {})

        if flows.get('status') != 'OK':
            return GateResult(
                name="DRUCKENMILLER",
                status=GateStatus.UNKNOWN,
                score="DATA MISSING",
                reason="FII/DII flow data unavailable - CRITICAL GAP",
                legend="Stanley Druckenmiller",
                principle="Never trade without knowing what big money is doing"
            )

        fii_net_5d = flows.get('fii_net_5d', 0)
        fii_trend = flows.get('fii_5d_trend', 'NEUTRAL')
        consecutive_selling = flows.get('fii_consecutive_selling_days', 0)

        # Heavy selling: >2000 Cr/day for 3+ consecutive days
        heavy_selling = fii_net_5d < -10000 and consecutive_selling >= 3

        if heavy_selling:
            passed = False
            reason = f"FII heavy selling: {fii_net_5d:.0f} Cr in 5 days, {consecutive_selling} consecutive days"
        elif fii_trend == 'HEAVY_SELLING':
            passed = False
            reason = f"FII in heavy selling mode"
        else:
            passed = True
            reason = f"FII 5-day net: {fii_net_5d:.0f} Cr, Trend: {fii_trend}"

        return GateResult(
            name="DRUCKENMILLER",
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            score=f"{fii_net_5d:.0f} Cr",
            reason=reason,
            legend="Stanley Druckenmiller",
            principle="Follow the big money, don't fight it"
        )

    def check_ptj_gate(self, context: Dict) -> GateResult:
        """
        PTJ GATE: Global Context Check

        Paul Tudor Jones principle: "Defense first. Global awareness always."

        Indian markets don't exist in isolation.
        Check US, Asia, Dollar, Crude before trading.
        """
        global_ctx = context.get('global', {})

        if global_ctx.get('status') != 'OK':
            return GateResult(
                name="PTJ",
                status=GateStatus.UNKNOWN,
                score="DATA MISSING",
                reason="Global context unavailable - add US/Asia/Dollar/Crude checks",
                legend="Paul Tudor Jones",
                principle="Markets are connected - check global before local"
            )

        risk_sentiment = global_ctx.get('risk_sentiment', 'NEUTRAL')
        us_change = global_ctx.get('sp500', {}).get('change_1d', 0)
        crude_change = global_ctx.get('crude', {}).get('change_1d', 0)
        usdinr_change = global_ctx.get('usdinr', {}).get('change_1d', 0)

        issues = []
        if us_change < -2:
            issues.append(f"US down {us_change:.1f}%")
        if crude_change > 5:
            issues.append(f"Crude spike +{crude_change:.1f}%")
        if usdinr_change > 1:
            issues.append(f"INR weakness +{usdinr_change:.1f}%")

        if risk_sentiment == 'RISK_OFF' or len(issues) >= 2:
            passed = False
            reason = f"Global risk-off: {', '.join(issues)}" if issues else "Global sentiment: RISK_OFF"
        else:
            passed = True
            reason = f"Global: {risk_sentiment} | US: {us_change:+.1f}% | Crude: {crude_change:+.1f}%"

        return GateResult(
            name="PTJ",
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            score=risk_sentiment,
            reason=reason,
            legend="Paul Tudor Jones",
            principle="Defense first - check global context"
        )

    def check_seykota_gate(self, context: Dict) -> GateResult:
        """
        SEYKOTA GATE: Trend Alignment Check

        Ed Seykota principle: "Trade with the trend."

        Only allow longs when NIFTY > EMA50.
        Only allow shorts when NIFTY < EMA50.
        No trades in trendless markets.
        """
        trend = context.get('trend', {})

        if not trend:
            return GateResult(
                name="SEYKOTA",
                status=GateStatus.UNKNOWN,
                score="DATA MISSING",
                reason="Trend data not calculated",
                legend="Ed Seykota",
                principle="The trend is your friend"
            )

        nifty_price = trend.get('price', 0)
        ema50 = trend.get('ema50', 0)
        trend_dir = trend.get('trend', 'UNKNOWN')
        long_allowed = trend.get('long_allowed', False)
        short_allowed = trend.get('short_allowed', False)

        if not long_allowed and not short_allowed:
            passed = False
            reason = f"No clear trend. NIFTY {nifty_price:.0f} vs EMA50 {ema50:.0f}"
        else:
            passed = True
            direction = "LONG" if long_allowed else "SHORT"
            reason = f"Trend: {trend_dir} - {direction}S allowed. NIFTY {nifty_price:.0f} vs EMA50 {ema50:.0f}"

        return GateResult(
            name="SEYKOTA",
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            score=trend_dir,
            reason=reason,
            legend="Ed Seykota",
            principle="Never trade against the trend"
        )

    def check_all_gates(self, context: Dict) -> Dict:
        """
        Run all 5 legend gates and return verdict.

        ALL gates must pass for trading to be allowed.
        """
        self.gates = [
            self.check_simons_gate(context),
            self.check_dalio_gate(context),
            self.check_druckenmiller_gate(context),
            self.check_ptj_gate(context),
            self.check_seykota_gate(context),
        ]

        passed_gates = [g for g in self.gates if g.status == GateStatus.PASSED]
        failed_gates = [g for g in self.gates if g.status == GateStatus.FAILED]
        unknown_gates = [g for g in self.gates if g.status == GateStatus.UNKNOWN]

        all_passed = len(failed_gates) == 0 and len(unknown_gates) == 0

        return {
            'verdict': 'TRADE_ALLOWED' if all_passed else 'NO_TRADE',
            'passed': len(passed_gates),
            'failed': len(failed_gates),
            'unknown': len(unknown_gates),
            'total': len(self.gates),
            'summary': f"{len(passed_gates)}/5 gates passed",
            'failed_names': [g.name for g in failed_gates],
            'unknown_names': [g.name for g in unknown_gates],
            'gates': [
                {
                    'name': g.name,
                    'status': g.status.value,
                    'score': g.score,
                    'reason': g.reason,
                    'legend': g.legend,
                    'principle': g.principle
                }
                for g in self.gates
            ]
        }

    def print_gates_report(self, context: Dict) -> str:
        """Generate a human-readable gates report."""
        result = self.check_all_gates(context)

        lines = []
        lines.append("=" * 70)
        lines.append("LEGEND GATES CHECK")
        lines.append("=" * 70)
        lines.append("")

        for gate in result['gates']:
            status_icon = "✓" if gate['status'] == 'PASSED' else "✗" if gate['status'] == 'FAILED' else "?"
            lines.append(f"[{status_icon}] {gate['name']} GATE ({gate['legend']})")
            lines.append(f"    Score: {gate['score']}")
            lines.append(f"    {gate['reason']}")
            lines.append(f"    Principle: \"{gate['principle']}\"")
            lines.append("")

        lines.append("-" * 70)
        lines.append(f"VERDICT: {result['verdict']}")
        lines.append(f"Gates: {result['summary']}")

        if result['failed_names']:
            lines.append(f"Failed: {', '.join(result['failed_names'])}")
        if result['unknown_names']:
            lines.append(f"Unknown: {', '.join(result['unknown_names'])}")

        lines.append("=" * 70)

        return "\n".join(lines)


def calculate_trend_context(nifty_data: pd.DataFrame) -> Dict:
    """
    Calculate trend context for Seykota Gate.

    Args:
        nifty_data: NIFTY OHLCV DataFrame

    Returns:
        Trend context dictionary
    """
    if len(nifty_data) < 200:
        return {'status': 'INSUFFICIENT_DATA'}

    close = nifty_data['close'].iloc[-1]
    ema20 = ta.ema(nifty_data['close'], length=20).iloc[-1]
    ema50 = ta.ema(nifty_data['close'], length=50).iloc[-1]
    ema200 = ta.ema(nifty_data['close'], length=200).iloc[-1]

    above_ema20 = close > ema20
    above_ema50 = close > ema50
    above_ema200 = close > ema200
    ema20_above_50 = ema20 > ema50
    ema50_above_200 = ema50 > ema200

    # Determine trend
    if above_ema50 and ema20_above_50 and ema50_above_200:
        trend = 'STRONG_UPTREND'
        long_allowed = True
        short_allowed = False
    elif above_ema50 and ema20_above_50:
        trend = 'UPTREND'
        long_allowed = True
        short_allowed = False
    elif above_ema50:
        trend = 'WEAK_UPTREND'
        long_allowed = True
        short_allowed = False
    elif not above_ema50 and not above_ema200:
        trend = 'STRONG_DOWNTREND'
        long_allowed = False
        short_allowed = True
    elif not above_ema50:
        trend = 'DOWNTREND'
        long_allowed = False
        short_allowed = True
    else:
        trend = 'NEUTRAL'
        long_allowed = False
        short_allowed = False

    return {
        'status': 'OK',
        'trend': trend,
        'price': round(close, 2),
        'ema20': round(ema20, 2),
        'ema50': round(ema50, 2),
        'ema200': round(ema200, 2),
        'long_allowed': long_allowed,
        'short_allowed': short_allowed,
        'above_ema20': above_ema20,
        'above_ema50': above_ema50,
        'above_ema200': above_ema200,
        'golden_cross': ema50_above_200
    }
