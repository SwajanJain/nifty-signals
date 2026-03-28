"""Profile builder and composite fundamental scorer."""

from typing import Any, Dict, List, Optional, Tuple

from config import BANKING_SECTORS
from .models import FundamentalProfile, FundamentalScore, ScreenerRawData


class ProfileBuilder:
    """Transforms ScreenerRawData into FundamentalProfile."""

    def build(self, raw: ScreenerRawData) -> FundamentalProfile:
        """Build complete fundamental profile from raw screener data."""
        is_banking = raw.sector in BANKING_SECTORS or raw.industry in BANKING_SECTORS

        p = FundamentalProfile(
            symbol=raw.symbol,
            company_name=raw.company_name,
            sector=raw.sector,
            industry=raw.industry,
            is_banking=is_banking,
            data_quality=raw.data_quality,
            last_updated=raw.fetched_at,
        )

        # --- Direct values ---
        p.market_cap = raw.market_cap
        p.current_price = raw.current_price
        p.pe_ratio = raw.pe_ratio
        p.dividend_yield = raw.dividend_yield
        p.roe = raw.roe
        p.roce = raw.roce
        p.book_value_per_share = raw.book_value

        # --- Computed valuation ---
        p.pb_ratio = self._compute_pb(raw)
        p.ev_ebitda = self._compute_ev_ebitda(raw)
        p.earnings_yield = (100.0 / raw.pe_ratio) if raw.pe_ratio > 0 else 0
        p.price_to_sales = self._compute_price_to_sales(raw)
        p.eps_ttm = self._compute_eps_ttm(raw)

        # --- Growth from screener's own calculations ---
        p.revenue_growth_3y = raw.compounded_sales_growth.get('3yr', 0) or 0
        p.revenue_growth_5y = raw.compounded_sales_growth.get('5yr', 0) or 0
        p.profit_growth_3y = raw.compounded_profit_growth.get('3yr', 0) or 0
        p.profit_growth_5y = raw.compounded_profit_growth.get('5yr', 0) or 0

        # EPS growth approximated from profit growth
        p.eps_growth_3y = p.profit_growth_3y
        p.eps_growth_5y = p.profit_growth_5y

        # PEG ratio
        p.peg_ratio = self._compute_peg(raw.pe_ratio, p.eps_growth_3y)

        # --- Profitability from annual P&L ---
        margins = self._compute_margins(raw)
        p.npm = margins.get('npm', 0)
        p.opm = margins.get('opm', 0)

        # DuPont
        dupont = self._compute_dupont(raw)
        p.dupont_npm = dupont[0]
        p.dupont_asset_turnover = dupont[1]
        p.dupont_equity_multiplier = dupont[2]

        # --- Financial health from balance sheet ---
        health = self._compute_financial_health(raw)
        p.debt_to_equity = health.get('debt_to_equity', 0)
        p.current_ratio = health.get('current_ratio', 0)
        p.interest_coverage = health.get('interest_coverage', 0)

        # --- Cash flow ---
        cf = self._compute_cash_flow(raw)
        p.operating_cash_flow = cf.get('ocf', 0)
        p.free_cash_flow = cf.get('fcf', 0)
        p.cash_flow_positive_years = cf.get('ocf_positive_years', 0)
        p.fcf_positive_years = cf.get('fcf_positive_years', 0)
        p.fcf_yield = (p.free_cash_flow / p.market_cap * 100) if p.market_cap > 0 else 0

        # --- Efficiency from ratios ---
        eff = self._compute_efficiency(raw)
        p.debtor_days = eff.get('debtor_days', 0)
        p.inventory_days = eff.get('inventory_days', 0)
        p.working_capital_days = eff.get('working_capital_days', 0)
        p.asset_turnover = p.dupont_asset_turnover

        # --- Ownership ---
        ownership = self._compute_ownership(raw)
        p.promoter_holding = ownership.get('promoter', 0)
        p.promoter_holding_change_1y = ownership.get('promoter_change', 0)
        p.promoter_pledge = ownership.get('pledge', 0)
        p.fii_holding = ownership.get('fii', 0)
        p.dii_holding = ownership.get('dii', 0)
        p.fii_holding_change_1y = ownership.get('fii_change', 0)

        # --- Quarterly momentum ---
        qm = self._compute_quarterly_momentum(raw)
        p.latest_qtr_revenue_yoy = qm.get('rev_yoy', 0)
        p.latest_qtr_profit_yoy = qm.get('profit_yoy', 0)
        p.qtr_eps_acceleration = qm.get('acceleration', False)
        p.consecutive_qtr_growth = qm.get('consecutive', 0)

        # --- Consistency ---
        consistency = self._compute_consistency(raw)
        p.roce_consistent_above_15 = consistency.get('roce_consistent', False)
        p.revenue_growing_consistently = consistency.get('rev_consistent', False)
        p.npm_stable_or_improving = consistency.get('npm_stable', False)
        p.no_loss_years_5 = consistency.get('no_losses', False)
        p.dividend_years_5 = consistency.get('dividend_years', 0)
        p.dividend_growing = consistency.get('div_growing', False)
        p.dividend_payout_ratio = consistency.get('payout_ratio', 0)

        return p

    # --- Computation helpers ---

    def _compute_pb(self, raw: ScreenerRawData) -> float:
        if raw.book_value and raw.book_value > 0 and raw.current_price > 0:
            return round(raw.current_price / raw.book_value, 2)
        return 0

    def _compute_peg(self, pe: float, growth: float) -> float:
        if pe > 0 and growth > 0:
            return round(pe / growth, 2)
        return 0

    def _compute_price_to_sales(self, raw: ScreenerRawData) -> float:
        """Market cap / TTM sales."""
        ttm_sales = self._get_latest_annual_value(raw, 'Sales')
        if ttm_sales and ttm_sales > 0 and raw.market_cap > 0:
            return round(raw.market_cap / ttm_sales, 2)
        return 0

    def _compute_eps_ttm(self, raw: ScreenerRawData) -> float:
        """Get TTM EPS from annual P&L."""
        return self._get_latest_annual_value(raw, 'EPS in Rs') or 0

    def _compute_ev_ebitda(self, raw: ScreenerRawData) -> float:
        """EV/EBITDA = (Market Cap + Debt - Cash) / EBITDA."""
        debt = self._get_latest_bs_value(raw, 'Borrowings') or 0
        cash = self._get_latest_bs_value(raw, 'Cash Equivalents') or 0
        if cash == 0:
            cash = self._get_latest_bs_value(raw, 'Other Assets') or 0

        operating_profit = self._get_latest_annual_value(raw, 'Operating Profit')
        depreciation = self._get_latest_annual_value(raw, 'Depreciation') or 0

        if operating_profit and operating_profit > 0:
            ebitda = operating_profit + depreciation
            ev = raw.market_cap + debt - cash
            if ebitda > 0:
                return round(ev / ebitda, 2)
        return 0

    def _compute_margins(self, raw: ScreenerRawData) -> Dict[str, float]:
        """NPM and OPM from latest annual P&L."""
        result = {'npm': 0, 'opm': 0}

        sales = self._get_latest_annual_value(raw, 'Sales')
        if not sales or sales <= 0:
            return result

        net_profit = self._get_latest_annual_value(raw, 'Net Profit')
        if net_profit is not None:
            result['npm'] = round(net_profit / sales * 100, 2)

        # OPM is often directly in the table
        opm = self._get_latest_annual_value(raw, 'OPM')
        if opm is not None:
            result['opm'] = opm
        else:
            op = self._get_latest_annual_value(raw, 'Operating Profit')
            if op is not None:
                result['opm'] = round(op / sales * 100, 2)

        return result

    def _compute_dupont(self, raw: ScreenerRawData) -> Tuple[float, float, float]:
        """DuPont: NPM × Asset Turnover × Equity Multiplier."""
        sales = self._get_latest_annual_value(raw, 'Sales') or 0
        net_profit = self._get_latest_annual_value(raw, 'Net Profit') or 0
        total_assets = self._get_latest_bs_value(raw, 'Total Assets') or 0
        equity = self._get_latest_bs_value(raw, 'Equity Capital') or 0
        reserves = self._get_latest_bs_value(raw, 'Reserves') or 0
        total_equity = equity + reserves

        npm = (net_profit / sales * 100) if sales > 0 else 0
        asset_turnover = (sales / total_assets) if total_assets > 0 else 0
        equity_multiplier = (total_assets / total_equity) if total_equity > 0 else 0

        return (round(npm, 2), round(asset_turnover, 2), round(equity_multiplier, 2))

    def _compute_financial_health(self, raw: ScreenerRawData) -> Dict[str, float]:
        """D/E, current ratio, interest coverage from balance sheet and P&L."""
        result = {'debt_to_equity': 0, 'current_ratio': 0, 'interest_coverage': 0}

        borrowings = self._get_latest_bs_value(raw, 'Borrowings') or 0
        equity = self._get_latest_bs_value(raw, 'Equity Capital') or 0
        reserves = self._get_latest_bs_value(raw, 'Reserves') or 0
        total_equity = equity + reserves

        if total_equity > 0:
            result['debt_to_equity'] = round(borrowings / total_equity, 2)

        # Interest coverage from P&L
        operating_profit = self._get_latest_annual_value(raw, 'Operating Profit') or 0
        interest = self._get_latest_annual_value(raw, 'Interest') or 0
        if interest > 0:
            result['interest_coverage'] = round(operating_profit / interest, 2)
        elif operating_profit > 0:
            result['interest_coverage'] = 100  # No interest = very high coverage

        # Current ratio (rough approximation from balance sheet)
        other_assets = self._get_latest_bs_value(raw, 'Other Assets') or 0
        other_liabilities = self._get_latest_bs_value(raw, 'Other Liabilities') or 0
        if other_liabilities > 0:
            result['current_ratio'] = round(other_assets / other_liabilities, 2)

        return result

    def _compute_cash_flow(self, raw: ScreenerRawData) -> Dict[str, Any]:
        """Cash flow metrics from cash flow statement."""
        result = {
            'ocf': 0, 'fcf': 0,
            'ocf_positive_years': 0, 'fcf_positive_years': 0,
        }

        if not raw.cash_flow:
            return result

        ocf_row = self._find_row(raw.cash_flow, 'Cash from Operating Activity')
        capex_row = self._find_row(raw.cash_flow, 'Cash from Investing Activity')

        if ocf_row:
            # Get latest year value
            latest_ocf = self._get_latest_value(ocf_row)
            result['ocf'] = latest_ocf or 0

            # Count positive years
            yearly_vals = self._get_yearly_values(ocf_row)
            result['ocf_positive_years'] = sum(1 for v in yearly_vals[-5:] if v and v > 0)

        if ocf_row and capex_row:
            latest_capex = self._get_latest_value(capex_row)
            if latest_capex is not None and result['ocf']:
                # Capex is negative in investing, so FCF = OCF + investing (which is negative)
                result['fcf'] = result['ocf'] + (latest_capex or 0)

            # Count FCF positive years
            ocf_vals = self._get_yearly_values(ocf_row)
            capex_vals = self._get_yearly_values(capex_row)
            min_len = min(len(ocf_vals), len(capex_vals))
            if min_len > 0:
                fcf_vals = [
                    (ocf_vals[i] or 0) + (capex_vals[i] or 0)
                    for i in range(max(0, min_len - 5), min_len)
                ]
                result['fcf_positive_years'] = sum(1 for v in fcf_vals if v > 0)

        return result

    def _compute_efficiency(self, raw: ScreenerRawData) -> Dict[str, float]:
        """Efficiency ratios from the ratios table."""
        result = {'debtor_days': 0, 'inventory_days': 0, 'working_capital_days': 0}

        if not raw.ratios:
            return result

        debtor_row = self._find_row(raw.ratios, 'Debtor Days')
        inv_row = self._find_row(raw.ratios, 'Inventory Days')
        wc_row = self._find_row(raw.ratios, 'Working Capital Days')

        if debtor_row:
            result['debtor_days'] = self._get_latest_value(debtor_row) or 0
        if inv_row:
            result['inventory_days'] = self._get_latest_value(inv_row) or 0
        if wc_row:
            result['working_capital_days'] = self._get_latest_value(wc_row) or 0

        return result

    def _compute_ownership(self, raw: ScreenerRawData) -> Dict[str, float]:
        """Parse shareholding data."""
        result = {
            'promoter': 0, 'promoter_change': 0, 'pledge': 0,
            'fii': 0, 'fii_change': 0, 'dii': 0,
        }

        if not raw.shareholding:
            return result

        promoter_row = self._find_row(raw.shareholding, 'Promoters')
        fii_row = self._find_row(raw.shareholding, 'FIIs')
        dii_row = self._find_row(raw.shareholding, 'DIIs')

        if promoter_row:
            vals = self._get_yearly_values(promoter_row)
            if vals:
                result['promoter'] = vals[-1] or 0
                if len(vals) >= 5:
                    result['promoter_change'] = (vals[-1] or 0) - (vals[-5] or 0)

        if fii_row:
            vals = self._get_yearly_values(fii_row)
            if vals:
                result['fii'] = vals[-1] or 0
                if len(vals) >= 5:
                    result['fii_change'] = (vals[-1] or 0) - (vals[-5] or 0)

        if dii_row:
            vals = self._get_yearly_values(dii_row)
            if vals:
                result['dii'] = vals[-1] or 0

        return result

    def _compute_quarterly_momentum(self, raw: ScreenerRawData) -> Dict[str, Any]:
        """Analyze quarterly results for YoY momentum."""
        result = {
            'rev_yoy': 0, 'profit_yoy': 0,
            'acceleration': False, 'consecutive': 0,
        }

        if not raw.quarterly_results:
            return result

        sales_row = self._find_row(raw.quarterly_results, 'Sales')
        profit_row = self._find_row(raw.quarterly_results, 'Net Profit')

        if sales_row:
            vals = self._get_yearly_values(sales_row)
            if len(vals) >= 5:
                # Latest quarter YoY
                latest = vals[-1] or 0
                year_ago = vals[-5] or 0  # 4 quarters back
                if year_ago > 0:
                    result['rev_yoy'] = round((latest - year_ago) / year_ago * 100, 1)

        if profit_row:
            vals = self._get_yearly_values(profit_row)
            if len(vals) >= 5:
                latest = vals[-1] or 0
                year_ago = vals[-5] or 0
                if year_ago > 0:
                    result['profit_yoy'] = round((latest - year_ago) / year_ago * 100, 1)

                # Check acceleration: is latest YoY > previous quarter's YoY?
                if len(vals) >= 6:
                    prev = vals[-2] or 0
                    prev_year_ago = vals[-6] or 0
                    if prev_year_ago > 0 and year_ago > 0:
                        prev_yoy = (prev - prev_year_ago) / prev_year_ago * 100
                        latest_yoy = result['profit_yoy']
                        result['acceleration'] = latest_yoy > prev_yoy

                # Consecutive quarters of YoY profit growth
                count = 0
                for i in range(len(vals) - 1, 3, -1):
                    curr = vals[i] or 0
                    yago = vals[i - 4] or 0
                    if yago > 0 and curr > yago:
                        count += 1
                    else:
                        break
                result['consecutive'] = count

        return result

    def _compute_consistency(self, raw: ScreenerRawData) -> Dict[str, Any]:
        """Check 5-year consistency of key metrics."""
        result = {
            'roce_consistent': False,
            'rev_consistent': False,
            'npm_stable': False,
            'no_losses': False,
            'dividend_years': 0,
            'div_growing': False,
            'payout_ratio': 0,
        }

        # ROCE consistency from ratios table
        if raw.ratios:
            roce_row = self._find_row(raw.ratios, 'ROCE')
            if roce_row:
                vals = self._get_yearly_values(roce_row)
                last5 = [v for v in vals[-5:] if v is not None]
                if len(last5) >= 3:
                    result['roce_consistent'] = all(v >= 15 for v in last5)

        # Revenue consistency from annual P&L
        if raw.annual_pl:
            sales_row = self._find_row(raw.annual_pl, 'Sales')
            if sales_row:
                vals = self._get_yearly_values(sales_row)
                last5 = [v for v in vals[-6:] if v is not None]
                if len(last5) >= 3:
                    growth = all(
                        last5[i] > last5[i - 1]
                        for i in range(1, len(last5))
                        if last5[i] and last5[i - 1] and last5[i - 1] > 0
                    )
                    result['rev_consistent'] = growth

            # NPM stability
            profit_row = self._find_row(raw.annual_pl, 'Net Profit')
            if sales_row and profit_row:
                sales_vals = self._get_yearly_values(sales_row)
                profit_vals = self._get_yearly_values(profit_row)
                min_len = min(len(sales_vals), len(profit_vals))
                if min_len >= 3:
                    npms = []
                    for i in range(max(0, min_len - 5), min_len):
                        s = sales_vals[i] or 0
                        p = profit_vals[i] or 0
                        if s > 0:
                            npms.append(p / s * 100)

                    if len(npms) >= 3:
                        # Stable = no NPM drop > 3 percentage points
                        drops = [
                            npms[i] - npms[i - 1]
                            for i in range(1, len(npms))
                        ]
                        result['npm_stable'] = all(d > -3 for d in drops)

            # No losses
            if profit_row:
                vals = self._get_yearly_values(profit_row)
                last5 = [v for v in vals[-5:] if v is not None]
                if len(last5) >= 3:
                    result['no_losses'] = all(v > 0 for v in last5)

            # Dividend
            div_row = self._find_row(raw.annual_pl, 'Dividend Payout')
            if div_row:
                vals = self._get_yearly_values(div_row)
                last5 = [v for v in vals[-5:] if v is not None]
                result['dividend_years'] = sum(1 for v in last5 if v and v > 0)
                if len(last5) >= 2:
                    result['div_growing'] = all(
                        last5[i] >= last5[i - 1]
                        for i in range(1, len(last5))
                        if last5[i] is not None and last5[i - 1] is not None
                    )
                if last5:
                    result['payout_ratio'] = last5[-1] or 0

        return result

    # --- Row/value extraction helpers ---

    def _find_row(self, table_data: List[Dict], label: str) -> Optional[Dict]:
        """Find a row by label (case-insensitive partial match)."""
        label_lower = label.lower()
        for row in table_data:
            row_label = (row.get('label') or '').lower()
            if label_lower in row_label or row_label in label_lower:
                return row
        return None

    def _get_latest_value(self, row: Dict) -> Optional[float]:
        """Get the most recent non-None value from a row dict."""
        vals = self._get_yearly_values(row)
        for v in reversed(vals):
            if v is not None:
                return v
        return None

    def _get_yearly_values(self, row: Dict) -> List[Optional[float]]:
        """Extract ordered numeric values from a row, skipping 'label'."""
        values = []
        for key, val in row.items():
            if key == 'label':
                continue
            if isinstance(val, (int, float)):
                values.append(val)
            else:
                values.append(None)
        return values

    def _get_latest_annual_value(self, raw: ScreenerRawData, label: str) -> Optional[float]:
        """Get latest value for a label from annual P&L."""
        if not raw.annual_pl:
            return None
        row = self._find_row(raw.annual_pl, label)
        if row:
            return self._get_latest_value(row)
        return None

    def _get_latest_bs_value(self, raw: ScreenerRawData, label: str) -> Optional[float]:
        """Get latest value for a label from balance sheet."""
        if not raw.balance_sheet:
            return None
        row = self._find_row(raw.balance_sheet, label)
        if row:
            return self._get_latest_value(row)
        return None


class FundamentalScorer:
    """Compute composite fundamental score (0-100)."""

    def score(self, profile: FundamentalProfile) -> FundamentalScore:
        """Compute complete fundamental score."""
        fs = FundamentalScore(
            symbol=profile.symbol,
            company_name=profile.company_name,
            sector=profile.sector,
        )

        fs.valuation_score = self._score_valuation(profile)
        fs.profitability_score = self._score_profitability(profile)
        fs.growth_score = self._score_growth(profile)
        fs.financial_health_score = self._score_financial_health(profile)
        fs.quality_score = self._score_quality(profile)

        fs.total_score = (
            fs.valuation_score
            + fs.profitability_score
            + fs.growth_score
            + fs.financial_health_score
            + fs.quality_score
        )
        fs.total_score = max(0, min(100, fs.total_score))

        fs.grade = self._assign_grade(fs.total_score)
        fs.green_flags, fs.red_flags = self._identify_flags(profile)

        return fs

    def _score_valuation(self, p: FundamentalProfile) -> int:
        """Score 0-20: PE(0-6), PB(0-4), PEG(0-5), EV/EBITDA(0-3), FCF yield(0-2)."""
        score = 0

        # PE ratio (lower is better for value)
        pe = p.pe_ratio
        if 0 < pe <= 10:
            score += 6
        elif pe <= 15:
            score += 5
        elif pe <= 20:
            score += 3
        elif pe <= 30:
            score += 1

        # PB ratio
        pb = p.pb_ratio
        if 0 < pb <= 1.0:
            score += 4
        elif pb <= 2.0:
            score += 3
        elif pb <= 3.0:
            score += 2
        elif pb <= 5.0:
            score += 1

        # PEG ratio
        peg = p.peg_ratio
        if 0 < peg <= 0.5:
            score += 5
        elif peg <= 1.0:
            score += 4
        elif peg <= 1.5:
            score += 3
        elif peg <= 2.0:
            score += 1

        # EV/EBITDA
        ev = p.ev_ebitda
        if 0 < ev <= 8:
            score += 3
        elif ev <= 12:
            score += 2
        elif ev <= 18:
            score += 1

        # FCF yield
        if p.fcf_yield > 5:
            score += 2
        elif p.fcf_yield > 3:
            score += 1

        return min(20, score)

    def _score_profitability(self, p: FundamentalProfile) -> int:
        """Score 0-25: ROE(0-8), ROCE(0-8), NPM(0-5), OPM(0-4)."""
        score = 0

        # ROE
        if p.roe >= 25:
            score += 8
        elif p.roe >= 20:
            score += 7
        elif p.roe >= 15:
            score += 5
        elif p.roe >= 12:
            score += 3
        elif p.roe >= 8:
            score += 1

        # ROCE (skip for banking)
        if not p.is_banking:
            if p.roce >= 25:
                score += 8
            elif p.roce >= 20:
                score += 7
            elif p.roce >= 15:
                score += 5
            elif p.roce >= 12:
                score += 3
            elif p.roce >= 8:
                score += 1
        else:
            # Give banking stocks average ROCE score
            score += 4

        # NPM
        if p.npm >= 20:
            score += 5
        elif p.npm >= 15:
            score += 4
        elif p.npm >= 10:
            score += 3
        elif p.npm >= 5:
            score += 2
        elif p.npm > 0:
            score += 1

        # OPM
        if p.opm >= 25:
            score += 4
        elif p.opm >= 20:
            score += 3
        elif p.opm >= 15:
            score += 2
        elif p.opm >= 10:
            score += 1

        return min(25, score)

    def _score_growth(self, p: FundamentalProfile) -> int:
        """Score 0-25: Revenue(0-7), Profit(0-7), EPS(0-6), Quarterly(0-5)."""
        score = 0

        # Revenue CAGR 3Y
        if p.revenue_growth_3y >= 25:
            score += 7
        elif p.revenue_growth_3y >= 20:
            score += 6
        elif p.revenue_growth_3y >= 15:
            score += 4
        elif p.revenue_growth_3y >= 10:
            score += 2
        elif p.revenue_growth_3y >= 5:
            score += 1

        # Profit CAGR 3Y
        if p.profit_growth_3y >= 30:
            score += 7
        elif p.profit_growth_3y >= 25:
            score += 6
        elif p.profit_growth_3y >= 20:
            score += 4
        elif p.profit_growth_3y >= 15:
            score += 3
        elif p.profit_growth_3y >= 10:
            score += 1

        # EPS CAGR 3Y
        if p.eps_growth_3y >= 30:
            score += 6
        elif p.eps_growth_3y >= 25:
            score += 5
        elif p.eps_growth_3y >= 20:
            score += 3
        elif p.eps_growth_3y >= 15:
            score += 2

        # Quarterly momentum
        if p.qtr_eps_acceleration and p.consecutive_qtr_growth >= 4:
            score += 5
        elif p.consecutive_qtr_growth >= 4:
            score += 4
        elif p.qtr_eps_acceleration:
            score += 3
        elif p.consecutive_qtr_growth >= 2:
            score += 2
        elif p.latest_qtr_profit_yoy > 0:
            score += 1

        return min(25, score)

    def _score_financial_health(self, p: FundamentalProfile) -> int:
        """Score 0-15: D/E(0-5), Interest(0-4), CF(0-3), Current(0-3)."""
        score = 0

        # D/E ratio (skip for banking)
        if not p.is_banking:
            de = p.debt_to_equity
            if de < 0.1:
                score += 5
            elif de < 0.3:
                score += 4
            elif de < 0.5:
                score += 3
            elif de < 1.0:
                score += 2
            elif de < 2.0:
                score += 1
        else:
            score += 3  # Average for banking

        # Interest coverage
        ic = p.interest_coverage
        if ic >= 10:
            score += 4
        elif ic >= 5:
            score += 3
        elif ic >= 3:
            score += 2
        elif ic >= 1.5:
            score += 1

        # CF positive years (out of 5)
        if p.cash_flow_positive_years >= 5:
            score += 3
        elif p.cash_flow_positive_years >= 4:
            score += 2
        elif p.cash_flow_positive_years >= 3:
            score += 1

        # Current ratio
        cr = p.current_ratio
        if cr >= 2.0:
            score += 3
        elif cr >= 1.5:
            score += 2
        elif cr >= 1.0:
            score += 1

        return min(15, score)

    def _score_quality(self, p: FundamentalProfile) -> int:
        """Score 0-15: ROCE consistency(0-4), Rev consistency(0-3), NPM(0-2),
        Promoter(0-3), FII trend(0-3)."""
        score = 0

        # ROCE consistency
        if p.roce_consistent_above_15:
            score += 4
        elif p.roce >= 15:
            score += 2

        # Revenue growth consistency
        if p.revenue_growing_consistently:
            score += 3
        elif p.revenue_growth_3y > 0:
            score += 1

        # NPM stable or improving
        if p.npm_stable_or_improving:
            score += 2

        # Promoter holding
        if p.promoter_holding >= 50:
            score += 3
        elif p.promoter_holding >= 40:
            score += 2
        elif p.promoter_holding >= 30:
            score += 1

        # Promoter pledge penalty
        if p.promoter_pledge > 20:
            score -= 3
        elif p.promoter_pledge > 10:
            score -= 2
        elif p.promoter_pledge > 5:
            score -= 1

        # FII trend
        if p.fii_holding_change_1y > 2:
            score += 3
        elif p.fii_holding_change_1y > 0:
            score += 2
        elif p.fii_holding_change_1y >= -1:
            score += 1

        return max(0, min(15, score))

    def _assign_grade(self, total: int) -> str:
        if total >= 90:
            return "A+"
        elif total >= 80:
            return "A"
        elif total >= 65:
            return "B"
        elif total >= 50:
            return "C"
        elif total >= 35:
            return "D"
        else:
            return "F"

    def _identify_flags(self, p: FundamentalProfile) -> Tuple[List[str], List[str]]:
        """Identify green and red flags."""
        green = []
        red = []

        # Green flags
        if p.roe >= 20:
            green.append(f"High ROE: {p.roe:.1f}%")
        if p.roce >= 20 and not p.is_banking:
            green.append(f"High ROCE: {p.roce:.1f}%")
        if p.debt_to_equity < 0.1 and not p.is_banking:
            green.append("Debt-free")
        if p.profit_growth_3y >= 20:
            green.append(f"Strong profit growth: {p.profit_growth_3y:.0f}% CAGR")
        if p.free_cash_flow > 0 and p.fcf_yield > 3:
            green.append(f"Strong FCF yield: {p.fcf_yield:.1f}%")
        if p.roce_consistent_above_15:
            green.append("Consistent ROCE >15% (5 years)")
        if p.promoter_holding >= 60:
            green.append(f"High promoter holding: {p.promoter_holding:.1f}%")
        if p.fii_holding_change_1y > 2:
            green.append(f"FII buying: +{p.fii_holding_change_1y:.1f}%")
        if p.qtr_eps_acceleration:
            green.append("Quarterly earnings accelerating")
        if p.dividend_yield >= 3:
            green.append(f"High dividend yield: {p.dividend_yield:.1f}%")
        if 0 < p.peg_ratio <= 1:
            green.append(f"Attractive PEG: {p.peg_ratio:.1f}")
        if p.no_loss_years_5:
            green.append("No loss in last 5 years")

        # Red flags
        if p.pe_ratio > 80:
            red.append(f"Very high PE: {p.pe_ratio:.0f}")
        if p.pe_ratio < 0:
            red.append("Loss-making (negative PE)")
        if p.debt_to_equity > 2.0 and not p.is_banking:
            red.append(f"Over-leveraged: D/E {p.debt_to_equity:.1f}")
        if p.roe < 8 and p.roe != 0:
            red.append(f"Low ROE: {p.roe:.1f}%")
        if p.profit_growth_3y < 0:
            red.append(f"Declining profits: {p.profit_growth_3y:.0f}%")
        if p.free_cash_flow < 0:
            red.append("Negative free cash flow")
        if p.promoter_pledge > 20:
            red.append(f"High promoter pledge: {p.promoter_pledge:.0f}%")
        if p.promoter_holding_change_1y < -3:
            red.append(f"Promoter selling: {p.promoter_holding_change_1y:.1f}%")
        if p.fii_holding_change_1y < -3:
            red.append(f"FII selling: {p.fii_holding_change_1y:.1f}%")
        if p.interest_coverage > 0 and p.interest_coverage < 2:
            red.append(f"Weak interest coverage: {p.interest_coverage:.1f}x")
        if p.latest_qtr_profit_yoy < -20:
            red.append(f"Quarterly profit down: {p.latest_qtr_profit_yoy:.0f}% YoY")

        return green, red
