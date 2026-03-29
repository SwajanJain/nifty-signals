"""Monte Carlo fair-value estimation via randomised DCF simulations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from fundamentals.valuation import ValuationResult

from fundamentals.models import FundamentalProfile, ScreenerRawData

logger = logging.getLogger(__name__)

# ---------- Simulation defaults ----------
DEFAULT_SIMULATIONS = 1000
PROJECTION_YEARS = 5

# India-centric parameter ranges
WACC_LOW = 0.10
WACC_HIGH = 0.16
TERMINAL_GROWTH_LOW = 0.03
TERMINAL_GROWTH_HIGH = 0.05
DEFAULT_TAX_RATE = 0.25
GROWTH_STD_FRACTION = 0.30  # standard-deviation = 30% of mean growth
MARGIN_STD_FRACTION = 0.15  # standard-deviation = 15% of mean margin


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


class MonteCarloValuation:
    """Run *N* randomised DCF scenarios and report percentile outcomes."""

    # ------------------------------------------------------------------ #
    #  helpers (mirrored from dcf.py but kept self-contained)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_latest_row(
        table: list, label: str, fallback: float = 0.0
    ) -> float:
        target = label.lower()
        for row in table:
            row_label = row.get("label", "").strip().rstrip("+").strip().lower()
            if row_label == target or target in row_label:
                year_keys = sorted(
                    (k for k in row if k != "label"), reverse=True
                )
                for yk in year_keys:
                    try:
                        return float(str(row[yk]).replace(",", ""))
                    except (ValueError, TypeError):
                        continue
        return fallback

    @staticmethod
    def _get_base_fcf(
        profile: FundamentalProfile,
        raw: ScreenerRawData,
    ) -> float:
        """Return best-available base FCF in Cr."""
        if profile.free_cash_flow and profile.free_cash_flow > 0:
            return profile.free_cash_flow

        ocf = MonteCarloValuation._extract_latest_row(
            raw.cash_flow, "cash from operating activity"
        )
        capex = abs(
            MonteCarloValuation._extract_latest_row(
                raw.cash_flow, "fixed assets purchased"
            )
        ) or abs(
            MonteCarloValuation._extract_latest_row(
                raw.cash_flow, "purchase of fixed assets"
            )
        )
        fcf = ocf - capex
        if fcf > 0:
            return fcf

        if profile.operating_cash_flow and profile.operating_cash_flow > 0:
            return profile.operating_cash_flow
        if ocf > 0:
            return ocf
        return 0.0

    @staticmethod
    def _get_mean_growth(profile: FundamentalProfile) -> float:
        """Best available growth rate as a decimal (e.g. 0.12)."""
        candidates = [
            profile.profit_growth_3y,
            profile.profit_growth_5y,
            profile.revenue_growth_3y,
            profile.revenue_growth_5y,
        ]
        for rate in candidates:
            if rate and rate > 0:
                return min(rate / 100.0, 0.35)  # cap 35%
        return 0.10  # fallback

    # ------------------------------------------------------------------ #
    #  core simulation (vectorised with numpy)
    # ------------------------------------------------------------------ #

    def _simulate(
        self,
        base_fcf: float,
        mean_growth: float,
        shares: float,
        net_debt: float,
        n: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Return array of *n* per-share fair-value estimates."""

        # Sample parameters
        growth_std = max(mean_growth * GROWTH_STD_FRACTION, 0.02)
        growths = rng.normal(mean_growth, growth_std, size=n)
        growths = np.clip(growths, -0.05, 0.40)  # floor -5%, cap 40%

        waccs = rng.uniform(WACC_LOW, WACC_HIGH, size=n)
        term_gs = rng.uniform(TERMINAL_GROWTH_LOW, TERMINAL_GROWTH_HIGH, size=n)

        # Ensure WACC > terminal growth (else perpetuity blows up)
        valid = waccs > term_gs + 0.01
        # For invalid rows, bump WACC
        waccs = np.where(valid, waccs, term_gs + 0.02)

        fair_values = np.zeros(n)

        for i in range(n):
            g = growths[i]
            wacc = waccs[i]
            tg = term_gs[i]

            # Project FCFs
            pv_fcfs = 0.0
            fcf = base_fcf
            for yr in range(1, PROJECTION_YEARS + 1):
                fcf *= 1 + g
                pv_fcfs += fcf / (1 + wacc) ** yr

            # Terminal
            term_fcf = fcf * (1 + tg)
            tv = term_fcf / (wacc - tg)
            pv_tv = tv / (1 + wacc) ** PROJECTION_YEARS

            ev = pv_fcfs + pv_tv  # enterprise value in Cr
            equity = ev - net_debt
            fv_per_share = max(equity * 1e7 / shares, 0) if shares > 0 else 0
            fair_values[i] = fv_per_share

        return fair_values

    # ------------------------------------------------------------------ #
    #  main entry
    # ------------------------------------------------------------------ #

    def value(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData,
        simulations: int = DEFAULT_SIMULATIONS,
    ) -> "ValuationResult":
        from fundamentals.valuation import ValuationResult

        assumptions: list[str] = []
        confidence = "MEDIUM"

        # Shares outstanding
        shares = _safe_div(
            profile.market_cap * 1e7,
            profile.current_price,
            default=0,
        )
        if shares <= 0:
            return ValuationResult(
                symbol=profile.symbol,
                model="monte_carlo",
                current_price=profile.current_price,
                signal="NOT_APPLICABLE",
                confidence="LOW",
                assumptions=["Cannot compute shares outstanding"],
            )

        base_fcf = self._get_base_fcf(profile, raw)
        if base_fcf <= 0:
            return ValuationResult(
                symbol=profile.symbol,
                model="monte_carlo",
                current_price=profile.current_price,
                signal="NOT_APPLICABLE",
                confidence="LOW",
                assumptions=["FCF/OCF non-positive; Monte Carlo not feasible"],
            )

        mean_growth = self._get_mean_growth(profile)

        # Net debt
        borrowings = self._extract_latest_row(raw.balance_sheet, "borrowings")
        cash_proxy = self._extract_latest_row(raw.balance_sheet, "cash equivalents")
        if cash_proxy <= 0:
            investments = self._extract_latest_row(raw.balance_sheet, "investments")
            cash_proxy = investments * 0.3
        net_debt = max(borrowings - cash_proxy, 0)

        if profile.is_banking:
            assumptions.append("Banking company; DCF-based MC less reliable")
            confidence = "LOW"

        assumptions.append(f"Simulations: {simulations}")
        assumptions.append(f"Base FCF: {base_fcf:.1f} Cr")
        assumptions.append(f"Mean growth: {mean_growth*100:.1f}%")
        assumptions.append(f"WACC range: {WACC_LOW*100:.0f}-{WACC_HIGH*100:.0f}%")
        assumptions.append(
            f"Terminal growth range: {TERMINAL_GROWTH_LOW*100:.0f}-"
            f"{TERMINAL_GROWTH_HIGH*100:.0f}%"
        )

        # Run simulation
        rng = np.random.default_rng(seed=42)  # reproducible
        fair_values = self._simulate(
            base_fcf=base_fcf,
            mean_growth=mean_growth,
            shares=shares,
            net_debt=net_debt,
            n=simulations,
            rng=rng,
        )

        # Percentiles
        bear_case = float(np.percentile(fair_values, 10))
        base_case = float(np.percentile(fair_values, 50))
        bull_case = float(np.percentile(fair_values, 90))
        prob_undervalued = float(
            np.mean(fair_values > profile.current_price) * 100
        )

        fair_value = base_case  # median is our point estimate

        mos = (
            (fair_value - profile.current_price) / fair_value * 100
            if fair_value > 0
            else 0
        )

        # Signal
        if prob_undervalued >= 70:
            signal = "UNDERVALUED"
        elif prob_undervalued <= 30:
            signal = "OVERVALUED"
        else:
            signal = "FAIR"

        # Confidence from spread
        spread_pct = (
            (bull_case - bear_case) / base_case * 100
            if base_case > 0
            else 0
        )
        if spread_pct > 150:
            confidence = "LOW"
            assumptions.append(
                f"Wide valuation spread ({spread_pct:.0f}%); low confidence"
            )
        elif spread_pct < 60 and confidence != "LOW":
            confidence = "HIGH"
            assumptions.append(
                f"Tight valuation spread ({spread_pct:.0f}%); high confidence"
            )

        return ValuationResult(
            symbol=profile.symbol,
            model="monte_carlo",
            fair_value=round(fair_value, 2),
            current_price=profile.current_price,
            margin_of_safety_pct=round(mos, 2),
            signal=signal,
            confidence=confidence,
            details={
                "bear_case": round(bear_case, 2),
                "base_case": round(base_case, 2),
                "bull_case": round(bull_case, 2),
                "prob_undervalued": round(prob_undervalued, 2),
                "spread_pct": round(spread_pct, 2),
                "mean_growth_pct": round(mean_growth * 100, 2),
                "base_fcf_cr": round(base_fcf, 2),
                "net_debt_cr": round(net_debt, 2),
                "simulations": simulations,
            },
            assumptions=assumptions,
        )
