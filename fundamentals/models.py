"""Data models for fundamental analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ScreenerRawData:
    """Raw data scraped from screener.in for a single stock."""

    symbol: str
    company_name: str
    sector: str
    industry: str

    # Top-line ratios
    market_cap: float = 0.0  # Cr
    current_price: float = 0.0
    pe_ratio: float = 0.0
    book_value: float = 0.0  # per share
    dividend_yield: float = 0.0  # %
    roce: float = 0.0  # %
    roe: float = 0.0  # %
    face_value: float = 10.0
    high_52w: float = 0.0
    low_52w: float = 0.0

    # Quarterly results: list of dicts per quarter
    # Keys: period, sales, expenses, operating_profit, opm_pct,
    #        other_income, interest, depreciation, pbt, tax_pct,
    #        net_profit, eps
    quarterly_results: List[Dict[str, Any]] = field(default_factory=list)

    # Annual P&L: list of dicts per year (+ TTM)
    annual_pl: List[Dict[str, Any]] = field(default_factory=list)

    # Growth rates from screener
    compounded_sales_growth: Dict[str, float] = field(default_factory=dict)
    compounded_profit_growth: Dict[str, float] = field(default_factory=dict)
    stock_price_cagr: Dict[str, float] = field(default_factory=dict)
    return_on_equity: Dict[str, float] = field(default_factory=dict)

    # Balance sheet: list of dicts per year
    balance_sheet: List[Dict[str, Any]] = field(default_factory=list)

    # Cash flow: list of dicts per year
    cash_flow: List[Dict[str, Any]] = field(default_factory=list)

    # Ratios: list of dicts per year
    ratios: List[Dict[str, Any]] = field(default_factory=list)

    # Shareholding: list of dicts per quarter
    shareholding: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    fetched_at: Optional[datetime] = None
    is_consolidated: bool = True
    data_quality: str = "GOOD"  # GOOD, PARTIAL, MISSING


@dataclass
class FundamentalProfile:
    """Computed fundamental profile for screening strategies."""

    symbol: str
    company_name: str
    sector: str
    industry: str

    # --- Valuation ---
    market_cap: float = 0.0  # Cr
    current_price: float = 0.0
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    ev_ebitda: float = 0.0
    peg_ratio: float = 0.0
    dividend_yield: float = 0.0  # %
    fcf_yield: float = 0.0  # %
    earnings_yield: float = 0.0  # %
    price_to_sales: float = 0.0

    # --- Profitability ---
    roe: float = 0.0  # %
    roce: float = 0.0  # %
    npm: float = 0.0  # Net profit margin % (TTM)
    opm: float = 0.0  # Operating profit margin % (TTM)

    # --- DuPont Decomposition ---
    dupont_npm: float = 0.0
    dupont_asset_turnover: float = 0.0
    dupont_equity_multiplier: float = 0.0

    # --- Growth ---
    revenue_growth_3y: float = 0.0  # CAGR %
    revenue_growth_5y: float = 0.0
    profit_growth_3y: float = 0.0  # CAGR %
    profit_growth_5y: float = 0.0
    eps_growth_3y: float = 0.0  # CAGR %
    eps_growth_5y: float = 0.0

    # --- Quarterly Momentum ---
    latest_qtr_revenue_yoy: float = 0.0  # % YoY growth
    latest_qtr_profit_yoy: float = 0.0
    qtr_eps_acceleration: bool = False
    consecutive_qtr_growth: int = 0

    # --- Financial Health ---
    debt_to_equity: float = 0.0
    current_ratio: float = 0.0
    interest_coverage: float = 0.0

    # --- Cash Flow ---
    operating_cash_flow: float = 0.0  # Cr (latest year)
    free_cash_flow: float = 0.0  # OCF - Capex
    cash_flow_positive_years: int = 0  # out of last 5
    fcf_positive_years: int = 0

    # --- Efficiency ---
    debtor_days: float = 0.0
    inventory_days: float = 0.0
    working_capital_days: float = 0.0
    asset_turnover: float = 0.0

    # --- Ownership ---
    promoter_holding: float = 0.0  # %
    promoter_holding_change_1y: float = 0.0
    promoter_pledge: float = 0.0  # %
    fii_holding: float = 0.0  # %
    dii_holding: float = 0.0  # %
    fii_holding_change_1y: float = 0.0

    # --- Consistency (5 years) ---
    roce_consistent_above_15: bool = False
    revenue_growing_consistently: bool = False
    npm_stable_or_improving: bool = False
    no_loss_years_5: bool = False
    dividend_years_5: int = 0
    dividend_growing: bool = False

    # --- Derived ---
    eps_ttm: float = 0.0
    book_value_per_share: float = 0.0
    dividend_payout_ratio: float = 0.0  # %

    # --- Metadata ---
    data_quality: str = "GOOD"
    last_updated: Optional[datetime] = None
    is_banking: bool = False


@dataclass
class FundamentalScore:
    """Composite fundamental score breakdown."""

    symbol: str
    company_name: str = ""
    sector: str = ""
    total_score: int = 0  # 0-100
    grade: str = "C"  # A+, A, B, C, D, F

    # Component scores
    valuation_score: int = 0  # 0-20
    profitability_score: int = 0  # 0-25
    growth_score: int = 0  # 0-25
    financial_health_score: int = 0  # 0-15
    quality_score: int = 0  # 0-15

    # Flags
    green_flags: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)

    # Strategy matches
    matches_value: bool = False
    matches_growth: bool = False
    matches_quality: bool = False
    matches_garp: bool = False
    matches_dividend: bool = False


@dataclass
class ScreenResult:
    """Result of running a screening strategy on a stock."""

    symbol: str
    company_name: str
    sector: str
    passes: bool
    strategy: str  # "value", "growth", "quality", "garp", "dividend"
    score: int = 0  # Strategy-specific score 0-100
    criteria_met: List[str] = field(default_factory=list)
    criteria_failed: List[str] = field(default_factory=list)
    key_metrics: Dict[str, Any] = field(default_factory=dict)
