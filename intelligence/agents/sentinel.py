"""
SENTINEL Agent - Market Context Assessment

The SENTINEL is the first line of defense. It assesses the overall
market environment before any trading decisions are made.

Key Responsibilities:
- Assess global market conditions
- Identify regime changes
- Detect risk-off environments
- Provide go/no-go trading signal
- Set portfolio-level risk parameters
"""

import json
from datetime import datetime
from typing import Dict, Any, List

from ..base import (
    IntelligenceAgent,
    AgentRole,
    AgentContext,
    AgentOutput,
    Confidence
)


SENTINEL_SYSTEM_PROMPT = """You are SENTINEL, an expert market context analyst for an Indian stock trading system.

Your role is to assess the OVERALL market environment and provide a clear go/no-go signal for trading.

You analyze:
1. Global markets (US futures, Asian markets, VIX)
2. Indian market regime (Nifty trend, breadth, FII/DII flows)
3. Macro risks (geopolitical, currency, global events)
4. Sector rotation patterns

Your output must be structured JSON with these fields:
- "market_assessment": Brief summary (1-2 sentences)
- "confidence": "high", "medium", "low", or "uncertain"
- "trading_environment": "FAVORABLE", "NEUTRAL", "CAUTIOUS", or "AVOID"
- "reasoning": Array of key observations (3-5 points)
- "risks": Array of identified risks
- "position_size_recommendation": Number between 0.0 (no trading) and 1.2 (slightly aggressive)
- "sectors_to_favor": Array of sector names to focus on
- "sectors_to_avoid": Array of sector names to avoid

IMPORTANT PRINCIPLES:
- When in doubt, be CAUTIOUS
- A CRASH regime means NO TRADING
- High VIX (>25) requires position reduction
- FII selling >2000 Cr is a warning sign
- Unknown data is NOT neutral - it's a risk

Always respond with valid JSON only."""


class SentinelAgent(IntelligenceAgent):
    """
    SENTINEL Agent - Market context assessment.

    Provides portfolio-level trading guidance based on
    global and domestic market conditions.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(
            role=AgentRole.SENTINEL,
            model="claude-3-haiku-20240307",
            enabled=enabled
        )

    def get_system_prompt(self) -> str:
        return SENTINEL_SYSTEM_PROMPT

    def format_context(self, context: AgentContext) -> str:
        """Format market context for the SENTINEL."""
        prompt_data = {
            "timestamp": context.timestamp.isoformat(),
            "market_regime": context.market_regime,
            "global_context": {
                "us_futures": context.global_context.get('us_futures', 'unknown'),
                "asian_markets": context.global_context.get('asian_markets', 'unknown'),
                "vix": context.global_context.get('vix', 'unknown'),
                "dollar_index": context.global_context.get('dollar_index', 'unknown'),
                "crude_oil": context.global_context.get('crude_oil', 'unknown'),
            },
            "indian_market": {
                "nifty_change_pct": context.price_data.get('nifty_change', 'unknown'),
                "advance_decline": context.price_data.get('advance_decline', 'unknown'),
                "fii_net": context.fii_dii_data.get('fii_net', 'unknown'),
                "dii_net": context.fii_dii_data.get('dii_net', 'unknown'),
            },
            "sectors": context.sector_data,
            "data_quality": context.data_quality,
        }

        return f"""Analyze this market context and provide your assessment:

{json.dumps(prompt_data, indent=2)}

Remember:
- If data quality is poor, be more conservative
- FII selling > 2000 Cr is a warning
- VIX > 25 requires caution
- Respond with JSON only"""

    def parse_response(self, response: str, context: AgentContext) -> AgentOutput:
        """Parse SENTINEL response into structured output."""
        try:
            # Try to parse as JSON
            data = json.loads(response)

            # Map trading environment to position modifier
            env_to_modifier = {
                "FAVORABLE": 1.0,
                "NEUTRAL": 0.8,
                "CAUTIOUS": 0.5,
                "AVOID": 0.0
            }

            trading_env = data.get('trading_environment', 'NEUTRAL')
            position_modifier = data.get(
                'position_size_recommendation',
                env_to_modifier.get(trading_env, 0.8)
            )

            # Map confidence
            confidence_map = {
                "high": Confidence.HIGH,
                "medium": Confidence.MEDIUM,
                "low": Confidence.LOW,
                "uncertain": Confidence.UNCERTAIN
            }

            return AgentOutput(
                agent_role=self.role,
                timestamp=datetime.now(),
                assessment=data.get('market_assessment', 'Unable to assess'),
                confidence=confidence_map.get(
                    data.get('confidence', 'medium'),
                    Confidence.MEDIUM
                ),
                reasoning=data.get('reasoning', []),
                factors_bullish=data.get('sectors_to_favor', []),
                factors_bearish=data.get('sectors_to_avoid', []),
                risks_identified=data.get('risks', []),
                recommendation=f"Trading environment: {trading_env}",
                position_modifier=position_modifier
            )

        except json.JSONDecodeError:
            # If not valid JSON, extract what we can
            return AgentOutput(
                agent_role=self.role,
                timestamp=datetime.now(),
                assessment="Could not parse AI response",
                confidence=Confidence.UNCERTAIN,
                reasoning=[response[:500]],  # Include partial response
                recommendation="Proceed with caution",
                position_modifier=0.8
            )

    def _generate_mock_response(self, context: AgentContext) -> str:
        """Generate a realistic mock response based on actual context."""
        # Analyze the context to generate appropriate mock
        vix = context.global_context.get('vix', 15)
        regime = context.market_regime
        fii_net = context.fii_dii_data.get('fii_net', 0)

        # Determine environment based on inputs
        if regime == "CRASH" or (isinstance(vix, (int, float)) and vix > 30):
            env = "AVOID"
            modifier = 0.0
            confidence = "high"
            assessment = "Market conditions are adverse. Recommend staying in cash."
            risks = ["High volatility", "Potential further downside", "Risk-off environment"]
        elif regime in ["STRONG_BEAR", "BEAR"] or (isinstance(fii_net, (int, float)) and fii_net < -2000):
            env = "CAUTIOUS"
            modifier = 0.5
            confidence = "medium"
            assessment = "Bearish conditions detected. Reduce exposure and be selective."
            risks = ["Continued FII selling", "Weak market breadth", "Potential for further decline"]
        elif regime in ["STRONG_BULL", "BULL"]:
            env = "FAVORABLE"
            modifier = 1.0
            confidence = "medium"
            assessment = "Market conditions are favorable for long positions."
            risks = ["Complacency risk", "Potential for pullback after extended rally"]
        else:
            env = "NEUTRAL"
            modifier = 0.8
            confidence = "medium"
            assessment = "Mixed market conditions. Proceed with standard position sizing."
            risks = ["Unclear direction", "Range-bound market"]

        return json.dumps({
            "market_assessment": assessment,
            "confidence": confidence,
            "trading_environment": env,
            "reasoning": [
                f"Market regime: {regime}",
                f"VIX level: {vix}",
                f"FII net: {fii_net}" if fii_net else "FII data unavailable",
            ],
            "risks": risks,
            "position_size_recommendation": modifier,
            "sectors_to_favor": [],
            "sectors_to_avoid": []
        })

    def quick_check(self, context: AgentContext) -> Dict[str, Any]:
        """
        Perform a quick rule-based check without AI.

        Used as a fast pre-filter before full AI analysis.
        """
        result = {
            "can_trade": True,
            "position_modifier": 1.0,
            "warnings": []
        }

        # Check regime
        regime = context.market_regime
        if regime == "CRASH":
            result["can_trade"] = False
            result["position_modifier"] = 0.0
            result["warnings"].append("CRASH regime - no trading")
            return result

        if regime in ["STRONG_BEAR"]:
            result["position_modifier"] = 0.3
            result["warnings"].append("Strong bear market - reduced sizing")

        if regime == "BEAR":
            result["position_modifier"] = 0.5
            result["warnings"].append("Bear market - cautious sizing")

        # Check VIX
        vix = context.global_context.get('vix')
        if isinstance(vix, (int, float)):
            if vix > 30:
                result["position_modifier"] *= 0.5
                result["warnings"].append(f"VIX very high ({vix}) - half sizing")
            elif vix > 25:
                result["position_modifier"] *= 0.7
                result["warnings"].append(f"VIX elevated ({vix}) - reduced sizing")

        # Check FII flows
        fii_net = context.fii_dii_data.get('fii_net')
        if isinstance(fii_net, (int, float)) and fii_net < -2000:
            result["position_modifier"] *= 0.8
            result["warnings"].append(f"Heavy FII selling ({fii_net} Cr)")

        # Check data quality
        for source, quality in context.data_quality.items():
            if quality == "unusable":
                result["warnings"].append(f"{source} data unusable")
                if source == "price":
                    result["can_trade"] = False
                    result["position_modifier"] = 0.0

        return result
