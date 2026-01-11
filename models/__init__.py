"""
Multi-Model Signal Generation.

Inspired by Jim Simons' Renaissance Technologies approach:
- Multiple independent models
- Ensemble voting
- Probability-weighted decisions
"""

from .ensemble import ModelEnsemble, EnsembleSignal
from .momentum import MomentumModel
from .mean_reversion import MeanReversionModel
from .breakout import BreakoutModel
from .trend_following import TrendFollowingModel

__all__ = [
    'ModelEnsemble',
    'EnsembleSignal',
    'MomentumModel',
    'MeanReversionModel',
    'BreakoutModel',
    'TrendFollowingModel'
]
