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


def _build_fund_scorer(refresh_holdings: bool = False):
    from funds import FundScorer
    from funds.scorer import LiveFundamentalScoreProvider, LiveTailwindProvider

    return FundScorer(
        fundamentals_provider=LiveFundamentalScoreProvider(force_refresh=refresh_holdings),
        tailwind_provider=LiveTailwindProvider(),
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

    scorer = _build_fund_scorer(refresh_holdings=refresh_holdings)
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

    scorer = _build_fund_scorer(refresh_holdings=refresh_holdings)
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
    )
    analysis = scorer.analyze(target)
    template = build_review_template(analysis)
    console.print_json(data=template)


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


def main():
    """Main entry point."""
    console.print("\n[bold]Nifty Signals[/bold] - Indian Stock Trading Signals\n", style="cyan")
    app()


if __name__ == "__main__":
    main()
