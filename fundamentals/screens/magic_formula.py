"""Joel Greenblatt's Magic Formula Screen."""

from fundamentals.models import FundamentalProfile, ScreenResult
from .base import BaseScreen


class MagicFormulaScreen(BaseScreen):
    """Joel Greenblatt's Magic Formula screen.

    Ranks stocks by two metrics:
    1. Earnings Yield (EBIT / EV) - higher is better
    2. Return on Capital (EBIT / (NWC + NFA)) - approximated with ROCE

    Excludes financials/banking. Requires profitability and minimum size.
    For single-stock screening, uses a point-based approach since
    cross-stock ranking is not available.
    """

    @property
    def name(self) -> str:
        return "magic_formula"

    @property
    def description(self) -> str:
        return "Greenblatt Magic Formula: High Earnings Yield + High ROCE"

    def screen(self, profile: FundamentalProfile) -> ScreenResult:
        p = profile
        met = []
        failed = []
        score = 0
        pe = p.pe_ratio or 0
        roce = p.roce or 0
        roe = p.roe or 0
        earnings_yield = p.earnings_yield or 0

        # Skip banking/finance stocks
        if p.is_banking:
            return ScreenResult(
                symbol=p.symbol,
                company_name=p.company_name,
                sector=p.sector,
                passes=False,
                strategy=self.name,
                score=0,
                criteria_met=[],
                criteria_failed=["Banking/finance excluded from Magic Formula"],
                key_metrics={},
            )

        # Hard filters
        if pe <= 0:
            failed.append(f"PE {pe:.1f} (not profitable)")
            return ScreenResult(
                symbol=p.symbol,
                company_name=p.company_name,
                sector=p.sector,
                passes=False,
                strategy=self.name,
                score=0,
                criteria_met=[],
                criteria_failed=failed,
                key_metrics={'PE': pe},
            )

        if p.market_cap < 500:
            failed.append(f"Market cap {p.market_cap:,.0f} Cr < 500 Cr minimum")
            return ScreenResult(
                symbol=p.symbol,
                company_name=p.company_name,
                sector=p.sector,
                passes=False,
                strategy=self.name,
                score=0,
                criteria_met=[],
                criteria_failed=failed,
                key_metrics={'Mkt Cap': f"{p.market_cap:,.0f} Cr"},
            )

        # 1. Earnings Yield (higher is better)
        ey = earnings_yield
        if ey > 15:
            met.append(f"Earnings yield {ey:.1f}% (excellent)")
            score += 25
        elif ey > 10:
            met.append(f"Earnings yield {ey:.1f}% (strong)")
            score += 20
        elif ey > 8:
            met.append(f"Earnings yield {ey:.1f}% (good)")
            score += 15
        elif ey > 5:
            met.append(f"Earnings yield {ey:.1f}% (adequate)")
            score += 10
        else:
            failed.append(f"Earnings yield {ey:.1f}% < 5%")

        # 2. ROCE (proxy for Return on Capital)
        if roce > 50:
            met.append(f"ROCE {roce:.1f}% (exceptional)")
            score += 25
        elif roce > 30:
            met.append(f"ROCE {roce:.1f}% (excellent)")
            score += 20
        elif roce > 20:
            met.append(f"ROCE {roce:.1f}% (good)")
            score += 15
        elif roce > 15:
            met.append(f"ROCE {roce:.1f}% (adequate)")
            score += 10
        elif roce > 10:
            met.append(f"ROCE {roce:.1f}% (marginal)")
            score += 5
        else:
            failed.append(f"ROCE {roce:.1f}% < 10%")

        # 3. ROE bonus
        if roe > 25:
            met.append(f"ROE {roe:.1f}% (excellent)")
            score += 15
        elif roe > 20:
            met.append(f"ROE {roe:.1f}% (strong)")
            score += 12
        elif roe > 15:
            met.append(f"ROE {roe:.1f}% (good)")
            score += 8
        elif roe > 10:
            met.append(f"ROE {roe:.1f}% (adequate)")
            score += 5
        else:
            failed.append(f"ROE {roe:.1f}% < 10%")

        # 4. Low debt bonus
        if p.debt_to_equity < 0.3:
            met.append(f"Low debt D/E {p.debt_to_equity:.2f}")
            score += 10
        elif p.debt_to_equity < 0.5:
            met.append(f"Moderate debt D/E {p.debt_to_equity:.2f}")
            score += 7
        elif p.debt_to_equity < 1.0:
            met.append(f"Acceptable debt D/E {p.debt_to_equity:.2f}")
            score += 3
        else:
            failed.append(f"High debt D/E {p.debt_to_equity:.2f}")

        # 5. Cash flow quality
        if p.free_cash_flow > 0 and p.operating_cash_flow > 0:
            met.append("Positive FCF and OCF")
            score += 10
        elif p.operating_cash_flow > 0:
            met.append("Positive OCF (FCF negative)")
            score += 5
        else:
            failed.append("Negative operating cash flow")

        # 6. Consistency bonus
        if p.roce_consistent_above_15:
            met.append("ROCE consistently above 15%")
            score += 15
        else:
            failed.append("ROCE not consistently above 15%")

        # Hard pass: profitable, adequate size, reasonable quality
        passes = (
            pe > 0
            and p.market_cap >= 500
            and earnings_yield > 5
            and roce > 10
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
                'Earnings Yield': f"{earnings_yield:.1f}%",
                'ROCE': f"{roce:.1f}%",
                'ROE': f"{roe:.1f}%",
                'D/E': p.debt_to_equity,
                'PE': pe,
                'Mkt Cap': f"{p.market_cap:,.0f} Cr",
            },
        )
