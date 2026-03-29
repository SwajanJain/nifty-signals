"""Peer-relative valuation using sector benchmark multiples."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from fundamentals.valuation import ValuationResult

from fundamentals.models import FundamentalProfile, ScreenerRawData

logger = logging.getLogger(__name__)

# ---------- Indian-market sector median multiples ----------
# Sector benchmarks as of Mar 2025 — review quarterly.
# Source: NSE sector indices / screener.in sector pages.
# EV/EBITDA = 0 means the metric is not meaningful for that sector (e.g., banks).
BENCHMARKS_LAST_UPDATED = '2025-03'

SECTOR_BENCHMARKS: Dict[str, Dict[str, float]] = {
    "IT": {"pe": 25, "pb": 6.0, "ev_ebitda": 18},
    "Banking": {"pe": 12, "pb": 2.0, "ev_ebitda": 0},
    "Financial Services": {"pe": 20, "pb": 3.0, "ev_ebitda": 15},
    "Pharma": {"pe": 28, "pb": 4.0, "ev_ebitda": 18},
    "Auto": {"pe": 22, "pb": 4.0, "ev_ebitda": 14},
    "FMCG": {"pe": 45, "pb": 12.0, "ev_ebitda": 30},
    "Metals": {"pe": 10, "pb": 1.5, "ev_ebitda": 7},
    "Oil & Gas": {"pe": 12, "pb": 1.5, "ev_ebitda": 8},
    "Power": {"pe": 15, "pb": 2.0, "ev_ebitda": 10},
    "Cement": {"pe": 28, "pb": 4.0, "ev_ebitda": 14},
    "Chemicals": {"pe": 30, "pb": 5.0, "ev_ebitda": 18},
    "Real Estate": {"pe": 25, "pb": 3.0, "ev_ebitda": 15},
    "Telecom": {"pe": 50, "pb": 3.0, "ev_ebitda": 10},
    "Consumer": {"pe": 40, "pb": 8.0, "ev_ebitda": 25},
    "Healthcare": {"pe": 30, "pb": 5.0, "ev_ebitda": 20},
    "Insurance": {"pe": 20, "pb": 3.5, "ev_ebitda": 0},
    "Capital Goods": {"pe": 35, "pb": 5.0, "ev_ebitda": 22},
    "Infra": {"pe": 20, "pb": 2.5, "ev_ebitda": 12},
    "Textiles": {"pe": 15, "pb": 2.0, "ev_ebitda": 10},
    "Media": {"pe": 20, "pb": 3.0, "ev_ebitda": 12},
    "Diversified": {"pe": 20, "pb": 3.0, "ev_ebitda": 15},
}

DEFAULT_BENCHMARKS: Dict[str, float] = {"pe": 22, "pb": 3.0, "ev_ebitda": 14}


def _premium_discount_pct(stock_val: float, benchmark: float) -> float:
    """Return % premium (+) or discount (-) vs benchmark.

    A *positive* number means the stock is *more expensive* than the benchmark.
    """
    if benchmark <= 0 or stock_val <= 0:
        return 0.0
    return ((stock_val - benchmark) / benchmark) * 100.0


def _match_sector(sector: str) -> tuple:
    """Fuzzy-match the profile sector to a benchmark key.

    Returns (benchmark_dict, matched_sector_name) so callers know which
    sector was used. Falls back to 'Market' (overall market average) if
    no sector matches.
    """
    sector_lower = sector.strip().lower()
    for key, bench in SECTOR_BENCHMARKS.items():
        if key.lower() in sector_lower or sector_lower in key.lower():
            return bench, key
    # Try partial token match
    for key, bench in SECTOR_BENCHMARKS.items():
        for token in key.lower().split():
            if token in sector_lower:
                return bench, key
    logger.debug(f"No sector benchmark match for '{sector}' — using Market default")
    return DEFAULT_BENCHMARKS, "Market"


class PeerRelativeValuation:
    """Compare a stock's multiples against sector medians.

    Optionally accepts a dict of real peer profiles for a richer
    comparison when available.
    """

    # ------------------------------------------------------------------ #
    #  peer-median computation (when real peers provided)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _peer_medians(
        peers: Dict[str, FundamentalProfile],
    ) -> Dict[str, float]:
        """Compute median PE, PB, EV/EBITDA across supplied peers."""
        pe_vals = sorted(p.pe_ratio for p in peers.values() if p.pe_ratio > 0)
        pb_vals = sorted(p.pb_ratio for p in peers.values() if p.pb_ratio > 0)
        ev_vals = sorted(p.ev_ebitda for p in peers.values() if p.ev_ebitda > 0)

        def _median(vals: list[float]) -> float:
            if not vals:
                return 0.0
            n = len(vals)
            mid = n // 2
            if n % 2 == 0:
                return (vals[mid - 1] + vals[mid]) / 2
            return vals[mid]

        return {
            "pe": _median(pe_vals),
            "pb": _median(pb_vals),
            "ev_ebitda": _median(ev_vals),
        }

    # ------------------------------------------------------------------ #
    #  implied fair value from a single multiple
    # ------------------------------------------------------------------ #

    @staticmethod
    def _implied_price_from_pe(
        benchmark_pe: float, eps: float
    ) -> float:
        if benchmark_pe <= 0 or eps <= 0:
            return 0.0
        return benchmark_pe * eps

    @staticmethod
    def _implied_price_from_pb(
        benchmark_pb: float, bvps: float
    ) -> float:
        if benchmark_pb <= 0 or bvps <= 0:
            return 0.0
        return benchmark_pb * bvps

    # ------------------------------------------------------------------ #
    #  main entry
    # ------------------------------------------------------------------ #

    def value(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData,
        peers: Optional[Dict[str, FundamentalProfile]] = None,
    ) -> "ValuationResult":
        from fundamentals.valuation import ValuationResult

        assumptions: list[str] = []
        confidence = "MEDIUM"

        # Pick benchmarks
        if peers and len(peers) >= 3:
            bench = self._peer_medians(peers)
            assumptions.append(f"Using real peer medians from {len(peers)} peers")
            confidence = "HIGH"
        else:
            bench, matched_sector = _match_sector(profile.sector)
            sector_label = profile.sector or "Unknown"
            if matched_sector == "Market":
                assumptions.append(
                    f"Sector '{sector_label}' not in benchmarks; using market defaults"
                )
                confidence = "LOW"
            else:
                assumptions.append(
                    f"Using sector benchmarks for '{matched_sector}' "
                    f"(benchmarks as of {BENCHMARKS_LAST_UPDATED})"
                )

        # ---------- Per-multiple analysis ----------
        multiples_compared = 0
        undervalued_count = 0
        overvalued_count = 0
        premium_discounts: Dict[str, float] = {}
        implied_prices: list[float] = []

        # P/E
        if profile.pe_ratio and profile.pe_ratio > 0 and bench["pe"] > 0:
            pd_pe = _premium_discount_pct(profile.pe_ratio, bench["pe"])
            premium_discounts["pe_premium_pct"] = round(pd_pe, 2)
            multiples_compared += 1
            if pd_pe < -20:
                undervalued_count += 1
            elif pd_pe > 20:
                overvalued_count += 1

            iv = self._implied_price_from_pe(bench["pe"], profile.eps_ttm)
            if iv > 0:
                implied_prices.append(iv)
                premium_discounts["implied_price_pe"] = round(iv, 2)
                assumptions.append(
                    f"PE: stock {profile.pe_ratio:.1f} vs sector {bench['pe']:.1f} "
                    f"({pd_pe:+.1f}%)"
                )

        # P/B
        if profile.pb_ratio and profile.pb_ratio > 0 and bench["pb"] > 0:
            pd_pb = _premium_discount_pct(profile.pb_ratio, bench["pb"])
            premium_discounts["pb_premium_pct"] = round(pd_pb, 2)
            multiples_compared += 1
            if pd_pb < -20:
                undervalued_count += 1
            elif pd_pb > 20:
                overvalued_count += 1

            iv = self._implied_price_from_pb(
                bench["pb"], profile.book_value_per_share
            )
            if iv > 0:
                implied_prices.append(iv)
                premium_discounts["implied_price_pb"] = round(iv, 2)
                assumptions.append(
                    f"PB: stock {profile.pb_ratio:.1f} vs sector {bench['pb']:.1f} "
                    f"({pd_pb:+.1f}%)"
                )

        # EV/EBITDA (skip for banking / sectors where it's 0)
        if (
            profile.ev_ebitda and profile.ev_ebitda > 0
            and bench.get("ev_ebitda", 0) > 0
            and not profile.is_banking
        ):
            pd_ev = _premium_discount_pct(profile.ev_ebitda, bench["ev_ebitda"])
            premium_discounts["ev_ebitda_premium_pct"] = round(pd_ev, 2)
            multiples_compared += 1
            if pd_ev < -20:
                undervalued_count += 1
            elif pd_ev > 20:
                overvalued_count += 1
            assumptions.append(
                f"EV/EBITDA: stock {profile.ev_ebitda:.1f} vs sector "
                f"{bench['ev_ebitda']:.1f} ({pd_ev:+.1f}%)"
            )

        # ---------- Composite fair value ----------
        if implied_prices:
            fair_value = sum(implied_prices) / len(implied_prices)
        else:
            fair_value = 0.0
            confidence = "LOW"
            assumptions.append("Could not compute implied prices; data insufficient")

        mos = (
            (fair_value - profile.current_price) / fair_value * 100
            if fair_value > 0
            else 0
        )

        # ---------- Signal ----------
        if multiples_compared == 0:
            signal = "NOT_APPLICABLE"
            confidence = "LOW"
        elif undervalued_count >= 2:
            signal = "UNDERVALUED"
        elif overvalued_count >= 2:
            signal = "OVERVALUED"
        elif mos > 15:
            signal = "UNDERVALUED"
        elif mos < -15:
            signal = "OVERVALUED"
        else:
            signal = "FAIR"

        premium_discounts["multiples_compared"] = multiples_compared
        premium_discounts["undervalued_metrics"] = undervalued_count
        premium_discounts["overvalued_metrics"] = overvalued_count

        return ValuationResult(
            symbol=profile.symbol,
            model="peer",
            fair_value=round(fair_value, 2),
            current_price=profile.current_price,
            margin_of_safety_pct=round(mos, 2),
            signal=signal,
            confidence=confidence,
            details=premium_discounts,
            assumptions=assumptions,
        )
