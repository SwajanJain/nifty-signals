"""
Adaptive Exit System - Dynamic exit strategies based on market conditions.

Critical insights:
- Fixed exits ignore market context (fatal flaw)
- Trail tighter in volatile/bearish markets
- Let winners run in trending markets
- Cut losers faster when regime deteriorates
- Time-based exits prevent capital decay

Rule: Your exit is more important than your entry.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
from rich.console import Console

console = Console()


class ExitReason(Enum):
    """Reason for exit recommendation."""
    STOP_LOSS = "STOP_LOSS"
    TARGET_HIT = "TARGET_HIT"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_DECAY = "TIME_DECAY"
    REGIME_CHANGE = "REGIME_CHANGE"
    MOMENTUM_LOSS = "MOMENTUM_LOSS"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
    SECTOR_WEAKNESS = "SECTOR_WEAKNESS"
    EARNINGS_APPROACHING = "EARNINGS_APPROACHING"
    FII_EXODUS = "FII_EXODUS"
    PARTIAL_PROFIT = "PARTIAL_PROFIT"
    HOLD = "HOLD"


class ExitUrgency(Enum):
    """Urgency level for exit."""
    IMMEDIATE = "IMMEDIATE"  # Exit at market
    TODAY = "TODAY"  # Exit before close
    SOON = "SOON"  # Within 2-3 days
    MONITOR = "MONITOR"  # Watch for trigger
    HOLD = "HOLD"  # Continue holding


@dataclass
class TrailingStopConfig:
    """Configuration for trailing stop."""
    initial_stop_pct: float  # Initial stop %
    trail_activation_pct: float  # Profit % to activate trail
    trail_step_pct: float  # How tight to trail
    max_trail_pct: float  # Maximum trail tightness


@dataclass
class ActivePosition:
    """An active trading position."""
    symbol: str
    entry_price: float
    entry_date: datetime
    quantity: int
    direction: str  # LONG or SHORT

    # Stop and targets
    initial_stop: float
    current_stop: float
    target_1: float
    target_2: float

    # Current state
    current_price: float
    high_since_entry: float
    low_since_entry: float
    days_held: int

    # P&L
    unrealized_pnl: float
    unrealized_pnl_pct: float

    # Partial exits
    partial_exits: List[Dict] = field(default_factory=list)
    remaining_quantity: int = 0

    def __post_init__(self):
        if self.remaining_quantity == 0:
            self.remaining_quantity = self.quantity


@dataclass
class ExitRecommendation:
    """Exit recommendation for a position."""
    symbol: str
    action: str  # EXIT_ALL, EXIT_PARTIAL, TRAIL_STOP, HOLD
    reason: ExitReason
    urgency: ExitUrgency

    # Specific instructions
    exit_price: Optional[float] = None
    exit_quantity: Optional[int] = None
    new_stop: Optional[float] = None
    new_target: Optional[float] = None

    # Context
    confidence: float = 0.0  # 0-100%
    notes: List[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = [f"[{self.symbol}] {self.action}"]
        lines.append(f"  Reason: {self.reason.value}")
        lines.append(f"  Urgency: {self.urgency.value}")

        if self.exit_price:
            lines.append(f"  Exit at: ₹{self.exit_price:,.2f}")
        if self.exit_quantity:
            lines.append(f"  Quantity: {self.exit_quantity}")
        if self.new_stop:
            lines.append(f"  New Stop: ₹{self.new_stop:,.2f}")

        for note in self.notes:
            lines.append(f"  • {note}")

        return "\n".join(lines)


class AdaptiveExitSystem:
    """
    Dynamic exit system that adapts to market conditions.

    Exit strategies by regime:
    - STRONG_BULL: Wide trails, let winners run
    - BULL: Standard trails, book partials at targets
    - NEUTRAL: Tighter trails, faster profit booking
    - BEAR: Very tight trails, quick exits
    - CRASH: Exit all immediately
    """

    # Trailing stop configurations by regime
    TRAIL_CONFIG = {
        "STRONG_BULL": TrailingStopConfig(
            initial_stop_pct=4.0,
            trail_activation_pct=5.0,
            trail_step_pct=3.0,
            max_trail_pct=2.5
        ),
        "BULL": TrailingStopConfig(
            initial_stop_pct=3.5,
            trail_activation_pct=4.0,
            trail_step_pct=2.5,
            max_trail_pct=2.0
        ),
        "NEUTRAL": TrailingStopConfig(
            initial_stop_pct=3.0,
            trail_activation_pct=3.0,
            trail_step_pct=2.0,
            max_trail_pct=1.5
        ),
        "BEAR": TrailingStopConfig(
            initial_stop_pct=2.5,
            trail_activation_pct=2.0,
            trail_step_pct=1.5,
            max_trail_pct=1.0
        ),
        "STRONG_BEAR": TrailingStopConfig(
            initial_stop_pct=2.0,
            trail_activation_pct=1.5,
            trail_step_pct=1.0,
            max_trail_pct=0.75
        ),
        "CRASH": TrailingStopConfig(
            initial_stop_pct=1.0,
            trail_activation_pct=0.5,
            trail_step_pct=0.5,
            max_trail_pct=0.5
        ),
    }

    # Time decay rules (max days to hold without profit)
    TIME_DECAY_DAYS = {
        "STRONG_BULL": 20,
        "BULL": 15,
        "NEUTRAL": 10,
        "BEAR": 5,
        "STRONG_BEAR": 3,
        "CRASH": 1,
    }

    def __init__(self):
        self.positions: Dict[str, ActivePosition] = {}

    def evaluate_position(
        self,
        position: ActivePosition,
        regime: str,
        current_atr: float,
        sector_rank: int = 5,
        fii_flow_score: int = 0,
        earnings_days_away: Optional[int] = None,
        vix: float = 15
    ) -> ExitRecommendation:
        """
        Evaluate a position and return exit recommendation.

        Considers:
        1. Stop loss hit
        2. Target hit
        3. Trailing stop adjustment
        4. Time decay
        5. Regime change
        6. Sector weakness
        7. FII exodus
        8. Upcoming earnings
        9. Volatility spike
        """
        regime_upper = regime.upper()
        config = self.TRAIL_CONFIG.get(regime_upper, self.TRAIL_CONFIG["NEUTRAL"])
        max_days = self.TIME_DECAY_DAYS.get(regime_upper, 10)

        notes = []

        # === CRASH MODE: EXIT EVERYTHING ===
        if regime_upper == "CRASH":
            return ExitRecommendation(
                symbol=position.symbol,
                action="EXIT_ALL",
                reason=ExitReason.REGIME_CHANGE,
                urgency=ExitUrgency.IMMEDIATE,
                exit_price=position.current_price,
                exit_quantity=position.remaining_quantity,
                confidence=100,
                notes=["CRASH regime - Exit all positions immediately"]
            )

        # === CHECK STOP LOSS ===
        if position.current_price <= position.current_stop:
            return ExitRecommendation(
                symbol=position.symbol,
                action="EXIT_ALL",
                reason=ExitReason.STOP_LOSS,
                urgency=ExitUrgency.IMMEDIATE,
                exit_price=position.current_stop,
                exit_quantity=position.remaining_quantity,
                confidence=100,
                notes=["Stop loss triggered"]
            )

        # === CHECK TARGET HIT ===
        if position.current_price >= position.target_2:
            return ExitRecommendation(
                symbol=position.symbol,
                action="EXIT_ALL",
                reason=ExitReason.TARGET_HIT,
                urgency=ExitUrgency.TODAY,
                exit_price=position.target_2,
                exit_quantity=position.remaining_quantity,
                confidence=95,
                notes=["Target 2 reached - Book full profits"]
            )

        if position.current_price >= position.target_1:
            # Partial profit booking at T1
            partial_qty = position.remaining_quantity // 2
            if partial_qty > 0:
                return ExitRecommendation(
                    symbol=position.symbol,
                    action="EXIT_PARTIAL",
                    reason=ExitReason.PARTIAL_PROFIT,
                    urgency=ExitUrgency.TODAY,
                    exit_price=position.target_1,
                    exit_quantity=partial_qty,
                    new_stop=position.entry_price,  # Move stop to breakeven
                    confidence=90,
                    notes=[
                        "Target 1 reached - Book 50%",
                        "Move stop to breakeven"
                    ]
                )

        # === TRAILING STOP LOGIC ===
        pnl_pct = position.unrealized_pnl_pct

        if pnl_pct >= config.trail_activation_pct:
            # Calculate trailing stop
            trail_pct = max(config.max_trail_pct, config.trail_step_pct)

            # ATR-adjusted trail
            atr_trail = (current_atr / position.current_price) * 100 * 1.5
            trail_pct = max(trail_pct, atr_trail)

            new_stop = position.high_since_entry * (1 - trail_pct / 100)

            # Only raise stop, never lower
            if new_stop > position.current_stop:
                notes.append(f"Trailing stop: {trail_pct:.1f}% from high")
                notes.append(f"Profit lock: {((new_stop - position.entry_price) / position.entry_price * 100):.1f}%")

                return ExitRecommendation(
                    symbol=position.symbol,
                    action="TRAIL_STOP",
                    reason=ExitReason.TRAILING_STOP,
                    urgency=ExitUrgency.MONITOR,
                    new_stop=new_stop,
                    confidence=85,
                    notes=notes
                )

        # === TIME DECAY CHECK ===
        if position.days_held >= max_days and pnl_pct < 2:
            return ExitRecommendation(
                symbol=position.symbol,
                action="EXIT_ALL",
                reason=ExitReason.TIME_DECAY,
                urgency=ExitUrgency.SOON,
                exit_price=position.current_price,
                exit_quantity=position.remaining_quantity,
                confidence=75,
                notes=[
                    f"Held {position.days_held} days with minimal profit",
                    f"Max hold for {regime} regime: {max_days} days",
                    "Capital better deployed elsewhere"
                ]
            )

        # === REGIME DETERIORATION ===
        if regime_upper in ["BEAR", "STRONG_BEAR"] and pnl_pct > 0:
            # Tighten stop significantly in bearish regime
            tight_stop = position.current_price * (1 - config.initial_stop_pct / 100)
            if tight_stop > position.current_stop:
                return ExitRecommendation(
                    symbol=position.symbol,
                    action="TRAIL_STOP",
                    reason=ExitReason.REGIME_CHANGE,
                    urgency=ExitUrgency.TODAY,
                    new_stop=tight_stop,
                    confidence=80,
                    notes=[
                        f"Regime: {regime} - Tightening stops",
                        "Protect profits in adverse conditions"
                    ]
                )

        # === SECTOR WEAKNESS ===
        if sector_rank > 8:  # Bottom 3 sectors
            if pnl_pct < 3:
                return ExitRecommendation(
                    symbol=position.symbol,
                    action="EXIT_ALL",
                    reason=ExitReason.SECTOR_WEAKNESS,
                    urgency=ExitUrgency.SOON,
                    exit_price=position.current_price,
                    exit_quantity=position.remaining_quantity,
                    confidence=70,
                    notes=[
                        f"Sector rank: {sector_rank}/10 (weak)",
                        "Rotate to stronger sectors"
                    ]
                )

        # === FII EXODUS ===
        if fii_flow_score <= -3:
            # Heavy FII selling
            if pnl_pct < 5:
                return ExitRecommendation(
                    symbol=position.symbol,
                    action="EXIT_ALL",
                    reason=ExitReason.FII_EXODUS,
                    urgency=ExitUrgency.TODAY,
                    exit_price=position.current_price,
                    exit_quantity=position.remaining_quantity,
                    confidence=80,
                    notes=[
                        "Heavy FII selling detected",
                        "Smart money exiting - follow them"
                    ]
                )

        # === EARNINGS APPROACHING ===
        if earnings_days_away is not None and earnings_days_away <= 3:
            return ExitRecommendation(
                symbol=position.symbol,
                action="EXIT_ALL",
                reason=ExitReason.EARNINGS_APPROACHING,
                urgency=ExitUrgency.TODAY,
                exit_price=position.current_price,
                exit_quantity=position.remaining_quantity,
                confidence=90,
                notes=[
                    f"Earnings in {earnings_days_away} days",
                    "Exit before binary event"
                ]
            )

        # === VOLATILITY SPIKE ===
        if vix > 25:
            # Tighten stops in high volatility
            vol_adjusted_stop = position.current_price * 0.97  # 3% tight stop
            if vol_adjusted_stop > position.current_stop and pnl_pct > 0:
                return ExitRecommendation(
                    symbol=position.symbol,
                    action="TRAIL_STOP",
                    reason=ExitReason.VOLATILITY_SPIKE,
                    urgency=ExitUrgency.TODAY,
                    new_stop=vol_adjusted_stop,
                    confidence=75,
                    notes=[
                        f"VIX elevated: {vix}",
                        "Tightening stop due to volatility"
                    ]
                )

        # === MOMENTUM LOSS ===
        # Check if price has been declining from high
        decline_from_high = (position.high_since_entry - position.current_price) / position.high_since_entry * 100

        if decline_from_high > 5 and pnl_pct > 0 and pnl_pct < 3:
            return ExitRecommendation(
                symbol=position.symbol,
                action="EXIT_ALL",
                reason=ExitReason.MOMENTUM_LOSS,
                urgency=ExitUrgency.SOON,
                exit_price=position.current_price,
                exit_quantity=position.remaining_quantity,
                confidence=65,
                notes=[
                    f"Down {decline_from_high:.1f}% from high",
                    "Momentum fading - exit while profitable"
                ]
            )

        # === DEFAULT: HOLD ===
        return ExitRecommendation(
            symbol=position.symbol,
            action="HOLD",
            reason=ExitReason.HOLD,
            urgency=ExitUrgency.HOLD,
            confidence=60,
            notes=[
                f"P&L: {pnl_pct:+.1f}%",
                f"Days held: {position.days_held}",
                f"Current stop: ₹{position.current_stop:,.2f}"
            ]
        )

    def evaluate_all_positions(
        self,
        positions: List[ActivePosition],
        regime: str,
        sector_ranks: Dict[str, int],
        fii_flow_score: int,
        earnings_calendar: Dict[str, int],
        vix: float,
        atr_data: Dict[str, float]
    ) -> List[ExitRecommendation]:
        """Evaluate all positions and return recommendations."""
        recommendations = []

        for position in positions:
            atr = atr_data.get(position.symbol, position.current_price * 0.02)
            sector_rank = sector_ranks.get(position.symbol, 5)
            earnings_days = earnings_calendar.get(position.symbol)

            rec = self.evaluate_position(
                position=position,
                regime=regime,
                current_atr=atr,
                sector_rank=sector_rank,
                fii_flow_score=fii_flow_score,
                earnings_days_away=earnings_days,
                vix=vix
            )
            recommendations.append(rec)

        # Sort by urgency
        urgency_order = {
            ExitUrgency.IMMEDIATE: 0,
            ExitUrgency.TODAY: 1,
            ExitUrgency.SOON: 2,
            ExitUrgency.MONITOR: 3,
            ExitUrgency.HOLD: 4
        }

        return sorted(recommendations, key=lambda x: urgency_order[x.urgency])

    def calculate_optimal_stop(
        self,
        entry_price: float,
        current_price: float,
        atr: float,
        regime: str,
        support_level: Optional[float] = None
    ) -> float:
        """
        Calculate optimal stop loss.

        Uses:
        1. ATR-based stop
        2. Regime-adjusted multiplier
        3. Support level if available
        """
        regime_upper = regime.upper()
        config = self.TRAIL_CONFIG.get(regime_upper, self.TRAIL_CONFIG["NEUTRAL"])

        # ATR-based stop (usually 1.5-2x ATR)
        atr_multiplier = {
            "STRONG_BULL": 2.5,
            "BULL": 2.0,
            "NEUTRAL": 1.5,
            "BEAR": 1.2,
            "STRONG_BEAR": 1.0,
            "CRASH": 0.5,
        }.get(regime_upper, 1.5)

        atr_stop = entry_price - (atr * atr_multiplier)

        # Percentage-based stop
        pct_stop = entry_price * (1 - config.initial_stop_pct / 100)

        # Use the tighter of ATR or percentage stop
        calculated_stop = max(atr_stop, pct_stop)

        # If support level available, consider it
        if support_level and support_level < entry_price:
            # Place stop slightly below support
            support_stop = support_level * 0.995
            # Use support if it's tighter than calculated
            if support_stop > calculated_stop:
                calculated_stop = support_stop

        return round(calculated_stop, 2)

    def get_portfolio_exit_summary(
        self,
        recommendations: List[ExitRecommendation]
    ) -> str:
        """Get summary of all exit recommendations."""
        lines = []
        lines.append("=" * 60)
        lines.append("PORTFOLIO EXIT ANALYSIS")
        lines.append("=" * 60)

        immediate = [r for r in recommendations if r.urgency == ExitUrgency.IMMEDIATE]
        today = [r for r in recommendations if r.urgency == ExitUrgency.TODAY]
        soon = [r for r in recommendations if r.urgency == ExitUrgency.SOON]
        holds = [r for r in recommendations if r.urgency == ExitUrgency.HOLD]

        if immediate:
            lines.append("\n🚨 IMMEDIATE EXIT REQUIRED:")
            for r in immediate:
                lines.append(f"  {r.symbol}: {r.reason.value}")

        if today:
            lines.append("\n⚠️ EXIT TODAY:")
            for r in today:
                lines.append(f"  {r.symbol}: {r.reason.value}")

        if soon:
            lines.append("\n📋 EXIT SOON (2-3 days):")
            for r in soon:
                lines.append(f"  {r.symbol}: {r.reason.value}")

        if holds:
            lines.append(f"\n✅ HOLD ({len(holds)} positions)")

        lines.append("=" * 60)
        return "\n".join(lines)


def get_exit_recommendation(
    symbol: str,
    entry_price: float,
    current_price: float,
    entry_date: datetime,
    stop_loss: float,
    target: float,
    regime: str = "NEUTRAL",
    atr: Optional[float] = None
) -> ExitRecommendation:
    """Quick function to get exit recommendation for a single position."""
    system = AdaptiveExitSystem()

    if atr is None:
        atr = current_price * 0.02  # 2% default

    position = ActivePosition(
        symbol=symbol,
        entry_price=entry_price,
        entry_date=entry_date,
        quantity=1,
        direction="LONG",
        initial_stop=stop_loss,
        current_stop=stop_loss,
        target_1=target,
        target_2=target * 1.5,
        current_price=current_price,
        high_since_entry=max(entry_price, current_price),
        low_since_entry=min(entry_price, current_price),
        days_held=(datetime.now() - entry_date).days,
        unrealized_pnl=(current_price - entry_price),
        unrealized_pnl_pct=((current_price - entry_price) / entry_price) * 100
    )

    return system.evaluate_position(position, regime, atr)
