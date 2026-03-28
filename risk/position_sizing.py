"""
Legendary Trader Position Sizing and Risk Management.

Implements stop/target strategies inspired by:
- Mark Minervini: Structure-based stops using pivot lows
- William O'Neil: Max 8% loss cap
- Paul Tudor Jones: Regime-aware ATR multipliers
- Ed Seykota: Wide trailing stops for trend capture
"""

from typing import Dict, List, Optional, Tuple
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
    target_3: Optional[float]  # Added T3 for runners
    position_size: int
    position_value: float
    risk_amount: float
    risk_percent: float
    reward_risk_ratio: float
    atr: float
    atr_multiple_sl: float
    stop_type: str  # "ATR", "PIVOT", "EMA", "HYBRID"


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

    def find_pivot_low(self, df: pd.DataFrame, lookback: int = 20) -> float:
        """
        Find the most recent pivot low (Minervini-style structure stop).

        A pivot low is a bar with lower lows on both sides.
        """
        if len(df) < lookback:
            return df['low'].min()

        recent = df.tail(lookback)
        lows = recent['low'].values

        # Find pivot lows (local minima)
        pivot_lows = []
        for i in range(2, len(lows) - 2):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                pivot_lows.append(lows[i])

        if pivot_lows:
            # Return the most recent pivot low
            return pivot_lows[-1]

        # Fallback to lowest low in last 10 bars
        return df['low'].tail(10).min()

    def get_ema_support(self, df: pd.DataFrame, ema_period: int = 20) -> float:
        """
        Get EMA as dynamic support level.

        Used as secondary stop reference - if price closes below EMA,
        the trade thesis is invalidated.
        """
        ema = ta.ema(df['close'], length=ema_period)
        if ema is not None and not pd.isna(ema.iloc[-1]):
            return ema.iloc[-1]
        return 0

    def get_regime_atr_multiplier(self, vix: float = 15.0) -> float:
        """
        Paul Tudor Jones style - adjust ATR multiplier based on volatility regime.

        Higher VIX = wider stops to avoid noise
        Lower VIX = tighter stops for better risk management
        """
        if vix > 25:
            return 3.0  # High volatility - wide stops
        elif vix > 18:
            return 2.5  # Elevated volatility
        elif vix > 12:
            return 2.0  # Normal volatility
        else:
            return 1.5  # Low volatility - tight stops

    def calculate_structure_stop(
        self,
        df: pd.DataFrame,
        entry_price: float,
        vix: float = 15.0,
        is_long: bool = True
    ) -> Tuple[float, str]:
        """
        Calculate stop loss using multiple structure methods (Minervini + O'Neil + PTJ).

        Uses the HIGHEST of:
        1. ATR-based stop (regime-adjusted)
        2. Pivot low stop (structure-based)
        3. EMA support stop

        Capped by O'Neil's max 8% rule.

        Returns:
            Tuple of (stop_price, stop_type)
        """
        atr = self.calculate_atr(df)
        atr_mult = self.get_regime_atr_multiplier(vix)

        # Method 1: ATR-based stop
        if is_long:
            atr_stop = entry_price - (atr * atr_mult)
        else:
            atr_stop = entry_price + (atr * atr_mult)

        # Method 2: Pivot low stop (structure)
        pivot_low = self.find_pivot_low(df)
        # Add small buffer below pivot
        pivot_stop = pivot_low * 0.995 if is_long else pivot_low * 1.005

        # Method 3: EMA support stop
        ema_20 = self.get_ema_support(df, 20)
        # Stop just below EMA
        ema_stop = ema_20 * 0.98 if is_long else ema_20 * 1.02

        # O'Neil's max 8% loss cap
        max_loss_stop = entry_price * 0.92 if is_long else entry_price * 1.08

        if is_long:
            # For longs, use highest stop (least risk)
            stops = {
                'ATR': atr_stop,
                'PIVOT': pivot_stop,
                'EMA': ema_stop
            }

            # Filter out stops that are too far (more than 10% away)
            valid_stops = {k: v for k, v in stops.items() if v > entry_price * 0.90}

            if valid_stops:
                # Use the highest (tightest) valid stop
                stop_type = max(valid_stops, key=valid_stops.get)
                best_stop = valid_stops[stop_type]
            else:
                stop_type = 'ATR'
                best_stop = atr_stop

            # Apply O'Neil cap - never lose more than 8%
            final_stop = max(best_stop, max_loss_stop)
            if final_stop == max_loss_stop and best_stop < max_loss_stop:
                stop_type = 'MAX_LOSS'
        else:
            # For shorts, use lowest stop (least risk)
            stops = {
                'ATR': atr_stop,
                'PIVOT': pivot_stop,
                'EMA': ema_stop
            }

            valid_stops = {k: v for k, v in stops.items() if v < entry_price * 1.10}

            if valid_stops:
                stop_type = min(valid_stops, key=valid_stops.get)
                best_stop = valid_stops[stop_type]
            else:
                stop_type = 'ATR'
                best_stop = atr_stop

            final_stop = min(best_stop, max_loss_stop)
            if final_stop == max_loss_stop and best_stop > max_loss_stop:
                stop_type = 'MAX_LOSS'

        return round(final_stop, 2), stop_type

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
        risk_reward_1: float = 2.0,  # Seykota: wider first target
        risk_reward_2: float = 4.0,  # Seykota: much wider second target
        risk_reward_3: float = 8.0,  # Seykota: let runners run
        is_long: bool = True
    ) -> Dict:
        """
        Calculate profit targets - Ed Seykota style.

        Seykota philosophy: "Cut losses short, let winners run"
        - T1 at 2R: Exit 25% - lock in small profit
        - T2 at 4R: Exit 25% - capture trend continuation
        - T3 at 8R: For the remaining 50% that trails

        This allows capturing 10-20R moves that make trading profitable.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_reward_1: R:R for first target (default 2.0)
            risk_reward_2: R:R for second target (default 4.0)
            risk_reward_3: R:R for third target (default 8.0)
            is_long: True for long trades

        Returns:
            Dict with target prices
        """
        risk = abs(entry_price - stop_loss)

        if is_long:
            target_1 = entry_price + (risk * risk_reward_1)
            target_2 = entry_price + (risk * risk_reward_2)
            target_3 = entry_price + (risk * risk_reward_3)
        else:
            target_1 = entry_price - (risk * risk_reward_1)
            target_2 = entry_price - (risk * risk_reward_2)
            target_3 = entry_price - (risk * risk_reward_3)

        return {
            'target_1': round(target_1, 2),
            'target_2': round(target_2, 2),
            'target_3': round(target_3, 2),
            'risk_reward_1': risk_reward_1,
            'risk_reward_2': risk_reward_2,
            'risk_reward_3': risk_reward_3,
            'risk_amount': round(risk, 2),
            'exit_plan': {
                'at_t1': 25,  # Exit 25% at T1
                'at_t2': 25,  # Exit 25% at T2
                'trail': 50   # Trail 50% with wide stop
            }
        }

    def create_trade_setup(
        self,
        symbol: str,
        df: pd.DataFrame,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        atr_multiplier: float = 2.0,
        regime_multiplier: float = 1.0,
        vix: float = 15.0,
        use_structure_stop: bool = True,
        custom_targets: Optional[Dict] = None
    ) -> TradeSetup:
        """
        Create complete trade setup with position sizing.

        Legendary Trader Edition:
        - Minervini: Structure-based stops (pivot lows)
        - O'Neil: Max 8% loss cap
        - PTJ: Regime-aware ATR multipliers
        - Seykota: Wide targets (2R, 4R, 8R) with 25/25/50 exit plan

        Args:
            symbol: Stock symbol
            df: OHLCV DataFrame
            entry_price: Entry price (defaults to current close)
            stop_loss: Stop loss (defaults to structure-based)
            atr_multiplier: ATR multiplier for stop (fallback)
            regime_multiplier: Position size adjustment for regime
            vix: Current VIX level for regime-aware stops
            use_structure_stop: Use multi-method structure stop (recommended)
            custom_targets: Custom target prices

        Returns:
            TradeSetup object
        """
        # Default entry to current price
        if entry_price is None:
            entry_price = df['close'].iloc[-1]

        # Calculate ATR
        atr = self.calculate_atr(df)

        # Calculate stop loss
        stop_type = "ATR"
        if stop_loss is None:
            if use_structure_stop:
                # Use legendary trader multi-method stop
                stop_loss, stop_type = self.calculate_structure_stop(
                    df, entry_price, vix, is_long=True
                )
            else:
                # Fallback to simple ATR stop
                stop_loss = self.calculate_atr_stop(df, entry_price, atr_multiplier)

        # Calculate position size
        sizing = self.calculate_position_size(entry_price, stop_loss, regime_multiplier)

        # Calculate targets (Seykota style: 2R, 4R, 8R)
        if custom_targets:
            target_1 = custom_targets.get('target_1', entry_price * 1.05)
            target_2 = custom_targets.get('target_2', entry_price * 1.10)
            target_3 = custom_targets.get('target_3', entry_price * 1.20)
        else:
            targets = self.calculate_targets(entry_price, stop_loss)
            target_1 = targets['target_1']
            target_2 = targets['target_2']
            target_3 = targets['target_3']

        # Calculate R:R (using T1 for standard comparison)
        risk = abs(entry_price - stop_loss)
        reward = abs(target_1 - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0

        return TradeSetup(
            symbol=symbol,
            entry_price=round(entry_price, 2),
            stop_loss=round(stop_loss, 2),
            target_1=round(target_1, 2),
            target_2=round(target_2, 2),
            target_3=round(target_3, 2),
            position_size=sizing['shares'],
            position_value=sizing['position_value'],
            risk_amount=sizing['risk_amount'],
            risk_percent=sizing['risk_percent'],
            reward_risk_ratio=round(rr_ratio, 2),
            atr=round(atr, 2),
            atr_multiple_sl=atr_multiplier,
            stop_type=stop_type
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
