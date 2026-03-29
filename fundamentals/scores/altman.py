"""Altman Z-Score — bankruptcy risk indicator.

Original Z-Score (manufacturing / general):
    Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

Service / non-manufacturing (Z'' Score):
    Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4

Components:
    X1 = Working Capital / Total Assets
    X2 = Retained Earnings / Total Assets
    X3 = EBIT / Total Assets
    X4 = Market Cap / Total Liabilities
    X5 = Revenue / Total Assets  (excluded for service companies)

Zones:
    Z > 2.99  → SAFE
    1.81-2.99 → GREY
    Z < 1.81  → DISTRESS

Banks are excluded (model not applicable).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from fundamentals.models import FundamentalProfile, ScreenerRawData

# Sectors where Altman Z-Score is not meaningful
_BANKING_KEYWORDS = {
    'bank', 'banking', 'finance', 'nbfc', 'insurance',
    'financial services', 'housing finance',
}

# Screener.in sector/industry labels that indicate a service company
_SERVICE_KEYWORDS = {
    'software', 'it services', 'it consulting', 'consulting',
    'media', 'entertainment', 'telecom', 'healthcare services',
    'education', 'hospitality', 'bpo', 'staffing',
}


@dataclass
class AltmanResult:
    """Result of Altman Z-Score computation."""

    symbol: str
    z_score: Optional[float] = None
    zone: str = "N/A"  # SAFE, GREY, DISTRESS, N/A
    components: Dict[str, Optional[float]] = field(default_factory=dict)
    is_applicable: bool = True
    details: List[str] = field(default_factory=list)


class AltmanZScore:
    """Compute the Altman Z-Score from screener.in raw data."""

    def score(self, profile: FundamentalProfile, raw: ScreenerRawData) -> AltmanResult:
        """Compute Altman Z-Score.

        Returns AltmanResult with is_applicable=False for banking companies.
        """
        result = AltmanResult(symbol=profile.symbol)

        # ------------------------------------------------------------------
        # Check applicability
        # ------------------------------------------------------------------
        if self._is_banking(profile):
            result.is_applicable = False
            result.zone = "N/A"
            result.details.append("Altman Z-Score not applicable for banking/finance companies")
            return result

        is_service = self._is_service(profile)

        # ------------------------------------------------------------------
        # Extract raw values
        # ------------------------------------------------------------------
        total_assets = self._get_latest_bs(raw, 'Total Assets')
        if not total_assets or total_assets <= 0:
            result.is_applicable = False
            result.details.append("Total Assets not available — cannot compute Z-Score")
            return result

        # Working capital proxy: screener.in aggregates current items into
        # Other Assets / Other Liabilities. True current assets/liabilities
        # are not separately available.
        other_assets = self._get_latest_bs(raw, 'Other Assets') or 0
        other_liabilities = self._get_latest_bs(raw, 'Other Liabilities') or 0
        working_capital = other_assets - other_liabilities

        # Retained Earnings proxy: Reserves (screener.in does not separate
        # retained earnings from other reserves)
        reserves = self._get_latest_bs(raw, 'Reserves') or 0

        # EBIT proxy: Operating Profit (screener.in does not report EBIT
        # directly; Operating Profit is the closest line item)
        operating_profit = self._get_latest_pl(raw, 'Operating Profit') or 0

        # Revenue
        sales = self._get_latest_pl(raw, 'Sales') or 0

        # Total Liabilities = Total Assets - (Equity Capital + Reserves)
        equity_capital = self._get_latest_bs(raw, 'Equity Capital') or 0
        total_equity = equity_capital + reserves
        total_liabilities = total_assets - total_equity
        if total_liabilities <= 0:
            # Fallback: use Borrowings + Other Liabilities
            borrowings = self._get_latest_bs(raw, 'Borrowings') or 0
            total_liabilities = borrowings + other_liabilities

        # Market Cap (from raw data, in Cr)
        market_cap = raw.market_cap or 0

        # ------------------------------------------------------------------
        # Compute components
        # ------------------------------------------------------------------
        x1 = working_capital / total_assets
        x2 = reserves / total_assets
        x3 = operating_profit / total_assets
        x4 = (market_cap / total_liabilities) if total_liabilities > 0 else 0
        x5 = sales / total_assets

        result.components = {
            'X1_working_capital_to_assets': round(x1, 4),
            'X2_retained_earnings_to_assets': round(x2, 4),
            'X3_ebit_to_assets': round(x3, 4),
            'X4_market_cap_to_liabilities': round(x4, 4),
            'X5_revenue_to_assets': round(x5, 4) if not is_service else None,
            'proxies_used': [
                'working_capital (Other Assets - Other Liabilities)',
                'retained_earnings (Reserves)',
                'EBIT (Operating Profit)',
            ],
        }

        # ------------------------------------------------------------------
        # Compute Z-Score
        # ------------------------------------------------------------------
        if is_service:
            z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
            result.details.append("Using Z'' model (service/non-manufacturing)")
        else:
            z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
            result.details.append("Using original Z model (manufacturing/general)")

        result.z_score = round(z, 2)

        # ------------------------------------------------------------------
        # Zone classification
        # ------------------------------------------------------------------
        if z > 2.99:
            result.zone = "SAFE"
            result.details.append(f"Z = {z:.2f} > 2.99 — low bankruptcy risk")
        elif z >= 1.81:
            result.zone = "GREY"
            result.details.append(f"Z = {z:.2f} (1.81-2.99) — moderate bankruptcy risk")
        else:
            result.zone = "DISTRESS"
            result.details.append(f"Z = {z:.2f} < 1.81 — high bankruptcy risk")

        # Add component breakdown
        result.details.append(
            f"X1={x1:.3f}, X2={x2:.3f}, X3={x3:.3f}, X4={x4:.3f}"
            + (f", X5={x5:.3f}" if not is_service else "")
        )
        result.details.append(
            "Proxies used: working_capital (Other Assets - Other Liabilities), "
            "retained_earnings (Reserves), EBIT (Operating Profit)"
        )

        return result

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_banking(profile: FundamentalProfile) -> bool:
        """Check if the company is a bank / NBFC / insurance / finance."""
        if profile.is_banking:
            return True
        combined = (profile.sector + ' ' + profile.industry).lower()
        return any(kw in combined for kw in _BANKING_KEYWORDS)

    @staticmethod
    def _is_service(profile: FundamentalProfile) -> bool:
        """Heuristic: is this a service / non-manufacturing company?"""
        combined = (profile.sector + ' ' + profile.industry).lower()
        return any(kw in combined for kw in _SERVICE_KEYWORDS)

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

    def _get_latest_value(self, row: dict) -> Optional[float]:
        """Most recent non-None value from a row."""
        vals = self._get_yearly_values(row)
        for v in reversed(vals):
            if v is not None:
                return v
        return None

    def _get_latest_bs(self, raw: ScreenerRawData, label: str) -> Optional[float]:
        """Get latest balance sheet value for a label."""
        row = self._find_row(raw.balance_sheet, label)
        return self._get_latest_value(row) if row else None

    def _get_latest_pl(self, raw: ScreenerRawData, label: str) -> Optional[float]:
        """Get latest annual P&L value for a label."""
        row = self._find_row(raw.annual_pl, label)
        return self._get_latest_value(row) if row else None
