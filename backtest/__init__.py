"""Backtesting framework for signal validation."""

from .engine import BacktestEngine, BacktestResult, Trade
from .metrics import PerformanceMetrics

__all__ = ['BacktestEngine', 'BacktestResult', 'Trade', 'PerformanceMetrics']
