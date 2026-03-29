"""Smart Money Tracker (E2) — Velocity and acceleration of institutional flows.

Goes beyond static holding percentages to track *how fast* promoters,
FIIs, and DIIs are accumulating or distributing. Velocity (change per
quarter) and acceleration (change in velocity) reveal early institutional
conviction before the move shows up in price.

Key signals:
1. Promoter Accumulation Velocity — rate and acceleration of promoter buying
2. FII Accumulation Velocity — systematic institutional interest
3. DII Accumulation — mutual fund buying trend
4. Promoter Pledge Reduction — management deleveraging
5. Convergence Signal — multiple holder types accumulating simultaneously
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from fundamentals.models import FundamentalProfile, ScreenerRawData


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SmartMoneySignal:
    """A single holder-type accumulation/distribution signal."""

    holder_type: str  # "PROMOTER", "FII", "DII"
    action: str  # "ACCUMULATING", "DISTRIBUTING", "STABLE"
    velocity: float = 0.0  # % change per quarter (positive = buying)
    acceleration: float = 0.0  # change in velocity
    quarters_of_trend: int = 0
    strength: str = "WEAK"  # "STRONG", "MODERATE", "WEAK"


@dataclass
class SmartMoneyResult:
    """Composite smart money analysis for a single stock."""

    symbol: str
    composite_score: int = 0  # -100 to +100
    signal: str = "NEUTRAL"
    # "STRONG_ACCUMULATION", "ACCUMULATION", "NEUTRAL",
    # "DISTRIBUTION", "STRONG_DISTRIBUTION"
    smart_money_signals: List[SmartMoneySignal] = field(default_factory=list)
    convergence: bool = False  # Multiple types accumulating
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_quarterly_holdings(
    shareholding: List[Dict[str, Any]],
) -> Dict[str, List[float]]:
    """Parse raw shareholding rows into {holder_type: [oldest..newest]}.

    The shareholding list from screener has rows like:
        {"label": "Promoters", "Mar 2024": 52.3, "Dec 2023": 51.8, ...}

    Keys in the dict columns are quarter labels listed newest-first.
    We reverse so index 0 = oldest, index -1 = newest.
    """
    label_map = {
        "promoter": "PROMOTER",
        "fii": "FII",
        "dii": "DII",
    }

    result: Dict[str, List[float]] = {}

    for row in shareholding:
        row_label = str(row.get("label", "")).lower()
        holder_type = None
        for keyword, htype in label_map.items():
            if keyword in row_label:
                holder_type = htype
                break
        if holder_type is None:
            continue

        quarters = [k for k in row if k.lower() != "label"]
        # Screener lists newest first; reverse for chronological order
        values: List[float] = []
        for q in reversed(quarters):
            try:
                values.append(float(row[q]))
            except (ValueError, TypeError):
                continue

        if values:
            result[holder_type] = values

    return result


def _compute_velocity_acceleration(
    quarterly_values: List[float],
) -> Tuple[float, float]:
    """Compute velocity (avg change/quarter) and acceleration (change in velocity).

    Velocity = average of last 2 quarter-over-quarter changes.
    Acceleration = difference between most recent change and the one before it.
    """
    if len(quarterly_values) < 3:
        velocity = (
            quarterly_values[-1] - quarterly_values[-2]
            if len(quarterly_values) >= 2
            else 0.0
        )
        return round(velocity, 3), 0.0

    changes = [
        quarterly_values[i] - quarterly_values[i - 1]
        for i in range(1, len(quarterly_values))
    ]

    # Velocity: average of last 2 changes (or just last 1 if only 2 data points)
    recent_changes = changes[-2:] if len(changes) >= 2 else changes[-1:]
    velocity = sum(recent_changes) / len(recent_changes)

    # Acceleration: change in the rate of change
    if len(changes) >= 2:
        acceleration = changes[-1] - changes[-2]
    else:
        acceleration = 0.0

    return round(velocity, 3), round(acceleration, 3)


def _count_trend_quarters(quarterly_values: List[float]) -> Tuple[int, str]:
    """Count consecutive quarters of the current trend direction.

    Returns (count, direction) where direction is "UP", "DOWN", or "FLAT".
    """
    if len(quarterly_values) < 2:
        return 0, "FLAT"

    count = 0
    for i in range(len(quarterly_values) - 1, 0, -1):
        diff = quarterly_values[i] - quarterly_values[i - 1]
        if i == len(quarterly_values) - 1:
            # Establish direction from most recent change
            if diff > 0.05:
                direction = "UP"
            elif diff < -0.05:
                direction = "DOWN"
            else:
                direction = "FLAT"
                count = 1
                break
            count = 1
        else:
            if direction == "UP" and diff > 0.05:
                count += 1
            elif direction == "DOWN" and diff < -0.05:
                count += 1
            else:
                break

    return count, direction


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class SmartMoneyTracker:
    """Analyze velocity and acceleration of institutional money flows."""

    # Weights for composite score
    PROMOTER_WEIGHT = 0.40
    FII_WEIGHT = 0.35
    DII_WEIGHT = 0.25

    def analyze(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData,
    ) -> SmartMoneyResult:
        """Analyze shareholding patterns for smart money signals.

        Parameters
        ----------
        profile : Computed fundamental profile.
        raw     : Raw screener data (has quarterly shareholding table).
        """
        holdings = _parse_quarterly_holdings(raw.shareholding)
        signals: List[SmartMoneySignal] = []
        holder_scores: Dict[str, float] = {}

        # --- Promoter ---
        promoter_signal = self._analyze_holder(
            holdings.get("PROMOTER", []),
            "PROMOTER",
            profile,
        )
        if promoter_signal:
            signals.append(promoter_signal)
            holder_scores["PROMOTER"] = self._signal_to_score(promoter_signal)

        # --- FII ---
        fii_signal = self._analyze_holder(
            holdings.get("FII", []),
            "FII",
            profile,
        )
        if fii_signal:
            signals.append(fii_signal)
            holder_scores["FII"] = self._signal_to_score(fii_signal)

        # --- DII ---
        dii_signal = self._analyze_holder(
            holdings.get("DII", []),
            "DII",
            profile,
        )
        if dii_signal:
            signals.append(dii_signal)
            holder_scores["DII"] = self._signal_to_score(dii_signal)

        # --- Promoter pledge reduction ---
        pledge_signal = self._analyze_pledge(profile, holdings.get("PROMOTER", []))
        if pledge_signal:
            signals.append(pledge_signal)

        # --- Convergence ---
        accumulating = [
            s for s in signals
            if s.action == "ACCUMULATING" and s.holder_type in ("PROMOTER", "FII", "DII")
        ]
        convergence = len(accumulating) >= 2

        # --- Composite score ---
        composite = self._compute_composite(holder_scores, convergence, pledge_signal)

        # --- Overall signal classification ---
        if composite >= 50:
            overall = "STRONG_ACCUMULATION"
        elif composite >= 20:
            overall = "ACCUMULATION"
        elif composite <= -50:
            overall = "STRONG_DISTRIBUTION"
        elif composite <= -20:
            overall = "DISTRIBUTION"
        else:
            overall = "NEUTRAL"

        return SmartMoneyResult(
            symbol=profile.symbol,
            composite_score=composite,
            signal=overall,
            smart_money_signals=signals,
            convergence=convergence,
            details={
                "holder_scores": holder_scores,
                "convergence_types": [s.holder_type for s in accumulating],
                "quarterly_data_points": {
                    ht: len(vals) for ht, vals in holdings.items()
                },
            },
        )

    # ------------------------------------------------------------------
    # Per-holder analysis
    # ------------------------------------------------------------------

    def _analyze_holder(
        self,
        quarterly_values: List[float],
        holder_type: str,
        profile: FundamentalProfile,
    ) -> Optional[SmartMoneySignal]:
        """Analyze a single holder type's accumulation/distribution pattern."""
        if len(quarterly_values) < 2:
            return None

        velocity, acceleration = _compute_velocity_acceleration(quarterly_values)
        trend_quarters, trend_direction = _count_trend_quarters(quarterly_values)

        # Determine action
        if velocity > 0.1:
            action = "ACCUMULATING"
        elif velocity < -0.1:
            action = "DISTRIBUTING"
        else:
            action = "STABLE"

        # Determine strength based on velocity magnitude, acceleration, and trend
        strength = self._classify_strength(
            velocity, acceleration, trend_quarters, action
        )

        return SmartMoneySignal(
            holder_type=holder_type,
            action=action,
            velocity=velocity,
            acceleration=acceleration,
            quarters_of_trend=trend_quarters,
            strength=strength,
        )

    def _classify_strength(
        self,
        velocity: float,
        acceleration: float,
        trend_quarters: int,
        action: str,
    ) -> str:
        """Classify signal strength from velocity, acceleration, and persistence."""
        if action == "STABLE":
            return "WEAK"

        abs_vel = abs(velocity)

        # Strong: high velocity + sustained trend or positive acceleration
        if abs_vel >= 1.0 and trend_quarters >= 3:
            return "STRONG"
        if abs_vel >= 0.5 and acceleration > 0 and trend_quarters >= 2:
            return "STRONG"

        # Moderate: decent velocity with some persistence
        if abs_vel >= 0.5 and trend_quarters >= 2:
            return "MODERATE"
        if abs_vel >= 0.3 and trend_quarters >= 3:
            return "MODERATE"

        return "WEAK"

    # ------------------------------------------------------------------
    # Pledge analysis
    # ------------------------------------------------------------------

    def _analyze_pledge(
        self,
        profile: FundamentalProfile,
        promoter_values: List[float],
    ) -> Optional[SmartMoneySignal]:
        """Detect promoter pledge reduction as a positive signal.

        Low or declining pledge = management confidence / deleveraging.
        High or rising pledge = risk factor.
        """
        pledge = profile.promoter_pledge

        if pledge <= 0:
            # No pledge at all — slightly positive but not a signal on its own
            return None

        # Pledge reduction is positive; increase is negative
        # We encode this as a PROMOTER signal with a special action
        if pledge < 5:
            return SmartMoneySignal(
                holder_type="PROMOTER",
                action="ACCUMULATING",
                velocity=0,
                acceleration=0,
                quarters_of_trend=0,
                strength="WEAK",
            )
        elif pledge > 20:
            return SmartMoneySignal(
                holder_type="PROMOTER",
                action="DISTRIBUTING",
                velocity=0,
                acceleration=0,
                quarters_of_trend=0,
                strength="STRONG",
            )
        elif pledge > 10:
            return SmartMoneySignal(
                holder_type="PROMOTER",
                action="DISTRIBUTING",
                velocity=0,
                acceleration=0,
                quarters_of_trend=0,
                strength="MODERATE",
            )

        return None

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _signal_to_score(self, signal: SmartMoneySignal) -> float:
        """Convert a single signal to a -100 to +100 score."""
        direction = 1 if signal.action == "ACCUMULATING" else -1
        if signal.action == "STABLE":
            direction = 0

        # Base from velocity (normalized: 1% per quarter = high)
        base = min(abs(signal.velocity) * 40, 60) * direction

        # Acceleration bonus
        if signal.acceleration > 0 and signal.action == "ACCUMULATING":
            base += min(signal.acceleration * 20, 20)
        elif signal.acceleration < 0 and signal.action == "DISTRIBUTING":
            base += max(signal.acceleration * 20, -20)

        # Trend persistence bonus
        base += signal.quarters_of_trend * 5 * direction

        return max(-100, min(100, base))

    def _compute_composite(
        self,
        holder_scores: Dict[str, float],
        convergence: bool,
        pledge_signal: Optional[SmartMoneySignal],
    ) -> int:
        """Compute weighted composite score from holder-level scores."""
        weighted_sum = 0.0

        promoter_score = holder_scores.get("PROMOTER", 0)
        fii_score = holder_scores.get("FII", 0)
        dii_score = holder_scores.get("DII", 0)

        weighted_sum += promoter_score * self.PROMOTER_WEIGHT
        weighted_sum += fii_score * self.FII_WEIGHT
        weighted_sum += dii_score * self.DII_WEIGHT

        # Convergence bonus: +15 if multiple types accumulating together
        if convergence:
            weighted_sum += 15

        # Pledge penalty/bonus
        if pledge_signal:
            if pledge_signal.strength == "STRONG" and pledge_signal.action == "DISTRIBUTING":
                weighted_sum -= 15
            elif pledge_signal.strength == "MODERATE" and pledge_signal.action == "DISTRIBUTING":
                weighted_sum -= 8

        return max(-100, min(100, int(round(weighted_sum))))
