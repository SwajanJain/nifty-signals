"""
Enhanced Master Orchestrator - Full Integration of Tier 1, 2, and 3 Components.

This is the ULTIMATE brain that coordinates:
- Tier 1: Core signals, regime, conviction, risk
- Tier 2: F&O data, FII/DII flows, earnings, fundamentals
- Tier 3: Regime transition, adaptive exits, walk-forward validation

Legendary principles applied:
- Simons: Multi-model ensemble, statistical edge
- Dalio: Risk parity, regime-aware, systematic
- Druckenmiller: Conviction sizing, concentrate when right
- PTJ: Defense first, macro awareness
- Seykota: Trend following with judgment

Rule: Every decision has a reason. Every reason has data.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
from rich.console import Console

# Import all components
from .orchestrator import MasterOrchestrator, TradeDecision, DecisionType, VetoReason

console = Console()


@dataclass
class EnhancedContext:
    """Enhanced market context with all data sources."""
    # Core context
    regime: str
    regime_score: int
    regime_multiplier: float

    # Global
    global_sentiment: str
    global_risk_score: int
    vix: float
    us_change: float
    asia_sentiment: str

    # Flows
    fii_net_today: float
    fii_5d_net: float
    fii_trend: str
    fii_flow_score: int
    dii_absorbing: bool

    # F&O
    pcr_oi: float
    max_pain: float
    oi_sentiment: str
    fo_score: int

    # Regime transition
    transition_warning: str
    transition_probability: float
    position_adjustment: float

    # Earnings filter
    stocks_to_avoid: List[str]
    stocks_post_earnings: List[str]


@dataclass
class EnhancedDecision(TradeDecision):
    """Enhanced trade decision with additional Tier 2/3 data."""
    # Fundamental data
    fundamental_grade: str = "C"
    fundamental_score: int = 50
    fundamental_flags: Dict = field(default_factory=dict)

    # F&O data
    fo_sentiment: str = "NEUTRAL"
    fo_score: int = 0
    max_pain: float = 0
    pcr: float = 1.0

    # Flow data
    fii_trend: str = "NEUTRAL"
    fii_flow_score: int = 0
    flow_aligned: bool = True

    # Earnings
    earnings_days_away: Optional[int] = None
    earnings_multiplier: float = 1.0

    # Transition warning
    regime_transition_risk: str = "NONE"
    transition_action: str = ""

    # Intraday levels
    immediate_resistance: float = 0
    immediate_support: float = 0
    pivot: float = 0

    # Exit strategy
    recommended_exit_strategy: str = ""
    trail_config: Dict = field(default_factory=dict)

    def get_enhanced_summary(self) -> str:
        """Get comprehensive summary including all Tier 2/3 data."""
        base_summary = self.get_summary()

        lines = [base_summary]
        lines.append("\n" + "=" * 60)
        lines.append("ENHANCED ANALYSIS (Tier 2 & 3)")
        lines.append("=" * 60)

        lines.append(f"\n[FUNDAMENTALS]")
        lines.append(f"  Grade: {self.fundamental_grade} ({self.fundamental_score}/100)")
        if self.fundamental_flags:
            if self.fundamental_flags.get('green'):
                lines.append(f"  + {', '.join(self.fundamental_flags['green'][:2])}")
            if self.fundamental_flags.get('red'):
                lines.append(f"  - {', '.join(self.fundamental_flags['red'][:2])}")

        lines.append(f"\n[F&O ANALYSIS]")
        lines.append(f"  Sentiment: {self.fo_sentiment} (Score: {self.fo_score:+d})")
        lines.append(f"  PCR: {self.pcr:.2f} | Max Pain: ₹{self.max_pain:,.0f}")

        lines.append(f"\n[INSTITUTIONAL FLOWS]")
        lines.append(f"  FII Trend: {self.fii_trend} (Score: {self.fii_flow_score:+d})")
        lines.append(f"  Flow Aligned: {'✓' if self.flow_aligned else '✗'}")

        if self.earnings_days_away is not None:
            lines.append(f"\n[EARNINGS]")
            lines.append(f"  Days Away: {self.earnings_days_away}")
            lines.append(f"  Size Multiplier: {self.earnings_multiplier:.0%}")

        lines.append(f"\n[REGIME TRANSITION]")
        lines.append(f"  Risk: {self.regime_transition_risk}")
        if self.transition_action:
            lines.append(f"  Action: {self.transition_action}")

        lines.append(f"\n[KEY LEVELS]")
        lines.append(f"  Pivot: ₹{self.pivot:,.2f}")
        lines.append(f"  Resistance: ₹{self.immediate_resistance:,.2f}")
        lines.append(f"  Support: ₹{self.immediate_support:,.2f}")

        lines.append(f"\n[EXIT STRATEGY]")
        lines.append(f"  {self.recommended_exit_strategy}")

        lines.append("=" * 60)
        return "\n".join(lines)


class EnhancedOrchestrator(MasterOrchestrator):
    """
    Enhanced Orchestrator integrating all Tier 1, 2, and 3 components.

    Workflow:
    1. Gather enhanced context (regime, flows, F&O, transitions)
    2. Filter candidates (earnings, fundamentals, liquidity)
    3. Generate signals (multi-model ensemble)
    4. Score conviction (enhanced with flow/F&O data)
    5. Risk checks (enhanced with transition warnings)
    6. Final decision with full audit trail
    7. Set exit strategy based on regime
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Initialize component trackers
        self._fo_fetcher = None
        self._fii_tracker = None
        self._earnings_calendar = None
        self._fundamentals_filter = None
        self._regime_detector = None
        self._exit_system = None
        self._levels_calculator = None
        self._trade_journal = None

    def _lazy_load_components(self):
        """Lazy load components to avoid circular imports."""
        if self._fo_fetcher is None:
            try:
                from data.sources.fo_data import FODataFetcher
                self._fo_fetcher = FODataFetcher()
            except ImportError:
                pass

        if self._fii_tracker is None:
            try:
                from data.sources.fii_dii import FIIDIITracker
                self._fii_tracker = FIIDIITracker()
            except ImportError:
                pass

        if self._earnings_calendar is None:
            try:
                from data.sources.earnings import EarningsCalendar
                self._earnings_calendar = EarningsCalendar()
            except ImportError:
                pass

        if self._fundamentals_filter is None:
            try:
                from data.sources.fundamentals import FundamentalsFilter
                self._fundamentals_filter = FundamentalsFilter()
            except ImportError:
                pass

        if self._regime_detector is None:
            try:
                from indicators.regime_transition import RegimeTransitionDetector
                self._regime_detector = RegimeTransitionDetector()
            except ImportError:
                pass

        if self._exit_system is None:
            try:
                from risk.adaptive_exits import AdaptiveExitSystem
                self._exit_system = AdaptiveExitSystem()
            except ImportError:
                pass

        if self._levels_calculator is None:
            try:
                from indicators.intraday_levels import IntradayLevelsCalculator
                self._levels_calculator = IntradayLevelsCalculator()
            except ImportError:
                pass

    def gather_enhanced_context(
        self,
        regime: str,
        regime_score: int,
        global_data: Optional[Dict] = None
    ) -> EnhancedContext:
        """Gather all context data from Tier 2 sources."""
        self._lazy_load_components()

        # Defaults
        context = EnhancedContext(
            regime=regime,
            regime_score=regime_score,
            regime_multiplier=self._get_regime_multiplier(regime),
            global_sentiment="NEUTRAL",
            global_risk_score=3,
            vix=15,
            us_change=0,
            asia_sentiment="NEUTRAL",
            fii_net_today=0,
            fii_5d_net=0,
            fii_trend="NEUTRAL",
            fii_flow_score=0,
            dii_absorbing=False,
            pcr_oi=1.0,
            max_pain=0,
            oi_sentiment="NEUTRAL",
            fo_score=0,
            transition_warning="NONE",
            transition_probability=0,
            position_adjustment=1.0,
            stocks_to_avoid=[],
            stocks_post_earnings=[]
        )

        # Global data
        if global_data:
            context.global_sentiment = global_data.get('sentiment', 'NEUTRAL')
            context.global_risk_score = global_data.get('risk_score', 3)
            context.vix = global_data.get('vix', 15)
            context.us_change = global_data.get('us_change', 0)

        # FII/DII flows
        if self._fii_tracker:
            try:
                flow_analysis = self._fii_tracker.analyze_flows(10)
                context.fii_net_today = flow_analysis.fii_net_today
                context.fii_5d_net = flow_analysis.fii_5d_net
                context.fii_trend = flow_analysis.fii_trend.value
                context.fii_flow_score = flow_analysis.score
                context.dii_absorbing = (
                    flow_analysis.fii_5d_net < -2000 and
                    flow_analysis.dii_5d_net > 1500
                )
            except Exception as e:
                console.print(f"[yellow]FII/DII fetch failed: {e}[/yellow]")

        # F&O data
        if self._fo_fetcher:
            try:
                fo_analysis = self._fo_fetcher.analyze_option_chain("NIFTY")
                if fo_analysis:
                    context.pcr_oi = fo_analysis.pcr_oi
                    context.max_pain = fo_analysis.max_pain
                    context.oi_sentiment = fo_analysis.sentiment.value
                    context.fo_score = fo_analysis.sentiment_score
            except Exception as e:
                console.print(f"[yellow]F&O fetch failed: {e}[/yellow]")

        # Regime transition
        if self._regime_detector:
            try:
                warning = self._regime_detector.detect_transition(
                    current_regime=regime,
                    breadth=self._regime_detector._default_breadth(),
                    distribution=None,
                    vix=context.vix,
                    fii_5d_flow=context.fii_5d_net,
                    global_risk_score=context.global_risk_score
                )
                context.transition_warning = warning.warning_level.value
                context.transition_probability = warning.probability
                context.position_adjustment = warning.position_adjustment
            except Exception as e:
                console.print(f"[yellow]Transition detection failed: {e}[/yellow]")

        # Earnings calendar
        if self._earnings_calendar:
            try:
                calendar = self._earnings_calendar.get_weekly_calendar()
                context.stocks_to_avoid = calendar.stocks_to_avoid
                context.stocks_post_earnings = calendar.stocks_post_earnings
            except Exception as e:
                console.print(f"[yellow]Earnings fetch failed: {e}[/yellow]")

        return context

    def _get_regime_multiplier(self, regime: str) -> float:
        """Get position size multiplier based on regime."""
        multipliers = {
            'STRONG_BULL': 1.0,
            'BULL': 0.8,
            'NEUTRAL': 0.5,
            'BEAR': 0.3,
            'STRONG_BEAR': 0.2,
            'CRASH': 0.0
        }
        return multipliers.get(regime.upper(), 0.5)

    def filter_candidates(
        self,
        candidates: List[str],
        context: EnhancedContext
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        Filter candidates using Tier 2 filters.

        Returns: (filtered_candidates, filtered_out_with_reasons)
        """
        self._lazy_load_components()

        filtered = []
        removed = {}

        for symbol in candidates:
            skip = False
            reason = ""

            # 1. Earnings filter
            if symbol in context.stocks_to_avoid:
                skip = True
                reason = "Earnings within 3 days"

            # 2. Fundamentals filter
            if not skip and self._fundamentals_filter:
                try:
                    fund_check = self._fundamentals_filter.check_stock(symbol)
                    if not fund_check.passes_filter:
                        skip = True
                        reason = f"Fundamentals: {fund_check.red_flags[0] if fund_check.red_flags else 'Weak'}"
                except:
                    pass

            if skip:
                removed[symbol] = reason
            else:
                filtered.append(symbol)

        return filtered, removed

    def make_enhanced_decision(
        self,
        symbol: str,
        price: float,
        atr: float,
        technical_score: int,
        signal_sources: List[str],
        confluence_count: int,
        sector: str,
        sector_rank: int,
        sector_strength: str,
        mtf_alignment: int,
        avg_daily_volume: float,
        context: EnhancedContext,
        prev_high: Optional[float] = None,
        prev_low: Optional[float] = None,
        prev_close: Optional[float] = None
    ) -> EnhancedDecision:
        """
        Make enhanced decision using all components.

        This is the MASTER decision function.
        """
        self._lazy_load_components()
        reasoning = []

        # === Step 1: Enhanced Conviction Score ===
        base_conviction, conviction_level, conviction_reasons = self._calculate_conviction(
            technical_score=technical_score,
            confluence_count=confluence_count,
            sector_rank=sector_rank,
            sector_strength=sector_strength,
            mtf_alignment=mtf_alignment,
            regime_score=context.regime_score
        )
        reasoning.extend(conviction_reasons)

        # Enhance conviction with flow data
        flow_bonus = 0
        if context.fii_flow_score >= 2:
            flow_bonus = 5
            reasoning.append(f"Flow bonus: +5 (FII buying)")
        elif context.fii_flow_score <= -2:
            flow_bonus = -5
            reasoning.append(f"Flow penalty: -5 (FII selling)")

        # Enhance with F&O data
        fo_bonus = 0
        if context.fo_score >= 2:
            fo_bonus = 3
            reasoning.append(f"F&O bonus: +3 (Bullish OI)")
        elif context.fo_score <= -2:
            fo_bonus = -3
            reasoning.append(f"F&O penalty: -3 (Bearish OI)")

        enhanced_conviction = base_conviction + flow_bonus + fo_bonus
        enhanced_conviction = max(0, min(100, enhanced_conviction))

        # Recalculate conviction level
        if enhanced_conviction >= 80:
            conviction_level = 'A'
        elif enhanced_conviction >= 60:
            conviction_level = 'B'
        elif enhanced_conviction >= 40:
            conviction_level = 'C'
        else:
            conviction_level = 'D'

        reasoning.append(f"Enhanced conviction: {enhanced_conviction:.0f}/100 → {conviction_level}")

        # === Step 2: Additional Filters ===

        # Check earnings
        earnings_days = None
        earnings_multiplier = 1.0
        if self._earnings_calendar:
            try:
                status = self._earnings_calendar.get_stock_status(symbol)
                earnings_days = status.days_to_earnings
                earnings_multiplier = status.position_size_multiplier
                if status.should_skip:
                    return self._create_enhanced_no_trade(
                        symbol, f"Earnings in {earnings_days} days",
                        enhanced_conviction, conviction_level, context
                    )
            except:
                pass

        # Check fundamentals
        fundamental_grade = "C"
        fundamental_score = 50
        fundamental_flags = {}
        fundamental_multiplier = 1.0

        if self._fundamentals_filter:
            try:
                fund_check = self._fundamentals_filter.check_stock(symbol)
                fundamental_grade = fund_check.grade.value
                fundamental_score = fund_check.quality_score
                fundamental_flags = {
                    'green': fund_check.green_flags,
                    'red': fund_check.red_flags
                }
                fundamental_multiplier = fund_check.position_multiplier

                if not fund_check.passes_filter:
                    return self._create_enhanced_no_trade(
                        symbol, f"Fundamental filter: {fund_check.red_flags[0] if fund_check.red_flags else 'Weak'}",
                        enhanced_conviction, conviction_level, context
                    )
            except:
                pass

        # === Step 3: Position Sizing with All Adjustments ===

        # Apply transition warning adjustment
        regime_multiplier = context.regime_multiplier * context.position_adjustment

        # Apply earnings and fundamental adjustments
        final_multiplier = regime_multiplier * earnings_multiplier * fundamental_multiplier

        correlation = self.get_correlation_with_portfolio(symbol, sector)
        entry_price = price
        stop_loss = entry_price - 2 * atr

        sizing = self.calculate_position_size(
            entry_price=entry_price,
            stop_loss=stop_loss,
            conviction_level=conviction_level,
            regime_multiplier=final_multiplier,
            correlation=correlation
        )

        if sizing['size'] == 0:
            return self._create_enhanced_no_trade(
                symbol, sizing.get('reason', 'Zero position size'),
                enhanced_conviction, conviction_level, context
            )

        # === Step 4: Risk Checks ===

        # Check if flow aligned (bullish signal + bullish flow)
        flow_aligned = not (
            (technical_score > 0 and context.fii_flow_score < -2) or
            (technical_score < 0 and context.fii_flow_score > 2)
        )

        has_event = earnings_days is not None and earnings_days <= 5

        passed, veto_reasons, warnings = self.run_risk_checks(
            symbol=symbol,
            sector=sector,
            position_value=sizing['position_value'],
            risk_amount=sizing['risk_amount'],
            avg_daily_volume=avg_daily_volume,
            has_upcoming_event=has_event,
            global_risk_score=context.global_risk_score
        )

        # Add transition warning
        if context.transition_warning in ['CRITICAL', 'HIGH']:
            warnings.append(f"Regime transition risk: {context.transition_warning}")

        # Add flow misalignment warning
        if not flow_aligned:
            warnings.append("Signal-flow misalignment")

        # === Step 5: Calculate Levels ===
        pivot = 0
        immediate_resistance = entry_price * 1.02
        immediate_support = entry_price * 0.98

        if self._levels_calculator and prev_high and prev_low and prev_close:
            try:
                levels = self._levels_calculator.calculate_all_levels(
                    symbol=symbol,
                    current_price=price,
                    prev_high=prev_high,
                    prev_low=prev_low,
                    prev_close=prev_close
                )
                pivot = levels.pivot
                immediate_resistance = levels.immediate_resistance
                immediate_support = levels.immediate_support
            except:
                pass

        # === Step 6: Determine Exit Strategy ===
        exit_strategy = self._determine_exit_strategy(context.regime, conviction_level)

        # === Step 7: Build Final Decision ===

        # Calculate targets
        risk = abs(entry_price - stop_loss)
        target_1 = entry_price + (risk * 1.5)
        target_2 = entry_price + (risk * 2.5)
        target_3 = entry_price + (risk * 4.0)

        if not passed:
            decision_type = DecisionType.NO_TRADE
        elif conviction_level == 'A':
            decision_type = DecisionType.STRONG_BUY
        elif conviction_level == 'B':
            decision_type = DecisionType.BUY
        else:
            decision_type = DecisionType.WEAK_BUY

        current_heat = self.get_current_portfolio_heat()
        heat_after = current_heat + (sizing['risk_amount'] / self.capital)

        decision = EnhancedDecision(
            # Base decision fields
            symbol=symbol,
            decision=decision_type,
            conviction_level=conviction_level,
            conviction_score=enhanced_conviction,
            entry_price=round(entry_price, 2),
            stop_loss=round(stop_loss, 2),
            target_1=round(target_1, 2),
            target_2=round(target_2, 2),
            target_3=round(target_3, 2),
            position_size=sizing['size'],
            position_value=round(sizing['position_value'], 2),
            risk_amount=round(sizing['risk_amount'], 2),
            risk_percent=round(sizing['risk_pct'], 2),
            portfolio_heat_after=round(heat_after * 100, 2),
            market_regime=context.regime,
            regime_score=context.regime_score,
            global_context={'risk_score': context.global_risk_score, 'vix': context.vix},
            sector_rank=sector_rank,
            sector_strength=sector_strength,
            mtf_alignment=mtf_alignment,
            technical_score=technical_score,
            signal_sources=signal_sources,
            confluence_count=confluence_count,
            passed_all_checks=passed,
            veto_reasons=veto_reasons,
            warnings=warnings,
            reasoning=reasoning,

            # Enhanced fields
            fundamental_grade=fundamental_grade,
            fundamental_score=fundamental_score,
            fundamental_flags=fundamental_flags,
            fo_sentiment=context.oi_sentiment,
            fo_score=context.fo_score,
            max_pain=context.max_pain,
            pcr=context.pcr_oi,
            fii_trend=context.fii_trend,
            fii_flow_score=context.fii_flow_score,
            flow_aligned=flow_aligned,
            earnings_days_away=earnings_days,
            earnings_multiplier=earnings_multiplier,
            regime_transition_risk=context.transition_warning,
            transition_action=f"Position adj: {context.position_adjustment:.0%}" if context.position_adjustment < 1 else "",
            immediate_resistance=round(immediate_resistance, 2),
            immediate_support=round(immediate_support, 2),
            pivot=round(pivot, 2),
            recommended_exit_strategy=exit_strategy,
            trail_config={}
        )

        self.decision_history.append(decision)
        return decision

    def _determine_exit_strategy(self, regime: str, conviction: str) -> str:
        """Determine exit strategy based on regime and conviction."""
        regime_upper = regime.upper()

        if regime_upper in ['CRASH', 'STRONG_BEAR']:
            return "TIGHT TRAIL: 1.5% from high, quick profit booking"
        elif regime_upper == 'BEAR':
            return "DEFENSIVE: 2% trail, book 50% at T1, tight stops"
        elif regime_upper == 'NEUTRAL':
            return "BALANCED: 2.5% trail, scale out at targets"
        elif regime_upper == 'BULL':
            if conviction == 'A':
                return "LET IT RUN: 3% trail, hold for T2/T3"
            else:
                return "STANDARD: 2.5% trail, book 50% at T1"
        else:  # STRONG_BULL
            if conviction == 'A':
                return "MAXIMIZE: 4% wide trail, pyramiding allowed, ride the trend"
            else:
                return "TREND RIDE: 3% trail, partial exits at resistance"

    def _create_enhanced_no_trade(
        self,
        symbol: str,
        reason: str,
        conviction: float,
        conviction_level: str,
        context: EnhancedContext
    ) -> EnhancedDecision:
        """Create NO_TRADE enhanced decision."""
        return EnhancedDecision(
            symbol=symbol,
            decision=DecisionType.NO_TRADE,
            conviction_level=conviction_level,
            conviction_score=conviction,
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
            market_regime=context.regime,
            regime_score=context.regime_score,
            global_context={},
            sector_rank=0,
            sector_strength="N/A",
            mtf_alignment=0,
            technical_score=0,
            signal_sources=[],
            confluence_count=0,
            passed_all_checks=False,
            veto_reasons=[reason],
            warnings=[],
            reasoning=[f"NO TRADE: {reason}"],
            fii_trend=context.fii_trend,
            fii_flow_score=context.fii_flow_score,
            regime_transition_risk=context.transition_warning
        )

    def get_daily_briefing(self, context: EnhancedContext) -> str:
        """Generate daily market briefing."""
        lines = []
        lines.append("=" * 70)
        lines.append(f"DAILY MARKET BRIEFING - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("=" * 70)

        # Regime
        lines.append(f"\n[REGIME]")
        lines.append(f"  Current: {context.regime} (Score: {context.regime_score:+d})")
        lines.append(f"  Position Multiplier: {context.regime_multiplier:.0%}")

        # Transition warning
        if context.transition_warning not in ['NONE', 'LOW']:
            lines.append(f"\n  ⚠️ TRANSITION WARNING: {context.transition_warning}")
            lines.append(f"     Probability: {context.transition_probability:.0f}%")
            lines.append(f"     Adjust positions to: {context.position_adjustment:.0%}")

        # Global
        lines.append(f"\n[GLOBAL]")
        lines.append(f"  Sentiment: {context.global_sentiment}")
        lines.append(f"  Risk Score: {context.global_risk_score}/5")
        lines.append(f"  VIX: {context.vix:.1f}")
        lines.append(f"  US Change: {context.us_change:+.1f}%")

        # Flows
        lines.append(f"\n[INSTITUTIONAL FLOWS]")
        lines.append(f"  FII Today: ₹{context.fii_net_today:,.0f} Cr")
        lines.append(f"  FII 5-Day: ₹{context.fii_5d_net:,.0f} Cr ({context.fii_trend})")
        lines.append(f"  Flow Score: {context.fii_flow_score:+d}")
        if context.dii_absorbing:
            lines.append(f"  DII absorbing FII selling ✓")

        # F&O
        lines.append(f"\n[F&O DATA]")
        lines.append(f"  PCR (OI): {context.pcr_oi:.2f}")
        lines.append(f"  Max Pain: ₹{context.max_pain:,.0f}")
        lines.append(f"  OI Sentiment: {context.oi_sentiment} ({context.fo_score:+d})")

        # Earnings
        if context.stocks_to_avoid:
            lines.append(f"\n[EARNINGS - AVOID]")
            lines.append(f"  {', '.join(context.stocks_to_avoid[:10])}")

        # Trading guidance
        lines.append(f"\n[TODAY'S GUIDANCE]")
        if context.regime.upper() in ['CRASH', 'STRONG_BEAR']:
            lines.append("  ❌ NO NEW LONGS - Stay in cash")
        elif context.transition_warning == 'CRITICAL':
            lines.append("  ⚠️ REDUCE EXPOSURE - Transition risk high")
        elif context.fii_flow_score <= -3:
            lines.append("  ⚠️ CAUTIOUS - Heavy FII selling")
        elif context.regime.upper() == 'STRONG_BULL' and context.fii_flow_score >= 2:
            lines.append("  ✅ AGGRESSIVE LONGS - All signals aligned")
        else:
            lines.append("  📊 SELECTIVE - Follow conviction levels")

        lines.append("=" * 70)
        return "\n".join(lines)


def create_enhanced_orchestrator(capital: float = 500000) -> EnhancedOrchestrator:
    """Factory function to create enhanced orchestrator."""
    return EnhancedOrchestrator(
        capital=capital,
        max_portfolio_heat=0.06,
        max_single_position=0.15,
        max_sector_exposure=0.30,
        max_correlated_positions=3,
        drawdown_scale_threshold=0.05,
        min_conviction_to_trade=40
    )
