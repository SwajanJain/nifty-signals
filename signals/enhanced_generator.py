"""Enhanced Signal Generator - Integrates all advanced components."""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
from rich.console import Console

from data.fetcher import StockDataFetcher
from indicators.technical import TechnicalIndicators
from indicators.price_action import PriceActionAnalyzer
from indicators.candlestick import CandlestickPatterns
from indicators.chart_patterns import ChartPatterns
from indicators.fibonacci import FibonacciAnalysis
from indicators.divergence import DivergenceDetector
from indicators.trend_strength import TrendStrength
from indicators.vcp import VCPScanner
from indicators.ttm_squeeze import TTMSqueeze
from indicators.narrow_range import NarrowRangeDetector
from indicators.cpr import CPRCalculator
from indicators.bb_patterns import BBPatternDetector
from indicators.market_regime import RegimeDetector, MarketRegime
from indicators.multi_timeframe import MultiTimeframeAnalyzer
from indicators.sector_strength import SectorStrengthAnalyzer, get_sector_for_stock
from risk.position_sizing import PositionSizer, PortfolioRiskManager, TradeSetup
from .scorer import SignalScorer, StockSignal, SignalType


console = Console()


@dataclass
class EnhancedSignal(StockSignal):
    """Enhanced signal with additional context."""
    # Market context
    market_regime: str = ""
    regime_multiplier: float = 1.0
    should_trade_regime: bool = True

    # Multi-timeframe
    weekly_trend: str = ""
    daily_trend: str = ""
    mtf_alignment: int = 0
    mtf_recommendation: str = ""

    # Sector context
    sector: str = ""
    sector_rank: int = 0
    sector_strength: str = ""
    sector_bonus: int = 0
    is_sector_leader: bool = False

    # Position sizing
    trade_setup: Optional[TradeSetup] = None
    position_approved: bool = True
    position_issues: List[str] = field(default_factory=list)

    # Swing pattern signals
    vcp_signals: Dict = field(default_factory=dict)
    squeeze_signals: Dict = field(default_factory=dict)
    narrow_range_signals: Dict = field(default_factory=dict)
    cpr_signals: Dict = field(default_factory=dict)
    bb_pattern_signals: Dict = field(default_factory=dict)

    # Final recommendation
    final_recommendation: str = ""
    confidence: str = ""
    skip_reasons: List[str] = field(default_factory=list)


class EnhancedSignalGenerator:
    """
    Enhanced signal generator that combines:
    - Technical indicators
    - Price action
    - Market regime
    - Multi-timeframe alignment
    - Sector strength
    - Position sizing
    """

    def __init__(
        self,
        capital: float = 500000,
        risk_per_trade: float = 0.01,
        max_portfolio_risk: float = 0.06
    ):
        """
        Initialize enhanced generator.

        Args:
            capital: Trading capital
            risk_per_trade: Risk per trade (fraction)
            max_portfolio_risk: Maximum portfolio risk
        """
        self.capital = capital
        self.fetcher = StockDataFetcher()
        self.scorer = SignalScorer()

        # Advanced components
        self.regime_detector = None
        self.sector_analyzer = None
        self.position_sizer = PositionSizer(
            capital=capital,
            risk_per_trade=risk_per_trade
        )
        self.portfolio_manager = PortfolioRiskManager(
            capital=capital,
            max_portfolio_risk=max_portfolio_risk
        )

        # Cache for market data
        self._market_regime = None
        self._sector_analysis = None

    def _initialize_market_context(self):
        """Initialize market regime and sector analysis."""
        if self._market_regime is None:
            console.print("[yellow]Analyzing market regime...[/yellow]")
            try:
                self.regime_detector = RegimeDetector()
                self._market_regime = self.regime_detector.detect_regime()
            except Exception as e:
                console.print(f"[red]Error detecting regime: {e}[/red]")
                self._market_regime = {
                    'regime': MarketRegime.NEUTRAL,
                    'regime_name': 'NEUTRAL',
                    'position_size_multiplier': 0.5,
                    'should_trade': True
                }

        if self._sector_analysis is None:
            console.print("[yellow]Analyzing sector strength...[/yellow]")
            try:
                self.sector_analyzer = SectorStrengthAnalyzer()
                self.sector_analyzer.fetch_sector_data()
                self._sector_analysis = self.sector_analyzer.analyze_sectors()
            except Exception as e:
                console.print(f"[red]Error analyzing sectors: {e}[/red]")
                self._sector_analysis = []

    def analyze_stock_enhanced(self, symbol: str) -> Optional[EnhancedSignal]:
        """
        Perform enhanced analysis on a single stock.

        Args:
            symbol: Stock symbol

        Returns:
            EnhancedSignal object or None
        """
        # Initialize market context if not done
        self._initialize_market_context()

        # Fetch daily data
        daily_df = self.fetcher.fetch_stock_data(symbol, "daily")
        if daily_df is None or len(daily_df) < 50:
            return None

        # Fetch weekly data for MTF
        weekly_df = self.fetcher.fetch_stock_data(symbol, "weekly")

        try:
            # Standard technical analysis
            tech = TechnicalIndicators(daily_df)
            price_action = PriceActionAnalyzer(daily_df)
            candlestick = CandlestickPatterns(daily_df)
            chart_patterns = ChartPatterns(daily_df)
            fibonacci = FibonacciAnalysis(daily_df)
            divergence = DivergenceDetector(daily_df)
            trend_strength = TrendStrength(daily_df)

            # Swing pattern indicators
            vcp_scanner = VCPScanner(daily_df)
            ttm_squeeze = TTMSqueeze(daily_df)
            narrow_range = NarrowRangeDetector(daily_df)
            cpr_calc = CPRCalculator(daily_df)
            bb_patterns = BBPatternDetector(daily_df)

            # Get all signals
            tech_signals = tech.get_all_signals()
            pa_signals = price_action.get_all_signals()
            candle_signals = candlestick.get_all_patterns()
            chart_signals = chart_patterns.get_all_patterns()
            fib_signals = fibonacci.get_all_signals()
            div_signals = divergence.get_all_divergences()
            trend_signals = trend_strength.get_all_signals()
            vcp_signals = vcp_scanner.get_all_signals()
            squeeze_signals = ttm_squeeze.get_all_signals()
            nr_signals = narrow_range.get_all_signals()
            cpr_signals = cpr_calc.get_all_signals()
            bb_pat_signals = bb_patterns.get_all_signals()

            # Base score
            base_score = (
                tech_signals['total_score'] +
                pa_signals['total_score'] +
                candle_signals['total_score'] +
                chart_signals['total_score'] +
                fib_signals['total_score'] +
                div_signals['total_score'] +
                trend_signals['total_score'] +
                vcp_signals['total_score'] +
                squeeze_signals['total_score'] +
                nr_signals['total_score'] +
                cpr_signals['total_score'] +
                bb_pat_signals['total_score']
            )

            # Multi-timeframe analysis
            mtf_data = self._analyze_mtf(daily_df, weekly_df)

            # Sector analysis
            sector_data = self._analyze_sector(symbol)

            # Adjust score based on context
            adjusted_score = base_score + mtf_data.get('score_bonus', 0) + sector_data.get('sector_bonus', 0)

            # Get stock info
            stock_info = self.fetcher.get_stock_info(symbol)
            current_price = daily_df['close'].iloc[-1]

            # Create trade setup with position sizing
            trade_setup = None
            position_approved = True
            position_issues = []

            if adjusted_score >= 3:  # Only calculate for potential buys
                regime_multiplier = self._market_regime.get('position_size_multiplier', 1.0)
                trade_setup = self.position_sizer.create_trade_setup(
                    symbol=symbol,
                    df=daily_df,
                    regime_multiplier=regime_multiplier
                )

                # Check portfolio constraints
                portfolio_check = self.portfolio_manager.can_take_trade({
                    'symbol': symbol,
                    'risk_amount': trade_setup.risk_amount,
                    'position_value': trade_setup.position_value,
                    'sector': sector_data.get('sector', 'Unknown')
                })
                position_approved = portfolio_check['approved']
                position_issues = portfolio_check.get('issues', []) + portfolio_check.get('warnings', [])

            # Determine final recommendation
            final_rec, confidence, skip_reasons = self._get_final_recommendation(
                score=adjusted_score,
                mtf_data=mtf_data,
                sector_data=sector_data,
                position_approved=position_approved
            )

            # Create enhanced signal
            signal = EnhancedSignal(
                symbol=symbol,
                name=stock_info['name'],
                price=current_price,
                signal_type=self.scorer.classify_signal(adjusted_score),
                total_score=adjusted_score,
                technical_score=tech_signals['total_score'],
                price_action_score=pa_signals['total_score'],
                technical_signals=tech_signals,
                price_action_signals=pa_signals,
                candlestick_signals=candle_signals,
                chart_pattern_signals=chart_signals,
                fibonacci_signals=fib_signals,
                divergence_signals=div_signals,
                trend_strength_signals=trend_signals,

                # Market context
                market_regime=self._market_regime.get('regime_name', 'NEUTRAL'),
                regime_multiplier=self._market_regime.get('position_size_multiplier', 1.0),
                should_trade_regime=self._market_regime.get('should_trade', True),

                # MTF
                weekly_trend=mtf_data.get('weekly_trend', 'UNKNOWN'),
                daily_trend=mtf_data.get('daily_trend', 'UNKNOWN'),
                mtf_alignment=mtf_data.get('alignment_score', 0),
                mtf_recommendation=mtf_data.get('recommendation', 'NEUTRAL'),

                # Sector
                sector=sector_data.get('sector', 'Unknown'),
                sector_rank=sector_data.get('sector_rank', 0),
                sector_strength=sector_data.get('sector_strength', 'UNKNOWN'),
                sector_bonus=sector_data.get('sector_bonus', 0),
                is_sector_leader=sector_data.get('is_sector_leader', False),

                # Swing patterns
                vcp_signals=vcp_signals,
                squeeze_signals=squeeze_signals,
                narrow_range_signals=nr_signals,
                cpr_signals=cpr_signals,
                bb_pattern_signals=bb_pat_signals,

                # Position
                trade_setup=trade_setup,
                position_approved=position_approved,
                position_issues=position_issues,

                # Final
                final_recommendation=final_rec,
                confidence=confidence,
                skip_reasons=skip_reasons
            )

            return signal

        except Exception as e:
            console.print(f"[red]Error analyzing {symbol}: {e}[/red]")
            return None

    def _analyze_mtf(self, daily_df: pd.DataFrame, weekly_df: Optional[pd.DataFrame]) -> Dict:
        """Analyze multi-timeframe alignment."""
        if weekly_df is None or len(weekly_df) < 50:
            return {
                'weekly_trend': 'UNKNOWN',
                'daily_trend': 'UNKNOWN',
                'alignment_score': 0,
                'recommendation': 'NEUTRAL',
                'score_bonus': 0
            }

        try:
            mtf = MultiTimeframeAnalyzer(daily_df, weekly_df)
            alignment = mtf.get_alignment()

            # Score bonus based on alignment
            alignment_score = alignment.get('alignment_score', 0)
            if alignment_score >= 2:
                score_bonus = 3
            elif alignment_score == 1:
                score_bonus = 1
            elif alignment_score == 0:
                score_bonus = 0
            elif alignment_score == -1:
                score_bonus = -2
            else:
                score_bonus = -4

            return {
                'weekly_trend': alignment['weekly']['trend_name'],
                'daily_trend': alignment['daily']['trend_name'],
                'alignment_score': alignment_score,
                'recommendation': alignment['recommendation'],
                'should_take_long': alignment['should_take_long'],
                'confidence': alignment['confidence'],
                'score_bonus': score_bonus
            }
        except Exception as e:
            console.print(f"[yellow]MTF analysis error: {e}[/yellow]")
            return {
                'weekly_trend': 'UNKNOWN',
                'daily_trend': 'UNKNOWN',
                'alignment_score': 0,
                'recommendation': 'NEUTRAL',
                'score_bonus': 0
            }

    def _analyze_sector(self, symbol: str) -> Dict:
        """Get sector analysis for a stock."""
        sector = get_sector_for_stock(symbol)
        if not sector or not self._sector_analysis:
            return {
                'sector': 'Unknown',
                'sector_rank': 0,
                'sector_strength': 'UNKNOWN',
                'sector_bonus': 0,
                'is_sector_leader': False
            }

        # Find sector in analysis
        for analysis in self._sector_analysis:
            if analysis.sector == sector:
                # Calculate bonus
                if analysis.strength.value == "STRONG":
                    bonus = 2
                elif analysis.strength.value == "MODERATE":
                    bonus = 1
                elif analysis.strength.value == "WEAK":
                    bonus = 0
                else:
                    bonus = -1

                # Extra bonus for sector leader
                is_leader = symbol in analysis.top_stocks
                if is_leader:
                    bonus += 1

                return {
                    'sector': sector,
                    'sector_rank': analysis.rank,
                    'sector_strength': analysis.strength.value,
                    'sector_bonus': bonus,
                    'is_sector_leader': is_leader,
                    'is_sector_laggard': symbol in analysis.lagging_stocks
                }

        return {
            'sector': sector,
            'sector_rank': 0,
            'sector_strength': 'UNKNOWN',
            'sector_bonus': 0,
            'is_sector_leader': False
        }

    def _get_final_recommendation(
        self,
        score: int,
        mtf_data: Dict,
        sector_data: Dict,
        position_approved: bool
    ) -> tuple:
        """
        Get final recommendation considering all factors.

        Returns:
            Tuple of (recommendation, confidence, skip_reasons)
        """
        skip_reasons = []

        # Check regime
        if not self._market_regime.get('should_trade', True):
            skip_reasons.append(f"Market regime: {self._market_regime.get('regime_name')}")

        # Check MTF
        if not mtf_data.get('should_take_long', True) and score > 0:
            skip_reasons.append(f"MTF not aligned: {mtf_data.get('recommendation')}")

        # Check sector
        if sector_data.get('sector_strength') == 'VERY_WEAK':
            skip_reasons.append(f"Weak sector: {sector_data.get('sector')} (Rank {sector_data.get('sector_rank')})")

        # Check position
        if not position_approved:
            skip_reasons.append("Position exceeds portfolio limits")

        # Determine recommendation
        if skip_reasons:
            recommendation = "SKIP"
            confidence = "LOW"
        elif score >= 7:
            recommendation = "STRONG_BUY"
            confidence = "HIGH"
        elif score >= 5:
            recommendation = "BUY"
            confidence = "MEDIUM" if mtf_data.get('alignment_score', 0) >= 1 else "LOW"
        elif score >= 3:
            recommendation = "WEAK_BUY"
            confidence = "LOW"
        elif score <= -5:
            recommendation = "STRONG_SELL"
            confidence = "HIGH"
        elif score <= -3:
            recommendation = "SELL"
            confidence = "MEDIUM"
        else:
            recommendation = "HOLD"
            confidence = "MEDIUM"

        return recommendation, confidence, skip_reasons

    def scan_enhanced(self, symbols: Optional[List[str]] = None) -> List[EnhancedSignal]:
        """
        Scan stocks with enhanced analysis.

        Args:
            symbols: Optional list of symbols

        Returns:
            List of EnhancedSignal sorted by score
        """
        if symbols is None:
            symbols = [s['symbol'] for s in self.fetcher.stocks]

        signals = []
        total = len(symbols)

        with console.status("[bold green]Enhanced scanning...") as status:
            for i, symbol in enumerate(symbols, 1):
                status.update(f"[bold green]Analyzing {symbol} ({i}/{total})...")
                signal = self.analyze_stock_enhanced(symbol)
                if signal:
                    signals.append(signal)

        # Sort by score
        signals.sort(key=lambda x: x.total_score, reverse=True)

        return signals

    def get_actionable_signals(self, signals: List[EnhancedSignal]) -> List[EnhancedSignal]:
        """Get only actionable buy signals (no skip reasons)."""
        return [
            s for s in signals
            if s.final_recommendation in ("STRONG_BUY", "BUY")
            and not s.skip_reasons
        ]

    def get_market_summary(self) -> Dict:
        """Get current market summary."""
        self._initialize_market_context()

        return {
            'regime': self._market_regime,
            'should_trade': self._market_regime.get('should_trade', True),
            'position_multiplier': self._market_regime.get('position_size_multiplier', 1.0),
            'top_sectors': [s.sector for s in self._sector_analysis[:3]] if self._sector_analysis else [],
            'avoid_sectors': [s.sector for s in self._sector_analysis[-3:]] if self._sector_analysis else [],
            'portfolio_status': self.portfolio_manager.get_portfolio_summary()
        }


def print_enhanced_signal(signal: EnhancedSignal) -> str:
    """Generate printable enhanced signal report."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"ENHANCED ANALYSIS: {signal.symbol} - {signal.name}")
    lines.append("=" * 70)

    # Price & Score
    lines.append(f"\nPrice: Rs {signal.price:.2f}")
    lines.append(f"Signal: {signal.final_recommendation} (Score: {signal.total_score:+d})")
    lines.append(f"Confidence: {signal.confidence}")

    # Skip reasons
    if signal.skip_reasons:
        lines.append(f"\n[SKIP REASONS]")
        for reason in signal.skip_reasons:
            lines.append(f"  - {reason}")

    # Market Context
    lines.append(f"\n[MARKET CONTEXT]")
    lines.append(f"Regime: {signal.market_regime} (Size: {signal.regime_multiplier:.0%})")
    lines.append(f"Weekly: {signal.weekly_trend} | Daily: {signal.daily_trend}")
    lines.append(f"MTF Alignment: {signal.mtf_alignment} ({signal.mtf_recommendation})")

    # Sector
    lines.append(f"\n[SECTOR]")
    lines.append(f"Sector: {signal.sector} (Rank #{signal.sector_rank})")
    lines.append(f"Strength: {signal.sector_strength} (Bonus: {signal.sector_bonus:+d})")
    if signal.is_sector_leader:
        lines.append(f"* SECTOR LEADER *")

    # Trade Setup
    if signal.trade_setup:
        ts = signal.trade_setup
        lines.append(f"\n[TRADE SETUP]")
        lines.append(f"Entry: Rs {ts.entry_price:.2f}")
        lines.append(f"Stop Loss: Rs {ts.stop_loss:.2f} (ATR x{ts.atr_multiple_sl})")
        lines.append(f"Target 1: Rs {ts.target_1:.2f}")
        lines.append(f"Target 2: Rs {ts.target_2:.2f}")
        lines.append(f"Position: {ts.position_size} shares (Rs {ts.position_value:,.0f})")
        lines.append(f"Risk: Rs {ts.risk_amount:,.0f} ({ts.risk_percent:.2f}%)")
        lines.append(f"R:R Ratio: 1:{ts.reward_risk_ratio:.1f}")

    # Position Issues
    if signal.position_issues:
        lines.append(f"\n[POSITION WARNINGS]")
        for issue in signal.position_issues:
            lines.append(f"  ! {issue}")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)
