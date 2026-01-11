"""CLI output formatting with rich tables."""

import csv
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from signals.scorer import StockSignal, SignalScorer, SignalType


console = Console()


class CLIOutput:
    """Format and display trading signals in CLI."""

    def __init__(self):
        self.scorer = SignalScorer()

    def display_scan_results(self, signals: List[StockSignal], show_all: bool = False):
        """
        Display scan results in a table.

        Args:
            signals: List of stock signals
            show_all: If False, only show buy/sell signals
        """
        if not show_all:
            # Filter to only actionable signals
            signals = [s for s in signals if s.signal_type != SignalType.HOLD]

        if not signals:
            console.print("[yellow]No actionable signals found.[/yellow]")
            return

        # Create table
        table = Table(
            title=f"Trading Signals ({len(signals)} stocks)",
            show_header=True,
            header_style="bold cyan",
        )

        table.add_column("Symbol", style="bold")
        table.add_column("Name", max_width=25)
        table.add_column("Price", justify="right")
        table.add_column("Signal", justify="center")
        table.add_column("Score", justify="center")
        table.add_column("Tech", justify="center")
        table.add_column("P/A", justify="center")

        for signal in signals:
            color = self.scorer.get_score_color(signal.signal_type)

            table.add_row(
                signal.symbol,
                signal.name[:25],
                f"₹{signal.price:,.2f}",
                Text(signal.signal_type.value, style=f"bold {color}"),
                Text(self.scorer.format_score(signal.total_score), style=color),
                self.scorer.format_score(signal.technical_score),
                self.scorer.format_score(signal.price_action_score),
            )

        console.print(table)

        # Summary
        buy_count = len([s for s in signals if s.signal_type in (SignalType.BUY, SignalType.STRONG_BUY)])
        sell_count = len([s for s in signals if s.signal_type in (SignalType.SELL, SignalType.STRONG_SELL)])

        console.print(f"\n[green]Buy Signals: {buy_count}[/green] | [red]Sell Signals: {sell_count}[/red]")

    def display_stock_analysis(self, signal: StockSignal):
        """Display detailed analysis for a single stock."""
        color = self.scorer.get_score_color(signal.signal_type)

        # Header
        header = Text()
        header.append(f"\n{signal.symbol} ", style="bold white")
        header.append(f"({signal.name})\n", style="dim")
        header.append(f"₹{signal.price:,.2f}", style="bold")

        console.print(Panel(header, title="Stock Analysis", border_style=color))

        # Signal summary
        signal_text = Text()
        signal_text.append("Signal: ", style="bold")
        signal_text.append(signal.signal_type.value, style=f"bold {color}")
        signal_text.append(f" (Score: {self.scorer.format_score(signal.total_score)})")
        console.print(signal_text)

        # Technical indicators
        console.print("\n[bold cyan]Technical Indicators:[/bold cyan]")
        tech = signal.technical_signals
        for key in ['rsi', 'macd', 'ema', 'bollinger', 'volume']:
            if key in tech:
                score = tech[key]['score']
                desc = tech[key]['description']
                score_color = "green" if score > 0 else "red" if score < 0 else "yellow"
                console.print(f"  [{score_color}]{self.scorer.format_score(score):>3}[/{score_color}] {desc}")

        # Price action
        console.print("\n[bold cyan]Price Action:[/bold cyan]")
        pa = signal.price_action_signals
        for key in ['trend', 'breakout', 'position']:
            if key in pa:
                score = pa[key]['score']
                desc = pa[key]['description']
                score_color = "green" if score > 0 else "red" if score < 0 else "yellow"
                console.print(f"  [{score_color}]{self.scorer.format_score(score):>3}[/{score_color}] {desc}")

        # Candlestick patterns
        if signal.candlestick_signals and signal.candlestick_signals.get('patterns'):
            console.print("\n[bold magenta]Candlestick Patterns:[/bold magenta]")
            for pattern in signal.candlestick_signals['patterns']:
                score = pattern['score']
                desc = pattern['pattern']
                score_color = "green" if score > 0 else "red" if score < 0 else "yellow"
                console.print(f"  [{score_color}]{self.scorer.format_score(score):>3}[/{score_color}] {desc}")

        # Chart patterns
        if signal.chart_pattern_signals and signal.chart_pattern_signals.get('patterns'):
            console.print("\n[bold blue]Chart Patterns:[/bold blue]")
            for pattern in signal.chart_pattern_signals['patterns']:
                score = pattern['score']
                desc = pattern['pattern']
                score_color = "green" if score > 0 else "red" if score < 0 else "yellow"
                console.print(f"  [{score_color}]{self.scorer.format_score(score):>3}[/{score_color}] {desc}")

        # Divergence
        if signal.divergence_signals and signal.divergence_signals.get('patterns'):
            console.print("\n[bold yellow]Divergence:[/bold yellow]")
            for pattern in signal.divergence_signals['patterns']:
                score = pattern['score']
                desc = pattern['pattern']
                score_color = "green" if score > 0 else "red" if score < 0 else "yellow"
                console.print(f"  [{score_color}]{self.scorer.format_score(score):>3}[/{score_color}] {desc}")

        # Trend Strength (ADX)
        if signal.trend_strength_signals:
            ts = signal.trend_strength_signals
            console.print("\n[bold white]Trend Strength (ADX):[/bold white]")
            adx = ts.get('adx', 0)
            strength = ts.get('trend_strength', 'Unknown')
            plus_di = ts.get('plus_di', 0)
            minus_di = ts.get('minus_di', 0)
            console.print(f"  ADX: {adx:.1f} ({strength})")
            console.print(f"  +DI: {plus_di:.1f} | -DI: {minus_di:.1f}")
            if ts.get('patterns'):
                for pattern in ts['patterns']:
                    score = pattern['score']
                    desc = pattern['pattern']
                    score_color = "green" if score > 0 else "red" if score < 0 else "yellow"
                    console.print(f"  [{score_color}]{self.scorer.format_score(score):>3}[/{score_color}] {desc}")

        # Fibonacci levels
        if signal.fibonacci_signals:
            fib = signal.fibonacci_signals
            console.print("\n[bold green]Fibonacci Analysis:[/bold green]")
            targets = fib.get('targets', {})
            if targets:
                trend = targets.get('trend', 'unknown')
                console.print(f"  Trend: {trend.title()}")
                console.print(f"  Swing High: ₹{targets.get('swing_high', 0):,.2f}")
                console.print(f"  Swing Low: ₹{targets.get('swing_low', 0):,.2f}")
                if targets.get('targets'):
                    console.print("  Targets:")
                    for t in targets['targets'][:2]:
                        console.print(f"    {t['ratio']:.1%}: ₹{t['price']:,.2f} ({t['distance_pct']:+.1f}%)")
                if targets.get('stops'):
                    console.print("  Stop Levels:")
                    for s in targets['stops'][:1]:
                        console.print(f"    {s['ratio']:.1%}: ₹{s['price']:,.2f} ({s['distance_pct']:.1f}% away)")
            if fib.get('patterns'):
                for pattern in fib['patterns']:
                    score = pattern['score']
                    desc = pattern['pattern']
                    score_color = "green" if score > 0 else "red" if score < 0 else "yellow"
                    console.print(f"  [{score_color}]{self.scorer.format_score(score):>3}[/{score_color}] {desc}")

        # Support/Resistance levels
        console.print("\n[bold cyan]Key Levels:[/bold cyan]")
        if pa.get('support'):
            console.print(f"  Support:    ₹{pa['support']:,.2f} ({pa['support_distance']:.1f}% away)")
        if pa.get('resistance'):
            console.print(f"  Resistance: ₹{pa['resistance']:,.2f} ({pa['resistance_distance']:.1f}% away)")

        # Score breakdown
        console.print("\n[bold white]Score Breakdown:[/bold white]")
        console.print(f"  Technical:     {self.scorer.format_score(signal.technical_score)}")
        console.print(f"  Price Action:  {self.scorer.format_score(signal.price_action_score)}")
        console.print(f"  Advanced:      {self.scorer.format_score(signal.advanced_score)}")
        console.print(f"  [bold]Total:         {self.scorer.format_score(signal.total_score)}[/bold]")

        console.print()

    def display_top_picks(self, signals: List[StockSignal], top_n: int = 10):
        """Display top buy and sell picks."""
        buy_signals = [s for s in signals if s.signal_type in (SignalType.BUY, SignalType.STRONG_BUY)]
        sell_signals = [s for s in signals if s.signal_type in (SignalType.SELL, SignalType.STRONG_SELL)]

        if buy_signals:
            console.print("\n[bold green]Top Buy Signals:[/bold green]")
            table = Table(show_header=True, header_style="bold green")
            table.add_column("Rank", justify="center")
            table.add_column("Symbol", style="bold")
            table.add_column("Price", justify="right")
            table.add_column("Score", justify="center")

            for i, signal in enumerate(buy_signals[:top_n], 1):
                table.add_row(
                    str(i),
                    signal.symbol,
                    f"₹{signal.price:,.2f}",
                    f"+{signal.total_score}",
                )
            console.print(table)

        if sell_signals:
            console.print("\n[bold red]Top Sell Signals:[/bold red]")
            table = Table(show_header=True, header_style="bold red")
            table.add_column("Rank", justify="center")
            table.add_column("Symbol", style="bold")
            table.add_column("Price", justify="right")
            table.add_column("Score", justify="center")

            for i, signal in enumerate(sell_signals[:top_n], 1):
                table.add_row(
                    str(i),
                    signal.symbol,
                    f"₹{signal.price:,.2f}",
                    str(signal.total_score),
                )
            console.print(table)

    def export_to_csv(self, signals: List[StockSignal], filepath: str):
        """Export signals to CSV file."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Symbol', 'Name', 'Price', 'Signal', 'Signal Strength', 'Total Score',
                'Technical Score', 'Price Action Score',
                'Support', 'Support Distance %', 'Resistance', 'Resistance Distance %'
            ])

            for signal in signals:
                pa = signal.price_action_signals
                support = pa.get('support')
                support_dist = pa.get('support_distance')
                resistance = pa.get('resistance')
                resistance_dist = pa.get('resistance_distance')

                writer.writerow([
                    signal.symbol,
                    signal.name,
                    signal.price,
                    signal.signal_type.value,
                    signal.signal_strength,
                    signal.total_score,
                    signal.technical_score,
                    signal.price_action_score,
                    f"{support:.2f}" if support is not None else "",
                    f"{support_dist:.1f}" if support_dist is not None else "",
                    f"{resistance:.2f}" if resistance is not None else "",
                    f"{resistance_dist:.1f}" if resistance_dist is not None else "",
                ])

        console.print(f"[green]Exported {len(signals)} signals to {filepath}[/green]")
