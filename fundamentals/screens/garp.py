"""Growth at Reasonable Price (GARP) Screen."""

from fundamentals.models import FundamentalProfile, ScreenResult
from .base import BaseScreen


class GARPScreen(BaseScreen):
    """Growth at Reasonable Price screen.

    Balances growth and valuation:
    - PEG ratio < 1.5
    - Earnings growth > 15%
    - ROE > 15%
    - Reasonable P/E < 30
    """

    @property
    def name(self) -> str:
        return "garp"

    @property
    def description(self) -> str:
        return "GARP: PEG < 1.5, Good Growth, Reasonable Valuation"

    def screen(self, profile: FundamentalProfile) -> ScreenResult:
        p = profile
        met = []
        failed = []
        score = 0
        peg = p.peg_ratio or 0
        roe = p.roe or 0
        pe = p.pe_ratio or 0

        # 1. PEG ratio < 1.5
        if 0 < peg <= 0.5:
            met.append(f"PEG {peg:.1f} (exceptional)")
            score += 30
        elif 0 < peg <= 1.0:
            met.append(f"PEG {peg:.1f} (attractive)")
            score += 25
        elif 0 < peg <= 1.5:
            met.append(f"PEG {peg:.1f} (reasonable)")
            score += 15
        else:
            failed.append(f"PEG {peg:.1f} > 1.5")

        # 2. Earnings growth > 15% (3Y CAGR)
        if p.profit_growth_3y >= 25:
            met.append(f"Profit growth {p.profit_growth_3y:.0f}% (excellent)")
            score += 25
        elif p.profit_growth_3y >= 20:
            met.append(f"Profit growth {p.profit_growth_3y:.0f}% (strong)")
            score += 20
        elif p.profit_growth_3y >= 15:
            met.append(f"Profit growth {p.profit_growth_3y:.0f}%")
            score += 15
        else:
            failed.append(f"Profit growth {p.profit_growth_3y:.0f}% < 15%")

        # 3. ROE > 15%
        if roe >= 25:
            met.append(f"ROE {roe:.1f}% (excellent)")
            score += 20
        elif roe >= 20:
            met.append(f"ROE {roe:.1f}% (strong)")
            score += 15
        elif roe >= 15:
            met.append(f"ROE {roe:.1f}%")
            score += 10
        else:
            failed.append(f"ROE {roe:.1f}% < 15%")

        # 4. P/E < 30 (reasonable valuation)
        if 0 < pe <= 15:
            met.append(f"PE {pe:.1f} (cheap)")
            score += 25
        elif pe <= 20:
            met.append(f"PE {pe:.1f} (reasonable)")
            score += 20
        elif pe <= 25:
            met.append(f"PE {pe:.1f} (fair)")
            score += 15
        elif pe <= 30:
            met.append(f"PE {pe:.1f} (slightly rich)")
            score += 10
        else:
            failed.append(f"PE {pe:.1f} > 30")

        # Hard pass criteria
        passes = (
            0 < peg <= 1.5
            and p.profit_growth_3y >= 15
            and roe >= 15
            and 0 < pe <= 30
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
                'PEG': peg,
                'PE': pe,
                'ROE': f"{roe:.1f}%",
                'Profit Growth': f"{p.profit_growth_3y:.0f}%",
            },
        )
