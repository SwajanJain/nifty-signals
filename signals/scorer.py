"""Signal scoring and classification."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from config import (
    STRONG_BUY_THRESHOLD, BUY_THRESHOLD,
    SELL_THRESHOLD, STRONG_SELL_THRESHOLD
)


class SignalType(Enum):
    """Signal classification."""
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"


@dataclass
class StockSignal:
    """Complete signal for a stock."""
    symbol: str
    name: str
    price: float
    signal_type: SignalType
    total_score: int
    technical_score: int
    price_action_score: int
    technical_signals: Dict
    price_action_signals: Dict
    # New advanced analysis fields
    candlestick_signals: Dict = field(default_factory=dict)
    chart_pattern_signals: Dict = field(default_factory=dict)
    fibonacci_signals: Dict = field(default_factory=dict)
    divergence_signals: Dict = field(default_factory=dict)
    trend_strength_signals: Dict = field(default_factory=dict)

    @property
    def signal_strength(self) -> str:
        """Get signal strength as a string."""
        if self.total_score >= STRONG_BUY_THRESHOLD:
            return "Very Strong"
        elif self.total_score >= BUY_THRESHOLD:
            return "Strong"
        elif self.total_score >= 1:
            return "Moderate"
        elif self.total_score >= SELL_THRESHOLD:
            return "Moderate"
        elif self.total_score >= STRONG_SELL_THRESHOLD:
            return "Strong"
        else:
            return "Very Strong"

    @property
    def advanced_score(self) -> int:
        """Get combined score from advanced analysis."""
        score = 0
        if self.candlestick_signals:
            score += self.candlestick_signals.get('total_score', 0)
        if self.chart_pattern_signals:
            score += self.chart_pattern_signals.get('total_score', 0)
        if self.fibonacci_signals:
            score += self.fibonacci_signals.get('total_score', 0)
        if self.divergence_signals:
            score += self.divergence_signals.get('total_score', 0)
        if self.trend_strength_signals:
            score += self.trend_strength_signals.get('total_score', 0)
        return score


class SignalScorer:
    """Score and classify trading signals."""

    @staticmethod
    def classify_signal(total_score: int) -> SignalType:
        """
        Classify the signal based on total score.

        Args:
            total_score: Combined score from all indicators

        Returns:
            SignalType enum value
        """
        if total_score >= STRONG_BUY_THRESHOLD:
            return SignalType.STRONG_BUY
        elif total_score >= BUY_THRESHOLD:
            return SignalType.BUY
        elif total_score <= STRONG_SELL_THRESHOLD:
            return SignalType.STRONG_SELL
        elif total_score <= SELL_THRESHOLD:
            return SignalType.SELL
        else:
            return SignalType.HOLD

    @staticmethod
    def get_score_color(signal_type: SignalType) -> str:
        """Get color for the signal type (for CLI display)."""
        colors = {
            SignalType.STRONG_BUY: "bright_green",
            SignalType.BUY: "green",
            SignalType.HOLD: "yellow",
            SignalType.SELL: "red",
            SignalType.STRONG_SELL: "bright_red",
        }
        return colors.get(signal_type, "white")

    @staticmethod
    def format_score(score: int) -> str:
        """Format score with sign."""
        if score > 0:
            return f"+{score}"
        return str(score)
