"""ATR-based Position Sizing and Risk Management."""

from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np
import pandas_ta as ta


@dataclass
class TradeSetup:
    """Complete trade setup with position sizing."""
    symbol: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    position_size: int
    position_value: float
    risk_amount: float
    risk_percent: float
    reward_risk_ratio: float
    atr: float
    atr_multiple_sl: float


class PositionSizer:
    """Calculate position sizes based on ATR and risk parameters."""

    def __init__(
        self,
        capital: float = 500000,  # Default 5 lakh
        risk_per_trade: float = 0.01,  # 1% risk per trade
        max_position_pct: float = 0.20,  # Max 20% of capital in one trade
        atr_period: int = 14
    ):
        """
        Initialize position sizer.

        Args:
            capital: Total trading capital
            risk_per_trade: Fraction of capital to risk per trade (0.01 = 1%)
            max_position_pct: Maximum position size as fraction of capital
            atr_period: ATR calculation period
        """
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.max_position_pct = max_position_pct
        self.atr_period = atr_period

    def calculate_atr(self, df: pd.DataFrame) -> float:
        """Calculate Average True Range."""
        atr = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
        return atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0

    def calculate_atr_stop(
        self,
        df: pd.DataFrame,
        entry_price: float,
        atr_multiplier: float = 2.0,
        is_long: bool = True
    ) -> float:
        """
        Calculate stop loss based on ATR.

        Args:
            df: OHLCV DataFrame
            entry_price: Entry price
            atr_multiplier: ATR multiplier for stop distance
            is_long: True for long trades, False for short

        Returns:
            Stop loss price
        """
        atr = self.calculate_atr(df)

        if is_long:
            stop_loss = entry_price - (atr * atr_multiplier)
        else:
            stop_loss = entry_price + (atr * atr_multiplier)

        return round(stop_loss, 2)

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        regime_multiplier: float = 1.0
    ) -> Dict:
        """
        Calculate position size based on risk.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            regime_multiplier: Adjust size based on market regime (0-1)

        Returns:
            Dict with position sizing details
        """
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share == 0:
            return {
                'shares': 0,
                'position_value': 0,
                'risk_amount': 0,
                'error': 'Stop loss equals entry price'
            }

        # Risk amount adjusted for regime
        adjusted_risk_pct = self.risk_per_trade * regime_multiplier
        risk_amount = self.capital * adjusted_risk_pct

        # Calculate shares based on risk
        shares_by_risk = int(risk_amount / risk_per_share)

        # Calculate max shares based on position limit
        max_position_value = self.capital * self.max_position_pct
        shares_by_position = int(max_position_value / entry_price)

        # Take the smaller of the two
        shares = min(shares_by_risk, shares_by_position)

        # Round to lot size (for F&O stocks, typically 1 for cash)
        # For simplicity, using 1 as lot size
        shares = max(1, shares)

        position_value = shares * entry_price
        actual_risk = shares * risk_per_share
        actual_risk_pct = actual_risk / self.capital

        return {
            'shares': shares,
            'position_value': round(position_value, 2),
            'risk_amount': round(actual_risk, 2),
            'risk_percent': round(actual_risk_pct * 100, 2),
            'risk_per_share': round(risk_per_share, 2),
            'regime_multiplier': regime_multiplier
        }

    def calculate_targets(
        self,
        entry_price: float,
        stop_loss: float,
        risk_reward_1: float = 1.5,
        risk_reward_2: float = 2.5,
        is_long: bool = True
    ) -> Dict:
        """
        Calculate profit targets based on risk-reward.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_reward_1: R:R for first target
            risk_reward_2: R:R for second target
            is_long: True for long trades

        Returns:
            Dict with target prices
        """
        risk = abs(entry_price - stop_loss)

        if is_long:
            target_1 = entry_price + (risk * risk_reward_1)
            target_2 = entry_price + (risk * risk_reward_2)
        else:
            target_1 = entry_price - (risk * risk_reward_1)
            target_2 = entry_price - (risk * risk_reward_2)

        return {
            'target_1': round(target_1, 2),
            'target_2': round(target_2, 2),
            'risk_reward_1': risk_reward_1,
            'risk_reward_2': risk_reward_2,
            'risk_amount': round(risk, 2)
        }

    def create_trade_setup(
        self,
        symbol: str,
        df: pd.DataFrame,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        atr_multiplier: float = 2.0,
        regime_multiplier: float = 1.0,
        custom_targets: Optional[Dict] = None
    ) -> TradeSetup:
        """
        Create complete trade setup with position sizing.

        Args:
            symbol: Stock symbol
            df: OHLCV DataFrame
            entry_price: Entry price (defaults to current close)
            stop_loss: Stop loss (defaults to ATR-based)
            atr_multiplier: ATR multiplier for stop
            regime_multiplier: Position size adjustment for regime
            custom_targets: Custom target prices

        Returns:
            TradeSetup object
        """
        # Default entry to current price
        if entry_price is None:
            entry_price = df['close'].iloc[-1]

        # Calculate ATR
        atr = self.calculate_atr(df)

        # Default stop to ATR-based
        if stop_loss is None:
            stop_loss = self.calculate_atr_stop(df, entry_price, atr_multiplier)

        # Calculate position size
        sizing = self.calculate_position_size(entry_price, stop_loss, regime_multiplier)

        # Calculate targets
        if custom_targets:
            target_1 = custom_targets.get('target_1', entry_price * 1.05)
            target_2 = custom_targets.get('target_2', entry_price * 1.10)
        else:
            targets = self.calculate_targets(entry_price, stop_loss)
            target_1 = targets['target_1']
            target_2 = targets['target_2']

        # Calculate R:R
        risk = abs(entry_price - stop_loss)
        reward = abs(target_1 - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0

        return TradeSetup(
            symbol=symbol,
            entry_price=round(entry_price, 2),
            stop_loss=round(stop_loss, 2),
            target_1=round(target_1, 2),
            target_2=round(target_2, 2),
            position_size=sizing['shares'],
            position_value=sizing['position_value'],
            risk_amount=sizing['risk_amount'],
            risk_percent=sizing['risk_percent'],
            reward_risk_ratio=round(rr_ratio, 2),
            atr=round(atr, 2),
            atr_multiple_sl=atr_multiplier
        )


class PortfolioRiskManager:
    """Manage risk across multiple positions."""

    def __init__(
        self,
        capital: float = 500000,
        max_portfolio_risk: float = 0.06,  # Max 6% total risk
        max_sector_exposure: float = 0.30,  # Max 30% in one sector
        max_correlated_positions: int = 2
    ):
        """
        Initialize portfolio risk manager.

        Args:
            capital: Total trading capital
            max_portfolio_risk: Maximum total portfolio risk
            max_sector_exposure: Maximum exposure to one sector
            max_correlated_positions: Max positions in correlated assets
        """
        self.capital = capital
        self.max_portfolio_risk = max_portfolio_risk
        self.max_sector_exposure = max_sector_exposure
        self.max_correlated_positions = max_correlated_positions
        self.open_positions: List[Dict] = []

    def add_position(self, position: Dict):
        """Add a position to tracking."""
        self.open_positions.append(position)

    def clear_positions(self):
        """Clear all positions."""
        self.open_positions = []

    def get_current_risk(self) -> float:
        """Calculate current total portfolio risk."""
        total_risk = sum(p.get('risk_amount', 0) for p in self.open_positions)
        return total_risk / self.capital

    def get_sector_exposure(self, sector: str) -> float:
        """Calculate exposure to a specific sector."""
        sector_value = sum(
            p.get('position_value', 0)
            for p in self.open_positions
            if p.get('sector') == sector
        )
        return sector_value / self.capital

    def can_take_trade(self, new_trade: Dict) -> Dict:
        """
        Check if a new trade can be taken within risk limits.

        Args:
            new_trade: Dict with trade details (risk_amount, sector, etc.)

        Returns:
            Dict with approval status and reasons
        """
        issues = []
        warnings = []

        # Check portfolio risk
        current_risk = self.get_current_risk()
        new_risk = new_trade.get('risk_amount', 0) / self.capital
        total_risk = current_risk + new_risk

        if total_risk > self.max_portfolio_risk:
            issues.append(
                f"Portfolio risk would exceed limit: {total_risk*100:.1f}% > {self.max_portfolio_risk*100:.1f}%"
            )

        # Check sector exposure
        sector = new_trade.get('sector', 'Unknown')
        current_sector_exp = self.get_sector_exposure(sector)
        new_sector_exp = new_trade.get('position_value', 0) / self.capital
        total_sector_exp = current_sector_exp + new_sector_exp

        if total_sector_exp > self.max_sector_exposure:
            issues.append(
                f"Sector exposure would exceed limit: {total_sector_exp*100:.1f}% > {self.max_sector_exposure*100:.1f}%"
            )

        # Check correlated positions
        sector_positions = [p for p in self.open_positions if p.get('sector') == sector]
        if len(sector_positions) >= self.max_correlated_positions:
            warnings.append(
                f"Already have {len(sector_positions)} positions in {sector} sector"
            )

        approved = len(issues) == 0

        return {
            'approved': approved,
            'issues': issues,
            'warnings': warnings,
            'current_portfolio_risk': round(current_risk * 100, 2),
            'projected_portfolio_risk': round(total_risk * 100, 2),
            'current_sector_exposure': round(current_sector_exp * 100, 2),
            'projected_sector_exposure': round(total_sector_exp * 100, 2)
        }

    def get_available_risk(self) -> float:
        """Get remaining risk capacity."""
        current_risk = self.get_current_risk()
        available = self.max_portfolio_risk - current_risk
        return max(0, available) * self.capital

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio risk summary."""
        total_value = sum(p.get('position_value', 0) for p in self.open_positions)
        total_risk = sum(p.get('risk_amount', 0) for p in self.open_positions)

        # Sector breakdown
        sectors = {}
        for p in self.open_positions:
            sector = p.get('sector', 'Unknown')
            if sector not in sectors:
                sectors[sector] = {'value': 0, 'risk': 0, 'count': 0}
            sectors[sector]['value'] += p.get('position_value', 0)
            sectors[sector]['risk'] += p.get('risk_amount', 0)
            sectors[sector]['count'] += 1

        return {
            'total_positions': len(self.open_positions),
            'total_value': round(total_value, 2),
            'total_risk': round(total_risk, 2),
            'risk_percent': round(total_risk / self.capital * 100, 2),
            'available_risk': round(self.get_available_risk(), 2),
            'sectors': sectors,
            'utilization': round(total_value / self.capital * 100, 2)
        }
