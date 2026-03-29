"""Beneish M-Score — earnings manipulation detector.

M = -4.84 + 0.920*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI
         + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI

Eight variables (all YoY current / prior unless noted):
    1. DSRI  — Days Sales Receivable Index
    2. GMI   — Gross Margin Index
    3. AQI   — Asset Quality Index
    4. SGI   — Sales Growth Index
    5. DEPI  — Depreciation Index
    6. SGAI  — SGA Expense Index
    7. TATA  — Total Accruals to Total Assets
    8. LVGI  — Leverage Index

Interpretation:
    M > -1.78  → LIKELY MANIPULATOR
    M <= -1.78 → UNLIKELY MANIPULATOR

Missing variables default to neutral (1.0 for ratios, 0.0 for TATA) with
reduced confidence.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from fundamentals.models import FundamentalProfile, ScreenerRawData


@dataclass
class BeneishResult:
    """Result of Beneish M-Score computation."""

    symbol: str
    m_score: Optional[float] = None
    is_manipulator: Optional[bool] = False  # None = insufficient data
    variables: Dict[str, Optional[float]] = field(default_factory=dict)
    confidence: str = "LOW"  # HIGH (all 8), MEDIUM (5-7), LOW (<5)
    details: List[str] = field(default_factory=list)


class BeneishMScore:
    """Compute the Beneish M-Score from screener.in raw data."""

    # Coefficients
    _INTERCEPT = -4.84
    _COEF = {
        'DSRI': 0.920,
        'GMI': 0.528,
        'AQI': 0.404,
        'SGI': 0.892,
        'DEPI': 0.115,
        'SGAI': -0.172,
        'TATA': 4.679,
        'LVGI': -0.327,
    }

    def score(self, profile: FundamentalProfile, raw: ScreenerRawData) -> BeneishResult:
        """Compute Beneish M-Score."""
        result = BeneishResult(symbol=profile.symbol)

        # ------------------------------------------------------------------
        # Extract two-year data series
        # ------------------------------------------------------------------
        sales_curr, sales_prev = self._latest_two(raw.annual_pl, 'Sales')
        net_profit_curr, net_profit_prev = self._latest_two(raw.annual_pl, 'Net Profit')
        depreciation_curr, depreciation_prev = self._latest_two(raw.annual_pl, 'Depreciation')
        expenses_curr, expenses_prev = self._latest_two(raw.annual_pl, 'Expenses')
        op_curr, op_prev = self._latest_two(raw.annual_pl, 'Operating Profit')
        material_curr, material_prev = self._latest_two(raw.annual_pl, 'Material Cost')
        # fallback for COGS
        if material_curr is None:
            material_curr, material_prev = self._latest_two(raw.annual_pl, 'Raw Material')
        if material_curr is None:
            material_curr, material_prev = self._latest_two(raw.annual_pl, 'Cost of Goods')

        receivables_curr, receivables_prev = self._latest_two(raw.balance_sheet, 'Trade Receivables')
        if receivables_curr is None:
            receivables_curr, receivables_prev = self._latest_two(raw.balance_sheet, 'Debtors')

        total_assets_curr, total_assets_prev = self._latest_two(raw.balance_sheet, 'Total Assets')
        other_assets_curr, other_assets_prev = self._latest_two(raw.balance_sheet, 'Other Assets')
        fixed_assets_curr, fixed_assets_prev = self._latest_two(raw.balance_sheet, 'Fixed Assets')
        if fixed_assets_curr is None:
            fixed_assets_curr, fixed_assets_prev = self._latest_two(raw.balance_sheet, 'Tangible Assets')
        borrowings_curr, borrowings_prev = self._latest_two(raw.balance_sheet, 'Borrowings')

        ocf_curr = self._latest_value(raw.cash_flow, 'Cash from Operating Activity')

        computed_count = 0
        variables: Dict[str, Optional[float]] = {}
        details: List[str] = []

        # ------------------------------------------------------------------
        # 1. DSRI — Days Sales Receivable Index
        #    (Receivables_t/Sales_t) / (Receivables_t-1/Sales_t-1)
        # ------------------------------------------------------------------
        dsri = self._ratio_of_ratios(receivables_curr, sales_curr, receivables_prev, sales_prev)
        if dsri is not None:
            variables['DSRI'] = round(dsri, 4)
            computed_count += 1
            details.append(f"DSRI={dsri:.3f}" + (" (receivables growing faster than sales)" if dsri > 1.05 else ""))
        else:
            variables['DSRI'] = None
            details.append("DSRI=N/A (using neutral 1.0)")

        # ------------------------------------------------------------------
        # 2. GMI — Gross Margin Index
        #    GM_t-1 / GM_t  (>1 means margin deterioration)
        #    GM = (Sales - COGS) / Sales
        # ------------------------------------------------------------------
        gmi = self._compute_gmi(sales_curr, sales_prev, material_curr, material_prev)
        if gmi is not None:
            variables['GMI'] = round(gmi, 4)
            computed_count += 1
            details.append(f"GMI={gmi:.3f}" + (" (margin deterioration)" if gmi > 1.0 else ""))
        else:
            variables['GMI'] = None
            details.append("GMI=N/A (using neutral 1.0)")

        # ------------------------------------------------------------------
        # 3. AQI — Asset Quality Index
        #    AQ = 1 - (Current Assets + PPE) / Total Assets
        #    AQI = AQ_t / AQ_t-1
        # ------------------------------------------------------------------
        aqi = self._compute_aqi(
            other_assets_curr, fixed_assets_curr, total_assets_curr,
            other_assets_prev, fixed_assets_prev, total_assets_prev,
        )
        if aqi is not None:
            variables['AQI'] = round(aqi, 4)
            computed_count += 1
            details.append(f"AQI={aqi:.3f}" + (" (rising 'other' assets)" if aqi > 1.0 else ""))
        else:
            variables['AQI'] = None
            details.append("AQI=N/A (using neutral 1.0)")

        # ------------------------------------------------------------------
        # 4. SGI — Sales Growth Index
        #    Sales_t / Sales_t-1
        # ------------------------------------------------------------------
        sgi = self._safe_divide(sales_curr, sales_prev)
        if sgi is not None:
            variables['SGI'] = round(sgi, 4)
            computed_count += 1
            details.append(f"SGI={sgi:.3f} (revenue growth {(sgi - 1) * 100:.1f}%)")
        else:
            variables['SGI'] = None
            details.append("SGI=N/A (using neutral 1.0)")

        # ------------------------------------------------------------------
        # 5. DEPI — Depreciation Index
        #    (Dep_t-1 / (Dep_t-1 + PPE_t-1)) / (Dep_t / (Dep_t + PPE_t))
        #    >1 means slowing depreciation rate
        # ------------------------------------------------------------------
        depi = self._compute_depi(depreciation_curr, depreciation_prev, fixed_assets_curr, fixed_assets_prev)
        if depi is not None:
            variables['DEPI'] = round(depi, 4)
            computed_count += 1
            details.append(f"DEPI={depi:.3f}" + (" (slowing depreciation)" if depi > 1.0 else ""))
        else:
            variables['DEPI'] = None
            details.append("DEPI=N/A (using neutral 1.0)")

        # ------------------------------------------------------------------
        # 6. SGAI — SGA Expense Index
        #    (SGA_t / Sales_t) / (SGA_t-1 / Sales_t-1)
        #    SGA ≈ Total Expenses - COGS - Depreciation
        # ------------------------------------------------------------------
        sgai = self._compute_sgai(
            expenses_curr, material_curr, depreciation_curr, sales_curr,
            expenses_prev, material_prev, depreciation_prev, sales_prev,
        )
        if sgai is not None:
            variables['SGAI'] = round(sgai, 4)
            computed_count += 1
            details.append(f"SGAI={sgai:.3f}")
        else:
            variables['SGAI'] = None
            details.append("SGAI=N/A (using neutral 1.0)")

        # ------------------------------------------------------------------
        # 7. TATA — Total Accruals to Total Assets
        #    (Net Profit - OCF) / Total Assets
        # ------------------------------------------------------------------
        tata = self._compute_tata(net_profit_curr, ocf_curr, total_assets_curr)
        if tata is not None:
            variables['TATA'] = round(tata, 4)
            computed_count += 1
            details.append(f"TATA={tata:.3f}" + (" (high accruals)" if tata > 0.05 else ""))
        else:
            variables['TATA'] = None
            details.append("TATA=N/A (using neutral 0.0)")

        # ------------------------------------------------------------------
        # 8. LVGI — Leverage Index
        #    (TotalLiab_t / TotalAssets_t) / (TotalLiab_t-1 / TotalAssets_t-1)
        # ------------------------------------------------------------------
        lvgi = self._compute_lvgi(borrowings_curr, total_assets_curr, borrowings_prev, total_assets_prev)
        if lvgi is not None:
            variables['LVGI'] = round(lvgi, 4)
            computed_count += 1
            details.append(f"LVGI={lvgi:.3f}" + (" (increasing leverage)" if lvgi > 1.0 else ""))
        else:
            variables['LVGI'] = None
            details.append("LVGI=N/A (using neutral 1.0)")

        # ------------------------------------------------------------------
        # Compute M-Score
        # ------------------------------------------------------------------
        # Use neutral defaults for missing variables — biases M-Score toward
        # "unlikely manipulator". Confidence level reflects how many variables
        # were actually computed vs defaulted.
        neutral_count = 8 - computed_count
        eff_dsri = variables.get('DSRI') if variables.get('DSRI') is not None else 1.0
        eff_gmi = variables.get('GMI') if variables.get('GMI') is not None else 1.0
        eff_aqi = variables.get('AQI') if variables.get('AQI') is not None else 1.0
        eff_sgi = variables.get('SGI') if variables.get('SGI') is not None else 1.0
        eff_depi = variables.get('DEPI') if variables.get('DEPI') is not None else 1.0
        eff_sgai = variables.get('SGAI') if variables.get('SGAI') is not None else 1.0
        eff_tata = variables.get('TATA') if variables.get('TATA') is not None else 0.0
        eff_lvgi = variables.get('LVGI') if variables.get('LVGI') is not None else 1.0

        if neutral_count > 0:
            details.append(f"WARNING: {neutral_count} of 8 variables used neutral defaults — M-Score may be unreliable")

        m = (
            self._INTERCEPT
            + self._COEF['DSRI'] * eff_dsri
            + self._COEF['GMI'] * eff_gmi
            + self._COEF['AQI'] * eff_aqi
            + self._COEF['SGI'] * eff_sgi
            + self._COEF['DEPI'] * eff_depi
            + self._COEF['SGAI'] * eff_sgai
            + self._COEF['TATA'] * eff_tata
            + self._COEF['LVGI'] * eff_lvgi
        )

        result.m_score = round(m, 2)
        result.variables = variables

        # ------------------------------------------------------------------
        # Confidence
        # ------------------------------------------------------------------
        if computed_count >= 8:
            result.confidence = "HIGH"
        elif computed_count >= 5:
            result.confidence = "MEDIUM"
        else:
            result.confidence = "LOW"

        # When confidence is LOW (<5 variables computed), the M-Score is
        # unreliable — set is_manipulator to None (insufficient data)
        if result.confidence == "LOW":
            result.is_manipulator = None
            details.append(f"Variables computed: {computed_count}/8 — confidence: {result.confidence}")
            details.append(f"M = {m:.2f} — INSUFFICIENT DATA for manipulation determination")
        else:
            result.is_manipulator = m > -1.78
            details.append(f"Variables computed: {computed_count}/8 — confidence: {result.confidence}")
            if result.is_manipulator:
                details.append(f"M = {m:.2f} > -1.78 — LIKELY MANIPULATOR (earnings quality red flag)")
            else:
                details.append(f"M = {m:.2f} <= -1.78 — UNLIKELY MANIPULATOR")

        result.details = details
        return result

    # ------------------------------------------------------------------
    # Variable computation helpers
    # ------------------------------------------------------------------

    def _compute_gmi(
        self,
        sales_curr: Optional[float], sales_prev: Optional[float],
        cogs_curr: Optional[float], cogs_prev: Optional[float],
    ) -> Optional[float]:
        """Gross Margin Index = GM_prev / GM_curr."""
        if None in (sales_curr, sales_prev, cogs_curr, cogs_prev):
            return None
        if sales_curr <= 0 or sales_prev <= 0:
            return None
        gm_curr = (sales_curr - cogs_curr) / sales_curr
        gm_prev = (sales_prev - cogs_prev) / sales_prev
        if gm_curr <= 0:
            return None
        return gm_prev / gm_curr

    def _compute_aqi(
        self,
        ca_curr: Optional[float], ppe_curr: Optional[float], ta_curr: Optional[float],
        ca_prev: Optional[float], ppe_prev: Optional[float], ta_prev: Optional[float],
    ) -> Optional[float]:
        """Asset Quality Index.

        AQ = 1 - (CurrentAssets + PPE) / TotalAssets
        AQI = AQ_curr / AQ_prev
        """
        if None in (ca_curr, ppe_curr, ta_curr, ca_prev, ppe_prev, ta_prev):
            return None
        if ta_curr <= 0 or ta_prev <= 0:
            return None
        aq_curr = 1 - ((ca_curr or 0) + (ppe_curr or 0)) / ta_curr
        aq_prev = 1 - ((ca_prev or 0) + (ppe_prev or 0)) / ta_prev
        if aq_prev == 0:
            return None
        return aq_curr / aq_prev

    def _compute_depi(
        self,
        dep_curr: Optional[float], dep_prev: Optional[float],
        ppe_curr: Optional[float], ppe_prev: Optional[float],
    ) -> Optional[float]:
        """Depreciation Index.

        DepRate = Dep / (Dep + PPE)
        DEPI = DepRate_prev / DepRate_curr   (>1 = slowing depreciation)
        """
        if None in (dep_curr, dep_prev, ppe_curr, ppe_prev):
            return None
        denom_curr = dep_curr + (ppe_curr or 0)
        denom_prev = dep_prev + (ppe_prev or 0)
        if denom_curr <= 0 or denom_prev <= 0:
            return None
        rate_curr = dep_curr / denom_curr
        rate_prev = dep_prev / denom_prev
        if rate_curr == 0:
            return None
        return rate_prev / rate_curr

    def _compute_sgai(
        self,
        expenses_curr: Optional[float], cogs_curr: Optional[float],
        dep_curr: Optional[float], sales_curr: Optional[float],
        expenses_prev: Optional[float], cogs_prev: Optional[float],
        dep_prev: Optional[float], sales_prev: Optional[float],
    ) -> Optional[float]:
        """SGA Expense Index.

        SGA ≈ Total Expenses - COGS - Depreciation
        SGAI = (SGA_curr/Sales_curr) / (SGA_prev/Sales_prev)
        """
        if None in (expenses_curr, sales_curr, expenses_prev, sales_prev):
            return None
        if sales_curr <= 0 or sales_prev <= 0:
            return None

        sga_curr = expenses_curr - (cogs_curr or 0) - (dep_curr or 0)
        sga_prev = expenses_prev - (cogs_prev or 0) - (dep_prev or 0)

        if sga_curr < 0 or sga_prev <= 0:
            return None

        ratio_curr = sga_curr / sales_curr
        ratio_prev = sga_prev / sales_prev
        if ratio_prev == 0:
            return None
        return ratio_curr / ratio_prev

    @staticmethod
    def _compute_tata(
        net_profit: Optional[float], ocf: Optional[float], total_assets: Optional[float],
    ) -> Optional[float]:
        """Total Accruals to Total Assets = (NP - OCF) / TA."""
        if None in (net_profit, ocf, total_assets) or total_assets == 0:
            return None
        return (net_profit - ocf) / total_assets

    def _compute_lvgi(
        self,
        debt_curr: Optional[float], ta_curr: Optional[float],
        debt_prev: Optional[float], ta_prev: Optional[float],
    ) -> Optional[float]:
        """Leverage Index = (Debt_t/TA_t) / (Debt_t-1/TA_t-1)."""
        return self._ratio_of_ratios(debt_curr, ta_curr, debt_prev, ta_prev)

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def _ratio_of_ratios(
        self,
        num_curr: Optional[float], den_curr: Optional[float],
        num_prev: Optional[float], den_prev: Optional[float],
    ) -> Optional[float]:
        """Compute (num_curr/den_curr) / (num_prev/den_prev)."""
        if None in (num_curr, den_curr, num_prev, den_prev):
            return None
        if den_curr == 0 or den_prev == 0:
            return None
        r_prev = num_prev / den_prev
        if r_prev == 0:
            return None
        r_curr = num_curr / den_curr
        return r_curr / r_prev

    @staticmethod
    def _safe_divide(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is None or b is None or b == 0:
            return None
        return a / b

    # ------------------------------------------------------------------
    # Data extraction helpers
    # ------------------------------------------------------------------

    def _find_row(self, table: list, label: str) -> Optional[dict]:
        """Find a row by case-insensitive partial match on label."""
        if not table:
            return None
        label_lower = label.lower()
        for row in table:
            row_label = str(row.get('label', '')).lower()
            if label_lower in row_label or row_label in label_lower:
                return row
        return None

    def _get_yearly_values(self, row: dict) -> List[Optional[float]]:
        """Extract ordered numeric values from a row, skipping 'label'."""
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

    def _latest_two(
        self, table: list, label: str,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return (latest, previous) year values for a label."""
        row = self._find_row(table, label)
        if not row:
            return None, None
        vals = [v for v in self._get_yearly_values(row) if v is not None]
        if len(vals) >= 2:
            return vals[-1], vals[-2]
        elif len(vals) == 1:
            return vals[0], None
        return None, None

    def _latest_value(self, table: list, label: str) -> Optional[float]:
        """Get the most recent value for a label from a table."""
        row = self._find_row(table, label)
        if not row:
            return None
        vals = self._get_yearly_values(row)
        for v in reversed(vals):
            if v is not None:
                return v
        return None
