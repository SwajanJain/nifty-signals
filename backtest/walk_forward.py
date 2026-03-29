"""
Walk-Forward Backtester - Proper out-of-sample validation.

Critical insights:
- Traditional backtest = curve fitting = failure in live trading
- Walk-forward prevents overfitting by design
- Out-of-sample performance is the ONLY truth
- Parameter stability across windows = robust strategy
- If it doesn't work walk-forward, it won't work live

Rule: Trust walk-forward results, distrust traditional backtests.

WARNING: Survivorship bias — backtests use current index constituents,
not historical. Stocks that were delisted or removed from the index are
excluded, which may overstate historical returns.
"""

from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()


class WindowType(Enum):
    """Walk-forward window type."""
    ANCHORED = "ANCHORED"  # Growing in-sample window
    ROLLING = "ROLLING"  # Fixed size rolling window


@dataclass
class WalkForwardWindow:
    """Single walk-forward window."""
    window_id: int
    in_sample_start: datetime
    in_sample_end: datetime
    out_sample_start: datetime
    out_sample_end: datetime

    # Results
    in_sample_return: float = 0.0
    out_sample_return: float = 0.0
    in_sample_sharpe: float = 0.0
    out_sample_sharpe: float = 0.0
    in_sample_trades: int = 0
    out_sample_trades: int = 0
    in_sample_win_rate: float = 0.0
    out_sample_win_rate: float = 0.0

    # Best parameters found in-sample
    best_params: Dict = field(default_factory=dict)

    # Efficiency ratio (out/in performance)
    efficiency_ratio: float = 0.0


@dataclass
class WalkForwardResult:
    """Complete walk-forward backtest result."""
    strategy_name: str
    total_windows: int
    window_type: WindowType

    # Aggregate metrics
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int

    # Stability metrics
    avg_efficiency_ratio: float  # Out-sample / In-sample
    param_stability: float  # How stable are optimal params
    degradation_pct: float  # Performance drop out-of-sample

    # Per-window results
    windows: List[WalkForwardWindow]

    # Robustness assessment
    is_robust: bool
    robustness_score: int  # 0-100
    warnings: List[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = []
        lines.append("=" * 70)
        lines.append(f"WALK-FORWARD BACKTEST: {self.strategy_name}")
        lines.append("=" * 70)

        lines.append(f"\n[AGGREGATE PERFORMANCE]")
        lines.append(f"  Total Return: {self.total_return:.1f}%")
        lines.append(f"  Annualized: {self.annualized_return:.1f}%")
        lines.append(f"  Sharpe Ratio: {self.sharpe_ratio:.2f}")
        lines.append(f"  Max Drawdown: {self.max_drawdown:.1f}%")
        lines.append(f"  Win Rate: {self.win_rate:.1f}%")
        lines.append(f"  Profit Factor: {self.profit_factor:.2f}")
        lines.append(f"  Total Trades: {self.total_trades}")

        lines.append(f"\n[ROBUSTNESS METRICS]")
        lines.append(f"  Efficiency Ratio: {self.avg_efficiency_ratio:.2f}")
        lines.append(f"  Param Stability: {self.param_stability:.1f}%")
        lines.append(f"  OOS Degradation: {self.degradation_pct:.1f}%")
        lines.append(f"  Robustness Score: {self.robustness_score}/100")
        lines.append(f"  Is Robust: {'YES ✓' if self.is_robust else 'NO ✗'}")

        if self.warnings:
            lines.append(f"\n[WARNINGS]")
            for w in self.warnings:
                lines.append(f"  ⚠️ {w}")

        lines.append(f"\n[PER-WINDOW RESULTS]")
        lines.append("-" * 70)
        lines.append(f"{'Window':<8} {'IS Return':<12} {'OOS Return':<12} {'Efficiency':<12} {'Trades':<8}")
        lines.append("-" * 70)

        for w in self.windows:
            lines.append(
                f"{w.window_id:<8} "
                f"{w.in_sample_return:>+10.1f}% "
                f"{w.out_sample_return:>+10.1f}% "
                f"{w.efficiency_ratio:>10.2f} "
                f"{w.out_sample_trades:>6}"
            )

        lines.append("=" * 70)
        return "\n".join(lines)


class WalkForwardBacktester:
    """
    Walk-Forward Backtester with proper out-of-sample validation.

    Process:
    1. Split data into multiple windows
    2. For each window:
       a. Optimize on in-sample (IS) period
       b. Test on out-of-sample (OOS) period
       c. Record both IS and OOS performance
    3. Aggregate OOS performance = true expected performance
    4. Check efficiency ratio (OOS/IS) for robustness

    A robust strategy has:
    - Efficiency ratio > 0.5 (OOS at least 50% of IS)
    - Consistent parameters across windows
    - Positive OOS in most windows
    """

    # Minimum thresholds for robustness
    MIN_EFFICIENCY_RATIO = 0.4  # OOS should be 40%+ of IS
    MIN_PARAM_STABILITY = 60  # Parameters should be 60%+ stable
    MAX_DEGRADATION = 50  # Max 50% degradation IS to OOS
    MIN_POSITIVE_WINDOWS = 0.6  # 60%+ windows should be profitable

    def __init__(
        self,
        window_type: WindowType = WindowType.ROLLING,
        in_sample_months: int = 12,
        out_sample_months: int = 3,
        step_months: int = 3
    ):
        self.window_type = window_type
        self.in_sample_months = in_sample_months
        self.out_sample_months = out_sample_months
        self.step_months = step_months

    def create_windows(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[WalkForwardWindow]:
        """Create walk-forward windows."""
        windows = []
        window_id = 1

        current_start = start_date

        while True:
            # In-sample period
            if self.window_type == WindowType.ANCHORED:
                is_start = start_date  # Always from beginning
            else:
                is_start = current_start

            is_end = is_start + timedelta(days=self.in_sample_months * 30)

            # Out-of-sample period
            oos_start = is_end + timedelta(days=1)
            oos_end = oos_start + timedelta(days=self.out_sample_months * 30)

            # Check if we've exceeded end date
            if oos_end > end_date:
                break

            windows.append(WalkForwardWindow(
                window_id=window_id,
                in_sample_start=is_start,
                in_sample_end=is_end,
                out_sample_start=oos_start,
                out_sample_end=oos_end
            ))

            window_id += 1
            current_start += timedelta(days=self.step_months * 30)

        return windows

    def run_backtest(
        self,
        strategy_name: str,
        data: pd.DataFrame,
        signal_func: Callable,
        param_grid: Dict[str, List],
        initial_capital: float = 1000000
    ) -> WalkForwardResult:
        """
        Run walk-forward backtest.

        Args:
            strategy_name: Name of strategy
            data: DataFrame with OHLCV data (must have 'date' column)
            signal_func: Function(data, **params) -> signals DataFrame
            param_grid: Dict of parameter names to lists of values to test
            initial_capital: Starting capital

        Returns:
            WalkForwardResult with complete analysis
        """
        # Ensure data is sorted by date
        data = data.sort_values('date').reset_index(drop=True)

        start_date = data['date'].min()
        end_date = data['date'].max()

        # Create windows
        windows = self.create_windows(start_date, end_date)

        if len(windows) < 3:
            console.print("[yellow]Warning: Less than 3 windows - results may not be reliable[/yellow]")

        # Run each window
        all_oos_returns = []
        all_best_params = []

        for window in windows:
            # Get in-sample and out-of-sample data
            is_data = data[
                (data['date'] >= window.in_sample_start) &
                (data['date'] <= window.in_sample_end)
            ].copy()

            oos_data = data[
                (data['date'] >= window.out_sample_start) &
                (data['date'] <= window.out_sample_end)
            ].copy()

            # Optimize on in-sample
            best_params, is_metrics = self._optimize_params(
                is_data, signal_func, param_grid, initial_capital
            )

            # Test on out-of-sample with best params
            oos_metrics = self._evaluate_params(
                oos_data, signal_func, best_params, initial_capital
            )

            # Record results
            window.best_params = best_params
            window.in_sample_return = is_metrics['total_return']
            window.out_sample_return = oos_metrics['total_return']
            window.in_sample_sharpe = is_metrics['sharpe_ratio']
            window.out_sample_sharpe = oos_metrics['sharpe_ratio']
            window.in_sample_trades = is_metrics['num_trades']
            window.out_sample_trades = oos_metrics['num_trades']
            window.in_sample_win_rate = is_metrics['win_rate']
            window.out_sample_win_rate = oos_metrics['win_rate']

            # Calculate efficiency ratio
            if abs(is_metrics['total_return']) > 0.01:
                window.efficiency_ratio = oos_metrics['total_return'] / is_metrics['total_return']
            else:
                window.efficiency_ratio = 1.0 if oos_metrics['total_return'] >= 0 else 0.0

            all_oos_returns.append(oos_metrics['total_return'])
            all_best_params.append(best_params)

        # Aggregate results
        result = self._aggregate_results(strategy_name, windows, all_best_params)

        return result

    def _optimize_params(
        self,
        data: pd.DataFrame,
        signal_func: Callable,
        param_grid: Dict[str, List],
        initial_capital: float
    ) -> Tuple[Dict, Dict]:
        """
        Optimize parameters on in-sample data.

        Returns best parameters and their metrics.
        """
        best_sharpe = -np.inf
        best_params = {}
        best_metrics = {}

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        # Simple grid search
        from itertools import product
        for combo in product(*param_values):
            params = dict(zip(param_names, combo))

            metrics = self._evaluate_params(data, signal_func, params, initial_capital)

            # Optimize for Sharpe ratio
            if metrics['sharpe_ratio'] > best_sharpe:
                best_sharpe = metrics['sharpe_ratio']
                best_params = params.copy()
                best_metrics = metrics.copy()

        return best_params, best_metrics

    def _evaluate_params(
        self,
        data: pd.DataFrame,
        signal_func: Callable,
        params: Dict,
        initial_capital: float
    ) -> Dict:
        """
        Evaluate a parameter set on data.

        Returns performance metrics.
        """
        try:
            # Generate signals
            signals = signal_func(data, **params)

            if signals.empty or 'signal' not in signals.columns:
                return self._empty_metrics()

            # Simulate trades
            trades = self._simulate_trades(data, signals, initial_capital)

            # Calculate metrics
            return self._calculate_metrics(trades, initial_capital, len(data))

        except Exception as e:
            console.print(f"[yellow]Evaluation error: {e}[/yellow]")
            return self._empty_metrics()

    def _simulate_trades(
        self,
        data: pd.DataFrame,
        signals: pd.DataFrame,
        initial_capital: float
    ) -> List[Dict]:
        """Simulate trades from signals with 1-bar entry delay to avoid look-ahead bias."""
        trades = []
        position = None
        capital = initial_capital
        pending_entry = False
        pending_exit = False

        # Merge signals with data
        merged = data.merge(signals[['date', 'signal']], on='date', how='left')
        merged['signal'] = merged['signal'].fillna(0)

        for idx, row in merged.iterrows():
            # Signal on bar N -> entry on bar N+1 open (no look-ahead bias)
            # Execute pending entry from previous bar's signal
            if pending_entry and position is None:
                entry_price = row['open'] if 'open' in row.index else row['close']
                position = {
                    'entry_date': row['date'],
                    'entry_price': entry_price,
                    'direction': 'LONG',
                    'size': capital * 0.1 / entry_price  # 10% position
                }
                pending_entry = False

            # Execute pending exit from previous bar's signal
            if pending_exit and position is not None:
                exit_price = row['open'] if 'open' in row.index else row['close']
                pnl = (exit_price - position['entry_price']) * position['size']
                pnl_pct = (exit_price - position['entry_price']) / position['entry_price'] * 100

                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': row['date'],
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'direction': position['direction']
                })

                capital += pnl
                position = None
                pending_exit = False

            # Record signals — execution deferred to next bar
            if position is None and not pending_entry:
                if row['signal'] > 0:  # Buy signal
                    pending_entry = True
            elif position is not None and not pending_exit:
                if row['signal'] < 0:  # Sell signal
                    pending_exit = True

        return trades

    def _calculate_metrics(
        self,
        trades: List[Dict],
        initial_capital: float,
        num_days: int
    ) -> Dict:
        """Calculate performance metrics from trades."""
        if not trades:
            return self._empty_metrics()

        # Basic metrics
        total_pnl = sum(t['pnl'] for t in trades)
        total_return = (total_pnl / initial_capital) * 100

        winners = [t for t in trades if t['pnl'] > 0]
        losers = [t for t in trades if t['pnl'] < 0]

        win_rate = len(winners) / len(trades) * 100 if trades else 0

        # Profit factor
        gross_profit = sum(t['pnl'] for t in winners) if winners else 0
        gross_loss = abs(sum(t['pnl'] for t in losers)) if losers else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Sharpe ratio (simplified)
        returns = [t['pnl_pct'] for t in trades]
        if len(returns) > 1:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (avg_return / std_return) * np.sqrt(252 / max(num_days, 1)) if std_return > 0 else 0
        else:
            sharpe = 0

        # Max drawdown
        equity_curve = [initial_capital]
        for t in trades:
            equity_curve.append(equity_curve[-1] + t['pnl'])

        peak = equity_curve[0]
        max_dd = 0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_dd,
            'num_trades': len(trades),
            'avg_win': np.mean([t['pnl_pct'] for t in winners]) if winners else 0,
            'avg_loss': np.mean([t['pnl_pct'] for t in losers]) if losers else 0,
        }

    def _empty_metrics(self) -> Dict:
        """Return empty metrics."""
        return {
            'total_return': 0,
            'sharpe_ratio': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'num_trades': 0,
            'avg_win': 0,
            'avg_loss': 0,
        }

    def _aggregate_results(
        self,
        strategy_name: str,
        windows: List[WalkForwardWindow],
        all_best_params: List[Dict]
    ) -> WalkForwardResult:
        """Aggregate results from all windows."""
        # Calculate aggregate metrics
        total_return = sum(w.out_sample_return for w in windows)
        num_years = len(windows) * self.out_sample_months / 12
        annualized_return = total_return / num_years if num_years > 0 else 0

        avg_sharpe = np.mean([w.out_sample_sharpe for w in windows])
        avg_win_rate = np.mean([w.out_sample_win_rate for w in windows])
        total_trades = sum(w.out_sample_trades for w in windows)

        # Calculate profit factor from windows
        total_is_return = sum(w.in_sample_return for w in windows)
        winners = [w.out_sample_return for w in windows if w.out_sample_return > 0]
        losers = [abs(w.out_sample_return) for w in windows if w.out_sample_return < 0]
        profit_factor = sum(winners) / sum(losers) if losers else (sum(winners) if winners else 0)

        # Efficiency ratio
        avg_efficiency = np.mean([w.efficiency_ratio for w in windows if w.efficiency_ratio > 0])

        # Parameter stability (what % of params are consistent)
        param_stability = self._calculate_param_stability(all_best_params)

        # Degradation (IS to OOS)
        if total_is_return > 0:
            degradation = ((total_is_return - total_return) / total_is_return) * 100
        else:
            degradation = 0

        # Robustness checks
        warnings = []
        positive_windows = len([w for w in windows if w.out_sample_return > 0])
        positive_pct = positive_windows / len(windows) if windows else 0

        if avg_efficiency < self.MIN_EFFICIENCY_RATIO:
            warnings.append(f"Low efficiency ratio: {avg_efficiency:.2f} (min: {self.MIN_EFFICIENCY_RATIO})")

        if param_stability < self.MIN_PARAM_STABILITY:
            warnings.append(f"Unstable parameters: {param_stability:.0f}% (min: {self.MIN_PARAM_STABILITY}%)")

        if degradation > self.MAX_DEGRADATION:
            warnings.append(f"High degradation: {degradation:.0f}% (max: {self.MAX_DEGRADATION}%)")

        if positive_pct < self.MIN_POSITIVE_WINDOWS:
            warnings.append(f"Only {positive_pct*100:.0f}% profitable windows (min: {self.MIN_POSITIVE_WINDOWS*100}%)")

        # Calculate robustness score
        robustness_score = self._calculate_robustness_score(
            avg_efficiency, param_stability, degradation, positive_pct, avg_sharpe
        )

        is_robust = (
            avg_efficiency >= self.MIN_EFFICIENCY_RATIO and
            param_stability >= self.MIN_PARAM_STABILITY and
            degradation <= self.MAX_DEGRADATION and
            positive_pct >= self.MIN_POSITIVE_WINDOWS
        )

        # Calculate max drawdown across all OOS periods
        oos_returns = [w.out_sample_return for w in windows]
        cumulative = np.cumsum(oos_returns)
        peak = np.maximum.accumulate(cumulative)
        drawdowns = (peak - cumulative)
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0

        return WalkForwardResult(
            strategy_name=strategy_name,
            total_windows=len(windows),
            window_type=self.window_type,
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=avg_sharpe,
            max_drawdown=max_drawdown,
            win_rate=avg_win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            avg_efficiency_ratio=avg_efficiency,
            param_stability=param_stability,
            degradation_pct=degradation,
            windows=windows,
            is_robust=is_robust,
            robustness_score=robustness_score,
            warnings=warnings
        )

    def _calculate_param_stability(self, all_params: List[Dict]) -> float:
        """Calculate how stable parameters are across windows."""
        if not all_params or len(all_params) < 2:
            return 100

        # For each parameter, check how often it's the same across windows
        param_names = all_params[0].keys()
        stability_scores = []

        for param in param_names:
            values = [p.get(param) for p in all_params]
            # Count most common value
            from collections import Counter
            counts = Counter(values)
            most_common_count = counts.most_common(1)[0][1]
            stability = most_common_count / len(values) * 100
            stability_scores.append(stability)

        return np.mean(stability_scores)

    def _calculate_robustness_score(
        self,
        efficiency: float,
        param_stability: float,
        degradation: float,
        positive_pct: float,
        sharpe: float
    ) -> int:
        """Calculate overall robustness score 0-100."""
        score = 0

        # Efficiency (0-25 points)
        if efficiency >= 0.8:
            score += 25
        elif efficiency >= 0.6:
            score += 20
        elif efficiency >= 0.4:
            score += 15
        elif efficiency >= 0.2:
            score += 10

        # Parameter stability (0-25 points)
        score += min(25, param_stability * 0.25)

        # Degradation (0-25 points) - lower is better
        if degradation <= 10:
            score += 25
        elif degradation <= 25:
            score += 20
        elif degradation <= 40:
            score += 15
        elif degradation <= 50:
            score += 10

        # Positive windows (0-15 points)
        score += min(15, positive_pct * 15)

        # Sharpe bonus (0-10 points)
        if sharpe >= 2.0:
            score += 10
        elif sharpe >= 1.5:
            score += 8
        elif sharpe >= 1.0:
            score += 5
        elif sharpe >= 0.5:
            score += 3

        return int(min(100, score))


def quick_walk_forward_test(
    data: pd.DataFrame,
    signal_func: Callable,
    param_grid: Dict[str, List],
    strategy_name: str = "Strategy"
) -> WalkForwardResult:
    """Quick function to run walk-forward backtest."""
    backtester = WalkForwardBacktester(
        window_type=WindowType.ROLLING,
        in_sample_months=12,
        out_sample_months=3,
        step_months=3
    )

    return backtester.run_backtest(
        strategy_name=strategy_name,
        data=data,
        signal_func=signal_func,
        param_grid=param_grid
    )
