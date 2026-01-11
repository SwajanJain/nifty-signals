"""Signal generation by combining all indicators."""

from typing import Dict, List, Optional
import pandas as pd
from rich.console import Console

from data.fetcher import StockDataFetcher
from indicators.technical import TechnicalIndicators
from indicators.price_action import PriceActionAnalyzer
from indicators.candlestick import CandlestickPatterns
from indicators.chart_patterns import ChartPatterns
from indicators.fibonacci import FibonacciAnalysis
from indicators.divergence import DivergenceDetector
from indicators.trend_strength import TrendStrength
from .scorer import SignalScorer, StockSignal, SignalType


console = Console()


class SignalGenerator:
    """Generate trading signals for stocks."""

    def __init__(self, timeframe: str = "daily"):
        """
        Initialize signal generator.

        Args:
            timeframe: 'daily' or 'weekly'
        """
        self.timeframe = timeframe
        self.fetcher = StockDataFetcher()
        self.scorer = SignalScorer()

    def analyze_stock(self, symbol: str) -> Optional[StockSignal]:
        """
        Analyze a single stock and generate signal.

        Args:
            symbol: Stock symbol (without .NS)

        Returns:
            StockSignal object or None if analysis fails
        """
        # Fetch data
        df = self.fetcher.fetch_stock_data(symbol, self.timeframe)
        if df is None or len(df) < 50:
            return None

        try:
            # Calculate all indicators
            tech = TechnicalIndicators(df)
            price_action = PriceActionAnalyzer(df)
            candlestick = CandlestickPatterns(df)
            chart_patterns = ChartPatterns(df)
            fibonacci = FibonacciAnalysis(df)
            divergence = DivergenceDetector(df)
            trend_strength = TrendStrength(df)

            # Get all signals
            tech_signals = tech.get_all_signals()
            pa_signals = price_action.get_all_signals()
            candle_signals = candlestick.get_all_patterns()
            chart_signals = chart_patterns.get_all_patterns()
            fib_signals = fibonacci.get_all_signals()
            div_signals = divergence.get_all_divergences()
            trend_signals = trend_strength.get_all_signals()

            # Combined score from all sources
            total_score = (
                tech_signals['total_score'] +
                pa_signals['total_score'] +
                candle_signals['total_score'] +
                chart_signals['total_score'] +
                fib_signals['total_score'] +
                div_signals['total_score'] +
                trend_signals['total_score']
            )

            # Get stock info
            stock_info = self.fetcher.get_stock_info(symbol)

            # Create signal object
            return StockSignal(
                symbol=symbol,
                name=stock_info['name'],
                price=df['close'].iloc[-1],
                signal_type=self.scorer.classify_signal(total_score),
                total_score=total_score,
                technical_score=tech_signals['total_score'],
                price_action_score=pa_signals['total_score'],
                technical_signals=tech_signals,
                price_action_signals=pa_signals,
                candlestick_signals=candle_signals,
                chart_pattern_signals=chart_signals,
                fibonacci_signals=fib_signals,
                divergence_signals=div_signals,
                trend_strength_signals=trend_signals,
            )

        except Exception as e:
            console.print(f"[red]Error analyzing {symbol}: {e}[/red]")
            return None

    def scan_all(self, symbols: Optional[List[str]] = None) -> List[StockSignal]:
        """
        Scan all stocks and generate signals.

        Args:
            symbols: Optional list of symbols to scan

        Returns:
            List of StockSignal objects sorted by score
        """
        if symbols is None:
            symbols = [s['symbol'] for s in self.fetcher.stocks]

        signals = []
        total = len(symbols)

        with console.status("[bold green]Scanning stocks...") as status:
            for i, symbol in enumerate(symbols, 1):
                status.update(f"[bold green]Analyzing {symbol} ({i}/{total})...")
                signal = self.analyze_stock(symbol)
                if signal:
                    signals.append(signal)

        # Sort by total score (descending)
        signals.sort(key=lambda x: x.total_score, reverse=True)

        return signals

    def get_buy_signals(self, signals: List[StockSignal]) -> List[StockSignal]:
        """Filter for buy signals only."""
        return [s for s in signals if s.signal_type in (SignalType.BUY, SignalType.STRONG_BUY)]

    def get_sell_signals(self, signals: List[StockSignal]) -> List[StockSignal]:
        """Filter for sell signals only."""
        return [s for s in signals if s.signal_type in (SignalType.SELL, SignalType.STRONG_SELL)]
