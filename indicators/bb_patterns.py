"""Bollinger Band Pattern Recognition.

Beyond simple overbought/oversold, recognizes specific patterns ON the bands:
  W-Bottom — price touches lower band twice, second low higher (bullish reversal)
  M-Top    — price touches upper band twice, second high lower (bearish reversal)
  Squeeze  — bandwidth contracts to N-period low (volatility compression)
  Walking the Bands — price hugs upper/lower band for 5+ bars (strong trend)
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np
import pandas_ta as ta

from config import BOLLINGER_PERIOD, BOLLINGER_STD


class BBPatternDetector:
    """Detect Bollinger Band patterns."""

    def __init__(self, df: pd.DataFrame, period: int = None, std: float = None):
        self.df = df.copy()
        self._period = period or BOLLINGER_PERIOD
        self._std = std or BOLLINGER_STD
        self._valid = len(df) >= self._period + 20

        if self._valid:
            self._compute_bands()

    def _compute_bands(self):
        bbands = ta.bbands(self.df['close'], length=self._period, std=self._std)
        cols = bbands.columns.tolist()
        bb_upper = [c for c in cols if c.startswith('BBU_')][0]
        bb_mid = [c for c in cols if c.startswith('BBM_')][0]
        bb_lower = [c for c in cols if c.startswith('BBL_')][0]

        self.df['bb_upper'] = bbands[bb_upper]
        self.df['bb_mid'] = bbands[bb_mid]
        self.df['bb_lower'] = bbands[bb_lower]
        self.df['bb_width'] = (self.df['bb_upper'] - self.df['bb_lower']) / self.df['bb_mid']
        self.df['pct_b'] = (
            (self.df['close'] - self.df['bb_lower']) /
            (self.df['bb_upper'] - self.df['bb_lower']).replace(0, np.nan)
        )

    # ------------------------------------------------------------------
    def detect_w_bottom(self, lookback: int = 30) -> Optional[Dict]:
        """W-Bottom: two touches of lower band with second low higher than first.

        Classic Bollinger reversal pattern — works best after a downtrend.
        """
        if not self._valid:
            return None

        recent = self.df.tail(lookback)
        # Find bars where price touched or went below lower band (%B < 0.05)
        touches = recent[recent['pct_b'] < 0.05]

        if len(touches) < 2:
            return None

        # Group touches into clusters (gaps of 3+ bars separate clusters)
        clusters = []
        current_cluster = [touches.index[0]]
        for i in range(1, len(touches)):
            idx_diff = recent.index.get_loc(touches.index[i]) - recent.index.get_loc(touches.index[i - 1])
            if idx_diff <= 3:
                current_cluster.append(touches.index[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [touches.index[i]]
        clusters.append(current_cluster)

        if len(clusters) < 2:
            return None

        # First touch low, second touch low
        first_low = recent.loc[clusters[0], 'low'].min()
        second_low = recent.loc[clusters[-1], 'low'].min()

        # W-bottom: second low higher than first
        if second_low > first_low:
            return {
                'pattern': 'W-Bottom',
                'first_low': round(first_low, 2),
                'second_low': round(second_low, 2),
                'bullish': True,
            }
        return None

    def detect_m_top(self, lookback: int = 30) -> Optional[Dict]:
        """M-Top: two touches of upper band with second high lower than first."""
        if not self._valid:
            return None

        recent = self.df.tail(lookback)
        touches = recent[recent['pct_b'] > 0.95]

        if len(touches) < 2:
            return None

        clusters = []
        current_cluster = [touches.index[0]]
        for i in range(1, len(touches)):
            idx_diff = recent.index.get_loc(touches.index[i]) - recent.index.get_loc(touches.index[i - 1])
            if idx_diff <= 3:
                current_cluster.append(touches.index[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [touches.index[i]]
        clusters.append(current_cluster)

        if len(clusters) < 2:
            return None

        first_high = recent.loc[clusters[0], 'high'].max()
        second_high = recent.loc[clusters[-1], 'high'].max()

        if second_high < first_high:
            return {
                'pattern': 'M-Top',
                'first_high': round(first_high, 2),
                'second_high': round(second_high, 2),
                'bearish': True,
            }
        return None

    def detect_squeeze(self, lookback: int = 20) -> Dict:
        """Bandwidth at N-period low = volatility squeeze.

        Precedes large moves in either direction.
        """
        if not self._valid:
            return {'squeeze': False, 'bandwidth': 0}

        bw = self.df['bb_width'].dropna()
        if len(bw) < lookback:
            return {'squeeze': False, 'bandwidth': 0}

        current_bw = bw.iloc[-1]
        min_bw = bw.iloc[-lookback:].min()

        squeeze = current_bw <= min_bw * 1.05  # within 5% of minimum

        return {
            'squeeze': bool(squeeze),
            'bandwidth': round(float(current_bw), 4),
            'min_bandwidth': round(float(min_bw), 4),
        }

    def detect_walking_bands(self, min_bars: int = 5) -> Optional[Dict]:
        """Price hugging upper or lower band for consecutive bars.

        Walking upper band = strong uptrend (not overbought).
        Walking lower band = strong downtrend (not oversold).
        """
        if not self._valid:
            return None

        recent = self.df.tail(min_bars + 5)
        if len(recent) < min_bars:
            return None

        # Walking upper: close above mid and %B > 0.8 for min_bars
        upper_walk = 0
        for i in range(len(recent) - 1, max(len(recent) - min_bars - 1, -1), -1):
            pct_b = recent['pct_b'].iloc[i]
            if pd.notna(pct_b) and pct_b > 0.8:
                upper_walk += 1
            else:
                break

        if upper_walk >= min_bars:
            return {
                'pattern': 'Walking Upper Band',
                'bars': upper_walk,
                'bullish': True,
            }

        # Walking lower: close below mid and %B < 0.2 for min_bars
        lower_walk = 0
        for i in range(len(recent) - 1, max(len(recent) - min_bars - 1, -1), -1):
            pct_b = recent['pct_b'].iloc[i]
            if pd.notna(pct_b) and pct_b < 0.2:
                lower_walk += 1
            else:
                break

        if lower_walk >= min_bars:
            return {
                'pattern': 'Walking Lower Band',
                'bars': lower_walk,
                'bearish': True,
            }

        return None

    # ------------------------------------------------------------------
    # Standard pipeline interface
    # ------------------------------------------------------------------
    def get_all_signals(self) -> Dict:
        signals = []
        total_score = 0

        w_bottom = self.detect_w_bottom()
        if w_bottom:
            signals.append(f"BB W-Bottom (lows: ₹{w_bottom['first_low']} → ₹{w_bottom['second_low']})")
            total_score += 2

        m_top = self.detect_m_top()
        if m_top:
            signals.append(f"BB M-Top (highs: ₹{m_top['first_high']} → ₹{m_top['second_high']})")
            total_score -= 2

        squeeze = self.detect_squeeze()
        if squeeze['squeeze']:
            signals.append(f"BB Squeeze (bandwidth {squeeze['bandwidth']:.4f})")
            total_score += 1  # directionally neutral, but increases probability

        walking = self.detect_walking_bands()
        if walking:
            signals.append(f"{walking['pattern']} ({walking['bars']} bars)")
            if walking.get('bullish'):
                total_score += 1
            else:
                total_score -= 1

        return {
            'total_score': total_score,
            'signals': signals,
            'details': {
                'w_bottom': w_bottom,
                'm_top': m_top,
                'squeeze': squeeze,
                'walking': walking,
            },
        }
