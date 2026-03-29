"""Discounted Cash Flow (DCF) valuation model for Indian equities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from fundamentals.valuation import ValuationResult

from fundamentals.models import FundamentalProfile, ScreenerRawData

logger = logging.getLogger(__name__)

# ---------- Default assumptions (India-centric) ----------
RISK_FREE_RATE = 0.07  # 10-yr G-Sec ~7%
EQUITY_RISK_PREMIUM = 0.06  # India ERP ~6%
DEFAULT_BETA = 1.0
DEFAULT_TAX_RATE = 0.25
TERMINAL_GROWTH = 0.04  # 4% long-term nominal GDP growth
DEFAULT_GROWTH_RATE = 0.10  # Conservative fallback
PROJECTION_YEARS = 5


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


class DCFValuation:
    """Five-year two-stage DCF with terminal value."""

    # ------------------------------------------------------------------ #
    #  helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _find_row(table: list, label: str) -> Optional[dict]:
        """Find a row by case-insensitive partial match on label.

        Screener.in labels often have trailing '+' (e.g. 'Borrowings+',
        'Sales+', 'Cash from Operating Activity+').
        """
        target = label.lower()
        for row in table:
            row_label = row.get("label", "").strip().rstrip("+").strip().lower()
            if row_label == target or target in row_label:
                return row
        return None

    @staticmethod
    def _extract_value(row: Optional[dict], fallback: float = 0.0) -> float:
        """Extract the most-recent numeric value from a row dict."""
        if not row:
            return fallback
        year_keys = sorted(
            (k for k in row if k != "label"), reverse=True
        )
        for yk in year_keys:
            try:
                val = float(str(row[yk]).replace(",", ""))
                return val
            except (ValueError, TypeError):
                continue
        return fallback

    def _extract_latest_row(
        self, table: list, label: str, fallback: float = 0.0
    ) -> float:
        """Pull the most-recent numeric value for *label* from a screener table."""
        return self._extract_value(self._find_row(table, label), fallback)

    def _extract_years(
        self, table: list, label: str, n: int = 5
    ) -> List[float]:
        """Return last *n* yearly values for *label* (oldest-first)."""
        row = self._find_row(table, label)
        if not row:
            return []
        year_keys = sorted(k for k in row if k != "label")
        vals: list[float] = []
        for yk in year_keys:
            try:
                vals.append(float(str(row[yk]).replace(",", "")))
            except (ValueError, TypeError):
                continue
        return vals[-n:]

    def _estimate_wacc(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData,
    ) -> float:
        """Approximate WACC using available data.

        For low-debt / debt-free companies we use cost of equity directly.
        For leveraged firms we blend Ke and Kd.
        """
        ke = RISK_FREE_RATE + DEFAULT_BETA * EQUITY_RISK_PREMIUM  # ~13%

        if profile.is_debt_free or profile.debt_to_equity <= 0.05:
            return ke

        # Approximate Kd from Interest / Total Borrowings
        interest = self._extract_latest_row(raw.annual_pl, "interest")
        borrowings = self._extract_latest_row(raw.balance_sheet, "borrowings")
        kd_pre = _safe_div(interest, borrowings, default=0.09)
        kd_post = kd_pre * (1 - DEFAULT_TAX_RATE)

        # Equity weight from D/E
        de = max(profile.debt_to_equity, 0.01)
        we = 1.0 / (1.0 + de)
        wd = 1.0 - we

        wacc = we * ke + wd * kd_post
        return max(wacc, 0.08)  # floor at 8%

    def _get_base_fcf(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData,
    ) -> tuple[float, list[str]]:
        """Determine starting FCF (Cr) and any assumption notes."""
        assumptions: list[str] = []

        if profile.free_cash_flow and profile.free_cash_flow > 0:
            return profile.free_cash_flow, assumptions

        # Fallback: try to compute from cash-flow statement
        ocf = self._extract_latest_row(
            raw.cash_flow, "cash from operating activity"
        )
        capex = abs(
            self._extract_latest_row(
                raw.cash_flow, "fixed assets purchased"
            )
        ) or abs(
            self._extract_latest_row(
                raw.cash_flow, "purchase of fixed assets"
            )
        )
        fcf = ocf - capex
        if fcf > 0:
            assumptions.append("FCF computed from OCF - Capex (raw cash-flow)")
            return fcf, assumptions

        # Last resort: use OCF directly
        if profile.operating_cash_flow and profile.operating_cash_flow > 0:
            assumptions.append("Using OCF as FCF proxy (capex unavailable)")
            return profile.operating_cash_flow, assumptions

        if ocf > 0:
            assumptions.append("Using raw OCF as FCF proxy")
            return ocf, assumptions

        return 0.0, ["FCF and OCF are non-positive; DCF unreliable"]

    def _get_growth_rate(self, profile: FundamentalProfile) -> tuple[float, list[str]]:
        """Pick the best available growth rate for FCF projection."""
        assumptions: list[str] = []

        # Prefer profit growth, then revenue growth
        candidates = [
            (profile.profit_growth_3y, "3Y profit CAGR"),
            (profile.profit_growth_5y, "5Y profit CAGR"),
            (profile.revenue_growth_3y, "3Y revenue CAGR"),
            (profile.revenue_growth_5y, "5Y revenue CAGR"),
        ]
        for rate, desc in candidates:
            if rate and rate > 0:
                # Cap at 30% to avoid over-optimism
                capped = min(rate / 100.0, 0.30)
                assumptions.append(f"Growth from {desc}: {rate:.1f}% (capped)")
                return capped, assumptions

        assumptions.append("No growth data; using conservative 10%")
        return DEFAULT_GROWTH_RATE, assumptions

    # ------------------------------------------------------------------ #
    #  main entry
    # ------------------------------------------------------------------ #

    def value(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData,
    ) -> "ValuationResult":
        from fundamentals.valuation import ValuationResult

        assumptions: list[str] = []
        confidence = "MEDIUM"

        # Banking: DCF is a poor fit
        if profile.is_banking:
            assumptions.append("Banking company -- DCF not ideal; low confidence")
            confidence = "LOW"

        # Shares outstanding
        shares = _safe_div(
            profile.market_cap * 1e7,  # Cr -> absolute
            profile.current_price,
            default=0,
        )
        if shares <= 0:
            return ValuationResult(
                symbol=profile.symbol,
                model="dcf",
                fair_value=0,
                current_price=profile.current_price,
                signal="NOT_APPLICABLE",
                confidence="LOW",
                assumptions=["Cannot compute shares outstanding"],
            )

        base_fcf, fcf_notes = self._get_base_fcf(profile, raw)
        assumptions.extend(fcf_notes)

        if base_fcf <= 0:
            return ValuationResult(
                symbol=profile.symbol,
                model="dcf",
                fair_value=0,
                current_price=profile.current_price,
                signal="NOT_APPLICABLE",
                confidence="LOW",
                assumptions=assumptions,
            )

        growth, g_notes = self._get_growth_rate(profile)
        assumptions.extend(g_notes)

        wacc = self._estimate_wacc(profile, raw)
        assumptions.append(f"WACC: {wacc*100:.1f}%")
        assumptions.append(f"Terminal growth: {TERMINAL_GROWTH*100:.1f}%")

        if wacc <= TERMINAL_GROWTH:
            assumptions.append("WACC <= terminal growth; unreliable")
            return ValuationResult(
                symbol=profile.symbol,
                model="dcf",
                current_price=profile.current_price,
                signal="NOT_APPLICABLE",
                confidence="LOW",
                assumptions=assumptions,
            )

        # ---- Project FCFs ----
        projected_fcfs: list[float] = []
        fcf = base_fcf
        for yr in range(1, PROJECTION_YEARS + 1):
            fcf *= 1 + growth
            projected_fcfs.append(fcf)

        # ---- Terminal value ----
        terminal_fcf = projected_fcfs[-1] * (1 + TERMINAL_GROWTH)
        terminal_value = terminal_fcf / (wacc - TERMINAL_GROWTH)

        # ---- Discount to present ----
        pv_fcfs = sum(
            cf / (1 + wacc) ** yr
            for yr, cf in enumerate(projected_fcfs, start=1)
        )
        pv_terminal = terminal_value / (1 + wacc) ** PROJECTION_YEARS

        enterprise_value = pv_fcfs + pv_terminal  # in Cr

        # Subtract net debt for equity value
        borrowings = self._extract_latest_row(raw.balance_sheet, "borrowings")
        # Cash proxy: try Cash Equivalents first, then Investments
        cash = self._extract_latest_row(raw.balance_sheet, "cash equivalents")
        if cash <= 0:
            # Use a fraction of Investments as liquid assets proxy
            investments = self._extract_latest_row(raw.balance_sheet, "investments")
            cash = investments * 0.3  # Conservative: only 30% liquid
        net_debt = max(borrowings - cash, 0)
        equity_value = enterprise_value - net_debt  # Cr

        fair_value_per_share = max(equity_value * 1e7 / shares, 0)

        # ---- Margin of safety ----
        mos = (
            (fair_value_per_share - profile.current_price)
            / fair_value_per_share
            * 100
            if fair_value_per_share > 0
            else 0
        )

        if mos > 25:
            signal = "UNDERVALUED"
        elif mos < -25:
            signal = "OVERVALUED"
        else:
            signal = "FAIR"

        # Terminal value dominance check
        tv_dominance_pct = (pv_terminal / enterprise_value * 100) if enterprise_value > 0 else 0
        if tv_dominance_pct > 75:
            assumptions.append(
                f"WARNING: Terminal value is {tv_dominance_pct:.0f}% of DCF — projection is speculative"
            )

        # Confidence adjustments
        if base_fcf == profile.operating_cash_flow:
            confidence = "LOW"
        if growth >= 0.25:
            confidence = "LOW"
            assumptions.append("High growth assumption reduces confidence")
        if tv_dominance_pct > 85:
            confidence = "LOW"

        return ValuationResult(
            symbol=profile.symbol,
            model="dcf",
            fair_value=round(fair_value_per_share, 2),
            current_price=profile.current_price,
            margin_of_safety_pct=round(mos, 2),
            signal=signal,
            confidence=confidence,
            details={
                "base_fcf_cr": round(base_fcf, 2),
                "growth_rate_pct": round(growth * 100, 2),
                "wacc_pct": round(wacc * 100, 2),
                "terminal_growth_pct": round(TERMINAL_GROWTH * 100, 2),
                "pv_projected_fcfs_cr": round(pv_fcfs, 2),
                "pv_terminal_cr": round(pv_terminal, 2),
                "tv_dominance_pct": round(tv_dominance_pct, 1),
                "enterprise_value_cr": round(enterprise_value, 2),
                "net_debt_cr": round(net_debt, 2),
                "equity_value_cr": round(equity_value, 2),
                "shares": round(shares, 0),
            },
            assumptions=assumptions,
        )
