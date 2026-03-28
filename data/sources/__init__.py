"""
Data Sources - Multiple providers for market data.

Primary: TrueData API (reliable, real-time Indian market data)
Fallback: yfinance (free, but less reliable)
Additional: FII/DII flows, F&O data, earnings, fundamentals
"""

from .fo_data import FODataFetcher, OptionChainAnalysis
from .fii_dii import FIIDIITracker, FlowAnalysis
from .earnings import EarningsCalendar, EarningsEvent
from .fundamentals import FundamentalsFilter, FundamentalCheckResult
from .truedata import (
    TrueDataClient,
    TrueDataConfig,
    TrueDataAuth,
    TrueDataMarketAPI,
    TrueDataCorporateAPI,
    OHLCVData,
    FIIDIIData,
    ShareholdingData,
    EarningsData,
    FinancialRatios,
    DataQuality,
    get_truedata_client,
)

__all__ = [
    # F&O Data
    'FODataFetcher',
    'OptionChainAnalysis',
    # FII/DII
    'FIIDIITracker',
    'FlowAnalysis',
    # Earnings
    'EarningsCalendar',
    'EarningsEvent',
    # Fundamentals
    'FundamentalsFilter',
    'FundamentalCheckResult',
    # TrueData API
    'TrueDataClient',
    'TrueDataConfig',
    'TrueDataAuth',
    'TrueDataMarketAPI',
    'TrueDataCorporateAPI',
    'OHLCVData',
    'FIIDIIData',
    'ShareholdingData',
    'EarningsData',
    'FinancialRatios',
    'DataQuality',
    'get_truedata_client',
]
