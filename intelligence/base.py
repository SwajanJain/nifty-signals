"""
Intelligence Layer Base - Foundation for AI-driven analysis.

This module provides the base infrastructure for AI agents that augment
the quantitative trading system with qualitative reasoning.

Design Philosophy:
- AI is an ADVISOR, not a decision maker
- Quantitative backbone provides the foundation
- AI adds context, validation, and explanation
- All AI outputs are structured and auditable
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TypeVar, Generic
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
import logging
import os

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Roles of intelligence agents."""
    SENTINEL = "sentinel"      # Market context assessment
    ANALYST = "analyst"        # Signal validation and enhancement
    VALIDATOR = "validator"    # Risk and sanity checks
    LEARNER = "learner"        # Pattern recognition from history
    EXPLAINER = "explainer"    # Human-readable reasoning


class Confidence(Enum):
    """Confidence levels for AI assessments."""
    HIGH = "high"           # >80% confidence
    MEDIUM = "medium"       # 50-80% confidence
    LOW = "low"             # <50% confidence
    UNCERTAIN = "uncertain" # Cannot assess


@dataclass
class AgentContext:
    """Context provided to an agent for analysis."""
    timestamp: datetime
    symbol: Optional[str] = None

    # Market data
    price_data: Dict[str, Any] = field(default_factory=dict)
    technical_indicators: Dict[str, Any] = field(default_factory=dict)

    # External context
    market_regime: str = "NEUTRAL"
    sector_data: Dict[str, Any] = field(default_factory=dict)
    global_context: Dict[str, Any] = field(default_factory=dict)
    fii_dii_data: Dict[str, Any] = field(default_factory=dict)

    # Signals from quantitative system
    quantitative_signals: Dict[str, Any] = field(default_factory=dict)
    ensemble_votes: Dict[str, bool] = field(default_factory=dict)
    conviction_score: int = 0

    # Historical context
    recent_trades: List[Dict[str, Any]] = field(default_factory=list)
    performance_stats: Dict[str, Any] = field(default_factory=dict)

    # Data quality
    data_quality: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class AgentOutput:
    """Structured output from an agent."""
    agent_role: AgentRole
    timestamp: datetime

    # Core assessment
    assessment: str  # Main conclusion
    confidence: Confidence
    reasoning: List[str]  # Step-by-step reasoning

    # Structured outputs
    factors_bullish: List[str] = field(default_factory=list)
    factors_bearish: List[str] = field(default_factory=list)
    risks_identified: List[str] = field(default_factory=list)

    # Recommendations
    recommendation: str = ""
    position_modifier: float = 1.0  # Multiplier for position size (0.0 to 1.5)

    # Metadata
    processing_time_ms: int = 0
    model_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['agent_role'] = self.agent_role.value
        data['timestamp'] = self.timestamp.isoformat()
        data['confidence'] = self.confidence.value
        return data

    @property
    def is_actionable(self) -> bool:
        """Whether the output is actionable (high/medium confidence)."""
        return self.confidence in [Confidence.HIGH, Confidence.MEDIUM]


class IntelligenceAgent(ABC):
    """
    Base class for all intelligence agents.

    Each agent has a specific role and provides structured analysis
    that augments the quantitative system.
    """

    def __init__(
        self,
        role: AgentRole,
        model: str = "claude-3-haiku-20240307",
        enabled: bool = True
    ):
        self.role = role
        self.model = model
        self.enabled = enabled
        self._last_output: Optional[AgentOutput] = None

    @property
    def name(self) -> str:
        """Agent name."""
        return f"{self.role.value.upper()}_AGENT"

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        pass

    @abstractmethod
    def format_context(self, context: AgentContext) -> str:
        """Format context into a prompt for the agent."""
        pass

    @abstractmethod
    def parse_response(self, response: str, context: AgentContext) -> AgentOutput:
        """Parse the AI response into structured output."""
        pass

    def analyze(self, context: AgentContext) -> AgentOutput:
        """
        Perform analysis on the given context.

        This is the main entry point for agent analysis.
        Override for custom implementations (e.g., mock for testing).
        """
        if not self.enabled:
            return self._disabled_output(context)

        start_time = datetime.now()

        try:
            # Get the AI response (implemented by subclass or AI caller)
            response = self._call_ai(context)

            # Parse into structured output
            output = self.parse_response(response, context)
            output.processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            output.model_used = self.model

            self._last_output = output
            return output

        except Exception as e:
            logger.error(f"{self.name} analysis failed: {e}")
            return self._error_output(context, str(e))

    def _call_ai(self, context: AgentContext) -> str:
        """
        Call the AI model.

        This is a placeholder - actual implementation depends on how
        Claude is integrated (via API, CLI, etc.)

        For now, returns a structured mock response.
        """
        # In production, this would call Claude API
        # For now, return a structured placeholder
        return self._generate_mock_response(context)

    def _generate_mock_response(self, context: AgentContext) -> str:
        """Generate a mock response for testing."""
        return json.dumps({
            "assessment": "Analysis pending - AI integration required",
            "confidence": "medium",
            "reasoning": ["Mock response generated", "AI API not connected"],
            "factors_bullish": [],
            "factors_bearish": [],
            "risks": [],
            "recommendation": "Proceed with quantitative signals",
            "position_modifier": 1.0
        })

    def _disabled_output(self, context: AgentContext) -> AgentOutput:
        """Output when agent is disabled."""
        return AgentOutput(
            agent_role=self.role,
            timestamp=datetime.now(),
            assessment="Agent disabled",
            confidence=Confidence.UNCERTAIN,
            reasoning=["Agent is disabled in configuration"],
            recommendation="Using quantitative signals only",
            position_modifier=1.0
        )

    def _error_output(self, context: AgentContext, error: str) -> AgentOutput:
        """Output when agent encounters an error."""
        return AgentOutput(
            agent_role=self.role,
            timestamp=datetime.now(),
            assessment=f"Analysis error: {error}",
            confidence=Confidence.UNCERTAIN,
            reasoning=[f"Error occurred: {error}", "Falling back to quantitative signals"],
            risks_identified=["AI analysis unavailable"],
            recommendation="Proceed with caution using quantitative signals only",
            position_modifier=0.8  # Slight reduction due to uncertainty
        )


@dataclass
class IntelligenceConfig:
    """Configuration for the intelligence layer."""
    # Agent enablement
    sentinel_enabled: bool = True
    analyst_enabled: bool = True
    validator_enabled: bool = True
    learner_enabled: bool = True
    explainer_enabled: bool = True

    # Model selection
    default_model: str = "claude-3-haiku-20240307"
    analyst_model: str = "claude-3-haiku-20240307"  # Can upgrade for deeper analysis

    # Behavior
    require_high_confidence: bool = False  # Require HIGH confidence for action
    min_confidence_for_trade: Confidence = Confidence.MEDIUM

    # Output
    verbose_reasoning: bool = True
    save_audit_trail: bool = True
    audit_trail_path: str = "journal/ai_audit.jsonl"

    @classmethod
    def from_env(cls) -> 'IntelligenceConfig':
        """Load configuration from environment variables."""
        return cls(
            sentinel_enabled=os.getenv('AI_SENTINEL_ENABLED', 'true').lower() == 'true',
            analyst_enabled=os.getenv('AI_ANALYST_ENABLED', 'true').lower() == 'true',
            validator_enabled=os.getenv('AI_VALIDATOR_ENABLED', 'true').lower() == 'true',
            learner_enabled=os.getenv('AI_LEARNER_ENABLED', 'true').lower() == 'true',
            explainer_enabled=os.getenv('AI_EXPLAINER_ENABLED', 'true').lower() == 'true',
            default_model=os.getenv('AI_DEFAULT_MODEL', 'claude-3-haiku-20240307'),
        )


class AuditLogger:
    """Logs all AI interactions for audit and learning."""

    def __init__(self, filepath: str = "journal/ai_audit.jsonl"):
        self.filepath = filepath
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

    def log(
        self,
        agent_output: AgentOutput,
        context_summary: Dict[str, Any],
        eventual_outcome: Optional[str] = None
    ):
        """Log an agent interaction."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'agent': agent_output.agent_role.value,
            'assessment': agent_output.assessment,
            'confidence': agent_output.confidence.value,
            'reasoning': agent_output.reasoning,
            'recommendation': agent_output.recommendation,
            'position_modifier': agent_output.position_modifier,
            'context_summary': context_summary,
            'eventual_outcome': eventual_outcome,
            'model': agent_output.model_used,
            'processing_time_ms': agent_output.processing_time_ms
        }

        try:
            with open(self.filepath, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")

    def get_recent_entries(self, n: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit entries."""
        entries = []
        try:
            with open(self.filepath, 'r') as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
            return entries[-n:]
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
            return []


# Singleton instances
_config: Optional[IntelligenceConfig] = None
_audit_logger: Optional[AuditLogger] = None


def get_intelligence_config() -> IntelligenceConfig:
    """Get intelligence configuration singleton."""
    global _config
    if _config is None:
        _config = IntelligenceConfig.from_env()
    return _config


def get_audit_logger() -> AuditLogger:
    """Get audit logger singleton."""
    global _audit_logger
    if _audit_logger is None:
        config = get_intelligence_config()
        _audit_logger = AuditLogger(config.audit_trail_path)
    return _audit_logger
