"""
LEARNER Agent - Pattern Recognition from History

The LEARNER analyzes historical trades and system performance to identify
patterns, improve decision-making, and avoid repeating mistakes.

Key Responsibilities:
- Analyze past trade outcomes
- Identify winning and losing patterns
- Detect regime-specific performance
- Track conviction calibration
- Suggest parameter adjustments
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from ..base import (
    IntelligenceAgent,
    AgentRole,
    AgentContext,
    AgentOutput,
    Confidence
)


LEARNER_SYSTEM_PROMPT = """You are LEARNER, a pattern recognition specialist for an Indian equity trading system.

Your role is to analyze historical performance and identify actionable patterns.

You analyze:
1. Win rate by market regime (when do we perform best/worst?)
2. Conviction calibration (are high conviction trades actually better?)
3. Sector performance (which sectors generate alpha?)
4. Model accuracy (which models are most reliable currently?)
5. Common mistakes (what errors keep recurring?)

Your output must be structured JSON:
- "analysis_summary": Brief summary of key findings
- "confidence": "high", "medium", "low", or "uncertain"
- "winning_patterns": Array of patterns that lead to wins
- "losing_patterns": Array of patterns that lead to losses
- "regime_insights": Object mapping regimes to performance insights
- "calibration_issues": Array of areas where our confidence is miscalibrated
- "suggested_adjustments": Object with specific parameter recommendations
- "current_trade_relevance": How these insights apply to current situation

PRINCIPLES:
- Only suggest changes based on statistically significant patterns (10+ trades)
- Recent performance (last 30 days) is more relevant than older data
- Be specific about what's working and what's not
- Focus on actionable insights, not general observations

Respond with valid JSON only."""


class LearnerAgent(IntelligenceAgent):
    """
    LEARNER Agent - Historical pattern analysis.

    Learns from past trades to improve future decisions.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(
            role=AgentRole.LEARNER,
            model="claude-3-haiku-20240307",
            enabled=enabled
        )

    def get_system_prompt(self) -> str:
        return LEARNER_SYSTEM_PROMPT

    def format_context(self, context: AgentContext) -> str:
        """Format historical data for the LEARNER."""
        # Summarize recent trades
        recent_trades = context.recent_trades[-50:] if context.recent_trades else []

        # Calculate basic stats
        if recent_trades:
            wins = sum(1 for t in recent_trades if t.get('result') == 'WIN')
            losses = sum(1 for t in recent_trades if t.get('result') == 'LOSS')
            total = wins + losses
            win_rate = (wins / total * 100) if total > 0 else 0
        else:
            wins = losses = total = 0
            win_rate = 0

        prompt_data = {
            "current_context": {
                "symbol": context.symbol,
                "regime": context.market_regime,
                "conviction_score": context.conviction_score,
            },
            "performance_summary": {
                "recent_trades": len(recent_trades),
                "wins": wins,
                "losses": losses,
                "win_rate": f"{win_rate:.1f}%",
            },
            "trades_by_regime": self._group_trades_by_regime(recent_trades),
            "trades_by_conviction": self._group_trades_by_conviction(recent_trades),
            "common_mistakes": context.performance_stats.get('common_mistakes', []),
            "recent_trades_detail": recent_trades[-10:],  # Last 10 trades
        }

        return f"""Analyze this historical performance data:

{json.dumps(prompt_data, indent=2)}

Identify patterns that can help with the current trading decision.
Focus on actionable insights.

Respond with JSON only."""

    def _group_trades_by_regime(self, trades: List[Dict]) -> Dict[str, Dict]:
        """Group trades by market regime."""
        groups = {}
        for trade in trades:
            regime = trade.get('regime', 'UNKNOWN')
            if regime not in groups:
                groups[regime] = {'trades': 0, 'wins': 0}
            groups[regime]['trades'] += 1
            if trade.get('result') == 'WIN':
                groups[regime]['wins'] += 1

        # Calculate win rates
        for regime in groups:
            total = groups[regime]['trades']
            wins = groups[regime]['wins']
            groups[regime]['win_rate'] = f"{(wins/total*100):.0f}%" if total > 0 else "N/A"

        return groups

    def _group_trades_by_conviction(self, trades: List[Dict]) -> Dict[str, Dict]:
        """Group trades by conviction level."""
        groups = {}
        for trade in trades:
            conviction = trade.get('conviction_level', 'B')
            if conviction not in groups:
                groups[conviction] = {'trades': 0, 'wins': 0}
            groups[conviction]['trades'] += 1
            if trade.get('result') == 'WIN':
                groups[conviction]['wins'] += 1

        for level in groups:
            total = groups[level]['trades']
            wins = groups[level]['wins']
            groups[level]['win_rate'] = f"{(wins/total*100):.0f}%" if total > 0 else "N/A"

        return groups

    def parse_response(self, response: str, context: AgentContext) -> AgentOutput:
        """Parse LEARNER response into structured output."""
        try:
            data = json.loads(response)

            # Extract position modifier from adjustments
            adjustments = data.get('suggested_adjustments', {})
            position_modifier = adjustments.get('position_modifier', 1.0)

            confidence_map = {
                "high": Confidence.HIGH,
                "medium": Confidence.MEDIUM,
                "low": Confidence.LOW,
                "uncertain": Confidence.UNCERTAIN
            }

            return AgentOutput(
                agent_role=self.role,
                timestamp=datetime.now(),
                assessment=data.get('analysis_summary', 'Analysis complete'),
                confidence=confidence_map.get(
                    data.get('confidence', 'medium'),
                    Confidence.MEDIUM
                ),
                reasoning=[data.get('current_trade_relevance', 'See patterns below')],
                factors_bullish=data.get('winning_patterns', []),
                factors_bearish=data.get('losing_patterns', []),
                risks_identified=data.get('calibration_issues', []),
                recommendation=str(adjustments),
                position_modifier=position_modifier
            )

        except json.JSONDecodeError:
            return AgentOutput(
                agent_role=self.role,
                timestamp=datetime.now(),
                assessment="Could not parse AI response",
                confidence=Confidence.UNCERTAIN,
                reasoning=[response[:500]],
                recommendation="No historical adjustments",
                position_modifier=1.0
            )

    def _generate_mock_response(self, context: AgentContext) -> str:
        """Generate a mock response based on historical data."""
        trades = context.recent_trades or []
        regime = context.market_regime
        conviction = context.conviction_score

        # Analyze patterns if we have enough data
        if len(trades) < 10:
            return json.dumps({
                "analysis_summary": "Insufficient trade history for pattern analysis",
                "confidence": "low",
                "winning_patterns": [],
                "losing_patterns": [],
                "regime_insights": {},
                "calibration_issues": ["Need 10+ trades for reliable patterns"],
                "suggested_adjustments": {},
                "current_trade_relevance": "Not enough data to inform current decision"
            })

        # Calculate basic metrics
        wins = sum(1 for t in trades if t.get('result') == 'WIN')
        total = len([t for t in trades if t.get('result') in ['WIN', 'LOSS']])
        win_rate = (wins / total * 100) if total > 0 else 50

        # Regime-specific analysis
        regime_trades = [t for t in trades if t.get('regime') == regime]
        regime_wins = sum(1 for t in regime_trades if t.get('result') == 'WIN')
        regime_total = len([t for t in regime_trades if t.get('result') in ['WIN', 'LOSS']])
        regime_wr = (regime_wins / regime_total * 100) if regime_total > 0 else win_rate

        # Generate insights
        winning_patterns = []
        losing_patterns = []
        calibration_issues = []
        adjustments = {}

        if regime_wr < win_rate - 10 and regime_total >= 5:
            losing_patterns.append(f"Underperformance in {regime} regime ({regime_wr:.0f}% vs {win_rate:.0f}% overall)")
            adjustments['position_modifier'] = 0.8
        elif regime_wr > win_rate + 10 and regime_total >= 5:
            winning_patterns.append(f"Outperformance in {regime} regime ({regime_wr:.0f}% vs {win_rate:.0f}% overall)")
            adjustments['position_modifier'] = 1.1

        # Conviction calibration
        high_conv = [t for t in trades if t.get('conviction_level') in ['A', 'A+']]
        low_conv = [t for t in trades if t.get('conviction_level') in ['C', 'D']]

        if high_conv:
            high_wr = sum(1 for t in high_conv if t.get('result') == 'WIN') / len(high_conv) * 100
            if high_wr < win_rate:
                calibration_issues.append(f"High conviction trades ({high_wr:.0f}%) underperforming average ({win_rate:.0f}%)")
            elif high_wr > win_rate + 15:
                winning_patterns.append(f"High conviction trades significantly outperform ({high_wr:.0f}%)")

        relevance = f"Current setup: {regime} regime, conviction {conviction}. "
        if regime_total >= 5:
            relevance += f"Historical win rate in this regime: {regime_wr:.0f}%"
        else:
            relevance += "Limited data for this regime."

        return json.dumps({
            "analysis_summary": f"Based on {total} trades with {win_rate:.0f}% win rate",
            "confidence": "medium" if total >= 20 else "low",
            "winning_patterns": winning_patterns,
            "losing_patterns": losing_patterns,
            "regime_insights": {
                regime: {
                    "trades": regime_total,
                    "win_rate": f"{regime_wr:.0f}%",
                    "comparison": "Above average" if regime_wr > win_rate else "Below average"
                }
            },
            "calibration_issues": calibration_issues,
            "suggested_adjustments": adjustments,
            "current_trade_relevance": relevance
        })

    def analyze_patterns(self, trades: List[Dict]) -> Dict[str, Any]:
        """
        Rule-based pattern analysis without AI.

        Returns identified patterns and recommendations.
        """
        result = {
            "sufficient_data": len(trades) >= 10,
            "overall_win_rate": 0,
            "regime_performance": {},
            "conviction_calibration": {},
            "recommendations": []
        }

        if len(trades) < 10:
            return result

        # Overall stats
        closed = [t for t in trades if t.get('result') in ['WIN', 'LOSS']]
        wins = sum(1 for t in closed if t.get('result') == 'WIN')
        result["overall_win_rate"] = (wins / len(closed) * 100) if closed else 0

        # By regime
        regimes = {}
        for trade in closed:
            regime = trade.get('regime', 'UNKNOWN')
            if regime not in regimes:
                regimes[regime] = {'wins': 0, 'total': 0}
            regimes[regime]['total'] += 1
            if trade.get('result') == 'WIN':
                regimes[regime]['wins'] += 1

        for regime, data in regimes.items():
            wr = (data['wins'] / data['total'] * 100) if data['total'] > 0 else 0
            result["regime_performance"][regime] = {
                "win_rate": wr,
                "trades": data['total'],
                "vs_average": wr - result["overall_win_rate"]
            }

        # By conviction
        convictions = {}
        for trade in closed:
            conv = trade.get('conviction_level', 'B')
            if conv not in convictions:
                convictions[conv] = {'wins': 0, 'total': 0}
            convictions[conv]['total'] += 1
            if trade.get('result') == 'WIN':
                convictions[conv]['wins'] += 1

        for conv, data in convictions.items():
            wr = (data['wins'] / data['total'] * 100) if data['total'] > 0 else 0
            result["conviction_calibration"][conv] = {
                "win_rate": wr,
                "trades": data['total'],
                "properly_calibrated": (conv in ['A', 'A+'] and wr >= result["overall_win_rate"]) or
                                       (conv == 'C' and wr <= result["overall_win_rate"])
            }

        # Generate recommendations
        for regime, perf in result["regime_performance"].items():
            if perf['trades'] >= 5:
                if perf['vs_average'] < -15:
                    result["recommendations"].append(
                        f"Reduce position size in {regime} regime (underperforming by {abs(perf['vs_average']):.0f}%)"
                    )
                elif perf['vs_average'] > 15:
                    result["recommendations"].append(
                        f"Consider increasing size in {regime} regime (outperforming by {perf['vs_average']:.0f}%)"
                    )

        return result
