"""Performance metrics and analysis for backtesting."""

from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime


@dataclass
class PerformanceMetrics:
    """Extended performance metrics."""

    # Risk-adjusted returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Monthly/Yearly breakdown
    monthly_returns: Dict[str, float] = None
    yearly_returns: Dict[str, float] = None

    # Best/Worst periods
    best_month: float = 0.0
    worst_month: float = 0.0
    best_trade_month: str = ""
    worst_trade_month: str = ""

    # Time analysis
    avg_time_in_market: float = 0.0  # Percentage of time with open position
    trades_per_month: float = 0.0

    # Symbol analysis
    best_symbol: str = ""
    worst_symbol: str = ""
    symbol_breakdown: Dict[str, Dict] = None


def calculate_advanced_metrics(
    trades: List,
    equity_curve: List[float],
    initial_capital: float,
    risk_free_rate: float = 0.05  # 5% annual risk-free rate for India
) -> PerformanceMetrics:
    """
    Calculate advanced performance metrics.

    Args:
        trades: List of Trade objects
        equity_curve: List of equity values
        initial_capital: Starting capital
        risk_free_rate: Risk-free rate for Sharpe calculation

    Returns:
        PerformanceMetrics object
    """
    metrics = PerformanceMetrics()

    if not trades or len(equity_curve) < 2:
        return metrics

    # Calculate returns
    equity = np.array(equity_curve)
    returns = np.diff(equity) / equity[:-1]

    # Sharpe Ratio (annualized assuming 252 trading days)
    if len(returns) > 0 and np.std(returns) > 0:
        avg_return = np.mean(returns) * 252  # Annualized
        std_return = np.std(returns) * np.sqrt(252)  # Annualized
        metrics.sharpe_ratio = (avg_return - risk_free_rate) / std_return

    # Sortino Ratio (using downside deviation)
    negative_returns = returns[returns < 0]
    if len(negative_returns) > 0:
        downside_std = np.std(negative_returns) * np.sqrt(252)
        avg_return = np.mean(returns) * 252
        if downside_std > 0:
            metrics.sortino_ratio = (avg_return - risk_free_rate) / downside_std

    # Calmar Ratio (return / max drawdown)
    peak = np.maximum.accumulate(equity)
    drawdown = (peak - equity) / peak
    max_dd = np.max(drawdown)
    total_return = (equity[-1] - initial_capital) / initial_capital

    if max_dd > 0:
        # Annualize the return if we have date info
        metrics.calmar_ratio = total_return / max_dd

    # Monthly returns
    monthly_pnl = {}
    for trade in trades:
        if trade.exit_date:
            month_key = trade.exit_date.strftime("%Y-%m")
            monthly_pnl[month_key] = monthly_pnl.get(month_key, 0) + trade.pnl

    if monthly_pnl:
        metrics.monthly_returns = monthly_pnl
        metrics.best_month = max(monthly_pnl.values())
        metrics.worst_month = min(monthly_pnl.values())

        best_month_key = max(monthly_pnl, key=monthly_pnl.get)
        worst_month_key = min(monthly_pnl, key=monthly_pnl.get)
        metrics.best_trade_month = best_month_key
        metrics.worst_trade_month = worst_month_key

    # Yearly returns
    yearly_pnl = {}
    for trade in trades:
        if trade.exit_date:
            year_key = str(trade.exit_date.year)
            yearly_pnl[year_key] = yearly_pnl.get(year_key, 0) + trade.pnl

    if yearly_pnl:
        metrics.yearly_returns = yearly_pnl

    # Symbol breakdown
    symbol_stats = {}
    for trade in trades:
        symbol = trade.symbol
        if symbol not in symbol_stats:
            symbol_stats[symbol] = {
                'trades': 0,
                'wins': 0,
                'pnl': 0,
                'avg_pnl': 0
            }

        symbol_stats[symbol]['trades'] += 1
        symbol_stats[symbol]['pnl'] += trade.pnl
        if trade.pnl > 0:
            symbol_stats[symbol]['wins'] += 1

    for symbol in symbol_stats:
        stats = symbol_stats[symbol]
        stats['win_rate'] = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
        stats['avg_pnl'] = stats['pnl'] / stats['trades'] if stats['trades'] > 0 else 0

    metrics.symbol_breakdown = symbol_stats

    if symbol_stats:
        metrics.best_symbol = max(symbol_stats, key=lambda x: symbol_stats[x]['pnl'])
        metrics.worst_symbol = min(symbol_stats, key=lambda x: symbol_stats[x]['pnl'])

    # Trades per month
    if trades:
        first_trade = min(t.entry_date for t in trades)
        last_trade = max(t.exit_date or t.entry_date for t in trades)
        months = (last_trade - first_trade).days / 30
        if months > 0:
            metrics.trades_per_month = len(trades) / months

    return metrics


def calculate_rolling_metrics(
    equity_curve: List[float],
    window: int = 20
) -> Dict:
    """
    Calculate rolling performance metrics.

    Args:
        equity_curve: List of equity values
        window: Rolling window size

    Returns:
        Dict with rolling metrics
    """
    if len(equity_curve) < window:
        return {}

    equity = np.array(equity_curve)
    returns = np.diff(equity) / equity[:-1]

    rolling_returns = pd.Series(returns).rolling(window).mean().tolist()
    rolling_volatility = pd.Series(returns).rolling(window).std().tolist()

    # Rolling Sharpe (simplified)
    rolling_sharpe = []
    for i in range(len(returns)):
        if i >= window - 1:
            window_returns = returns[i - window + 1:i + 1]
            if np.std(window_returns) > 0:
                sharpe = np.mean(window_returns) / np.std(window_returns) * np.sqrt(252)
                rolling_sharpe.append(sharpe)
            else:
                rolling_sharpe.append(0)
        else:
            rolling_sharpe.append(None)

    return {
        'rolling_returns': rolling_returns,
        'rolling_volatility': rolling_volatility,
        'rolling_sharpe': rolling_sharpe
    }


def compare_to_benchmark(
    equity_curve: List[float],
    benchmark_data: pd.DataFrame,
    start_date: datetime,
    end_date: datetime
) -> Dict:
    """
    Compare strategy performance to benchmark (Nifty 50).

    Args:
        equity_curve: Strategy equity curve
        benchmark_data: Benchmark OHLCV data
        start_date: Start date
        end_date: End date

    Returns:
        Dict with comparison metrics
    """
    # Filter benchmark to date range
    mask = (benchmark_data.index >= start_date) & (benchmark_data.index <= end_date)
    benchmark = benchmark_data.loc[mask]

    if len(benchmark) == 0:
        return {}

    # Calculate benchmark return
    benchmark_return = (benchmark['close'].iloc[-1] - benchmark['close'].iloc[0]) / benchmark['close'].iloc[0] * 100

    # Strategy return
    initial = equity_curve[0]
    final = equity_curve[-1]
    strategy_return = (final - initial) / initial * 100

    # Alpha (excess return)
    alpha = strategy_return - benchmark_return

    # Correlation
    if len(equity_curve) > 1 and len(benchmark) > 1:
        # Resample to match lengths
        equity_returns = np.diff(equity_curve) / equity_curve[:-1]
        benchmark_returns = benchmark['close'].pct_change().dropna().values

        min_len = min(len(equity_returns), len(benchmark_returns))
        if min_len > 0:
            correlation = np.corrcoef(
                equity_returns[:min_len],
                benchmark_returns[:min_len]
            )[0, 1]
        else:
            correlation = 0
    else:
        correlation = 0

    return {
        'strategy_return': strategy_return,
        'benchmark_return': benchmark_return,
        'alpha': alpha,
        'correlation': correlation,
        'outperformed': strategy_return > benchmark_return
    }


def generate_detailed_report(
    result,  # BacktestResult
    metrics: PerformanceMetrics
) -> str:
    """Generate detailed performance report."""
    report = []

    report.append("\n" + "=" * 60)
    report.append("ADVANCED PERFORMANCE METRICS")
    report.append("=" * 60)

    report.append("\nRISK-ADJUSTED RETURNS")
    report.append("-" * 40)
    report.append(f"Sharpe Ratio:       {metrics.sharpe_ratio:.2f}")
    report.append(f"Sortino Ratio:      {metrics.sortino_ratio:.2f}")
    report.append(f"Calmar Ratio:       {metrics.calmar_ratio:.2f}")

    if metrics.monthly_returns:
        report.append("\nMONTHLY PERFORMANCE")
        report.append("-" * 40)
        report.append(f"Best Month:         Rs {metrics.best_month:,.0f} ({metrics.best_trade_month})")
        report.append(f"Worst Month:        Rs {metrics.worst_month:,.0f} ({metrics.worst_trade_month})")
        report.append(f"Trades/Month:       {metrics.trades_per_month:.1f}")

    if metrics.yearly_returns:
        report.append("\nYEARLY RETURNS")
        report.append("-" * 40)
        for year, pnl in sorted(metrics.yearly_returns.items()):
            report.append(f"{year}: Rs {pnl:,.0f}")

    if metrics.symbol_breakdown:
        report.append("\nTOP PERFORMING SYMBOLS")
        report.append("-" * 40)

        sorted_symbols = sorted(
            metrics.symbol_breakdown.items(),
            key=lambda x: x[1]['pnl'],
            reverse=True
        )

        for symbol, stats in sorted_symbols[:5]:
            report.append(
                f"{symbol:12s} Trades: {stats['trades']:3d} | "
                f"Win: {stats['win_rate']:.0f}% | "
                f"PnL: Rs {stats['pnl']:,.0f}"
            )

        report.append("\nWORST PERFORMING SYMBOLS")
        report.append("-" * 40)
        for symbol, stats in sorted_symbols[-5:]:
            report.append(
                f"{symbol:12s} Trades: {stats['trades']:3d} | "
                f"Win: {stats['win_rate']:.0f}% | "
                f"PnL: Rs {stats['pnl']:,.0f}"
            )

    report.append("\n" + "=" * 60)

    return "\n".join(report)
