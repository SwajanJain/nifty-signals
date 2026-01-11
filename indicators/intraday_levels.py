"""
Intraday Levels Calculator - Key levels for trading decisions.

Critical insights:
- Pivot points are self-fulfilling (everyone watches them)
- VWAP is institutional benchmark
- Previous day H/L/C are key references
- Opening range breakout sets the tone
- Multiple level confluence = high probability zone

Rule: Know your levels BEFORE the market opens.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()


class LevelType(Enum):
    """Type of price level."""
    PIVOT = "PIVOT"
    RESISTANCE = "RESISTANCE"
    SUPPORT = "SUPPORT"
    VWAP = "VWAP"
    PDH = "PDH"  # Previous Day High
    PDL = "PDL"  # Previous Day Low
    PDC = "PDC"  # Previous Day Close
    ORB_HIGH = "ORB_HIGH"  # Opening Range High
    ORB_LOW = "ORB_LOW"  # Opening Range Low
    ATH = "ATH"  # All Time High
    ATL = "ATL"  # 52-Week Low
    FIBO = "FIBO"  # Fibonacci level
    ROUND = "ROUND"  # Round number


class LevelStrength(Enum):
    """Strength of the level."""
    STRONG = "STRONG"  # Multiple confluences
    MODERATE = "MODERATE"  # Single confluence
    WEAK = "WEAK"  # Calculated level only


@dataclass
class PriceLevel:
    """A single price level."""
    price: float
    level_type: LevelType
    name: str
    strength: LevelStrength = LevelStrength.MODERATE
    confluences: List[str] = field(default_factory=list)
    distance_pct: float = 0.0  # Distance from current price


@dataclass
class IntradayLevels:
    """Complete intraday levels analysis."""
    symbol: str
    current_price: float
    calculated_at: datetime

    # Pivot system
    pivot: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float

    # Camarilla pivots
    cam_r1: float
    cam_r2: float
    cam_r3: float
    cam_r4: float
    cam_s1: float
    cam_s2: float
    cam_s3: float
    cam_s4: float

    # Previous day
    pdh: float
    pdl: float
    pdc: float

    # VWAP (if available)
    vwap: Optional[float] = None

    # Opening range (first 15/30 min)
    orb_high: Optional[float] = None
    orb_low: Optional[float] = None

    # Key zones
    immediate_resistance: float = 0.0
    immediate_support: float = 0.0

    # All levels sorted
    all_levels: List[PriceLevel] = field(default_factory=list)

    # Analysis
    bias: str = "NEUTRAL"  # BULLISH/BEARISH/NEUTRAL
    key_zones: List[Tuple[float, float, str]] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"INTRADAY LEVELS: {self.symbol}")
        lines.append(f"CMP: ₹{self.current_price:,.2f} | Bias: {self.bias}")
        lines.append("=" * 60)

        lines.append(f"\n[STANDARD PIVOTS]")
        lines.append(f"  R3: ₹{self.r3:,.2f} ({self._dist(self.r3):+.1f}%)")
        lines.append(f"  R2: ₹{self.r2:,.2f} ({self._dist(self.r2):+.1f}%)")
        lines.append(f"  R1: ₹{self.r1:,.2f} ({self._dist(self.r1):+.1f}%)")
        lines.append(f"  PP: ₹{self.pivot:,.2f} ({self._dist(self.pivot):+.1f}%)")
        lines.append(f"  S1: ₹{self.s1:,.2f} ({self._dist(self.s1):+.1f}%)")
        lines.append(f"  S2: ₹{self.s2:,.2f} ({self._dist(self.s2):+.1f}%)")
        lines.append(f"  S3: ₹{self.s3:,.2f} ({self._dist(self.s3):+.1f}%)")

        lines.append(f"\n[PREVIOUS DAY]")
        lines.append(f"  PDH: ₹{self.pdh:,.2f} ({self._dist(self.pdh):+.1f}%)")
        lines.append(f"  PDC: ₹{self.pdc:,.2f} ({self._dist(self.pdc):+.1f}%)")
        lines.append(f"  PDL: ₹{self.pdl:,.2f} ({self._dist(self.pdl):+.1f}%)")

        if self.vwap:
            lines.append(f"\n[VWAP]: ₹{self.vwap:,.2f} ({self._dist(self.vwap):+.1f}%)")

        if self.orb_high and self.orb_low:
            lines.append(f"\n[OPENING RANGE]")
            lines.append(f"  High: ₹{self.orb_high:,.2f}")
            lines.append(f"  Low: ₹{self.orb_low:,.2f}")

        lines.append(f"\n[KEY ZONES]")
        lines.append(f"  Resistance: ₹{self.immediate_resistance:,.2f}")
        lines.append(f"  Support: ₹{self.immediate_support:,.2f}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def _dist(self, level: float) -> float:
        """Calculate distance from current price."""
        return ((level - self.current_price) / self.current_price) * 100


class IntradayLevelsCalculator:
    """
    Calculate intraday trading levels.

    Pivot Systems:
    1. Standard Pivots (most common)
    2. Camarilla Pivots (for range trading)
    3. Fibonacci Pivots (for trend days)
    4. Woodie Pivots (open-weighted)

    Additional Levels:
    - Previous day H/L/C
    - VWAP (Volume Weighted Average Price)
    - Opening Range (first 15/30 min)
    - Round numbers
    - ATH/52-week levels
    """

    def __init__(self):
        self._cache: Dict[str, IntradayLevels] = {}

    def calculate_standard_pivots(
        self,
        high: float,
        low: float,
        close: float
    ) -> Dict[str, float]:
        """
        Calculate standard pivot points.

        PP = (H + L + C) / 3
        R1 = 2*PP - L
        R2 = PP + (H - L)
        R3 = H + 2*(PP - L)
        S1 = 2*PP - H
        S2 = PP - (H - L)
        S3 = L - 2*(H - PP)
        """
        pp = (high + low + close) / 3

        r1 = 2 * pp - low
        r2 = pp + (high - low)
        r3 = high + 2 * (pp - low)

        s1 = 2 * pp - high
        s2 = pp - (high - low)
        s3 = low - 2 * (high - pp)

        return {
            'pivot': round(pp, 2),
            'r1': round(r1, 2),
            'r2': round(r2, 2),
            'r3': round(r3, 2),
            's1': round(s1, 2),
            's2': round(s2, 2),
            's3': round(s3, 2),
        }

    def calculate_camarilla_pivots(
        self,
        high: float,
        low: float,
        close: float
    ) -> Dict[str, float]:
        """
        Calculate Camarilla pivot points.

        Used for range trading - levels are closer together.
        """
        range_hl = high - low

        h4 = close + (range_hl * 1.1 / 2)
        h3 = close + (range_hl * 1.1 / 4)
        h2 = close + (range_hl * 1.1 / 6)
        h1 = close + (range_hl * 1.1 / 12)

        l1 = close - (range_hl * 1.1 / 12)
        l2 = close - (range_hl * 1.1 / 6)
        l3 = close - (range_hl * 1.1 / 4)
        l4 = close - (range_hl * 1.1 / 2)

        return {
            'cam_r4': round(h4, 2),
            'cam_r3': round(h3, 2),
            'cam_r2': round(h2, 2),
            'cam_r1': round(h1, 2),
            'cam_s1': round(l1, 2),
            'cam_s2': round(l2, 2),
            'cam_s3': round(l3, 2),
            'cam_s4': round(l4, 2),
        }

    def calculate_fibonacci_levels(
        self,
        high: float,
        low: float
    ) -> Dict[str, float]:
        """Calculate Fibonacci retracement levels."""
        range_hl = high - low

        return {
            'fib_0': round(low, 2),
            'fib_236': round(low + range_hl * 0.236, 2),
            'fib_382': round(low + range_hl * 0.382, 2),
            'fib_500': round(low + range_hl * 0.500, 2),
            'fib_618': round(low + range_hl * 0.618, 2),
            'fib_786': round(low + range_hl * 0.786, 2),
            'fib_100': round(high, 2),
        }

    def calculate_vwap(self, intraday_data: pd.DataFrame) -> Optional[float]:
        """
        Calculate VWAP from intraday data.

        VWAP = Cumulative(Price * Volume) / Cumulative(Volume)
        """
        if intraday_data.empty:
            return None

        if 'volume' not in intraday_data.columns:
            return None

        try:
            # Typical price
            if all(col in intraday_data.columns for col in ['high', 'low', 'close']):
                tp = (intraday_data['high'] + intraday_data['low'] + intraday_data['close']) / 3
            else:
                tp = intraday_data['close']

            vwap = (tp * intraday_data['volume']).sum() / intraday_data['volume'].sum()
            return round(vwap, 2)

        except Exception:
            return None

    def calculate_opening_range(
        self,
        intraday_data: pd.DataFrame,
        minutes: int = 15
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate opening range (first N minutes).

        ORB strategy: Breakout above/below opening range indicates direction.
        """
        if intraday_data.empty:
            return None, None

        try:
            # Assume data has time component
            if 'datetime' in intraday_data.columns:
                start_time = intraday_data['datetime'].min()
                end_time = start_time + timedelta(minutes=minutes)
                orb_data = intraday_data[intraday_data['datetime'] <= end_time]
            else:
                # Take first few rows as proxy
                orb_data = intraday_data.head(minutes)

            if orb_data.empty:
                return None, None

            orb_high = orb_data['high'].max() if 'high' in orb_data.columns else orb_data['close'].max()
            orb_low = orb_data['low'].min() if 'low' in orb_data.columns else orb_data['close'].min()

            return round(orb_high, 2), round(orb_low, 2)

        except Exception:
            return None, None

    def find_round_numbers(
        self,
        current_price: float,
        range_pct: float = 5
    ) -> List[float]:
        """Find significant round numbers near current price."""
        rounds = []

        # Determine step size based on price magnitude
        if current_price >= 10000:
            step = 500
        elif current_price >= 1000:
            step = 100
        elif current_price >= 100:
            step = 50
        else:
            step = 10

        lower = current_price * (1 - range_pct / 100)
        upper = current_price * (1 + range_pct / 100)

        level = (int(lower / step) - 1) * step
        while level <= upper:
            if lower <= level <= upper:
                rounds.append(float(level))
            level += step

        return rounds

    def calculate_all_levels(
        self,
        symbol: str,
        current_price: float,
        prev_high: float,
        prev_low: float,
        prev_close: float,
        intraday_data: Optional[pd.DataFrame] = None,
        high_52w: Optional[float] = None,
        low_52w: Optional[float] = None
    ) -> IntradayLevels:
        """
        Calculate all intraday levels.

        Combines multiple systems and identifies confluences.
        """
        # Standard pivots
        std_pivots = self.calculate_standard_pivots(prev_high, prev_low, prev_close)

        # Camarilla pivots
        cam_pivots = self.calculate_camarilla_pivots(prev_high, prev_low, prev_close)

        # VWAP and ORB if intraday data available
        vwap = None
        orb_high, orb_low = None, None
        if intraday_data is not None and not intraday_data.empty:
            vwap = self.calculate_vwap(intraday_data)
            orb_high, orb_low = self.calculate_opening_range(intraday_data)

        # Collect all levels
        all_levels = []

        # Add pivot levels
        for name, price in std_pivots.items():
            level_type = (
                LevelType.PIVOT if 'pivot' in name
                else LevelType.RESISTANCE if 'r' in name
                else LevelType.SUPPORT
            )
            all_levels.append(PriceLevel(
                price=price,
                level_type=level_type,
                name=name.upper(),
                strength=LevelStrength.MODERATE
            ))

        # Add PDH/PDL/PDC
        all_levels.append(PriceLevel(
            price=prev_high,
            level_type=LevelType.PDH,
            name="PDH",
            strength=LevelStrength.STRONG
        ))
        all_levels.append(PriceLevel(
            price=prev_low,
            level_type=LevelType.PDL,
            name="PDL",
            strength=LevelStrength.STRONG
        ))
        all_levels.append(PriceLevel(
            price=prev_close,
            level_type=LevelType.PDC,
            name="PDC",
            strength=LevelStrength.MODERATE
        ))

        # Add VWAP
        if vwap:
            all_levels.append(PriceLevel(
                price=vwap,
                level_type=LevelType.VWAP,
                name="VWAP",
                strength=LevelStrength.STRONG
            ))

        # Add ORB levels
        if orb_high:
            all_levels.append(PriceLevel(
                price=orb_high,
                level_type=LevelType.ORB_HIGH,
                name="ORB_HIGH",
                strength=LevelStrength.MODERATE
            ))
        if orb_low:
            all_levels.append(PriceLevel(
                price=orb_low,
                level_type=LevelType.ORB_LOW,
                name="ORB_LOW",
                strength=LevelStrength.MODERATE
            ))

        # Add round numbers
        rounds = self.find_round_numbers(current_price)
        for r in rounds:
            all_levels.append(PriceLevel(
                price=r,
                level_type=LevelType.ROUND,
                name=f"ROUND_{int(r)}",
                strength=LevelStrength.WEAK
            ))

        # Add 52-week levels
        if high_52w:
            all_levels.append(PriceLevel(
                price=high_52w,
                level_type=LevelType.ATH,
                name="52W_HIGH",
                strength=LevelStrength.STRONG
            ))
        if low_52w:
            all_levels.append(PriceLevel(
                price=low_52w,
                level_type=LevelType.ATL,
                name="52W_LOW",
                strength=LevelStrength.STRONG
            ))

        # Calculate distance and identify confluences
        for level in all_levels:
            level.distance_pct = ((level.price - current_price) / current_price) * 100

        # Find confluences (levels within 0.3% of each other)
        all_levels = self._identify_confluences(all_levels)

        # Sort by price
        all_levels.sort(key=lambda x: x.price)

        # Find immediate support and resistance
        resistances = [l for l in all_levels if l.price > current_price]
        supports = [l for l in all_levels if l.price < current_price]

        immediate_resistance = resistances[0].price if resistances else current_price * 1.02
        immediate_support = supports[-1].price if supports else current_price * 0.98

        # Determine bias
        bias = self._determine_bias(current_price, std_pivots, prev_high, prev_low, vwap)

        return IntradayLevels(
            symbol=symbol,
            current_price=current_price,
            calculated_at=datetime.now(),
            pivot=std_pivots['pivot'],
            r1=std_pivots['r1'],
            r2=std_pivots['r2'],
            r3=std_pivots['r3'],
            s1=std_pivots['s1'],
            s2=std_pivots['s2'],
            s3=std_pivots['s3'],
            cam_r1=cam_pivots['cam_r1'],
            cam_r2=cam_pivots['cam_r2'],
            cam_r3=cam_pivots['cam_r3'],
            cam_r4=cam_pivots['cam_r4'],
            cam_s1=cam_pivots['cam_s1'],
            cam_s2=cam_pivots['cam_s2'],
            cam_s3=cam_pivots['cam_s3'],
            cam_s4=cam_pivots['cam_s4'],
            pdh=prev_high,
            pdl=prev_low,
            pdc=prev_close,
            vwap=vwap,
            orb_high=orb_high,
            orb_low=orb_low,
            immediate_resistance=immediate_resistance,
            immediate_support=immediate_support,
            all_levels=all_levels,
            bias=bias
        )

    def _identify_confluences(
        self,
        levels: List[PriceLevel],
        tolerance_pct: float = 0.3
    ) -> List[PriceLevel]:
        """Identify confluence zones where multiple levels cluster."""
        for i, level in enumerate(levels):
            confluences = []
            for j, other in enumerate(levels):
                if i != j:
                    pct_diff = abs(level.price - other.price) / level.price * 100
                    if pct_diff <= tolerance_pct:
                        confluences.append(other.name)

            level.confluences = confluences

            # Upgrade strength if confluences found
            if len(confluences) >= 2:
                level.strength = LevelStrength.STRONG
            elif len(confluences) == 1:
                level.strength = LevelStrength.MODERATE

        return levels

    def _determine_bias(
        self,
        current_price: float,
        pivots: Dict[str, float],
        pdh: float,
        pdl: float,
        vwap: Optional[float]
    ) -> str:
        """Determine intraday bias based on price position."""
        bullish_count = 0
        bearish_count = 0

        # Price vs Pivot
        if current_price > pivots['pivot']:
            bullish_count += 1
        else:
            bearish_count += 1

        # Price vs PDH/PDL
        if current_price > pdh:
            bullish_count += 2  # Strong bullish
        elif current_price < pdl:
            bearish_count += 2  # Strong bearish

        # Price vs VWAP
        if vwap:
            if current_price > vwap:
                bullish_count += 1
            else:
                bearish_count += 1

        # Price vs R1/S1
        if current_price > pivots['r1']:
            bullish_count += 1
        elif current_price < pivots['s1']:
            bearish_count += 1

        if bullish_count > bearish_count + 1:
            return "BULLISH"
        elif bearish_count > bullish_count + 1:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def get_nearest_levels(
        self,
        levels: IntradayLevels,
        n: int = 3
    ) -> Tuple[List[PriceLevel], List[PriceLevel]]:
        """Get N nearest resistance and support levels."""
        current = levels.current_price

        resistances = sorted(
            [l for l in levels.all_levels if l.price > current],
            key=lambda x: x.price
        )[:n]

        supports = sorted(
            [l for l in levels.all_levels if l.price < current],
            key=lambda x: x.price,
            reverse=True
        )[:n]

        return resistances, supports


def calculate_intraday_levels(
    symbol: str,
    current_price: float,
    prev_high: float,
    prev_low: float,
    prev_close: float
) -> IntradayLevels:
    """Quick function to calculate intraday levels."""
    calculator = IntradayLevelsCalculator()
    return calculator.calculate_all_levels(
        symbol=symbol,
        current_price=current_price,
        prev_high=prev_high,
        prev_low=prev_low,
        prev_close=prev_close
    )
