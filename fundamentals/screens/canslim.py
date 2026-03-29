"""William O'Neil's CAN SLIM Growth Screen."""

from fundamentals.models import FundamentalProfile, ScreenResult
from .base import BaseScreen


class CANSLIMScreen(BaseScreen):
    """William O'Neil's CAN SLIM growth investing screen.

    Seven criteria:
    C - Current quarterly earnings growth > 25%
    A - Annual earnings growth > 25% (3Y) or > 20% (5Y)
    N - New highs/products (EPS acceleration as proxy)
    S - Supply/demand (institutional quality market cap)
    L - Leader (strong ROCE and ROE)
    I - Institutional sponsorship (FII/DII presence)
    M - Market direction (deferred to regime layer)

    Hard pass: C and A must both pass.
    """

    @property
    def name(self) -> str:
        return "canslim"

    @property
    def description(self) -> str:
        return "O'Neil CAN SLIM: Strong Quarterly + Annual Earnings, Leadership"

    def screen(self, profile: FundamentalProfile) -> ScreenResult:
        p = profile
        met = []
        failed = []
        score = 0
        roce = p.roce or 0
        roe = p.roe or 0

        # --- C: Current quarterly earnings > 25% YoY ---
        c_pass = False
        if p.latest_qtr_profit_yoy >= 50:
            met.append(f"C: Quarterly profit +{p.latest_qtr_profit_yoy:.0f}% (exceptional)")
            score += 20
            c_pass = True
        elif p.latest_qtr_profit_yoy >= 35:
            met.append(f"C: Quarterly profit +{p.latest_qtr_profit_yoy:.0f}% (strong)")
            score += 15
            c_pass = True
        elif p.latest_qtr_profit_yoy >= 25:
            met.append(f"C: Quarterly profit +{p.latest_qtr_profit_yoy:.0f}%")
            score += 12
            c_pass = True
        else:
            failed.append(f"C: Quarterly profit +{p.latest_qtr_profit_yoy:.0f}% < 25%")

        # --- A: Annual earnings growth ---
        a_pass = False
        if p.profit_growth_3y >= 35:
            met.append(f"A: 3Y profit CAGR {p.profit_growth_3y:.0f}% (exceptional)")
            score += 20
            a_pass = True
        elif p.profit_growth_3y >= 25:
            met.append(f"A: 3Y profit CAGR {p.profit_growth_3y:.0f}%")
            score += 15
            a_pass = True
        elif p.profit_growth_5y >= 20:
            met.append(f"A: 5Y profit CAGR {p.profit_growth_5y:.0f}% (alt threshold)")
            score += 12
            a_pass = True
        else:
            failed.append(
                f"A: 3Y profit CAGR {p.profit_growth_3y:.0f}% < 25% "
                f"and 5Y {p.profit_growth_5y:.0f}% < 20%"
            )

        # --- N: New highs / new earnings momentum ---
        if p.qtr_eps_acceleration and p.consecutive_qtr_growth >= 3:
            met.append(
                f"N: EPS accelerating + {p.consecutive_qtr_growth} consecutive "
                f"quarters growth"
            )
            score += 12
        elif p.qtr_eps_acceleration:
            met.append("N: EPS accelerating")
            score += 8
        elif p.consecutive_qtr_growth >= 2:
            met.append(f"N: {p.consecutive_qtr_growth} consecutive quarters growth")
            score += 5
        else:
            failed.append("N: No earnings acceleration or consecutive growth")

        # --- S: Supply/demand (institutional quality) ---
        if p.market_cap >= 5000:
            met.append(f"S: Large/mid cap {p.market_cap:,.0f} Cr")
            score += 10
        elif p.market_cap >= 1000:
            met.append(f"S: Institutional quality {p.market_cap:,.0f} Cr")
            score += 7
        else:
            failed.append(f"S: Market cap {p.market_cap:,.0f} Cr < 1000 Cr")

        # --- L: Leader (ROCE >= 15% and ROE >= 15%) ---
        l_pass = roce >= 15 and roe >= 15
        if roce >= 25 and roe >= 25:
            met.append(f"L: Leader ROCE {roce:.1f}% ROE {roe:.1f}% (dominant)")
            score += 15
        elif l_pass:
            met.append(f"L: Leader ROCE {roce:.1f}% ROE {roe:.1f}%")
            score += 10
        else:
            parts = []
            if roce < 15:
                parts.append(f"ROCE {roce:.1f}%")
            if roe < 15:
                parts.append(f"ROE {roe:.1f}%")
            failed.append(f"L: Not a leader ({', '.join(parts)} < 15%)")

        # --- I: Institutional sponsorship ---
        i_pass = p.fii_holding > 5 or p.dii_holding > 10
        if p.fii_holding > 10 and p.dii_holding > 15:
            met.append(
                f"I: Strong institutional FII {p.fii_holding:.1f}% "
                f"DII {p.dii_holding:.1f}%"
            )
            score += 12
        elif p.fii_holding > 5:
            met.append(f"I: FII holding {p.fii_holding:.1f}%")
            score += 8
        elif p.dii_holding > 10:
            met.append(f"I: DII holding {p.dii_holding:.1f}%")
            score += 6
        else:
            failed.append(
                f"I: Low institutional FII {p.fii_holding:.1f}% "
                f"DII {p.dii_holding:.1f}%"
            )

        # --- M: Market direction (always pass, checked at regime level) ---
        met.append("M: Market direction (deferred to regime analysis)")
        score += 5

        # Bonus: revenue growth confirms earnings quality
        if p.revenue_growth_3y >= 20:
            met.append(f"Revenue growth {p.revenue_growth_3y:.0f}% confirms earnings")
            score += 6

        # Hard pass: C and A must both pass
        passes = c_pass and a_pass

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
                'Qtr Profit YoY': f"{p.latest_qtr_profit_yoy:.0f}%",
                '3Y Profit CAGR': f"{p.profit_growth_3y:.0f}%",
                'ROCE': f"{roce:.1f}%",
                'ROE': f"{roe:.1f}%",
                'FII': f"{p.fii_holding:.1f}%",
                'Mkt Cap': f"{p.market_cap:,.0f} Cr",
            },
        )
