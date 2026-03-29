"""Financial scoring models — Piotroski F-Score, Altman Z-Score, Beneish M-Score."""

from .piotroski import PiotroskiFScore
from .altman import AltmanZScore
from .beneish import BeneishMScore

SCORING_MODELS = {
    'piotroski': PiotroskiFScore,
    'altman': AltmanZScore,
    'beneish': BeneishMScore,
}

def get_scoring_model(name: str):
    cls = SCORING_MODELS.get(name.lower())
    if cls is None:
        raise ValueError(f"Unknown scoring model: {name}. Available: {list(SCORING_MODELS.keys())}")
    return cls()
