"""Backtesting Engine - Simulate trades and measure performance."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np


class TradeStatus(Enum):
    """Trade status."""
    OPEN = "OPEN"
    CLOSED_TP1 = "CLOSED_TP1"
    CLOSED_TP2 = "CLOSED_TP2"
    CLOSED_SL = "CLOSED_SL"
    CLOSED_TIME = "CLOSED_TIME"
    CLOSED_TRAILING = "CLOSED_TRAILING"


@dataclass
class Trade:
    """Individual trade record."""
    symbol: str
    entry_date: datetime
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    position_size: int
    direction: str = "LONG"  # LONG or SHORT

    # Exit fields (filled when trade closes)
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    status: TradeStatus = TradeStatus.OPEN

    # Calculated fields
    pnl: float = 0.0
    pnl_percent: float = 0.0
    holding_days: int = 0
    max_favorable: float = 0.0  # Max favorable excursion
    max_adverse: float = 0.0    # Max adverse excursion (drawdown)

    def calculate_pnl(self, transaction_cost_bps: float = 5.0, slippage_bps: float = 5.0):
        """Calculate PnL when trade is closed, including transaction costs and slippage.

        Transaction costs cover: brokerage, STT, GST, stamp duty, SEBI turnover fee.
        Slippage models market impact on exit.
        """
        if self.exit_price is None:
            return

        # Apply slippage to exit price (adverse direction)
        if self.direction == "LONG":
            effective_exit = self.exit_price * (1 - slippage_bps / 10000)
        else:
            effective_exit = self.exit_price * (1 + slippage_bps / 10000)

        # Compute raw PnL
        if self.direction == "LONG":
            raw_pnl = (effective_exit - self.entry_price) * self.position_size
            self.pnl_percent = (effective_exit - self.entry_price) / self.entry_price * 100
        else:
            raw_pnl = (self.entry_price - effective_exit) * self.position_size
            self.pnl_percent = (self.entry_price - effective_exit) / self.entry_price * 100

        # Deduct transaction costs (both sides)
        entry_value = self.entry_price * self.position_size
        exit_value = effective_exit * self.position_size
        txn_cost = (entry_value + exit_value) * transaction_cost_bps / 10000
        self.pnl = raw_pnl - txn_cost

        if self.entry_date and self.exit_date:
            self.holding_days = (self.exit_date - self.entry_date).days


@dataclass
class BacktestResult:
    """Backtest results summary."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0

    profit_factor: float = 0.0  # Gross profit / Gross loss
    expectancy: float = 0.0     # Expected return per trade

    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    max_consecutive_losses: int = 0

    avg_holding_days: float = 0.0
    avg_rr_achieved: float = 0.0  # Average R:R actually achieved

    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

    # By exit type
    exits_by_type: Dict[str, int] = field(default_factory=dict)

    # Costs
    total_transaction_costs: float = 0.0
    total_slippage_cost: float = 0.0


class BacktestEngine:
    """
    Backtesting engine for signal validation.

    Supports:
    - ATR-based stops
    - Multiple targets (partial exits)
    - Trailing stops
    - Time-based exits
    - Position sizing based on risk
    - Transaction costs (brokerage + STT + GST + stamp + SEBI)
    - Slippage modeling
    """

    # Transaction costs per side (bps) — conservative estimate for Indian markets:
    # ~3-5 bps brokerage + ~1 bp STT + ~1 bp GST/stamp/SEBI ≈ 5 bps per side
    TRANSACTION_COST_BPS = 5.0  # per side
    # Slippage per side (bps) — conservative for liquid Nifty 500 stocks
    SLIPPAGE_BPS = 5.0  # per side

    def __init__(
        self,
        initial_capital: float = 500000,
        risk_per_trade: float = 0.01,
        max_holding_days: int = 20,
        use_trailing_stop: bool = True,
        trailing_activation: float = 1.0,  # Activate at 1R profit
        trailing_distance: float = 0.5,    # Trail by 0.5R
        partial_exit_pct: float = 0.5      # Exit 50% at T1
    ):
        """
        Initialize backtest engine.

        Args:
            initial_capital: Starting capital
            risk_per_trade: Risk per trade as fraction
            max_holding_days: Max days to hold a trade
            use_trailing_stop: Whether to use trailing stops
            trailing_activation: R multiple to activate trailing
            trailing_distance: R multiple for trailing distance
            partial_exit_pct: Percentage to exit at T1
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.max_holding_days = max_holding_days
        self.use_trailing_stop = use_trailing_stop
        self.trailing_activation = trailing_activation
        self.trailing_distance = trailing_distance
        self.partial_exit_pct = partial_exit_pct
        self.total_transaction_costs = 0.0

        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_capital]

    def run_backtest(
        self,
        signals: List[Dict],
        price_data: Dict[str, pd.DataFrame]
    ) -> BacktestResult:
        """
        Run backtest on historical signals.

        Args:
            signals: List of signal dictionaries with keys:
                     symbol, date, entry_price, stop_loss, target_1, target_2, direction
            price_data: Dict mapping symbol to OHLCV DataFrame

        Returns:
            BacktestResult with performance metrics
        """
        self.capital = self.initial_capital
        self.trades = []
        self.equity_curve = [self.initial_capital]

        for signal in signals:
            symbol = signal['symbol']
            entry_date = pd.to_datetime(signal['date'])

            if symbol not in price_data:
                continue

            df = price_data[symbol]

            # Find entry date in data
            if entry_date not in df.index:
                # Find next available date
                future_dates = df.index[df.index >= entry_date]
                if len(future_dates) == 0:
                    continue
                entry_date = future_dates[0]

            # Create trade — apply slippage to entry price
            raw_entry = signal.get('entry_price', df.loc[entry_date, 'close'])
            direction = signal.get('direction', 'LONG')
            # Slippage: buy at higher price, sell at lower price
            if direction == 'LONG':
                entry_price = raw_entry * (1 + self.SLIPPAGE_BPS / 10000)
            else:
                entry_price = raw_entry * (1 - self.SLIPPAGE_BPS / 10000)
            stop_loss = signal['stop_loss']
            risk_per_share = abs(entry_price - stop_loss)

            if risk_per_share == 0:
                continue

            # Calculate position size
            risk_amount = self.capital * self.risk_per_trade
            position_size = int(risk_amount / risk_per_share)

            if position_size <= 0:
                continue

            trade = Trade(
                symbol=symbol,
                entry_date=entry_date,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_1=signal['target_1'],
                target_2=signal['target_2'],
                position_size=position_size,
                direction=signal.get('direction', 'LONG')
            )

            # Simulate trade
            self._simulate_trade(trade, df)
            self.trades.append(trade)

            # Update capital and equity curve
            self.capital += trade.pnl
            self.equity_curve.append(self.capital)

        # Calculate results
        return self._calculate_results()

    def _simulate_trade(self, trade: Trade, df: pd.DataFrame):
        """Simulate a single trade through price data."""
        entry_idx = df.index.get_loc(trade.entry_date)

        # Get data after entry
        future_data = df.iloc[entry_idx + 1:]

        if len(future_data) == 0:
            trade.status = TradeStatus.OPEN
            return

        risk = abs(trade.entry_price - trade.stop_loss)
        trailing_stop = trade.stop_loss
        trailing_activated = False
        partial_exited = False
        remaining_size = trade.position_size
        total_pnl = 0.0

        for i, (date, row) in enumerate(future_data.iterrows()):
            high = row['high']
            low = row['low']
            close = row['close']

            # Track excursions
            if trade.direction == "LONG":
                favorable = (high - trade.entry_price) / trade.entry_price * 100
                adverse = (trade.entry_price - low) / trade.entry_price * 100
            else:
                favorable = (trade.entry_price - low) / trade.entry_price * 100
                adverse = (high - trade.entry_price) / trade.entry_price * 100

            trade.max_favorable = max(trade.max_favorable, favorable)
            trade.max_adverse = max(trade.max_adverse, adverse)

            # Check stop loss
            if trade.direction == "LONG":
                if low <= trailing_stop:
                    trade.exit_date = date
                    trade.exit_price = trailing_stop
                    trade.status = TradeStatus.CLOSED_TRAILING if trailing_activated else TradeStatus.CLOSED_SL
                    trade.calculate_pnl()
                    return
            else:
                if high >= trailing_stop:
                    trade.exit_date = date
                    trade.exit_price = trailing_stop
                    trade.status = TradeStatus.CLOSED_TRAILING if trailing_activated else TradeStatus.CLOSED_SL
                    trade.calculate_pnl()
                    return

            # Check T1 - partial exit
            if not partial_exited:
                if trade.direction == "LONG" and high >= trade.target_1:
                    partial_size = int(trade.position_size * self.partial_exit_pct)
                    partial_pnl = (trade.target_1 - trade.entry_price) * partial_size
                    total_pnl += partial_pnl
                    remaining_size -= partial_size
                    partial_exited = True

                    # Move stop to breakeven
                    trailing_stop = trade.entry_price

                elif trade.direction == "SHORT" and low <= trade.target_1:
                    partial_size = int(trade.position_size * self.partial_exit_pct)
                    partial_pnl = (trade.entry_price - trade.target_1) * partial_size
                    total_pnl += partial_pnl
                    remaining_size -= partial_size
                    partial_exited = True
                    trailing_stop = trade.entry_price

            # Check T2 - full exit
            if trade.direction == "LONG" and high >= trade.target_2:
                trade.exit_date = date
                trade.exit_price = trade.target_2
                trade.status = TradeStatus.CLOSED_TP2
                trade.pnl = total_pnl + (trade.target_2 - trade.entry_price) * remaining_size
                trade.pnl_percent = trade.pnl / (trade.entry_price * trade.position_size) * 100
                trade.holding_days = (date - trade.entry_date).days
                return

            elif trade.direction == "SHORT" and low <= trade.target_2:
                trade.exit_date = date
                trade.exit_price = trade.target_2
                trade.status = TradeStatus.CLOSED_TP2
                trade.pnl = total_pnl + (trade.entry_price - trade.target_2) * remaining_size
                trade.pnl_percent = trade.pnl / (trade.entry_price * trade.position_size) * 100
                trade.holding_days = (date - trade.entry_date).days
                return

            # Update trailing stop
            if self.use_trailing_stop and partial_exited:
                if trade.direction == "LONG":
                    current_profit_r = (high - trade.entry_price) / risk
                    if current_profit_r >= self.trailing_activation:
                        trailing_activated = True
                        new_stop = high - (risk * self.trailing_distance)
                        trailing_stop = max(trailing_stop, new_stop)
                else:
                    current_profit_r = (trade.entry_price - low) / risk
                    if current_profit_r >= self.trailing_activation:
                        trailing_activated = True
                        new_stop = low + (risk * self.trailing_distance)
                        trailing_stop = min(trailing_stop, new_stop)

            # Check max holding days
            holding_days = (date - trade.entry_date).days
            if holding_days >= self.max_holding_days:
                trade.exit_date = date
                trade.exit_price = close
                trade.status = TradeStatus.CLOSED_TIME
                trade.pnl = total_pnl + (close - trade.entry_price) * remaining_size if trade.direction == "LONG" \
                           else total_pnl + (trade.entry_price - close) * remaining_size
                trade.pnl_percent = trade.pnl / (trade.entry_price * trade.position_size) * 100
                trade.holding_days = holding_days
                return

        # If we reach here, trade is still open (end of data)
        last_date = future_data.index[-1]
        last_close = future_data.iloc[-1]['close']
        trade.exit_date = last_date
        trade.exit_price = last_close
        trade.status = TradeStatus.CLOSED_TIME
        trade.pnl = total_pnl + (last_close - trade.entry_price) * remaining_size if trade.direction == "LONG" \
                   else total_pnl + (trade.entry_price - last_close) * remaining_size
        trade.pnl_percent = trade.pnl / (trade.entry_price * trade.position_size) * 100
        trade.holding_days = (last_date - trade.entry_date).days

    def _calculate_results(self) -> BacktestResult:
        """Calculate backtest performance metrics."""
        result = BacktestResult()
        result.trades = self.trades
        result.equity_curve = self.equity_curve

        if not self.trades:
            return result

        # Basic counts
        result.total_trades = len(self.trades)
        winners = [t for t in self.trades if t.pnl > 0]
        losers = [t for t in self.trades if t.pnl < 0]

        result.winning_trades = len(winners)
        result.losing_trades = len(losers)
        result.win_rate = len(winners) / len(self.trades) * 100 if self.trades else 0

        # PnL metrics
        result.total_pnl = sum(t.pnl for t in self.trades)
        result.total_pnl_percent = (self.capital - self.initial_capital) / self.initial_capital * 100

        if winners:
            result.avg_win = sum(t.pnl for t in winners) / len(winners)
            result.largest_win = max(t.pnl for t in winners)

        if losers:
            result.avg_loss = sum(t.pnl for t in losers) / len(losers)
            result.largest_loss = min(t.pnl for t in losers)

        # Profit factor
        gross_profit = sum(t.pnl for t in winners) if winners else 0
        gross_loss = abs(sum(t.pnl for t in losers)) if losers else 1
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Expectancy
        if self.trades:
            result.expectancy = result.total_pnl / len(self.trades)

        # Drawdown
        equity = np.array(self.equity_curve)
        peak = np.maximum.accumulate(equity)
        drawdown = peak - equity
        result.max_drawdown = np.max(drawdown)
        result.max_drawdown_percent = (result.max_drawdown / np.max(peak)) * 100 if np.max(peak) > 0 else 0

        # Consecutive losses
        current_streak = 0
        max_streak = 0
        for trade in self.trades:
            if trade.pnl < 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        result.max_consecutive_losses = max_streak

        # Average holding
        result.avg_holding_days = sum(t.holding_days for t in self.trades) / len(self.trades)

        # Average R:R achieved
        rr_achieved = []
        for t in self.trades:
            risk = abs(t.entry_price - t.stop_loss)
            if risk > 0:
                rr = t.pnl_percent / (risk / t.entry_price * 100)
                rr_achieved.append(rr)
        result.avg_rr_achieved = sum(rr_achieved) / len(rr_achieved) if rr_achieved else 0

        # Exits by type
        for t in self.trades:
            status_name = t.status.value
            result.exits_by_type[status_name] = result.exits_by_type.get(status_name, 0) + 1

        return result


def generate_report(result: BacktestResult) -> str:
    """Generate human-readable backtest report."""
    report = []
    report.append("=" * 60)
    report.append("BACKTEST RESULTS")
    report.append("=" * 60)
    report.append("")

    report.append("TRADE SUMMARY")
    report.append("-" * 40)
    report.append(f"Total Trades:       {result.total_trades}")
    report.append(f"Winning Trades:     {result.winning_trades}")
    report.append(f"Losing Trades:      {result.losing_trades}")
    report.append(f"Win Rate:           {result.win_rate:.1f}%")
    report.append("")

    report.append("PROFITABILITY")
    report.append("-" * 40)
    report.append(f"Total PnL:          Rs {result.total_pnl:,.0f}")
    report.append(f"Return:             {result.total_pnl_percent:.2f}%")
    report.append(f"Avg Win:            Rs {result.avg_win:,.0f}")
    report.append(f"Avg Loss:           Rs {result.avg_loss:,.0f}")
    report.append(f"Largest Win:        Rs {result.largest_win:,.0f}")
    report.append(f"Largest Loss:       Rs {result.largest_loss:,.0f}")
    report.append(f"Profit Factor:      {result.profit_factor:.2f}")
    report.append(f"Expectancy/Trade:   Rs {result.expectancy:,.0f}")
    report.append("")

    report.append("RISK METRICS")
    report.append("-" * 40)
    report.append(f"Max Drawdown:       Rs {result.max_drawdown:,.0f} ({result.max_drawdown_percent:.1f}%)")
    report.append(f"Max Consec. Losses: {result.max_consecutive_losses}")
    report.append(f"Avg R:R Achieved:   {result.avg_rr_achieved:.2f}")
    report.append("")

    report.append("TRADE CHARACTERISTICS")
    report.append("-" * 40)
    report.append(f"Avg Holding Days:   {result.avg_holding_days:.1f}")
    report.append("")

    report.append("EXIT BREAKDOWN")
    report.append("-" * 40)
    for exit_type, count in result.exits_by_type.items():
        pct = count / result.total_trades * 100 if result.total_trades > 0 else 0
        report.append(f"{exit_type:20s} {count:4d} ({pct:.1f}%)")

    report.append("")
    report.append("=" * 60)

    return "\n".join(report)
