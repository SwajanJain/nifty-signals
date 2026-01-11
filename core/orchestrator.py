"""
Master Orchestrator - The Brain of the Trading System.

Inspired by:
- Jim Simons: Ensemble of models, probability-weighted decisions
- Ray Dalio: Systematic principles, risk parity
- Stanley Druckenmiller: Conviction-based sizing, regime awareness
- Paul Tudor Jones: Defense first, global macro

This orchestrator coordinates all components and makes final decisions.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
from rich.console import Console

console = Console()


class DecisionType(Enum):
    """Final decision types."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    WEAK_BUY = "WEAK_BUY"
    NO_TRADE = "NO_TRADE"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class VetoReason(Enum):
    """Reasons for vetoing a trade."""
    REGIME_BEARISH = "Market regime too bearish"
    LOW_LIQUIDITY = "Insufficient liquidity"
    HIGH_CORRELATION = "Too correlated with existing positions"
    PORTFOLIO_FULL = "Portfolio heat limit reached"
    DRAWDOWN_LIMIT = "In drawdown - reducing exposure"
    EVENT_RISK = "Earnings/event too close"
    GLOBAL_RISK_OFF = "Global risk-off environment"
    WEAK_CONVICTION = "Signal conviction too low"
    MTF_CONFLICT = "Multi-timeframe conflict"
    SECTOR_WEAK = "Sector is underperforming"


@dataclass
class TradeDecision:
    """Final trade decision with full context and audit trail."""
    # Core decision
    symbol: str
    decision: DecisionType
    conviction_level: str  # A, B, C, D
    conviction_score: float  # 0-100

    # Trade setup
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    target_3: Optional[float]

    # Position sizing
    position_size: int
    position_value: float
    risk_amount: float
    risk_percent: float
    portfolio_heat_after: float

    # Context
    market_regime: str
    regime_score: int
    global_context: Dict
    sector_rank: int
    sector_strength: str
    mtf_alignment: int

    # Signal details
    technical_score: int
    signal_sources: List[str]  # Which models contributed
    confluence_count: int  # Number of aligned signals

    # Risk checks
    passed_all_checks: bool
    veto_reasons: List[str]
    warnings: List[str]

    # Audit trail
    decision_time: datetime = field(default_factory=datetime.now)
    reasoning: List[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"DECISION: {self.decision.value} | Conviction: {self.conviction_level} ({self.conviction_score:.0f}/100)")
        lines.append(f"{'='*60}")

        if self.decision in [DecisionType.STRONG_BUY, DecisionType.BUY, DecisionType.WEAK_BUY]:
            lines.append(f"\nTrade Setup:")
            lines.append(f"  Entry: ₹{self.entry_price:,.2f}")
            lines.append(f"  Stop:  ₹{self.stop_loss:,.2f} ({(self.stop_loss/self.entry_price-1)*100:+.1f}%)")
            lines.append(f"  T1:    ₹{self.target_1:,.2f} ({(self.target_1/self.entry_price-1)*100:+.1f}%)")
            lines.append(f"  T2:    ₹{self.target_2:,.2f} ({(self.target_2/self.entry_price-1)*100:+.1f}%)")
            lines.append(f"\nPosition Sizing:")
            lines.append(f"  Shares: {self.position_size}")
            lines.append(f"  Value:  ₹{self.position_value:,.0f}")
            lines.append(f"  Risk:   ₹{self.risk_amount:,.0f} ({self.risk_percent:.2f}%)")
            lines.append(f"  Portfolio Heat After: {self.portfolio_heat_after:.1f}%")

        lines.append(f"\nContext:")
        lines.append(f"  Regime: {self.market_regime} (Score: {self.regime_score})")
        lines.append(f"  Sector: Rank #{self.sector_rank} ({self.sector_strength})")
        lines.append(f"  MTF: {self.mtf_alignment:+d}")
        lines.append(f"  Confluence: {self.confluence_count} signals aligned")

        if self.veto_reasons:
            lines.append(f"\n⛔ VETOED: {', '.join(self.veto_reasons)}")

        if self.warnings:
            lines.append(f"\n⚠️ Warnings: {', '.join(self.warnings)}")

        lines.append(f"\nReasoning:")
        for r in self.reasoning:
            lines.append(f"  • {r}")

        return "\n".join(lines)


class MasterOrchestrator:
    """
    The brain of the trading system.

    Coordinates all components:
    1. Context Layer: Global, Regime, Sector
    2. Signal Layer: Multiple models with ensemble voting
    3. Conviction Layer: Signal quality scoring
    4. Risk Layer: Portfolio-level checks and vetos
    5. Execution Layer: Final trade parameters

    Design principles:
    - Defense first (Paul Tudor Jones)
    - Conviction-based sizing (Druckenmiller)
    - Ensemble voting (Simons)
    - Systematic with judgment (Seykota)
    """

    def __init__(
        self,
        capital: float = 500000,
        max_portfolio_heat: float = 0.06,  # 6% max total risk
        max_single_position: float = 0.15,  # 15% max single position
        max_sector_exposure: float = 0.30,  # 30% max sector exposure
        max_correlated_positions: int = 3,
        drawdown_scale_threshold: float = 0.05,  # Scale down after 5% drawdown
        min_conviction_to_trade: float = 40,  # Minimum conviction score
    ):
        self.capital = capital
        self.max_portfolio_heat = max_portfolio_heat
        self.max_single_position = max_single_position
        self.max_sector_exposure = max_sector_exposure
        self.max_correlated_positions = max_correlated_positions
        self.drawdown_scale_threshold = drawdown_scale_threshold
        self.min_conviction_to_trade = min_conviction_to_trade

        # State
        self.current_positions: List[Dict] = []
        self.current_drawdown: float = 0.0
        self.peak_equity: float = capital
        self.current_equity: float = capital

        # Context cache
        self._market_context: Optional[Dict] = None
        self._global_context: Optional[Dict] = None
        self._sector_rankings: Optional[List] = None

        # Decision audit
        self.decision_history: List[TradeDecision] = []

    def update_equity(self, new_equity: float):
        """Update equity and calculate drawdown."""
        self.current_equity = new_equity
        self.peak_equity = max(self.peak_equity, new_equity)
        self.current_drawdown = (self.peak_equity - new_equity) / self.peak_equity

    def get_current_portfolio_heat(self) -> float:
        """Calculate current total portfolio risk."""
        total_risk = sum(p.get('risk_amount', 0) for p in self.current_positions)
        return total_risk / self.capital

    def get_sector_exposure(self, sector: str) -> float:
        """Get current exposure to a sector."""
        sector_value = sum(
            p.get('position_value', 0)
            for p in self.current_positions
            if p.get('sector') == sector
        )
        return sector_value / self.capital

    def get_correlation_with_portfolio(self, symbol: str, sector: str) -> float:
        """
        Estimate correlation with current portfolio.

        Simple approach: Same sector = high correlation
        """
        same_sector_count = sum(
            1 for p in self.current_positions
            if p.get('sector') == sector
        )

        # Simple correlation estimate based on sector overlap
        if same_sector_count == 0:
            return 0.2  # Base market correlation
        elif same_sector_count == 1:
            return 0.5
        elif same_sector_count == 2:
            return 0.7
        else:
            return 0.85

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        conviction_level: str,
        regime_multiplier: float,
        correlation: float
    ) -> Dict:
        """
        Calculate position size using conviction and correlation.

        Conviction levels:
        - A: 2% risk (highest conviction)
        - B: 1% risk (standard)
        - C: 0.5% risk (lower conviction)
        - D: No trade

        Adjustments:
        - Regime multiplier: 0.0 to 1.0
        - Correlation: Higher correlation = smaller size
        - Drawdown: Scale down when in drawdown
        """
        # Base risk by conviction
        conviction_risk = {
            'A': 0.02,
            'B': 0.01,
            'C': 0.005,
            'D': 0.0
        }

        base_risk_pct = conviction_risk.get(conviction_level, 0.0)

        if base_risk_pct == 0:
            return {
                'size': 0,
                'risk_pct': 0,
                'reason': 'Conviction too low'
            }

        # Adjust for regime
        adjusted_risk = base_risk_pct * regime_multiplier

        # Adjust for correlation (more correlated = smaller size)
        correlation_factor = 1.0 - (correlation * 0.5)  # Max 50% reduction
        adjusted_risk *= correlation_factor

        # Adjust for drawdown
        if self.current_drawdown > self.drawdown_scale_threshold:
            drawdown_factor = 1.0 - (self.current_drawdown / 0.15)  # Scale to 0 at 15% DD
            drawdown_factor = max(0.25, drawdown_factor)  # Min 25% of normal
            adjusted_risk *= drawdown_factor

        # Calculate shares
        risk_amount = self.capital * adjusted_risk
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share == 0:
            return {
                'size': 0,
                'risk_pct': 0,
                'reason': 'Invalid stop loss'
            }

        shares = int(risk_amount / risk_per_share)

        # Check max position size
        max_shares = int((self.capital * self.max_single_position) / entry_price)
        shares = min(shares, max_shares)

        position_value = shares * entry_price
        actual_risk = shares * risk_per_share
        actual_risk_pct = actual_risk / self.capital

        return {
            'size': shares,
            'position_value': position_value,
            'risk_amount': actual_risk,
            'risk_pct': actual_risk_pct * 100,
            'base_risk': base_risk_pct * 100,
            'regime_mult': regime_multiplier,
            'correlation_factor': correlation_factor,
            'drawdown_factor': drawdown_factor if self.current_drawdown > self.drawdown_scale_threshold else 1.0
        }

    def check_liquidity(self, symbol: str, avg_daily_volume: float, position_value: float) -> Tuple[bool, str]:
        """
        Check if position is liquid enough.

        Rules:
        - Position should be < 2% of ADV (can exit in 1 day easily)
        - Minimum ADV of 10 Cr
        """
        min_adv = 10_00_00_000  # 10 Cr

        if avg_daily_volume < min_adv:
            return False, f"ADV ₹{avg_daily_volume/1e7:.1f}Cr < minimum ₹10Cr"

        position_pct_of_adv = position_value / avg_daily_volume
        if position_pct_of_adv > 0.02:  # 2%
            return False, f"Position is {position_pct_of_adv*100:.1f}% of ADV (max 2%)"

        return True, "Liquidity OK"

    def run_risk_checks(
        self,
        symbol: str,
        sector: str,
        position_value: float,
        risk_amount: float,
        avg_daily_volume: float,
        has_upcoming_event: bool,
        global_risk_score: float
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Run all risk checks.

        Returns: (passed, veto_reasons, warnings)
        """
        veto_reasons = []
        warnings = []

        # 1. Portfolio heat check
        current_heat = self.get_current_portfolio_heat()
        projected_heat = current_heat + (risk_amount / self.capital)

        if projected_heat > self.max_portfolio_heat:
            veto_reasons.append(VetoReason.PORTFOLIO_FULL.value)

        # 2. Sector exposure check
        current_sector_exp = self.get_sector_exposure(sector)
        projected_sector_exp = current_sector_exp + (position_value / self.capital)

        if projected_sector_exp > self.max_sector_exposure:
            veto_reasons.append(f"Sector exposure {projected_sector_exp*100:.0f}% > {self.max_sector_exposure*100:.0f}%")

        # 3. Correlation check
        same_sector_count = sum(1 for p in self.current_positions if p.get('sector') == sector)
        if same_sector_count >= self.max_correlated_positions:
            veto_reasons.append(VetoReason.HIGH_CORRELATION.value)

        # 4. Liquidity check
        liquidity_ok, liquidity_msg = self.check_liquidity(symbol, avg_daily_volume, position_value)
        if not liquidity_ok:
            veto_reasons.append(liquidity_msg)

        # 5. Event risk
        if has_upcoming_event:
            veto_reasons.append(VetoReason.EVENT_RISK.value)

        # 6. Global risk
        if global_risk_score < -2:  # Strong risk-off
            veto_reasons.append(VetoReason.GLOBAL_RISK_OFF.value)

        # 7. Drawdown check (warning, not veto)
        if self.current_drawdown > self.drawdown_scale_threshold:
            warnings.append(f"In {self.current_drawdown*100:.1f}% drawdown - position sized down")

        return len(veto_reasons) == 0, veto_reasons, warnings

    def make_decision(
        self,
        symbol: str,
        technical_score: int,
        signal_sources: List[str],
        confluence_count: int,
        price: float,
        atr: float,
        sector: str,
        sector_rank: int,
        sector_strength: str,
        mtf_alignment: int,
        regime_name: str,
        regime_score: int,
        regime_multiplier: float,
        global_context: Dict,
        avg_daily_volume: float,
        has_upcoming_event: bool = False,
        custom_stop: Optional[float] = None,
        custom_targets: Optional[Dict] = None
    ) -> TradeDecision:
        """
        Make final trade decision considering all factors.

        This is where all components come together.
        """
        reasoning = []

        # Step 1: Calculate conviction score
        conviction_score, conviction_level, conviction_reasons = self._calculate_conviction(
            technical_score=technical_score,
            confluence_count=confluence_count,
            sector_rank=sector_rank,
            sector_strength=sector_strength,
            mtf_alignment=mtf_alignment,
            regime_score=regime_score
        )
        reasoning.extend(conviction_reasons)

        # Step 2: Determine if we should trade at all
        if conviction_score < self.min_conviction_to_trade:
            return self._create_no_trade_decision(
                symbol=symbol,
                reason=f"Conviction {conviction_score:.0f} < minimum {self.min_conviction_to_trade}",
                conviction_score=conviction_score,
                conviction_level=conviction_level,
                technical_score=technical_score,
                signal_sources=signal_sources,
                confluence_count=confluence_count,
                reasoning=reasoning
            )

        # Step 3: Calculate trade setup
        entry_price = price
        stop_loss = custom_stop if custom_stop else (entry_price - 2 * atr)

        if custom_targets:
            target_1 = custom_targets.get('target_1', entry_price + 1.5 * atr * 2)
            target_2 = custom_targets.get('target_2', entry_price + 2.5 * atr * 2)
            target_3 = custom_targets.get('target_3')
        else:
            risk = abs(entry_price - stop_loss)
            target_1 = entry_price + (risk * 1.5)
            target_2 = entry_price + (risk * 2.5)
            target_3 = entry_price + (risk * 4.0)

        # Step 4: Calculate position size
        correlation = self.get_correlation_with_portfolio(symbol, sector)
        sizing = self.calculate_position_size(
            entry_price=entry_price,
            stop_loss=stop_loss,
            conviction_level=conviction_level,
            regime_multiplier=regime_multiplier,
            correlation=correlation
        )

        if sizing['size'] == 0:
            return self._create_no_trade_decision(
                symbol=symbol,
                reason=sizing.get('reason', 'Position size calculated to zero'),
                conviction_score=conviction_score,
                conviction_level=conviction_level,
                technical_score=technical_score,
                signal_sources=signal_sources,
                confluence_count=confluence_count,
                reasoning=reasoning
            )

        reasoning.append(f"Position sized: {sizing['size']} shares (risk: {sizing['risk_pct']:.2f}%)")

        # Step 5: Run risk checks
        global_risk_score = global_context.get('risk_score', 0)
        passed, veto_reasons, warnings = self.run_risk_checks(
            symbol=symbol,
            sector=sector,
            position_value=sizing['position_value'],
            risk_amount=sizing['risk_amount'],
            avg_daily_volume=avg_daily_volume,
            has_upcoming_event=has_upcoming_event,
            global_risk_score=global_risk_score
        )

        # Step 6: Make final decision
        if not passed:
            decision_type = DecisionType.NO_TRADE
            reasoning.append(f"Trade vetoed: {', '.join(veto_reasons)}")
        elif conviction_level == 'A':
            decision_type = DecisionType.STRONG_BUY
        elif conviction_level == 'B':
            decision_type = DecisionType.BUY
        else:
            decision_type = DecisionType.WEAK_BUY

        # Calculate portfolio heat after trade
        current_heat = self.get_current_portfolio_heat()
        heat_after = current_heat + (sizing['risk_amount'] / self.capital)

        decision = TradeDecision(
            symbol=symbol,
            decision=decision_type,
            conviction_level=conviction_level,
            conviction_score=conviction_score,
            entry_price=round(entry_price, 2),
            stop_loss=round(stop_loss, 2),
            target_1=round(target_1, 2),
            target_2=round(target_2, 2),
            target_3=round(target_3, 2) if target_3 else None,
            position_size=sizing['size'],
            position_value=round(sizing['position_value'], 2),
            risk_amount=round(sizing['risk_amount'], 2),
            risk_percent=round(sizing['risk_pct'], 2),
            portfolio_heat_after=round(heat_after * 100, 2),
            market_regime=regime_name,
            regime_score=regime_score,
            global_context=global_context,
            sector_rank=sector_rank,
            sector_strength=sector_strength,
            mtf_alignment=mtf_alignment,
            technical_score=technical_score,
            signal_sources=signal_sources,
            confluence_count=confluence_count,
            passed_all_checks=passed,
            veto_reasons=veto_reasons,
            warnings=warnings,
            reasoning=reasoning
        )

        # Save to history
        self.decision_history.append(decision)

        return decision

    def _calculate_conviction(
        self,
        technical_score: int,
        confluence_count: int,
        sector_rank: int,
        sector_strength: str,
        mtf_alignment: int,
        regime_score: int
    ) -> Tuple[float, str, List[str]]:
        """
        Calculate conviction score (0-100) and level (A/B/C/D).

        Scoring:
        - Technical score: 0-30 points
        - Confluence: 0-20 points
        - Sector: 0-15 points
        - MTF alignment: 0-20 points
        - Regime: 0-15 points
        """
        score = 0
        reasons = []

        # Technical score (normalized to 0-30)
        tech_contribution = min(30, max(0, (technical_score + 10) * 1.5))
        score += tech_contribution
        reasons.append(f"Technical: {tech_contribution:.0f}/30 (raw: {technical_score:+d})")

        # Confluence (0-20)
        conf_contribution = min(20, confluence_count * 4)
        score += conf_contribution
        reasons.append(f"Confluence: {conf_contribution:.0f}/20 ({confluence_count} signals)")

        # Sector (0-15)
        sector_scores = {'STRONG': 15, 'MODERATE': 10, 'WEAK': 5, 'VERY_WEAK': 0}
        sector_contribution = sector_scores.get(sector_strength, 5)
        # Bonus for top 3 sectors
        if sector_rank <= 3:
            sector_contribution += 5
        sector_contribution = min(15, sector_contribution)
        score += sector_contribution
        reasons.append(f"Sector: {sector_contribution:.0f}/15 (Rank #{sector_rank}, {sector_strength})")

        # MTF alignment (0-20)
        if mtf_alignment >= 2:
            mtf_contribution = 20
        elif mtf_alignment == 1:
            mtf_contribution = 15
        elif mtf_alignment == 0:
            mtf_contribution = 5
        else:
            mtf_contribution = 0
        score += mtf_contribution
        reasons.append(f"MTF: {mtf_contribution:.0f}/20 (alignment: {mtf_alignment:+d})")

        # Regime (0-15)
        if regime_score >= 5:
            regime_contribution = 15
        elif regime_score >= 2:
            regime_contribution = 12
        elif regime_score >= 0:
            regime_contribution = 8
        elif regime_score >= -2:
            regime_contribution = 4
        else:
            regime_contribution = 0
        score += regime_contribution
        reasons.append(f"Regime: {regime_contribution:.0f}/15 (score: {regime_score:+d})")

        # Determine level
        if score >= 80:
            level = 'A'
        elif score >= 60:
            level = 'B'
        elif score >= 40:
            level = 'C'
        else:
            level = 'D'

        reasons.append(f"TOTAL: {score:.0f}/100 → Conviction {level}")

        return score, level, reasons

    def _create_no_trade_decision(
        self,
        symbol: str,
        reason: str,
        conviction_score: float,
        conviction_level: str,
        technical_score: int,
        signal_sources: List[str],
        confluence_count: int,
        reasoning: List[str]
    ) -> TradeDecision:
        """Create a NO_TRADE decision."""
        reasoning.append(f"NO TRADE: {reason}")

        return TradeDecision(
            symbol=symbol,
            decision=DecisionType.NO_TRADE,
            conviction_level=conviction_level,
            conviction_score=conviction_score,
            entry_price=0,
            stop_loss=0,
            target_1=0,
            target_2=0,
            target_3=None,
            position_size=0,
            position_value=0,
            risk_amount=0,
            risk_percent=0,
            portfolio_heat_after=self.get_current_portfolio_heat() * 100,
            market_regime="N/A",
            regime_score=0,
            global_context={},
            sector_rank=0,
            sector_strength="N/A",
            mtf_alignment=0,
            technical_score=technical_score,
            signal_sources=signal_sources,
            confluence_count=confluence_count,
            passed_all_checks=False,
            veto_reasons=[reason],
            warnings=[],
            reasoning=reasoning
        )

    def add_position(self, position: Dict):
        """Add a position to current holdings."""
        self.current_positions.append(position)

    def remove_position(self, symbol: str):
        """Remove a position from current holdings."""
        self.current_positions = [p for p in self.current_positions if p.get('symbol') != symbol]

    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio summary."""
        total_value = sum(p.get('position_value', 0) for p in self.current_positions)
        total_risk = sum(p.get('risk_amount', 0) for p in self.current_positions)

        # Group by sector
        sectors = {}
        for p in self.current_positions:
            sector = p.get('sector', 'Unknown')
            if sector not in sectors:
                sectors[sector] = {'count': 0, 'value': 0, 'risk': 0}
            sectors[sector]['count'] += 1
            sectors[sector]['value'] += p.get('position_value', 0)
            sectors[sector]['risk'] += p.get('risk_amount', 0)

        return {
            'positions': len(self.current_positions),
            'total_value': total_value,
            'total_risk': total_risk,
            'portfolio_heat': (total_risk / self.capital) * 100,
            'utilization': (total_value / self.capital) * 100,
            'current_equity': self.current_equity,
            'drawdown': self.current_drawdown * 100,
            'sectors': sectors,
            'available_heat': (self.max_portfolio_heat - (total_risk / self.capital)) * self.capital
        }
