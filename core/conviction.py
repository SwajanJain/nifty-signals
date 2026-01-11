"""
Conviction Scoring Engine.

Determines signal quality based on multiple factors:
- Technical confluence
- Context alignment
- Historical performance
- Signal source reliability

Inspired by Mark Minervini's SEPA and William O'Neil's CAN SLIM scoring.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np


class ConvictionLevel(Enum):
    """Conviction levels with associated risk."""
    A_PLUS = ("A+", 0.025)   # 2.5% risk - Exceptional setup
    A = ("A", 0.02)          # 2.0% risk - High conviction
    B = ("B", 0.01)          # 1.0% risk - Standard
    C = ("C", 0.005)         # 0.5% risk - Low conviction
    D = ("D", 0.0)           # 0.0% risk - No trade

    def __init__(self, label: str, risk_pct: float):
        self.label = label
        self.risk_pct = risk_pct


@dataclass
class ConvictionFactors:
    """All factors that contribute to conviction."""
    # Technical quality (0-25)
    technical_score: float = 0
    technical_max: float = 25

    # Confluence (0-20)
    confluence_score: float = 0
    confluence_max: float = 20

    # Context alignment (0-20)
    context_score: float = 0
    context_max: float = 20

    # Sector/Relative strength (0-15)
    sector_score: float = 0
    sector_max: float = 15

    # Timing quality (0-10)
    timing_score: float = 0
    timing_max: float = 10

    # Historical edge (0-10)
    historical_score: float = 0
    historical_max: float = 10

    @property
    def total(self) -> float:
        return (
            self.technical_score +
            self.confluence_score +
            self.context_score +
            self.sector_score +
            self.timing_score +
            self.historical_score
        )

    @property
    def max_possible(self) -> float:
        return (
            self.technical_max +
            self.confluence_max +
            self.context_max +
            self.sector_max +
            self.timing_max +
            self.historical_max
        )

    @property
    def percentage(self) -> float:
        return (self.total / self.max_possible) * 100


class ConvictionScorer:
    """
    Score trading signals for conviction level.

    Higher conviction = larger position size.
    Low conviction = skip or tiny position.
    """

    def __init__(
        self,
        signal_weights: Optional[Dict[str, float]] = None,
        min_confluence: int = 2,
        require_mtf_alignment: bool = True
    ):
        """
        Initialize scorer.

        Args:
            signal_weights: Custom weights for different signal sources
            min_confluence: Minimum signals for consideration
            require_mtf_alignment: Whether MTF alignment is required
        """
        self.signal_weights = signal_weights or {
            'rsi_oversold': 1.0,
            'macd_cross': 1.2,
            'ema_alignment': 1.0,
            'volume_breakout': 1.5,
            'support_bounce': 1.3,
            'resistance_break': 1.5,
            'bullish_candle': 0.8,
            'bullish_divergence': 1.4,
            'chart_pattern': 1.6,
            'fibonacci_level': 1.0,
            'adx_trending': 1.1
        }
        self.min_confluence = min_confluence
        self.require_mtf_alignment = require_mtf_alignment

    def score_technical(
        self,
        raw_score: int,
        signal_details: Dict
    ) -> Tuple[float, List[str]]:
        """
        Score technical signal quality.

        Args:
            raw_score: Combined indicator score
            signal_details: Individual signal details

        Returns:
            (score, reasoning)
        """
        reasoning = []

        # Base score from raw (normalized to 0-15)
        # Assuming raw_score ranges from -15 to +15
        normalized = ((raw_score + 15) / 30) * 15
        normalized = max(0, min(15, normalized))

        reasoning.append(f"Base technical: {normalized:.1f}/15 (raw: {raw_score:+d})")

        # Bonus for key signals
        bonus = 0

        # Check for strong signals
        if signal_details.get('breakout_with_volume', False):
            bonus += 3
            reasoning.append("Breakout with volume: +3")

        if signal_details.get('bullish_divergence', False):
            bonus += 2
            reasoning.append("Bullish divergence: +2")

        if signal_details.get('at_support', False):
            bonus += 2
            reasoning.append("At support level: +2")

        if signal_details.get('golden_cross', False):
            bonus += 2
            reasoning.append("Golden cross: +2")

        # Penalty for weak signals
        if signal_details.get('extended_from_ema', False):
            bonus -= 2
            reasoning.append("Extended from EMA: -2")

        if signal_details.get('low_volume', False):
            bonus -= 2
            reasoning.append("Low volume: -2")

        total = min(25, normalized + bonus)
        reasoning.append(f"Technical total: {total:.1f}/25")

        return total, reasoning

    def score_confluence(
        self,
        active_signals: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Score signal confluence.

        More aligned signals = higher conviction.
        """
        reasoning = []
        count = len(active_signals)

        if count < self.min_confluence:
            reasoning.append(f"Only {count} signals (min: {self.min_confluence})")
            return 0, reasoning

        # Calculate weighted confluence
        weighted_sum = sum(
            self.signal_weights.get(sig, 1.0)
            for sig in active_signals
        )

        # Normalize to 0-20
        # Assume max weighted sum around 10
        score = min(20, (weighted_sum / 10) * 20)

        reasoning.append(f"Confluence: {count} signals, weighted: {weighted_sum:.1f}")
        reasoning.append(f"Confluence score: {score:.1f}/20")

        return score, reasoning

    def score_context(
        self,
        regime_score: int,
        mtf_alignment: int,
        global_risk_score: float
    ) -> Tuple[float, List[str]]:
        """
        Score context alignment (regime, MTF, global).
        """
        reasoning = []
        score = 0

        # Regime contribution (0-8)
        if regime_score >= 5:
            regime_contrib = 8
        elif regime_score >= 2:
            regime_contrib = 6
        elif regime_score >= 0:
            regime_contrib = 4
        elif regime_score >= -2:
            regime_contrib = 2
        else:
            regime_contrib = 0

        score += regime_contrib
        reasoning.append(f"Regime: {regime_contrib}/8 (score: {regime_score:+d})")

        # MTF contribution (0-8)
        if mtf_alignment >= 2:
            mtf_contrib = 8
        elif mtf_alignment == 1:
            mtf_contrib = 6
        elif mtf_alignment == 0:
            mtf_contrib = 2
        else:
            mtf_contrib = 0
            if self.require_mtf_alignment:
                reasoning.append("MTF CONFLICT - Requires alignment")

        score += mtf_contrib
        reasoning.append(f"MTF: {mtf_contrib}/8 (alignment: {mtf_alignment:+d})")

        # Global risk (0-4)
        if global_risk_score >= 1:
            global_contrib = 4
        elif global_risk_score >= 0:
            global_contrib = 3
        elif global_risk_score >= -1:
            global_contrib = 1
        else:
            global_contrib = 0

        score += global_contrib
        reasoning.append(f"Global: {global_contrib}/4 (risk score: {global_risk_score:+.1f})")

        reasoning.append(f"Context total: {score}/20")
        return min(20, score), reasoning

    def score_sector(
        self,
        sector_rank: int,
        sector_strength: str,
        is_sector_leader: bool,
        relative_strength: float
    ) -> Tuple[float, List[str]]:
        """
        Score sector positioning.
        """
        reasoning = []
        score = 0

        # Sector rank contribution (0-7)
        if sector_rank <= 3:
            rank_contrib = 7
        elif sector_rank <= 5:
            rank_contrib = 5
        elif sector_rank <= 8:
            rank_contrib = 3
        else:
            rank_contrib = 1

        score += rank_contrib
        reasoning.append(f"Sector rank #{sector_rank}: {rank_contrib}/7")

        # Sector strength (0-5)
        strength_scores = {'STRONG': 5, 'MODERATE': 3, 'WEAK': 1, 'VERY_WEAK': 0}
        strength_contrib = strength_scores.get(sector_strength, 2)
        score += strength_contrib
        reasoning.append(f"Sector strength ({sector_strength}): {strength_contrib}/5")

        # Leader bonus (0-3)
        if is_sector_leader:
            score += 3
            reasoning.append("Sector leader: +3")

        reasoning.append(f"Sector total: {score}/15")
        return min(15, score), reasoning

    def score_timing(
        self,
        distance_to_entry: float,  # % from ideal entry
        days_since_breakout: int,
        volume_confirmation: bool
    ) -> Tuple[float, List[str]]:
        """
        Score entry timing quality.
        """
        reasoning = []
        score = 0

        # Distance to ideal entry (0-4)
        if distance_to_entry <= 1:
            dist_contrib = 4
        elif distance_to_entry <= 2:
            dist_contrib = 3
        elif distance_to_entry <= 3:
            dist_contrib = 2
        else:
            dist_contrib = 0

        score += dist_contrib
        reasoning.append(f"Entry distance ({distance_to_entry:.1f}%): {dist_contrib}/4")

        # Days since breakout (0-3)
        if days_since_breakout <= 1:
            days_contrib = 3
        elif days_since_breakout <= 3:
            days_contrib = 2
        elif days_since_breakout <= 5:
            days_contrib = 1
        else:
            days_contrib = 0

        score += days_contrib
        reasoning.append(f"Days since signal ({days_since_breakout}): {days_contrib}/3")

        # Volume confirmation (0-3)
        if volume_confirmation:
            score += 3
            reasoning.append("Volume confirmed: +3")
        else:
            reasoning.append("No volume confirmation: +0")

        reasoning.append(f"Timing total: {score}/10")
        return min(10, score), reasoning

    def score_historical(
        self,
        pattern_win_rate: float,
        avg_rr_achieved: float,
        sample_size: int
    ) -> Tuple[float, List[str]]:
        """
        Score based on historical performance of similar setups.
        """
        reasoning = []

        if sample_size < 10:
            reasoning.append(f"Insufficient history ({sample_size} samples)")
            return 5, reasoning  # Neutral score

        score = 0

        # Win rate contribution (0-5)
        if pattern_win_rate >= 0.7:
            wr_contrib = 5
        elif pattern_win_rate >= 0.6:
            wr_contrib = 4
        elif pattern_win_rate >= 0.5:
            wr_contrib = 3
        elif pattern_win_rate >= 0.4:
            wr_contrib = 1
        else:
            wr_contrib = 0

        score += wr_contrib
        reasoning.append(f"Win rate ({pattern_win_rate*100:.0f}%): {wr_contrib}/5")

        # Avg R:R contribution (0-5)
        if avg_rr_achieved >= 2.0:
            rr_contrib = 5
        elif avg_rr_achieved >= 1.5:
            rr_contrib = 4
        elif avg_rr_achieved >= 1.0:
            rr_contrib = 2
        else:
            rr_contrib = 0

        score += rr_contrib
        reasoning.append(f"Avg R:R ({avg_rr_achieved:.1f}): {rr_contrib}/5")

        reasoning.append(f"Historical total: {score}/10")
        return min(10, score), reasoning

    def calculate_conviction(
        self,
        technical_score: int,
        signal_details: Dict,
        active_signals: List[str],
        regime_score: int,
        mtf_alignment: int,
        global_risk_score: float,
        sector_rank: int,
        sector_strength: str,
        is_sector_leader: bool,
        relative_strength: float,
        distance_to_entry: float,
        days_since_breakout: int,
        volume_confirmation: bool,
        pattern_win_rate: float = 0.55,
        avg_rr_achieved: float = 1.5,
        sample_size: int = 50
    ) -> Tuple[ConvictionLevel, float, ConvictionFactors, List[str]]:
        """
        Calculate overall conviction.

        Returns:
            (level, score, factors, reasoning)
        """
        all_reasoning = []

        # Calculate all component scores
        tech_score, tech_reasoning = self.score_technical(technical_score, signal_details)
        all_reasoning.extend(tech_reasoning)

        conf_score, conf_reasoning = self.score_confluence(active_signals)
        all_reasoning.extend(conf_reasoning)

        ctx_score, ctx_reasoning = self.score_context(regime_score, mtf_alignment, global_risk_score)
        all_reasoning.extend(ctx_reasoning)

        sector_score, sector_reasoning = self.score_sector(
            sector_rank, sector_strength, is_sector_leader, relative_strength
        )
        all_reasoning.extend(sector_reasoning)

        timing_score, timing_reasoning = self.score_timing(
            distance_to_entry, days_since_breakout, volume_confirmation
        )
        all_reasoning.extend(timing_reasoning)

        hist_score, hist_reasoning = self.score_historical(
            pattern_win_rate, avg_rr_achieved, sample_size
        )
        all_reasoning.extend(hist_reasoning)

        # Create factors object
        factors = ConvictionFactors(
            technical_score=tech_score,
            confluence_score=conf_score,
            context_score=ctx_score,
            sector_score=sector_score,
            timing_score=timing_score,
            historical_score=hist_score
        )

        # Determine level
        total_pct = factors.percentage

        # Check for disqualifying conditions
        if self.require_mtf_alignment and mtf_alignment < 0:
            level = ConvictionLevel.D
            all_reasoning.append("DISQUALIFIED: MTF conflict")
        elif len(active_signals) < self.min_confluence:
            level = ConvictionLevel.D
            all_reasoning.append(f"DISQUALIFIED: Only {len(active_signals)} signals")
        elif total_pct >= 85:
            level = ConvictionLevel.A_PLUS
        elif total_pct >= 70:
            level = ConvictionLevel.A
        elif total_pct >= 55:
            level = ConvictionLevel.B
        elif total_pct >= 40:
            level = ConvictionLevel.C
        else:
            level = ConvictionLevel.D

        all_reasoning.append(f"\nFINAL: {factors.total:.0f}/{factors.max_possible:.0f} ({total_pct:.0f}%) → {level.label}")

        return level, factors.total, factors, all_reasoning


def get_conviction_summary(level: ConvictionLevel, factors: ConvictionFactors) -> str:
    """Generate human-readable conviction summary."""
    lines = []
    lines.append("=" * 50)
    lines.append(f"CONVICTION: {level.label} ({factors.percentage:.0f}%)")
    lines.append(f"Risk Allocation: {level.risk_pct * 100:.1f}%")
    lines.append("=" * 50)

    lines.append("\nBreakdown:")
    lines.append(f"  Technical:   {factors.technical_score:.0f}/{factors.technical_max:.0f}")
    lines.append(f"  Confluence:  {factors.confluence_score:.0f}/{factors.confluence_max:.0f}")
    lines.append(f"  Context:     {factors.context_score:.0f}/{factors.context_max:.0f}")
    lines.append(f"  Sector:      {factors.sector_score:.0f}/{factors.sector_max:.0f}")
    lines.append(f"  Timing:      {factors.timing_score:.0f}/{factors.timing_max:.0f}")
    lines.append(f"  Historical:  {factors.historical_score:.0f}/{factors.historical_max:.0f}")
    lines.append(f"  {'─' * 30}")
    lines.append(f"  TOTAL:       {factors.total:.0f}/{factors.max_possible:.0f}")

    return "\n".join(lines)
