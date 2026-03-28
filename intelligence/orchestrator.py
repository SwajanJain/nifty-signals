"""
Intelligence Orchestrator - Coordinates all AI agents.

This module manages the flow of analysis through all intelligence agents
and combines their outputs into a unified trading decision.

Flow:
1. SENTINEL assesses market conditions → go/no-go
2. ANALYST validates individual signals → quality assessment
3. VALIDATOR performs final safety checks → approval
4. LEARNER provides historical context → adjustments
5. EXPLAINER synthesizes everything → clear recommendation
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from .base import (
    AgentContext,
    AgentOutput,
    Confidence,
    IntelligenceConfig,
    AuditLogger,
    get_intelligence_config,
    get_audit_logger
)
from .agents import (
    SentinelAgent,
    AnalystAgent,
    ValidatorAgent,
    LearnerAgent,
    ExplainerAgent
)

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceResult:
    """Combined result from all intelligence agents."""
    timestamp: datetime

    # Individual agent outputs
    sentinel: Optional[AgentOutput] = None
    analyst: Optional[AgentOutput] = None
    validator: Optional[AgentOutput] = None
    learner: Optional[AgentOutput] = None
    explainer: Optional[AgentOutput] = None

    # Combined assessment
    can_trade: bool = False
    final_position_modifier: float = 1.0
    confidence: Confidence = Confidence.UNCERTAIN
    recommendation: str = ""

    # Aggregated factors
    all_bullish: List[str] = field(default_factory=list)
    all_bearish: List[str] = field(default_factory=list)
    all_risks: List[str] = field(default_factory=list)
    all_warnings: List[str] = field(default_factory=list)

    # Processing metadata
    agents_consulted: List[str] = field(default_factory=list)
    total_processing_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'can_trade': self.can_trade,
            'final_position_modifier': self.final_position_modifier,
            'confidence': self.confidence.value,
            'recommendation': self.recommendation,
            'all_bullish': self.all_bullish,
            'all_bearish': self.all_bearish,
            'all_risks': self.all_risks,
            'all_warnings': self.all_warnings,
            'agents_consulted': self.agents_consulted,
            'total_processing_time_ms': self.total_processing_time_ms,
            'sentinel': self.sentinel.to_dict() if self.sentinel else None,
            'analyst': self.analyst.to_dict() if self.analyst else None,
            'validator': self.validator.to_dict() if self.validator else None,
            'learner': self.learner.to_dict() if self.learner else None,
            'explainer': self.explainer.to_dict() if self.explainer else None,
        }


class IntelligenceOrchestrator:
    """
    Orchestrates the intelligence layer.

    Coordinates all AI agents to produce a unified trading decision.
    """

    def __init__(self, config: Optional[IntelligenceConfig] = None):
        self.config = config or get_intelligence_config()
        self.audit = get_audit_logger()

        # Initialize agents
        self.sentinel = SentinelAgent(enabled=self.config.sentinel_enabled)
        self.analyst = AnalystAgent(enabled=self.config.analyst_enabled)
        self.validator = ValidatorAgent(enabled=self.config.validator_enabled)
        self.learner = LearnerAgent(enabled=self.config.learner_enabled)
        self.explainer = ExplainerAgent(enabled=self.config.explainer_enabled)

    def analyze(self, context: AgentContext) -> IntelligenceResult:
        """
        Run full intelligence analysis on the given context.

        This is the main entry point for the intelligence layer.
        """
        start_time = datetime.now()
        result = IntelligenceResult(timestamp=start_time)

        try:
            # Phase 1: SENTINEL - Market Assessment
            if self.config.sentinel_enabled:
                result.sentinel = self.sentinel.analyze(context)
                result.agents_consulted.append("SENTINEL")

                # Early exit if SENTINEL says no trading
                if result.sentinel.position_modifier == 0:
                    result.can_trade = False
                    result.final_position_modifier = 0
                    result.recommendation = "NO TRADE - Market conditions unfavorable"
                    result.all_warnings.append(result.sentinel.assessment)
                    self._finalize_result(result, start_time)
                    return result

            # Phase 2: ANALYST - Signal Validation
            if self.config.analyst_enabled and context.symbol:
                result.analyst = self.analyst.analyze(context)
                result.agents_consulted.append("ANALYST")

            # Phase 3: LEARNER - Historical Context
            if self.config.learner_enabled and context.recent_trades:
                result.learner = self.learner.analyze(context)
                result.agents_consulted.append("LEARNER")

            # Phase 4: VALIDATOR - Final Safety Check
            if self.config.validator_enabled:
                result.validator = self.validator.analyze(context)
                result.agents_consulted.append("VALIDATOR")

                # Check for rejection
                if result.validator.position_modifier == 0:
                    result.can_trade = False
                    result.final_position_modifier = 0
                    result.recommendation = "REJECTED - Failed validation checks"
                    result.all_risks.extend(result.validator.risks_identified)
                    self._finalize_result(result, start_time)
                    return result

            # Phase 5: EXPLAINER - Generate Summary
            if self.config.explainer_enabled:
                result.explainer = self.explainer.analyze(context)
                result.agents_consulted.append("EXPLAINER")

            # Combine all outputs
            self._combine_outputs(result)
            self._finalize_result(result, start_time)

            # Audit logging
            self._log_analysis(result, context)

            return result

        except Exception as e:
            logger.error(f"Intelligence analysis failed: {e}")
            result.can_trade = False
            result.recommendation = f"Analysis failed: {str(e)}"
            result.all_warnings.append("Intelligence layer encountered an error")
            self._finalize_result(result, start_time)
            return result

    def quick_check(self, context: AgentContext) -> Dict[str, Any]:
        """
        Perform quick rule-based checks without full AI analysis.

        Useful for fast pre-filtering before expensive AI calls.
        """
        result = {
            "can_proceed": True,
            "position_modifier": 1.0,
            "warnings": [],
            "blockers": []
        }

        # Quick SENTINEL check
        sentinel_check = self.sentinel.quick_check(context)
        if not sentinel_check["can_trade"]:
            result["can_proceed"] = False
            result["position_modifier"] = 0
            result["blockers"].extend(sentinel_check["warnings"])
            return result

        result["position_modifier"] *= sentinel_check["position_modifier"]
        result["warnings"].extend(sentinel_check["warnings"])

        # Quick ANALYST check (if we have a symbol)
        if context.symbol:
            analyst_check = self.analyst.validate_signal(context)
            if not analyst_check["is_valid"]:
                result["can_proceed"] = False
                result["position_modifier"] = 0
                result["blockers"].extend(analyst_check["issues"])
                return result

            result["position_modifier"] *= analyst_check["position_modifier"]
            result["warnings"].extend(analyst_check["issues"])

        return result

    def _combine_outputs(self, result: IntelligenceResult):
        """Combine all agent outputs into final result."""
        # Calculate combined position modifier
        modifiers = []
        confidences = []

        for output in [result.sentinel, result.analyst, result.validator, result.learner]:
            if output:
                modifiers.append(output.position_modifier)
                confidences.append(output.confidence)
                result.all_bullish.extend(output.factors_bullish)
                result.all_bearish.extend(output.factors_bearish)
                result.all_risks.extend(output.risks_identified)

        # Multiply all modifiers
        result.final_position_modifier = 1.0
        for m in modifiers:
            result.final_position_modifier *= m

        # Determine overall confidence
        if Confidence.HIGH in confidences and Confidence.LOW not in confidences:
            result.confidence = Confidence.HIGH
        elif Confidence.LOW in confidences or Confidence.UNCERTAIN in confidences:
            result.confidence = Confidence.LOW
        else:
            result.confidence = Confidence.MEDIUM

        # Determine if we can trade
        result.can_trade = (
            result.final_position_modifier > 0 and
            result.confidence != Confidence.UNCERTAIN
        )

        # Generate recommendation
        if result.final_position_modifier == 0:
            result.recommendation = "NO TRADE"
        elif result.final_position_modifier < 0.5:
            result.recommendation = f"REDUCED SIZE ({result.final_position_modifier*100:.0f}% of normal)"
        elif result.final_position_modifier >= 1.0:
            result.recommendation = "FULL SIZE APPROVED"
        else:
            result.recommendation = f"MODERATE SIZE ({result.final_position_modifier*100:.0f}% of normal)"

        # Use explainer's one-liner if available
        if result.explainer and result.explainer.reasoning:
            result.recommendation = result.explainer.reasoning[0] or result.recommendation

    def _finalize_result(self, result: IntelligenceResult, start_time: datetime):
        """Finalize the result with timing information."""
        result.total_processing_time_ms = int(
            (datetime.now() - start_time).total_seconds() * 1000
        )

        # Deduplicate lists
        result.all_bullish = list(set(result.all_bullish))
        result.all_bearish = list(set(result.all_bearish))
        result.all_risks = list(set(result.all_risks))
        result.all_warnings = list(set(result.all_warnings))

    def _log_analysis(self, result: IntelligenceResult, context: AgentContext):
        """Log the analysis for audit purposes."""
        if not self.config.save_audit_trail:
            return

        context_summary = {
            'symbol': context.symbol,
            'regime': context.market_regime,
            'conviction': context.conviction_score,
            'data_quality': context.data_quality,
        }

        # Log each agent output
        for output in [result.sentinel, result.analyst, result.validator, result.learner, result.explainer]:
            if output:
                self.audit.log(output, context_summary)

    def get_summary(self, result: IntelligenceResult) -> str:
        """Get a human-readable summary of the intelligence result."""
        lines = []
        lines.append("=" * 60)
        lines.append("INTELLIGENCE LAYER SUMMARY")
        lines.append("=" * 60)

        lines.append(f"\nCan Trade: {'YES' if result.can_trade else 'NO'}")
        lines.append(f"Position Size: {result.final_position_modifier*100:.0f}%")
        lines.append(f"Confidence: {result.confidence.value.upper()}")
        lines.append(f"Recommendation: {result.recommendation}")

        if result.all_bullish:
            lines.append("\n[BULLISH FACTORS]")
            for factor in result.all_bullish[:5]:
                lines.append(f"  + {factor}")

        if result.all_bearish:
            lines.append("\n[BEARISH FACTORS]")
            for factor in result.all_bearish[:5]:
                lines.append(f"  - {factor}")

        if result.all_risks:
            lines.append("\n[RISKS]")
            for risk in result.all_risks[:5]:
                lines.append(f"  ! {risk}")

        lines.append(f"\nAgents consulted: {', '.join(result.agents_consulted)}")
        lines.append(f"Processing time: {result.total_processing_time_ms}ms")
        lines.append("=" * 60)

        return "\n".join(lines)


# Singleton instance
_orchestrator: Optional[IntelligenceOrchestrator] = None


def get_intelligence_orchestrator() -> IntelligenceOrchestrator:
    """Get intelligence orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IntelligenceOrchestrator()
    return _orchestrator
