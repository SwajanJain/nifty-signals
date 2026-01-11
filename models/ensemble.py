"""
Model Ensemble - Combines multiple models for robust signals.

Inspired by:
- Jim Simons: Multiple independent models, ensemble voting
- Ray Dalio: Systematic, diversified approach
- Ed Seykota: Different models for different regimes

Each model specializes in different market conditions:
- Momentum: Works in trending markets
- Mean Reversion: Works in ranging markets
- Breakout: Captures new trends
- Trend Following: Rides established trends
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np


class SignalDirection(Enum):
    """Signal direction."""
    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class ModelSignal:
    """Signal from a single model."""
    model_name: str
    direction: SignalDirection
    confidence: float  # 0-1
    weight: float  # Model weight in ensemble
    reasons: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    @property
    def weighted_score(self) -> float:
        """Get weighted score."""
        return self.direction.value * self.confidence * self.weight


@dataclass
class EnsembleSignal:
    """Combined signal from all models."""
    symbol: str
    direction: SignalDirection
    raw_score: float  # Sum of weighted scores
    normalized_score: float  # -1 to +1
    confidence: float  # 0-1
    agreement_pct: float  # % of models agreeing
    model_signals: List[ModelSignal]
    active_models: int
    agreeing_models: int
    reasons: List[str] = field(default_factory=list)

    @property
    def is_strong_signal(self) -> bool:
        """Check if signal is strong (high agreement + confidence)."""
        return self.agreement_pct >= 0.7 and self.confidence >= 0.6

    @property
    def confluence_count(self) -> int:
        """Count of models with same direction."""
        return self.agreeing_models


class BaseModel(ABC):
    """Base class for all signal models."""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight
        self.regime_weights = {
            'STRONG_BULL': 1.0,
            'BULL': 1.0,
            'NEUTRAL': 1.0,
            'BEAR': 1.0,
            'STRONG_BEAR': 1.0,
            'CRASH': 0.0
        }

    def get_regime_adjusted_weight(self, regime: str) -> float:
        """Get weight adjusted for current regime."""
        regime_mult = self.regime_weights.get(regime, 1.0)
        return self.weight * regime_mult

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, regime: str = "NEUTRAL") -> ModelSignal:
        """Generate signal from data."""
        pass


class ModelEnsemble:
    """
    Ensemble of multiple models.

    Combines signals using weighted voting.
    """

    def __init__(
        self,
        models: Optional[List[BaseModel]] = None,
        min_agreement: float = 0.5,  # Minimum model agreement for signal
        min_confidence: float = 0.4   # Minimum confidence threshold
    ):
        """
        Initialize ensemble.

        Args:
            models: List of models (if None, uses default set)
            min_agreement: Minimum fraction of models that must agree
            min_confidence: Minimum confidence for signal
        """
        self.models = models or []
        self.min_agreement = min_agreement
        self.min_confidence = min_confidence

    def add_model(self, model: BaseModel):
        """Add a model to ensemble."""
        self.models.append(model)

    def generate_ensemble_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        regime: str = "NEUTRAL"
    ) -> EnsembleSignal:
        """
        Generate combined signal from all models.

        Args:
            symbol: Stock symbol
            df: OHLCV DataFrame
            regime: Current market regime

        Returns:
            EnsembleSignal with combined result
        """
        if not self.models:
            return self._empty_signal(symbol)

        # Collect signals from all models
        model_signals = []
        for model in self.models:
            try:
                signal = model.generate_signal(df, regime)
                signal.weight = model.get_regime_adjusted_weight(regime)
                model_signals.append(signal)
            except Exception as e:
                # Skip failed models
                continue

        if not model_signals:
            return self._empty_signal(symbol)

        # Calculate ensemble metrics
        total_weight = sum(s.weight for s in model_signals)
        if total_weight == 0:
            return self._empty_signal(symbol)

        # Weighted score
        raw_score = sum(s.weighted_score for s in model_signals)

        # Normalize to -1 to +1
        max_possible = total_weight * 2  # Max if all models STRONG_BUY with conf 1
        normalized_score = raw_score / max_possible if max_possible > 0 else 0

        # Determine direction
        if normalized_score >= 0.5:
            direction = SignalDirection.STRONG_BUY
        elif normalized_score >= 0.2:
            direction = SignalDirection.BUY
        elif normalized_score <= -0.5:
            direction = SignalDirection.STRONG_SELL
        elif normalized_score <= -0.2:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.NEUTRAL

        # Calculate agreement
        if normalized_score > 0:
            # Count models agreeing on bullish
            agreeing = sum(1 for s in model_signals if s.direction.value > 0)
        elif normalized_score < 0:
            # Count models agreeing on bearish
            agreeing = sum(1 for s in model_signals if s.direction.value < 0)
        else:
            agreeing = sum(1 for s in model_signals if s.direction.value == 0)

        agreement_pct = agreeing / len(model_signals)

        # Calculate confidence
        confidences = [s.confidence for s in model_signals]
        avg_confidence = np.mean(confidences)

        # Boost confidence if high agreement
        if agreement_pct >= 0.8:
            confidence = min(1.0, avg_confidence * 1.2)
        elif agreement_pct >= 0.6:
            confidence = avg_confidence
        else:
            confidence = avg_confidence * 0.8

        # Collect reasons from agreeing models
        reasons = []
        for s in model_signals:
            if (normalized_score > 0 and s.direction.value > 0) or \
               (normalized_score < 0 and s.direction.value < 0):
                reasons.extend([f"[{s.model_name}] {r}" for r in s.reasons[:2]])

        return EnsembleSignal(
            symbol=symbol,
            direction=direction,
            raw_score=raw_score,
            normalized_score=normalized_score,
            confidence=confidence,
            agreement_pct=agreement_pct,
            model_signals=model_signals,
            active_models=len(model_signals),
            agreeing_models=agreeing,
            reasons=reasons[:10]  # Limit reasons
        )

    def _empty_signal(self, symbol: str) -> EnsembleSignal:
        """Create empty neutral signal."""
        return EnsembleSignal(
            symbol=symbol,
            direction=SignalDirection.NEUTRAL,
            raw_score=0,
            normalized_score=0,
            confidence=0,
            agreement_pct=0,
            model_signals=[],
            active_models=0,
            agreeing_models=0
        )

    def get_model_performance(self, results: List[Dict]) -> Dict:
        """
        Analyze historical performance of each model.

        Args:
            results: List of historical trade results

        Returns:
            Performance metrics per model
        """
        # Group results by model
        model_results = {m.name: [] for m in self.models}

        for result in results:
            signals = result.get('model_signals', [])
            outcome = result.get('outcome', 0)  # 1 = win, -1 = loss

            for sig in signals:
                model_name = sig.get('model_name')
                if model_name in model_results:
                    # Did this model's signal match outcome?
                    signal_dir = sig.get('direction', 0)
                    correct = (signal_dir > 0 and outcome > 0) or (signal_dir < 0 and outcome < 0)
                    model_results[model_name].append({
                        'correct': correct,
                        'confidence': sig.get('confidence', 0.5)
                    })

        # Calculate metrics
        performance = {}
        for model_name, trades in model_results.items():
            if not trades:
                continue

            correct_count = sum(1 for t in trades if t['correct'])
            total = len(trades)
            win_rate = correct_count / total if total > 0 else 0.5

            # Confidence-weighted accuracy
            weighted_correct = sum(t['confidence'] for t in trades if t['correct'])
            total_confidence = sum(t['confidence'] for t in trades)
            weighted_accuracy = weighted_correct / total_confidence if total_confidence > 0 else 0.5

            performance[model_name] = {
                'trades': total,
                'win_rate': win_rate,
                'weighted_accuracy': weighted_accuracy
            }

        return performance


def create_default_ensemble(regime: str = "NEUTRAL") -> ModelEnsemble:
    """
    Create default ensemble with all models.

    Args:
        regime: Current market regime for weight adjustment

    Returns:
        Configured ModelEnsemble
    """
    from .momentum import MomentumModel
    from .mean_reversion import MeanReversionModel
    from .breakout import BreakoutModel
    from .trend_following import TrendFollowingModel

    ensemble = ModelEnsemble()

    # Add models with regime-appropriate weights
    if regime in ['STRONG_BULL', 'BULL']:
        # Trending market - favor momentum and breakout
        ensemble.add_model(MomentumModel(weight=1.2))
        ensemble.add_model(BreakoutModel(weight=1.3))
        ensemble.add_model(TrendFollowingModel(weight=1.1))
        ensemble.add_model(MeanReversionModel(weight=0.6))

    elif regime in ['BEAR', 'STRONG_BEAR']:
        # Bearish - be cautious, favor defensive
        ensemble.add_model(MomentumModel(weight=0.7))
        ensemble.add_model(BreakoutModel(weight=0.5))
        ensemble.add_model(TrendFollowingModel(weight=0.8))
        ensemble.add_model(MeanReversionModel(weight=0.8))

    elif regime == 'CRASH':
        # Crash - minimal trading
        ensemble.add_model(MeanReversionModel(weight=0.3))

    else:
        # Neutral - balanced
        ensemble.add_model(MomentumModel(weight=1.0))
        ensemble.add_model(BreakoutModel(weight=1.0))
        ensemble.add_model(TrendFollowingModel(weight=1.0))
        ensemble.add_model(MeanReversionModel(weight=1.0))

    return ensemble
