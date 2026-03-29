"""Valuation models -- DCF, DDM, Peer Relative, Monte Carlo."""

from dataclasses import dataclass, field
from typing import Dict, Optional

from .dcf import DCFValuation
from .ddm import DDMValuation
from .peer_relative import PeerRelativeValuation
from .monte_carlo import MonteCarloValuation


@dataclass
class ValuationResult:
    """Output of any valuation model."""

    symbol: str
    model: str  # "dcf", "ddm", "peer", "monte_carlo"
    fair_value: float = 0.0  # per share
    current_price: float = 0.0
    margin_of_safety_pct: float = 0.0  # (fair - current) / fair * 100
    signal: str = "FAIR"  # UNDERVALUED, FAIR, OVERVALUED, NOT_APPLICABLE
    confidence: str = "MEDIUM"  # HIGH, MEDIUM, LOW
    details: Dict[str, float] = field(default_factory=dict)
    assumptions: list = field(default_factory=list)


VALUATION_MODELS = {
    "dcf": DCFValuation,
    "ddm": DDMValuation,
    "peer": PeerRelativeValuation,
    "monte_carlo": MonteCarloValuation,
}


def get_valuation_model(name: str):
    """Return an instance of the requested valuation model.

    Raises ValueError for unknown model names.
    """
    cls = VALUATION_MODELS.get(name.lower())
    if cls is None:
        raise ValueError(
            f"Unknown valuation model: {name}. "
            f"Available: {list(VALUATION_MODELS.keys())}"
        )
    return cls()
