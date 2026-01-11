"""Sector Relative Strength Analysis - Pick stocks from strongest sectors."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
import yfinance as yf


# Nifty 100 stocks organized by sector
SECTOR_MAPPING = {
    "IT": [
        "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "MPHASIS",
        "COFORGE", "PERSISTENT", "LTTS"
    ],
    "Banking": [
        "HDFCBANK", "ICICIBANK", "KOTAKBANK", "SBIN", "AXISBANK",
        "INDUSINDBK", "BANKBARODA", "PNB", "FEDERALBNK", "IDFCFIRSTB"
    ],
    "Finance": [
        "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "SBICARD", "MUTHOOTFIN",
        "LICHSGFIN", "M&MFIN", "SHRIRAMFIN", "PFC", "RECLTD"
    ],
    "Pharma": [
        "SUNPHARMA", "DRREDDY", "DIVISLAB", "CIPLA", "APOLLOHOSP",
        "LUPIN", "TORNTPHARM", "AUROPHARMA", "BIOCON", "ALKEM"
    ],
    "Auto": [
        "MARUTI", "TATAMTRDVR", "M&M", "BAJAJ-AUTO", "HEROMOTOCO",
        "EICHERMOT", "TVSMOTOR", "ASHOKLEY", "BALKRISIND", "MRF"
    ],
    "Energy": [
        "RELIANCE", "ONGC", "NTPC", "POWERGRID", "ADANIGREEN",
        "ADANIENSOL", "TATAPOWER", "COALINDIA", "IOC", "BPCL"
    ],
    "Metals": [
        "TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "NMDC",
        "JINDALSTEL", "SAIL", "NATIONALUM", "HINDZINC", "APLAPOLLO"
    ],
    "FMCG": [
        "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR",
        "MARICO", "GODREJCP", "COLPAL", "TATACONSUM", "VBL"
    ],
    "Infra": [
        "LT", "ADANIPORTS", "DLF", "GODREJPROP", "OBEROIRLTY",
        "BHARTIARTL", "INDIGO", "LODHA", "IRCTC", "PAYTM"
    ],
    "Capital Goods": [
        "SIEMENS", "ABB", "HAVELLS", "BHEL", "BEL",
        "CUMMINSIND", "THERMAX", "VOLTAS", "BLUESTARCO", "AIAENG"
    ],
    "Consumer": [
        "TITAN", "ASIANPAINT", "PIDILITIND", "PAGEIND", "JUBLFOOD",
        "TRENT", "DIXON", "VBL", "DMART", "NYKAA"
    ],
    "Insurance": [
        "SBILIFE", "HDFCLIFE", "ICICIGI", "ICICIPRULI", "LICI"
    ],
    "Cement": [
        "ULTRACEMCO", "GRASIM", "SHREECEM", "AMBUJACEM", "ACC",
        "DALBHARAT", "RAMCOCEM", "JKCEMENT", "INDIACEM"
    ]
}


class SectorStrength(Enum):
    """Sector strength classification."""
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    VERY_WEAK = "VERY_WEAK"


@dataclass
class SectorAnalysis:
    """Sector analysis result."""
    sector: str
    rank: int
    strength: SectorStrength
    weekly_return: float
    monthly_return: float
    rs_score: float  # Relative strength score
    momentum_score: float
    stocks_above_50ema: int
    total_stocks: int
    top_stocks: List[str]
    lagging_stocks: List[str]


class SectorStrengthAnalyzer:
    """Analyze sector relative strength to identify leading sectors."""

    def __init__(self, lookback_weekly: int = 4, lookback_monthly: int = 12):
        """
        Initialize sector analyzer.

        Args:
            lookback_weekly: Weeks for short-term performance
            lookback_monthly: Weeks for long-term performance
        """
        self.lookback_weekly = lookback_weekly
        self.lookback_monthly = lookback_monthly
        self.sector_data: Dict[str, pd.DataFrame] = {}
        self.stock_data: Dict[str, pd.DataFrame] = {}

    def _get_nse_symbol(self, symbol: str) -> str:
        """Convert to NSE symbol format."""
        return f"{symbol}.NS"

    def fetch_sector_data(self, sectors: Optional[List[str]] = None):
        """
        Fetch data for all stocks in specified sectors.

        Args:
            sectors: List of sectors to analyze (None = all)
        """
        if sectors is None:
            sectors = list(SECTOR_MAPPING.keys())

        for sector in sectors:
            stocks = SECTOR_MAPPING.get(sector, [])
            for symbol in stocks:
                try:
                    ticker = yf.Ticker(self._get_nse_symbol(symbol))
                    data = ticker.history(period="6mo")
                    if len(data) > 0:
                        data.columns = [c.lower() for c in data.columns]
                        self.stock_data[symbol] = data
                except Exception as e:
                    print(f"Error fetching {symbol}: {e}")

    def calculate_stock_rs(self, symbol: str, benchmark_data: pd.DataFrame) -> Dict:
        """
        Calculate relative strength for a stock vs benchmark (Nifty 50).

        Args:
            symbol: Stock symbol
            benchmark_data: Nifty 50 data

        Returns:
            Dict with RS metrics
        """
        if symbol not in self.stock_data:
            return {'rs_score': 0, 'momentum': 0}

        stock = self.stock_data[symbol]

        # Align dates
        common_dates = stock.index.intersection(benchmark_data.index)
        if len(common_dates) < 20:
            return {'rs_score': 0, 'momentum': 0}

        stock_aligned = stock.loc[common_dates]
        bench_aligned = benchmark_data.loc[common_dates]

        # RS Ratio = Stock Price / Benchmark Price
        rs_ratio = stock_aligned['close'] / bench_aligned['close']

        # RS Score = Current RS / 50-day MA of RS
        rs_ma = rs_ratio.rolling(50).mean()
        current_rs = rs_ratio.iloc[-1] / rs_ma.iloc[-1] if rs_ma.iloc[-1] > 0 else 1

        # Momentum = RS change over 20 days
        if len(rs_ratio) >= 20:
            rs_momentum = (rs_ratio.iloc[-1] - rs_ratio.iloc[-20]) / rs_ratio.iloc[-20] * 100
        else:
            rs_momentum = 0

        # Check if stock is above 50 EMA
        if len(stock) >= 50:
            ema_50 = stock['close'].ewm(span=50).mean().iloc[-1]
            above_ema = stock['close'].iloc[-1] > ema_50
        else:
            above_ema = False

        return {
            'rs_score': current_rs,
            'momentum': rs_momentum,
            'above_50ema': above_ema,
            'weekly_return': self._calculate_return(stock, 5),
            'monthly_return': self._calculate_return(stock, 22)
        }

    def _calculate_return(self, df: pd.DataFrame, days: int) -> float:
        """Calculate return over specified days."""
        if len(df) < days:
            return 0
        return (df['close'].iloc[-1] - df['close'].iloc[-days]) / df['close'].iloc[-days] * 100

    def analyze_sectors(self) -> List[SectorAnalysis]:
        """
        Analyze all sectors and rank by relative strength.

        Returns:
            List of SectorAnalysis sorted by strength (strongest first)
        """
        # Fetch Nifty 50 as benchmark
        try:
            nifty = yf.Ticker("^NSEI")
            benchmark_data = nifty.history(period="6mo")
            benchmark_data.columns = [c.lower() for c in benchmark_data.columns]
        except Exception as e:
            print(f"Error fetching Nifty: {e}")
            return []

        sector_results = []

        for sector, stocks in SECTOR_MAPPING.items():
            sector_rs_scores = []
            sector_momentum = []
            stocks_above_ema = 0
            stock_performances = []

            for symbol in stocks:
                if symbol not in self.stock_data:
                    continue

                rs_data = self.calculate_stock_rs(symbol, benchmark_data)
                sector_rs_scores.append(rs_data['rs_score'])
                sector_momentum.append(rs_data['momentum'])

                if rs_data['above_50ema']:
                    stocks_above_ema += 1

                stock_performances.append({
                    'symbol': symbol,
                    'rs_score': rs_data['rs_score'],
                    'weekly': rs_data['weekly_return'],
                    'monthly': rs_data['monthly_return']
                })

            if not sector_rs_scores:
                continue

            # Calculate sector aggregates
            avg_rs = np.mean(sector_rs_scores)
            avg_momentum = np.mean(sector_momentum)

            # Calculate sector return
            sector_weekly = np.mean([s['weekly'] for s in stock_performances])
            sector_monthly = np.mean([s['monthly'] for s in stock_performances])

            # Sort stocks by performance
            stock_performances.sort(key=lambda x: x['rs_score'], reverse=True)
            top_stocks = [s['symbol'] for s in stock_performances[:3]]
            lagging_stocks = [s['symbol'] for s in stock_performances[-3:]]

            # Determine sector strength
            if avg_rs > 1.05 and avg_momentum > 5:
                strength = SectorStrength.STRONG
            elif avg_rs > 1.0 and avg_momentum > 0:
                strength = SectorStrength.MODERATE
            elif avg_rs > 0.95:
                strength = SectorStrength.WEAK
            else:
                strength = SectorStrength.VERY_WEAK

            sector_results.append(SectorAnalysis(
                sector=sector,
                rank=0,  # Will be set after sorting
                strength=strength,
                weekly_return=sector_weekly,
                monthly_return=sector_monthly,
                rs_score=avg_rs,
                momentum_score=avg_momentum,
                stocks_above_50ema=stocks_above_ema,
                total_stocks=len(stocks),
                top_stocks=top_stocks,
                lagging_stocks=lagging_stocks
            ))

        # Sort by RS score and assign ranks
        sector_results.sort(key=lambda x: x.rs_score, reverse=True)
        for i, result in enumerate(sector_results):
            result.rank = i + 1

        return sector_results

    def get_sector_rotation_signal(self, sector_analysis: List[SectorAnalysis]) -> Dict:
        """
        Generate sector rotation signals.

        Args:
            sector_analysis: List of SectorAnalysis results

        Returns:
            Dict with rotation signals and recommendations
        """
        if not sector_analysis:
            return {'signal': 'NO_DATA', 'recommendations': []}

        strong_sectors = [s for s in sector_analysis if s.strength == SectorStrength.STRONG]
        weak_sectors = [s for s in sector_analysis if s.strength == SectorStrength.VERY_WEAK]

        recommendations = []

        # Buy signals - stocks from strong sectors
        for sector in strong_sectors[:3]:
            for stock in sector.top_stocks[:2]:
                recommendations.append({
                    'action': 'BUY',
                    'symbol': stock,
                    'sector': sector.sector,
                    'reason': f"Leading stock in strong sector ({sector.sector})",
                    'sector_rank': sector.rank,
                    'sector_rs': sector.rs_score
                })

        # Avoid signals - stocks from weak sectors
        for sector in weak_sectors:
            for stock in sector.lagging_stocks:
                recommendations.append({
                    'action': 'AVOID',
                    'symbol': stock,
                    'sector': sector.sector,
                    'reason': f"Lagging stock in weak sector ({sector.sector})",
                    'sector_rank': sector.rank
                })

        # Determine overall rotation signal
        avg_strong = len(strong_sectors)
        avg_weak = len(weak_sectors)

        if avg_strong > 4:
            signal = "BULLISH_ROTATION"
        elif avg_weak > 4:
            signal = "BEARISH_ROTATION"
        else:
            signal = "MIXED_ROTATION"

        return {
            'signal': signal,
            'strong_sectors': [s.sector for s in strong_sectors],
            'weak_sectors': [s.sector for s in weak_sectors],
            'recommendations': recommendations,
            'best_sector': sector_analysis[0].sector if sector_analysis else None,
            'worst_sector': sector_analysis[-1].sector if sector_analysis else None
        }

    def get_stock_sector_score(self, symbol: str) -> Dict:
        """
        Get sector-adjusted score for a stock.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with sector context for the stock
        """
        # Find stock's sector
        stock_sector = None
        for sector, stocks in SECTOR_MAPPING.items():
            if symbol in stocks:
                stock_sector = sector
                break

        if not stock_sector:
            return {
                'sector': 'Unknown',
                'sector_rank': 0,
                'sector_bonus': 0,
                'trade_recommendation': 'NEUTRAL'
            }

        # Get sector analysis
        sector_analysis = self.analyze_sectors()

        for analysis in sector_analysis:
            if analysis.sector == stock_sector:
                # Calculate bonus based on sector strength
                if analysis.strength == SectorStrength.STRONG:
                    bonus = 2
                    recommendation = "PREFER"
                elif analysis.strength == SectorStrength.MODERATE:
                    bonus = 1
                    recommendation = "OKAY"
                elif analysis.strength == SectorStrength.WEAK:
                    bonus = 0
                    recommendation = "CAUTION"
                else:
                    bonus = -1
                    recommendation = "AVOID"

                # Extra bonus if stock is in top performers
                if symbol in analysis.top_stocks:
                    bonus += 1
                    recommendation = "STRONG_PREFER" if bonus > 2 else recommendation

                return {
                    'sector': stock_sector,
                    'sector_rank': analysis.rank,
                    'sector_strength': analysis.strength.value,
                    'sector_bonus': bonus,
                    'trade_recommendation': recommendation,
                    'is_sector_leader': symbol in analysis.top_stocks,
                    'is_sector_laggard': symbol in analysis.lagging_stocks
                }

        return {
            'sector': stock_sector,
            'sector_rank': 0,
            'sector_bonus': 0,
            'trade_recommendation': 'NEUTRAL'
        }


def get_sector_for_stock(symbol: str) -> Optional[str]:
    """Get sector for a given stock symbol."""
    for sector, stocks in SECTOR_MAPPING.items():
        if symbol in stocks:
            return sector
    return None


def print_sector_report(sector_analysis: List[SectorAnalysis]) -> str:
    """Generate printable sector report."""
    lines = []
    lines.append("=" * 70)
    lines.append("SECTOR RELATIVE STRENGTH ANALYSIS")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"{'Rank':<5}{'Sector':<15}{'RS':<8}{'Mom':<8}{'1W %':<8}{'1M %':<8}{'Strength':<12}")
    lines.append("-" * 70)

    for s in sector_analysis:
        lines.append(
            f"{s.rank:<5}{s.sector:<15}{s.rs_score:.3f}   "
            f"{s.momentum_score:+.1f}%   {s.weekly_return:+.1f}%   "
            f"{s.monthly_return:+.1f}%   {s.strength.value:<12}"
        )

    lines.append("")
    lines.append("TOP SECTORS TO FOCUS:")
    for s in sector_analysis[:3]:
        lines.append(f"  {s.sector}: {', '.join(s.top_stocks)}")

    lines.append("")
    lines.append("SECTORS TO AVOID:")
    for s in sector_analysis[-3:]:
        lines.append(f"  {s.sector}: {', '.join(s.lagging_stocks)}")

    lines.append("=" * 70)

    return "\n".join(lines)
