"""Market Regime Detection - Bull/Bear/Range/Crash identification."""

from typing import Dict, Tuple
from enum import Enum
import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta


class MarketRegime(Enum):
    """Market regime classification."""
    STRONG_BULL = "STRONG_BULL"
    BULL = "BULL"
    NEUTRAL = "NEUTRAL"
    BEAR = "BEAR"
    STRONG_BEAR = "STRONG_BEAR"
    CRASH = "CRASH"


class RegimeDetector:
    """Detect current market regime using multiple factors."""

    def __init__(self):
        self.nifty_data = None
        self.vix_data = None
        self._fetch_data()

    def _fetch_data(self):
        """Fetch Nifty 50 and India VIX data."""
        try:
            # Nifty 50
            nifty = yf.Ticker("^NSEI")
            self.nifty_data = nifty.history(period="1y")
            self.nifty_data.columns = [c.lower() for c in self.nifty_data.columns]

            # India VIX
            vix = yf.Ticker("^INDIAVIX")
            self.vix_data = vix.history(period="3mo")
            self.vix_data.columns = [c.lower() for c in self.vix_data.columns]
        except Exception as e:
            print(f"Error fetching market data: {e}")

    def get_trend_strength(self) -> Dict:
        """
        Analyze Nifty trend using multiple indicators.

        Returns:
            Dict with trend analysis
        """
        if self.nifty_data is None or len(self.nifty_data) < 200:
            return {'trend': 'UNKNOWN', 'score': 0}

        df = self.nifty_data.copy()

        # Calculate indicators
        df['sma_50'] = ta.sma(df['close'], length=50)
        df['sma_200'] = ta.sma(df['close'], length=200)
        df['ema_20'] = ta.ema(df['close'], length=20)

        # ADX for trend strength
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        adx_col = [c for c in adx_data.columns if c.startswith('ADX_')][0]
        df['adx'] = adx_data[adx_col]

        latest = df.iloc[-1]
        prev_week = df.iloc[-5] if len(df) > 5 else latest
        prev_month = df.iloc[-22] if len(df) > 22 else latest

        # Trend scoring
        score = 0
        signals = []

        # Price vs Moving Averages
        if latest['close'] > latest['sma_50']:
            score += 1
            signals.append("Price > 50 SMA")
        else:
            score -= 1
            signals.append("Price < 50 SMA")

        if latest['close'] > latest['sma_200']:
            score += 2
            signals.append("Price > 200 SMA (Long-term bullish)")
        else:
            score -= 2
            signals.append("Price < 200 SMA (Long-term bearish)")

        # Golden/Death Cross
        if latest['sma_50'] > latest['sma_200']:
            score += 1
            signals.append("Golden Cross (50 > 200)")
        else:
            score -= 1
            signals.append("Death Cross (50 < 200)")

        # Weekly momentum
        weekly_change = (latest['close'] - prev_week['close']) / prev_week['close'] * 100
        if weekly_change > 2:
            score += 1
            signals.append(f"Strong weekly momentum (+{weekly_change:.1f}%)")
        elif weekly_change < -2:
            score -= 1
            signals.append(f"Weak weekly momentum ({weekly_change:.1f}%)")

        # Monthly momentum
        monthly_change = (latest['close'] - prev_month['close']) / prev_month['close'] * 100
        if monthly_change > 5:
            score += 1
            signals.append(f"Strong monthly trend (+{monthly_change:.1f}%)")
        elif monthly_change < -5:
            score -= 1
            signals.append(f"Weak monthly trend ({monthly_change:.1f}%)")

        # ADX trend strength
        adx_value = latest['adx']
        if adx_value > 25:
            signals.append(f"ADX {adx_value:.1f} (Strong trend)")
        else:
            signals.append(f"ADX {adx_value:.1f} (Weak/No trend)")

        return {
            'score': score,
            'signals': signals,
            'nifty_level': latest['close'],
            'sma_50': latest['sma_50'],
            'sma_200': latest['sma_200'],
            'weekly_change': weekly_change,
            'monthly_change': monthly_change,
            'adx': adx_value
        }

    def get_volatility_regime(self) -> Dict:
        """
        Analyze VIX to determine volatility regime.

        Returns:
            Dict with volatility analysis
        """
        if self.vix_data is None or len(self.vix_data) < 5:
            return {'regime': 'UNKNOWN', 'vix': 0, 'score': 0}

        current_vix = self.vix_data['close'].iloc[-1]
        avg_vix = self.vix_data['close'].rolling(20).mean().iloc[-1]
        vix_change = (current_vix - self.vix_data['close'].iloc[-5]) / self.vix_data['close'].iloc[-5] * 100

        score = 0
        regime = "NORMAL"

        if current_vix < 12:
            regime = "LOW_VOL"
            score += 1  # Low vol = bullish
        elif current_vix < 15:
            regime = "NORMAL"
            score += 0
        elif current_vix < 20:
            regime = "ELEVATED"
            score -= 1
        elif current_vix < 25:
            regime = "HIGH"
            score -= 2
        else:
            regime = "EXTREME"
            score -= 3

        # VIX spike detection
        if vix_change > 20:
            score -= 2  # VIX spiking = danger

        return {
            'regime': regime,
            'vix': current_vix,
            'avg_vix': avg_vix,
            'vix_change_5d': vix_change,
            'score': score
        }

    def get_breadth(self) -> Dict:
        """
        Estimate market breadth using Nifty components.
        Simple proxy: Check if recent moves are broad-based.

        Returns:
            Dict with breadth analysis
        """
        if self.nifty_data is None:
            return {'breadth': 'UNKNOWN', 'score': 0}

        df = self.nifty_data.copy()

        # Calculate % of days up in last 10 days
        df['daily_return'] = df['close'].pct_change()
        recent_returns = df['daily_return'].tail(10)
        up_days = (recent_returns > 0).sum()

        # Calculate average up vs down volume
        df['up_volume'] = np.where(df['daily_return'] > 0, df['volume'], 0)
        df['down_volume'] = np.where(df['daily_return'] < 0, df['volume'], 0)

        recent_up_vol = df['up_volume'].tail(10).mean()
        recent_down_vol = df['down_volume'].tail(10).mean()

        vol_ratio = recent_up_vol / recent_down_vol if recent_down_vol > 0 else 1

        score = 0
        if up_days >= 7:
            score += 2
            breadth = "STRONG_BULLISH"
        elif up_days >= 5:
            score += 1
            breadth = "BULLISH"
        elif up_days >= 4:
            score += 0
            breadth = "NEUTRAL"
        elif up_days >= 3:
            score -= 1
            breadth = "BEARISH"
        else:
            score -= 2
            breadth = "STRONG_BEARISH"

        return {
            'breadth': breadth,
            'up_days_10': up_days,
            'volume_ratio': vol_ratio,
            'score': score
        }

    def detect_regime(self) -> Dict:
        """
        Combine all factors to determine market regime.

        Returns:
            Dict with complete regime analysis
        """
        trend = self.get_trend_strength()
        volatility = self.get_volatility_regime()
        breadth = self.get_breadth()

        # Combined score
        total_score = trend['score'] + volatility['score'] + breadth['score']

        # Determine regime
        if volatility['regime'] == "EXTREME" and total_score < -3:
            regime = MarketRegime.CRASH
        elif total_score >= 5:
            regime = MarketRegime.STRONG_BULL
        elif total_score >= 2:
            regime = MarketRegime.BULL
        elif total_score >= -1:
            regime = MarketRegime.NEUTRAL
        elif total_score >= -4:
            regime = MarketRegime.BEAR
        else:
            regime = MarketRegime.STRONG_BEAR

        # Strategy recommendations based on regime
        strategy = self._get_strategy_recommendation(regime, volatility['vix'])

        return {
            'regime': regime,
            'regime_name': regime.value,
            'total_score': total_score,
            'trend': trend,
            'volatility': volatility,
            'breadth': breadth,
            'strategy': strategy,
            'position_size_multiplier': strategy['size_multiplier'],
            'should_trade': strategy['should_trade']
        }

    def _get_strategy_recommendation(self, regime: MarketRegime, vix: float) -> Dict:
        """Get strategy recommendations based on regime."""

        recommendations = {
            MarketRegime.STRONG_BULL: {
                'bias': 'AGGRESSIVE_LONG',
                'strategies': ['Breakout', 'Momentum', 'Buy dips'],
                'size_multiplier': 1.0,
                'should_trade': True,
                'notes': 'Full position size. Buy breakouts aggressively.'
            },
            MarketRegime.BULL: {
                'bias': 'LONG',
                'strategies': ['Breakout', 'Pullback buys'],
                'size_multiplier': 0.8,
                'should_trade': True,
                'notes': 'Normal position size. Prefer pullback entries.'
            },
            MarketRegime.NEUTRAL: {
                'bias': 'NEUTRAL',
                'strategies': ['Range trading', 'Mean reversion'],
                'size_multiplier': 0.5,
                'should_trade': True,
                'notes': 'Reduced size. Avoid breakout trades.'
            },
            MarketRegime.BEAR: {
                'bias': 'DEFENSIVE',
                'strategies': ['Only strong setups', 'Quick profits'],
                'size_multiplier': 0.3,
                'should_trade': True,
                'notes': 'Small positions only. Take profits quickly.'
            },
            MarketRegime.STRONG_BEAR: {
                'bias': 'CASH',
                'strategies': ['Mostly cash', 'Only oversold bounces'],
                'size_multiplier': 0.2,
                'should_trade': False,
                'notes': 'Preserve capital. Avoid new longs.'
            },
            MarketRegime.CRASH: {
                'bias': 'CASH',
                'strategies': ['100% cash', 'Wait for stabilization'],
                'size_multiplier': 0.0,
                'should_trade': False,
                'notes': 'DO NOT TRADE. Wait for VIX to drop below 20.'
            }
        }

        return recommendations.get(regime, recommendations[MarketRegime.NEUTRAL])
