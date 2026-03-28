"""Graham/Buffett Value Screen."""

from fundamentals.models import FundamentalProfile, ScreenResult
from .base import BaseScreen


class ValueScreen(BaseScreen):
    """Graham/Buffett value investing screen.

    Looks for undervalued stocks with strong financials:
    - Low PE, Low PB, Low Debt
    - Consistent earnings, adequate market cap
    - Graham intrinsic value margin of safety
    """

    @property
    def name(self) -> str:
        return "value"

    @property
    def description(self) -> str:
        return "Graham/Buffett Value: Low PE, Low PB, Low Debt, Consistent Earnings"

    def screen(self, profile: FundamentalProfile) -> ScreenResult:
        p = profile
        met = []
        failed = []
        score = 0

        # 1. P/E < 15
        if 0 < p.pe_ratio <= 10:
            met.append(f"PE {p.pe_ratio:.1f} (excellent)")
            score += 25
        elif 0 < p.pe_ratio <= 12:
            met.append(f"PE {p.pe_ratio:.1f} (good)")
            score += 20
        elif 0 < p.pe_ratio <= 15:
            met.append(f"PE {p.pe_ratio:.1f}")
            score += 15
        elif 0 < p.pe_ratio <= 20:
            met.append(f"PE {p.pe_ratio:.1f} (slightly high)")
            score += 5
        else:
            failed.append(f"PE {p.pe_ratio:.1f} > 15")

        # 2. P/B < 2.0
        if 0 < p.pb_ratio <= 1.0:
            met.append(f"PB {p.pb_ratio:.1f} (deep value)")
            score += 20
        elif 0 < p.pb_ratio <= 1.5:
            met.append(f"PB {p.pb_ratio:.1f} (good)")
            score += 15
        elif 0 < p.pb_ratio <= 2.0:
            met.append(f"PB {p.pb_ratio:.1f}")
            score += 10
        else:
            failed.append(f"PB {p.pb_ratio:.1f} > 2.0")

        # 3. D/E < 0.5
        if not p.is_banking:
            if p.debt_to_equity < 0.1:
                met.append("Debt-free")
                score += 15
            elif p.debt_to_equity < 0.3:
                met.append(f"Low debt D/E {p.debt_to_equity:.1f}")
                score += 12
            elif p.debt_to_equity < 0.5:
                met.append(f"Moderate debt D/E {p.debt_to_equity:.1f}")
                score += 10
            else:
                failed.append(f"D/E {p.debt_to_equity:.1f} > 0.5")
        else:
            met.append("Banking (D/E not applicable)")
            score += 8

        # 4. No losses in last 5 years
        if p.no_loss_years_5:
            met.append("Profitable all 5 years")
            score += 15
        else:
            failed.append("Has loss year(s) in last 5 years")

        # 5. Market cap > 5000 Cr
        if p.market_cap >= 50000:
            met.append(f"Large cap: {p.market_cap:,.0f} Cr")
            score += 10
        elif p.market_cap >= 20000:
            met.append(f"Mid cap: {p.market_cap:,.0f} Cr")
            score += 7
        elif p.market_cap >= 5000:
            met.append(f"Adequate size: {p.market_cap:,.0f} Cr")
            score += 5
        else:
            failed.append(f"Market cap {p.market_cap:,.0f} Cr < 5000 Cr")

        # 6. Graham intrinsic value margin of safety
        # Intrinsic Value = EPS × (8.5 + 2 × growth_rate)
        if p.eps_ttm > 0 and p.eps_growth_3y > 0:
            graham_value = p.eps_ttm * (8.5 + 2 * p.eps_growth_3y)
            margin = (graham_value - p.current_price) / graham_value * 100 if graham_value > 0 else 0
            if margin > 30:
                met.append(f"Margin of safety {margin:.0f}% (excellent)")
                score += 15
            elif margin > 20:
                met.append(f"Margin of safety {margin:.0f}%")
                score += 10
            elif margin > 10:
                met.append(f"Margin of safety {margin:.0f}% (thin)")
                score += 5
            else:
                failed.append(f"No margin of safety ({margin:.0f}%)")

        # Hard pass criteria
        passes = (
            (0 < p.pe_ratio <= 20)
            and (p.pb_ratio <= 2.5 or p.pb_ratio == 0)
            and (p.debt_to_equity <= 0.5 or p.is_banking)
            and p.no_loss_years_5
            and p.market_cap >= 5000
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
                'PE': p.pe_ratio,
                'PB': p.pb_ratio,
                'D/E': p.debt_to_equity,
                'ROE': p.roe,
                'Mkt Cap': f"{p.market_cap:,.0f} Cr",
            },
        )
