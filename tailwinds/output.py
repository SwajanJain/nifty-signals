"""Rich CLI formatting for tailwind analysis output."""

from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import (
    CompositeScore,
    NewsItem,
    SectorTailwind,
    TailwindScore,
    Theme,
)

console = Console()


def tailwind_color(score: int) -> str:
    if score >= 70:
        return "green"
    elif score >= 55:
        return "cyan"
    elif score >= 45:
        return "yellow"
    elif score >= 30:
        return "red"
    return "bold red"


def direction_icon(direction: str) -> str:
    return "[green]+[/green]" if direction == "TAILWIND" else "[red]-[/red]"


def composite_color(score: int) -> str:
    if score >= 75:
        return "green"
    elif score >= 60:
        return "cyan"
    elif score >= 45:
        return "yellow"
    elif score >= 30:
        return "red"
    return "bold red"


class TailwindOutput:
    """Rich-formatted CLI output for tailwind analysis."""

    def display_themes(self, themes: List[Theme]):
        """Display all active macro themes."""
        table = Table(title="Active Macro Themes", show_lines=True)
        table.add_column("#", width=3, style="dim")
        table.add_column("Theme", width=30, style="bold")
        table.add_column("Category", width=18)
        table.add_column("Dir", width=10, justify="center")
        table.add_column("Str", width=4, justify="center")
        table.add_column("Sectors", width=35)

        for i, t in enumerate(themes, 1):
            direction = (
                "[green]TAILWIND[/green]"
                if t.direction == "TAILWIND"
                else "[red]HEADWIND[/red]"
            )
            strength_bar = "[green]" + "*" * t.strength + "[/green]" if t.direction == "TAILWIND" else "[red]" + "*" * t.strength + "[/red]"

            sectors = ", ".join(
                f"{s}({w:.0%})" for s, w in sorted(
                    t.affected_sectors.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:4]
            )

            table.add_row(
                str(i),
                t.name,
                t.category.replace("_", " ").title(),
                direction,
                strength_bar,
                sectors,
            )

        console.print(table)

    def display_sector_scores(self, sectors: Dict[str, SectorTailwind]):
        """Display all sectors ranked by tailwind score."""
        table = Table(title="Sector Tailwind Rankings", show_lines=False)
        table.add_column("#", width=3, style="dim")
        table.add_column("Sector", width=18, style="bold")
        table.add_column("Score", width=6, justify="right")
        table.add_column("Grade", width=16)
        table.add_column("Policy", width=7, justify="right")
        table.add_column("Demand", width=7, justify="right")
        table.add_column("Global", width=7, justify="right")
        table.add_column("Cycle", width=7, justify="right")
        table.add_column("Top Theme", width=25)

        for i, (sector, st) in enumerate(sectors.items(), 1):
            color = tailwind_color(st.total_score)
            top_theme = st.contributing_themes[0]["name"] if st.contributing_themes else "-"

            table.add_row(
                str(i),
                sector,
                f"[{color}]{st.total_score}[/]",
                f"[{color}]{st.grade}[/]",
                str(st.policy_support_score),
                str(st.demand_dynamics_score),
                str(st.global_alignment_score),
                str(st.sector_cycle_score),
                top_theme[:25],
            )

        console.print(table)

    def display_sector_deep_dive(
        self,
        sector_tailwind: SectorTailwind,
        news_items: List[NewsItem],
    ):
        """Detailed sector analysis with themes and news."""
        st = sector_tailwind
        color = tailwind_color(st.total_score)

        # Header
        header = Text()
        header.append(f"Sector: {st.sector}\n", style="bold")
        header.append(f"Tailwind Score: ")
        header.append(f"{st.total_score}/100", style=color)
        header.append(f" ({st.grade})")

        console.print(Panel(header, title="Sector Tailwind Analysis", border_style="cyan"))

        # Component breakdown
        comp_table = Table(title="Score Components", show_lines=True)
        comp_table.add_column("Component", width=20)
        comp_table.add_column("Score", width=6, justify="right")
        comp_table.add_column("Max", width=4, justify="right")
        comp_table.add_column("Bar", width=20)

        components = [
            ("Policy Support", st.policy_support_score, 25),
            ("Demand Dynamics", st.demand_dynamics_score, 25),
            ("Global Alignment", st.global_alignment_score, 25),
            ("Sector Cycle", st.sector_cycle_score, 25),
        ]

        for name, val, max_val in components:
            pct = val / max_val if max_val > 0 else 0
            bar_filled = int(pct * 15)
            bar = "[green]" + "\u2588" * bar_filled + "[/green]" + "\u2591" * (15 - bar_filled)
            comp_table.add_row(name, str(val), str(max_val), bar)

        console.print(comp_table)

        # Contributing themes
        if st.contributing_themes:
            console.print("\n[bold]Contributing Themes[/bold]")
            for ct in st.contributing_themes:
                icon = direction_icon(ct["direction"])
                console.print(
                    f"  {icon} {ct['name']} "
                    f"(impact: {ct['impact']:.1f}, {ct['category'].replace('_', ' ').lower()})"
                )

        # News highlights
        if st.news_highlights:
            console.print(f"\n[bold]Recent News ({st.sector})[/bold]")
            for headline in st.news_highlights[:5]:
                console.print(f"  [dim]-[/dim] {headline}")

        # News sentiment
        s = st.news_sentiment
        total = s["bullish"] + s["bearish"] + s["neutral"]
        if total > 0:
            console.print(
                f"\n[bold]News Sentiment:[/bold] "
                f"[green]{s['bullish']} bullish[/green] / "
                f"[red]{s['bearish']} bearish[/red] / "
                f"[dim]{s['neutral']} neutral[/dim] "
                f"(from {total} articles)"
            )

    def display_composite_analysis(
        self,
        composite: CompositeScore,
        tailwind: TailwindScore,
        fundamental_green_flags: List[str] = None,
        fundamental_red_flags: List[str] = None,
    ):
        """Display combined internal + external + composite analysis."""
        c = composite

        # Summary line
        console.print()
        f_color = composite_color(c.fundamental_score)
        t_color = tailwind_color(c.tailwind_score)
        c_color = composite_color(c.composite_score)

        console.print(
            f"[bold]{c.symbol}[/bold] | "
            f"Internal: [{f_color}]{c.fundamental_score}/100 ({c.fundamental_grade})[/] | "
            f"External: [{t_color}]{c.tailwind_score}/100[/] | "
            f"Composite: [{c_color}]{c.composite_score}/100 ({c.composite_grade})[/]"
        )

        # Breakdown table
        table = Table(title="Score Breakdown", show_lines=True)
        table.add_column("Dimension", width=20)
        table.add_column("Score", width=8, justify="right")
        table.add_column("Weight", width=8, justify="right")
        table.add_column("Contribution", width=12, justify="right")

        table.add_row(
            "Internal (Fundamentals)",
            f"[{f_color}]{c.fundamental_score}[/]",
            "50%",
            f"{c.fundamental_score * 0.5:.0f}",
        )
        table.add_row(
            "External (Tailwinds)",
            f"[{t_color}]{c.tailwind_score}[/]",
            "30%",
            f"{c.tailwind_score * 0.3:.0f}",
        )
        table.add_row(
            "Valuation",
            f"-",
            "20%",
            f"-",
        )
        table.add_row(
            "[bold]COMPOSITE[/bold]",
            f"[{c_color}][bold]{c.composite_score}[/bold][/]",
            "100%",
            f"[{c_color}]{c.composite_grade}[/]",
        )

        console.print(table)

        # Tailwind details
        if tailwind.key_themes:
            console.print(f"\n[bold]Active Themes for {c.sector}[/bold]")
            for theme in tailwind.key_themes[:5]:
                console.print(f"  [cyan]-[/cyan] {theme}")

        console.print(f"\n[dim]{tailwind.explanation}[/dim]")

        # Flags
        if fundamental_green_flags:
            console.print("\n[bold green]GREEN FLAGS[/bold green]")
            for flag in fundamental_green_flags:
                console.print(f"  [green]+[/green] {flag}")
        if fundamental_red_flags:
            console.print("\n[bold red]RED FLAGS[/bold red]")
            for flag in fundamental_red_flags:
                console.print(f"  [red]-[/red] {flag}")

    def display_composite_scan(
        self,
        composites: List[CompositeScore],
        top_n: int = 20,
    ):
        """Display ranked composite scores for multiple stocks."""
        table = Table(
            title=f"Composite Scan - Top {min(top_n, len(composites))} Stocks",
            show_lines=False,
        )
        table.add_column("#", width=4, style="dim")
        table.add_column("Symbol", width=12, style="bold")
        table.add_column("Sector", width=14)
        table.add_column("Internal", width=9, justify="right")
        table.add_column("External", width=9, justify="right")
        table.add_column("Composite", width=10, justify="right")
        table.add_column("Grade", width=6, justify="center")

        for i, c in enumerate(composites[:top_n], 1):
            f_color = composite_color(c.fundamental_score)
            t_color = tailwind_color(c.tailwind_score)
            c_color = composite_color(c.composite_score)

            table.add_row(
                str(i),
                c.symbol,
                c.sector[:14] if c.sector else "",
                f"[{f_color}]{c.fundamental_score}[/]",
                f"[{t_color}]{c.tailwind_score}[/]",
                f"[{c_color}]{c.composite_score}[/]",
                f"[{c_color}]{c.composite_grade}[/]",
            )

        console.print(table)
