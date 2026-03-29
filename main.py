#!/usr/bin/env python3
"""
Nifty Signals - Trading signal generator for Indian stocks.

A CLI tool that analyzes Nifty 100 stocks using technical indicators
and price action patterns to generate buy/sell signals.
"""

import sys
import json
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


def _print_footer():
    """Print standard disclaimer and data source attribution."""
    console.print(
        "\n[dim]Data: screener.in (fundamentals), Yahoo Finance (prices) | "
        "Not investment advice — verify independently before trading[/dim]"
    )


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
    _print_footer()

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

    _print_footer()


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

    _print_footer()


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
    _print_footer()


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
    _print_footer()


@app.command()
def reddit(
    limit: int = typer.Option(
        25,
        "--limit", "-l",
        help="Posts per subreddit per sort mode (default: 25)"
    ),
    comments: bool = typer.Option(
        False,
        "--comments",
        help="Also fetch comments for top budget posts (slower)"
    ),
    cached: bool = typer.Option(
        False,
        "--cached",
        help="Use cached results if available"
    ),
):
    """
    Fetch Reddit sentiment from Indian investment subreddits.

    Analyzes posts from r/IndiaInvestments, r/IndianStreetBets,
    r/IndianStockMarket for budget discussions, stock mentions,
    and sector sentiment.

    Examples:
        python main.py reddit
        python main.py reddit --comments --limit 50
        python main.py reddit --cached
    """
    from data.reddit_fetcher import RedditFetcher, format_reddit_report

    console.print(f"\n[bold cyan]Reddit Sentiment Agent[/bold cyan]\n")

    fetcher = RedditFetcher()

    if cached:
        cached_data = fetcher.load_cache()
        if cached_data:
            console.print("[dim]Using cached results[/dim]\n")
            report = format_reddit_report(cached_data)
            console.print(report)
            return
        console.print("[yellow]No cache found, fetching fresh data...[/yellow]\n")

    analysis = fetcher.fetch_and_analyze(
        limit_per_sub=limit,
        fetch_comments=comments,
    )
    report = format_reddit_report(analysis)
    console.print(report)

    console.print(f"\n[dim]Results cached to .cache/reddit_posts.json[/dim]")


# =============================================================================
# Fundamental Analysis Commands
# =============================================================================


@app.command()
def fundamental_scan(
    top: int = typer.Option(20, "--top", "-n", help="Show top N stocks"),
    sector: Optional[str] = typer.Option(
        None, "--sector", "-s", help="Filter by sector"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force refresh data from screener.in"
    ),
    min_score: int = typer.Option(0, "--min-score", help="Minimum fundamental score"),
):
    """
    Full Nifty 500 fundamental scan with composite scoring.

    Fetches data from screener.in, computes fundamental scores,
    and ranks stocks by overall fundamental quality.

    Examples:
        python main.py fundamental-scan
        python main.py fundamental-scan --top 10 --sector IT
        python main.py fundamental-scan --refresh --min-score 60
    """
    from config import get_nifty500_stocks
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder, FundamentalScorer
    from fundamentals.output import FundamentalOutput

    console.print("\n[bold cyan]Fundamental Scan - Nifty 500[/bold cyan]\n")

    stocks = get_nifty500_stocks()
    if not stocks:
        console.print("[red]No Nifty 500 stocks found in stocks.json[/red]")
        raise typer.Exit(1)

    symbols = [s['symbol'] for s in stocks]
    if sector:
        symbols = [
            s['symbol'] for s in stocks
            if s.get('sector', '').lower() == sector.lower()
        ]
        console.print(f"Filtering by sector: {sector} ({len(symbols)} stocks)\n")

    # Fetch data
    fetcher = ScreenerFetcher()
    raw_data = fetcher.fetch_batch(symbols, force_refresh=refresh)

    if not raw_data:
        console.print("[red]No fundamental data fetched. Check your connection.[/red]")
        raise typer.Exit(1)

    # Build profiles and score
    builder = ProfileBuilder()
    scorer = FundamentalScorer()
    profiles = {}
    scores = []

    for symbol, raw in raw_data.items():
        profile = builder.build(raw)
        fs = scorer.score(profile)
        if fs.total_score >= min_score:
            profiles[symbol] = profile
            scores.append(fs)

    # Sort by score
    scores.sort(key=lambda s: s.total_score, reverse=True)

    # Display
    output = FundamentalOutput()
    output.display_scan_results(scores, profiles, top_n=top)

    console.print(f"\n[dim]Total: {len(scores)} stocks scored | Showing top {min(top, len(scores))}[/dim]")
    _print_footer()


@app.command()
def fundamental_analyze(
    symbol: str = typer.Argument(..., help="Stock symbol (e.g., RELIANCE)"),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force refresh data from screener.in"
    ),
):
    """
    Deep fundamental analysis of a single stock.

    Fetches comprehensive financial data from screener.in and provides
    detailed scoring, valuation, profitability, growth, and quality analysis.

    Examples:
        python main.py fundamental-analyze RELIANCE
        python main.py fundamental-analyze TCS --refresh
    """
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder, FundamentalScorer
    from fundamentals.screens import SCREENS
    from fundamentals.output import FundamentalOutput

    symbol = symbol.upper()
    console.print(f"\n[bold cyan]Fundamental Analysis: {symbol}[/bold cyan]\n")

    # Fetch
    fetcher = ScreenerFetcher()
    raw = fetcher.fetch_stock(symbol, force_refresh=refresh)

    if not raw:
        console.print(f"[red]Could not fetch data for {symbol}.[/red]")
        raise typer.Exit(1)

    # Build profile and score
    builder = ProfileBuilder()
    profile = builder.build(raw)

    scorer = FundamentalScorer()
    fs = scorer.score(profile)

    # Check which strategies match
    for name, screen_cls in SCREENS.items():
        screen = screen_cls()
        result = screen.screen(profile)
        setattr(fs, f'matches_{name}', result.passes)

    # Display
    output = FundamentalOutput()
    output.display_stock_analysis(profile, fs)
    _print_footer()


@app.command()
def screen(
    strategy: str = typer.Argument(
        ..., help="Strategy: value, growth, quality, garp, dividend"
    ),
    top: int = typer.Option(20, "--top", "-n", help="Show top N matches"),
    sector: Optional[str] = typer.Option(
        None, "--sector", help="Filter by sector"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force refresh data from screener.in"
    ),
):
    """
    Run a specific fundamental screening strategy on Nifty 500.

    Available strategies: value, growth, quality, garp, dividend

    Examples:
        python main.py screen value
        python main.py screen growth --top 10
        python main.py screen quality --sector IT
    """
    from config import get_nifty500_stocks
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder
    from fundamentals.screens import get_screen
    from fundamentals.output import FundamentalOutput

    console.print(f"\n[bold cyan]{strategy.upper()} Screen - Nifty 500[/bold cyan]\n")

    try:
        screen_instance = get_screen(strategy)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]{screen_instance.description}[/dim]\n")

    # Load stocks
    stocks = get_nifty500_stocks()
    if not stocks:
        console.print("[red]No Nifty 500 stocks found in stocks.json[/red]")
        raise typer.Exit(1)

    symbols = [s['symbol'] for s in stocks]
    if sector:
        symbols = [
            s['symbol'] for s in stocks
            if s.get('sector', '').lower() == sector.lower()
        ]
        console.print(f"Filtering by sector: {sector} ({len(symbols)} stocks)\n")

    # Fetch data
    fetcher = ScreenerFetcher()
    raw_data = fetcher.fetch_batch(symbols, force_refresh=refresh)

    # Build profiles
    builder = ProfileBuilder()
    profiles = {}
    for symbol_key, raw in raw_data.items():
        profiles[symbol_key] = builder.build(raw)

    # Run screen
    results = screen_instance.screen_batch(profiles)

    # Display
    output = FundamentalOutput()
    output.display_screen_results(results[:top], strategy)

    console.print(f"\n[dim]{len(results)} stocks passed out of {len(profiles)} analyzed[/dim]")


@app.command()
def fundamental_compare(
    symbols: str = typer.Argument(
        ..., help="Comma-separated symbols (e.g., TCS,INFY,WIPRO)"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force refresh data from screener.in"
    ),
):
    """
    Compare fundamentals of 2+ stocks side-by-side.

    Examples:
        python main.py fundamental-compare TCS,INFY,WIPRO
        python main.py fundamental-compare HDFCBANK,ICICIBANK,KOTAKBANK
    """
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder, FundamentalScorer
    from fundamentals.output import FundamentalOutput

    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    if len(symbol_list) < 2:
        console.print("[red]Please provide at least 2 symbols separated by commas.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Fundamental Comparison: {', '.join(symbol_list)}[/bold cyan]\n")

    fetcher = ScreenerFetcher()
    builder = ProfileBuilder()
    scorer = FundamentalScorer()

    profiles = []
    scores = []

    for sym in symbol_list:
        raw = fetcher.fetch_stock(sym, force_refresh=refresh)
        if not raw:
            console.print(f"[yellow]Could not fetch {sym}, skipping.[/yellow]")
            continue

        profile = builder.build(raw)
        fs = scorer.score(profile)
        profiles.append(profile)
        scores.append(fs)

    if len(profiles) < 2:
        console.print("[red]Need at least 2 stocks for comparison.[/red]")
        raise typer.Exit(1)

    output = FundamentalOutput()
    output.display_comparison(profiles, scores)


# =============================================================================
# Tailwind / External Factors Commands
# =============================================================================


@app.command()
def tailwinds(
    sector: Optional[str] = typer.Option(
        None, "--sector", "-s", help="Deep dive into a specific sector"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force refresh news data"
    ),
):
    """
    Show macro themes and sector tailwind analysis.

    Analyzes external factors: government policies, demand shifts,
    global trends, commodity cycles, and their impact on sectors.

    Examples:
        python main.py tailwinds
        python main.py tailwinds --sector IT
        python main.py tailwinds --refresh
    """
    from tailwinds.registry import ThemeRegistry
    from tailwinds.analyzer import TailwindAnalyzer
    from tailwinds.news_fetcher import NewsFetcher
    from tailwinds.output import TailwindOutput

    console.print("\n[bold cyan]Tailwind Analysis - External Factors[/bold cyan]\n")

    registry = ThemeRegistry()
    fetcher = NewsFetcher()
    analyzer = TailwindAnalyzer(registry=registry, fetcher=fetcher)
    output = TailwindOutput()

    if sector:
        # Sector deep dive
        console.print(f"Analyzing tailwinds for [bold]{sector}[/bold]...\n")
        sector_result = analyzer.analyze_sector(sector)
        news_items = fetcher.fetch_all(force_refresh=refresh)
        sector_news = fetcher.get_sector_news(news_items, sector)
        output.display_sector_deep_dive(sector_result, sector_news)
    else:
        # Show all themes + sector rankings
        themes = registry.get_active_themes()
        output.display_themes(themes)

        console.print()
        sector_scores = analyzer.analyze_all_sectors(force_refresh=refresh)
        output.display_sector_scores(sector_scores)

        # Summary
        tailwind_sectors = [s for s, st in sector_scores.items() if st.total_score >= 60]
        headwind_sectors = [s for s, st in sector_scores.items() if st.total_score < 40]

        if tailwind_sectors:
            console.print(f"\n[green]Tailwind sectors:[/green] {', '.join(tailwind_sectors)}")
        if headwind_sectors:
            console.print(f"[red]Headwind sectors:[/red] {', '.join(headwind_sectors)}")


@app.command()
def full_analyze(
    symbol: str = typer.Argument(..., help="Stock symbol (e.g., RELIANCE)"),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force refresh all data"
    ),
):
    """
    Combined fundamental + tailwind analysis for a single stock.

    Shows internal quality score, external environment score,
    and blended composite score.

    Examples:
        python main.py full-analyze RELIANCE
        python main.py full-analyze TCS --refresh
    """
    from config import get_nifty500_stocks
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder, FundamentalScorer
    from fundamentals.screens import SCREENS
    from fundamentals.output import FundamentalOutput
    from tailwinds.analyzer import TailwindAnalyzer, CompositeAnalyzer
    from tailwinds.output import TailwindOutput

    symbol = symbol.upper()
    console.print(f"\n[bold cyan]Full Analysis: {symbol}[/bold cyan]\n")

    # --- Fundamental ---
    fetcher = ScreenerFetcher()
    raw = fetcher.fetch_stock(symbol, force_refresh=refresh)
    if not raw:
        console.print(f"[red]Could not fetch fundamental data for {symbol}.[/red]")
        raise typer.Exit(1)

    builder = ProfileBuilder()
    profile = builder.build(raw)

    scorer = FundamentalScorer()
    fs = scorer.score(profile)

    # Check strategies
    for name, screen_cls in SCREENS.items():
        screen_obj = screen_cls()
        result = screen_obj.screen(profile)
        setattr(fs, f'matches_{name}', result.passes)

    # --- Tailwind ---
    # Determine sector from profile or stocks.json
    sector = profile.sector
    if not sector:
        stocks = get_nifty500_stocks()
        for s in stocks:
            if s['symbol'] == symbol:
                sector = s.get('sector', '')
                break

    tw_analyzer = TailwindAnalyzer()
    tw_score = tw_analyzer.score_stock(symbol, sector) if sector else None

    # --- Display fundamental ---
    fund_output = FundamentalOutput()
    fund_output.display_stock_analysis(profile, fs)

    # --- Display composite ---
    if tw_score:
        composite_analyzer = CompositeAnalyzer()
        composite = composite_analyzer.compute(fs, tw_score, profile)

        console.print("\n" + "=" * 60)
        tw_output = TailwindOutput()
        tw_output.display_composite_analysis(
            composite,
            tw_score,
            fundamental_green_flags=fs.green_flags,
            fundamental_red_flags=fs.red_flags,
        )
    else:
        console.print(f"\n[yellow]No sector mapping found for {symbol} - tailwind score unavailable.[/yellow]")

    _print_footer()


@app.command()
def full_scan(
    top: int = typer.Option(20, "--top", "-n", help="Show top N stocks"),
    sector: Optional[str] = typer.Option(
        None, "--sector", "-s", help="Filter by sector"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force refresh all data"
    ),
):
    """
    Nifty 500 scan ranked by composite score (fundamental + tailwind).

    Examples:
        python main.py full-scan --top 10
        python main.py full-scan --sector IT
    """
    from config import get_nifty500_stocks
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder, FundamentalScorer
    from tailwinds.analyzer import TailwindAnalyzer, CompositeAnalyzer
    from tailwinds.output import TailwindOutput

    console.print("\n[bold cyan]Full Composite Scan - Nifty 500[/bold cyan]\n")

    stocks = get_nifty500_stocks()
    if not stocks:
        console.print("[red]No Nifty 500 stocks found in stocks.json[/red]")
        raise typer.Exit(1)

    if sector:
        stocks = [s for s in stocks if s.get('sector', '').lower() == sector.lower()]
        console.print(f"Filtering by sector: {sector} ({len(stocks)} stocks)\n")

    symbols = [s['symbol'] for s in stocks]
    stock_sectors = {s['symbol']: s.get('sector', '') for s in stocks}

    # Fetch fundamentals
    fetcher = ScreenerFetcher()
    raw_data = fetcher.fetch_batch(symbols, force_refresh=refresh)

    # Score
    builder = ProfileBuilder()
    scorer = FundamentalScorer()
    tw_analyzer = TailwindAnalyzer()
    composite_analyzer = CompositeAnalyzer()

    composites = []
    for sym, raw in raw_data.items():
        profile = builder.build(raw)
        fs = scorer.score(profile)

        sec = stock_sectors.get(sym, profile.sector or '')
        tw = tw_analyzer.score_stock(sym, sec) if sec else None

        if tw:
            comp = composite_analyzer.compute(fs, tw, profile)
            composites.append(comp)

    composites.sort(key=lambda c: c.composite_score, reverse=True)

    # Display
    output = TailwindOutput()
    output.display_composite_scan(composites, top_n=top)

    console.print(f"\n[dim]Total: {len(composites)} stocks scored | Showing top {min(top, len(composites))}[/dim]")
    _print_footer()


# =============================================================================
# Fund / ETF Commands
# =============================================================================


def _resolve_portfolio_schemes(universe, portfolio: Optional[str]):
    schemes = []
    if not portfolio:
        return schemes
    for raw in portfolio.split(","):
        query = raw.strip()
        if not query:
            continue
        scheme = universe.find(query)
        if scheme:
            schemes.append(scheme)
    return schemes


def _load_imported_portfolio(path: Optional[str]):
    if not path:
        return None
    from funds.portfolio_loader import load_portfolio
    return load_portfolio(Path(path))


def _build_fund_scorer(refresh_holdings: bool = False, market_regime: str = "normal"):
    from funds import FundScorer
    from funds.scorer import LiveFundamentalScoreProvider, LiveTailwindProvider

    return FundScorer(
        fundamentals_provider=LiveFundamentalScoreProvider(force_refresh=refresh_holdings),
        tailwind_provider=LiveTailwindProvider(),
        market_regime=market_regime,
    )


def _build_nifty_index_researcher(refresh_holdings: bool = False, market_regime: str = "normal"):
    from funds import NiftyIndexResearcher

    return NiftyIndexResearcher(
        scorer=_build_fund_scorer(refresh_holdings=refresh_holdings, market_regime=market_regime)
    )


@app.command()
def fund_sync():
    """Sync local fund metadata and NAV history."""
    from funds.sync import FundSyncService

    result = FundSyncService().sync_universe(write=True)
    console.print_json(data=result)


@app.command()
def fund_import_portfolio(
    path: str = typer.Argument(..., help="Path to CSV, JSON, or CAS PDF"),
    name: Optional[str] = typer.Option(None, "--name", help="Portfolio name override"),
):
    """Import a portfolio for overlap-aware fund recommendations."""
    from funds.cache import FundCache
    from funds.portfolio_loader import load_portfolio

    imported = load_portfolio(Path(path), name=name)
    payload = {
        "name": imported.name,
        "source": imported.source,
        "as_of": imported.as_of,
        "positions": [
            {
                "kind": position.kind,
                "identifier": position.identifier,
                "name": position.name,
                "weight": position.weight,
                "units": position.units,
                "amount": position.amount,
            }
            for position in imported.positions
        ],
    }
    FundCache().set_imported_portfolio(imported.name, imported.source, payload)
    console.print_json(data={"name": imported.name, "source": imported.source, "positions": len(imported.positions)})


@app.command()
def fund_portfolio_fit(
    scheme: str = typer.Argument(..., help="Scheme name or identifier"),
    portfolio_file: Optional[str] = typer.Option(None, "--portfolio-file", help="Imported portfolio file path"),
    portfolio_name: Optional[str] = typer.Option(None, "--portfolio-name", help="Previously imported portfolio name"),
):
    """Evaluate a scheme against an imported portfolio."""
    from funds.cache import FundCache
    from funds.portfolio_fit import PortfolioFitAnalyzer
    from funds.portfolio_loader import load_portfolio
    from funds.universe import FundUniverse

    universe = FundUniverse()
    target = universe.find(scheme)
    if not target:
        console.print(f"[red]Could not find scheme: {scheme}[/red]")
        raise typer.Exit(1)

    imported = None
    if portfolio_file:
        imported = load_portfolio(Path(portfolio_file))
    elif portfolio_name:
        payload = FundCache().get_imported_portfolio(portfolio_name)
        if not payload:
            console.print(f"[red]No imported portfolio found: {portfolio_name}[/red]")
            raise typer.Exit(1)
        from funds.models import ImportedPortfolio, ImportedPosition
        imported = ImportedPortfolio(
            name=payload["name"],
            source=payload.get("source", "cached"),
            as_of=payload.get("as_of", ""),
            positions=[
                ImportedPosition(
                    kind=item["kind"],
                    identifier=item["identifier"],
                    name=item.get("name", item["identifier"]),
                    weight=float(item.get("weight", 0.0)),
                    units=float(item.get("units", 0.0)),
                    amount=float(item.get("amount", 0.0)),
                )
                for item in payload.get("positions", [])
            ],
        )
    else:
        console.print("[red]Provide either --portfolio-file or --portfolio-name.[/red]")
        raise typer.Exit(1)

    fit = PortfolioFitAnalyzer().analyze_imported(target, imported, universe=universe)
    console.print_json(
        data={
            "scheme": target.name,
            "portfolio": imported.name,
            "fit_label": fit.fit_label,
            "fit_score": fit.fit_score,
            "overlap_pct": fit.overlap_pct,
            "notes": fit.notes,
        }
    )


@app.command()
def fund_review_write(
    scheme: str = typer.Argument(..., help="Scheme name or identifier"),
    verdict: str = typer.Option(..., "--verdict", help="INVEST, STAGGER, WATCH, AVOID"),
    confidence: str = typer.Option("MEDIUM", "--confidence", help="LOW, MEDIUM, HIGH"),
    thesis: str = typer.Option("", "--thesis", help="Short thesis"),
    reviewer: str = typer.Option("claude", "--reviewer", help="Reviewer name"),
):
    """Write or update a manual review entry for a scheme."""
    from funds.models import FundResearchReview
    from funds.review_store import WritableResearchReviewStore
    from funds.universe import FundUniverse

    universe = FundUniverse()
    target = universe.find(scheme)
    if not target:
        console.print(f"[red]Could not find scheme: {scheme}[/red]")
        raise typer.Exit(1)

    store = WritableResearchReviewStore()
    existing = store.get(target.scheme_id)
    review = FundResearchReview(
        scheme_id=target.scheme_id,
        validated_at=datetime.now().date().isoformat(),
        reviewer=reviewer,
        verdict=verdict.upper(),
        confidence=confidence.upper(),
        thesis_quality_score=existing.thesis_quality_score if existing else 70,
        evidence_quality_score=existing.evidence_quality_score if existing else 70,
        portfolio_fit_score=existing.portfolio_fit_score if existing else 70,
        strengths=list(existing.strengths) if existing else [],
        concerns=list(existing.concerns) if existing else [],
        open_questions=list(existing.open_questions) if existing else [],
        thesis=thesis or (existing.thesis if existing else ""),
        disconfirmations=list(existing.disconfirmations) if existing else [],
        notes=list(existing.notes) if existing else [],
    )
    store.upsert(review)
    console.print_json(data={"scheme": target.name, "verdict": review.verdict, "confidence": review.confidence})


@app.command()
def fund_review_list_stale(
    max_age_days: int = typer.Option(30, "--max-age-days", help="Max review age before staleness"),
):
    """List stale fund reviews."""
    from funds.review_store import WritableResearchReviewStore

    items = WritableResearchReviewStore().list_stale(max_age_days=max_age_days)
    console.print_json(
        data={
            "count": len(items),
            "reviews": [
                {"scheme_id": item.scheme_id, "validated_at": item.validated_at, "verdict": item.verdict}
                for item in items
            ],
        }
    )


@app.command()
def fund_sip_backtest(
    scheme: str = typer.Argument(..., help="Scheme name or identifier"),
    monthly_amount: float = typer.Option(10000, "--monthly-amount", help="Monthly SIP amount"),
):
    """Run a simple SIP backtest from cached NAV history."""
    from funds.backtest import backtest_single_scheme_sip
    from funds.cache import FundCache
    from funds.universe import FundUniverse

    universe = FundUniverse()
    target = universe.find(scheme)
    if not target:
        console.print(f"[red]Could not find scheme: {scheme}[/red]")
        raise typer.Exit(1)

    history = FundCache().get_nav_history(target.scheme_id)
    if not history:
        console.print("[red]No NAV history found. Run fund-sync first.[/red]")
        raise typer.Exit(1)

    result = backtest_single_scheme_sip(target.scheme_id, history, monthly_amount)
    console.print_json(
        data={
            "scheme": target.name,
            "months": result.sip.months,
            "invested": result.sip.invested,
            "final_value": result.sip.final_value,
            "absolute_return_pct": result.sip.absolute_return_pct,
        }
    )


@app.command()
def fund_scan(
    top: int = typer.Option(10, "--top", "-n", help="Show top N funds"),
    strategy: Optional[str] = typer.Option(
        None, "--strategy", "-s", help="Filter by strategy: core, thematic, sectoral"
    ),
    vehicle: Optional[str] = typer.Option(
        None, "--vehicle", "-v", help="Filter by vehicle: mutual_fund, etf"
    ),
    theme: Optional[str] = typer.Option(
        None, "--theme", "-t", help="Filter by theme or sector"
    ),
    refresh_holdings: bool = typer.Option(
        False, "--refresh-holdings", help="Force refresh underlying stock fundamentals"
    ),
    portfolio: Optional[str] = typer.Option(
        None, "--portfolio", help="Comma-separated existing fund names for overlap checks"
    ),
    portfolio_file: Optional[str] = typer.Option(
        None, "--portfolio-file", help="CSV/JSON/CAS portfolio file for look-through overlap checks"
    ),
    market_regime: str = typer.Option(
        "normal", "--market-regime", help="Market regime: normal, weak, strong"
    ),
):
    """
    Scan the curated fund universe and rank schemes by investability.

    Examples:
        python main.py fund-scan
        python main.py fund-scan --strategy thematic --theme defense
        python main.py fund-scan --vehicle etf
    """
    from funds import FundOutput, FundUniverse

    console.print("\n[bold cyan]Fund / ETF Scan[/bold cyan]\n")

    universe = FundUniverse()
    schemes = universe.filter(strategy_type=strategy, vehicle_type=vehicle, theme=theme)
    if not schemes:
        console.print("[red]No schemes matched the requested filters.[/red]")
        raise typer.Exit(1)

    scorer = _build_fund_scorer(refresh_holdings=refresh_holdings, market_regime=market_regime)
    current_portfolio = _resolve_portfolio_schemes(universe, portfolio)
    imported = _load_imported_portfolio(portfolio_file)
    analyses = [scorer.analyze(scheme, current_portfolio=current_portfolio) for scheme in schemes]
    if imported:
        from funds.portfolio_fit import PortfolioFitAnalyzer
        fit_analyzer = PortfolioFitAnalyzer()
        for analysis in analyses:
            fit = fit_analyzer.analyze_imported(analysis.scheme, imported, universe=universe)
            analysis.portfolio_fit = fit
            analysis.portfolio_fit_score = fit.fit_score // 10
    analyses.sort(key=lambda a: a.overall_score, reverse=True)

    FundOutput().display_scan_results(analyses, top_n=top)
    console.print(f"\n[dim]Scored {len(analyses)} schemes[/dim]")


@app.command()
def fund_analyze(
    scheme: str = typer.Argument(..., help="Scheme name or identifier"),
    refresh_holdings: bool = typer.Option(
        False, "--refresh-holdings", help="Force refresh underlying stock fundamentals"
    ),
    portfolio: Optional[str] = typer.Option(
        None, "--portfolio", help="Comma-separated existing fund names for overlap checks"
    ),
    portfolio_file: Optional[str] = typer.Option(
        None, "--portfolio-file", help="CSV/JSON/CAS portfolio file for look-through overlap checks"
    ),
    market_regime: str = typer.Option(
        "normal", "--market-regime", help="Market regime: normal, weak, strong"
    ),
):
    """
    Deep analysis of a mutual fund or ETF.

    Examples:
        python main.py fund-analyze "Parag Parikh Flexi Cap Fund"
        python main.py fund-analyze "HDFC Defence Fund" --portfolio "Parag Parikh Flexi Cap Fund"
    """
    from funds import FundOutput, FundUniverse

    universe = FundUniverse()
    target = universe.find(scheme)
    if not target:
        console.print(f"[red]Could not find scheme: {scheme}[/red]")
        raise typer.Exit(1)

    scorer = _build_fund_scorer(refresh_holdings=refresh_holdings, market_regime=market_regime)
    current_portfolio = _resolve_portfolio_schemes(universe, portfolio)
    analysis = scorer.analyze(target, current_portfolio=current_portfolio)
    imported = _load_imported_portfolio(portfolio_file)
    if imported:
        from funds.portfolio_fit import PortfolioFitAnalyzer
        fit = PortfolioFitAnalyzer().analyze_imported(target, imported, universe=universe)
        analysis.portfolio_fit = fit
        analysis.portfolio_fit_score = fit.fit_score // 10
    FundOutput().display_scheme_analysis(analysis)


@app.command()
def fund_compare(
    schemes: str = typer.Argument(
        ..., help='Comma-separated scheme names or ids (e.g. "Parag Parikh Flexi Cap Fund,HDFC Defence Fund")'
    ),
    refresh_holdings: bool = typer.Option(
        False, "--refresh-holdings", help="Force refresh underlying stock fundamentals"
    ),
    market_regime: str = typer.Option(
        "normal", "--market-regime", help="Market regime: normal, weak, strong"
    ),
):
    """
    Compare multiple funds side-by-side.
    """
    from funds import FundOutput, FundScorer, FundUniverse
    from funds.scorer import LiveFundamentalScoreProvider, LiveTailwindProvider

    universe = FundUniverse()
    targets = []
    for raw in schemes.split(","):
        q = raw.strip()
        if not q:
            continue
        scheme = universe.find(q)
        if scheme:
            targets.append(scheme)

    if len(targets) < 2:
        console.print("[red]Need at least 2 valid schemes for comparison.[/red]")
        raise typer.Exit(1)

    scorer = FundScorer(
        fundamentals_provider=LiveFundamentalScoreProvider(force_refresh=refresh_holdings),
        tailwind_provider=LiveTailwindProvider(),
        market_regime=market_regime,
    )
    analyses = [scorer.analyze(target) for target in targets]
    FundOutput().display_comparison(analyses)


@app.command()
def theme_funds(
    theme: str = typer.Argument(..., help="Theme keyword like defense, infra, manufacturing"),
    top: int = typer.Option(8, "--top", "-n", help="Show top N matching thematic funds"),
    refresh_holdings: bool = typer.Option(
        False, "--refresh-holdings", help="Force refresh underlying stock fundamentals"
    ),
    market_regime: str = typer.Option(
        "normal", "--market-regime", help="Market regime: normal, weak, strong"
    ),
):
    """
    Show thematic funds aligned to a specific thesis.
    """
    from funds import FundOutput, FundScorer, FundUniverse
    from funds.scorer import LiveFundamentalScoreProvider, LiveTailwindProvider

    universe = FundUniverse()
    schemes = universe.filter(strategy_type="thematic", theme=theme)
    if not schemes:
        console.print(f"[red]No thematic funds matched theme: {theme}[/red]")
        raise typer.Exit(1)

    scorer = FundScorer(
        fundamentals_provider=LiveFundamentalScoreProvider(force_refresh=refresh_holdings),
        tailwind_provider=LiveTailwindProvider(),
        market_regime=market_regime,
    )
    analyses = [scorer.analyze(scheme) for scheme in schemes]
    analyses.sort(key=lambda a: a.overall_score, reverse=True)
    FundOutput().display_scan_results(analyses, top_n=top)


@app.command()
def fund_market_extract(
    output_dir: str = typer.Option(
        "data/funds_market",
        "--output-dir",
        help="Directory to write Groww/Zerodha mutual-fund universe files",
    ),
):
    """
    Extract the broader mutual-fund market universe from Groww and Zerodha.

    Outputs:
        - groww_funds.json
        - zerodha_funds.json
        - zerodha_mf_instruments.csv
        - fund_market_union.json
        - fund_market_union.csv
        - fund_market_both.json / .csv
        - fund_market_groww_only.json / .csv
        - fund_market_zerodha_only.json / .csv
        - fund_market_summary.json
    """
    from funds.market_universe import MarketFundUniverseExtractor

    target = Path(output_dir)
    console.print("\n[bold cyan]Extracting market mutual-fund universe[/bold cyan]\n")
    summary = MarketFundUniverseExtractor(output_dir=target).extract(write=True)
    console.print_json(data=summary)
    console.print(f"\n[green]Wrote outputs to[/green] {target}")


@app.command()
def fund_review_template(
    scheme: str = typer.Argument(..., help="Scheme name or identifier"),
    refresh_holdings: bool = typer.Option(
        False, "--refresh-holdings", help="Force refresh underlying stock fundamentals"
    ),
    market_regime: str = typer.Option(
        "normal", "--market-regime", help="Market regime: normal, weak, strong"
    ),
):
    """
    Build a structured review template for funds_research.json from the current analysis.
    """
    from funds import FundScorer, FundUniverse
    from funds.research import build_review_template
    from funds.scorer import LiveFundamentalScoreProvider, LiveTailwindProvider

    universe = FundUniverse()
    target = universe.find(scheme)
    if not target:
        console.print(f"[red]Could not find scheme: {scheme}[/red]")
        raise typer.Exit(1)

    scorer = FundScorer(
        fundamentals_provider=LiveFundamentalScoreProvider(force_refresh=refresh_holdings),
        tailwind_provider=LiveTailwindProvider(),
        market_regime=market_regime,
    )
    analysis = scorer.analyze(target)
    template = build_review_template(analysis)
    console.print_json(data=template)


@app.command()
def nifty_index_scan(
    top: int = typer.Option(10, "--top", "-n", help="Show top N indices"),
    family: Optional[str] = typer.Option(
        None, "--family", "-f", help="Filter by family: sectoral, thematic, factor"
    ),
    theme: Optional[str] = typer.Option(
        None, "--theme", "-t", help="Filter by index theme keyword"
    ),
    refresh_holdings: bool = typer.Option(
        False, "--refresh-holdings", help="Force refresh underlying stock fundamentals"
    ),
    market_regime: str = typer.Option(
        "normal", "--market-regime", help="Market regime: normal, weak, strong"
    ),
):
    """
    Scan curated Nifty indices using live proxy-fund holdings.

    Examples:
        python main.py nifty-index-scan
        python main.py nifty-index-scan --family thematic
        python main.py nifty-index-scan --theme defence --market-regime weak
    """
    from funds import NiftyIndexOutput

    console.print("\n[bold cyan]Nifty Index Scan[/bold cyan]\n")
    researcher = _build_nifty_index_researcher(
        refresh_holdings=refresh_holdings,
        market_regime=market_regime,
    )
    analyses = researcher.scan(family=family, theme=theme)
    if not analyses:
        console.print("[red]No Nifty indices matched the requested filters.[/red]")
        raise typer.Exit(1)
    NiftyIndexOutput().display_scan_results(analyses, top_n=top)
    console.print(f"\n[dim]Scored {len(analyses)} curated Nifty indices[/dim]")


@app.command()
def nifty_index_analyze(
    index: str = typer.Argument(..., help="Nifty index name or identifier"),
    refresh_holdings: bool = typer.Option(
        False, "--refresh-holdings", help="Force refresh underlying stock fundamentals"
    ),
    market_regime: str = typer.Option(
        "normal", "--market-regime", help="Market regime: normal, weak, strong"
    ),
):
    """
    Deep research on a curated Nifty index using a live proxy basket.

    Examples:
        python main.py nifty-index-analyze "Nifty India Defence"
        python main.py nifty-index-analyze "Nifty200 Value 30" --market-regime weak
    """
    from funds import NiftyIndexOutput

    researcher = _build_nifty_index_researcher(
        refresh_holdings=refresh_holdings,
        market_regime=market_regime,
    )
    try:
        analysis = researcher.analyze(index)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    NiftyIndexOutput().display_analysis(analysis)


@app.command()
def factor_scan(
    top: int = typer.Option(20, "--top", "-n", help="Show top N stocks"),
    sector: Optional[str] = typer.Option(None, "--sector", "-s", help="Filter by sector"),
    factor: Optional[str] = typer.Option(None, "--factor", "-f",
        help="Sort by: momentum, value, quality, growth, low_vol, composite"),
    stocks: Optional[str] = typer.Option(None, "--stocks", help="Comma-separated symbols"),
):
    """Multi-factor scoring scan (momentum, value, quality, growth, volatility)."""
    from fundamentals.factor_model import FactorModel
    from fundamentals.scorer import ProfileBuilder
    from data.fetcher import StockDataFetcher

    if stocks:
        symbols = [s.strip().upper() for s in stocks.split(",")]
    else:
        from config import get_nifty100_symbols
        symbols = get_nifty100_symbols()

    if not symbols:
        console.print("[red]No symbols.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Multi-Factor Scan[/bold cyan] ({len(symbols)} stocks)\n")

    fetcher = StockDataFetcher()
    builder = ProfileBuilder()
    model = FactorModel()

    stock_data = {}
    with console.status("[bold green]Fetching data & building profiles...[/bold green]"):
        for sym in symbols:
            try:
                df = fetcher.fetch_stock_data(sym, "daily")
                if df is None or len(df) < 60:
                    continue
                profile = builder.build(sym)
                if profile and profile.data_quality != "MISSING":
                    stock_data[sym] = (df, profile)
            except Exception:
                continue

    if not stock_data:
        console.print("[red]No valid data to score.[/red]")
        raise typer.Exit(1)

    results = model.score_universe(stock_data)

    # Filter by sector
    if sector:
        results = [r for r in results if sector.lower() in r.sector.lower()]

    # Sort by specific factor
    sort_key = factor or 'composite'
    sort_map = {
        'momentum': 'momentum_score', 'value': 'value_score',
        'quality': 'quality_score', 'growth': 'growth_score',
        'low_vol': 'low_vol_score', 'composite': 'composite_score',
    }
    attr = sort_map.get(sort_key, 'composite_score')
    results.sort(key=lambda r: getattr(r, attr), reverse=True)

    # Display
    from rich.table import Table
    table = Table(title=f"Factor Scores (sorted by {sort_key})", show_header=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Symbol", style="bold")
    table.add_column("Sector", style="dim")
    table.add_column("Mom", justify="right")
    table.add_column("Val", justify="right")
    table.add_column("Qual", justify="right")
    table.add_column("Grow", justify="right")
    table.add_column("LowV", justify="right")
    table.add_column("Composite", justify="right", style="bold cyan")

    for i, r in enumerate(results[:top], 1):
        table.add_row(
            str(i), r.symbol, r.sector[:12],
            f"{r.momentum_score:.0f}", f"{r.value_score:.0f}",
            f"{r.quality_score:.0f}", f"{r.growth_score:.0f}",
            f"{r.low_vol_score:.0f}", f"{r.composite_score:.0f}",
        )
    console.print(table)


@app.command()
def pipe_scan(
    strategy: str = typer.Argument("swing_breakout", help="Pipe: swing_breakout, momentum, narrow_range"),
    top: int = typer.Option(20, "--top", "-n", help="Max results"),
    stocks: Optional[str] = typer.Option(None, "--stocks", "-s", help="Comma-separated symbols"),
    all_stocks: bool = typer.Option(False, "--all", help="Use Nifty 500 instead of 100"),
):
    """Run a piped scanner with chained filters (funnel report)."""
    from signals.piped_scanner import PIPE_REGISTRY
    from data.fetcher import StockDataFetcher

    if strategy not in PIPE_REGISTRY:
        console.print(f"[red]Unknown pipe: {strategy}. Available: {', '.join(PIPE_REGISTRY.keys())}[/red]")
        raise typer.Exit(1)

    from config import get_nifty100_symbols, get_nifty500_symbols

    if stocks:
        symbols = [s.strip().upper() for s in stocks.split(",")]
    elif all_stocks:
        symbols = get_nifty500_symbols()
    else:
        symbols = get_nifty100_symbols()

    if not symbols:
        console.print("[red]No symbols to scan.[/red]")
        raise typer.Exit(1)

    pipe = PIPE_REGISTRY[strategy]()
    console.print(f"\n[bold cyan]Piped Scanner: {pipe.name}[/bold cyan]")
    console.print(f"Universe: {len(symbols)} stocks\n")

    fetcher = StockDataFetcher()
    with console.status("[bold green]Running piped scan...[/bold green]"):
        report = pipe.run(symbols, fetcher)

    # Display funnel report
    from rich.table import Table

    funnel = Table(title="Filter Funnel", show_header=True)
    funnel.add_column("Stage", style="cyan")
    funnel.add_column("In", justify="right")
    funnel.add_column("Out", justify="right")
    funnel.add_column("Eliminated", justify="right", style="red")

    for stage in report.stages:
        funnel.add_row(
            stage.name,
            str(stage.input_count),
            str(stage.output_count),
            str(stage.input_count - stage.output_count),
        )
    console.print(funnel)

    # Display survivors
    if report.final_survivors:
        results_table = Table(title=f"\nSurvivors ({len(report.final_survivors)})", show_header=True)
        results_table.add_column("#", justify="right", style="dim")
        results_table.add_column("Symbol", style="bold green")
        results_table.add_column("Details")

        for i, sym in enumerate(report.final_survivors[:top], 1):
            detail_str = ", ".join(
                f"{k}: {v}" for k, v in report.details.get(sym, {}).items()
            )
            results_table.add_row(str(i), sym, detail_str)
        console.print(results_table)
    else:
        console.print("\n[yellow]No stocks passed all filters.[/yellow]")


@app.command()
def backtest(
    strategy: str = typer.Argument("swing", help="Strategy: swing, momentum, mean_reversion"),
    symbol: str = typer.Option("RELIANCE", "--symbol", "-s", help="Stock symbol"),
    days: int = typer.Option(1000, "--days", "-d", help="Days of historical data"),
):
    """Run walk-forward backtest for a trading strategy."""
    from backtest.bt_strategies import STRATEGY_REGISTRY, run_backtest
    from rich.table import Table

    if strategy not in STRATEGY_REGISTRY:
        console.print(f"[red]Unknown strategy: {strategy}. Available: {', '.join(STRATEGY_REGISTRY.keys())}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Walk-Forward Backtest[/bold cyan]")
    console.print(f"Strategy: {STRATEGY_REGISTRY[strategy]['name']} | Symbol: {symbol} | Days: {days}\n")

    with console.status("[bold green]Running walk-forward backtest...[/bold green]"):
        result = run_backtest(strategy, symbol, days)

    if isinstance(result, dict) and 'error' in result:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)

    # Summary table
    summary = Table(title="Performance Summary", show_header=True)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", justify="right")

    summary.add_row("Total Return", f"{result.total_return:+.1f}%")
    summary.add_row("Annualized Return", f"{result.annualized_return:+.1f}%")
    summary.add_row("Sharpe Ratio", f"{result.sharpe_ratio:.2f}")
    summary.add_row("Max Drawdown", f"{result.max_drawdown:.1f}%")
    summary.add_row("Win Rate", f"{result.win_rate:.1f}%")
    summary.add_row("Profit Factor", f"{result.profit_factor:.2f}")
    summary.add_row("Total Trades", str(result.total_trades))
    console.print(summary)

    # Robustness table
    robust = Table(title="\nRobustness Metrics", show_header=True)
    robust.add_column("Metric", style="cyan")
    robust.add_column("Value", justify="right")

    robust.add_row("Efficiency Ratio", f"{result.avg_efficiency_ratio:.2f}")
    robust.add_row("Param Stability", f"{result.param_stability:.0f}%")
    robust.add_row("OOS Degradation", f"{result.degradation_pct:.0f}%")
    robust.add_row("Robustness Score", f"{result.robustness_score}/100")
    color = "green" if result.is_robust else "red"
    robust.add_row("Is Robust", f"[{color}]{'YES' if result.is_robust else 'NO'}[/{color}]")
    console.print(robust)

    # Per-window table
    if result.windows:
        win_table = Table(title="\nPer-Window Results", show_header=True)
        win_table.add_column("#", justify="right", style="dim")
        win_table.add_column("IS Return", justify="right")
        win_table.add_column("OOS Return", justify="right")
        win_table.add_column("Efficiency", justify="right")
        win_table.add_column("Trades", justify="right")

        for w in result.windows:
            oos_color = "green" if w.out_sample_return > 0 else "red"
            win_table.add_row(
                str(w.window_id),
                f"{w.in_sample_return:+.1f}%",
                f"[{oos_color}]{w.out_sample_return:+.1f}%[/{oos_color}]",
                f"{w.efficiency_ratio:.2f}",
                str(w.out_sample_trades),
            )
        console.print(win_table)

    if result.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for w in result.warnings:
            console.print(f"  [yellow]• {w}[/yellow]")


@app.command()
def portfolio_risk(
    stocks: str = typer.Option(
        "RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        "--stocks", "-s",
        help="Comma-separated symbols (simulated portfolio)"
    ),
    capital: float = typer.Option(500000, "--capital", "-c", help="Total capital"),
):
    """Portfolio risk analysis: VaR, CVaR, correlations, stress tests."""
    from data.fetcher import StockDataFetcher
    from risk.portfolio_risk import PortfolioRiskCalculator
    from rich.table import Table

    symbols = [s.strip().upper() for s in stocks.split(",")]
    console.print(f"\n[bold cyan]Portfolio Risk Analysis[/bold cyan] ({len(symbols)} positions)\n")

    fetcher = StockDataFetcher()
    per_stock_value = capital / len(symbols)

    positions = {}
    returns_data = {}

    with console.status("[bold green]Fetching price data...[/bold green]"):
        from config import get_nifty500_stocks
        all_stocks_info = get_nifty500_stocks()
        sector_map = {s['symbol']: s.get('sector', 'Unknown') for s in all_stocks_info}

        for sym in symbols:
            try:
                df = fetcher.fetch_stock_data(sym, "daily")
                if df is None or len(df) < 60:
                    continue
                ret = df['close'].pct_change().dropna()
                returns_data[sym] = ret
                positions[sym] = {
                    'value': per_stock_value,
                    'sector': sector_map.get(sym, 'Unknown'),
                }
            except Exception:
                continue

    if not positions:
        console.print("[red]No valid data.[/red]")
        raise typer.Exit(1)

    calc = PortfolioRiskCalculator()
    report = calc.full_report(positions, returns_data)

    # --- VaR Summary ---
    var_table = Table(title="Value at Risk (95% confidence, 1-day)", show_header=True)
    var_table.add_column("Metric", style="cyan")
    var_table.add_column("Undiversified", justify="right")
    var_table.add_column("Diversified", justify="right", style="green")

    var_table.add_row("VaR %", f"{report.var.var_pct}%", f"{report.diversified_var.var_pct}%")
    var_table.add_row(
        "VaR Amount",
        f"₹{report.var.var_amount:,.0f}",
        f"₹{report.diversified_var.var_amount:,.0f}",
    )
    var_table.add_row("CVaR %", f"{report.var.cvar_pct}%", f"{report.diversified_var.cvar_pct}%")
    var_table.add_row(
        "CVaR Amount",
        f"₹{report.var.cvar_amount:,.0f}",
        f"₹{report.diversified_var.cvar_amount:,.0f}",
    )
    div_benefit = report.var.var_amount - report.diversified_var.var_amount
    var_table.add_row("Diversification Benefit", "", f"₹{div_benefit:,.0f}")
    console.print(var_table)

    # --- Individual VaR ---
    if report.individual_var:
        ind_table = Table(title="\nIndividual Position VaR", show_header=True)
        ind_table.add_column("Symbol", style="bold")
        ind_table.add_column("Value", justify="right")
        ind_table.add_column("VaR %", justify="right")
        ind_table.add_column("VaR ₹", justify="right", style="red")

        for sym, v in sorted(report.individual_var.items(), key=lambda x: x[1].var_pct, reverse=True):
            ind_table.add_row(
                sym,
                f"₹{positions[sym]['value']:,.0f}",
                f"{v.var_pct}%",
                f"₹{v.var_amount:,.0f}",
            )
        console.print(ind_table)

    # --- Correlation ---
    if report.correlation.high_pairs:
        corr_table = Table(title="\nHigh Correlation Pairs (>0.7)", show_header=True)
        corr_table.add_column("Pair", style="yellow")
        corr_table.add_column("Correlation", justify="right")
        for a, b, c in report.correlation.high_pairs:
            corr_table.add_row(f"{a} — {b}", f"{c:.3f}")
        console.print(corr_table)
    console.print(f"\n[dim]Average pairwise correlation: {report.correlation.avg_correlation:.3f}[/dim]")

    # --- Stress Tests ---
    stress_table = Table(title="\nStress Test Scenarios", show_header=True)
    stress_table.add_column("Scenario", style="cyan")
    stress_table.add_column("Portfolio Loss %", justify="right", style="red")
    stress_table.add_column("Portfolio Loss ₹", justify="right", style="red")

    for st in report.stress_tests:
        stress_table.add_row(
            st.scenario, f"{st.portfolio_loss_pct}%", f"₹{st.portfolio_loss_amount:,.0f}"
        )
    console.print(stress_table)

    # --- Warnings ---
    if report.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for w in report.warnings:
            console.print(f"  [yellow]• {w}[/yellow]")


# =============================================================================
# RRG — Relative Rotation Graph
# =============================================================================

@app.command()
def rrg(
    benchmark: str = typer.Option("^NSEI", "--benchmark", "-b", help="Benchmark index symbol"),
    top: int = typer.Option(15, "--top", "-n", help="Show top N sectors/stocks"),
):
    """Relative Rotation Graph — sector rotation quadrants (Leading/Weakening/Lagging/Improving)."""
    from rich.table import Table
    from data.fetcher import StockDataFetcher
    from indicators.rrg import RRGCalculator
    from config import get_nifty100_symbols

    console.print("\n[bold cyan]Relative Rotation Graph[/bold cyan]\n")

    fetcher = StockDataFetcher()
    rrg_calc = RRGCalculator()

    with console.status("Fetching benchmark data..."):
        bench_df = fetcher.fetch_stock_data(benchmark, 'daily')
        if bench_df is None or len(bench_df) < 100:
            console.print("[red]Could not fetch benchmark data[/red]")
            raise typer.Exit(1)

    symbols = get_nifty100_symbols()[:top * 3]
    stock_dfs = {}
    with console.status(f"Fetching data for {len(symbols)} stocks..."):
        for sym in symbols:
            df = fetcher.fetch_stock_data(sym, 'daily')
            if df is not None and len(df) >= 100:
                stock_dfs[sym] = df

    if len(stock_dfs) < 3:
        console.print("[red]Not enough data[/red]")
        raise typer.Exit(1)

    results = rrg_calc.calculate_universe(stock_dfs, bench_df)

    quadrant_colors = {
        'Leading': 'green', 'Weakening': 'yellow',
        'Lagging': 'red', 'Improving': 'cyan',
    }

    t = Table(title="RRG Quadrant Analysis", show_header=True)
    t.add_column("#", style="dim")
    t.add_column("Symbol", style="bold")
    t.add_column("Quadrant")
    t.add_column("RS-Ratio", justify="right")
    t.add_column("RS-Momentum", justify="right")

    for i, r in enumerate(results[:top], 1):
        color = quadrant_colors.get(r.quadrant, 'white')
        t.add_row(
            str(i), r.symbol,
            f"[{color}]{r.quadrant}[/{color}]",
            f"{r.rs_ratio:.2f}", f"{r.rs_momentum:.2f}",
        )
    console.print(t)

    # Summary by quadrant
    for q in ['Leading', 'Improving', 'Weakening', 'Lagging']:
        stocks_in_q = [r.symbol for r in results if r.quadrant == q]
        if stocks_in_q:
            color = quadrant_colors[q]
            console.print(f"  [{color}]{q}[/{color}]: {', '.join(stocks_in_q[:8])}")


# =============================================================================
# Insiders — Bulk Deal & Insider Tracker
# =============================================================================

@app.command()
def insiders(
    symbol: str = typer.Argument(..., help="Stock symbol to check"),
):
    """Track insider/promoter buying patterns and institutional accumulation."""
    from data.insider_tracker import InsiderTracker
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder

    console.print(f"\n[bold cyan]Insider/Smart Money Tracker — {symbol.upper()}[/bold cyan]\n")

    fetcher = ScreenerFetcher()
    raw = fetcher.fetch_stock(symbol.upper())
    if not raw:
        console.print(f"[red]Could not fetch data for {symbol}[/red]")
        raise typer.Exit(1)

    builder = ProfileBuilder()
    profile = builder.build(raw)
    tracker = InsiderTracker()
    signals = tracker.analyze(profile, raw)
    composite = tracker.get_composite_score(signals)

    if composite > 30:
        color = 'green'
    elif composite < -30:
        color = 'red'
    else:
        color = 'yellow'
    console.print(f"  Composite Score: [{color}]{composite:+d}[/{color}] (-100 to +100)\n")

    if signals:
        for sig in signals:
            s_color = 'green' if sig.score > 0 else 'red' if sig.score < 0 else 'dim'
            console.print(f"  [{s_color}]{sig.signal_type}[/{s_color}] ({sig.strength})")
            console.print(f"    Score: {sig.score:+d}")
            for k, v in sig.details.items():
                console.print(f"    {k}: {v}")
            console.print()
    else:
        console.print("  [dim]No insider signals detected[/dim]")

    # Ownership snapshot
    console.print(f"  [bold]Ownership Snapshot:[/bold]")
    console.print(f"    Promoter: {profile.promoter_holding:.1f}% (change: {profile.promoter_holding_change_1y:+.1f}%)")
    console.print(f"    FII: {profile.fii_holding:.1f}% (change: {profile.fii_holding_change_1y:+.1f}%)")
    console.print(f"    DII: {profile.dii_holding:.1f}%")
    if profile.promoter_pledge > 0:
        console.print(f"    Pledge: {profile.promoter_pledge:.1f}%")


# =============================================================================
# Scoring Models (Piotroski, Altman Z, Beneish M)
# =============================================================================

@app.command()
def score(
    symbol: str = typer.Argument(..., help="Stock symbol to score"),
    model: str = typer.Option("all", "--model", "-m", help="Scoring model: piotroski, altman, beneish, or all"),
):
    """Run financial scoring models on a stock (Piotroski F-Score, Altman Z, Beneish M)."""
    from rich.table import Table
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder

    console.print(f"\n[bold cyan]Financial Scoring — {symbol.upper()}[/bold cyan]\n")
    fetcher = ScreenerFetcher()
    raw = fetcher.fetch_stock(symbol.upper())
    if not raw:
        console.print(f"[red]Could not fetch data for {symbol}[/red]")
        raise typer.Exit(1)

    builder = ProfileBuilder()
    profile = builder.build(raw)

    models_to_run = ['piotroski', 'altman', 'beneish'] if model == 'all' else [model]

    for m in models_to_run:
        if m == 'piotroski':
            from fundamentals.scores.piotroski import PiotroskiFScore
            result = PiotroskiFScore().score(profile, raw)
            zone_color = {'STRONG': 'green', 'MODERATE': 'yellow', 'WEAK': 'red'}.get(result.zone, 'white')
            console.print(f"\n[bold]Piotroski F-Score: [{zone_color}]{result.f_score}/9 ({result.zone})[/{zone_color}][/bold]")
            t = Table(show_header=True)
            t.add_column("Criterion", style="cyan")
            t.add_column("Pass", justify="center")
            for k, v in result.criteria.items():
                t.add_row(k, "[green]YES[/green]" if v else "[red]NO[/red]")
            console.print(t)

        elif m == 'altman':
            from fundamentals.scores.altman import AltmanZScore
            result = AltmanZScore().score(profile, raw)
            if not result.is_applicable:
                console.print("\n[dim]Altman Z-Score: Not applicable for banking/finance[/dim]")
            else:
                zone_color = {'SAFE': 'green', 'GREY': 'yellow', 'DISTRESS': 'red'}.get(result.zone, 'white')
                console.print(f"\n[bold]Altman Z-Score: [{zone_color}]{result.z_score:.2f} ({result.zone})[/{zone_color}][/bold]")
                for k, v in result.components.items():
                    console.print(f"  {k}: {v:.4f}")

        elif m == 'beneish':
            from fundamentals.scores.beneish import BeneishMScore
            result = BeneishMScore().score(profile, raw)
            flag_color = 'red' if result.is_manipulator else 'green'
            label = 'LIKELY MANIPULATOR' if result.is_manipulator else 'UNLIKELY MANIPULATOR'
            console.print(f"\n[bold]Beneish M-Score: [{flag_color}]{result.m_score:.2f} ({label})[/{flag_color}][/bold]")
            console.print(f"  Confidence: {result.confidence}")

    for d in result.details:
        console.print(f"  [dim]{d}[/dim]")


# =============================================================================
# Valuation Models (DCF, DDM, Peer Relative, Monte Carlo)
# =============================================================================

@app.command()
def valuate(
    symbol: str = typer.Argument(..., help="Stock symbol to valuate"),
    model: str = typer.Option("all", "--model", "-m", help="Valuation model: dcf, ddm, peer, monte_carlo, or all"),
):
    """Run valuation models on a stock (DCF, DDM, Peer Relative, Monte Carlo)."""
    from rich.table import Table
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder

    console.print(f"\n[bold cyan]Valuation Analysis — {symbol.upper()}[/bold cyan]\n")
    fetcher = ScreenerFetcher()
    raw = fetcher.fetch_stock(symbol.upper())
    if not raw:
        console.print(f"[red]Could not fetch data for {symbol}[/red]")
        raise typer.Exit(1)

    builder = ProfileBuilder()
    profile = builder.build(raw)

    models_to_run = ['dcf', 'ddm', 'peer', 'monte_carlo'] if model == 'all' else [model]

    t = Table(title="Valuation Summary", show_header=True)
    t.add_column("Model", style="cyan")
    t.add_column("Fair Value", justify="right")
    t.add_column("Current", justify="right")
    t.add_column("Margin of Safety", justify="right")
    t.add_column("Signal", justify="center")
    t.add_column("Confidence")

    for m in models_to_run:
        try:
            if m == 'dcf':
                from fundamentals.valuation.dcf import DCFValuation
                result = DCFValuation().value(profile, raw)
            elif m == 'ddm':
                from fundamentals.valuation.ddm import DDMValuation
                result = DDMValuation().value(profile, raw)
            elif m == 'peer':
                from fundamentals.valuation.peer_relative import PeerRelativeValuation
                result = PeerRelativeValuation().value(profile, raw)
            elif m == 'monte_carlo':
                from fundamentals.valuation.monte_carlo import MonteCarloValuation
                result = MonteCarloValuation().value(profile, raw)
            else:
                continue

            signal_color = {'UNDERVALUED': 'green', 'FAIR': 'yellow', 'OVERVALUED': 'red', 'NOT_APPLICABLE': 'dim'}.get(result.signal, 'white')
            t.add_row(
                result.model.upper(),
                f"₹{result.fair_value:,.0f}" if result.fair_value > 0 else "N/A",
                f"₹{result.current_price:,.0f}",
                f"{result.margin_of_safety_pct:+.1f}%",
                f"[{signal_color}]{result.signal}[/{signal_color}]",
                result.confidence,
            )
        except Exception as e:
            t.add_row(m.upper(), "Error", "", "", str(e)[:30], "")

    console.print(t)


# =============================================================================
# Multibagger Scanner
# =============================================================================

@app.command()
def multibagger_scan(
    top: int = typer.Option(10, "--top", "-n", help="Show top N candidates"),
    sector: Optional[str] = typer.Option(None, "--sector", "-s", help="Filter by sector"),
):
    """Scan for potential multibagger candidates using multi-signal analysis."""
    from rich.table import Table
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder
    from fundamentals.screens.multibagger import MultibaggerScreen
    from config import get_nifty500_symbols

    console.print("\n[bold cyan]Multibagger Scanner[/bold cyan]\n")
    symbols = get_nifty500_symbols()
    if not symbols:
        console.print("[red]No symbols found in stocks.json[/red]")
        raise typer.Exit(1)

    fetcher = ScreenerFetcher()
    builder = ProfileBuilder()
    screen = MultibaggerScreen()
    results = []

    with console.status(f"Scanning {len(symbols)} stocks..."):
        for i, sym in enumerate(symbols):
            try:
                raw = fetcher.fetch_stock(sym)
                if not raw or raw.data_quality == 'MISSING':
                    continue
                profile = builder.build(raw)
                if sector and profile.sector.lower() != sector.lower():
                    continue
                sr = screen.screen(profile, raw)
                if sr.score > 0:
                    results.append(sr)
            except Exception:
                continue

    results.sort(key=lambda x: x.score, reverse=True)
    results = results[:top]

    if not results:
        console.print("[yellow]No multibagger candidates found[/yellow]")
        raise typer.Exit()

    t = Table(title=f"Top {len(results)} Multibagger Candidates", show_header=True)
    t.add_column("#", style="dim")
    t.add_column("Symbol", style="bold")
    t.add_column("Sector")
    t.add_column("Score", justify="right", style="cyan")
    t.add_column("Pass", justify="center")
    t.add_column("Key Strengths")

    for i, r in enumerate(results, 1):
        pass_str = "[green]YES[/green]" if r.passes else "[red]NO[/red]"
        strengths = " | ".join(r.criteria_met[:3]) if r.criteria_met else ""
        t.add_row(str(i), r.symbol, r.sector, str(r.score), pass_str, strengths)

    console.print(t)


# =============================================================================
# Theme & Supply Chain Commands
# =============================================================================

@app.command()
def themes(
    theme: Optional[str] = typer.Argument(None, help="Specific theme to analyze"),
):
    """List investment themes and their beneficiary stocks."""
    from rich.table import Table
    from tailwinds.supply_chain import SupplyChainMapper, THEME_BENEFICIARIES

    mapper = SupplyChainMapper()

    if theme:
        if theme not in THEME_BENEFICIARIES:
            console.print(f"[red]Unknown theme: {theme}[/red]")
            console.print(f"Available: {', '.join(THEME_BENEFICIARIES.keys())}")
            raise typer.Exit(1)

        info = THEME_BENEFICIARIES[theme]
        console.print(f"\n[bold cyan]{info['description']}[/bold cyan]\n")
        for role in ['direct', 'supply_chain', 'raw_material', 'infra']:
            stocks = info.get(role, [])
            if stocks:
                console.print(f"  [bold]{role.replace('_', ' ').title()}:[/bold] {', '.join(stocks)}")
    else:
        t = Table(title="Investment Themes", show_header=True)
        t.add_column("Theme", style="cyan")
        t.add_column("Description")
        t.add_column("Stocks", justify="right")
        for name, info in THEME_BENEFICIARIES.items():
            total = sum(len(info.get(r, [])) for r in ['direct', 'supply_chain', 'raw_material', 'infra'])
            t.add_row(name, info['description'], str(total))
        console.print(t)


@app.command()
def mood():
    """Show the Market Mood Index (composite sentiment indicator)."""
    from indicators.market_mood import MarketMoodIndex

    console.print("\n[bold cyan]Market Mood Index[/bold cyan]\n")
    with console.status("Calculating mood..."):
        mmi = MarketMoodIndex()
        result = mmi.calculate()

    mood_colors = {
        'EXTREME_FEAR': 'red', 'FEAR': 'red',
        'NEUTRAL': 'yellow',
        'GREED': 'green', 'EXTREME_GREED': 'green',
    }
    color = mood_colors.get(result.mood_label, 'white')
    console.print(f"  Mood Score: [{color}]{result.mood_score}/100[/{color}]")
    console.print(f"  Label: [{color}]{result.mood_label}[/{color}]")
    console.print(f"  Interpretation: {result.interpretation}\n")

    for comp, val in result.components.items():
        console.print(f"  {comp}: {val}/100")


@app.command()
def inflection(
    symbol: str = typer.Argument(..., help="Stock symbol to analyze"),
):
    """Detect fundamental inflection points for a stock."""
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder
    from fundamentals.inflection import InflectionDetector

    console.print(f"\n[bold cyan]Inflection Detection — {symbol.upper()}[/bold cyan]\n")

    fetcher = ScreenerFetcher()
    raw = fetcher.fetch_stock(symbol.upper())
    if not raw:
        console.print(f"[red]Could not fetch data for {symbol}[/red]")
        raise typer.Exit(1)

    builder = ProfileBuilder()
    profile = builder.build(raw)
    detector = InflectionDetector()
    result = detector.detect(profile, raw)

    stage_colors = {
        'NO_INFLECTION': 'dim', 'EARLY_INFLECTION': 'yellow',
        'CONFIRMED_INFLECTION': 'green', 'MATURE_INFLECTION': 'cyan',
    }
    color = stage_colors.get(result.stage, 'white')
    console.print(f"  Stage: [{color}]{result.stage}[/{color}]")
    console.print(f"  Score: {result.inflection_score}/100")

    if result.signals:
        console.print(f"\n  [bold]Detected Signals:[/bold]")
        for sig in result.signals:
            strength_color = {'STRONG': 'green', 'MODERATE': 'yellow', 'EARLY': 'dim'}.get(sig.strength, 'white')
            console.print(f"    [{strength_color}]{sig.signal_type}[/{strength_color}] ({sig.strength}) — Score: {sig.score}")
            for ev in sig.evidence:
                console.print(f"      {ev}")
    else:
        console.print("  [dim]No inflection signals detected[/dim]")


@app.command()
def smart_money(
    symbol: str = typer.Argument(..., help="Stock symbol to analyze"),
):
    """Track smart money (promoter/FII/DII) accumulation patterns."""
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder
    from data.smart_money import SmartMoneyTracker

    console.print(f"\n[bold cyan]Smart Money Analysis — {symbol.upper()}[/bold cyan]\n")

    fetcher = ScreenerFetcher()
    raw = fetcher.fetch_stock(symbol.upper())
    if not raw:
        console.print(f"[red]Could not fetch data for {symbol}[/red]")
        raise typer.Exit(1)

    builder = ProfileBuilder()
    profile = builder.build(raw)
    tracker = SmartMoneyTracker()
    result = tracker.analyze(profile, raw)

    signal_colors = {
        'STRONG_ACCUMULATION': 'green', 'ACCUMULATION': 'green',
        'NEUTRAL': 'yellow',
        'DISTRIBUTION': 'red', 'STRONG_DISTRIBUTION': 'red',
    }
    color = signal_colors.get(result.signal, 'white')
    console.print(f"  Signal: [{color}]{result.signal}[/{color}]")
    console.print(f"  Composite Score: {result.composite_score}")
    console.print(f"  Convergence: {'YES' if result.convergence else 'NO'}")

    if result.smart_money_signals:
        for sig in result.smart_money_signals:
            action_color = 'green' if sig.action == 'ACCUMULATING' else 'red' if sig.action == 'DISTRIBUTING' else 'dim'
            console.print(f"\n  [{action_color}]{sig.holder_type}: {sig.action}[/{action_color}]")
            console.print(f"    Velocity: {sig.velocity:+.2f}%/qtr | Acceleration: {sig.acceleration:+.2f}")
            console.print(f"    Trend: {sig.quarters_of_trend} quarters | Strength: {sig.strength}")


@app.command()
def catalysts(
    symbol: str = typer.Argument(..., help="Stock symbol to scan"),
):
    """Scan news for company-specific catalysts (orders, expansions, approvals)."""
    from rich.table import Table
    from data.catalyst_scanner import CatalystScanner

    console.print(f"\n[bold cyan]Catalyst Scanner — {symbol.upper()}[/bold cyan]\n")

    with console.status("Scanning news..."):
        scanner = CatalystScanner()
        result = scanner.scan(symbol.upper())

    signal_colors = {
        'STRONG_CATALYST': 'green', 'MODERATE_CATALYST': 'yellow',
        'WEAK_CATALYST': 'dim', 'NO_CATALYST': 'red',
    }
    color = signal_colors.get(result.signal, 'white')
    console.print(f"  Signal: [{color}]{result.signal}[/{color}]")
    console.print(f"  Catalyst Score: {result.catalyst_score}/100")
    if result.dominant_catalyst:
        console.print(f"  Dominant Type: {result.dominant_catalyst}")

    if result.catalysts:
        t = Table(show_header=True)
        t.add_column("Type", style="cyan")
        t.add_column("Headline")
        t.add_column("+/-", justify="center")
        for c in result.catalysts[:10]:
            sentiment = "[green]+[/green]" if c.is_positive else "[red]-[/red]"
            t.add_row(c.catalyst_type, c.headline[:80], sentiment)
        console.print(t)
    else:
        console.print("  [dim]No catalysts found in recent news[/dim]")


@app.command()
def rs_rank(
    top: int = typer.Option(20, "--top", "-n", help="Show top N stocks by RS rating"),
):
    """Rank stocks by O'Neil Relative Strength Rating (1-99)."""
    from rich.table import Table
    from data.fetcher import StockDataFetcher
    from indicators.rs_rating import RSRating
    from config import get_nifty100_symbols

    console.print("\n[bold cyan]O'Neil RS Rating Rankings[/bold cyan]\n")

    symbols = get_nifty100_symbols()
    if not symbols:
        console.print("[red]No symbols found[/red]")
        raise typer.Exit(1)

    fetcher = StockDataFetcher()
    rs = RSRating()
    stock_dfs = {}

    with console.status(f"Fetching data for {len(symbols)} stocks..."):
        for sym in symbols:
            df = fetcher.fetch_stock_data(sym, 'daily')
            if df is not None and len(df) >= 200:
                stock_dfs[sym] = df

    if len(stock_dfs) < 5:
        console.print("[red]Not enough data for ranking[/red]")
        raise typer.Exit(1)

    results = rs.rank_universe(stock_dfs)[:top]

    t = Table(title=f"Top {len(results)} by RS Rating", show_header=True)
    t.add_column("#", style="dim")
    t.add_column("Symbol", style="bold")
    t.add_column("RS Rating", justify="right", style="cyan")
    t.add_column("Interpretation")
    t.add_column("Raw Score", justify="right")

    for i, r in enumerate(results, 1):
        color = 'green' if r.rs_rating >= 80 else 'yellow' if r.rs_rating >= 60 else 'white'
        t.add_row(str(i), r.symbol, f"[{color}]{r.rs_rating}[/{color}]", r.interpretation, f"{r.raw_score:.1f}%")
    console.print(t)


# =============================================================================
# Deep Analysis (combines all new modules)
# =============================================================================

@app.command()
def deep_analyze(
    symbol: str = typer.Argument(..., help="Stock symbol for deep analysis"),
):
    """Deep analysis combining scoring, valuation, inflection, smart money, and catalysts."""
    from rich.table import Table
    from rich.panel import Panel
    from fundamentals.screener_fetcher import ScreenerFetcher
    from fundamentals.scorer import ProfileBuilder, FundamentalScorer

    console.print(f"\n[bold cyan]Deep Analysis — {symbol.upper()}[/bold cyan]\n")

    fetcher = ScreenerFetcher()
    raw = fetcher.fetch_stock(symbol.upper())
    if not raw:
        console.print(f"[red]Could not fetch data for {symbol}[/red]")
        raise typer.Exit(1)

    builder = ProfileBuilder()
    profile = builder.build(raw)
    scorer = FundamentalScorer()
    fs = scorer.score(profile)

    # Header
    console.print(f"  {profile.company_name} | {profile.sector} | Mkt Cap: ₹{profile.market_cap:,.0f} Cr")
    console.print(f"  Price: ₹{profile.current_price:,.0f} | PE: {profile.pe_ratio or 0:.1f} | ROE: {profile.roe or 0:.1f}% | ROCE: {profile.roce or 0:.1f}%")
    console.print(f"  Fundamental Score: {fs.total_score}/100 ({fs.grade})\n")

    # Scoring Models
    console.print("[bold]1. Financial Scoring Models[/bold]")
    try:
        from fundamentals.scores.piotroski import PiotroskiFScore
        p = PiotroskiFScore().score(profile, raw)
        zone_c = {'STRONG': 'green', 'MODERATE': 'yellow', 'WEAK': 'red'}.get(p.zone, 'white')
        console.print(f"   Piotroski F-Score: [{zone_c}]{p.f_score}/9 ({p.zone})[/{zone_c}]")
    except Exception:
        console.print("   Piotroski: [dim]unavailable[/dim]")

    try:
        from fundamentals.scores.altman import AltmanZScore
        a = AltmanZScore().score(profile, raw)
        if a.is_applicable:
            zone_c = {'SAFE': 'green', 'GREY': 'yellow', 'DISTRESS': 'red'}.get(a.zone, 'white')
            console.print(f"   Altman Z-Score: [{zone_c}]{a.z_score:.2f} ({a.zone})[/{zone_c}]")
        else:
            console.print("   Altman Z-Score: [dim]N/A (banking)[/dim]")
    except Exception:
        console.print("   Altman: [dim]unavailable[/dim]")

    try:
        from fundamentals.scores.beneish import BeneishMScore
        b = BeneishMScore().score(profile, raw)
        flag_c = 'red' if b.is_manipulator else 'green'
        label = 'FLAG' if b.is_manipulator else 'CLEAN'
        console.print(f"   Beneish M-Score: [{flag_c}]{b.m_score:.2f} ({label})[/{flag_c}] [dim]({b.confidence} confidence)[/dim]")
    except Exception:
        console.print("   Beneish: [dim]unavailable[/dim]")

    # Valuation
    console.print("\n[bold]2. Valuation Models[/bold]")
    val_table = Table(show_header=True, show_edge=False, pad_edge=False)
    val_table.add_column("Model", style="cyan")
    val_table.add_column("Fair Value", justify="right")
    val_table.add_column("MoS", justify="right")
    val_table.add_column("Signal")

    for vmodel_name, vmodel_cls_path in [
        ('DCF', 'fundamentals.valuation.dcf.DCFValuation'),
        ('DDM', 'fundamentals.valuation.ddm.DDMValuation'),
        ('Peer', 'fundamentals.valuation.peer_relative.PeerRelativeValuation'),
        ('Monte Carlo', 'fundamentals.valuation.monte_carlo.MonteCarloValuation'),
    ]:
        try:
            parts = vmodel_cls_path.rsplit('.', 1)
            mod = __import__(parts[0], fromlist=[parts[1]])
            cls = getattr(mod, parts[1])
            vr = cls().value(profile, raw)
            sc = {'UNDERVALUED': 'green', 'FAIR': 'yellow', 'OVERVALUED': 'red'}.get(vr.signal, 'dim')
            val_table.add_row(
                vmodel_name,
                f"₹{vr.fair_value:,.0f}" if vr.fair_value > 0 else "N/A",
                f"{vr.margin_of_safety_pct:+.1f}%",
                f"[{sc}]{vr.signal}[/{sc}]",
            )
        except Exception:
            val_table.add_row(vmodel_name, "—", "—", "[dim]error[/dim]")
    console.print(val_table)

    # Inflection
    console.print("\n[bold]3. Inflection Detection[/bold]")
    try:
        from fundamentals.inflection import InflectionDetector
        inf = InflectionDetector().detect(profile, raw)
        sc = {'CONFIRMED_INFLECTION': 'green', 'EARLY_INFLECTION': 'yellow', 'MATURE_INFLECTION': 'cyan'}.get(inf.stage, 'dim')
        console.print(f"   Stage: [{sc}]{inf.stage}[/{sc}] | Score: {inf.inflection_score}/100")
        for sig in inf.signals:
            console.print(f"   • {sig.signal_type} ({sig.strength})")
    except Exception:
        console.print("   [dim]unavailable[/dim]")

    # Smart Money
    console.print("\n[bold]4. Smart Money[/bold]")
    try:
        from data.smart_money import SmartMoneyTracker
        sm = SmartMoneyTracker().analyze(profile, raw)
        sc = {'STRONG_ACCUMULATION': 'green', 'ACCUMULATION': 'green', 'DISTRIBUTION': 'red', 'STRONG_DISTRIBUTION': 'red'}.get(sm.signal, 'yellow')
        console.print(f"   Signal: [{sc}]{sm.signal}[/{sc}] | Score: {sm.composite_score} | Convergence: {'YES' if sm.convergence else 'NO'}")
    except Exception:
        console.print("   [dim]unavailable[/dim]")

    # Catalysts
    console.print("\n[bold]5. Catalyst Scanner[/bold]")
    try:
        from data.catalyst_scanner import CatalystScanner
        cat = CatalystScanner().scan(symbol.upper(), profile.company_name)
        sc = {'STRONG_CATALYST': 'green', 'MODERATE_CATALYST': 'yellow'}.get(cat.signal, 'dim')
        console.print(f"   Signal: [{sc}]{cat.signal}[/{sc}] | Score: {cat.catalyst_score}/100")
        for c in cat.catalysts[:3]:
            console.print(f"   • [{c.catalyst_type}] {c.headline[:70]}")
    except Exception:
        console.print("   [dim]unavailable[/dim]")

    # Supply Chain / Theme exposure
    console.print("\n[bold]6. Theme Exposure[/bold]")
    try:
        from tailwinds.supply_chain import SupplyChainMapper
        scm = SupplyChainMapper().map_stock(symbol.upper())
        if scm.theme_count > 0:
            for te in scm.theme_exposures:
                console.print(f"   • {te['theme']} ({te['role']})")
        else:
            console.print("   [dim]No theme exposure found[/dim]")
    except Exception:
        console.print("   [dim]unavailable[/dim]")

    # Screens
    console.print("\n[bold]7. Screen Matches[/bold]")
    from fundamentals.screens import SCREENS
    matches = []
    for sname, scls in SCREENS.items():
        try:
            sr = scls().screen(profile) if sname != 'multibagger' else scls().screen(profile, raw)
            if sr.passes:
                matches.append(f"{sname} ({sr.score})")
        except Exception:
            continue
    if matches:
        console.print(f"   Passes: [green]{', '.join(matches)}[/green]")
    else:
        console.print("   [dim]No screens passed[/dim]")


@app.command()
def recommend(
    universe: str = typer.Option(
        "nifty_100", "--universe", "-u", help="Universe: nifty_100 or nifty_500"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force refresh all data"
    ),
):
    """
    Master investment recommendation — one multibagger, one hedge, one compounder.

    Orchestrates ALL modules: screens, scoring models, valuation,
    inflection detection, smart money, catalysts, and themes into
    a single unified recommendation with full investment thesis.

    Examples:
        python main.py recommend
        python main.py recommend --universe nifty_500
    """
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from core.investment_orchestrator import InvestmentOrchestrator

    orchestrator = InvestmentOrchestrator(universe=universe)
    result = orchestrator.recommend(force_refresh=refresh)

    # ── Market Context ──
    console.print()
    regime_color = {
        "STRONG_BULL": "bold green",
        "BULL": "green",
        "NEUTRAL": "yellow",
        "BEAR": "red",
        "STRONG_BEAR": "bold red",
        "CRASH": "bold red on white",
    }.get(result.regime, "white")

    console.print(Panel(
        f"[{regime_color}]{result.regime}[/{regime_color}]  |  "
        f"Position sizing: {result.regime_position_size}  |  "
        f"Should trade: {'YES' if result.regime_should_trade else 'NO'}\n"
        f"[dim]{result.regime_details.get('rationale', '')}[/dim]",
        title="[bold]MARKET REGIME[/bold]",
        border_style="cyan",
    ))

    if result.regime == "CRASH":
        console.print("[bold red]CRASH regime — stay 100% cash. Picks below are WATCHLIST only.[/bold red]\n")

    if result.errors:
        for err in result.errors:
            console.print(f"[yellow]Warning: {err}[/yellow]")

    console.print(
        f"[dim]Universe: {result.universe_size} stocks | "
        f"Fetched: {result.stocks_fetched}[/dim]\n"
    )

    # ── Render each pick ──
    picks = [
        ("MULTIBAGGER", result.multibagger, result.multibagger_alternates, "bold magenta"),
        ("HEDGE", result.hedge, result.hedge_alternates, "bold blue"),
        ("COMPOUNDER", result.compounder, result.compounder_alternates, "bold green"),
    ]

    for bucket_name, thesis, alternates, color in picks:
        if not thesis:
            console.print(Panel(
                "[dim]No qualifying candidate found[/dim]",
                title=f"[{color}]{bucket_name}[/{color}]",
                border_style="dim",
            ))
            continue

        _render_thesis(console, thesis, bucket_name, color, alternates)

    # ── Summary table ──
    console.print()
    summary = Table(title="Recommendation Summary", show_edge=True, border_style="cyan")
    summary.add_column("Bucket", style="bold")
    summary.add_column("Stock")
    summary.add_column("Price", justify="right")
    summary.add_column("Fair Value", justify="right")
    summary.add_column("MoS", justify="right")
    summary.add_column("Fund. Score", justify="right")
    summary.add_column("Conviction")

    for bucket_name, thesis, _, _ in picks:
        if thesis:
            mos_color = "green" if thesis.margin_of_safety > 0 else "red"
            conv_color = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}.get(thesis.conviction, "white")
            summary.add_row(
                bucket_name,
                f"{thesis.symbol}",
                f"₹{thesis.current_price:,.0f}",
                f"₹{thesis.fair_value:,.0f}" if thesis.fair_value else "—",
                f"[{mos_color}]{thesis.margin_of_safety:+.0f}%[/{mos_color}]" if thesis.fair_value else "—",
                f"{thesis.fundamental_score}/100",
                f"[{conv_color}]{thesis.conviction}[/{conv_color}]",
            )
        else:
            summary.add_row(bucket_name, "—", "—", "—", "—", "—", "—")

    console.print(summary)
    console.print(
        "\n[dim]Disclaimer: This is a quantitative screening tool, not investment advice. "
        "Always do your own research before investing.[/dim]\n"
    )


def _render_thesis(console, t, bucket_name, color, alternates):
    """Render a single StockThesis as a rich panel."""
    from rich.table import Table
    from rich.panel import Panel

    lines = []

    # Header
    lines.append(
        f"[bold]{t.company_name}[/bold] ({t.symbol})  |  "
        f"{t.sector}  |  Mkt Cap: ₹{t.market_cap:,.0f} Cr"
    )
    lines.append(
        f"Price: ₹{t.current_price:,.0f}  |  "
        f"PE: {t.pe_ratio or 0:.1f}  |  ROE: {t.roe or 0:.1f}%  |  ROCE: {t.roce or 0:.1f}%  |  "
        f"D/E: {t.debt_to_equity:.2f}"
    )
    lines.append("")

    # Thesis summary
    lines.append(f"[italic]{t.thesis_summary}[/italic]")
    lines.append("")

    # Screens passed
    if t.screens_passed:
        lines.append(f"Screens: [green]{', '.join(t.screens_passed)}[/green]")

    # Scoring models
    scoring_parts = []
    if t.piotroski is not None:
        pc = {"STRONG": "green", "MODERATE": "yellow", "WEAK": "red"}.get(t.piotroski_zone, "white")
        scoring_parts.append(f"Piotroski [{pc}]{t.piotroski}/9[/{pc}]")
    if t.altman_z is not None:
        ac = {"SAFE": "green", "GREY": "yellow", "DISTRESS": "red"}.get(t.altman_zone, "white")
        scoring_parts.append(f"Altman [{ac}]{t.altman_z:.2f}[/{ac}]")
    if t.beneish_m is not None:
        bc = "red" if t.beneish_flag else "green"
        label = "FLAG" if t.beneish_flag else "CLEAN"
        scoring_parts.append(f"Beneish [{bc}]{label}[/{bc}]")
    if scoring_parts:
        lines.append(f"Scores: {' | '.join(scoring_parts)}")

    # Valuation
    if t.valuation_models:
        val_parts = []
        for vm in t.valuation_models:
            sc = {"UNDERVALUED": "green", "FAIR": "yellow", "OVERVALUED": "red"}.get(vm["signal"], "dim")
            fv = f"₹{vm['fair_value']:,.0f}" if vm["fair_value"] > 0 else "N/A"
            val_parts.append(f"{vm['model']}: {fv} [{sc}]{vm['signal']}[/{sc}]")
        lines.append(f"Valuations: {' | '.join(val_parts)}")

    # Inflection
    if t.inflection_stage:
        ic = {"CONFIRMED_INFLECTION": "green", "EARLY_INFLECTION": "yellow"}.get(t.inflection_stage, "dim")
        lines.append(f"Inflection: [{ic}]{t.inflection_stage}[/{ic}] (score {t.inflection_score})")
        for sig in t.inflection_signals[:3]:
            lines.append(f"  - {sig}")

    # Smart money
    if t.smart_money_signal:
        sc = {"STRONG_ACCUMULATION": "green", "ACCUMULATION": "green",
              "DISTRIBUTION": "red", "STRONG_DISTRIBUTION": "red"}.get(t.smart_money_signal, "yellow")
        conv = " (converging)" if t.smart_money_convergence else ""
        lines.append(f"Smart Money: [{sc}]{t.smart_money_signal}[/{sc}]{conv}")

    # Catalysts
    if t.catalysts:
        cat_color = {"STRONG_CATALYST": "green", "MODERATE_CATALYST": "yellow"}.get(t.catalyst_signal, "dim")
        lines.append(f"Catalysts: [{cat_color}]{t.catalyst_signal}[/{cat_color}]")
        for c in t.catalysts[:2]:
            lines.append(f"  - {c}")

    # Themes
    if t.theme_exposures:
        lines.append(f"Themes: {', '.join(t.theme_exposures[:3])}")

    lines.append("")

    # Bull / Bear case
    if t.bull_case:
        lines.append("[green]Bull Case:[/green]")
        for b in t.bull_case:
            lines.append(f"  + {b}")

    if t.bear_case:
        lines.append("[red]Bear Case:[/red]")
        for b in t.bear_case:
            lines.append(f"  - {b}")

    # Conviction
    conv_color = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}.get(t.conviction, "white")
    lines.append(f"\nConviction: [{conv_color}]{t.conviction}[/{conv_color}]  |  "
                 f"Fundamental: {t.fundamental_score}/100 ({t.fundamental_grade})  |  "
                 f"Composite: {t.composite_score}/100 ({t.composite_grade})")

    # Alternates
    if alternates:
        lines.append(f"[dim]Alternates: {', '.join(alternates)}[/dim]")

    console.print(Panel(
        "\n".join(lines),
        title=f"[{color}]{bucket_name}[/{color}]",
        border_style=color.replace("bold ", ""),
        padding=(1, 2),
    ))


def main():
    """Main entry point."""
    console.print("\n[bold]Nifty Signals[/bold] - Indian Stock Trading Signals\n", style="cyan")
    app()


if __name__ == "__main__":
    main()
