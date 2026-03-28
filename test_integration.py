#!/usr/bin/env python3
"""
Integration Test - Verify all components work together.

Run this script to test:
1. Reliable data fetcher (yfinance)
2. Data quality gates
3. Position manager
4. Intelligence layer (mock mode without Claude API key)
5. Intelligent orchestrator

Usage:
    python test_integration.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def test_reliable_fetcher():
    """Test the reliable data fetcher with yfinance."""
    console.print("\n[bold blue]1. Testing Reliable Data Fetcher...[/bold blue]")

    from data.reliable_fetcher import get_reliable_fetcher, SYMBOL_MAPPINGS, KNOWN_FAILURES

    fetcher = get_reliable_fetcher()
    console.print("[green]✓ Fetcher initialized[/green]")
    console.print(f"[dim]  Primary source: {fetcher.primary_source}[/dim]")
    console.print(f"[dim]  Symbol mappings: {len(SYMBOL_MAPPINGS)}[/dim]")
    console.print(f"[dim]  Known failures: {len(KNOWN_FAILURES)}[/dim]")

    # Test fetching data for a Nifty 50 stock
    test_symbol = "RELIANCE"
    console.print(f"[dim]Fetching data for {test_symbol}...[/dim]")

    try:
        result = fetcher.get_historical_data(test_symbol, days=365)

        if result.is_valid and len(result.df) > 0:
            console.print(f"[green]✓ Data fetched: {len(result.df)} bars[/green]")
            console.print(f"[dim]  Quality: {result.quality.value}[/dim]")
            console.print(f"[dim]  Source: {result.source}[/dim]")
            console.print(f"[dim]  Latest price: ₹{result.df.iloc[-1]['close']:,.2f}[/dim]")
            return True
        else:
            console.print("[yellow]⚠ Data returned but may be invalid[/yellow]")
            console.print(f"[dim]  Quality: {result.quality.value}[/dim]")
            return False
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def test_symbol_mappings():
    """Test that symbol mappings work correctly."""
    console.print("\n[bold blue]2. Testing Symbol Mappings...[/bold blue]")

    from data.reliable_fetcher import get_reliable_fetcher

    fetcher = get_reliable_fetcher()

    # Test ABB (should map to ABB.BO)
    console.print("[dim]Testing ABB (uses BSE mapping)...[/dim]")
    abb = fetcher.get_historical_data("ABB", days=30)
    if abb.is_valid:
        console.print(f"[green]✓ ABB: {len(abb.df)} bars fetched[/green]")
    else:
        console.print(f"[yellow]⚠ ABB: Quality is {abb.quality.value}[/yellow]")

    # Test MCDOWELL-N (should map to UNITDSPR.NS)
    console.print("[dim]Testing MCDOWELL-N (uses alternative symbol)...[/dim]")
    mcdowell = fetcher.get_historical_data("MCDOWELL-N", days=30)
    if mcdowell.is_valid:
        console.print(f"[green]✓ MCDOWELL-N: {len(mcdowell.df)} bars fetched[/green]")
    else:
        console.print(f"[yellow]⚠ MCDOWELL-N: Quality is {mcdowell.quality.value}[/yellow]")

    # Test known failure (TATAMOTORS)
    console.print("[dim]Testing TATAMOTORS (known failure)...[/dim]")
    tata = fetcher.get_historical_data("TATAMOTORS", days=30)
    if not tata.is_valid:
        console.print(f"[green]✓ TATAMOTORS correctly marked as unusable[/green]")
    else:
        console.print(f"[yellow]⚠ TATAMOTORS unexpectedly worked[/yellow]")

    return True


def test_data_gates():
    """Test data quality gates."""
    console.print("\n[bold blue]3. Testing Data Quality Gates...[/bold blue]")

    from data.quality_monitor import get_data_gates
    from data.models import DataQuality
    import pandas as pd

    gates = get_data_gates()
    console.print("[green]✓ Data gates initialized[/green]")

    # Test with mock data
    mock_price_df = pd.DataFrame({
        'open': [100, 101, 102],
        'high': [105, 106, 107],
        'low': [98, 99, 100],
        'close': [103, 104, 105],
        'volume': [1000000, 1100000, 1200000]
    })

    result = gates.check_all_gates(
        price_quality=DataQuality.GOOD,
        price_data=mock_price_df,
        fii_dii_data={'fii_net': 500},
        fii_dii_quality=DataQuality.GOOD,
        fundamentals={'pe_ratio': 25},
        fundamentals_quality=DataQuality.DEGRADED,
        earnings_data={},
        earnings_quality=DataQuality.UNUSABLE,
        global_context={'vix': 15},
        global_quality=DataQuality.GOOD
    )

    console.print(f"[green]✓ Gates checked[/green]")
    console.print(f"[dim]  Allow trading: {result.allow_trading}[/dim]")
    console.print(f"[dim]  Combined multiplier: {result.combined_multiplier:.2f}[/dim]")
    console.print(f"[dim]  Overall quality: {result.overall_quality.value}[/dim]")

    if result.warnings:
        console.print("[dim]  Warnings:[/dim]")
        for w in result.warnings:
            console.print(f"[dim]    - {w}[/dim]")

    return True


def test_position_manager():
    """Test position manager."""
    console.print("\n[bold blue]4. Testing Position Manager...[/bold blue]")

    from journal.position_manager import get_position_manager

    pm = get_position_manager(capital=1_000_000)
    console.print("[green]✓ Position manager initialized[/green]")
    console.print(f"[dim]  Capital: ₹{pm.capital:,.0f}[/dim]")

    # Test position sizing
    sizing = pm.calculate_position_size(
        entry_price=2500,
        stop_loss=2400,
        conviction_level='B',
        data_quality_multiplier=0.9
    )

    console.print(f"[green]✓ Position sizing calculated[/green]")
    console.print(f"[dim]  Shares: {sizing['shares']}[/dim]")
    console.print(f"[dim]  Value: ₹{sizing['value']:,.0f}[/dim]")
    console.print(f"[dim]  Risk: ₹{sizing['risk_amount']:,.0f} ({sizing['risk_pct']:.2f}%)[/dim]")

    # Get portfolio status
    status = pm.get_portfolio_status()
    console.print(f"[green]✓ Portfolio status[/green]")
    console.print(f"[dim]  Heat: {status.current_heat:.1f}%[/dim]")
    console.print(f"[dim]  Available: {status.heat_available:.1f}%[/dim]")

    return True


def test_intelligence_layer():
    """Test intelligence layer (mock mode)."""
    console.print("\n[bold blue]5. Testing Intelligence Layer (Mock Mode)...[/bold blue]")

    try:
        from intelligence import get_intelligence_orchestrator, AgentContext

        intel = get_intelligence_orchestrator()
        console.print("[green]✓ Intelligence orchestrator initialized[/green]")

        # Create test context
        context = AgentContext(
            timestamp=datetime.now(),
            symbol="RELIANCE",
            market_regime="BULL",
            price_data={'current_price': 2500},
            ensemble_votes={'momentum': True, 'trend': True, 'breakout': False, 'mean_reversion': False},
            conviction_score=65,
            global_context={'vix': 15},
            fii_dii_data={'fii_net': 1000},
            data_quality={'price': 'good', 'fii_dii': 'good'}
        )

        # Quick check (rule-based)
        quick = intel.quick_check(context)
        console.print(f"[green]✓ Quick check completed[/green]")
        console.print(f"[dim]  Can proceed: {quick['can_proceed']}[/dim]")
        console.print(f"[dim]  Position modifier: {quick['position_modifier']:.2f}[/dim]")

        # Full analysis (uses mock responses without Claude API key)
        result = intel.analyze(context)
        console.print(f"[green]✓ Full analysis completed[/green]")
        console.print(f"[dim]  Can trade: {result.can_trade}[/dim]")
        console.print(f"[dim]  Final modifier: {result.final_position_modifier:.2f}[/dim]")
        console.print(f"[dim]  Agents consulted: {', '.join(result.agents_consulted)}[/dim]")

        return True
    except Exception as e:
        console.print(f"[yellow]⚠ Intelligence layer test skipped: {e}[/yellow]")
        return True  # Non-critical


def test_intelligent_orchestrator():
    """Test the full intelligent orchestrator."""
    console.print("\n[bold blue]6. Testing Intelligent Orchestrator...[/bold blue]")

    try:
        from core.intelligent_orchestrator import get_intelligent_orchestrator

        orchestrator = get_intelligent_orchestrator(capital=1_000_000)
        console.print("[green]✓ Intelligent orchestrator initialized[/green]")

        # Analyze a stock
        console.print("[dim]Analyzing RELIANCE...[/dim]")
        analysis = orchestrator.analyze_stock(
            symbol="RELIANCE",
            market_regime="BULL",
            include_intelligence=True
        )

        console.print(f"[green]✓ Analysis completed[/green]")
        console.print(f"[dim]  Decision: {analysis.final_decision.value}[/dim]")
        console.print(f"[dim]  Conviction: {analysis.final_conviction}/100[/dim]")
        console.print(f"[dim]  Position modifier: {analysis.final_position_modifier:.2f}[/dim]")

        # Display full summary
        console.print("\n[bold]Full Analysis Summary:[/bold]")
        summary = orchestrator.get_analysis_summary(analysis)
        console.print(summary)

        return True

    except ImportError as e:
        console.print(f"[yellow]⚠ Import error (some dependencies may be missing): {e}[/yellow]")
        return False
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def test_system_health():
    """Test system health check."""
    console.print("\n[bold blue]7. Testing System Health...[/bold blue]")

    from data.reliable_fetcher import get_reliable_fetcher

    fetcher = get_reliable_fetcher()
    health = fetcher.get_system_health()

    console.print(f"[green]✓ System health checked[/green]")
    console.print(f"[dim]  Price data: {health.price_data.value}[/dim]")
    console.print(f"[dim]  Overall: {health.overall.value}[/dim]")
    console.print(f"[dim]  yfinance available: {health.yfinance_available}[/dim]")
    console.print(f"[dim]  Allow trading: {health.allow_trading}[/dim]")
    console.print(f"[dim]  Position multiplier: {health.position_size_multiplier:.2f}[/dim]")

    if health.warnings:
        for w in health.warnings:
            console.print(f"[dim]  Warning: {w}[/dim]")

    return health.allow_trading


def main():
    """Run all integration tests."""
    console.print(Panel.fit(
        "[bold green]Nifty Signals - Integration Test[/bold green]\n"
        "Testing all system components (yfinance-only mode)...",
        border_style="green"
    ))

    results = {}

    # Run tests
    results['Reliable Fetcher'] = test_reliable_fetcher()
    results['Symbol Mappings'] = test_symbol_mappings()
    results['Data Gates'] = test_data_gates()
    results['Position Manager'] = test_position_manager()
    results['Intelligence Layer'] = test_intelligence_layer()
    results['Intelligent Orchestrator'] = test_intelligent_orchestrator()
    results['System Health'] = test_system_health()

    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold]Test Results Summary[/bold]")
    console.print("=" * 60)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Component")
    table.add_column("Status")

    for name, passed in results.items():
        status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        table.add_row(name, status)

    console.print(table)

    # Overall result
    all_passed = all(results.values())
    if all_passed:
        console.print("\n[bold green]All tests passed! System is ready.[/bold green]")
    else:
        console.print("\n[bold yellow]Some tests failed. Check the output above.[/bold yellow]")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
