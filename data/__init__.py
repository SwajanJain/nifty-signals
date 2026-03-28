"""
Data Layer - yfinance-based data fetching with quality monitoring.

Components:
- models: Core data models (DataQuality, OHLCVData, etc.)
- reliable_fetcher: yfinance fetcher with symbol mappings
- quality_monitor: Data quality gates and monitoring
- fetcher: Legacy yfinance-based fetcher
- cache: Data caching layer
"""

from .fetcher import StockDataFetcher
from .cache import DataCache
from .models import (
    DataQuality,
    OHLCVData,
    DataResult,
    SystemDataHealth,
)
from .reliable_fetcher import (
    ReliableDataFetcher,
    get_reliable_fetcher,
    SYMBOL_MAPPINGS,
    KNOWN_FAILURES,
)
from .quality_monitor import (
    DataGates,
    DataGateResults,
    GateResult,
    GateStatus,
    DataQualityMonitor,
    get_data_gates,
    get_quality_monitor,
)

__all__ = [
    # Legacy
    "StockDataFetcher",
    "DataCache",
    # Models
    "DataQuality",
    "OHLCVData",
    "DataResult",
    "SystemDataHealth",
    # Reliable fetcher
    "ReliableDataFetcher",
    "get_reliable_fetcher",
    "SYMBOL_MAPPINGS",
    "KNOWN_FAILURES",
    # Quality monitor
    "DataGates",
    "DataGateResults",
    "GateResult",
    "GateStatus",
    "DataQualityMonitor",
    "get_data_gates",
    "get_quality_monitor",
]
