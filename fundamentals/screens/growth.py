"""Peter Lynch / CAN SLIM Growth Screen."""

from fundamentals.models import FundamentalProfile, ScreenResult
from .base import BaseScreen


class GrowthScreen(BaseScreen):
    """Peter Lynch / CAN SLIM growth investing screen.

    Looks for high-growth stocks at reasonable valuations:
    - High EPS and revenue growth
    - PEG ratio < 1.5
    - Quarterly earnings acceleration
    - Institutional interest
    """

    @property
    def name(self) -> str:
        return "growth"

    @property
    def description(self) -> str:
        return "Peter Lynch Growth: High EPS Growth, Revenue Growth, PEG < 1.5"

    def screen(self, profile: FundamentalProfile) -> ScreenResult:
        p = profile
        met = []
        failed = []
        score = 0

        # 1. EPS CAGR 3Y > 20%
        if p.eps_growth_3y >= 30:
            met.append(f"EPS growth {p.eps_growth_3y:.0f}% (exceptional)")
            score += 25
        elif p.eps_growth_3y >= 25:
            met.append(f"EPS growth {p.eps_growth_3y:.0f}% (excellent)")
            score += 20
        elif p.eps_growth_3y >= 20:
            met.append(f"EPS growth {p.eps_growth_3y:.0f}%")
            score += 15
        else:
            failed.append(f"EPS growth {p.eps_growth_3y:.0f}% < 20%")

        # 2. Revenue CAGR 3Y > 15%
        if p.revenue_growth_3y >= 25:
            met.append(f"Revenue growth {p.revenue_growth_3y:.0f}% (excellent)")
            score += 20
        elif p.revenue_growth_3y >= 20:
            met.append(f"Revenue growth {p.revenue_growth_3y:.0f}%")
            score += 15
        elif p.revenue_growth_3y >= 15:
            met.append(f"Revenue growth {p.revenue_growth_3y:.0f}%")
            score += 10
        else:
            failed.append(f"Revenue growth {p.revenue_growth_3y:.0f}% < 15%")

        # 3. PEG ratio < 1.5
        if 0 < p.peg_ratio <= 0.5:
            met.append(f"PEG {p.peg_ratio:.1f} (very attractive)")
            score += 20
        elif 0 < p.peg_ratio <= 1.0:
            met.append(f"PEG {p.peg_ratio:.1f} (good)")
            score += 15
        elif 0 < p.peg_ratio <= 1.5:
            met.append(f"PEG {p.peg_ratio:.1f}")
            score += 10
        else:
            failed.append(f"PEG {p.peg_ratio:.1f} > 1.5")

        # 4. Quarterly earnings acceleration
        if p.qtr_eps_acceleration and p.consecutive_qtr_growth >= 4:
            met.append(f"Accelerating earnings + {p.consecutive_qtr_growth} quarters growth")
            score += 15
        elif p.qtr_eps_acceleration:
            met.append("Earnings accelerating")
            score += 10
        elif p.consecutive_qtr_growth >= 3:
            met.append(f"{p.consecutive_qtr_growth} consecutive quarters of growth")
            score += 7
        else:
            failed.append("No quarterly acceleration")

        # 5. Institutional interest (FII increasing)
        if p.fii_holding_change_1y > 2:
            met.append(f"FII increasing: +{p.fii_holding_change_1y:.1f}%")
            score += 10
        elif p.fii_holding_change_1y > 0:
            met.append(f"FII stable/increasing: +{p.fii_holding_change_1y:.1f}%")
            score += 5
        else:
            failed.append(f"FII declining: {p.fii_holding_change_1y:.1f}%")

        # 6. Profitability (ROE > 12%)
        if p.roe >= 20:
            met.append(f"Strong ROE: {p.roe:.1f}%")
            score += 10
        elif p.roe >= 15:
            met.append(f"Good ROE: {p.roe:.1f}%")
            score += 7
        elif p.roe >= 12:
            met.append(f"Adequate ROE: {p.roe:.1f}%")
            score += 5
        else:
            failed.append(f"ROE {p.roe:.1f}% < 12%")

        # Hard pass criteria
        passes = (
            p.eps_growth_3y >= 20
            and p.revenue_growth_3y >= 15
            and 0 < p.peg_ratio <= 1.5
            and p.roe >= 12
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
                'EPS Growth': f"{p.eps_growth_3y:.0f}%",
                'Rev Growth': f"{p.revenue_growth_3y:.0f}%",
                'PEG': p.peg_ratio,
                'ROE': f"{p.roe:.1f}%",
                'Qtr Growth': p.consecutive_qtr_growth,
            },
        )
