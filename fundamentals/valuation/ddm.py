"""Dividend Discount Model (DDM) -- Gordon Growth & two-stage variant."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fundamentals.valuation import ValuationResult

from fundamentals.models import FundamentalProfile, ScreenerRawData

logger = logging.getLogger(__name__)

# ---------- India-centric defaults ----------
COST_OF_EQUITY = 0.13  # ~13% (Rf 7% + Beta*ERP 6%)
MAX_STAGE1_GROWTH = 0.20  # Cap high-growth phase at 20%
TERMINAL_GROWTH_CAP = 0.06  # Max sustainable terminal growth
STAGE1_YEARS = 5


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


class DDMValuation:
    """Two-stage Dividend Discount Model.

    Stage 1: higher growth for *STAGE1_YEARS* years.
    Stage 2: perpetuity at sustainable growth.

    Best suited for banks, utilities, and mature dividend payers.
    """

    # ------------------------------------------------------------------ #
    #  helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sustainable_growth(roe_pct: float, payout_pct: float) -> float:
        """g = ROE * (1 - payout_ratio)."""
        roe = roe_pct / 100.0 if roe_pct > 1 else roe_pct
        payout = payout_pct / 100.0 if payout_pct > 1 else payout_pct
        payout = max(min(payout, 0.95), 0.0)
        return roe * (1 - payout)

    @staticmethod
    def _current_dps(profile: FundamentalProfile) -> float:
        """Derive current DPS = EPS * payout_ratio."""
        if not profile.eps_ttm or profile.eps_ttm <= 0:
            return 0.0
        payout = profile.dividend_payout_ratio
        if payout <= 0:
            # Try deriving from dividend_yield
            if profile.dividend_yield > 0 and profile.current_price > 0:
                return profile.current_price * (profile.dividend_yield / 100.0)
            return 0.0
        payout_frac = payout / 100.0 if payout > 1 else payout
        return profile.eps_ttm * payout_frac

    # ------------------------------------------------------------------ #
    #  valuation
    # ------------------------------------------------------------------ #

    def _gordon_growth(
        self,
        dps: float,
        ke: float,
        g: float,
    ) -> float:
        """Simple Gordon Growth: D1 / (Ke - g)."""
        d1 = dps * (1 + g)
        if ke <= g:
            return 0.0
        return d1 / (ke - g)

    def _two_stage(
        self,
        dps: float,
        g1: float,
        g2: float,
        ke: float,
    ) -> float:
        """Two-stage DDM.

        Stage 1: dividends grow at *g1* for STAGE1_YEARS.
        Stage 2: Gordon perpetuity at *g2*.
        """
        pv_stage1 = 0.0
        div = dps
        for yr in range(1, STAGE1_YEARS + 1):
            div *= 1 + g1
            pv_stage1 += div / (1 + ke) ** yr

        # Terminal value at end of stage 1
        terminal_div = div * (1 + g2)
        if ke <= g2:
            return pv_stage1  # Cannot compute terminal
        terminal_value = terminal_div / (ke - g2)
        pv_terminal = terminal_value / (1 + ke) ** STAGE1_YEARS

        return pv_stage1 + pv_terminal

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

        # ---- Guard: non-dividend payers ----
        dps = self._current_dps(profile)
        if dps <= 0:
            return ValuationResult(
                symbol=profile.symbol,
                model="ddm",
                current_price=profile.current_price,
                signal="NOT_APPLICABLE",
                confidence="LOW",
                assumptions=[
                    "No dividends detected; DDM not applicable",
                ],
            )

        assumptions.append(f"Current DPS: {dps:.2f}")

        # ---- Ke ----
        ke = COST_OF_EQUITY
        # Slightly lower Ke for banks (stable, regulated)
        if profile.is_banking:
            ke = 0.12
            assumptions.append("Banking: Ke adjusted to 12%")
        assumptions.append(f"Cost of equity: {ke*100:.1f}%")

        # ---- Growth rates ----
        payout_pct = profile.dividend_payout_ratio
        if payout_pct <= 0 and profile.dividend_yield > 0 and (profile.eps_ttm or 0) > 0:
            payout_pct = (dps / profile.eps_ttm) * 100
        assumptions.append(f"Payout ratio: {payout_pct:.1f}%")

        g_sustainable = self._sustainable_growth(profile.roe or 0, payout_pct)

        # Stage 1 growth: best of profit growth and sustainable, capped
        g1_candidates = [
            profile.profit_growth_3y / 100.0 if profile.profit_growth_3y > 0 else 0,
            profile.profit_growth_5y / 100.0 if profile.profit_growth_5y > 0 else 0,
            g_sustainable,
        ]
        g1 = min(max(g1_candidates), MAX_STAGE1_GROWTH)
        if g1 <= 0:
            g1 = g_sustainable if g_sustainable > 0 else 0.08
            assumptions.append("No positive growth data; using fallback 8%")

        # Terminal growth
        g2 = min(g_sustainable, TERMINAL_GROWTH_CAP)
        if g2 <= 0:
            g2 = 0.04  # 4% floor for India
            assumptions.append("Terminal growth floored at 4%")

        assumptions.append(f"Stage-1 growth (5yr): {g1*100:.1f}%")
        assumptions.append(f"Terminal growth: {g2*100:.1f}%")

        # ---- Compute ----
        if abs(g1 - g2) < 0.005:
            # Single-stage Gordon
            fair_value = self._gordon_growth(dps, ke, g2)
            assumptions.append("Single-stage Gordon (g1 ~ g2)")
        else:
            fair_value = self._two_stage(dps, g1, g2, ke)
            assumptions.append("Two-stage DDM applied")

        fair_value = max(fair_value, 0)

        # ---- Margin of safety ----
        mos = (
            (fair_value - profile.current_price) / fair_value * 100
            if fair_value > 0
            else 0
        )

        if mos > 20:
            signal = "UNDERVALUED"
        elif mos < -20:
            signal = "OVERVALUED"
        else:
            signal = "FAIR"

        # Confidence adjustments
        if profile.dividend_years_5 and profile.dividend_years_5 >= 5:
            confidence = "HIGH"
            assumptions.append("5+ years of dividends; high confidence")
        if payout_pct > 90:
            confidence = "LOW"
            assumptions.append("Very high payout (>90%); may not sustain")
        if profile.dividend_growing:
            assumptions.append("Dividend is growing -- positive signal")

        return ValuationResult(
            symbol=profile.symbol,
            model="ddm",
            fair_value=round(fair_value, 2),
            current_price=profile.current_price,
            margin_of_safety_pct=round(mos, 2),
            signal=signal,
            confidence=confidence,
            details={
                "dps": round(dps, 2),
                "ke_pct": round(ke * 100, 2),
                "g1_pct": round(g1 * 100, 2),
                "g2_pct": round(g2 * 100, 2),
                "g_sustainable_pct": round(g_sustainable * 100, 2),
                "payout_ratio_pct": round(payout_pct, 2),
            },
            assumptions=assumptions,
        )
