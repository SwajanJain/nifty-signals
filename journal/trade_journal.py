"""
Trade Journal System - Track, analyze, and learn from every trade.

Critical insights:
- You can't improve what you don't measure
- Patterns emerge from systematic tracking
- Best traders are best journalers
- Review is more important than execution
- Edge comes from learning, not from signals

Rule: Every trade teaches something. Capture it.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import json
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()


class TradeResult(Enum):
    """Trade outcome."""
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
    OPEN = "OPEN"


class TradeType(Enum):
    """Type of trade."""
    MOMENTUM = "MOMENTUM"
    BREAKOUT = "BREAKOUT"
    TREND_FOLLOWING = "TREND_FOLLOWING"
    MEAN_REVERSION = "MEAN_REVERSION"
    SWING = "SWING"
    POSITIONAL = "POSITIONAL"


class ExitType(Enum):
    """How the trade was exited."""
    TARGET_HIT = "TARGET_HIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_EXIT = "TIME_EXIT"
    MANUAL = "MANUAL"
    REGIME_CHANGE = "REGIME_CHANGE"
    OPEN = "OPEN"


@dataclass
class TradeEntry:
    """A single trade entry in the journal."""
    # Identifiers
    trade_id: str
    symbol: str
    trade_date: datetime

    # Entry details
    entry_price: float
    entry_time: datetime
    position_size: int
    position_value: float
    direction: str  # LONG or SHORT

    # Exit details
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_type: ExitType = ExitType.OPEN

    # Trade setup
    trade_type: TradeType = TradeType.SWING
    conviction_level: str = "B"
    conviction_score: int = 50

    # Context at entry
    regime: str = "NEUTRAL"
    sector: str = ""
    sector_rank: int = 5
    vix_at_entry: float = 15

    # Planned levels
    planned_stop: float = 0.0
    planned_target1: float = 0.0
    planned_target2: float = 0.0
    planned_rr: float = 2.0

    # Actual results
    pnl: float = 0.0
    pnl_pct: float = 0.0
    result: TradeResult = TradeResult.OPEN
    mae: float = 0.0  # Maximum Adverse Excursion
    mfe: float = 0.0  # Maximum Favorable Excursion

    # Model signals at entry
    momentum_signal: bool = False
    breakout_signal: bool = False
    trend_signal: bool = False
    mean_rev_signal: bool = False
    models_agreeing: int = 0

    # Notes and lessons
    entry_reason: str = ""
    exit_reason: str = ""
    mistakes: List[str] = field(default_factory=list)
    lessons: List[str] = field(default_factory=list)
    emotional_state: str = ""  # Calm/Anxious/FOMO/Greedy/Fear
    followed_plan: bool = True

    # Tags for analysis
    tags: List[str] = field(default_factory=list)

    def close_trade(
        self,
        exit_price: float,
        exit_time: datetime,
        exit_type: ExitType,
        exit_reason: str = ""
    ) -> None:
        """Close the trade and calculate results."""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_type = exit_type
        self.exit_reason = exit_reason

        # Calculate P&L
        if self.direction == "LONG":
            self.pnl = (exit_price - self.entry_price) * self.position_size
            self.pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * 100
        else:
            self.pnl = (self.entry_price - exit_price) * self.position_size
            self.pnl_pct = ((self.entry_price - exit_price) / self.entry_price) * 100

        # Determine result
        if self.pnl_pct > 0.5:
            self.result = TradeResult.WIN
        elif self.pnl_pct < -0.5:
            self.result = TradeResult.LOSS
        else:
            self.result = TradeResult.BREAKEVEN

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        data = asdict(self)
        # Convert enums and datetimes
        data['trade_date'] = self.trade_date.isoformat()
        data['entry_time'] = self.entry_time.isoformat()
        data['exit_time'] = self.exit_time.isoformat() if self.exit_time else None
        data['exit_type'] = self.exit_type.value
        data['trade_type'] = self.trade_type.value
        data['result'] = self.result.value
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeEntry':
        """Create from dictionary."""
        data['trade_date'] = datetime.fromisoformat(data['trade_date'])
        data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        data['exit_time'] = datetime.fromisoformat(data['exit_time']) if data['exit_time'] else None
        data['exit_type'] = ExitType(data['exit_type'])
        data['trade_type'] = TradeType(data['trade_type'])
        data['result'] = TradeResult(data['result'])
        return cls(**data)


@dataclass
class JournalStats:
    """Aggregated journal statistics."""
    total_trades: int = 0
    open_trades: int = 0
    closed_trades: int = 0

    # Win/Loss
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    win_rate: float = 0.0

    # P&L
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0

    # Streaks
    current_streak: int = 0
    best_streak: int = 0
    worst_streak: int = 0

    # By category
    by_regime: Dict[str, Dict] = field(default_factory=dict)
    by_trade_type: Dict[str, Dict] = field(default_factory=dict)
    by_conviction: Dict[str, Dict] = field(default_factory=dict)
    by_sector: Dict[str, Dict] = field(default_factory=dict)

    # Performance metrics
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_mae: float = 0.0
    avg_mfe: float = 0.0

    # Behavioral
    plan_adherence: float = 0.0
    avg_hold_time_days: float = 0.0


class TradeJournal:
    """
    Complete trade journal system.

    Features:
    1. Trade logging with full context
    2. Performance analytics
    3. Pattern recognition
    4. Mistake tracking
    5. Lesson extraction
    6. Regime-based analysis
    7. Export to various formats
    """

    def __init__(self, journal_path: str = "journal/trades.json"):
        self.journal_path = Path(journal_path)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.trades: List[TradeEntry] = []
        self._load_journal()

    def _load_journal(self) -> None:
        """Load journal from file."""
        if self.journal_path.exists():
            try:
                with open(self.journal_path, 'r') as f:
                    data = json.load(f)
                    self.trades = [TradeEntry.from_dict(t) for t in data]
                console.print(f"[green]Loaded {len(self.trades)} trades from journal[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not load journal: {e}[/yellow]")
                self.trades = []
        else:
            self.trades = []

    def _save_journal(self) -> None:
        """Save journal to file."""
        try:
            with open(self.journal_path, 'w') as f:
                json.dump([t.to_dict() for t in self.trades], f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving journal: {e}[/red]")

    def add_trade(self, trade: TradeEntry) -> str:
        """Add a new trade to journal."""
        # Generate trade ID if not provided
        if not trade.trade_id:
            trade.trade_id = f"{trade.symbol}_{trade.trade_date.strftime('%Y%m%d_%H%M%S')}"

        self.trades.append(trade)
        self._save_journal()

        console.print(f"[green]Trade added: {trade.trade_id}[/green]")
        return trade.trade_id

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_type: ExitType,
        exit_reason: str = "",
        mistakes: List[str] = None,
        lessons: List[str] = None
    ) -> Optional[TradeEntry]:
        """Close an existing trade."""
        for trade in self.trades:
            if trade.trade_id == trade_id:
                trade.close_trade(
                    exit_price=exit_price,
                    exit_time=datetime.now(),
                    exit_type=exit_type,
                    exit_reason=exit_reason
                )
                if mistakes:
                    trade.mistakes = mistakes
                if lessons:
                    trade.lessons = lessons

                self._save_journal()
                console.print(f"[green]Trade closed: {trade_id} | P&L: ₹{trade.pnl:,.2f} ({trade.pnl_pct:+.1f}%)[/green]")
                return trade

        console.print(f"[red]Trade not found: {trade_id}[/red]")
        return None

    def get_open_trades(self) -> List[TradeEntry]:
        """Get all open trades."""
        return [t for t in self.trades if t.result == TradeResult.OPEN]

    def get_closed_trades(self) -> List[TradeEntry]:
        """Get all closed trades."""
        return [t for t in self.trades if t.result != TradeResult.OPEN]

    def calculate_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> JournalStats:
        """Calculate comprehensive statistics."""
        # Filter trades
        trades = self.trades
        if start_date:
            trades = [t for t in trades if t.trade_date >= start_date]
        if end_date:
            trades = [t for t in trades if t.trade_date <= end_date]

        closed = [t for t in trades if t.result != TradeResult.OPEN]

        stats = JournalStats()
        stats.total_trades = len(trades)
        stats.open_trades = len([t for t in trades if t.result == TradeResult.OPEN])
        stats.closed_trades = len(closed)

        if not closed:
            return stats

        # Win/Loss analysis
        stats.wins = len([t for t in closed if t.result == TradeResult.WIN])
        stats.losses = len([t for t in closed if t.result == TradeResult.LOSS])
        stats.breakevens = len([t for t in closed if t.result == TradeResult.BREAKEVEN])
        stats.win_rate = (stats.wins / stats.closed_trades) * 100 if stats.closed_trades > 0 else 0

        # P&L analysis
        stats.total_pnl = sum(t.pnl for t in closed)

        winners = [t for t in closed if t.result == TradeResult.WIN]
        losers = [t for t in closed if t.result == TradeResult.LOSS]

        stats.avg_win = np.mean([t.pnl_pct for t in winners]) if winners else 0
        stats.avg_loss = np.mean([t.pnl_pct for t in losers]) if losers else 0

        gross_profit = sum(t.pnl for t in winners) if winners else 0
        gross_loss = abs(sum(t.pnl for t in losers)) if losers else 1
        stats.profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit

        # Expectancy
        stats.expectancy = (
            (stats.win_rate / 100) * stats.avg_win -
            ((100 - stats.win_rate) / 100) * abs(stats.avg_loss)
        )

        # Streaks
        stats.current_streak, stats.best_streak, stats.worst_streak = self._calculate_streaks(closed)

        # By category analysis
        stats.by_regime = self._analyze_by_category(closed, 'regime')
        stats.by_trade_type = self._analyze_by_category(closed, 'trade_type')
        stats.by_conviction = self._analyze_by_category(closed, 'conviction_level')
        stats.by_sector = self._analyze_by_category(closed, 'sector')

        # MAE/MFE
        stats.avg_mae = np.mean([t.mae for t in closed if t.mae > 0]) if closed else 0
        stats.avg_mfe = np.mean([t.mfe for t in closed if t.mfe > 0]) if closed else 0

        # Plan adherence
        stats.plan_adherence = (
            len([t for t in closed if t.followed_plan]) / len(closed) * 100
            if closed else 0
        )

        # Average hold time
        hold_times = []
        for t in closed:
            if t.exit_time and t.entry_time:
                hold_times.append((t.exit_time - t.entry_time).days)
        stats.avg_hold_time_days = np.mean(hold_times) if hold_times else 0

        return stats

    def _calculate_streaks(
        self,
        trades: List[TradeEntry]
    ) -> Tuple[int, int, int]:
        """Calculate win/loss streaks."""
        if not trades:
            return 0, 0, 0

        current_streak = 0
        best_win_streak = 0
        worst_loss_streak = 0
        temp_win = 0
        temp_loss = 0

        for trade in sorted(trades, key=lambda x: x.trade_date):
            if trade.result == TradeResult.WIN:
                temp_win += 1
                temp_loss = 0
                best_win_streak = max(best_win_streak, temp_win)
                current_streak = temp_win
            elif trade.result == TradeResult.LOSS:
                temp_loss += 1
                temp_win = 0
                worst_loss_streak = max(worst_loss_streak, temp_loss)
                current_streak = -temp_loss
            else:
                pass  # Breakeven doesn't break streak

        return current_streak, best_win_streak, worst_loss_streak

    def _analyze_by_category(
        self,
        trades: List[TradeEntry],
        category: str
    ) -> Dict[str, Dict]:
        """Analyze trades by a specific category."""
        results = {}

        # Group trades
        groups = {}
        for trade in trades:
            key = str(getattr(trade, category, 'UNKNOWN'))
            if hasattr(getattr(trade, category, None), 'value'):
                key = getattr(trade, category).value
            if key not in groups:
                groups[key] = []
            groups[key].append(trade)

        # Calculate stats for each group
        for key, group_trades in groups.items():
            wins = len([t for t in group_trades if t.result == TradeResult.WIN])
            total = len(group_trades)
            pnl = sum(t.pnl for t in group_trades)

            results[key] = {
                'trades': total,
                'wins': wins,
                'win_rate': (wins / total * 100) if total > 0 else 0,
                'total_pnl': pnl,
                'avg_pnl_pct': np.mean([t.pnl_pct for t in group_trades])
            }

        return results

    def get_common_mistakes(self) -> Dict[str, int]:
        """Get frequency of common mistakes."""
        mistakes = {}
        for trade in self.trades:
            for mistake in trade.mistakes:
                mistakes[mistake] = mistakes.get(mistake, 0) + 1

        return dict(sorted(mistakes.items(), key=lambda x: x[1], reverse=True))

    def get_key_lessons(self) -> List[str]:
        """Extract key lessons from profitable trades."""
        lessons = []
        for trade in self.trades:
            if trade.result == TradeResult.WIN and trade.lessons:
                lessons.extend(trade.lessons)
        return list(set(lessons))

    def get_summary(self) -> str:
        """Get human-readable journal summary."""
        stats = self.calculate_stats()

        lines = []
        lines.append("=" * 70)
        lines.append("TRADE JOURNAL SUMMARY")
        lines.append("=" * 70)

        lines.append(f"\n[OVERVIEW]")
        lines.append(f"  Total Trades: {stats.total_trades}")
        lines.append(f"  Open: {stats.open_trades} | Closed: {stats.closed_trades}")

        lines.append(f"\n[PERFORMANCE]")
        lines.append(f"  Win Rate: {stats.win_rate:.1f}%")
        lines.append(f"  Wins: {stats.wins} | Losses: {stats.losses} | BE: {stats.breakevens}")
        lines.append(f"  Total P&L: ₹{stats.total_pnl:,.2f}")
        lines.append(f"  Avg Win: {stats.avg_win:+.1f}% | Avg Loss: {stats.avg_loss:.1f}%")
        lines.append(f"  Profit Factor: {stats.profit_factor:.2f}")
        lines.append(f"  Expectancy: {stats.expectancy:.2f}%")

        lines.append(f"\n[STREAKS]")
        lines.append(f"  Current: {stats.current_streak:+d}")
        lines.append(f"  Best Win Streak: {stats.best_streak}")
        lines.append(f"  Worst Loss Streak: {stats.worst_streak}")

        lines.append(f"\n[BEHAVIOR]")
        lines.append(f"  Plan Adherence: {stats.plan_adherence:.0f}%")
        lines.append(f"  Avg Hold Time: {stats.avg_hold_time_days:.1f} days")

        if stats.by_regime:
            lines.append(f"\n[BY REGIME]")
            for regime, data in stats.by_regime.items():
                lines.append(f"  {regime}: {data['trades']} trades, {data['win_rate']:.0f}% WR, ₹{data['total_pnl']:,.0f}")

        if stats.by_conviction:
            lines.append(f"\n[BY CONVICTION]")
            for level, data in sorted(stats.by_conviction.items()):
                lines.append(f"  {level}: {data['trades']} trades, {data['win_rate']:.0f}% WR")

        # Common mistakes
        mistakes = self.get_common_mistakes()
        if mistakes:
            lines.append(f"\n[TOP MISTAKES]")
            for mistake, count in list(mistakes.items())[:5]:
                lines.append(f"  - {mistake}: {count}x")

        lines.append("=" * 70)
        return "\n".join(lines)

    def export_to_csv(self, filepath: str) -> None:
        """Export journal to CSV."""
        if not self.trades:
            console.print("[yellow]No trades to export[/yellow]")
            return

        df = pd.DataFrame([t.to_dict() for t in self.trades])
        df.to_csv(filepath, index=False)
        console.print(f"[green]Exported {len(self.trades)} trades to {filepath}[/green]")

    def weekly_review(self) -> str:
        """Generate weekly review."""
        week_ago = datetime.now() - timedelta(days=7)
        stats = self.calculate_stats(start_date=week_ago)

        lines = []
        lines.append("=" * 60)
        lines.append(f"WEEKLY REVIEW ({week_ago.strftime('%Y-%m-%d')} to today)")
        lines.append("=" * 60)

        lines.append(f"\nTrades: {stats.closed_trades}")
        lines.append(f"Win Rate: {stats.win_rate:.0f}%")
        lines.append(f"P&L: ₹{stats.total_pnl:,.2f}")
        lines.append(f"Expectancy: {stats.expectancy:.2f}%")

        if stats.closed_trades > 0:
            lines.append(f"\n[LESSONS THIS WEEK]")
            week_trades = [t for t in self.trades if t.trade_date >= week_ago]
            for trade in week_trades:
                if trade.lessons:
                    lines.append(f"  {trade.symbol}: {', '.join(trade.lessons)}")

        lines.append("=" * 60)
        return "\n".join(lines)


def create_trade_entry(
    symbol: str,
    entry_price: float,
    position_size: int,
    stop_loss: float,
    target: float,
    conviction: str = "B",
    trade_type: str = "SWING",
    regime: str = "NEUTRAL",
    entry_reason: str = ""
) -> TradeEntry:
    """Quick function to create a trade entry."""
    now = datetime.now()

    return TradeEntry(
        trade_id=f"{symbol}_{now.strftime('%Y%m%d_%H%M%S')}",
        symbol=symbol,
        trade_date=now,
        entry_price=entry_price,
        entry_time=now,
        position_size=position_size,
        position_value=entry_price * position_size,
        direction="LONG",
        planned_stop=stop_loss,
        planned_target1=target,
        planned_target2=target * 1.5,
        planned_rr=(target - entry_price) / (entry_price - stop_loss) if entry_price > stop_loss else 2.0,
        conviction_level=conviction,
        trade_type=TradeType[trade_type],
        regime=regime,
        entry_reason=entry_reason
    )
