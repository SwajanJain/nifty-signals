"""
Position Manager - Real-time portfolio tracking and risk management.

Integrates with:
- Trade Journal for historical tracking
- Data Quality Monitor for data health awareness
- Risk limits from CLAUDE.md specifications

Key Features:
- Portfolio heat calculation (max 6%)
- Sector exposure tracking (max 30% per sector)
- Correlation-aware position limits (max 3 per sector)
- Real-time P&L tracking
- Position size recommendations based on data quality
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import json
import logging

from .trade_journal import TradeJournal, TradeEntry, TradeResult

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """Position status."""
    OPEN = "OPEN"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    CLOSED = "CLOSED"


@dataclass
class Position:
    """A currently open position."""
    symbol: str
    entry_date: datetime
    entry_price: float
    quantity: int
    stop_loss: float
    target1: float
    target2: Optional[float] = None

    # Current state
    current_price: float = 0.0
    last_updated: Optional[datetime] = None

    # Classification
    sector: str = ""
    conviction_level: str = "B"
    conviction_score: int = 50
    trade_type: str = "SWING"

    # Risk metrics
    risk_per_share: float = 0.0
    total_risk: float = 0.0
    risk_pct_of_capital: float = 0.0

    # Linked trade ID
    trade_id: str = ""

    def __post_init__(self):
        """Calculate derived fields."""
        if self.current_price == 0:
            self.current_price = self.entry_price
        if not self.last_updated:
            self.last_updated = self.entry_date
        self._calculate_risk()

    def _calculate_risk(self):
        """Calculate risk metrics."""
        self.risk_per_share = abs(self.entry_price - self.stop_loss)
        self.total_risk = self.risk_per_share * self.quantity

    @property
    def position_value(self) -> float:
        """Current position value."""
        return self.current_price * self.quantity

    @property
    def entry_value(self) -> float:
        """Original entry value."""
        return self.entry_price * self.quantity

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L."""
        return (self.current_price - self.entry_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L percentage."""
        if self.entry_price == 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100

    @property
    def distance_to_stop_pct(self) -> float:
        """Distance to stop loss as percentage."""
        if self.current_price == 0:
            return 0.0
        return ((self.current_price - self.stop_loss) / self.current_price) * 100

    @property
    def distance_to_target1_pct(self) -> float:
        """Distance to target 1 as percentage."""
        if self.current_price == 0:
            return 0.0
        return ((self.target1 - self.current_price) / self.current_price) * 100

    @property
    def is_profitable(self) -> bool:
        """Is position currently profitable."""
        return self.unrealized_pnl > 0

    @property
    def should_trail_stop(self) -> bool:
        """Should consider trailing stop."""
        return self.unrealized_pnl_pct > 5.0

    def update_price(self, price: float):
        """Update current price."""
        self.current_price = price
        self.last_updated = datetime.now()

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            'symbol': self.symbol,
            'entry_date': self.entry_date.isoformat(),
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'stop_loss': self.stop_loss,
            'target1': self.target1,
            'target2': self.target2,
            'current_price': self.current_price,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'sector': self.sector,
            'conviction_level': self.conviction_level,
            'conviction_score': self.conviction_score,
            'trade_type': self.trade_type,
            'trade_id': self.trade_id
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Position':
        """Create from dictionary."""
        data['entry_date'] = datetime.fromisoformat(data['entry_date'])
        if data.get('last_updated'):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        return cls(**data)


@dataclass
class PortfolioRiskLimits:
    """Risk limits for the portfolio."""
    max_portfolio_heat: float = 6.0  # Max 6% total risk
    max_position_pct: float = 15.0   # Max 15% per position
    max_sector_pct: float = 30.0     # Max 30% per sector
    max_positions_per_sector: int = 3
    min_liquidity_cr: float = 10.0   # Min 10 Cr ADV
    max_adv_pct: float = 2.0         # Max 2% of ADV
    drawdown_scale_threshold: float = 5.0  # Scale down after 5% DD


@dataclass
class PortfolioStatus:
    """Current portfolio status and health."""
    total_capital: float
    invested_capital: float
    cash_available: float

    # Positions
    total_positions: int
    positions_by_sector: Dict[str, int]

    # Risk metrics
    current_heat: float  # Total risk as % of capital
    heat_available: float  # Remaining risk budget

    # P&L
    unrealized_pnl: float
    unrealized_pnl_pct: float

    # Health
    within_limits: bool
    warnings: List[str] = field(default_factory=list)

    # Data quality multiplier from quality gates
    data_quality_multiplier: float = 1.0


class PositionManager:
    """
    Manages open positions and portfolio risk.

    Features:
    - Real-time position tracking
    - Portfolio heat calculation
    - Sector exposure management
    - Position size recommendations
    - Integration with data quality system
    """

    def __init__(
        self,
        capital: float = 1_000_000,  # Default 10 Lakh
        positions_file: str = "journal/positions.json",
        limits: Optional[PortfolioRiskLimits] = None
    ):
        self.capital = capital
        self.positions_file = Path(positions_file)
        self.positions_file.parent.mkdir(parents=True, exist_ok=True)
        self.limits = limits or PortfolioRiskLimits()

        self.positions: Dict[str, Position] = {}
        self._load_positions()

        # Link to trade journal
        self.journal = TradeJournal()

    def _load_positions(self):
        """Load positions from file."""
        if self.positions_file.exists():
            try:
                with open(self.positions_file, 'r') as f:
                    data = json.load(f)
                    self.positions = {
                        symbol: Position.from_dict(pos_data)
                        for symbol, pos_data in data.items()
                    }
                logger.info(f"Loaded {len(self.positions)} positions")
            except Exception as e:
                logger.warning(f"Could not load positions: {e}")
                self.positions = {}
        else:
            self.positions = {}

    def _save_positions(self):
        """Save positions to file."""
        try:
            with open(self.positions_file, 'w') as f:
                json.dump(
                    {symbol: pos.to_dict() for symbol, pos in self.positions.items()},
                    f,
                    indent=2
                )
        except Exception as e:
            logger.error(f"Error saving positions: {e}")

    def add_position(self, position: Position) -> bool:
        """
        Add a new position after checking limits.

        Returns True if position was added, False if rejected.
        """
        # Check if already have position in this symbol
        if position.symbol in self.positions:
            logger.warning(f"Already have position in {position.symbol}")
            return False

        # Check portfolio heat
        current_heat = self._calculate_heat()
        position_heat = (position.total_risk / self.capital) * 100

        if current_heat + position_heat > self.limits.max_portfolio_heat:
            logger.warning(
                f"Position would exceed portfolio heat limit: "
                f"Current {current_heat:.1f}% + New {position_heat:.1f}% > {self.limits.max_portfolio_heat}%"
            )
            return False

        # Check sector limits
        sector_count = self._count_positions_in_sector(position.sector)
        if sector_count >= self.limits.max_positions_per_sector:
            logger.warning(
                f"Already have {sector_count} positions in {position.sector} sector"
            )
            return False

        # Check position size limit
        position_pct = (position.entry_value / self.capital) * 100
        if position_pct > self.limits.max_position_pct:
            logger.warning(
                f"Position size {position_pct:.1f}% exceeds limit {self.limits.max_position_pct}%"
            )
            return False

        # Check sector exposure
        sector_exposure = self._calculate_sector_exposure(position.sector)
        new_sector_exposure = sector_exposure + position_pct
        if new_sector_exposure > self.limits.max_sector_pct:
            logger.warning(
                f"Sector exposure would be {new_sector_exposure:.1f}% (limit {self.limits.max_sector_pct}%)"
            )
            return False

        # All checks passed - add position
        position._calculate_risk()
        position.risk_pct_of_capital = position_heat
        self.positions[position.symbol] = position
        self._save_positions()

        logger.info(f"Added position: {position.symbol} | Risk: {position_heat:.2f}%")
        return True

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str = ""
    ) -> Optional[Tuple[Position, float]]:
        """
        Close a position and calculate realized P&L.

        Returns (Position, realized_pnl) or None if position not found.
        """
        if symbol not in self.positions:
            logger.warning(f"Position not found: {symbol}")
            return None

        position = self.positions[symbol]
        position.update_price(exit_price)
        realized_pnl = position.unrealized_pnl

        # Remove from active positions
        del self.positions[symbol]
        self._save_positions()

        logger.info(
            f"Closed position: {symbol} | P&L: {realized_pnl:,.2f} ({position.unrealized_pnl_pct:+.1f}%)"
        )

        return position, realized_pnl

    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions."""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].update_price(price)
        self._save_positions()

    def _calculate_heat(self) -> float:
        """Calculate current portfolio heat (total risk %)."""
        total_risk = sum(pos.total_risk for pos in self.positions.values())
        return (total_risk / self.capital) * 100 if self.capital > 0 else 0

    def _count_positions_in_sector(self, sector: str) -> int:
        """Count positions in a sector."""
        return sum(1 for pos in self.positions.values() if pos.sector == sector)

    def _calculate_sector_exposure(self, sector: str) -> float:
        """Calculate total exposure to a sector as % of capital."""
        sector_value = sum(
            pos.position_value for pos in self.positions.values()
            if pos.sector == sector
        )
        return (sector_value / self.capital) * 100 if self.capital > 0 else 0

    def get_portfolio_status(
        self,
        data_quality_multiplier: float = 1.0
    ) -> PortfolioStatus:
        """Get current portfolio status."""
        invested = sum(pos.position_value for pos in self.positions.values())
        unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())

        # Sector breakdown
        sectors = {}
        for pos in self.positions.values():
            sector = pos.sector or "Unknown"
            sectors[sector] = sectors.get(sector, 0) + 1

        # Risk metrics
        current_heat = self._calculate_heat()
        heat_available = max(0, self.limits.max_portfolio_heat - current_heat)

        # Apply data quality multiplier to available heat
        effective_heat_available = heat_available * data_quality_multiplier

        # Check limits
        warnings = []
        within_limits = True

        if current_heat > self.limits.max_portfolio_heat * 0.8:
            warnings.append(f"Portfolio heat at {current_heat:.1f}% - approaching limit")

        if current_heat > self.limits.max_portfolio_heat:
            warnings.append(f"Portfolio heat EXCEEDED: {current_heat:.1f}%")
            within_limits = False

        for sector, count in sectors.items():
            if count >= self.limits.max_positions_per_sector:
                warnings.append(f"{sector} sector has {count} positions - at limit")
            exposure = self._calculate_sector_exposure(sector)
            if exposure > self.limits.max_sector_pct * 0.8:
                warnings.append(f"{sector} sector exposure at {exposure:.1f}%")

        if data_quality_multiplier < 1.0:
            warnings.append(f"Data quality degraded - sizing reduced to {data_quality_multiplier*100:.0f}%")

        return PortfolioStatus(
            total_capital=self.capital,
            invested_capital=invested,
            cash_available=self.capital - invested,
            total_positions=len(self.positions),
            positions_by_sector=sectors,
            current_heat=current_heat,
            heat_available=effective_heat_available,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=(unrealized_pnl / self.capital) * 100 if self.capital > 0 else 0,
            within_limits=within_limits,
            warnings=warnings,
            data_quality_multiplier=data_quality_multiplier
        )

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        conviction_level: str = "B",
        data_quality_multiplier: float = 1.0,
        risk_by_conviction: Optional[Dict[str, float]] = None,
        risk_per_share_override: Optional[float] = None,
        risk_multiplier: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calculate recommended position size based on conviction and available risk.

        Returns:
            Dictionary with shares, value, risk metrics
        """
        # Base risk allocation by conviction (percent of capital)
        conviction_risk_pct = {
            "A+": 2.5,
            "A": 2.0,
            "B": 1.0,
            "C": 0.5,
            "D": 0.0
        }

        risk_map = risk_by_conviction or conviction_risk_pct
        base_risk_pct = float(risk_map.get(conviction_level, risk_map.get("B", 1.0)))

        # Apply data quality multiplier
        adjusted_risk_pct = base_risk_pct * data_quality_multiplier * float(risk_multiplier)

        # Check available heat
        current_heat = self._calculate_heat()
        available_heat = max(0, self.limits.max_portfolio_heat - current_heat)

        # Cap at available heat
        final_risk_pct = min(adjusted_risk_pct, available_heat)

        if final_risk_pct <= 0:
            return {
                'shares': 0,
                'value': 0,
                'risk_amount': 0,
                'risk_pct': 0,
                'reason': 'No risk budget available',
                'can_trade': False
            }

        # Calculate position
        risk_per_share = float(risk_per_share_override) if risk_per_share_override else abs(entry_price - stop_loss)
        if risk_per_share == 0:
            return {
                'shares': 0,
                'value': 0,
                'risk_amount': 0,
                'risk_pct': 0,
                'reason': 'Invalid stop loss (same as entry)',
                'can_trade': False
            }

        risk_amount = self.capital * (final_risk_pct / 100)
        shares = int(risk_amount / risk_per_share)

        # Check position size limit
        position_value = shares * entry_price
        max_position_value = self.capital * (self.limits.max_position_pct / 100)

        if position_value > max_position_value:
            shares = int(max_position_value / entry_price)
            position_value = shares * entry_price

        actual_risk = shares * risk_per_share
        actual_risk_pct = (actual_risk / self.capital) * 100

        return {
            'shares': shares,
            'value': position_value,
            'risk_amount': actual_risk,
            'risk_pct': actual_risk_pct,
            'reason': f'Based on {conviction_level} conviction, {data_quality_multiplier*100:.0f}% data quality',
            'can_trade': shares > 0,
            'adjustments': {
                'base_risk_pct': base_risk_pct,
                'after_data_quality': adjusted_risk_pct,
                'after_heat_cap': final_risk_pct
            },
            'risk_per_share': risk_per_share,
            'risk_multiplier': float(risk_multiplier),
        }

    def get_positions_needing_attention(self) -> Dict[str, List[Position]]:
        """Get positions that need attention."""
        result = {
            'near_stop': [],
            'at_target': [],
            'need_trailing_stop': [],
            'stale_data': []
        }

        for pos in self.positions.values():
            # Near stop loss (within 2%)
            if pos.distance_to_stop_pct < 2:
                result['near_stop'].append(pos)

            # At or past target
            if pos.current_price >= pos.target1:
                result['at_target'].append(pos)

            # Should consider trailing stop
            if pos.should_trail_stop:
                result['need_trailing_stop'].append(pos)

            # Stale price data (not updated in 30 min during market hours)
            if pos.last_updated:
                minutes_stale = (datetime.now() - pos.last_updated).seconds / 60
                if minutes_stale > 30:
                    result['stale_data'].append(pos)

        return result

    def get_summary(self) -> str:
        """Get human-readable portfolio summary."""
        status = self.get_portfolio_status()

        lines = []
        lines.append("=" * 60)
        lines.append("PORTFOLIO SUMMARY")
        lines.append("=" * 60)

        lines.append(f"\n[CAPITAL]")
        lines.append(f"  Total: {status.total_capital:,.0f}")
        lines.append(f"  Invested: {status.invested_capital:,.0f}")
        lines.append(f"  Cash: {status.cash_available:,.0f}")

        lines.append(f"\n[POSITIONS: {status.total_positions}]")
        for symbol, pos in self.positions.items():
            pnl_str = f"+{pos.unrealized_pnl_pct:.1f}%" if pos.is_profitable else f"{pos.unrealized_pnl_pct:.1f}%"
            lines.append(f"  {symbol}: {pos.quantity} @ {pos.entry_price:.2f} | {pnl_str}")

        lines.append(f"\n[RISK]")
        lines.append(f"  Portfolio Heat: {status.current_heat:.1f}% / {self.limits.max_portfolio_heat}%")
        lines.append(f"  Available Heat: {status.heat_available:.1f}%")

        lines.append(f"\n[P&L]")
        lines.append(f"  Unrealized: {status.unrealized_pnl:,.0f} ({status.unrealized_pnl_pct:+.2f}%)")

        if status.warnings:
            lines.append(f"\n[WARNINGS]")
            for warning in status.warnings:
                lines.append(f"  ! {warning}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def can_take_new_position(
        self,
        sector: str,
        data_quality_multiplier: float = 1.0
    ) -> Tuple[bool, str]:
        """
        Check if we can take a new position.

        Returns (can_trade, reason).
        """
        # Check data quality
        if data_quality_multiplier == 0:
            return False, "Data quality too poor for trading"

        # Check portfolio heat
        current_heat = self._calculate_heat()
        available_heat = self.limits.max_portfolio_heat - current_heat
        min_risk = 0.5  # Minimum 0.5% risk per trade

        if available_heat < min_risk:
            return False, f"Insufficient risk budget: {available_heat:.1f}% available"

        # Check sector limits
        sector_count = self._count_positions_in_sector(sector)
        if sector_count >= self.limits.max_positions_per_sector:
            return False, f"Sector limit reached: {sector_count} positions in {sector}"

        # Check sector exposure
        sector_exposure = self._calculate_sector_exposure(sector)
        if sector_exposure > self.limits.max_sector_pct * 0.9:
            return False, f"Sector exposure high: {sector_exposure:.1f}% in {sector}"

        return True, "OK"


# Singleton instance
_position_manager: Optional[PositionManager] = None


def get_position_manager(capital: float = 1_000_000) -> PositionManager:
    """Get position manager singleton."""
    global _position_manager
    if _position_manager is None:
        _position_manager = PositionManager(capital=capital)
    return _position_manager
