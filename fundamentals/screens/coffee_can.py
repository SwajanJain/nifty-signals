"""Saurabh Mukherjea's Coffee Can Investing Screen."""

from fundamentals.models import FundamentalProfile, ScreenResult
from .base import BaseScreen


class CoffeeCanScreen(BaseScreen):
    """Saurabh Mukherjea's Coffee Can Investing screen.

    Long-term buy-and-hold screen for consistent compounders:
    - ROCE consistently >= 15% (tighter: roce_consistent + roce >= 18)
    - Revenue growing consistently with 5Y CAGR >= 10%
    - Market cap >= 5000 Cr (institutional quality)
    - No loss years in last 5 years
    - Low leverage (D/E < 0.5 or debt-free)
    - Positive free cash flow in at least 4 of 5 years

    All three mandatory criteria: ROCE consistent, revenue consistent,
    no losses.
    """

    @property
    def name(self) -> str:
        return "coffee_can"

    @property
    def description(self) -> str:
        return "Coffee Can: Consistent ROCE, Revenue Growth, Zero Losses, Low Debt"

    def screen(self, profile: FundamentalProfile) -> ScreenResult:
        p = profile
        met = []
        failed = []
        score = 0

        # --- Mandatory 1: ROCE consistency ---
        # NOTE: True Coffee Can investing (Saurabh Mukherjea) requires 10 years
        # of consistent ROCE > 15%. Screener.in provides only 5 years of annual
        # data. This screen approximates with 5Y data + stricter current ROCE
        # threshold (>=18%) as a proxy for longer-term consistency.
        roce = p.roce or 0
        roce_ok = p.roce_consistent_above_15 and roce >= 18
        if p.roce_consistent_above_15 and roce >= 25:
            met.append(f"ROCE {roce:.1f}% consistently above 15% (excellent, 5Y data)")
            score += 25
        elif p.roce_consistent_above_15 and roce >= 20:
            met.append(f"ROCE {roce:.1f}% consistently above 15% (strong, 5Y data)")
            score += 20
        elif roce_ok:
            met.append(f"ROCE {roce:.1f}% consistently above 15% (5Y data)")
            score += 15
        else:
            parts = []
            if not p.roce_consistent_above_15:
                parts.append("ROCE not consistent above 15%")
            if roce < 18:
                parts.append(f"current ROCE {roce:.1f}% < 18%")
            failed.append(f"ROCE consistency: {', '.join(parts)}")

        # --- Mandatory 2: Revenue growing consistently ---
        revenue_ok = p.revenue_growing_consistently and p.revenue_growth_5y >= 10
        if p.revenue_growing_consistently and p.revenue_growth_5y >= 20:
            met.append(f"Revenue growing consistently at {p.revenue_growth_5y:.0f}% CAGR (excellent)")
            score += 20
        elif p.revenue_growing_consistently and p.revenue_growth_5y >= 15:
            met.append(f"Revenue growing consistently at {p.revenue_growth_5y:.0f}% CAGR (strong)")
            score += 15
        elif revenue_ok:
            met.append(f"Revenue growing consistently at {p.revenue_growth_5y:.0f}% CAGR")
            score += 10
        else:
            parts = []
            if not p.revenue_growing_consistently:
                parts.append("revenue not growing consistently")
            if p.revenue_growth_5y < 10:
                parts.append(f"5Y CAGR {p.revenue_growth_5y:.0f}% < 10%")
            failed.append(f"Revenue consistency: {', '.join(parts)}")

        # --- Mandatory 3: No loss years ---
        if p.no_loss_years_5:
            met.append("No loss years in last 5 years")
            score += 10
        else:
            failed.append("Has loss year(s) in last 5 years")

        # --- Market cap >= 5000 Cr ---
        if p.market_cap >= 50000:
            met.append(f"Large cap: {p.market_cap:,.0f} Cr")
            score += 10
        elif p.market_cap >= 20000:
            met.append(f"Upper mid cap: {p.market_cap:,.0f} Cr")
            score += 8
        elif p.market_cap >= 5000:
            met.append(f"Institutional quality: {p.market_cap:,.0f} Cr")
            score += 5
        else:
            failed.append(f"Market cap {p.market_cap:,.0f} Cr < 5000 Cr")

        # --- Low leverage ---
        if p.is_debt_free or p.debt_to_equity < 0.1:
            met.append("Debt-free or near debt-free")
            score += 10
        elif p.debt_to_equity < 0.3:
            met.append(f"Very low debt D/E {p.debt_to_equity:.2f}")
            score += 8
        elif p.debt_to_equity < 0.5:
            met.append(f"Low debt D/E {p.debt_to_equity:.2f}")
            score += 5
        else:
            failed.append(f"High debt D/E {p.debt_to_equity:.2f} > 0.5")

        # --- Positive FCF in at least 4 of 5 years ---
        if p.fcf_positive_years >= 5:
            met.append("FCF positive all 5 years")
            score += 10
        elif p.fcf_positive_years >= 4:
            met.append(f"FCF positive {p.fcf_positive_years}/5 years")
            score += 7
        else:
            failed.append(f"FCF positive only {p.fcf_positive_years}/5 years")

        # --- Bonus: High promoter holding ---
        if p.promoter_holding > 60:
            met.append(f"High promoter holding {p.promoter_holding:.1f}%")
            score += 5
        elif p.promoter_holding > 50:
            met.append(f"Good promoter holding {p.promoter_holding:.1f}%")
            score += 3

        # --- Bonus: NPM stable or improving ---
        if p.npm_stable_or_improving:
            met.append("NPM stable or improving")
            score += 5

        # --- Bonus: Dividend growing ---
        if p.dividend_growing:
            met.append("Dividend growing consistently")
            score += 5

        # Hard pass: all three mandatory + size + leverage
        passes = (
            roce_ok
            and revenue_ok
            and p.no_loss_years_5
            and p.market_cap >= 5000
            and (p.debt_to_equity < 0.5 or p.is_debt_free)
            and p.fcf_positive_years >= 4
        )

        return ScreenResult(
            symbol=p.symbol,
            company_name=p.company_name,
            sector=p.sector,
            passes=passes,
            strategy=self.name,
            score=min(100, score),
            criteria_met=met,
            criteria_failed=failed,
            key_metrics={
                'ROCE': f"{roce:.1f}%",
                'Rev Growth 5Y': f"{p.revenue_growth_5y:.0f}%",
                'D/E': p.debt_to_equity,
                'FCF +ve Years': f"{p.fcf_positive_years}/5",
                'Promoter': f"{p.promoter_holding:.1f}%",
                'Mkt Cap': f"{p.market_cap:,.0f} Cr",
            },
        )
