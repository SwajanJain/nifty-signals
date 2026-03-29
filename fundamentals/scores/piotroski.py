"""Piotroski F-Score (0-9) — financial strength indicator.

Uses annual P&L, balance sheet, and cash flow data from ScreenerRawData.

Criteria (9 points total):
  Profitability (4):
    1. ROA > 0
    2. Operating Cash Flow > 0
    3. ROA improved YoY (delta ROA > 0)
    4. Cash quality: OCF > Net Profit (accruals check)
  Leverage / Liquidity (3):
    5. Long-term debt / Total Assets decreased YoY
    6. Current ratio improved YoY
    7. No new equity issued (shares outstanding did not increase)
  Operating Efficiency (2):
    8. Gross margin (OPM) improved YoY
    9. Asset turnover (Revenue / Total Assets) improved YoY
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from fundamentals.models import FundamentalProfile, ScreenerRawData


@dataclass
class PiotroskiResult:
    """Result of Piotroski F-Score computation."""

    symbol: str
    f_score: int = 0  # 0-9
    criteria: Dict[str, bool] = field(default_factory=dict)
    zone: str = "WEAK"  # STRONG (>=7), MODERATE (>=4), WEAK (<4)
    details: List[str] = field(default_factory=list)


class PiotroskiFScore:
    """Compute the Piotroski F-Score from screener.in raw data."""

    def score(self, profile: FundamentalProfile, raw: ScreenerRawData) -> PiotroskiResult:
        """Compute Piotroski F-Score (0-9)."""
        result = PiotroskiResult(symbol=profile.symbol)

        criteria = {}
        details = []
        total = 0

        # ------------------------------------------------------------------
        # Extract required annual series
        # ------------------------------------------------------------------
        net_profit_curr, net_profit_prev = self._get_latest_two(raw.annual_pl, 'Net Profit')
        sales_curr, sales_prev = self._get_latest_two(raw.annual_pl, 'Sales')
        opm_curr, opm_prev = self._get_opm_two_years(raw)

        total_assets_curr, total_assets_prev = self._get_latest_two(raw.balance_sheet, 'Total Assets')
        borrowings_curr, borrowings_prev = self._get_latest_two(raw.balance_sheet, 'Borrowings')
        equity_cap_curr, equity_cap_prev = self._get_latest_two(raw.balance_sheet, 'Equity Capital')

        ocf_curr = self._get_latest_value_from_table(raw.cash_flow, 'Cash from Operating Activity')

        # Current ratio proxy: screener.in does not provide a separate current
        # assets/liabilities breakdown. Other Assets and Other Liabilities are
        # the closest available proxies. This may over/understate the true
        # current ratio.
        other_assets_curr, other_assets_prev = self._get_latest_two(raw.balance_sheet, 'Other Assets')
        other_liab_curr, other_liab_prev = self._get_latest_two(raw.balance_sheet, 'Other Liabilities')

        # ------------------------------------------------------------------
        # 1. ROA > 0
        # ------------------------------------------------------------------
        roa_curr = self._safe_divide(net_profit_curr, total_assets_curr)
        roa_pass = roa_curr is not None and roa_curr > 0
        criteria['roa_positive'] = roa_pass
        if roa_pass:
            total += 1
            details.append(f"ROA positive: {roa_curr:.2%}")
        else:
            details.append(f"ROA not positive: {self._fmt_pct(roa_curr)}")

        # ------------------------------------------------------------------
        # 2. Operating Cash Flow > 0
        # ------------------------------------------------------------------
        ocf_pass = ocf_curr is not None and ocf_curr > 0
        criteria['ocf_positive'] = ocf_pass
        if ocf_pass:
            total += 1
            details.append(f"OCF positive: {ocf_curr:,.0f} Cr")
        else:
            details.append(f"OCF not positive: {self._fmt_num(ocf_curr)}")

        # ------------------------------------------------------------------
        # 3. Delta ROA > 0 (ROA improved YoY)
        # ------------------------------------------------------------------
        roa_prev = self._safe_divide(net_profit_prev, total_assets_prev)
        if roa_curr is not None and roa_prev is not None:
            delta_roa = roa_curr - roa_prev
            delta_roa_pass = delta_roa > 0
            criteria['delta_roa_positive'] = delta_roa_pass
            if delta_roa_pass:
                total += 1
                details.append(f"ROA improved: {roa_prev:.2%} -> {roa_curr:.2%}")
            else:
                details.append(f"ROA declined: {roa_prev:.2%} -> {roa_curr:.2%}")
        else:
            criteria['delta_roa_positive'] = False
            details.append("ROA YoY: insufficient data")

        # ------------------------------------------------------------------
        # 4. Accruals: OCF > Net Profit (cash quality)
        # ------------------------------------------------------------------
        if ocf_curr is not None and net_profit_curr is not None:
            accrual_pass = ocf_curr > net_profit_curr
            criteria['accruals_quality'] = accrual_pass
            if accrual_pass:
                total += 1
                details.append(f"Cash quality good: OCF ({ocf_curr:,.0f}) > NP ({net_profit_curr:,.0f})")
            else:
                details.append(f"Cash quality weak: OCF ({ocf_curr:,.0f}) <= NP ({net_profit_curr:,.0f})")
        else:
            criteria['accruals_quality'] = False
            details.append("Cash quality: insufficient data")

        # ------------------------------------------------------------------
        # 5. Delta Leverage: Borrowings / Total Assets decreased
        # ------------------------------------------------------------------
        lev_curr = self._safe_divide(borrowings_curr, total_assets_curr)
        lev_prev = self._safe_divide(borrowings_prev, total_assets_prev)
        if lev_curr is not None and lev_prev is not None:
            delta_lev_pass = lev_curr <= lev_prev
            criteria['leverage_decreased'] = delta_lev_pass
            if delta_lev_pass:
                total += 1
                details.append(f"Leverage decreased: {lev_prev:.2%} -> {lev_curr:.2%}")
            else:
                details.append(f"Leverage increased: {lev_prev:.2%} -> {lev_curr:.2%}")
        else:
            # If no borrowings data, assume debt-free => pass
            if borrowings_curr is not None and borrowings_curr == 0:
                criteria['leverage_decreased'] = True
                total += 1
                details.append("Debt-free — leverage check passed")
            else:
                criteria['leverage_decreased'] = False
                details.append("Leverage: insufficient data")

        # ------------------------------------------------------------------
        # 6. Delta Current Ratio: improved YoY
        # ------------------------------------------------------------------
        cr_curr = self._safe_divide(other_assets_curr, other_liab_curr)
        cr_prev = self._safe_divide(other_assets_prev, other_liab_prev)
        if cr_curr is not None and cr_prev is not None:
            cr_pass = cr_curr >= cr_prev
            criteria['current_ratio_improved'] = cr_pass
            if cr_pass:
                total += 1
                details.append(f"Current ratio improved: {cr_prev:.2f} -> {cr_curr:.2f} (proxy)")
            else:
                details.append(f"Current ratio declined: {cr_prev:.2f} -> {cr_curr:.2f} (proxy)")
        else:
            criteria['current_ratio_improved'] = False
            details.append("Current ratio: insufficient data (proxy)")

        # ------------------------------------------------------------------
        # 7. No new equity issued (shares outstanding didn't increase)
        # ------------------------------------------------------------------
        if equity_cap_curr is not None and equity_cap_prev is not None:
            no_dilution = equity_cap_curr <= equity_cap_prev
            criteria['no_dilution'] = no_dilution
            if no_dilution:
                total += 1
                details.append(f"No dilution: equity capital {equity_cap_prev:,.0f} -> {equity_cap_curr:,.0f}")
            else:
                details.append(f"Equity diluted: {equity_cap_prev:,.0f} -> {equity_cap_curr:,.0f}")
        else:
            criteria['no_dilution'] = False
            details.append("Dilution check: insufficient data")

        # ------------------------------------------------------------------
        # 8. Delta Gross Margin (OPM improved YoY)
        # ------------------------------------------------------------------
        if opm_curr is not None and opm_prev is not None:
            opm_pass = opm_curr >= opm_prev
            criteria['margin_improved'] = opm_pass
            if opm_pass:
                total += 1
                details.append(f"OPM improved: {opm_prev:.1f}% -> {opm_curr:.1f}%")
            else:
                details.append(f"OPM declined: {opm_prev:.1f}% -> {opm_curr:.1f}%")
        else:
            criteria['margin_improved'] = False
            details.append("OPM YoY: insufficient data")

        # ------------------------------------------------------------------
        # 9. Delta Asset Turnover: Revenue / Total Assets improved YoY
        # ------------------------------------------------------------------
        at_curr = self._safe_divide(sales_curr, total_assets_curr)
        at_prev = self._safe_divide(sales_prev, total_assets_prev)
        if at_curr is not None and at_prev is not None:
            at_pass = at_curr >= at_prev
            criteria['asset_turnover_improved'] = at_pass
            if at_pass:
                total += 1
                details.append(f"Asset turnover improved: {at_prev:.2f} -> {at_curr:.2f}")
            else:
                details.append(f"Asset turnover declined: {at_prev:.2f} -> {at_curr:.2f}")
        else:
            criteria['asset_turnover_improved'] = False
            details.append("Asset turnover: insufficient data")

        # ------------------------------------------------------------------
        # Finalize
        # ------------------------------------------------------------------
        result.f_score = total
        result.criteria = criteria
        result.details = details

        if total >= 7:
            result.zone = "STRONG"
        elif total >= 4:
            result.zone = "MODERATE"
        else:
            result.zone = "WEAK"

        return result

    # ------------------------------------------------------------------
    # Data extraction helpers
    # ------------------------------------------------------------------

    def _find_row(self, table: list, label: str) -> Optional[dict]:
        """Find a row in a screener table by label (case-insensitive partial match)."""
        if not table:
            return None
        label_lower = label.lower()
        for row in table:
            row_label = str(row.get('label', '')).lower()
            if label_lower in row_label or row_label in label_lower:
                return row
        return None

    def _get_yearly_values(self, row: dict) -> List[Optional[float]]:
        """Extract ordered numeric values from a row dict, skipping 'label' key."""
        if not row:
            return []
        values = []
        for k, v in row.items():
            if k == 'label':
                continue
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                values.append(None)
        return values

    def _get_latest_value(self, row: dict) -> Optional[float]:
        """Get the most recent non-None value from a row."""
        vals = self._get_yearly_values(row)
        for v in reversed(vals):
            if v is not None:
                return v
        return None

    def _get_latest_two(
        self, table: list, label: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return (latest, previous) year values for a label in a table."""
        row = self._find_row(table, label)
        if not row:
            return None, None
        vals = [v for v in self._get_yearly_values(row) if v is not None]
        if len(vals) >= 2:
            return vals[-1], vals[-2]
        elif len(vals) == 1:
            return vals[0], None
        return None, None

    def _get_latest_value_from_table(self, table: list, label: str) -> Optional[float]:
        """Convenience: find row then get its latest value."""
        row = self._find_row(table, label)
        return self._get_latest_value(row) if row else None

    def _get_opm_two_years(self, raw: ScreenerRawData) -> Tuple[Optional[float], Optional[float]]:
        """Get OPM for latest two years.

        First tries the 'OPM' row directly (screener sometimes provides it as %).
        Falls back to computing Operating Profit / Sales.
        """
        # Try direct OPM row
        opm_row = self._find_row(raw.annual_pl, 'OPM')
        if opm_row:
            vals = [v for v in self._get_yearly_values(opm_row) if v is not None]
            if len(vals) >= 2:
                return vals[-1], vals[-2]

        # Fallback: compute from Operating Profit / Sales
        op_curr, op_prev = self._get_latest_two(raw.annual_pl, 'Operating Profit')
        sales_curr, sales_prev = self._get_latest_two(raw.annual_pl, 'Sales')

        opm_curr = (op_curr / sales_curr * 100) if (op_curr is not None and sales_curr and sales_curr > 0) else None
        opm_prev = (op_prev / sales_prev * 100) if (op_prev is not None and sales_prev and sales_prev > 0) else None

        return opm_curr, opm_prev

    # ------------------------------------------------------------------
    # Formatting / math helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
        """Safe division returning None if inputs are missing or denominator is zero."""
        if numerator is None or denominator is None or denominator == 0:
            return None
        return numerator / denominator

    @staticmethod
    def _fmt_pct(val: Optional[float]) -> str:
        return f"{val:.2%}" if val is not None else "N/A"

    @staticmethod
    def _fmt_num(val: Optional[float]) -> str:
        return f"{val:,.0f}" if val is not None else "N/A"
