"""
Data Quality Monitor

Tracks data quality across all sources.
Provides system-wide "data health" status.
Implements fail-closed data gates.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from .models import DataQuality

logger = logging.getLogger(__name__)


class GateStatus(Enum):
    """Status of a data gate"""
    PASSED = "passed"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class GateResult:
    """Result of a single gate check"""
    name: str
    status: GateStatus
    reason: str = ""
    action: str = ""
    multiplier: float = 1.0  # Position size multiplier if degraded

    @property
    def passed(self) -> bool:
        return self.status == GateStatus.PASSED


@dataclass
class DataGateResults:
    """Results of all data gate checks"""
    price_gate: GateResult
    fii_dii_gate: GateResult
    fundamentals_gate: GateResult
    earnings_gate: GateResult
    global_context_gate: GateResult

    overall_quality: DataQuality
    combined_multiplier: float
    allow_trading: bool
    warnings: List[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all([
            self.price_gate.passed,
            self.fii_dii_gate.passed,
            self.fundamentals_gate.passed,
            self.earnings_gate.passed,
            self.global_context_gate.passed
        ])


class DataGates:
    """
    Data Gate System

    Every data source has a gate that must PASS before we trust the data.
    If gate FAILS → no bonus from that source, possibly VETO trade.

    Philosophy: "Unknown" is not "Neutral" - it's "Don't Trust"
    """

    def check_price_gate(
        self,
        price_data: Any,
        quality: DataQuality
    ) -> GateResult:
        """
        Check price data quality

        Price data is CRITICAL - if this fails, no trading
        """
        if quality == DataQuality.UNUSABLE:
            return GateResult(
                name="price_data",
                status=GateStatus.FAILED,
                reason="Price data unavailable or corrupted",
                action="NO_TRADE - Cannot generate signals without price data",
                multiplier=0.0
            )

        if quality == DataQuality.DEGRADED:
            return GateResult(
                name="price_data",
                status=GateStatus.DEGRADED,
                reason="Price data is stale or incomplete",
                action="Reduce position sizes by 50%",
                multiplier=0.5
            )

        return GateResult(
            name="price_data",
            status=GateStatus.PASSED,
            multiplier=1.0
        )

    def check_fii_dii_gate(
        self,
        fii_dii_data: Dict[str, Any],
        quality: DataQuality
    ) -> GateResult:
        """
        Check FII/DII data quality

        FII/DII is SUPPLEMENTARY - if fails, just remove bonus
        """
        is_synthetic = fii_dii_data.get('is_synthetic', False)

        if quality == DataQuality.UNUSABLE or is_synthetic:
            return GateResult(
                name="fii_dii",
                status=GateStatus.FAILED,
                reason="FII/DII data unavailable or synthetic",
                action="FII/DII bonus set to 0 (not negative)",
                multiplier=1.0  # Don't reduce size, just remove bonus
            )

        if quality == DataQuality.DEGRADED:
            return GateResult(
                name="fii_dii",
                status=GateStatus.DEGRADED,
                reason="FII/DII data is stale",
                action="FII/DII bonus reduced by 50%",
                multiplier=1.0
            )

        return GateResult(
            name="fii_dii",
            status=GateStatus.PASSED,
            multiplier=1.0
        )

    def check_fundamentals_gate(
        self,
        fundamentals: Dict[str, Any],
        quality: DataQuality
    ) -> GateResult:
        """
        Check fundamentals data quality

        Fundamentals is FILTER - if fails, be more conservative
        """
        if quality == DataQuality.UNUSABLE:
            return GateResult(
                name="fundamentals",
                status=GateStatus.FAILED,
                reason="Fundamentals data unavailable",
                action="Skip fundamental filters, require higher technical conviction",
                multiplier=0.7  # More conservative sizing
            )

        if quality == DataQuality.DEGRADED:
            # Check which specific fields are missing
            missing_critical = []
            if fundamentals.get('promoter_holding') is None:
                missing_critical.append('promoter_holding')
            if fundamentals.get('promoter_pledge') is None:
                missing_critical.append('promoter_pledge')

            if missing_critical:
                return GateResult(
                    name="fundamentals",
                    status=GateStatus.DEGRADED,
                    reason=f"Missing: {', '.join(missing_critical)}",
                    action="Partial fundamental screening only",
                    multiplier=0.9
                )

        return GateResult(
            name="fundamentals",
            status=GateStatus.PASSED,
            multiplier=1.0
        )

    def check_earnings_gate(
        self,
        earnings_data: Dict[str, Any],
        quality: DataQuality
    ) -> GateResult:
        """
        Check earnings calendar data quality

        Earnings is RISK - if unknown, be conservative
        """
        if quality == DataQuality.UNUSABLE:
            return GateResult(
                name="earnings",
                status=GateStatus.FAILED,
                reason="Earnings calendar unavailable",
                action="Assume earnings may be near - reduce position size",
                multiplier=0.7  # Conservative assumption
            )

        has_earnings = earnings_data.get('has_earnings')
        if has_earnings is None:  # Unknown
            return GateResult(
                name="earnings",
                status=GateStatus.DEGRADED,
                reason="Earnings date unknown for this stock",
                action="Using conservative earnings assumption",
                multiplier=0.8
            )

        return GateResult(
            name="earnings",
            status=GateStatus.PASSED,
            multiplier=1.0
        )

    def check_global_context_gate(
        self,
        global_context: Dict[str, Any],
        quality: DataQuality
    ) -> GateResult:
        """
        Check global context data quality

        Global context is ENVIRONMENT - if fails, be cautious
        """
        if quality == DataQuality.UNUSABLE:
            return GateResult(
                name="global_context",
                status=GateStatus.FAILED,
                reason="Global market data unavailable",
                action="Cannot assess global risk - be cautious",
                multiplier=0.8
            )

        vix = global_context.get('vix')
        if vix is None:
            return GateResult(
                name="global_context",
                status=GateStatus.DEGRADED,
                reason="VIX data unavailable",
                action="Cannot assess volatility - be cautious",
                multiplier=0.9
            )

        return GateResult(
            name="global_context",
            status=GateStatus.PASSED,
            multiplier=1.0
        )

    def check_all_gates(
        self,
        price_quality: DataQuality,
        price_data: Any,
        fii_dii_data: Dict[str, Any],
        fii_dii_quality: DataQuality,
        fundamentals: Dict[str, Any],
        fundamentals_quality: DataQuality,
        earnings_data: Dict[str, Any],
        earnings_quality: DataQuality,
        global_context: Dict[str, Any],
        global_quality: DataQuality
    ) -> DataGateResults:
        """
        Check all data gates and compute combined results

        Returns comprehensive gate results with:
        - Individual gate statuses
        - Combined position size multiplier
        - Overall trading permission
        - Warnings list
        """
        # Check each gate
        price_gate = self.check_price_gate(price_data, price_quality)
        fii_dii_gate = self.check_fii_dii_gate(fii_dii_data, fii_dii_quality)
        fundamentals_gate = self.check_fundamentals_gate(fundamentals, fundamentals_quality)
        earnings_gate = self.check_earnings_gate(earnings_data, earnings_quality)
        global_gate = self.check_global_context_gate(global_context, global_quality)

        # Compute combined multiplier
        combined_multiplier = (
            price_gate.multiplier *
            fii_dii_gate.multiplier *
            fundamentals_gate.multiplier *
            earnings_gate.multiplier *
            global_gate.multiplier
        )

        # Determine overall quality
        if price_gate.status == GateStatus.FAILED:
            overall_quality = DataQuality.UNUSABLE
        elif price_gate.status == GateStatus.DEGRADED:
            overall_quality = DataQuality.DEGRADED
        else:
            # Check other gates
            degraded_count = sum([
                fii_dii_gate.status == GateStatus.DEGRADED,
                fundamentals_gate.status == GateStatus.DEGRADED,
                earnings_gate.status == GateStatus.DEGRADED,
                global_gate.status == GateStatus.DEGRADED
            ])

            if degraded_count >= 3:
                overall_quality = DataQuality.DEGRADED
            elif degraded_count >= 1:
                overall_quality = DataQuality.GOOD
            else:
                overall_quality = DataQuality.EXCELLENT

        # Determine if trading allowed
        allow_trading = price_gate.status != GateStatus.FAILED

        # Collect warnings
        warnings = []
        for gate in [price_gate, fii_dii_gate, fundamentals_gate, earnings_gate, global_gate]:
            if gate.status != GateStatus.PASSED and gate.action:
                warnings.append(f"{gate.name}: {gate.action}")

        return DataGateResults(
            price_gate=price_gate,
            fii_dii_gate=fii_dii_gate,
            fundamentals_gate=fundamentals_gate,
            earnings_gate=earnings_gate,
            global_context_gate=global_gate,
            overall_quality=overall_quality,
            combined_multiplier=combined_multiplier,
            allow_trading=allow_trading,
            warnings=warnings
        )


class DataQualityMonitor:
    """
    Monitors data quality across the system

    Provides:
    - Real-time quality tracking
    - Historical quality metrics
    - Alert thresholds
    """

    def __init__(self):
        self.gates = DataGates()
        self._quality_history: List[Dict[str, Any]] = []
        self._last_check: Optional[datetime] = None

    def record_quality(
        self,
        source: str,
        quality: DataQuality,
        details: Dict[str, Any] = None
    ):
        """Record a quality measurement"""
        self._quality_history.append({
            'timestamp': datetime.now(),
            'source': source,
            'quality': quality.value,
            'details': details or {}
        })

        # Keep last 1000 records
        if len(self._quality_history) > 1000:
            self._quality_history = self._quality_history[-1000:]

    def get_recent_quality(
        self,
        source: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get quality records for a source in recent hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            r for r in self._quality_history
            if r['source'] == source and r['timestamp'] > cutoff
        ]

    def get_quality_summary(self) -> Dict[str, Any]:
        """Get summary of data quality across all sources"""
        recent = self._quality_history[-100:] if self._quality_history else []

        if not recent:
            return {
                'overall': 'UNKNOWN',
                'sources': {}
            }

        # Group by source
        by_source = {}
        for record in recent:
            source = record['source']
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(record['quality'])

        # Compute average quality per source
        source_quality = {}
        for source, qualities in by_source.items():
            excellent_pct = qualities.count('excellent') / len(qualities)
            good_pct = qualities.count('good') / len(qualities)
            degraded_pct = qualities.count('degraded') / len(qualities)

            if excellent_pct > 0.8:
                avg_quality = 'EXCELLENT'
            elif excellent_pct + good_pct > 0.8:
                avg_quality = 'GOOD'
            elif degraded_pct < 0.5:
                avg_quality = 'DEGRADED'
            else:
                avg_quality = 'POOR'

            source_quality[source] = avg_quality

        # Overall assessment
        if all(q in ['EXCELLENT', 'GOOD'] for q in source_quality.values()):
            overall = 'GOOD'
        elif 'POOR' in source_quality.values():
            overall = 'POOR'
        else:
            overall = 'DEGRADED'

        return {
            'overall': overall,
            'sources': source_quality,
            'record_count': len(recent)
        }


# Singleton instances
_gates: Optional[DataGates] = None
_monitor: Optional[DataQualityMonitor] = None


def get_data_gates() -> DataGates:
    """Get data gates singleton"""
    global _gates
    if _gates is None:
        _gates = DataGates()
    return _gates


def get_quality_monitor() -> DataQualityMonitor:
    """Get quality monitor singleton"""
    global _monitor
    if _monitor is None:
        _monitor = DataQualityMonitor()
    return _monitor
