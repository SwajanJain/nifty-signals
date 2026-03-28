"""
Intelligent Orchestrator - The Ultimate Integration Layer.

This module brings together ALL components into a unified trading system:
1. Quantitative Backbone (signals, indicators, ensemble models)
2. Reliable Data Layer (TrueData primary, yfinance fallback)
3. Position Management (portfolio tracking, risk limits)
4. Intelligence Layer (5 AI agents for qualitative analysis)

Design Philosophy:
- Quantitative signals provide the FOUNDATION
- Data quality gates determine CONFIDENCE
- Position manager enforces DISCIPLINE
- Intelligence layer adds WISDOM
- Human trader makes FINAL DECISION

Flow:
1. Data Collection → Check quality gates
2. Signal Generation → Quantitative backbone
3. Intelligence Analysis → AI validation and context
4. Risk Management → Position sizing and limits
5. Decision Output → Clear, actionable recommendation

Legendary Principles:
- Simons: Multi-model ensemble, statistical edge
- Dalio: Risk parity, systematic, regime-aware
- Druckenmiller: Conviction sizing, concentrate when right
- PTJ: Defense first, macro awareness
- Seykota: Trend following with judgment
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import logging
import json

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Core components
from .enhanced_orchestrator import EnhancedContext, EnhancedDecision
from .conviction import ConvictionScorer

# Data layer (use absolute imports for compatibility)
from data.reliable_fetcher import ReliableDataFetcher, get_reliable_fetcher
from data.models import DataQuality, SystemDataHealth
from data.quality_monitor import DataGates, DataGateResults, get_data_gates

# Position management
from journal.position_manager import (
    PositionManager,
    Position,
    PortfolioStatus,
    get_position_manager
)
from journal.trade_journal import TradeJournal

# Intelligence layer
from intelligence import (
    IntelligenceOrchestrator as IntelOrchestrator,
    IntelligenceResult,
    AgentContext,
    Confidence,
    get_intelligence_orchestrator as get_intel_orchestrator
)

logger = logging.getLogger(__name__)
console = Console()


class TradingDecision(Enum):
    """Final trading decision."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    AVOID = "AVOID"
    SELL = "SELL"


@dataclass
class DataHealthStatus:
    """Current data health across all sources."""
    price_quality: str
    fii_dii_quality: str
    fundamentals_quality: str
    global_quality: str

    overall_quality: str
    data_multiplier: float
    can_trade: bool
    warnings: List[str] = field(default_factory=list)


@dataclass
class IntegratedAnalysis:
    """Complete integrated analysis from all layers."""
    timestamp: datetime
    symbol: str

    # Data Health
    data_health: DataHealthStatus

    # Quantitative Analysis
    quant_conviction: int
    quant_signal: str
    model_votes: Dict[str, bool]
    technical_levels: Dict[str, float]

    # Intelligence Analysis
    intelligence_result: Optional[IntelligenceResult]
    ai_confidence: str
    ai_position_modifier: float

    # Position Management
    portfolio_status: PortfolioStatus
    can_take_position: bool
    max_position_size: int
    max_position_value: float

    # Combined Assessment
    final_decision: TradingDecision
    final_conviction: int
    final_position_modifier: float

    # Trade Setup (if applicable)
    entry_price: float = 0
    stop_loss: float = 0
    target1: float = 0
    target2: float = 0
    recommended_shares: int = 0
    risk_amount: float = 0

    # Reasoning
    bullish_factors: List[str] = field(default_factory=list)
    bearish_factors: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['final_decision'] = self.final_decision.value
        if self.intelligence_result:
            data['intelligence_result'] = self.intelligence_result.to_dict()
        return data


class IntelligentOrchestrator:
    """
    The Ultimate Trading Orchestrator.

    Integrates:
    - Quantitative signal generation
    - Multi-source reliable data
    - Position and risk management
    - AI-powered analysis and validation
    """

    def __init__(
        self,
        capital: float = 1_000_000,
        use_intelligence: bool = True
    ):
        self.capital = capital
        self.use_intelligence = use_intelligence

        # Initialize components
        self.data_fetcher = get_reliable_fetcher()
        self.data_gates = get_data_gates()
        self.position_manager = get_position_manager(capital)
        self.conviction_scorer = ConvictionScorer()

        if use_intelligence:
            self.intelligence = get_intel_orchestrator()
        else:
            self.intelligence = None

        self.journal = TradeJournal()

    def analyze_stock(
        self,
        symbol: str,
        market_regime: str = "NEUTRAL",
        include_intelligence: bool = True
    ) -> IntegratedAnalysis:
        """
        Perform complete integrated analysis for a stock.

        This is the main entry point for the intelligent system.
        """
        timestamp = datetime.now()

        # Step 1: Fetch all data with quality tracking
        data_health, all_data = self._fetch_all_data(symbol)

        # Step 2: Check if we can proceed
        if not data_health.can_trade:
            return self._create_no_trade_analysis(
                timestamp, symbol, data_health,
                "Data quality insufficient for trading"
            )

        # Step 3: Generate quantitative signals
        quant_analysis = self._generate_quantitative_signals(
            symbol, all_data, market_regime
        )

        # Step 4: Intelligence layer analysis
        intelligence_result = None
        if include_intelligence and self.use_intelligence:
            intelligence_result = self._run_intelligence_analysis(
                symbol, all_data, quant_analysis, market_regime
            )

        # Step 5: Position management check
        portfolio_status, position_sizing = self._check_position_management(
            symbol, all_data, data_health.data_multiplier
        )

        # Step 6: Combine everything into final decision
        analysis = self._combine_analysis(
            timestamp=timestamp,
            symbol=symbol,
            data_health=data_health,
            all_data=all_data,
            quant_analysis=quant_analysis,
            intelligence_result=intelligence_result,
            portfolio_status=portfolio_status,
            position_sizing=position_sizing,
            market_regime=market_regime
        )

        return analysis

    def _fetch_all_data(
        self,
        symbol: str
    ) -> Tuple[DataHealthStatus, Dict[str, Any]]:
        """Fetch all required data with quality tracking."""
        all_data = {}

        # Fetch price data - returns OHLCVData object
        price_result = self.data_fetcher.get_historical_data(symbol, days=365)
        all_data['price_data'] = price_result.df
        all_data['price_quality'] = price_result.quality

        # Fetch fundamentals - returns DataResult object
        fund_result = self.data_fetcher.get_fundamentals(symbol)
        all_data['fundamentals'] = fund_result.data
        all_data['fund_quality'] = fund_result.quality

        # Global context from yfinance
        global_result = self.data_fetcher.get_global_context()
        all_data['global_context'] = global_result.data
        all_data['global_quality'] = global_result.quality

        # FII/DII - not available from yfinance, use degraded placeholder
        all_data['fii_dii'] = {'is_synthetic': True, 'fii_net': 0, 'dii_net': 0}
        all_data['fii_quality'] = DataQuality.DEGRADED

        # Run data gates
        gate_results = self.data_gates.check_all_gates(
            price_quality=price_result.quality,
            price_data=price_result.df,
            fii_dii_data=all_data['fii_dii'],
            fii_dii_quality=all_data['fii_quality'],
            fundamentals=fund_result.data,
            fundamentals_quality=fund_result.quality,
            earnings_data={},
            earnings_quality=fund_result.quality,
            global_context=all_data['global_context'],
            global_quality=all_data['global_quality']
        )

        all_data['gate_results'] = gate_results

        # Build health status
        data_health = DataHealthStatus(
            price_quality=price_result.quality.value,
            fii_dii_quality=all_data['fii_quality'].value,
            fundamentals_quality=fund_result.quality.value,
            global_quality=all_data['global_quality'].value,
            overall_quality=gate_results.overall_quality.value,
            data_multiplier=gate_results.combined_multiplier,
            can_trade=gate_results.allow_trading,
            warnings=gate_results.warnings
        )

        return data_health, all_data

    def _generate_quantitative_signals(
        self,
        symbol: str,
        all_data: Dict[str, Any],
        market_regime: str
    ) -> Dict[str, Any]:
        """Generate quantitative signals from the backbone system."""
        price_data = all_data.get('price_data')

        # Default structure if we can't generate signals
        quant = {
            'conviction_score': 0,
            'signal': 'HOLD',
            'model_votes': {},
            'technical_indicators': {},
            'levels': {}
        }

        if price_data is None or price_data.empty:
            return quant

        try:
            # Calculate technical indicators
            df = price_data.copy()

            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))

            # Moving averages
            df['ema20'] = df['close'].ewm(span=20).mean()
            df['ema50'] = df['close'].ewm(span=50).mean()
            df['ema200'] = df['close'].ewm(span=200).mean()

            # MACD
            exp1 = df['close'].ewm(span=12).mean()
            exp2 = df['close'].ewm(span=26).mean()
            df['macd'] = exp1 - exp2
            df['macd_signal'] = df['macd'].ewm(span=9).mean()

            latest = df.iloc[-1]
            current_price = latest['close']

            # Model votes (simplified)
            votes = {}

            # Momentum model
            rsi = latest['rsi']
            votes['momentum'] = 30 < rsi < 70 and current_price > latest['ema20']

            # Trend model
            votes['trend'] = (
                current_price > latest['ema50'] and
                latest['ema20'] > latest['ema50']
            )

            # Breakout model (simplified - price near 52-week high)
            high_52w = df['high'].rolling(252).max().iloc[-1] if len(df) >= 252 else df['high'].max()
            votes['breakout'] = current_price > high_52w * 0.95

            # Mean reversion model
            votes['mean_reversion'] = rsi < 40 and current_price > latest['ema200']

            # Calculate conviction
            bullish_votes = sum(1 for v in votes.values() if v)
            base_conviction = bullish_votes * 20  # 0-80 from models

            # Regime adjustment
            regime_multiplier = {
                'STRONG_BULL': 1.2,
                'BULL': 1.0,
                'NEUTRAL': 0.8,
                'BEAR': 0.6,
                'STRONG_BEAR': 0.4,
                'CRASH': 0.2
            }.get(market_regime, 0.8)

            conviction = int(base_conviction * regime_multiplier)
            conviction = min(100, max(0, conviction))

            # Determine signal
            if bullish_votes >= 3 and conviction >= 60:
                signal = 'STRONG_BUY'
            elif bullish_votes >= 2 and conviction >= 40:
                signal = 'BUY'
            elif bullish_votes <= 1:
                signal = 'HOLD'
            else:
                signal = 'HOLD'

            # Calculate levels
            atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
            stop_loss = current_price - (2 * atr)
            target1 = current_price + (3 * atr)
            target2 = current_price + (5 * atr)

            quant = {
                'conviction_score': conviction,
                'signal': signal,
                'model_votes': votes,
                'technical_indicators': {
                    'rsi': rsi,
                    'macd': latest['macd'],
                    'macd_signal': latest['macd_signal'],
                    'ema20': latest['ema20'],
                    'ema50': latest['ema50'],
                    'ema200': latest['ema200'],
                    'current_price': current_price
                },
                'levels': {
                    'entry': current_price,
                    'stop_loss': stop_loss,
                    'target1': target1,
                    'target2': target2,
                    'atr': atr
                }
            }

        except Exception as e:
            logger.error(f"Error generating quantitative signals: {e}")

        return quant

    def _run_intelligence_analysis(
        self,
        symbol: str,
        all_data: Dict[str, Any],
        quant_analysis: Dict[str, Any],
        market_regime: str
    ) -> Optional[IntelligenceResult]:
        """Run the AI intelligence layer analysis."""
        if not self.intelligence:
            return None

        try:
            # Build context for intelligence layer
            price_data = all_data.get('price_data')
            current_price = 0
            if price_data is not None and not price_data.empty:
                current_price = price_data.iloc[-1]['close']

            context = AgentContext(
                timestamp=datetime.now(),
                symbol=symbol,
                price_data={
                    'current_price': current_price,
                    'has_earnings_soon': None,  # Would need to fetch
                },
                technical_indicators=quant_analysis.get('technical_indicators', {}),
                market_regime=market_regime,
                sector_data=all_data.get('fundamentals', {}).get('sector_data', {}),
                global_context=all_data.get('global_context', {}),
                fii_dii_data=all_data.get('fii_dii', {}),
                quantitative_signals=quant_analysis.get('levels', {}),
                ensemble_votes=quant_analysis.get('model_votes', {}),
                conviction_score=quant_analysis.get('conviction_score', 0),
                recent_trades=self._get_recent_trades(symbol),
                performance_stats=self._get_performance_stats(),
                data_quality={
                    'price': all_data.get('price_quality', 'unknown').value if hasattr(all_data.get('price_quality'), 'value') else 'unknown',
                    'fii_dii': all_data.get('fii_quality', 'unknown').value if hasattr(all_data.get('fii_quality'), 'value') else 'unknown',
                    'fundamentals': all_data.get('fund_quality', 'unknown').value if hasattr(all_data.get('fund_quality'), 'value') else 'unknown',
                }
            )

            return self.intelligence.analyze(context)

        except Exception as e:
            logger.error(f"Intelligence analysis failed: {e}")
            return None

    def _check_position_management(
        self,
        symbol: str,
        all_data: Dict[str, Any],
        data_multiplier: float
    ) -> Tuple[PortfolioStatus, Dict[str, Any]]:
        """Check position management constraints."""
        # Get portfolio status
        portfolio_status = self.position_manager.get_portfolio_status(data_multiplier)

        # Get sector for limit checks
        sector = all_data.get('fundamentals', {}).get('sector', 'Unknown')

        # Check if we can take new position
        can_take, reason = self.position_manager.can_take_new_position(
            sector, data_multiplier
        )

        # Calculate position sizing
        levels = all_data.get('levels', {})
        entry = levels.get('entry', 0)
        stop = levels.get('stop_loss', 0)

        # Determine conviction level
        quant = all_data.get('quant_analysis', {})
        conviction_score = quant.get('conviction_score', 50)

        if conviction_score >= 70:
            conviction_level = 'A'
        elif conviction_score >= 55:
            conviction_level = 'B'
        else:
            conviction_level = 'C'

        position_sizing = self.position_manager.calculate_position_size(
            entry_price=entry if entry else 100,
            stop_loss=stop if stop else 95,
            conviction_level=conviction_level,
            data_quality_multiplier=data_multiplier
        )

        position_sizing['can_take_position'] = can_take
        position_sizing['rejection_reason'] = reason if not can_take else ''

        return portfolio_status, position_sizing

    def _get_recent_trades(self, symbol: str = None) -> List[Dict]:
        """Get recent trades for the LEARNER agent."""
        trades = self.journal.get_closed_trades()[-50:]
        return [t.to_dict() for t in trades]

    def _get_performance_stats(self) -> Dict[str, Any]:
        """Get performance stats for context."""
        portfolio = self.position_manager.get_portfolio_status()
        return {
            'portfolio_heat': portfolio.current_heat,
            'positions_count': portfolio.total_positions,
            'sector_exposure': portfolio.positions_by_sector,
        }

    def _combine_analysis(
        self,
        timestamp: datetime,
        symbol: str,
        data_health: DataHealthStatus,
        all_data: Dict[str, Any],
        quant_analysis: Dict[str, Any],
        intelligence_result: Optional[IntelligenceResult],
        portfolio_status: PortfolioStatus,
        position_sizing: Dict[str, Any],
        market_regime: str
    ) -> IntegratedAnalysis:
        """Combine all analysis into final decision."""
        # Start with quantitative assessment
        quant_conviction = quant_analysis.get('conviction_score', 0)
        quant_signal = quant_analysis.get('signal', 'HOLD')
        levels = quant_analysis.get('levels', {})

        # Get AI adjustments
        ai_confidence = 'medium'
        ai_modifier = 1.0
        if intelligence_result:
            ai_confidence = intelligence_result.confidence.value
            ai_modifier = intelligence_result.final_position_modifier

        # Calculate final position modifier
        final_modifier = data_health.data_multiplier * ai_modifier

        # Adjust conviction based on intelligence
        conviction_adjustment = 0
        if intelligence_result:
            if intelligence_result.confidence == Confidence.HIGH:
                conviction_adjustment = 10
            elif intelligence_result.confidence == Confidence.LOW:
                conviction_adjustment = -10

        final_conviction = min(100, max(0, quant_conviction + conviction_adjustment))

        # Determine final decision
        can_take = position_sizing.get('can_take_position', False)

        if not data_health.can_trade:
            decision = TradingDecision.AVOID
        elif not can_take:
            decision = TradingDecision.AVOID
        elif final_modifier == 0:
            decision = TradingDecision.AVOID
        elif quant_signal == 'STRONG_BUY' and final_conviction >= 70:
            decision = TradingDecision.STRONG_BUY
        elif quant_signal in ['STRONG_BUY', 'BUY'] and final_conviction >= 50:
            decision = TradingDecision.BUY
        else:
            decision = TradingDecision.HOLD

        # Gather all factors
        bullish = list(quant_analysis.get('model_votes', {}).keys())
        bullish = [k for k, v in quant_analysis.get('model_votes', {}).items() if v]
        bearish = [k for k, v in quant_analysis.get('model_votes', {}).items() if not v]

        if intelligence_result:
            bullish.extend(intelligence_result.all_bullish)
            bearish.extend(intelligence_result.all_bearish)

        risks = list(data_health.warnings)
        if intelligence_result:
            risks.extend(intelligence_result.all_risks)

        warnings = []
        if portfolio_status.warnings:
            warnings.extend(portfolio_status.warnings)

        # Build analysis object
        analysis = IntegratedAnalysis(
            timestamp=timestamp,
            symbol=symbol,
            data_health=data_health,
            quant_conviction=quant_conviction,
            quant_signal=quant_signal,
            model_votes=quant_analysis.get('model_votes', {}),
            technical_levels=quant_analysis.get('technical_indicators', {}),
            intelligence_result=intelligence_result,
            ai_confidence=ai_confidence,
            ai_position_modifier=ai_modifier,
            portfolio_status=portfolio_status,
            can_take_position=can_take,
            max_position_size=position_sizing.get('shares', 0),
            max_position_value=position_sizing.get('value', 0),
            final_decision=decision,
            final_conviction=final_conviction,
            final_position_modifier=final_modifier,
            entry_price=levels.get('entry', 0),
            stop_loss=levels.get('stop_loss', 0),
            target1=levels.get('target1', 0),
            target2=levels.get('target2', 0),
            recommended_shares=position_sizing.get('shares', 0),
            risk_amount=position_sizing.get('risk_amount', 0),
            bullish_factors=list(set(bullish)),
            bearish_factors=list(set(bearish)),
            risks=list(set(risks)),
            warnings=list(set(warnings))
        )

        return analysis

    def _create_no_trade_analysis(
        self,
        timestamp: datetime,
        symbol: str,
        data_health: DataHealthStatus,
        reason: str
    ) -> IntegratedAnalysis:
        """Create an analysis result when trading is not possible."""
        return IntegratedAnalysis(
            timestamp=timestamp,
            symbol=symbol,
            data_health=data_health,
            quant_conviction=0,
            quant_signal='NO_DATA',
            model_votes={},
            technical_levels={},
            intelligence_result=None,
            ai_confidence='uncertain',
            ai_position_modifier=0,
            portfolio_status=self.position_manager.get_portfolio_status(),
            can_take_position=False,
            max_position_size=0,
            max_position_value=0,
            final_decision=TradingDecision.AVOID,
            final_conviction=0,
            final_position_modifier=0,
            risks=[reason],
            warnings=data_health.warnings
        )

    def get_analysis_summary(self, analysis: IntegratedAnalysis) -> str:
        """Generate a human-readable summary of the analysis."""
        lines = []
        lines.append("=" * 70)
        lines.append(f"INTELLIGENT ANALYSIS: {analysis.symbol}")
        lines.append(f"Generated: {analysis.timestamp.strftime('%Y-%m-%d %H:%M')}")
        lines.append("=" * 70)

        # Decision
        decision_color = {
            TradingDecision.STRONG_BUY: "green",
            TradingDecision.BUY: "green",
            TradingDecision.HOLD: "yellow",
            TradingDecision.AVOID: "red",
            TradingDecision.SELL: "red"
        }.get(analysis.final_decision, "white")

        lines.append(f"\n[bold {decision_color}]DECISION: {analysis.final_decision.value}[/bold {decision_color}]")
        lines.append(f"Conviction: {analysis.final_conviction}/100")
        lines.append(f"Position Size: {analysis.final_position_modifier*100:.0f}% of normal")

        # Data Health
        lines.append(f"\n[DATA HEALTH]")
        lines.append(f"  Overall: {analysis.data_health.overall_quality}")
        lines.append(f"  Can Trade: {'YES' if analysis.data_health.can_trade else 'NO'}")
        if analysis.data_health.warnings:
            for w in analysis.data_health.warnings[:3]:
                lines.append(f"  ! {w}")

        # Quantitative
        lines.append(f"\n[QUANTITATIVE ANALYSIS]")
        lines.append(f"  Signal: {analysis.quant_signal}")
        lines.append(f"  Conviction: {analysis.quant_conviction}/100")
        lines.append(f"  Models: {sum(analysis.model_votes.values())}/{len(analysis.model_votes)} bullish")

        # Intelligence
        if analysis.intelligence_result:
            lines.append(f"\n[AI INTELLIGENCE]")
            lines.append(f"  Confidence: {analysis.ai_confidence.upper()}")
            lines.append(f"  Modifier: {analysis.ai_position_modifier*100:.0f}%")
            if analysis.intelligence_result.recommendation:
                lines.append(f"  Rec: {analysis.intelligence_result.recommendation}")

        # Trade Setup (if actionable)
        if analysis.final_decision in [TradingDecision.STRONG_BUY, TradingDecision.BUY]:
            lines.append(f"\n[TRADE SETUP]")
            lines.append(f"  Entry: ₹{analysis.entry_price:,.2f}")
            lines.append(f"  Stop: ₹{analysis.stop_loss:,.2f}")
            lines.append(f"  Target 1: ₹{analysis.target1:,.2f}")
            lines.append(f"  Target 2: ₹{analysis.target2:,.2f}")
            lines.append(f"  Shares: {analysis.recommended_shares}")
            lines.append(f"  Risk: ₹{analysis.risk_amount:,.2f}")

        # Portfolio
        lines.append(f"\n[PORTFOLIO]")
        lines.append(f"  Heat: {analysis.portfolio_status.current_heat:.1f}%")
        lines.append(f"  Available: {analysis.portfolio_status.heat_available:.1f}%")
        lines.append(f"  Positions: {analysis.portfolio_status.total_positions}")

        # Factors
        if analysis.bullish_factors:
            lines.append(f"\n[BULLISH]")
            for f in analysis.bullish_factors[:5]:
                lines.append(f"  + {f}")

        if analysis.bearish_factors:
            lines.append(f"\n[BEARISH]")
            for f in analysis.bearish_factors[:5]:
                lines.append(f"  - {f}")

        if analysis.risks:
            lines.append(f"\n[RISKS]")
            for r in analysis.risks[:5]:
                lines.append(f"  ! {r}")

        lines.append("=" * 70)
        return "\n".join(lines)

    def display_analysis(self, analysis: IntegratedAnalysis):
        """Display analysis using Rich console."""
        summary = self.get_analysis_summary(analysis)
        console.print(Panel(summary, title=f"Analysis: {analysis.symbol}"))


# Singleton instance
_intelligent_orchestrator: Optional[IntelligentOrchestrator] = None


def get_intelligent_orchestrator(capital: float = 1_000_000) -> IntelligentOrchestrator:
    """Get intelligent orchestrator singleton."""
    global _intelligent_orchestrator
    if _intelligent_orchestrator is None:
        _intelligent_orchestrator = IntelligentOrchestrator(capital=capital)
    return _intelligent_orchestrator
