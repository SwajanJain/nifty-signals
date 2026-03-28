"""
Data Models for Nifty Signals

Essential data classes used across the trading system.
"""

import pandas as pd
from datetime import datetime
from typing import Optional, List, Any
from dataclasses import dataclass, field
from enum import Enum


class DataQuality(Enum):
    """Data quality levels - used for position sizing decisions"""
    EXCELLENT = "excellent"  # Fresh, complete, verified
    GOOD = "good"            # Recent, mostly complete
    DEGRADED = "degraded"    # Stale or partial data
    UNUSABLE = "unusable"    # Missing or invalid


@dataclass
class OHLCVData:
    """OHLCV data result from any source"""
    symbol: str
    df: pd.DataFrame
    quality: DataQuality
    source: str = "yfinance"
    fetched_at: datetime = field(default_factory=datetime.now)

    @property
    def is_valid(self) -> bool:
        return self.quality in [DataQuality.EXCELLENT, DataQuality.GOOD] and len(self.df) > 0

    @property
    def row_count(self) -> int:
        return len(self.df) if self.df is not None else 0


@dataclass
class DataResult:
    """Unified data result from any source"""
    data: Any
    quality: DataQuality
    source: str
    fetched_at: datetime = field(default_factory=datetime.now)
    staleness_hours: float = 0.0
    warnings: List[str] = field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        return self.quality in [DataQuality.EXCELLENT, DataQuality.GOOD, DataQuality.DEGRADED]

    @property
    def is_reliable(self) -> bool:
        return self.quality in [DataQuality.EXCELLENT, DataQuality.GOOD]


@dataclass
class SystemDataHealth:
    """Overall system data health status"""
    price_data: DataQuality
    fundamentals_data: DataQuality
    overall: DataQuality

    yfinance_available: bool

    # Recommended adjustments based on data quality
    position_size_multiplier: float
    allow_trading: bool
    warnings: List[str] = field(default_factory=list)
