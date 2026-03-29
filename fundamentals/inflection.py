"""Fundamental Inflection Detector (E1) — Detect early multibagger turning points.

Identifies companies at fundamental inflection points where revenue is
accelerating, margins are expanding, operating leverage is kicking in,
and/or cash flows are inflecting positive. These are the earliest signals
of a potential multibagger.

Inflection signals detected:
1. Revenue Acceleration — revenue growth rate itself is increasing
2. Operating Leverage — operating profit growing faster than revenue
3. Margin Expansion — OPM/NPM trending upward over 3+ quarters
4. Earnings Acceleration — EPS growth rate accelerating quarter over quarter
5. Cash Flow Inflection — OCF or FCF turning positive after being negative

NOTE: Inflection detection is heuristic-based and has not been backtested.
Signals should be treated as hypotheses requiring manual verification,
not confirmed inflection points. The scoring is directional guidance only.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from fundamentals.models import FundamentalProfile, ScreenerRawData


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class InflectionSignal:
    """A single inflection signal with type, strength, evidence, and score."""

    signal_type: str
    # "REVENUE_ACCELERATION", "OPERATING_LEVERAGE", "MARGIN_EXPANSION",
    # "EARNINGS_ACCELERATION", "CASH_FLOW_INFLECTION"
    strength: str  # "STRONG", "MODERATE", "EARLY"
    evidence: List[str] = field(default_factory=list)
    score: int = 0  # 0-100


@dataclass
class InflectionResult:
    """Composite inflection analysis for a single stock."""

    symbol: str
    has_inflection: bool = False
    inflection_score: int = 0  # 0-100 composite
    signals: List[InflectionSignal] = field(default_factory=list)
    stage: str = "NO_INFLECTION"
    # "NO_INFLECTION", "EARLY_INFLECTION", "CONFIRMED_INFLECTION",
    # "MATURE_INFLECTION"
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_quarterly_series(
    quarterly_results: List[Dict[str, Any]],
    label: str,
) -> List[Optional[float]]:
    """Extract a quarterly time-series for *label* from raw quarterly data.

    Returns values in order as they appear in the dict (most recent first,
    matching screener.in convention).
    """
    if not quarterly_results:
        return []

    label_lower = label.lower()
    for row in quarterly_results:
        row_label = str(row.get("label", "")).lower()
        if label_lower in row_label:
            values: List[Optional[float]] = []
            for key, val in row.items():
                if key == "label":
                    continue
                try:
                    values.append(float(val))
                except (TypeError, ValueError):
                    values.append(None)
            return values
    return []


def _safe_yoy_growth(current: Optional[float], year_ago: Optional[float]) -> Optional[float]:
    """Compute YoY growth %, returning None if inputs are invalid."""
    if current is None or year_ago is None:
        return None
    if year_ago == 0:
        return None if current == 0 else 100.0
    return round((current - year_ago) / abs(year_ago) * 100, 2)


def _compute_yoy_growth_series(
    values: List[Optional[float]],
) -> List[Optional[float]]:
    """Given quarterly values (most-recent-first), compute YoY growth for each
    quarter that has a same-quarter-last-year counterpart (index + 4).

    Returns a list aligned to positions 0..len-5 (most recent first).
    """
    growths: List[Optional[float]] = []
    for i in range(len(values) - 4):
        growths.append(_safe_yoy_growth(values[i], values[i + 4]))
    return growths


def _find_cash_flow_row(
    cash_flow: List[Dict[str, Any]],
    label: str,
) -> Optional[Dict[str, Any]]:
    """Find a row in the cash flow table by partial label match."""
    label_lower = label.lower()
    for row in cash_flow:
        row_label = str(row.get("label", "")).lower()
        if label_lower in row_label or row_label in label_lower:
            return row
    return None


def _get_annual_values(row: Dict[str, Any]) -> List[Optional[float]]:
    """Extract ordered numeric values from a row dict, skipping 'label'."""
    values: List[Optional[float]] = []
    for key, val in row.items():
        if key == "label":
            continue
        if isinstance(val, (int, float)):
            values.append(float(val))
        else:
            values.append(None)
    return values


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class InflectionDetector:
    """Detect fundamental inflection points from quarterly and annual data."""

    def detect(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData,
    ) -> InflectionResult:
        """Run all inflection detectors and return composite result.

        Parameters
        ----------
        profile : Computed fundamental profile.
        raw     : Raw screener data with quarterly_results, cash_flow, etc.
        """
        signals: List[InflectionSignal] = []

        rev_signal = self._detect_revenue_acceleration(profile, raw)
        if rev_signal:
            signals.append(rev_signal)

        leverage_signal = self._detect_operating_leverage(profile, raw)
        if leverage_signal:
            signals.append(leverage_signal)

        margin_signal = self._detect_margin_expansion(raw)
        if margin_signal:
            signals.append(margin_signal)

        eps_signal = self._detect_earnings_acceleration(raw)
        if eps_signal:
            signals.append(eps_signal)

        cf_signal = self._detect_cash_flow_inflection(raw)
        if cf_signal:
            signals.append(cf_signal)

        # Composite score: weighted average of signal scores, capped at 100
        if signals:
            # Weight order-win/expansion type signals higher
            weight_map = {
                "REVENUE_ACCELERATION": 1.2,
                "OPERATING_LEVERAGE": 1.1,
                "MARGIN_EXPANSION": 1.0,
                "EARNINGS_ACCELERATION": 1.3,
                "CASH_FLOW_INFLECTION": 0.9,
            }
            weighted_sum = sum(
                s.score * weight_map.get(s.signal_type, 1.0) for s in signals
            )
            total_weight = sum(
                weight_map.get(s.signal_type, 1.0) for s in signals
            )
            composite = int(round(weighted_sum / total_weight)) if total_weight else 0
        else:
            composite = 0

        # Determine stage
        strong_count = sum(1 for s in signals if s.strength == "STRONG")
        moderate_count = sum(1 for s in signals if s.strength == "MODERATE")

        if strong_count >= 3 or (strong_count >= 2 and moderate_count >= 1):
            stage = "MATURE_INFLECTION"
        elif strong_count >= 1 and len(signals) >= 2:
            stage = "CONFIRMED_INFLECTION"
        elif len(signals) >= 1:
            stage = "EARLY_INFLECTION"
        else:
            stage = "NO_INFLECTION"

        return InflectionResult(
            symbol=profile.symbol,
            has_inflection=len(signals) > 0,
            inflection_score=min(100, composite),
            signals=signals,
            stage=stage,
            details={
                "signal_count": len(signals),
                "strong_signals": strong_count,
                "moderate_signals": moderate_count,
                "early_signals": sum(
                    1 for s in signals if s.strength == "EARLY"
                ),
                "signal_types": [s.signal_type for s in signals],
            },
        )

    # ------------------------------------------------------------------
    # 1. Revenue Acceleration
    # ------------------------------------------------------------------

    def _detect_revenue_acceleration(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData,
    ) -> Optional[InflectionSignal]:
        """Revenue growth rate is itself increasing quarter-over-quarter.

        We compute YoY revenue growth for each of the last 3-4 quarters and
        check if the growth rate is accelerating (latest > previous > earlier).
        """
        sales = _get_quarterly_series(raw.quarterly_results, "sales")
        if len(sales) < 8:
            return None

        yoy_growths = _compute_yoy_growth_series(sales)
        # Need at least 3 YoY growth values to detect acceleration
        valid = [g for g in yoy_growths[:4] if g is not None]
        if len(valid) < 3:
            return None

        # Check acceleration: each successive quarter grows faster
        accelerating_count = 0
        for i in range(len(valid) - 1):
            if valid[i] > valid[i + 1]:
                accelerating_count += 1

        evidence = []
        for i, g in enumerate(valid[:4]):
            quarter_label = f"Q-{i}" if i > 0 else "Latest Q"
            evidence.append(f"{quarter_label} revenue YoY: {g:.1f}%")

        if accelerating_count >= 3:
            strength = "STRONG"
            score = 85
        elif accelerating_count >= 2:
            strength = "MODERATE"
            score = 60
        elif accelerating_count >= 1 and valid[0] is not None and valid[0] > 20:
            strength = "EARLY"
            score = 40
        else:
            return None

        # Bonus if absolute growth is also high
        if valid[0] is not None and valid[0] > 30:
            score = min(100, score + 10)
            evidence.append(f"Latest quarter growth {valid[0]:.1f}% is exceptional")

        return InflectionSignal(
            signal_type="REVENUE_ACCELERATION",
            strength=strength,
            evidence=evidence,
            score=score,
        )

    # ------------------------------------------------------------------
    # 2. Operating Leverage
    # ------------------------------------------------------------------

    def _detect_operating_leverage(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData,
    ) -> Optional[InflectionSignal]:
        """Operating profit growing significantly faster than revenue.

        Operating leverage = profit growth >> revenue growth (ratio > 1.5x).
        """
        evidence = []

        # Use profile-level growth rates first
        rev_growth = profile.revenue_growth_3y
        profit_growth = profile.profit_growth_3y

        # Also check quarterly for more recent signal
        sales = _get_quarterly_series(raw.quarterly_results, "sales")
        op_profit = _get_quarterly_series(raw.quarterly_results, "operating_profit")

        quarterly_leverage = False
        if len(sales) >= 5 and len(op_profit) >= 5:
            rev_yoy = _safe_yoy_growth(sales[0], sales[4])
            op_yoy = _safe_yoy_growth(op_profit[0], op_profit[4])

            if rev_yoy is not None and op_yoy is not None and rev_yoy > 0:
                leverage_ratio = op_yoy / rev_yoy if rev_yoy != 0 else 0
                evidence.append(
                    f"Latest Q: Revenue YoY {rev_yoy:.1f}%, "
                    f"OP YoY {op_yoy:.1f}% (leverage ratio: {leverage_ratio:.1f}x)"
                )
                if leverage_ratio >= 1.5:
                    quarterly_leverage = True

        # Check annual-level operating leverage
        annual_leverage = False
        if rev_growth > 5 and profit_growth > 0:
            annual_ratio = profit_growth / rev_growth if rev_growth != 0 else 0
            evidence.append(
                f"3Y CAGR: Revenue {rev_growth:.0f}%, "
                f"Profit {profit_growth:.0f}% (ratio: {annual_ratio:.1f}x)"
            )
            if annual_ratio >= 1.5:
                annual_leverage = True

        # OPM expansion confirmation
        opm_values = _get_quarterly_series(raw.quarterly_results, "opm")
        if len(opm_values) >= 4:
            valid_opm = [v for v in opm_values[:4] if v is not None]
            if len(valid_opm) >= 3:
                if valid_opm[0] > valid_opm[-1]:
                    evidence.append(
                        f"OPM expanding: {valid_opm[-1]:.1f}% -> {valid_opm[0]:.1f}%"
                    )

        if quarterly_leverage and annual_leverage:
            return InflectionSignal(
                signal_type="OPERATING_LEVERAGE",
                strength="STRONG",
                evidence=evidence,
                score=80,
            )
        elif quarterly_leverage or annual_leverage:
            return InflectionSignal(
                signal_type="OPERATING_LEVERAGE",
                strength="MODERATE",
                evidence=evidence,
                score=55,
            )
        elif profit_growth > rev_growth * 1.2 and profit_growth > 15:
            evidence.append("Profit growing modestly faster than revenue")
            return InflectionSignal(
                signal_type="OPERATING_LEVERAGE",
                strength="EARLY",
                evidence=evidence,
                score=35,
            )

        return None

    # ------------------------------------------------------------------
    # 3. Margin Expansion
    # ------------------------------------------------------------------

    def _detect_margin_expansion(
        self,
        raw: ScreenerRawData,
    ) -> Optional[InflectionSignal]:
        """OPM and/or NPM trending upward over 3+ consecutive quarters."""
        opm_values = _get_quarterly_series(raw.quarterly_results, "opm")
        evidence = []
        opm_expanding_quarters = 0
        npm_expanding_quarters = 0

        # OPM expansion (most-recent-first, so check if [i] > [i+1])
        if len(opm_values) >= 4:
            valid_opm = [v for v in opm_values[:6] if v is not None]
            if len(valid_opm) >= 3:
                for i in range(len(valid_opm) - 1):
                    if valid_opm[i] > valid_opm[i + 1]:
                        opm_expanding_quarters += 1
                    else:
                        break

                if opm_expanding_quarters >= 2:
                    evidence.append(
                        f"OPM expanding {opm_expanding_quarters + 1} quarters: "
                        f"{valid_opm[opm_expanding_quarters]:.1f}% -> {valid_opm[0]:.1f}%"
                    )

        # NPM expansion: compute from net_profit / sales
        sales = _get_quarterly_series(raw.quarterly_results, "sales")
        net_profit = _get_quarterly_series(raw.quarterly_results, "net_profit")

        if len(sales) >= 4 and len(net_profit) >= 4:
            min_len = min(len(sales), len(net_profit), 6)
            npms: List[Optional[float]] = []
            for i in range(min_len):
                s = sales[i]
                p = net_profit[i]
                if s is not None and p is not None and s > 0:
                    npms.append(round(p / s * 100, 2))
                else:
                    npms.append(None)

            valid_npm = [v for v in npms if v is not None]
            if len(valid_npm) >= 3:
                for i in range(len(valid_npm) - 1):
                    if valid_npm[i] > valid_npm[i + 1]:
                        npm_expanding_quarters += 1
                    else:
                        break

                if npm_expanding_quarters >= 2:
                    evidence.append(
                        f"NPM expanding {npm_expanding_quarters + 1} quarters: "
                        f"{valid_npm[npm_expanding_quarters]:.1f}% -> {valid_npm[0]:.1f}%"
                    )

        total_quarters = max(opm_expanding_quarters, npm_expanding_quarters)
        both_expanding = opm_expanding_quarters >= 2 and npm_expanding_quarters >= 2

        if both_expanding or total_quarters >= 4:
            return InflectionSignal(
                signal_type="MARGIN_EXPANSION",
                strength="STRONG",
                evidence=evidence,
                score=75,
            )
        elif total_quarters >= 3:
            return InflectionSignal(
                signal_type="MARGIN_EXPANSION",
                strength="MODERATE",
                evidence=evidence,
                score=55,
            )
        elif total_quarters >= 2:
            return InflectionSignal(
                signal_type="MARGIN_EXPANSION",
                strength="EARLY",
                evidence=evidence,
                score=35,
            )

        return None

    # ------------------------------------------------------------------
    # 4. Earnings Acceleration
    # ------------------------------------------------------------------

    def _detect_earnings_acceleration(
        self,
        raw: ScreenerRawData,
    ) -> Optional[InflectionSignal]:
        """EPS growth rate accelerating: recent quarters growing faster than
        older quarters.
        """
        eps = _get_quarterly_series(raw.quarterly_results, "eps")
        if len(eps) < 8:
            return None

        yoy_growths = _compute_yoy_growth_series(eps)
        valid = [g for g in yoy_growths[:4] if g is not None]
        if len(valid) < 3:
            return None

        evidence = []
        for i, g in enumerate(valid[:4]):
            quarter_label = f"Q-{i}" if i > 0 else "Latest Q"
            evidence.append(f"{quarter_label} EPS YoY: {g:.1f}%")

        # Count how many successive quarters show acceleration
        accelerating = 0
        for i in range(len(valid) - 1):
            if valid[i] > valid[i + 1]:
                accelerating += 1

        # Also check if latest growth is positive and strong
        latest_positive_and_strong = (
            valid[0] is not None and valid[0] > 20
        )

        if accelerating >= 3:
            strength = "STRONG"
            score = 85
        elif accelerating >= 2:
            strength = "MODERATE"
            score = 60
        elif accelerating >= 1 and latest_positive_and_strong:
            strength = "EARLY"
            score = 40
        else:
            return None

        # Bonus for high absolute EPS growth
        if valid[0] is not None and valid[0] > 50:
            score = min(100, score + 10)
            evidence.append(f"Latest EPS growth {valid[0]:.1f}% is exceptional")

        return InflectionSignal(
            signal_type="EARNINGS_ACCELERATION",
            strength=strength,
            evidence=evidence,
            score=score,
        )

    # ------------------------------------------------------------------
    # 5. Cash Flow Inflection
    # ------------------------------------------------------------------

    def _detect_cash_flow_inflection(
        self,
        raw: ScreenerRawData,
    ) -> Optional[InflectionSignal]:
        """OCF or FCF turning positive after being negative.

        Checks the annual cash flow statement for sign changes from
        negative to positive in operating cash flow or free cash flow.
        """
        if not raw.cash_flow:
            return None

        evidence = []
        ocf_inflection = False
        fcf_inflection = False

        # OCF inflection
        ocf_row = _find_cash_flow_row(raw.cash_flow, "Cash from Operating Activity")
        if ocf_row:
            ocf_values = _get_annual_values(ocf_row)
            valid_ocf = [v for v in ocf_values if v is not None]

            if len(valid_ocf) >= 2:
                latest = valid_ocf[-1]
                prior = valid_ocf[-2]

                if latest > 0 and prior < 0:
                    ocf_inflection = True
                    evidence.append(
                        f"OCF turned positive: {prior:.0f} Cr -> {latest:.0f} Cr"
                    )
                elif latest > 0 and len(valid_ocf) >= 3 and valid_ocf[-3] < 0:
                    ocf_inflection = True
                    evidence.append(
                        f"OCF inflected positive 2 years ago, sustained: "
                        f"{valid_ocf[-3]:.0f} -> {prior:.0f} -> {latest:.0f} Cr"
                    )

        # FCF inflection (OCF + Investing CF)
        capex_row = _find_cash_flow_row(raw.cash_flow, "Cash from Investing Activity")
        if ocf_row and capex_row:
            ocf_values = _get_annual_values(ocf_row)
            capex_values = _get_annual_values(capex_row)
            min_len = min(len(ocf_values), len(capex_values))

            if min_len >= 2:
                fcf_values = []
                for i in range(min_len):
                    o = ocf_values[i]
                    c = capex_values[i]
                    if o is not None and c is not None:
                        fcf_values.append(o + c)  # capex is typically negative
                    else:
                        fcf_values.append(None)

                valid_fcf = [v for v in fcf_values if v is not None]
                if len(valid_fcf) >= 2:
                    latest_fcf = valid_fcf[-1]
                    prior_fcf = valid_fcf[-2]

                    if latest_fcf > 0 and prior_fcf < 0:
                        fcf_inflection = True
                        evidence.append(
                            f"FCF turned positive: {prior_fcf:.0f} Cr -> "
                            f"{latest_fcf:.0f} Cr"
                        )

        if not evidence:
            return None

        if ocf_inflection and fcf_inflection:
            return InflectionSignal(
                signal_type="CASH_FLOW_INFLECTION",
                strength="STRONG",
                evidence=evidence,
                score=75,
            )
        elif ocf_inflection or fcf_inflection:
            return InflectionSignal(
                signal_type="CASH_FLOW_INFLECTION",
                strength="MODERATE",
                evidence=evidence,
                score=50,
            )

        return None
