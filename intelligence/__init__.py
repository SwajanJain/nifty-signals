"""
Intelligence Layer - AI-augmented trading analysis.

This module provides a layer of AI-driven analysis that augments
the quantitative trading backbone with qualitative reasoning.

Key Components:
- SENTINEL: Market context assessment
- ANALYST: Signal validation
- VALIDATOR: Risk and sanity checks
- LEARNER: Pattern recognition
- EXPLAINER: Human-readable reasoning

Usage:
    from intelligence import get_intelligence_orchestrator, AgentContext

    orchestrator = get_intelligence_orchestrator()
    context = AgentContext(
        timestamp=datetime.now(),
        symbol="RELIANCE",
        market_regime="BULL",
        ...
    )
    result = orchestrator.analyze(context)
    print(orchestrator.get_summary(result))

Design Philosophy:
- AI is an ADVISOR, not a decision maker
- Quantitative backbone provides the foundation
- AI adds context, validation, and explanation
- All outputs are structured and auditable
- When uncertain, be conservative
"""

from .base import (
    AgentRole,
    Confidence,
    AgentContext,
    AgentOutput,
    IntelligenceConfig,
    AuditLogger,
    get_intelligence_config,
    get_audit_logger,
)

from .orchestrator import (
    IntelligenceOrchestrator,
    IntelligenceResult,
    get_intelligence_orchestrator,
)

from .agents import (
    SentinelAgent,
    AnalystAgent,
    ValidatorAgent,
    LearnerAgent,
    ExplainerAgent,
)

__all__ = [
    # Core types
    'AgentRole',
    'Confidence',
    'AgentContext',
    'AgentOutput',
    'IntelligenceConfig',
    'IntelligenceResult',
    # Orchestrator
    'IntelligenceOrchestrator',
    'get_intelligence_orchestrator',
    # Individual agents
    'SentinelAgent',
    'AnalystAgent',
    'ValidatorAgent',
    'LearnerAgent',
    'ExplainerAgent',
    # Config
    'get_intelligence_config',
    'get_audit_logger',
]
