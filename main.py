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


def main():
    """Main entry point."""
    console.print("\n[bold]Nifty Signals[/bold] - Indian Stock Trading Signals\n", style="cyan")
    app()


if __name__ == "__main__":
    main()
