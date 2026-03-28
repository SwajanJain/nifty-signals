"""
Intelligence Agents - Specialized AI analysts.

Each agent has a specific role in the trading decision process:
- SENTINEL: Market context assessment (go/no-go)
- ANALYST: Signal validation and enhancement
- VALIDATOR: Risk and sanity checks
- LEARNER: Pattern recognition from history
- EXPLAINER: Human-readable reasoning
"""

from .sentinel import SentinelAgent
from .analyst import AnalystAgent
from .validator import ValidatorAgent
from .learner import LearnerAgent
from .explainer import ExplainerAgent

__all__ = [
    'SentinelAgent',
    'AnalystAgent',
    'ValidatorAgent',
    'LearnerAgent',
    'ExplainerAgent',
]
