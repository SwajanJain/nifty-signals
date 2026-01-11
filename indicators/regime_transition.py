"""
Regime Transition Early Warning - Predict regime changes before they happen.

Critical insights:
- Regime changes don't happen overnight - early signs exist
- Breadth deterioration precedes index drops
- VIX spike + FII outflow = incoming storm
- Distribution days cluster before corrections
- Sector rotation signals regime shifts

Rule: The best trades are made BEFORE regime changes, not during.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
from rich.console import Console

console = Console()


class TransitionType(Enum):
    """Type of regime transition."""
    BULL_TO_NEUTRAL = "BULL_TO_NEUTRAL"
    BULL_TO_BEAR = "BULL_TO_BEAR"
    NEUTRAL_TO_BULL = "NEUTRAL_TO_BULL"
    NEUTRAL_TO_BEAR = "NEUTRAL_TO_BEAR"
    BEAR_TO_NEUTRAL = "BEAR_TO_NEUTRAL"
    BEAR_TO_BULL = "BEAR_TO_BULL"
    CRASH_WARNING = "CRASH_WARNING"
    RECOVERY_SIGNAL = "RECOVERY_SIGNAL"
    STABLE = "STABLE"


class WarningLevel(Enum):
    """Warning severity level."""
    CRITICAL = "CRITICAL"  # Act immediately
    HIGH = "HIGH"  # Prepare to act
    MODERATE = "MODERATE"  # Monitor closely
    LOW = "LOW"  # Early signal
    NONE = "NONE"  # No warning


@dataclass
class BreadthIndicators:
    """Market breadth indicators."""
    advance_decline_ratio: float  # > 1 bullish, < 1 bearish
    advance_decline_line: float  # Cumulative A/D
    new_highs_lows_ratio: float  # > 1 bullish
    percent_above_50ma: float  # % stocks above 50 MA
    percent_above_200ma: float  # % stocks above 200 MA
    mcclellan_oscillator: float  # Breadth momentum

    # Divergences
    price_breadth_divergence: bool  # Index up, breadth down
    divergence_days: int  # Days of divergence


@dataclass
class DistributionAnalysis:
    """Distribution day analysis (institutional selling)."""
    distribution_days_count: int  # In last 25 sessions
    distribution_days_dates: List[datetime]
    clustering: bool  # 4+ in 2 weeks = danger
    stalling_days: int  # Up on low volume
    accumulation_days: int  # For balance


@dataclass
class TransitionSignal:
    """Single transition warning signal."""
    signal_type: str
    description: str
    weight: float  # -1 to +1 (negative = bearish)
    triggered_at: datetime


@dataclass
class RegimeTransitionWarning:
    """Complete regime transition analysis."""
    current_regime: str
    predicted_regime: str
    transition_type: TransitionType
    warning_level: WarningLevel
    probability: float  # 0-100%

    # Time estimates
    estimated_days_to_transition: Optional[int]

    # Components
    breadth: BreadthIndicators
    distribution: DistributionAnalysis
    signals: List[TransitionSignal]

    # Scores
    bearish_score: float  # 0-100
    bullish_score: float  # 0-100

    # Recommendations
    action: str
    position_adjustment: float  # Multiplier (0.5 = half positions)
    notes: List[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = []
        lines.append("=" * 60)
        lines.append("REGIME TRANSITION WARNING")
        lines.append("=" * 60)

        lines.append(f"\nCurrent: {self.current_regime}")
        lines.append(f"Predicted: {self.predicted_regime}")
        lines.append(f"Transition: {self.transition_type.value}")
        lines.append(f"Warning Level: {self.warning_level.value}")
        lines.append(f"Probability: {self.probability:.0f}%")

        if self.estimated_days_to_transition:
            lines.append(f"Est. Time: {self.estimated_days_to_transition} days")

        lines.append(f"\n[BREADTH]")
        lines.append(f"  A/D Ratio: {self.breadth.advance_decline_ratio:.2f}")
        lines.append(f"  % > 50MA: {self.breadth.percent_above_50ma:.0f}%")
        lines.append(f"  % > 200MA: {self.breadth.percent_above_200ma:.0f}%")
        if self.breadth.price_breadth_divergence:
            lines.append(f"  ⚠️ DIVERGENCE: {self.breadth.divergence_days} days")

        lines.append(f"\n[DISTRIBUTION]")
        lines.append(f"  Distribution Days: {self.distribution.distribution_days_count}")
        if self.distribution.clustering:
            lines.append(f"  ⚠️ CLUSTERING DETECTED")

        lines.append(f"\n[SIGNALS]")
        for signal in self.signals[:5]:
            emoji = "🔴" if signal.weight < 0 else "🟢"
            lines.append(f"  {emoji} {signal.description}")

        lines.append(f"\n[ACTION]")
        lines.append(f"  {self.action}")
        lines.append(f"  Position Size: {self.position_adjustment:.0%} of normal")

        lines.append("=" * 60)
        return "\n".join(lines)


class RegimeTransitionDetector:
    """
    Detect regime transitions before they happen.

    Uses multiple leading indicators:
    1. Market breadth deterioration
    2. Distribution day clustering
    3. Sector rotation patterns
    4. VIX term structure
    5. FII flow momentum
    6. Global risk indicators
    """

    # Thresholds
    DISTRIBUTION_DANGER_THRESHOLD = 5  # 5+ in 25 days
    BREADTH_DIVERGENCE_DAYS = 5  # 5+ days of divergence
    CRITICAL_PERCENT_ABOVE_50MA = 30  # Below 30% = bearish
    BULLISH_PERCENT_ABOVE_50MA = 70  # Above 70% = bullish

    def __init__(self):
        self._cache: Dict = {}

    def analyze_breadth(self, market_data: pd.DataFrame) -> BreadthIndicators:
        """
        Analyze market breadth from Nifty 100 data.

        market_data should have columns: symbol, close, close_prev, ma_50, ma_200
        """
        if market_data.empty:
            return self._default_breadth()

        try:
            # Calculate advances/declines
            market_data['change'] = market_data['close'] - market_data['close_prev']
            advances = (market_data['change'] > 0).sum()
            declines = (market_data['change'] < 0).sum()

            # A/D Ratio
            ad_ratio = advances / max(declines, 1)

            # % above moving averages
            if 'ma_50' in market_data.columns:
                above_50ma = (market_data['close'] > market_data['ma_50']).mean() * 100
            else:
                above_50ma = 50  # Default

            if 'ma_200' in market_data.columns:
                above_200ma = (market_data['close'] > market_data['ma_200']).mean() * 100
            else:
                above_200ma = 50

            # New highs/lows (simplified)
            if 'high_52w' in market_data.columns and 'low_52w' in market_data.columns:
                new_highs = (market_data['close'] >= market_data['high_52w'] * 0.98).sum()
                new_lows = (market_data['close'] <= market_data['low_52w'] * 1.02).sum()
                nh_nl_ratio = new_highs / max(new_lows, 1)
            else:
                nh_nl_ratio = 1.0

            # McClellan Oscillator (simplified)
            # Real calc uses 19 and 39 day EMAs of A-D
            ad_diff = advances - declines
            mcclellan = ad_diff  # Simplified

            # Check for divergence (price up, breadth down)
            # This would need historical data - using placeholder
            divergence = above_50ma < 50 and ad_ratio < 1

            return BreadthIndicators(
                advance_decline_ratio=ad_ratio,
                advance_decline_line=ad_diff,
                new_highs_lows_ratio=nh_nl_ratio,
                percent_above_50ma=above_50ma,
                percent_above_200ma=above_200ma,
                mcclellan_oscillator=mcclellan,
                price_breadth_divergence=divergence,
                divergence_days=5 if divergence else 0
            )

        except Exception as e:
            console.print(f"[yellow]Breadth analysis error: {e}[/yellow]")
            return self._default_breadth()

    def _default_breadth(self) -> BreadthIndicators:
        """Return default breadth indicators."""
        return BreadthIndicators(
            advance_decline_ratio=1.0,
            advance_decline_line=0,
            new_highs_lows_ratio=1.0,
            percent_above_50ma=50,
            percent_above_200ma=50,
            mcclellan_oscillator=0,
            price_breadth_divergence=False,
            divergence_days=0
        )

    def analyze_distribution(
        self,
        index_data: pd.DataFrame,
        lookback: int = 25
    ) -> DistributionAnalysis:
        """
        Analyze distribution days (institutional selling).

        Distribution day criteria:
        - Index down > 0.2%
        - Volume higher than previous day
        - Occurs in uptrend
        """
        if index_data.empty or len(index_data) < lookback:
            return DistributionAnalysis(
                distribution_days_count=0,
                distribution_days_dates=[],
                clustering=False,
                stalling_days=0,
                accumulation_days=0
            )

        try:
            df = index_data.tail(lookback).copy()
            df['pct_change'] = df['close'].pct_change() * 100
            df['vol_change'] = df['volume'].pct_change()

            distribution_days = []
            stalling_days = 0
            accumulation_days = 0

            for idx, row in df.iterrows():
                # Distribution: Down > 0.2% on higher volume
                if row['pct_change'] < -0.2 and row['vol_change'] > 0:
                    distribution_days.append(idx)
                # Stalling: Up slightly on low volume (weak buying)
                elif 0 < row['pct_change'] < 0.3 and row['vol_change'] < -0.1:
                    stalling_days += 1
                # Accumulation: Up > 0.5% on higher volume
                elif row['pct_change'] > 0.5 and row['vol_change'] > 0:
                    accumulation_days += 1

            # Check for clustering (4+ distribution days in 2 weeks)
            if len(distribution_days) >= 4:
                recent_dist = [d for d in distribution_days if d >= df.index[-10]]
                clustering = len(recent_dist) >= 4
            else:
                clustering = False

            return DistributionAnalysis(
                distribution_days_count=len(distribution_days),
                distribution_days_dates=distribution_days,
                clustering=clustering,
                stalling_days=stalling_days,
                accumulation_days=accumulation_days
            )

        except Exception as e:
            console.print(f"[yellow]Distribution analysis error: {e}[/yellow]")
            return DistributionAnalysis(
                distribution_days_count=0,
                distribution_days_dates=[],
                clustering=False,
                stalling_days=0,
                accumulation_days=0
            )

    def detect_transition(
        self,
        current_regime: str,
        breadth: BreadthIndicators,
        distribution: DistributionAnalysis,
        vix: float = 15,
        fii_5d_flow: float = 0,
        global_risk_score: int = 3
    ) -> RegimeTransitionWarning:
        """
        Detect potential regime transition.

        Combines all signals to predict regime changes.
        """
        signals = []
        bearish_score = 0
        bullish_score = 0

        # === BREADTH SIGNALS ===

        # A/D Ratio
        if breadth.advance_decline_ratio < 0.5:
            signals.append(TransitionSignal(
                signal_type="breadth",
                description=f"Weak A/D ratio: {breadth.advance_decline_ratio:.2f}",
                weight=-0.8,
                triggered_at=datetime.now()
            ))
            bearish_score += 15
        elif breadth.advance_decline_ratio > 2.0:
            signals.append(TransitionSignal(
                signal_type="breadth",
                description=f"Strong A/D ratio: {breadth.advance_decline_ratio:.2f}",
                weight=0.8,
                triggered_at=datetime.now()
            ))
            bullish_score += 15

        # % Above 50 MA
        if breadth.percent_above_50ma < self.CRITICAL_PERCENT_ABOVE_50MA:
            signals.append(TransitionSignal(
                signal_type="breadth",
                description=f"Only {breadth.percent_above_50ma:.0f}% above 50MA",
                weight=-0.9,
                triggered_at=datetime.now()
            ))
            bearish_score += 20
        elif breadth.percent_above_50ma > self.BULLISH_PERCENT_ABOVE_50MA:
            signals.append(TransitionSignal(
                signal_type="breadth",
                description=f"{breadth.percent_above_50ma:.0f}% above 50MA",
                weight=0.7,
                triggered_at=datetime.now()
            ))
            bullish_score += 15

        # Divergence
        if breadth.price_breadth_divergence:
            signals.append(TransitionSignal(
                signal_type="divergence",
                description=f"Price-breadth divergence ({breadth.divergence_days} days)",
                weight=-0.9,
                triggered_at=datetime.now()
            ))
            bearish_score += 20

        # === DISTRIBUTION SIGNALS ===

        if distribution.distribution_days_count >= self.DISTRIBUTION_DANGER_THRESHOLD:
            signals.append(TransitionSignal(
                signal_type="distribution",
                description=f"{distribution.distribution_days_count} distribution days",
                weight=-0.8,
                triggered_at=datetime.now()
            ))
            bearish_score += 15

        if distribution.clustering:
            signals.append(TransitionSignal(
                signal_type="distribution",
                description="Distribution day clustering - DANGER",
                weight=-1.0,
                triggered_at=datetime.now()
            ))
            bearish_score += 25

        if distribution.accumulation_days > distribution.distribution_days_count:
            signals.append(TransitionSignal(
                signal_type="accumulation",
                description=f"{distribution.accumulation_days} accumulation days",
                weight=0.6,
                triggered_at=datetime.now()
            ))
            bullish_score += 10

        # === VIX SIGNALS ===

        if vix > 25:
            signals.append(TransitionSignal(
                signal_type="vix",
                description=f"Elevated VIX: {vix:.1f}",
                weight=-0.7,
                triggered_at=datetime.now()
            ))
            bearish_score += 15
        elif vix > 30:
            signals.append(TransitionSignal(
                signal_type="vix",
                description=f"HIGH VIX: {vix:.1f} - Crash risk",
                weight=-1.0,
                triggered_at=datetime.now()
            ))
            bearish_score += 25
        elif vix < 12:
            signals.append(TransitionSignal(
                signal_type="vix",
                description=f"Low VIX: {vix:.1f} - Complacency",
                weight=-0.3,
                triggered_at=datetime.now()
            ))
            bearish_score += 5  # Contrarian warning

        # === FII FLOW SIGNALS ===

        if fii_5d_flow < -5000:
            signals.append(TransitionSignal(
                signal_type="flows",
                description=f"Heavy FII selling: ₹{abs(fii_5d_flow):,.0f} Cr",
                weight=-0.9,
                triggered_at=datetime.now()
            ))
            bearish_score += 20
        elif fii_5d_flow < -2000:
            signals.append(TransitionSignal(
                signal_type="flows",
                description=f"FII outflow: ₹{abs(fii_5d_flow):,.0f} Cr",
                weight=-0.5,
                triggered_at=datetime.now()
            ))
            bearish_score += 10
        elif fii_5d_flow > 3000:
            signals.append(TransitionSignal(
                signal_type="flows",
                description=f"Strong FII inflow: ₹{fii_5d_flow:,.0f} Cr",
                weight=0.7,
                triggered_at=datetime.now()
            ))
            bullish_score += 15

        # === GLOBAL RISK SIGNALS ===

        if global_risk_score >= 4:
            signals.append(TransitionSignal(
                signal_type="global",
                description=f"High global risk score: {global_risk_score}/5",
                weight=-0.6,
                triggered_at=datetime.now()
            ))
            bearish_score += 10
        elif global_risk_score <= 1:
            signals.append(TransitionSignal(
                signal_type="global",
                description=f"Low global risk: {global_risk_score}/5",
                weight=0.5,
                triggered_at=datetime.now()
            ))
            bullish_score += 10

        # === DETERMINE TRANSITION ===

        net_score = bullish_score - bearish_score

        # Predict regime change
        transition_type, predicted_regime, warning_level, probability = self._determine_transition(
            current_regime, net_score, bearish_score, bullish_score
        )

        # Calculate position adjustment
        if warning_level == WarningLevel.CRITICAL:
            position_adjustment = 0.25
            action = "REDUCE EXPOSURE IMMEDIATELY"
        elif warning_level == WarningLevel.HIGH:
            position_adjustment = 0.5
            action = "Reduce positions, tighten stops"
        elif warning_level == WarningLevel.MODERATE:
            position_adjustment = 0.75
            action = "Monitor closely, no new positions"
        elif warning_level == WarningLevel.LOW:
            position_adjustment = 0.9
            action = "Early warning - stay alert"
        else:
            position_adjustment = 1.0
            action = "Normal operations"

        # Estimate days to transition
        if warning_level in [WarningLevel.CRITICAL, WarningLevel.HIGH]:
            est_days = 5
        elif warning_level == WarningLevel.MODERATE:
            est_days = 10
        elif warning_level == WarningLevel.LOW:
            est_days = 20
        else:
            est_days = None

        return RegimeTransitionWarning(
            current_regime=current_regime,
            predicted_regime=predicted_regime,
            transition_type=transition_type,
            warning_level=warning_level,
            probability=probability,
            estimated_days_to_transition=est_days,
            breadth=breadth,
            distribution=distribution,
            signals=sorted(signals, key=lambda x: abs(x.weight), reverse=True),
            bearish_score=bearish_score,
            bullish_score=bullish_score,
            action=action,
            position_adjustment=position_adjustment,
            notes=self._generate_notes(signals, current_regime)
        )

    def _determine_transition(
        self,
        current_regime: str,
        net_score: float,
        bearish_score: float,
        bullish_score: float
    ) -> Tuple[TransitionType, str, WarningLevel, float]:
        """Determine transition type and probability."""

        current_lower = current_regime.lower()

        # Strong bearish signals
        if bearish_score >= 60:
            if "bull" in current_lower:
                return (
                    TransitionType.BULL_TO_BEAR,
                    "BEAR",
                    WarningLevel.CRITICAL,
                    min(95, 50 + bearish_score * 0.5)
                )
            elif "neutral" in current_lower:
                return (
                    TransitionType.NEUTRAL_TO_BEAR,
                    "BEAR",
                    WarningLevel.HIGH,
                    min(90, 50 + bearish_score * 0.4)
                )
            elif "bear" in current_lower:
                return (
                    TransitionType.CRASH_WARNING,
                    "CRASH",
                    WarningLevel.CRITICAL,
                    min(85, 40 + bearish_score * 0.5)
                )

        # Moderate bearish
        elif bearish_score >= 40:
            if "bull" in current_lower:
                return (
                    TransitionType.BULL_TO_NEUTRAL,
                    "NEUTRAL",
                    WarningLevel.HIGH,
                    min(80, 40 + bearish_score * 0.4)
                )
            elif "neutral" in current_lower:
                return (
                    TransitionType.NEUTRAL_TO_BEAR,
                    "BEAR",
                    WarningLevel.MODERATE,
                    min(70, 30 + bearish_score * 0.4)
                )

        # Strong bullish signals
        elif bullish_score >= 50:
            if "bear" in current_lower:
                return (
                    TransitionType.BEAR_TO_NEUTRAL,
                    "NEUTRAL",
                    WarningLevel.LOW,  # Positive but cautious
                    min(75, 40 + bullish_score * 0.4)
                )
            elif "neutral" in current_lower:
                return (
                    TransitionType.NEUTRAL_TO_BULL,
                    "BULL",
                    WarningLevel.NONE,
                    min(70, 30 + bullish_score * 0.4)
                )

        # Mild bearish
        elif bearish_score >= 25:
            return (
                TransitionType.STABLE,
                current_regime,
                WarningLevel.LOW,
                30
            )

        # No clear signal
        return (
            TransitionType.STABLE,
            current_regime,
            WarningLevel.NONE,
            15
        )

    def _generate_notes(
        self,
        signals: List[TransitionSignal],
        current_regime: str
    ) -> List[str]:
        """Generate actionable notes."""
        notes = []

        bearish_signals = [s for s in signals if s.weight < 0]
        bullish_signals = [s for s in signals if s.weight > 0]

        if len(bearish_signals) > len(bullish_signals):
            notes.append("More bearish signals than bullish")

        # Check for dangerous combinations
        signal_types = [s.signal_type for s in bearish_signals]
        if "distribution" in signal_types and "flows" in signal_types:
            notes.append("Distribution + FII selling = Smart money exiting")

        if "breadth" in signal_types and "vix" in signal_types:
            notes.append("Weak breadth + High VIX = Correction likely")

        if "divergence" in signal_types:
            notes.append("Price-breadth divergence often precedes 5-10% corrections")

        return notes


def get_transition_warning(
    current_regime: str,
    market_data: Optional[pd.DataFrame] = None,
    index_data: Optional[pd.DataFrame] = None,
    vix: float = 15,
    fii_5d_flow: float = 0,
    global_risk_score: int = 3
) -> RegimeTransitionWarning:
    """Quick function to get regime transition warning."""
    detector = RegimeTransitionDetector()

    if market_data is not None:
        breadth = detector.analyze_breadth(market_data)
    else:
        breadth = detector._default_breadth()

    if index_data is not None:
        distribution = detector.analyze_distribution(index_data)
    else:
        distribution = DistributionAnalysis(
            distribution_days_count=0,
            distribution_days_dates=[],
            clustering=False,
            stalling_days=0,
            accumulation_days=0
        )

    return detector.detect_transition(
        current_regime=current_regime,
        breadth=breadth,
        distribution=distribution,
        vix=vix,
        fii_5d_flow=fii_5d_flow,
        global_risk_score=global_risk_score
    )
