"""Dividend Income Screen."""

from fundamentals.models import FundamentalProfile, ScreenResult
from .base import BaseScreen


class DividendScreen(BaseScreen):
    """Dividend income investing screen.

    Looks for reliable dividend-paying stocks:
    - Dividend yield > 2%
    - Consistent dividend history (5 years)
    - Sustainable payout ratio (20-60%)
    - Growing dividends
    - Strong cash flows
    """

    @property
    def name(self) -> str:
        return "dividend"

    @property
    def description(self) -> str:
        return "Dividend Income: High Yield, Consistent History, Sustainable Payout"

    def screen(self, profile: FundamentalProfile) -> ScreenResult:
        p = profile
        met = []
        failed = []
        score = 0

        # 1. Dividend yield > 2%
        if p.dividend_yield >= 4:
            met.append(f"Yield {p.dividend_yield:.1f}% (high)")
            score += 25
        elif p.dividend_yield >= 3:
            met.append(f"Yield {p.dividend_yield:.1f}% (good)")
            score += 20
        elif p.dividend_yield >= 2:
            met.append(f"Yield {p.dividend_yield:.1f}%")
            score += 15
        else:
            failed.append(f"Yield {p.dividend_yield:.1f}% < 2%")

        # 2. Consistent dividend history (5 years)
        if p.dividend_years_5 >= 5:
            met.append("Dividend paid all 5 years")
            score += 20
        elif p.dividend_years_5 >= 4:
            met.append(f"Dividend paid {p.dividend_years_5}/5 years")
            score += 10
        else:
            failed.append(f"Dividend paid only {p.dividend_years_5}/5 years")

        # 3. Payout ratio 20-60% (sustainable)
        pr = p.dividend_payout_ratio
        if 30 <= pr <= 50:
            met.append(f"Optimal payout ratio {pr:.0f}%")
            score += 20
        elif 20 <= pr <= 60:
            met.append(f"Sustainable payout ratio {pr:.0f}%")
            score += 15
        elif 60 < pr <= 80:
            met.append(f"High payout ratio {pr:.0f}% (monitor)")
            score += 5
        elif pr > 0:
            failed.append(f"Payout ratio {pr:.0f}% outside 20-60% range")
        else:
            failed.append("No payout data")

        # 4. Growing dividends
        if p.dividend_growing:
            met.append("Dividends increasing")
            score += 20
        else:
            failed.append("Dividends not consistently growing")

        # 5. Strong cash flows (FCF positive)
        if p.free_cash_flow > 0 and p.fcf_positive_years >= 4:
            met.append(f"Strong FCF ({p.fcf_positive_years}/5 years positive)")
            score += 15
        elif p.free_cash_flow > 0:
            met.append("FCF positive (current year)")
            score += 10
        else:
            failed.append("Negative free cash flow")

        # Hard pass criteria
        passes = (
            p.dividend_yield >= 2
            and p.dividend_years_5 >= 4
            and 10 <= p.dividend_payout_ratio <= 80
            and p.free_cash_flow > 0
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
                'Yield': f"{p.dividend_yield:.1f}%",
                'Payout': f"{p.dividend_payout_ratio:.0f}%",
                'Div Years': f"{p.dividend_years_5}/5",
                'FCF': f"{p.free_cash_flow:,.0f} Cr",
                'Growing': 'Yes' if p.dividend_growing else 'No',
            },
        )
