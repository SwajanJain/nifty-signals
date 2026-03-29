"""Quality at Reasonable Price (QARP) Compounder Screen."""

from fundamentals.models import FundamentalProfile, ScreenResult
from .base import BaseScreen


class CompounderScreen(BaseScreen):
    """Quality at Reasonable Price (QARP) compounder screen.

    Combines quality + reasonable valuation for long-term compounding:

    Quality gate (need 3 of 4):
    - ROCE >= 15%
    - ROE >= 12%
    - NPM >= 8%
    - cash_flow_positive_years >= 4

    Reasonable price (need at least 1):
    - PE < 40
    - PEG < 2.0
    - PE < 25 if growth < 15%

    Growth minimum:
    - revenue_growth_3y >= 10%
    - profit_growth_3y >= 12%

    Financial strength:
    - debt_to_equity < 1.0
    - no_loss_years_5
    """

    @property
    def name(self) -> str:
        return "compounder"

    @property
    def description(self) -> str:
        return "QARP Compounder: Quality Business + Reasonable Valuation + Growth"

    def screen(self, profile: FundamentalProfile) -> ScreenResult:
        p = profile
        met = []
        failed = []
        score = 0
        pe = p.pe_ratio or 0
        peg = p.peg_ratio or 0
        roce = p.roce or 0
        roe = p.roe or 0
        npm = p.npm or 0

        # --- Quality Gate (need 3 of 4) ---
        quality_count = 0

        # Q1: ROCE >= 15%
        if roce >= 25:
            met.append(f"Q: ROCE {roce:.1f}% (excellent)")
            score += 15
            quality_count += 1
        elif roce >= 20:
            met.append(f"Q: ROCE {roce:.1f}% (strong)")
            score += 12
            quality_count += 1
        elif roce >= 15:
            met.append(f"Q: ROCE {roce:.1f}%")
            score += 8
            quality_count += 1
        else:
            failed.append(f"Q: ROCE {roce:.1f}% < 15%")

        # Q2: ROE >= 12%
        if roe >= 20:
            met.append(f"Q: ROE {roe:.1f}% (strong)")
            score += 12
            quality_count += 1
        elif roe >= 15:
            met.append(f"Q: ROE {roe:.1f}% (good)")
            score += 8
            quality_count += 1
        elif roe >= 12:
            met.append(f"Q: ROE {roe:.1f}%")
            score += 5
            quality_count += 1
        else:
            failed.append(f"Q: ROE {roe:.1f}% < 12%")

        # Q3: NPM >= 8%
        if npm >= 15:
            met.append(f"Q: NPM {npm:.1f}% (strong)")
            score += 10
            quality_count += 1
        elif npm >= 10:
            met.append(f"Q: NPM {npm:.1f}% (good)")
            score += 7
            quality_count += 1
        elif npm >= 8:
            met.append(f"Q: NPM {npm:.1f}%")
            score += 5
            quality_count += 1
        else:
            failed.append(f"Q: NPM {npm:.1f}% < 8%")

        # Q4: Cash flow positive years >= 4
        if p.cash_flow_positive_years >= 5:
            met.append("Q: Positive cash flow all 5 years")
            score += 8
            quality_count += 1
        elif p.cash_flow_positive_years >= 4:
            met.append(f"Q: Positive cash flow {p.cash_flow_positive_years}/5 years")
            score += 5
            quality_count += 1
        else:
            failed.append(
                f"Q: Cash flow positive {p.cash_flow_positive_years}/5 years < 4"
            )

        quality_gate_pass = quality_count >= 3

        # --- Reasonable Price (need at least 1) ---
        price_pass = False

        # P1: PE < 40
        if 0 < pe <= 20:
            met.append(f"P: PE {pe:.1f} (attractive)")
            score += 12
            price_pass = True
        elif 0 < pe <= 30:
            met.append(f"P: PE {pe:.1f} (reasonable)")
            score += 8
            price_pass = True
        elif 0 < pe < 40:
            met.append(f"P: PE {pe:.1f} (fair)")
            score += 4
            price_pass = True
        else:
            failed.append(f"P: PE {pe:.1f} >= 40 or negative")

        # P2: PEG < 2.0
        if 0 < peg <= 1.0:
            met.append(f"P: PEG {peg:.1f} (attractive)")
            score += 10
            price_pass = True
        elif 0 < peg <= 1.5:
            met.append(f"P: PEG {peg:.1f} (reasonable)")
            score += 7
            price_pass = True
        elif 0 < peg < 2.0:
            met.append(f"P: PEG {peg:.1f} (fair)")
            score += 3
            price_pass = True
        else:
            if peg >= 2.0:
                failed.append(f"P: PEG {peg:.1f} >= 2.0")

        # P3: Low-growth valuation check
        if p.profit_growth_3y < 15 and pe >= 25:
            failed.append(
                f"P: Growth {p.profit_growth_3y:.0f}% < 15% but PE {pe:.1f} >= 25"
            )
            price_pass = False  # Override if growth doesn't justify valuation

        # --- Growth Minimum ---
        growth_pass = True

        if p.revenue_growth_3y >= 20:
            met.append(f"G: Revenue growth {p.revenue_growth_3y:.0f}% (strong)")
            score += 8
        elif p.revenue_growth_3y >= 10:
            met.append(f"G: Revenue growth {p.revenue_growth_3y:.0f}%")
            score += 5
        else:
            failed.append(f"G: Revenue growth {p.revenue_growth_3y:.0f}% < 10%")
            growth_pass = False

        if p.profit_growth_3y >= 25:
            met.append(f"G: Profit growth {p.profit_growth_3y:.0f}% (strong)")
            score += 8
        elif p.profit_growth_3y >= 12:
            met.append(f"G: Profit growth {p.profit_growth_3y:.0f}%")
            score += 5
        else:
            failed.append(f"G: Profit growth {p.profit_growth_3y:.0f}% < 12%")
            growth_pass = False

        # --- Financial Strength ---
        strength_pass = True

        if p.debt_to_equity < 0.5 or p.is_debt_free:
            met.append(f"F: Low debt D/E {p.debt_to_equity:.2f}")
            score += 5
        elif p.debt_to_equity < 1.0:
            met.append(f"F: Moderate debt D/E {p.debt_to_equity:.2f}")
            score += 3
        else:
            failed.append(f"F: High debt D/E {p.debt_to_equity:.2f} >= 1.0")
            strength_pass = False

        if p.no_loss_years_5:
            met.append("F: No loss years in last 5 years")
            score += 5
        else:
            failed.append("F: Has loss year(s) in last 5 years")
            strength_pass = False

        # --- Bonus points ---
        if p.promoter_holding > 50:
            met.append(f"Bonus: High promoter holding {p.promoter_holding:.1f}%")
            score += 3
        elif p.promoter_holding > 40:
            met.append(f"Bonus: Good promoter holding {p.promoter_holding:.1f}%")
            score += 2

        if p.fii_holding_change_1y > 1:
            met.append(f"Bonus: FII increasing +{p.fii_holding_change_1y:.1f}%")
            score += 3

        if p.dividend_growing:
            met.append("Bonus: Dividend growing")
            score += 2

        if p.roce_consistent_above_15:
            met.append("Bonus: ROCE consistently above 15%")
            score += 3

        # Hard pass: quality gate (3/4) + at least 1 price criterion + growth + strength
        passes = (
            quality_gate_pass
            and price_pass
            and growth_pass
            and strength_pass
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
                'ROE': f"{roe:.1f}%",
                'NPM': f"{npm:.1f}%",
                'PE': pe,
                'PEG': peg,
                'Profit Growth': f"{p.profit_growth_3y:.0f}%",
                'D/E': p.debt_to_equity,
            },
        )
