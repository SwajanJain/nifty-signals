"""
Legendary Trader Exit Strategy Rules.

Implements exit strategies inspired by:
- Ed Seykota: "Cut losses short, let winners run" - wide trailing stops
- Jesse Livermore: "Big money is made in the sitting" - no time limit on winners
- Paul Tudor Jones: "Play great defense" - regime-aware exits
- Mark Minervini: Technical invalidation triggers
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pandas_ta as ta


class ExitReason(Enum):
    """Reason for exit."""
    STOP_LOSS = "STOP_LOSS"
    TARGET_1 = "TARGET_1"
    TARGET_2 = "TARGET_2"
    TARGET_3 = "TARGET_3"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_STOP = "TIME_STOP"
    OPPORTUNITY_COST = "OPPORTUNITY_COST"  # New: only for losers when better opportunity exists
    TECHNICAL_EXIT = "TECHNICAL_EXIT"
    REGIME_CHANGE = "REGIME_CHANGE"
    NEWS_EXIT = "NEWS_EXIT"
    MANUAL = "MANUAL"


class ExitUrgency(Enum):
    """Exit urgency level."""
    IMMEDIATE = "IMMEDIATE"     # Exit now at market
    END_OF_DAY = "END_OF_DAY"  # Exit before market close
    NEXT_SESSION = "NEXT_SESSION"  # Exit on next session open
    MONITOR = "MONITOR"        # Keep watching


@dataclass
class ExitSignal:
    """Exit signal with details."""
    should_exit: bool
    exit_type: ExitReason
    urgency: ExitUrgency
    exit_price: Optional[float]
    exit_quantity_pct: float  # Percentage to exit (0-100)
    reason: str
    new_stop_loss: Optional[float] = None  # For trailing stop updates


@dataclass
class TradePosition:
    """Current trade position."""
    symbol: str
    entry_date: datetime
    entry_price: float
    current_price: float
    stop_loss: float
    target_1: float
    target_2: float
    target_3: Optional[float]
    position_size: int
    remaining_size: int  # After partial exits
    atr: float
    direction: str = "LONG"


class ExitStrategyManager:
    """
    Legendary Trader Exit Strategy Manager.

    Implements:
    - Seykota: Wide trailing stops (3x ATR), 25/25/50 partial exits
    - Livermore: No time limit on winners, only exit losers
    - PTJ: Regime-aware exits
    - Minervini: Technical invalidation triggers

    Key Philosophy:
    "Let winners run, cut losers short"
    """

    def __init__(
        self,
        # Livermore: No max hold for winners - removed arbitrary 20-day limit
        time_stop_days: int = 10,  # Only for LOSERS - if no progress
        trailing_start_r: float = 1.5,  # Start trailing after 1.5R (Seykota)
        trailing_atr_multiple: float = 3.0,  # Wide 3x ATR trail (Seykota)
        partial_exit_1_pct: float = 25,  # Exit 25% at T1 (2R)
        partial_exit_2_pct: float = 25,  # Exit 25% at T2 (4R)
        # Remaining 50% rides with trailing stop to potential 10-20R
    ):
        """
        Initialize exit manager - Legendary Trader Edition.

        Key changes from standard:
        - No max_holding_days - Livermore held winners for months
        - Wide 3x ATR trailing stop - Seykota captures big trends
        - 25/25/50 exits - lets 50% of position capture big moves
        - Time stop only applies to LOSERS

        Args:
            time_stop_days: Days without progress before exit (LOSERS ONLY)
            trailing_start_r: R multiple to start trailing (default 1.5)
            trailing_atr_multiple: ATR multiple for trailing (default 3.0 - wide)
            partial_exit_1_pct: Percentage to exit at T1 (default 25%)
            partial_exit_2_pct: Percentage to exit at T2 (default 25%)
        """
        self.time_stop_days = time_stop_days
        self.trailing_start_r = trailing_start_r
        self.trailing_atr_multiple = trailing_atr_multiple
        self.partial_exit_1_pct = partial_exit_1_pct
        self.partial_exit_2_pct = partial_exit_2_pct

    def check_stop_loss(self, position: TradePosition) -> ExitSignal:
        """Check if stop loss is hit."""
        if position.direction == "LONG":
            if position.current_price <= position.stop_loss:
                return ExitSignal(
                    should_exit=True,
                    exit_type=ExitReason.STOP_LOSS,
                    urgency=ExitUrgency.IMMEDIATE,
                    exit_price=position.stop_loss,
                    exit_quantity_pct=100,
                    reason=f"Stop loss hit at {position.stop_loss}"
                )
        else:
            if position.current_price >= position.stop_loss:
                return ExitSignal(
                    should_exit=True,
                    exit_type=ExitReason.STOP_LOSS,
                    urgency=ExitUrgency.IMMEDIATE,
                    exit_price=position.stop_loss,
                    exit_quantity_pct=100,
                    reason=f"Stop loss hit at {position.stop_loss}"
                )

        return ExitSignal(
            should_exit=False,
            exit_type=ExitReason.STOP_LOSS,
            urgency=ExitUrgency.MONITOR,
            exit_price=None,
            exit_quantity_pct=0,
            reason="Stop loss not hit"
        )

    def check_targets(self, position: TradePosition, df: pd.DataFrame) -> ExitSignal:
        """Check if any targets are hit."""
        high = df['high'].iloc[-1] if position.direction == "LONG" else df['low'].iloc[-1]

        # Check T1
        if position.direction == "LONG":
            if high >= position.target_1:
                return ExitSignal(
                    should_exit=True,
                    exit_type=ExitReason.TARGET_1,
                    urgency=ExitUrgency.IMMEDIATE,
                    exit_price=position.target_1,
                    exit_quantity_pct=self.partial_exit_1_pct,
                    reason=f"Target 1 reached at {position.target_1}",
                    new_stop_loss=position.entry_price  # Move to breakeven
                )

            if high >= position.target_2:
                return ExitSignal(
                    should_exit=True,
                    exit_type=ExitReason.TARGET_2,
                    urgency=ExitUrgency.IMMEDIATE,
                    exit_price=position.target_2,
                    exit_quantity_pct=self.partial_exit_2_pct,
                    reason=f"Target 2 reached at {position.target_2}",
                    new_stop_loss=position.target_1  # Lock in T1 profit
                )

            if position.target_3 and high >= position.target_3:
                return ExitSignal(
                    should_exit=True,
                    exit_type=ExitReason.TARGET_3,
                    urgency=ExitUrgency.IMMEDIATE,
                    exit_price=position.target_3,
                    exit_quantity_pct=100,  # Exit all remaining
                    reason=f"Target 3 reached at {position.target_3}"
                )

        return ExitSignal(
            should_exit=False,
            exit_type=ExitReason.TARGET_1,
            urgency=ExitUrgency.MONITOR,
            exit_price=None,
            exit_quantity_pct=0,
            reason="No targets hit"
        )

    def calculate_trailing_stop(
        self,
        position: TradePosition,
        df: pd.DataFrame
    ) -> Tuple[float, bool]:
        """
        Calculate trailing stop using ATR or Chandelier method.

        Returns:
            Tuple of (new_stop_price, should_update)
        """
        # Calculate current profit in R
        risk = abs(position.entry_price - position.stop_loss)
        if risk == 0:
            return position.stop_loss, False

        if position.direction == "LONG":
            current_r = (position.current_price - position.entry_price) / risk
        else:
            current_r = (position.entry_price - position.current_price) / risk

        # Only start trailing after reaching trailing_start_r
        if current_r < self.trailing_start_r:
            return position.stop_loss, False

        # Calculate ATR-based trailing stop (Chandelier Exit)
        atr = position.atr
        if atr == 0:
            atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]

        # Find highest high (for long) in last 22 periods
        lookback = min(22, len(df))

        if position.direction == "LONG":
            highest_high = df['high'].tail(lookback).max()
            new_trailing_stop = highest_high - (self.trailing_atr_multiple * atr)

            # Only update if higher than current stop
            if new_trailing_stop > position.stop_loss:
                return round(new_trailing_stop, 2), True
        else:
            lowest_low = df['low'].tail(lookback).min()
            new_trailing_stop = lowest_low + (self.trailing_atr_multiple * atr)

            if new_trailing_stop < position.stop_loss:
                return round(new_trailing_stop, 2), True

        return position.stop_loss, False

    def check_time_stop(
        self,
        position: TradePosition,
        df: pd.DataFrame,
        better_opportunity_available: bool = False
    ) -> ExitSignal:
        """
        Check time-based exit conditions - Livermore Edition.

        KEY PHILOSOPHY: "Big money is made in the sitting"
        - NO max holding period for winners
        - Time stop ONLY applies to losing/flat positions
        - Opportunity cost exit only when better signal exists

        Args:
            position: Current position
            df: OHLCV DataFrame
            better_opportunity_available: True if a better signal exists
        """
        now = datetime.now()
        holding_days = (now - position.entry_date).days

        # Calculate current profit in R
        risk = abs(position.entry_price - position.stop_loss)
        if risk == 0:
            risk = position.entry_price * 0.02  # Fallback 2%

        if position.direction == "LONG":
            current_r = (position.current_price - position.entry_price) / risk
        else:
            current_r = (position.entry_price - position.current_price) / risk

        # LIVERMORE RULE: Winners have NO time limit
        if current_r >= 1.0:
            return ExitSignal(
                should_exit=False,
                exit_type=ExitReason.TIME_STOP,
                urgency=ExitUrgency.MONITOR,
                exit_price=None,
                exit_quantity_pct=0,
                reason=f"Winner at {current_r:.1f}R - no time limit (Livermore)"
            )

        # For losers/flat positions: check time stop
        if holding_days >= self.time_stop_days:
            # If losing or barely profitable after time_stop_days
            if current_r < 0.5:
                # Opportunity cost exit: only if better opportunity exists
                if better_opportunity_available:
                    return ExitSignal(
                        should_exit=True,
                        exit_type=ExitReason.OPPORTUNITY_COST,
                        urgency=ExitUrgency.NEXT_SESSION,
                        exit_price=position.current_price,
                        exit_quantity_pct=100,
                        reason=f"Dead money ({current_r:.1f}R after {holding_days}d) - better opportunity exists"
                    )
                else:
                    # No better opportunity - warn but don't force exit
                    return ExitSignal(
                        should_exit=False,
                        exit_type=ExitReason.TIME_STOP,
                        urgency=ExitUrgency.MONITOR,
                        exit_price=None,
                        exit_quantity_pct=0,
                        reason=f"Flat at {current_r:.1f}R for {holding_days}d - watch for better setup"
                    )

        return ExitSignal(
            should_exit=False,
            exit_type=ExitReason.TIME_STOP,
            urgency=ExitUrgency.MONITOR,
            exit_price=None,
            exit_quantity_pct=0,
            reason=f"Day {holding_days} | P&L: {current_r:.1f}R"
        )

    def check_technical_exit(self, position: TradePosition, df: pd.DataFrame) -> ExitSignal:
        """Check technical indicators for exit signals."""
        if len(df) < 20:
            return ExitSignal(
                should_exit=False,
                exit_type=ExitReason.TECHNICAL_EXIT,
                urgency=ExitUrgency.MONITOR,
                exit_price=None,
                exit_quantity_pct=0,
                reason="Insufficient data"
            )

        signals = []

        # RSI extreme
        rsi = ta.rsi(df['close'], length=14).iloc[-1]
        if position.direction == "LONG" and rsi > 80:
            signals.append(f"RSI overbought ({rsi:.0f})")
        elif position.direction == "SHORT" and rsi < 20:
            signals.append(f"RSI oversold ({rsi:.0f})")

        # MACD divergence/crossover
        macd_data = ta.macd(df['close'])
        macd_col = [c for c in macd_data.columns if c.startswith('MACD_')][0]
        signal_col = [c for c in macd_data.columns if c.startswith('MACDs_')][0]
        hist_col = [c for c in macd_data.columns if c.startswith('MACDh_')][0]

        macd_line = macd_data[macd_col].iloc[-1]
        signal_line = macd_data[signal_col].iloc[-1]
        hist = macd_data[hist_col].iloc[-1]
        prev_hist = macd_data[hist_col].iloc[-2]

        # Bearish crossover for long
        if position.direction == "LONG":
            if macd_line < signal_line and hist < prev_hist:
                signals.append("MACD bearish crossover")
        else:
            if macd_line > signal_line and hist > prev_hist:
                signals.append("MACD bullish crossover")

        # Price below key EMA
        ema_20 = ta.ema(df['close'], length=20).iloc[-1]
        if position.direction == "LONG" and position.current_price < ema_20 * 0.98:
            signals.append("Price broke below EMA20")
        elif position.direction == "SHORT" and position.current_price > ema_20 * 1.02:
            signals.append("Price broke above EMA20")

        # Volume spike on adverse move
        vol_sma = df['volume'].rolling(20).mean().iloc[-1]
        current_vol = df['volume'].iloc[-1]
        daily_change = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]

        if position.direction == "LONG":
            if daily_change < -0.02 and current_vol > vol_sma * 2:
                signals.append("High volume selloff")
        else:
            if daily_change > 0.02 and current_vol > vol_sma * 2:
                signals.append("High volume rally")

        if signals:
            return ExitSignal(
                should_exit=True,
                exit_type=ExitReason.TECHNICAL_EXIT,
                urgency=ExitUrgency.END_OF_DAY,
                exit_price=position.current_price,
                exit_quantity_pct=50,  # Partial exit on technical warning
                reason="; ".join(signals)
            )

        return ExitSignal(
            should_exit=False,
            exit_type=ExitReason.TECHNICAL_EXIT,
            urgency=ExitUrgency.MONITOR,
            exit_price=None,
            exit_quantity_pct=0,
            reason="No technical exit signals"
        )

    def evaluate_position(
        self,
        position: TradePosition,
        df: pd.DataFrame,
        market_regime: Optional[str] = None,
        better_opportunity_available: bool = False
    ) -> List[ExitSignal]:
        """
        Evaluate all exit conditions for a position - Legendary Trader Edition.

        Key Philosophy:
        - Stop loss is ALWAYS respected (defense first - PTJ)
        - Winners trail with wide stops (Seykota)
        - No arbitrary time limit on winners (Livermore)
        - Regime change overrides all (PTJ)

        Args:
            position: Current position
            df: OHLCV DataFrame
            market_regime: Current market regime (if known)
            better_opportunity_available: True if scanner found better signal

        Returns:
            List of ExitSignals sorted by urgency
        """
        signals = []

        # Check stop loss first (highest priority) - PTJ: "Defense first"
        sl_signal = self.check_stop_loss(position)
        if sl_signal.should_exit:
            signals.append(sl_signal)
            return signals  # Stop loss is immediate, don't check others

        # Check targets (25/25/50 exit plan)
        target_signal = self.check_targets(position, df)
        if target_signal.should_exit:
            signals.append(target_signal)

        # Calculate and check trailing stop (3x ATR - Seykota style)
        new_stop, should_update = self.calculate_trailing_stop(position, df)
        if should_update:
            signals.append(ExitSignal(
                should_exit=False,
                exit_type=ExitReason.TRAILING_STOP,
                urgency=ExitUrgency.MONITOR,
                exit_price=None,
                exit_quantity_pct=0,
                reason=f"Trail stop → Rs {new_stop} (3x ATR Chandelier)",
                new_stop_loss=new_stop
            ))

        # Check time/opportunity cost (Livermore: only exit losers)
        time_signal = self.check_time_stop(position, df, better_opportunity_available)
        if time_signal.should_exit:
            signals.append(time_signal)

        # Check technical exits (Minervini: invalidation triggers)
        tech_signal = self.check_technical_exit(position, df)
        if tech_signal.should_exit:
            signals.append(tech_signal)

        # Check regime change - PTJ: "Know when to be defensive"
        if market_regime in ["CRASH", "STRONG_BEAR"]:
            signals.append(ExitSignal(
                should_exit=True,
                exit_type=ExitReason.REGIME_CHANGE,
                urgency=ExitUrgency.END_OF_DAY,
                exit_price=position.current_price,
                exit_quantity_pct=100,
                reason=f"Regime → {market_regime} - exit all longs (PTJ defense)"
            ))

        # Sort by urgency
        urgency_order = {
            ExitUrgency.IMMEDIATE: 0,
            ExitUrgency.END_OF_DAY: 1,
            ExitUrgency.NEXT_SESSION: 2,
            ExitUrgency.MONITOR: 3
        }
        signals.sort(key=lambda x: urgency_order[x.urgency])

        return signals

    def get_exit_recommendation(
        self,
        signals: List[ExitSignal]
    ) -> Dict:
        """
        Get final exit recommendation from multiple signals.

        Args:
            signals: List of exit signals

        Returns:
            Dict with exit recommendation
        """
        if not signals:
            return {
                'action': 'HOLD',
                'reason': 'No exit signals',
                'urgency': 'NONE'
            }

        # Filter to actionable signals
        actionable = [s for s in signals if s.should_exit]

        if not actionable:
            # Check for stop updates
            stop_updates = [s for s in signals if s.new_stop_loss is not None]
            if stop_updates:
                return {
                    'action': 'UPDATE_STOP',
                    'new_stop': stop_updates[0].new_stop_loss,
                    'reason': stop_updates[0].reason,
                    'urgency': 'NONE'
                }
            return {
                'action': 'HOLD',
                'reason': 'No actionable exit signals',
                'urgency': 'NONE'
            }

        # Get highest priority signal
        primary_signal = actionable[0]

        # Aggregate exit quantity if multiple signals
        total_exit_pct = min(100, sum(s.exit_quantity_pct for s in actionable))

        return {
            'action': 'EXIT',
            'exit_type': primary_signal.exit_type.value,
            'exit_price': primary_signal.exit_price,
            'exit_quantity_pct': total_exit_pct,
            'urgency': primary_signal.urgency.value,
            'reason': primary_signal.reason,
            'all_reasons': [s.reason for s in actionable],
            'new_stop': primary_signal.new_stop_loss
        }


def print_exit_analysis(position: TradePosition, signals: List[ExitSignal]) -> str:
    """Generate printable exit analysis."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"EXIT ANALYSIS: {position.symbol}")
    lines.append("=" * 60)

    # Position summary
    holding_days = (datetime.now() - position.entry_date).days
    risk = abs(position.entry_price - position.stop_loss)
    current_r = (position.current_price - position.entry_price) / risk if risk > 0 else 0

    lines.append("")
    lines.append("POSITION STATUS")
    lines.append("-" * 40)
    lines.append(f"Entry: Rs {position.entry_price:.2f}")
    lines.append(f"Current: Rs {position.current_price:.2f}")
    lines.append(f"Stop Loss: Rs {position.stop_loss:.2f}")
    lines.append(f"Holding Days: {holding_days}")
    lines.append(f"Current P&L: {current_r:.2f}R ({(current_r * risk / position.entry_price * 100):.1f}%)")

    lines.append("")
    lines.append("EXIT SIGNALS")
    lines.append("-" * 40)

    if not signals:
        lines.append("No exit signals - HOLD position")
    else:
        for signal in signals:
            status = "EXIT" if signal.should_exit else "INFO"
            lines.append(f"[{status}] {signal.exit_type.value}: {signal.reason}")
            if signal.should_exit:
                lines.append(f"       Urgency: {signal.urgency.value}")
                lines.append(f"       Exit %: {signal.exit_quantity_pct}%")
            if signal.new_stop_loss:
                lines.append(f"       New Stop: Rs {signal.new_stop_loss:.2f}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
