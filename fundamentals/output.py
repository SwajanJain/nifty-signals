"""Rich CLI formatting for fundamental analysis output."""

from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import FundamentalProfile, FundamentalScore, ScreenResult

console = Console()


def grade_color(grade: str) -> str:
    """Get color for a grade."""
    return {
        'A+': 'bold green',
        'A': 'green',
        'B': 'cyan',
        'C': 'yellow',
        'D': 'red',
        'F': 'bold red',
    }.get(grade, 'white')


def score_color(score: int) -> str:
    if score >= 80:
        return 'green'
    elif score >= 65:
        return 'cyan'
    elif score >= 50:
        return 'yellow'
    elif score >= 35:
        return 'red'
    return 'bold red'


class FundamentalOutput:
    """Rich-formatted CLI output for fundamental analysis."""

    def display_scan_results(
        self,
        scores: List[FundamentalScore],
        profiles: Dict[str, FundamentalProfile],
        top_n: int = 20,
    ):
        """Display top N stocks by composite fundamental score."""
        table = Table(
            title=f"Fundamental Scan - Top {min(top_n, len(scores))} Stocks",
            show_lines=False,
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Symbol", style="bold", width=12)
        table.add_column("Sector", width=14)
        table.add_column("Score", width=6, justify="right")
        table.add_column("Grade", width=6, justify="center")
        table.add_column("PE", width=6, justify="right")
        table.add_column("ROE%", width=7, justify="right")
        table.add_column("ROCE%", width=7, justify="right")
        table.add_column("D/E", width=5, justify="right")
        table.add_column("3Y Grw%", width=8, justify="right")
        table.add_column("Yield%", width=7, justify="right")

        for i, fs in enumerate(scores[:top_n], 1):
            p = profiles.get(fs.symbol)
            if not p:
                continue

            table.add_row(
                str(i),
                fs.symbol,
                fs.sector[:14] if fs.sector else "",
                f"[{score_color(fs.total_score)}]{fs.total_score}[/]",
                f"[{grade_color(fs.grade)}]{fs.grade}[/]",
                f"{p.pe_ratio:.1f}" if p.pe_ratio else "-",
                f"{p.roe:.1f}" if p.roe else "-",
                f"{p.roce:.1f}" if p.roce else "-",
                f"{p.debt_to_equity:.1f}" if not p.is_banking else "-",
                f"{p.profit_growth_3y:.0f}" if p.profit_growth_3y else "-",
                f"{p.dividend_yield:.1f}" if p.dividend_yield else "-",
            )

        console.print(table)

    def display_screen_results(self, results: List[ScreenResult], strategy_name: str):
        """Display results of a specific screening strategy."""
        if not results:
            console.print(f"[yellow]No stocks passed the {strategy_name} screen.[/yellow]")
            return

        table = Table(
            title=f"{strategy_name.upper()} Screen Results ({len(results)} matches)",
            show_lines=True,
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Symbol", style="bold", width=12)
        table.add_column("Name", width=25)
        table.add_column("Sector", width=14)
        table.add_column("Score", width=6, justify="right")

        # Add dynamic columns from key_metrics of first result
        if results:
            for key in results[0].key_metrics:
                table.add_column(key, width=10, justify="right")

        for i, r in enumerate(results, 1):
            row = [
                str(i),
                r.symbol,
                r.company_name[:25] if r.company_name else "",
                r.sector[:14] if r.sector else "",
                f"[{score_color(r.score)}]{r.score}[/]",
            ]
            for key in results[0].key_metrics:
                val = r.key_metrics.get(key, '-')
                row.append(str(val))

            table.add_row(*row)

        console.print(table)

        # Show criteria summary for top 3
        console.print()
        for r in results[:3]:
            met_str = ", ".join(r.criteria_met) if r.criteria_met else "None"
            console.print(f"[bold]{r.symbol}[/bold]: {met_str}")

    def display_stock_analysis(
        self,
        profile: FundamentalProfile,
        score: FundamentalScore,
    ):
        """Deep fundamental analysis report for a single stock."""
        p = profile
        fs = score

        # --- Header ---
        header = Text()
        header.append(f"{p.symbol}", style="bold")
        header.append(f" - {p.company_name}\n", style="dim")
        header.append(f"Sector: {p.sector}")
        if p.industry:
            header.append(f" | Industry: {p.industry}")
        header.append(f"\nPrice: Rs {p.current_price:,.2f}")
        header.append(f" | Market Cap: Rs {p.market_cap:,.0f} Cr")

        console.print(Panel(header, title="Fundamental Analysis", border_style="cyan"))

        # --- Score Breakdown ---
        score_table = Table(title="Score Breakdown", show_lines=True)
        score_table.add_column("Component", width=20)
        score_table.add_column("Score", width=8, justify="right")
        score_table.add_column("Max", width=6, justify="right")
        score_table.add_column("Bar", width=20)

        components = [
            ("Valuation", fs.valuation_score, 20),
            ("Profitability", fs.profitability_score, 25),
            ("Growth", fs.growth_score, 25),
            ("Financial Health", fs.financial_health_score, 15),
            ("Quality", fs.quality_score, 15),
        ]

        for name, val, max_val in components:
            pct = val / max_val if max_val > 0 else 0
            bar_filled = int(pct * 15)
            bar = "[green]" + "█" * bar_filled + "[/green]" + "░" * (15 - bar_filled)
            score_table.add_row(name, str(val), str(max_val), bar)

        score_table.add_row(
            "[bold]TOTAL[/bold]",
            f"[{score_color(fs.total_score)}][bold]{fs.total_score}[/bold][/]",
            "100",
            f"[{grade_color(fs.grade)}]Grade: {fs.grade}[/]",
        )

        console.print(score_table)

        # --- Valuation ---
        val_table = Table(title="Valuation", show_lines=False)
        val_table.add_column("Metric", width=18)
        val_table.add_column("Value", width=12, justify="right")

        val_metrics = [
            ("P/E Ratio", f"{p.pe_ratio:.1f}" if p.pe_ratio else "-"),
            ("P/B Ratio", f"{p.pb_ratio:.1f}" if p.pb_ratio else "-"),
            ("EV/EBITDA", f"{p.ev_ebitda:.1f}" if p.ev_ebitda else "-"),
            ("PEG Ratio", f"{p.peg_ratio:.1f}" if p.peg_ratio else "-"),
            ("Dividend Yield", f"{p.dividend_yield:.1f}%"),
            ("FCF Yield", f"{p.fcf_yield:.1f}%"),
            ("Earnings Yield", f"{p.earnings_yield:.1f}%"),
            ("Price/Sales", f"{p.price_to_sales:.1f}" if p.price_to_sales else "-"),
        ]
        for name, val in val_metrics:
            val_table.add_row(name, val)

        # --- Profitability ---
        prof_table = Table(title="Profitability", show_lines=False)
        prof_table.add_column("Metric", width=18)
        prof_table.add_column("Value", width=12, justify="right")

        prof_metrics = [
            ("ROE", f"{p.roe:.1f}%"),
            ("ROCE", f"{p.roce:.1f}%"),
            ("Net Profit Margin", f"{p.npm:.1f}%"),
            ("Operating Margin", f"{p.opm:.1f}%"),
        ]
        for name, val in prof_metrics:
            prof_table.add_row(name, val)

        console.print()
        # Print side by side using columns
        console.print(val_table)
        console.print(prof_table)

        # --- Growth ---
        growth_table = Table(title="Growth", show_lines=False)
        growth_table.add_column("Metric", width=22)
        growth_table.add_column("Value", width=12, justify="right")

        growth_metrics = [
            ("Revenue Growth 3Y", f"{p.revenue_growth_3y:.0f}%"),
            ("Revenue Growth 5Y", f"{p.revenue_growth_5y:.0f}%"),
            ("Profit Growth 3Y", f"{p.profit_growth_3y:.0f}%"),
            ("Profit Growth 5Y", f"{p.profit_growth_5y:.0f}%"),
            ("Qtr Revenue YoY", f"{p.latest_qtr_revenue_yoy:.1f}%"),
            ("Qtr Profit YoY", f"{p.latest_qtr_profit_yoy:.1f}%"),
            ("Earnings Acceleration", "Yes" if p.qtr_eps_acceleration else "No"),
            ("Consecutive Qtr Growth", str(p.consecutive_qtr_growth)),
        ]
        for name, val in growth_metrics:
            growth_table.add_row(name, val)

        console.print(growth_table)

        # --- Financial Health ---
        health_table = Table(title="Financial Health", show_lines=False)
        health_table.add_column("Metric", width=22)
        health_table.add_column("Value", width=12, justify="right")

        health_metrics = [
            ("Debt/Equity", f"{p.debt_to_equity:.2f}" if not p.is_banking else "N/A"),
            ("Interest Coverage", f"{p.interest_coverage:.1f}x"),
            ("Current Ratio", f"{p.current_ratio:.1f}"),
            ("OCF", f"Rs {p.operating_cash_flow:,.0f} Cr"),
            ("FCF", f"Rs {p.free_cash_flow:,.0f} Cr"),
            ("OCF Positive Years", f"{p.cash_flow_positive_years}/5"),
            ("FCF Positive Years", f"{p.fcf_positive_years}/5"),
        ]
        for name, val in health_metrics:
            health_table.add_row(name, val)

        console.print(health_table)

        # --- Ownership ---
        own_table = Table(title="Ownership", show_lines=False)
        own_table.add_column("Metric", width=22)
        own_table.add_column("Value", width=12, justify="right")

        own_metrics = [
            ("Promoter Holding", f"{p.promoter_holding:.1f}%"),
            ("Promoter Change (1Y)", f"{p.promoter_holding_change_1y:+.1f}%"),
            ("FII Holding", f"{p.fii_holding:.1f}%"),
            ("FII Change (1Y)", f"{p.fii_holding_change_1y:+.1f}%"),
            ("DII Holding", f"{p.dii_holding:.1f}%"),
        ]
        if p.promoter_pledge > 0:
            own_metrics.append(("Promoter Pledge", f"[red]{p.promoter_pledge:.1f}%[/red]"))
        for name, val in own_metrics:
            own_table.add_row(name, val)

        console.print(own_table)

        # --- Strategy Matches ---
        strategies_table = Table(title="Strategy Matches", show_lines=False)
        strategies_table.add_column("Strategy", width=15)
        strategies_table.add_column("Match", width=8, justify="center")

        strategy_checks = [
            ("Value", fs.matches_value),
            ("Growth", fs.matches_growth),
            ("Quality", fs.matches_quality),
            ("GARP", fs.matches_garp),
            ("Dividend", fs.matches_dividend),
        ]
        for name, matches in strategy_checks:
            icon = "[green]Yes[/green]" if matches else "[dim]No[/dim]"
            strategies_table.add_row(name, icon)

        console.print(strategies_table)

        # --- Flags ---
        if fs.green_flags:
            console.print("\n[bold green]GREEN FLAGS[/bold green]")
            for flag in fs.green_flags:
                console.print(f"  [green]+[/green] {flag}")

        if fs.red_flags:
            console.print("\n[bold red]RED FLAGS[/bold red]")
            for flag in fs.red_flags:
                console.print(f"  [red]-[/red] {flag}")

    def display_comparison(
        self,
        profiles: List[FundamentalProfile],
        scores: List[FundamentalScore],
    ):
        """Side-by-side comparison of 2+ stocks."""
        table = Table(title="Fundamental Comparison", show_lines=True)

        table.add_column("Metric", width=20, style="bold")
        for p in profiles:
            table.add_column(p.symbol, width=14, justify="right")

        # Score
        table.add_row(
            "Score / Grade",
            *[
                f"[{score_color(s.total_score)}]{s.total_score}[/] [{grade_color(s.grade)}]{s.grade}[/]"
                for s in scores
            ],
        )

        # Valuation
        table.add_row("--- VALUATION ---", *["" for _ in profiles])
        table.add_row("P/E", *[f"{p.pe_ratio:.1f}" for p in profiles])
        table.add_row("P/B", *[f"{p.pb_ratio:.1f}" for p in profiles])
        table.add_row("EV/EBITDA", *[f"{p.ev_ebitda:.1f}" for p in profiles])
        table.add_row("PEG", *[f"{p.peg_ratio:.1f}" for p in profiles])
        table.add_row("Div Yield", *[f"{p.dividend_yield:.1f}%" for p in profiles])

        # Profitability
        table.add_row("--- PROFITABILITY ---", *["" for _ in profiles])
        table.add_row("ROE", *[f"{p.roe:.1f}%" for p in profiles])
        table.add_row("ROCE", *[f"{p.roce:.1f}%" for p in profiles])
        table.add_row("NPM", *[f"{p.npm:.1f}%" for p in profiles])
        table.add_row("OPM", *[f"{p.opm:.1f}%" for p in profiles])

        # Growth
        table.add_row("--- GROWTH ---", *["" for _ in profiles])
        table.add_row("Revenue 3Y", *[f"{p.revenue_growth_3y:.0f}%" for p in profiles])
        table.add_row("Profit 3Y", *[f"{p.profit_growth_3y:.0f}%" for p in profiles])
        table.add_row("Qtr Profit YoY", *[f"{p.latest_qtr_profit_yoy:.0f}%" for p in profiles])

        # Health
        table.add_row("--- HEALTH ---", *["" for _ in profiles])
        table.add_row(
            "D/E",
            *[f"{p.debt_to_equity:.2f}" if not p.is_banking else "N/A" for p in profiles],
        )
        table.add_row("Interest Cov", *[f"{p.interest_coverage:.1f}x" for p in profiles])
        table.add_row("Mkt Cap (Cr)", *[f"{p.market_cap:,.0f}" for p in profiles])

        # Ownership
        table.add_row("--- OWNERSHIP ---", *["" for _ in profiles])
        table.add_row("Promoter", *[f"{p.promoter_holding:.1f}%" for p in profiles])
        table.add_row("FII", *[f"{p.fii_holding:.1f}%" for p in profiles])

        console.print(table)
