#!/usr/bin/env python3
"""
Nifty Signals - Trading signal generator for Indian stocks.

A CLI tool that analyzes Nifty 100 stocks using technical indicators
and price action patterns to generate buy/sell signals.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from typing import Optional, List
import typer
from rich.console import Console

from signals.generator import SignalGenerator
from signals.enhanced_generator import EnhancedSignalGenerator, print_enhanced_signal
from output.cli import CLIOutput
from config import REPORTS_DIR


app = typer.Typer(
    name="nifty-signals",
    help="Trading signal generator for Indian Nifty 100 stocks",
    add_completion=False,
)
console = Console()


@app.command()
def scan(
    timeframe: str = typer.Option(
        "daily",
        "--timeframe", "-t",
        help="Timeframe for analysis: 'daily' or 'weekly'"
    ),
    stocks: Optional[str] = typer.Option(
        None,
        "--stocks", "-s",
        help="Comma-separated list of stock symbols to scan"
    ),
    export: Optional[str] = typer.Option(
        None,
        "--export", "-e",
        help="Export results to CSV file"
    ),
    show_all: bool = typer.Option(
        False,
        "--all", "-a",
        help="Show all stocks including HOLD signals"
    ),
    top: int = typer.Option(
        10,
        "--top", "-n",
        help="Show top N buy and sell signals"
    ),
):
    """
    Scan stocks and generate trading signals.

    Examples:
        python main.py scan --timeframe daily
        python main.py scan -t weekly --stocks RELIANCE,TCS,INFY
        python main.py scan --export signals.csv
    """
    console.print(f"\n[bold cyan]Nifty Signals Scanner[/bold cyan]")
    console.print(f"Timeframe: {timeframe.upper()}\n")

    # Parse stock list if provided
    symbol_list = None
    if stocks:
        symbol_list = [s.strip().upper() for s in stocks.split(",")]
        console.print(f"Scanning {len(symbol_list)} stocks: {', '.join(symbol_list)}\n")

    # Generate signals
    generator = SignalGenerator(timeframe=timeframe)
    signals = generator.scan_all(symbols=symbol_list)

    if not signals:
        console.print("[red]No signals generated. Check your internet connection.[/red]")
        raise typer.Exit(1)

    # Display results
    output = CLIOutput()

    if show_all:
        output.display_scan_results(signals, show_all=True)
    else:
        output.display_top_picks(signals, top_n=top)
        console.print("\n[dim]Use --all to see all signals including HOLD[/dim]")

    # Export if requested
    if export:
        output.export_to_csv(signals, export)


@app.command()
def generate(
    timeframe: str = typer.Option(
        "daily",
        "--timeframe", "-t",
        help="Timeframe for analysis: 'daily' or 'weekly'"
    ),
    stocks: Optional[str] = typer.Option(
        None,
        "--stocks", "-s",
        help="Comma-separated list of stock symbols to scan"
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output-dir", "-o",
        help="Directory to write CSV outputs"
    ),
    top: int = typer.Option(
        10,
        "--top", "-n",
        help="Number of top BUY signals to export separately"
    ),
):
    """
    Generate daily/weekly signal CSVs for automated use.

    Examples:
        python main.py generate --timeframe daily
        python main.py generate -t weekly --output-dir reports
    """
    console.print(f"\n[bold cyan]Generating Signals[/bold cyan]")
    console.print(f"Timeframe: {timeframe.upper()}\n")

    symbol_list = None
    if stocks:
        symbol_list = [s.strip().upper() for s in stocks.split(",")]
        console.print(f"Scanning {len(symbol_list)} stocks: {', '.join(symbol_list)}\n")

    generator = SignalGenerator(timeframe=timeframe)
    signals = generator.scan_all(symbols=symbol_list)

    if not signals:
        console.print("[red]No signals generated. Check your internet connection.[/red]")
        raise typer.Exit(1)

    output = CLIOutput()
    target_dir = Path(output_dir) if output_dir else REPORTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    date_tag = datetime.now().strftime("%Y-%m-%d")
    all_path = target_dir / f"signals_{timeframe}_{date_tag}.csv"
    output.export_to_csv(signals, str(all_path))

    buy_signals = generator.get_buy_signals(signals)
    if top > 0:
        buy_signals = buy_signals[:top]

    buy_path = target_dir / f"buy_signals_{timeframe}_{date_tag}.csv"
    output.export_to_csv(buy_signals, str(buy_path))


@app.command()
def analyze(
    symbol: str = typer.Argument(
        ...,
        help="Stock symbol to analyze (e.g., RELIANCE)"
    ),
    timeframe: str = typer.Option(
        "daily",
        "--timeframe", "-t",
        help="Timeframe for analysis: 'daily' or 'weekly'"
    ),
):
    """
    Analyze a single stock in detail.

    Examples:
        python main.py analyze RELIANCE
        python main.py analyze TCS --timeframe weekly
    """
    symbol = symbol.upper()
    console.print(f"\n[bold cyan]Analyzing {symbol}...[/bold cyan]\n")

    generator = SignalGenerator(timeframe=timeframe)
    signal = generator.analyze_stock(symbol)

    if not signal:
        console.print(f"[red]Could not analyze {symbol}. Check if the symbol is valid.[/red]")
        raise typer.Exit(1)

    output = CLIOutput()
    output.display_stock_analysis(signal)


@app.command()
def list_stocks():
    """
    List all available Nifty 100 stocks.
    """
    from data.fetcher import StockDataFetcher

    fetcher = StockDataFetcher()

    console.print("\n[bold cyan]Nifty 100 Stocks[/bold cyan]\n")

    for i, stock in enumerate(fetcher.stocks, 1):
        console.print(f"{i:3}. {stock['symbol']:15} - {stock['name']}")

    console.print(f"\n[dim]Total: {len(fetcher.stocks)} stocks[/dim]")


@app.command()
def clear_cache():
    """
    Clear the data cache.
    """
    from data.cache import DataCache

    cache = DataCache()
    cache.clear()
    console.print("[green]Cache cleared successfully.[/green]")


@app.command()
def enhanced_scan(
    stocks: Optional[str] = typer.Option(
        None,
        "--stocks", "-s",
        help="Comma-separated list of stock symbols to scan"
    ),
    capital: float = typer.Option(
        500000,
        "--capital", "-c",
        help="Trading capital for position sizing"
    ),
    risk: float = typer.Option(
        0.01,
        "--risk", "-r",
        help="Risk per trade (0.01 = 1%)"
    ),
    top: int = typer.Option(
        5,
        "--top", "-n",
        help="Show top N actionable signals"
    ),
):
    """
    Enhanced scan with market regime, MTF, sector analysis, and position sizing.

    Examples:
        python main.py enhanced-scan
        python main.py enhanced-scan --capital 1000000 --risk 0.02
    """
    console.print(f"\n[bold cyan]Enhanced Signal Scanner[/bold cyan]")
    console.print(f"Capital: Rs {capital:,.0f} | Risk per trade: {risk*100:.1f}%\n")

    # Parse stock list if provided
    symbol_list = None
    if stocks:
        symbol_list = [s.strip().upper() for s in stocks.split(",")]
        console.print(f"Scanning {len(symbol_list)} stocks: {', '.join(symbol_list)}\n")

    # Generate enhanced signals
    generator = EnhancedSignalGenerator(
        capital=capital,
        risk_per_trade=risk
    )

    # Get market summary first
    market = generator.get_market_summary()

    console.print("[bold]Market Context[/bold]")
    console.print(f"Regime: {market['regime'].get('regime_name', 'UNKNOWN')}")
    console.print(f"Should Trade: {'Yes' if market['should_trade'] else 'NO - Stay in cash'}")
    console.print(f"Position Size: {market['position_multiplier']*100:.0f}% of normal")
    if market['top_sectors']:
        console.print(f"Top Sectors: {', '.join(market['top_sectors'])}")
    if market['avoid_sectors']:
        console.print(f"Avoid Sectors: {', '.join(market['avoid_sectors'])}")
    console.print()

    if not market['should_trade']:
        console.print("[bold red]Market regime suggests staying in cash. No signals generated.[/bold red]")
        raise typer.Exit(0)

    # Run enhanced scan
    signals = generator.scan_enhanced(symbols=symbol_list)

    if not signals:
        console.print("[red]No signals generated.[/red]")
        raise typer.Exit(1)

    # Get actionable signals
    actionable = generator.get_actionable_signals(signals)

    console.print(f"\n[bold]Results[/bold]")
    console.print(f"Scanned: {len(signals)} stocks")
    console.print(f"Actionable BUY signals: {len(actionable)}\n")

    # Display top actionable signals
    if actionable:
        console.print("[bold green]TOP ACTIONABLE SIGNALS[/bold green]")
        console.print("-" * 70)

        for signal in actionable[:top]:
            ts = signal.trade_setup
            console.print(f"\n[bold]{signal.symbol}[/bold] - {signal.name}")
            console.print(f"Price: Rs {signal.price:.2f} | Score: {signal.total_score:+d} | {signal.final_recommendation}")
            console.print(f"Sector: {signal.sector} (Rank #{signal.sector_rank}) | MTF: {signal.mtf_recommendation}")
            if ts:
                console.print(f"Entry: Rs {ts.entry_price:.2f} | SL: Rs {ts.stop_loss:.2f} | T1: Rs {ts.target_1:.2f} | T2: Rs {ts.target_2:.2f}")
                console.print(f"Position: {ts.position_size} shares (Rs {ts.position_value:,.0f}) | Risk: Rs {ts.risk_amount:,.0f} ({ts.risk_percent:.1f}%)")
            console.print("-" * 70)
    else:
        console.print("[yellow]No actionable signals found. Consider waiting for better setups.[/yellow]")

    # Show skipped high-score stocks
    high_score_skipped = [s for s in signals if s.total_score >= 5 and s.skip_reasons]
    if high_score_skipped:
        console.print(f"\n[bold yellow]HIGH SCORE BUT SKIPPED ({len(high_score_skipped)})[/bold yellow]")
        for signal in high_score_skipped[:3]:
            console.print(f"  {signal.symbol}: Score {signal.total_score:+d} - {', '.join(signal.skip_reasons)}")


@app.command()
def regime():
    """
    Show current market regime analysis.

    Examples:
        python main.py regime
    """
    from indicators.market_regime import RegimeDetector

    console.print(f"\n[bold cyan]Market Regime Analysis[/bold cyan]\n")

    detector = RegimeDetector()
    regime = detector.detect_regime()

    console.print(f"[bold]Regime: {regime['regime_name']}[/bold]")
    console.print(f"Total Score: {regime['total_score']}")
    console.print(f"Should Trade: {'Yes' if regime['should_trade'] else 'NO'}")
    console.print(f"Position Size: {regime['position_size_multiplier']*100:.0f}% of normal")

    console.print(f"\n[bold]Trend Analysis[/bold]")
    trend = regime['trend']
    console.print(f"Nifty: {trend['nifty_level']:,.0f}")
    console.print(f"Score: {trend['score']}")
    for signal in trend['signals']:
        console.print(f"  - {signal}")

    console.print(f"\n[bold]Volatility (VIX)[/bold]")
    vol = regime['volatility']
    console.print(f"VIX: {vol['vix']:.1f} ({vol['regime']})")
    console.print(f"Avg VIX: {vol['avg_vix']:.1f}")
    console.print(f"5-day change: {vol['vix_change_5d']:.1f}%")

    console.print(f"\n[bold]Market Breadth[/bold]")
    breadth = regime['breadth']
    console.print(f"Breadth: {breadth['breadth']}")
    console.print(f"Up days (10): {breadth['up_days_10']}")

    console.print(f"\n[bold]Strategy Recommendation[/bold]")
    strategy = regime['strategy']
    console.print(f"Bias: {strategy['bias']}")
    console.print(f"Strategies: {', '.join(strategy['strategies'])}")
    console.print(f"Notes: {strategy['notes']}")


@app.command()
def sectors():
    """
    Show sector relative strength analysis.

    Examples:
        python main.py sectors
    """
    from indicators.sector_strength import SectorStrengthAnalyzer, print_sector_report

    console.print(f"\n[bold cyan]Sector Relative Strength Analysis[/bold cyan]\n")
    console.print("Fetching sector data (this may take a minute)...\n")

    analyzer = SectorStrengthAnalyzer()
    analyzer.fetch_sector_data()
    analysis = analyzer.analyze_sectors()

    if not analysis:
        console.print("[red]Could not analyze sectors.[/red]")
        raise typer.Exit(1)

    report = print_sector_report(analysis)
    console.print(report)


@app.command()
def analyze_enhanced(
    symbol: str = typer.Argument(
        ...,
        help="Stock symbol to analyze (e.g., RELIANCE)"
    ),
    capital: float = typer.Option(
        500000,
        "--capital", "-c",
        help="Trading capital for position sizing"
    ),
):
    """
    Enhanced analysis of a single stock with all advanced features.

    Examples:
        python main.py analyze-enhanced RELIANCE
        python main.py analyze-enhanced TCS --capital 1000000
    """
    symbol = symbol.upper()
    console.print(f"\n[bold cyan]Enhanced Analysis: {symbol}[/bold cyan]\n")

    generator = EnhancedSignalGenerator(capital=capital)
    signal = generator.analyze_stock_enhanced(symbol)

    if not signal:
        console.print(f"[red]Could not analyze {symbol}.[/red]")
        raise typer.Exit(1)

    report = print_enhanced_signal(signal)
    console.print(report)


def main():
    """Main entry point."""
    console.print("\n[bold]Nifty Signals[/bold] - Indian Stock Trading Signals\n", style="cyan")
    app()


if __name__ == "__main__":
    main()
