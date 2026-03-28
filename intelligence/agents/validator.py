"""
VALIDATOR Agent - Risk and Sanity Checks

The VALIDATOR performs the final safety check before any trade is executed.
It looks for reasons NOT to take the trade.

Key Responsibilities:
- Identify risks the other agents might have missed
- Check for red flags (earnings, news, corporate actions)
- Validate position sizing and portfolio impact
- Ensure risk management rules are followed
- Provide final go/no-go decision
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


VALIDATOR_SYSTEM_PROMPT = """You are VALIDATOR, the final safety check for an Indian equity trading system.

Your role is to find reasons NOT to take a trade. You are the last line of defense.

You check:
1. Risk management rules (position limits, portfolio heat)
2. Event risks (earnings, corporate actions, ex-dates)
3. Liquidity concerns (can we exit if needed?)
4. Correlation risks (are we doubling down on same exposure?)
5. Gap risks (overnight holds in volatile environment)

Your output must be structured JSON:
- "validation_result": "APPROVED", "APPROVED_WITH_CAUTION", "REDUCE_SIZE", or "REJECT"
- "confidence": "high", "medium", "low", or "uncertain"
- "reasoning": Array of validation checks performed
- "risks_found": Array of specific risks identified
- "red_flags": Array of critical issues that should block the trade
- "suggested_adjustments": Object with any recommended changes
- "final_position_modifier": Number 0.0 to 1.0 (1.0 = full size approved)

CRITICAL PRINCIPLES:
- Earnings in 3 days = REJECT (or heavy reduction)
- Portfolio heat > 6% = REJECT new positions
- Single position > 15% of capital = REDUCE_SIZE
- More than 3 positions in same sector = REJECT
- Unknown risks are NOT acceptable - be conservative
- Your job is to PROTECT capital, not to find trades

Respond with valid JSON only."""


class ValidatorAgent(IntelligenceAgent):
    """
    VALIDATOR Agent - Final safety check.

    The last line of defense before trade execution.
    Looks for reasons NOT to trade.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(
            role=AgentRole.VALIDATOR,
            model="claude-3-haiku-20240307",
            enabled=enabled
        )

    def get_system_prompt(self) -> str:
        return VALIDATOR_SYSTEM_PROMPT

    def format_context(self, context: AgentContext) -> str:
        """Format context for validation."""
        prompt_data = {
            "symbol": context.symbol,
            "timestamp": context.timestamp.isoformat(),
            "proposed_trade": context.quantitative_signals,
            "portfolio_state": {
                "current_heat": context.performance_stats.get('portfolio_heat', 0),
                "positions_count": context.performance_stats.get('positions_count', 0),
                "sector_exposure": context.performance_stats.get('sector_exposure', {}),
            },
            "stock_context": {
                "sector": context.sector_data.get('sector_name', 'Unknown'),
                "has_earnings_soon": context.price_data.get('has_earnings_soon', 'unknown'),
                "avg_daily_volume_cr": context.price_data.get('adv_cr', 'unknown'),
            },
            "market_conditions": {
                "regime": context.market_regime,
                "vix": context.global_context.get('vix', 'unknown'),
            },
            "data_quality": context.data_quality,
        }

        return f"""Validate this proposed trade:

{json.dumps(prompt_data, indent=2)}

Your job is to find reasons NOT to take this trade.
Check all risk management rules.
When uncertain, be conservative.

Respond with JSON only."""

    def parse_response(self, response: str, context: AgentContext) -> AgentOutput:
        """Parse VALIDATOR response into structured output."""
        try:
            data = json.loads(response)

            result = data.get('validation_result', 'APPROVED')
            position_modifier = data.get('final_position_modifier', 1.0)

            # Override modifier based on result
            if result == "REJECT":
                position_modifier = 0.0
            elif result == "REDUCE_SIZE":
                position_modifier = min(position_modifier, 0.5)
            elif result == "APPROVED_WITH_CAUTION":
                position_modifier = min(position_modifier, 0.8)

            confidence_map = {
                "high": Confidence.HIGH,
                "medium": Confidence.MEDIUM,
                "low": Confidence.LOW,
                "uncertain": Confidence.UNCERTAIN
            }

            return AgentOutput(
                agent_role=self.role,
                timestamp=datetime.now(),
                assessment=f"Validation: {result}",
                confidence=confidence_map.get(
                    data.get('confidence', 'medium'),
                    Confidence.MEDIUM
                ),
                reasoning=data.get('reasoning', []),
                factors_bullish=[],
                factors_bearish=data.get('red_flags', []),
                risks_identified=data.get('risks_found', []),
                recommendation=result,
                position_modifier=position_modifier
            )

        except json.JSONDecodeError:
            return AgentOutput(
                agent_role=self.role,
                timestamp=datetime.now(),
                assessment="Could not parse AI response",
                confidence=Confidence.UNCERTAIN,
                reasoning=[response[:500]],
                recommendation="APPROVED_WITH_CAUTION",
                position_modifier=0.8
            )

    def _generate_mock_response(self, context: AgentContext) -> str:
        """Generate a realistic mock response."""
        risks = []
        red_flags = []
        reasoning = []
        result = "APPROVED"
        modifier = 1.0

        # Check portfolio heat
        heat = context.performance_stats.get('portfolio_heat', 0)
        if heat > 6:
            red_flags.append(f"Portfolio heat ({heat}%) exceeds 6% limit")
            result = "REJECT"
            modifier = 0.0
        elif heat > 5:
            risks.append(f"Portfolio heat ({heat}%) approaching limit")
            modifier *= 0.7
        reasoning.append(f"Portfolio heat check: {heat}%")

        # Check sector concentration
        positions = context.performance_stats.get('positions_count', 0)
        if positions >= 5:
            risks.append(f"Already have {positions} open positions")
            modifier *= 0.8
        reasoning.append(f"Position count check: {positions}")

        # Check for earnings
        has_earnings = context.price_data.get('has_earnings_soon')
        if has_earnings == True:
            red_flags.append("Earnings announcement within 3 days")
            result = "REJECT"
            modifier = 0.0
        elif has_earnings == 'unknown':
            risks.append("Earnings date unknown - cannot verify")
            modifier *= 0.8
        reasoning.append(f"Earnings check: {has_earnings}")

        # Check liquidity
        adv = context.price_data.get('adv_cr')
        if isinstance(adv, (int, float)) and adv < 10:
            risks.append(f"Low liquidity: {adv} Cr ADV (min 10 Cr)")
            modifier *= 0.7
        reasoning.append(f"Liquidity check: ADV = {adv}")

        # Check data quality
        for source, quality in context.data_quality.items():
            if quality == "unusable" and source == "price":
                red_flags.append(f"Price data is {quality}")
                result = "REJECT"
                modifier = 0.0
            elif quality in ["unusable", "degraded"]:
                risks.append(f"{source} data quality: {quality}")
                modifier *= 0.9
        reasoning.append("Data quality checks performed")

        # Determine final result
        if red_flags and result != "REJECT":
            result = "REJECT" if len(red_flags) > 1 else "REDUCE_SIZE"
            modifier = 0.0 if result == "REJECT" else 0.5
        elif risks and result == "APPROVED":
            result = "APPROVED_WITH_CAUTION"
            modifier = min(modifier, 0.8)

        return json.dumps({
            "validation_result": result,
            "confidence": "high" if not risks else "medium",
            "reasoning": reasoning,
            "risks_found": risks,
            "red_flags": red_flags,
            "suggested_adjustments": {
                "reduce_size_by": int((1 - modifier) * 100) if modifier < 1 else 0
            },
            "final_position_modifier": modifier
        })

    def quick_validate(
        self,
        context: AgentContext,
        portfolio_heat: float,
        sector_positions: int,
        has_earnings_soon: Optional[bool]
    ) -> Dict[str, Any]:
        """
        Quick rule-based validation without AI.

        Returns validation result.
        """
        result = {
            "approved": True,
            "result": "APPROVED",
            "modifier": 1.0,
            "red_flags": [],
            "warnings": []
        }

        # Hard blocks
        if portfolio_heat > 6:
            result["approved"] = False
            result["result"] = "REJECT"
            result["modifier"] = 0.0
            result["red_flags"].append(f"Portfolio heat ({portfolio_heat}%) > 6%")

        if sector_positions >= 3:
            result["approved"] = False
            result["result"] = "REJECT"
            result["modifier"] = 0.0
            result["red_flags"].append(f"Sector limit reached ({sector_positions} positions)")

        if has_earnings_soon == True:
            result["approved"] = False
            result["result"] = "REJECT"
            result["modifier"] = 0.0
            result["red_flags"].append("Earnings announcement within 3 days")

        # Warnings (reduce size but allow)
        if not result["red_flags"]:
            if portfolio_heat > 5:
                result["result"] = "APPROVED_WITH_CAUTION"
                result["modifier"] *= 0.7
                result["warnings"].append(f"Portfolio heat ({portfolio_heat}%) high")

            if sector_positions >= 2:
                result["modifier"] *= 0.8
                result["warnings"].append(f"Already {sector_positions} in sector")

            if has_earnings_soon is None:
                result["modifier"] *= 0.8
                result["warnings"].append("Earnings date unknown")

            # Check regime
            regime = context.market_regime
            if regime in ["CRASH"]:
                result["approved"] = False
                result["result"] = "REJECT"
                result["modifier"] = 0.0
                result["red_flags"].append("CRASH regime - no new positions")
            elif regime in ["STRONG_BEAR"]:
                result["modifier"] *= 0.5
                result["warnings"].append("Strong bear market")

        return result
