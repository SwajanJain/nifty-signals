"""
EXPLAINER Agent - Human-Readable Reasoning

The EXPLAINER synthesizes all analysis into clear, understandable
explanations for the human trader.

Key Responsibilities:
- Synthesize technical and AI analysis
- Provide clear trade rationale
- Explain risk factors in plain language
- Generate actionable summaries
- Create audit-ready documentation
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..base import (
    IntelligenceAgent,
    AgentRole,
    AgentContext,
    AgentOutput,
    Confidence
)


EXPLAINER_SYSTEM_PROMPT = """You are EXPLAINER, a clear communicator for an Indian equity trading system.

Your role is to synthesize complex analysis into clear, actionable explanations.

You must:
1. Summarize the trade setup in plain language
2. Explain WHY this is or isn't a good trade
3. List the key risks clearly
4. Provide the action with specific numbers
5. Be concise but complete

Your output must be structured JSON:
- "summary": 2-3 sentence summary of the trade opportunity
- "confidence": "high", "medium", "low", or "uncertain"
- "why_trade": Array of reasons TO take this trade
- "why_not_trade": Array of reasons NOT to take this trade
- "key_risks": Array of critical risks to monitor
- "action": Object with entry, stop, target, size
- "monitoring_points": What to watch after entry
- "one_liner": Single sentence recommendation

PRINCIPLES:
- Avoid jargon - explain like you're talking to a smart friend
- Be specific with numbers (₹2450 not "around support")
- If you're not convinced, say so clearly
- Always include the risk in plain language
- The human makes the final decision - give them what they need

Respond with valid JSON only."""


class ExplainerAgent(IntelligenceAgent):
    """
    EXPLAINER Agent - Clear communication.

    Synthesizes all analysis into human-readable explanations.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(
            role=AgentRole.EXPLAINER,
            model="claude-3-haiku-20240307",
            enabled=enabled
        )

    def get_system_prompt(self) -> str:
        return EXPLAINER_SYSTEM_PROMPT

    def format_context(self, context: AgentContext) -> str:
        """Format all analysis for the EXPLAINER."""
        # Gather all the analysis
        prompt_data = {
            "symbol": context.symbol,
            "current_price": context.price_data.get('current_price'),
            "market_regime": context.market_regime,
            "quantitative_analysis": {
                "conviction_score": context.conviction_score,
                "signal_direction": "BUY" if any(context.ensemble_votes.values()) else "NO SIGNAL",
                "models_agreeing": sum(1 for v in context.ensemble_votes.values() if v),
                "total_models": len(context.ensemble_votes),
            },
            "technical_levels": context.technical_indicators,
            "proposed_trade": context.quantitative_signals,
            "sector_context": context.sector_data,
            "data_quality_issues": [
                f"{k}: {v}" for k, v in context.data_quality.items()
                if v in ['degraded', 'unusable']
            ],
        }

        return f"""Create a clear explanation for this trading opportunity:

{json.dumps(prompt_data, indent=2)}

Be specific, clear, and actionable.
Include exact numbers for entry, stop, and target.

Respond with JSON only."""

    def parse_response(self, response: str, context: AgentContext) -> AgentOutput:
        """Parse EXPLAINER response into structured output."""
        try:
            data = json.loads(response)

            confidence_map = {
                "high": Confidence.HIGH,
                "medium": Confidence.MEDIUM,
                "low": Confidence.LOW,
                "uncertain": Confidence.UNCERTAIN
            }

            return AgentOutput(
                agent_role=self.role,
                timestamp=datetime.now(),
                assessment=data.get('summary', 'Analysis complete'),
                confidence=confidence_map.get(
                    data.get('confidence', 'medium'),
                    Confidence.MEDIUM
                ),
                reasoning=[data.get('one_liner', '')],
                factors_bullish=data.get('why_trade', []),
                factors_bearish=data.get('why_not_trade', []),
                risks_identified=data.get('key_risks', []),
                recommendation=data.get('one_liner', 'See detailed analysis'),
                position_modifier=1.0  # Explainer doesn't modify position
            )

        except json.JSONDecodeError:
            return AgentOutput(
                agent_role=self.role,
                timestamp=datetime.now(),
                assessment="Could not parse AI response",
                confidence=Confidence.UNCERTAIN,
                reasoning=[response[:500]],
                recommendation="See raw analysis",
                position_modifier=1.0
            )

    def _generate_mock_response(self, context: AgentContext) -> str:
        """Generate a clear explanation based on context."""
        symbol = context.symbol or "UNKNOWN"
        price = context.price_data.get('current_price', 0)
        conviction = context.conviction_score
        regime = context.market_regime

        votes = context.ensemble_votes
        agreeing = sum(1 for v in votes.values() if v) if votes else 0
        total = len(votes) if votes else 4

        # Get proposed levels
        signals = context.quantitative_signals
        entry = signals.get('entry', price)
        stop = signals.get('stop_loss', price * 0.95)
        target = signals.get('target1', price * 1.1)

        # Calculate risk/reward
        risk_pct = abs((entry - stop) / entry * 100) if entry else 5
        reward_pct = abs((target - entry) / entry * 100) if entry else 10
        rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 2

        # Build explanation
        why_trade = []
        why_not = []
        risks = []

        # Signal strength
        if agreeing >= 3:
            why_trade.append(f"Strong signal - {agreeing}/{total} models agree")
        elif agreeing >= 2:
            why_trade.append(f"Decent signal - {agreeing}/{total} models agree")
        else:
            why_not.append(f"Weak signal - only {agreeing}/{total} models agree")

        # Conviction
        if conviction >= 70:
            why_trade.append(f"High conviction ({conviction}/100)")
        elif conviction >= 50:
            why_trade.append(f"Moderate conviction ({conviction}/100)")
        else:
            why_not.append(f"Low conviction ({conviction}/100)")

        # Risk/reward
        if rr_ratio >= 2:
            why_trade.append(f"Good risk/reward ({rr_ratio:.1f}:1)")
        else:
            why_not.append(f"Marginal risk/reward ({rr_ratio:.1f}:1)")

        # Regime
        if regime in ["STRONG_BULL", "BULL"]:
            why_trade.append(f"Favorable market regime ({regime})")
        elif regime in ["STRONG_BEAR", "CRASH"]:
            why_not.append(f"Unfavorable market regime ({regime})")
            risks.append(f"Trading against the trend in {regime} market")

        # Data quality
        for source, quality in context.data_quality.items():
            if quality in ['degraded', 'unusable']:
                risks.append(f"Data quality concern: {source} is {quality}")

        # Always add standard risks
        risks.append("Market gap risk on overnight holds")
        risks.append("News/events can invalidate technical setup")

        # Determine recommendation
        if agreeing >= 2 and conviction >= 50 and regime not in ["CRASH", "STRONG_BEAR"]:
            confidence = "medium" if agreeing >= 3 else "low"
            one_liner = f"CONSIDER BUYING {symbol} at ₹{entry:.0f} with stop at ₹{stop:.0f}"
        else:
            confidence = "low"
            one_liner = f"AVOID {symbol} - insufficient conviction for entry"

        summary = f"{symbol} at ₹{price:.0f} shows a {'strong' if agreeing >= 3 else 'moderate' if agreeing >= 2 else 'weak'} setup. "
        summary += f"Conviction is {conviction}/100 in a {regime} market. "
        summary += f"Risk/reward is {rr_ratio:.1f}:1."

        return json.dumps({
            "summary": summary,
            "confidence": confidence,
            "why_trade": why_trade,
            "why_not_trade": why_not,
            "key_risks": risks,
            "action": {
                "entry": f"₹{entry:.0f}",
                "stop_loss": f"₹{stop:.0f} ({risk_pct:.1f}% risk)",
                "target": f"₹{target:.0f} ({reward_pct:.1f}% reward)",
                "risk_reward": f"{rr_ratio:.1f}:1"
            },
            "monitoring_points": [
                f"Watch if price breaks below ₹{stop:.0f}",
                "Monitor volume for confirmation",
                "Exit if market regime deteriorates"
            ],
            "one_liner": one_liner
        })

    def generate_report(
        self,
        context: AgentContext,
        sentinel_output: Optional[AgentOutput] = None,
        analyst_output: Optional[AgentOutput] = None,
        validator_output: Optional[AgentOutput] = None
    ) -> str:
        """
        Generate a comprehensive human-readable report.

        Combines outputs from all agents into a clear summary.
        """
        symbol = context.symbol or "UNKNOWN"
        price = context.price_data.get('current_price', 0)

        lines = []
        lines.append("=" * 60)
        lines.append(f"TRADING ANALYSIS: {symbol}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("=" * 60)

        # Market Context
        lines.append("\n## MARKET CONTEXT")
        if sentinel_output:
            lines.append(f"Assessment: {sentinel_output.assessment}")
            lines.append(f"Confidence: {sentinel_output.confidence.value.upper()}")
            if sentinel_output.risks_identified:
                lines.append("Risks:")
                for risk in sentinel_output.risks_identified:
                    lines.append(f"  - {risk}")

        # Signal Analysis
        lines.append("\n## SIGNAL ANALYSIS")
        if analyst_output:
            lines.append(f"Assessment: {analyst_output.assessment}")
            if analyst_output.factors_bullish:
                lines.append("Bullish Factors:")
                for factor in analyst_output.factors_bullish:
                    lines.append(f"  + {factor}")
            if analyst_output.factors_bearish:
                lines.append("Bearish Factors:")
                for factor in analyst_output.factors_bearish:
                    lines.append(f"  - {factor}")

        # Validation
        lines.append("\n## VALIDATION")
        if validator_output:
            lines.append(f"Result: {validator_output.recommendation}")
            if validator_output.risks_identified:
                lines.append("Identified Risks:")
                for risk in validator_output.risks_identified:
                    lines.append(f"  ! {risk}")

        # Final Recommendation
        lines.append("\n## RECOMMENDATION")
        signals = context.quantitative_signals
        entry = signals.get('entry', price)
        stop = signals.get('stop_loss', price * 0.95)
        target = signals.get('target1', price * 1.1)

        lines.append(f"Entry: ₹{entry:.2f}")
        lines.append(f"Stop Loss: ₹{stop:.2f}")
        lines.append(f"Target: ₹{target:.2f}")

        # Position modifier
        modifiers = []
        if sentinel_output:
            modifiers.append(sentinel_output.position_modifier)
        if analyst_output:
            modifiers.append(analyst_output.position_modifier)
        if validator_output:
            modifiers.append(validator_output.position_modifier)

        if modifiers:
            combined = 1.0
            for m in modifiers:
                combined *= m
            lines.append(f"\nPosition Size: {combined*100:.0f}% of normal")

        lines.append("=" * 60)
        return "\n".join(lines)
