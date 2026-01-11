"""
Fundamentals Filter - Quality check for trading candidates.

Critical insights:
- Technical signals on weak fundamentals = house built on sand
- Debt-laden companies amplify downside risk
- Quality stocks recover faster from drawdowns
- ROE > 15% = management creating value
- Cash flow positive = sustainable business

Rule: Only trade technically strong + fundamentally sound stocks.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import pandas as pd
import requests
from rich.console import Console

console = Console()


class FundamentalGrade(Enum):
    """Fundamental quality grade."""
    A = "A"  # Excellent - Green flag
    B = "B"  # Good - Acceptable
    C = "C"  # Average - Caution
    D = "D"  # Poor - Avoid
    F = "F"  # Failing - Do not trade


class DebtLevel(Enum):
    """Debt classification."""
    DEBT_FREE = "DEBT_FREE"
    LOW_DEBT = "LOW_DEBT"
    MODERATE_DEBT = "MODERATE_DEBT"
    HIGH_DEBT = "HIGH_DEBT"
    OVER_LEVERAGED = "OVER_LEVERAGED"


@dataclass
class FundamentalData:
    """Fundamental data for a stock."""
    symbol: str
    company_name: str
    sector: str
    industry: str

    # Valuation
    market_cap: float  # In Cr
    pe_ratio: float
    pb_ratio: float
    ev_ebitda: float

    # Profitability
    roe: float  # Return on Equity %
    roce: float  # Return on Capital Employed %
    npm: float  # Net Profit Margin %
    opm: float  # Operating Profit Margin %

    # Growth
    revenue_growth_3y: float  # 3-year CAGR %
    profit_growth_3y: float  # 3-year CAGR %
    eps_growth_3y: float  # 3-year CAGR %

    # Financial health
    debt_to_equity: float
    current_ratio: float
    interest_coverage: float

    # Cash flow
    operating_cash_flow: float  # In Cr
    free_cash_flow: float  # In Cr
    cash_flow_positive: bool

    # Quality metrics
    promoter_holding: float  # %
    promoter_pledge: float  # % of promoter holding pledged
    institutional_holding: float  # FII + DII %

    # Derived
    grade: FundamentalGrade = FundamentalGrade.C
    debt_level: DebtLevel = DebtLevel.MODERATE_DEBT
    quality_score: int = 50  # 0-100
    red_flags: List[str] = field(default_factory=list)
    green_flags: List[str] = field(default_factory=list)


@dataclass
class FundamentalCheckResult:
    """Result of fundamental quality check."""
    symbol: str
    passes_filter: bool
    grade: FundamentalGrade
    quality_score: int
    position_multiplier: float  # 0.0 to 1.0

    # Detailed
    data: Optional[FundamentalData] = None
    red_flags: List[str] = field(default_factory=list)
    green_flags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class FundamentalsFilter:
    """
    Filter stocks based on fundamental quality.

    Data sources:
    - BSE/NSE financial data
    - Screener.in style metrics
    - Manual cache for Nifty 100
    """

    # Thresholds for filtering
    MIN_MARKET_CAP = 5000  # 5000 Cr minimum
    MAX_PE = 100  # Skip extreme PE
    MIN_ROE = 10  # Minimum ROE %
    MAX_DEBT_TO_EQUITY = 2.0  # Maximum D/E ratio
    MIN_PROMOTER_HOLDING = 25  # Minimum promoter %
    MAX_PROMOTER_PLEDGE = 30  # Maximum pledge %

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        self._cache: Dict[str, FundamentalData] = {}
        self._load_nifty100_fundamentals()

    def _load_nifty100_fundamentals(self):
        """
        Load fundamental data for Nifty 100 stocks.

        Note: In production, this would fetch from BSE/NSE/Screener.in API.
        Using representative data for development.
        """
        # Representative fundamental data for major Nifty 100 stocks
        # In production: Fetch from screener.in API or NSE corporate filings

        nifty100_data = {
            # Large Cap IT - Strong fundamentals
            "TCS": {
                "company_name": "Tata Consultancy Services",
                "sector": "IT",
                "industry": "IT Services",
                "market_cap": 1400000,
                "pe_ratio": 30,
                "pb_ratio": 12,
                "ev_ebitda": 22,
                "roe": 48,
                "roce": 58,
                "npm": 19,
                "opm": 25,
                "revenue_growth_3y": 12,
                "profit_growth_3y": 10,
                "eps_growth_3y": 11,
                "debt_to_equity": 0.05,
                "current_ratio": 2.5,
                "interest_coverage": 100,
                "operating_cash_flow": 45000,
                "free_cash_flow": 40000,
                "promoter_holding": 72,
                "promoter_pledge": 0,
                "institutional_holding": 18,
            },
            "INFY": {
                "company_name": "Infosys",
                "sector": "IT",
                "industry": "IT Services",
                "market_cap": 650000,
                "pe_ratio": 25,
                "pb_ratio": 8,
                "ev_ebitda": 18,
                "roe": 32,
                "roce": 38,
                "npm": 17,
                "opm": 23,
                "revenue_growth_3y": 14,
                "profit_growth_3y": 12,
                "eps_growth_3y": 13,
                "debt_to_equity": 0.08,
                "current_ratio": 2.2,
                "interest_coverage": 80,
                "operating_cash_flow": 25000,
                "free_cash_flow": 22000,
                "promoter_holding": 15,
                "promoter_pledge": 0,
                "institutional_holding": 55,
            },

            # Banks - Moderate leverage expected
            "HDFCBANK": {
                "company_name": "HDFC Bank",
                "sector": "Banking",
                "industry": "Private Bank",
                "market_cap": 1200000,
                "pe_ratio": 22,
                "pb_ratio": 3.5,
                "ev_ebitda": 0,  # Not applicable for banks
                "roe": 17,
                "roce": 0,  # Not applicable for banks
                "npm": 22,
                "opm": 0,
                "revenue_growth_3y": 18,
                "profit_growth_3y": 20,
                "eps_growth_3y": 19,
                "debt_to_equity": 0,  # Banks have different metrics
                "current_ratio": 0,
                "interest_coverage": 0,
                "operating_cash_flow": 50000,
                "free_cash_flow": 45000,
                "promoter_holding": 26,
                "promoter_pledge": 0,
                "institutional_holding": 55,
            },
            "ICICIBANK": {
                "company_name": "ICICI Bank",
                "sector": "Banking",
                "industry": "Private Bank",
                "market_cap": 800000,
                "pe_ratio": 20,
                "pb_ratio": 3.0,
                "ev_ebitda": 0,
                "roe": 16,
                "roce": 0,
                "npm": 20,
                "opm": 0,
                "revenue_growth_3y": 20,
                "profit_growth_3y": 25,
                "eps_growth_3y": 24,
                "debt_to_equity": 0,
                "current_ratio": 0,
                "interest_coverage": 0,
                "operating_cash_flow": 40000,
                "free_cash_flow": 35000,
                "promoter_holding": 0,  # Widely held
                "promoter_pledge": 0,
                "institutional_holding": 60,
            },

            # Reliance - Conglomerate
            "RELIANCE": {
                "company_name": "Reliance Industries",
                "sector": "Energy",
                "industry": "Oil & Gas",
                "market_cap": 1800000,
                "pe_ratio": 28,
                "pb_ratio": 2.5,
                "ev_ebitda": 12,
                "roe": 9,
                "roce": 10,
                "npm": 8,
                "opm": 15,
                "revenue_growth_3y": 22,
                "profit_growth_3y": 15,
                "eps_growth_3y": 14,
                "debt_to_equity": 0.4,
                "current_ratio": 1.1,
                "interest_coverage": 8,
                "operating_cash_flow": 120000,
                "free_cash_flow": 80000,
                "promoter_holding": 50,
                "promoter_pledge": 0,
                "institutional_holding": 30,
            },

            # FMCG - Stable but expensive
            "HINDUNILVR": {
                "company_name": "Hindustan Unilever",
                "sector": "FMCG",
                "industry": "FMCG",
                "market_cap": 600000,
                "pe_ratio": 60,
                "pb_ratio": 12,
                "ev_ebitda": 40,
                "roe": 20,
                "roce": 25,
                "npm": 15,
                "opm": 22,
                "revenue_growth_3y": 8,
                "profit_growth_3y": 10,
                "eps_growth_3y": 10,
                "debt_to_equity": 0.02,
                "current_ratio": 1.5,
                "interest_coverage": 200,
                "operating_cash_flow": 12000,
                "free_cash_flow": 10000,
                "promoter_holding": 62,
                "promoter_pledge": 0,
                "institutional_holding": 25,
            },
            "ITC": {
                "company_name": "ITC Limited",
                "sector": "FMCG",
                "industry": "Tobacco/FMCG",
                "market_cap": 550000,
                "pe_ratio": 28,
                "pb_ratio": 8,
                "ev_ebitda": 18,
                "roe": 28,
                "roce": 35,
                "npm": 28,
                "opm": 38,
                "revenue_growth_3y": 10,
                "profit_growth_3y": 12,
                "eps_growth_3y": 12,
                "debt_to_equity": 0.01,
                "current_ratio": 2.5,
                "interest_coverage": 500,
                "operating_cash_flow": 18000,
                "free_cash_flow": 15000,
                "promoter_holding": 0,  # Widely held
                "promoter_pledge": 0,
                "institutional_holding": 50,
            },

            # Auto - Cyclical
            "MARUTI": {
                "company_name": "Maruti Suzuki",
                "sector": "Auto",
                "industry": "Passenger Vehicles",
                "market_cap": 400000,
                "pe_ratio": 35,
                "pb_ratio": 5,
                "ev_ebitda": 22,
                "roe": 14,
                "roce": 18,
                "npm": 8,
                "opm": 11,
                "revenue_growth_3y": 15,
                "profit_growth_3y": 18,
                "eps_growth_3y": 17,
                "debt_to_equity": 0.02,
                "current_ratio": 1.8,
                "interest_coverage": 100,
                "operating_cash_flow": 15000,
                "free_cash_flow": 10000,
                "promoter_holding": 56,
                "promoter_pledge": 0,
                "institutional_holding": 30,
            },

            # Pharma
            "SUNPHARMA": {
                "company_name": "Sun Pharmaceutical",
                "sector": "Pharma",
                "industry": "Pharmaceuticals",
                "market_cap": 350000,
                "pe_ratio": 40,
                "pb_ratio": 4,
                "ev_ebitda": 25,
                "roe": 11,
                "roce": 13,
                "npm": 18,
                "opm": 25,
                "revenue_growth_3y": 12,
                "profit_growth_3y": 15,
                "eps_growth_3y": 14,
                "debt_to_equity": 0.15,
                "current_ratio": 2.0,
                "interest_coverage": 30,
                "operating_cash_flow": 8000,
                "free_cash_flow": 5000,
                "promoter_holding": 54,
                "promoter_pledge": 0,
                "institutional_holding": 25,
            },

            # Example of weaker fundamentals
            "TATASTEEL": {
                "company_name": "Tata Steel",
                "sector": "Metals",
                "industry": "Steel",
                "market_cap": 180000,
                "pe_ratio": 8,
                "pb_ratio": 1.5,
                "ev_ebitda": 5,
                "roe": 15,
                "roce": 12,
                "npm": 8,
                "opm": 18,
                "revenue_growth_3y": 20,
                "profit_growth_3y": 30,
                "eps_growth_3y": 28,
                "debt_to_equity": 0.8,
                "current_ratio": 0.9,
                "interest_coverage": 5,
                "operating_cash_flow": 25000,
                "free_cash_flow": 15000,
                "promoter_holding": 33,
                "promoter_pledge": 0,
                "institutional_holding": 40,
            },

            # High debt example
            "VEDL": {
                "company_name": "Vedanta Limited",
                "sector": "Metals",
                "industry": "Mining",
                "market_cap": 120000,
                "pe_ratio": 6,
                "pb_ratio": 1.2,
                "ev_ebitda": 4,
                "roe": 18,
                "roce": 15,
                "npm": 12,
                "opm": 30,
                "revenue_growth_3y": 25,
                "profit_growth_3y": 40,
                "eps_growth_3y": 38,
                "debt_to_equity": 1.5,
                "current_ratio": 0.8,
                "interest_coverage": 3,
                "operating_cash_flow": 20000,
                "free_cash_flow": 10000,
                "promoter_holding": 65,
                "promoter_pledge": 25,  # High pledge
                "institutional_holding": 20,
            },
        }

        # Convert to FundamentalData objects
        for symbol, data in nifty100_data.items():
            fundamental = FundamentalData(
                symbol=symbol,
                company_name=data["company_name"],
                sector=data["sector"],
                industry=data["industry"],
                market_cap=data["market_cap"],
                pe_ratio=data["pe_ratio"],
                pb_ratio=data["pb_ratio"],
                ev_ebitda=data["ev_ebitda"],
                roe=data["roe"],
                roce=data["roce"],
                npm=data["npm"],
                opm=data["opm"],
                revenue_growth_3y=data["revenue_growth_3y"],
                profit_growth_3y=data["profit_growth_3y"],
                eps_growth_3y=data["eps_growth_3y"],
                debt_to_equity=data["debt_to_equity"],
                current_ratio=data["current_ratio"],
                interest_coverage=data["interest_coverage"],
                operating_cash_flow=data["operating_cash_flow"],
                free_cash_flow=data["free_cash_flow"],
                cash_flow_positive=data["free_cash_flow"] > 0,
                promoter_holding=data["promoter_holding"],
                promoter_pledge=data["promoter_pledge"],
                institutional_holding=data["institutional_holding"],
            )

            # Calculate grade and flags
            self._calculate_grade(fundamental)
            self._cache[symbol] = fundamental

    def _calculate_grade(self, data: FundamentalData) -> None:
        """Calculate fundamental grade and identify flags."""
        score = 50  # Start neutral
        red_flags = []
        green_flags = []

        # Profitability checks
        if data.roe >= 20:
            score += 15
            green_flags.append(f"High ROE: {data.roe}%")
        elif data.roe >= 15:
            score += 10
            green_flags.append(f"Good ROE: {data.roe}%")
        elif data.roe < 10:
            score -= 15
            red_flags.append(f"Low ROE: {data.roe}%")

        # Debt checks
        if data.debt_to_equity < 0.1:
            score += 10
            green_flags.append("Debt-free")
            data.debt_level = DebtLevel.DEBT_FREE
        elif data.debt_to_equity < 0.5:
            score += 5
            data.debt_level = DebtLevel.LOW_DEBT
        elif data.debt_to_equity < 1.0:
            data.debt_level = DebtLevel.MODERATE_DEBT
        elif data.debt_to_equity < 2.0:
            score -= 10
            red_flags.append(f"High debt: D/E {data.debt_to_equity}")
            data.debt_level = DebtLevel.HIGH_DEBT
        else:
            score -= 20
            red_flags.append(f"Over-leveraged: D/E {data.debt_to_equity}")
            data.debt_level = DebtLevel.OVER_LEVERAGED

        # Growth checks
        if data.profit_growth_3y >= 20:
            score += 10
            green_flags.append(f"Strong profit growth: {data.profit_growth_3y}%")
        elif data.profit_growth_3y >= 10:
            score += 5
        elif data.profit_growth_3y < 0:
            score -= 15
            red_flags.append(f"Declining profits: {data.profit_growth_3y}%")

        # Cash flow checks
        if data.cash_flow_positive and data.free_cash_flow > 0:
            score += 10
            green_flags.append("Strong free cash flow")
        elif data.free_cash_flow < 0:
            score -= 15
            red_flags.append("Negative free cash flow")

        # Promoter holding
        if data.promoter_holding >= 50:
            score += 5
            green_flags.append(f"High promoter holding: {data.promoter_holding}%")
        elif data.promoter_holding < 25 and data.promoter_holding > 0:
            score -= 5
            red_flags.append(f"Low promoter holding: {data.promoter_holding}%")

        # Promoter pledge
        if data.promoter_pledge > 30:
            score -= 20
            red_flags.append(f"High promoter pledge: {data.promoter_pledge}%")
        elif data.promoter_pledge > 10:
            score -= 10
            red_flags.append(f"Promoter pledge: {data.promoter_pledge}%")

        # Interest coverage
        if data.interest_coverage > 0 and data.interest_coverage < 3:
            score -= 10
            red_flags.append(f"Weak interest coverage: {data.interest_coverage}x")

        # Valuation (moderate impact - technical handles timing)
        if data.pe_ratio > 80:
            score -= 5
            red_flags.append(f"Very high PE: {data.pe_ratio}")
        elif data.pe_ratio < 0:
            score -= 10
            red_flags.append("Loss-making (negative PE)")

        # Assign grade
        score = max(0, min(100, score))
        data.quality_score = score

        if score >= 80:
            data.grade = FundamentalGrade.A
        elif score >= 65:
            data.grade = FundamentalGrade.B
        elif score >= 50:
            data.grade = FundamentalGrade.C
        elif score >= 35:
            data.grade = FundamentalGrade.D
        else:
            data.grade = FundamentalGrade.F

        data.red_flags = red_flags
        data.green_flags = green_flags

    def check_stock(self, symbol: str) -> FundamentalCheckResult:
        """
        Check fundamental quality of a stock.

        Returns whether it passes filter and grade.
        """
        # Check cache
        data = self._cache.get(symbol)

        if not data:
            # Stock not in cache - return neutral (don't filter)
            return FundamentalCheckResult(
                symbol=symbol,
                passes_filter=True,
                grade=FundamentalGrade.C,
                quality_score=50,
                position_multiplier=0.8,
                notes=["Fundamental data not available - proceed with caution"]
            )

        # Determine if passes filter
        passes = True
        notes = []

        # Hard filters
        if data.grade == FundamentalGrade.F:
            passes = False
            notes.append("FAILING fundamentals - Do not trade")
        elif data.promoter_pledge > self.MAX_PROMOTER_PLEDGE:
            passes = False
            notes.append(f"Promoter pledge too high: {data.promoter_pledge}%")
        elif data.debt_level == DebtLevel.OVER_LEVERAGED:
            passes = False
            notes.append("Over-leveraged - Avoid")

        # Position size multiplier based on grade
        if data.grade == FundamentalGrade.A:
            multiplier = 1.0
            notes.append("Excellent fundamentals - Full position")
        elif data.grade == FundamentalGrade.B:
            multiplier = 0.9
            notes.append("Good fundamentals")
        elif data.grade == FundamentalGrade.C:
            multiplier = 0.7
            notes.append("Average fundamentals - Reduced position")
        elif data.grade == FundamentalGrade.D:
            multiplier = 0.5
            notes.append("Weak fundamentals - Half position max")
        else:
            multiplier = 0.0
            notes.append("Failing fundamentals - No position")

        return FundamentalCheckResult(
            symbol=symbol,
            passes_filter=passes,
            grade=data.grade,
            quality_score=data.quality_score,
            position_multiplier=multiplier if passes else 0.0,
            data=data,
            red_flags=data.red_flags,
            green_flags=data.green_flags,
            notes=notes
        )

    def filter_signals(
        self,
        signals: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter trading signals based on fundamental quality.

        Returns (tradable_signals, filtered_out)
        """
        tradable = []
        filtered = []

        for signal in signals:
            symbol = signal.get('symbol', '')
            result = self.check_stock(symbol)

            if not result.passes_filter:
                signal['filter_reason'] = "; ".join(result.red_flags)
                signal['fundamental_grade'] = result.grade.value
                filtered.append(signal)
            else:
                signal['fundamental_grade'] = result.grade.value
                signal['fundamental_score'] = result.quality_score
                signal['fundamental_multiplier'] = result.position_multiplier
                signal['fundamental_flags'] = {
                    'green': result.green_flags,
                    'red': result.red_flags
                }
                tradable.append(signal)

        return tradable, filtered

    def get_sector_fundamentals(self, sector: str) -> List[FundamentalData]:
        """Get all stocks in a sector sorted by quality score."""
        sector_stocks = [
            data for data in self._cache.values()
            if data.sector.lower() == sector.lower()
        ]
        return sorted(sector_stocks, key=lambda x: x.quality_score, reverse=True)

    def get_top_quality_stocks(self, n: int = 20) -> List[FundamentalData]:
        """Get top N quality stocks by fundamental score."""
        all_stocks = list(self._cache.values())
        return sorted(all_stocks, key=lambda x: x.quality_score, reverse=True)[:n]

    def get_summary(self, symbol: str) -> str:
        """Get human-readable fundamental summary."""
        result = self.check_stock(symbol)

        if not result.data:
            return f"{symbol}: Fundamental data not available"

        data = result.data
        lines = [
            f"{'=' * 50}",
            f"FUNDAMENTALS: {symbol}",
            f"{'=' * 50}",
            f"Grade: {data.grade.value} ({data.quality_score}/100)",
            f"",
            f"[VALUATION]",
            f"  PE: {data.pe_ratio} | PB: {data.pb_ratio}",
            f"  Market Cap: ₹{data.market_cap:,.0f} Cr",
            f"",
            f"[PROFITABILITY]",
            f"  ROE: {data.roe}% | ROCE: {data.roce}%",
            f"  NPM: {data.npm}% | OPM: {data.opm}%",
            f"",
            f"[GROWTH (3Y CAGR)]",
            f"  Revenue: {data.revenue_growth_3y}%",
            f"  Profit: {data.profit_growth_3y}%",
            f"",
            f"[FINANCIAL HEALTH]",
            f"  Debt/Equity: {data.debt_to_equity}",
            f"  Status: {data.debt_level.value}",
            f"",
            f"[OWNERSHIP]",
            f"  Promoter: {data.promoter_holding}% (Pledge: {data.promoter_pledge}%)",
            f"  Institutional: {data.institutional_holding}%",
        ]

        if data.green_flags:
            lines.append(f"\n[GREEN FLAGS]")
            for flag in data.green_flags:
                lines.append(f"  + {flag}")

        if data.red_flags:
            lines.append(f"\n[RED FLAGS]")
            for flag in data.red_flags:
                lines.append(f"  - {flag}")

        lines.append(f"{'=' * 50}")

        return "\n".join(lines)


def get_fundamental_score(symbol: str) -> int:
    """Quick function to get fundamental score for a stock."""
    filter = FundamentalsFilter()
    result = filter.check_stock(symbol)
    return result.quality_score
