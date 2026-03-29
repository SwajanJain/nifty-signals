"""Coffee Can / Consistent Compounder Quality Screen."""

from fundamentals.models import FundamentalProfile, ScreenResult
from .base import BaseScreen


class QualityScreen(BaseScreen):
    """Consistent compounder / Coffee Can quality screen.

    Looks for high-quality businesses with consistent performance:
    - ROCE > 15% consistently over 5 years
    - Revenue growth > 10% consistently
    - Low debt, strong cash flows
    - High promoter holding, stable margins
    """

    @property
    def name(self) -> str:
        return "quality"

    @property
    def description(self) -> str:
        return "Consistent Compounder: High ROCE, Consistent Growth, Low Debt"

    def screen(self, profile: FundamentalProfile) -> ScreenResult:
        p = profile
        met = []
        failed = []
        score = 0
        roce = p.roce or 0
        roe = p.roe or 0
        npm = p.npm or 0

        # 1. ROCE > 15% consistently (all 5 years)
        if not p.is_banking:
            if p.roce_consistent_above_15 and roce >= 20:
                met.append(f"ROCE {roce:.1f}% (consistent >15%, currently >20%)")
                score += 25
            elif p.roce_consistent_above_15:
                met.append(f"ROCE {roce:.1f}% (consistent >15%)")
                score += 20
            elif roce >= 15:
                met.append(f"ROCE {roce:.1f}% (current >15%, not fully consistent)")
                score += 10
            else:
                failed.append(f"ROCE {roce:.1f}% < 15%")
        else:
            if roe >= 15:
                met.append(f"ROE {roe:.1f}% (banking)")
                score += 15
            else:
                failed.append(f"ROE {roe:.1f}% < 15% (banking)")

        # 2. Revenue growth > 10% consistently
        if p.revenue_growing_consistently and p.revenue_growth_3y >= 15:
            met.append(f"Revenue growing consistently ({p.revenue_growth_3y:.0f}% CAGR)")
            score += 20
        elif p.revenue_growing_consistently:
            met.append(f"Revenue growing consistently ({p.revenue_growth_3y:.0f}% CAGR)")
            score += 15
        elif p.revenue_growth_3y >= 10:
            met.append(f"Revenue growth {p.revenue_growth_3y:.0f}% (not fully consistent)")
            score += 10
        else:
            failed.append(f"Revenue growth {p.revenue_growth_3y:.0f}% < 10%")

        # 3. Low debt D/E < 0.5
        if not p.is_banking:
            if p.debt_to_equity < 0.1:
                met.append("Debt-free")
                score += 15
            elif p.debt_to_equity < 0.3:
                met.append(f"Very low debt D/E {p.debt_to_equity:.2f}")
                score += 12
            elif p.debt_to_equity < 0.5:
                met.append(f"Low debt D/E {p.debt_to_equity:.2f}")
                score += 10
            else:
                failed.append(f"D/E {p.debt_to_equity:.2f} > 0.5")
        else:
            score += 8

        # 4. OCF positive consistently (5 years)
        if p.cash_flow_positive_years >= 5:
            met.append("OCF positive all 5 years")
            score += 15
        elif p.cash_flow_positive_years >= 4:
            met.append(f"OCF positive {p.cash_flow_positive_years}/5 years")
            score += 10
        else:
            failed.append(f"OCF positive only {p.cash_flow_positive_years}/5 years")

        # 5. Promoter holding > 30%
        if p.promoter_holding >= 50:
            met.append(f"High promoter holding {p.promoter_holding:.1f}%")
            score += 10
        elif p.promoter_holding >= 40:
            met.append(f"Good promoter holding {p.promoter_holding:.1f}%")
            score += 7
        elif p.promoter_holding >= 30:
            met.append(f"Adequate promoter holding {p.promoter_holding:.1f}%")
            score += 5
        elif p.promoter_holding > 0:
            failed.append(f"Low promoter holding {p.promoter_holding:.1f}%")
        else:
            met.append("Widely held (no promoter)")
            score += 5

        # 6. NPM stable or improving
        if p.npm_stable_or_improving:
            met.append(f"NPM stable/improving ({npm:.1f}%)")
            score += 15
        else:
            failed.append("NPM declining")

        # Hard pass criteria
        passes = (
            (roce >= 15 or p.is_banking)
            and p.revenue_growth_3y >= 10
            and (p.debt_to_equity <= 0.5 or p.is_banking)
            and p.cash_flow_positive_years >= 3
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
                'Rev Growth': f"{p.revenue_growth_3y:.0f}%",
                'D/E': p.debt_to_equity,
                'NPM': f"{npm:.1f}%",
                'OCF Years': f"{p.cash_flow_positive_years}/5",
            },
        )
