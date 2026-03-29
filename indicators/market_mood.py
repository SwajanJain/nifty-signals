"""Market Mood Index — Composite real-time sentiment gauge.

Combines VIX level, market breadth proxy, and Nifty distance from 200 DMA
into a 0-100 score (0 = extreme fear, 100 = extreme greed) with a contrarian
interpretation layer.

Data is fetched via yfinance when not supplied by the caller.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf


@dataclass
class MoodResult:
    """Composite market mood reading."""

    mood_score: int  # 0-100 (0 = extreme fear, 100 = extreme greed)
    mood_label: str
    # "EXTREME_FEAR", "FEAR", "NEUTRAL", "GREED", "EXTREME_GREED"
    components: Dict[str, int] = field(default_factory=dict)
    interpretation: str = ""  # Contrarian signal text


def _mood_label(score: int) -> str:
    """Map numeric score to human-readable mood label."""
    if score <= 15:
        return "EXTREME_FEAR"
    elif score <= 35:
        return "FEAR"
    elif score <= 65:
        return "NEUTRAL"
    elif score <= 85:
        return "GREED"
    else:
        return "EXTREME_GREED"


def _contrarian_text(label: str) -> str:
    """Return a contrarian interpretation of the mood."""
    return {
        "EXTREME_FEAR": (
            "Extreme fear often marks capitulation — historically a strong "
            "buying opportunity for quality stocks. Consider staggered entry."
        ),
        "FEAR": (
            "Fear is elevated. Selective buying in high-conviction names can "
            "work well. Keep stops tight."
        ),
        "NEUTRAL": (
            "Sentiment is balanced. Follow individual stock setups; no broad "
            "sentiment edge."
        ),
        "GREED": (
            "Greed is building. Tighten trailing stops, book partial profits, "
            "avoid chasing momentum."
        ),
        "EXTREME_GREED": (
            "Extreme greed — markets are euphoric. Historically precedes sharp "
            "corrections. Raise cash, hedge positions, avoid fresh leveraged longs."
        ),
    }.get(label, "Sentiment data unavailable.")


class MarketMoodIndex:
    """Compute a composite market sentiment score from multiple signals.

    Components (each mapped to 0-100):
      1. India VIX level        — weight 35%
      2. Market breadth proxy   — weight 30%
      3. Nifty distance from 200 DMA — weight 35%
    """

    COMPONENT_WEIGHTS = {
        "vix": 0.35,
        "breadth": 0.30,
        "dma_distance": 0.35,
    }

    def __init__(self):
        self._nifty_df: Optional[pd.DataFrame] = None
        self._vix_df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def _fetch_nifty(self) -> Optional[pd.DataFrame]:
        """Fetch Nifty 50 daily data (1 year)."""
        try:
            ticker = yf.Ticker("^NSEI")
            df = ticker.history(period="1y")
            if df.empty:
                return None
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            print(f"Error fetching Nifty 50: {e}")
            return None

    def _fetch_vix(self) -> Optional[pd.DataFrame]:
        """Fetch India VIX data (3 months)."""
        try:
            ticker = yf.Ticker("^INDIAVIX")
            df = ticker.history(period="3mo")
            if df.empty:
                return None
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            print(f"Error fetching India VIX: {e}")
            return None

    # ------------------------------------------------------------------
    # Component calculations
    # ------------------------------------------------------------------

    def _vix_component(self, vix_df: Optional[pd.DataFrame]) -> int:
        """Map India VIX level to a 0-100 mood score.

        Lower VIX → higher mood (complacency/greed).
        Higher VIX → lower mood (fear/panic).
        """
        if vix_df is None or vix_df.empty:
            return 50  # neutral fallback

        current_vix = float(vix_df["close"].iloc[-1])

        if current_vix < 12:
            return 90  # euphoria
        elif current_vix < 15:
            return 70  # calm
        elif current_vix < 20:
            return 50  # cautious
        elif current_vix < 25:
            return 30  # fear
        else:
            return 10  # panic

    def _breadth_component(self, nifty_df: Optional[pd.DataFrame]) -> int:
        """Proxy market breadth using percentage of up-days in last 20 sessions.

        In a broad-based rally most days close positive; in sell-offs the
        majority close negative.  This is a simple but effective proxy when
        component-level advance/decline data is unavailable.
        """
        if nifty_df is None or len(nifty_df) < 20:
            return 50

        daily_returns = nifty_df["close"].pct_change().dropna().tail(20)
        up_pct = (daily_returns > 0).sum() / len(daily_returns) * 100

        # Map 0-100% up-days to 0-100 mood
        # 70%+ up days → greedy; 30%- up days → fearful
        return max(0, min(100, int(up_pct)))

    def _dma_distance_component(self, nifty_df: Optional[pd.DataFrame]) -> int:
        """Score based on Nifty distance from its 200-day moving average.

        >10% above → extreme greed (95)
         5-10% above → greed (75)
         0-5% above → mild greed (60)
         0-5% below → mild fear (40)
         5-10% below → fear (25)
        >10% below → extreme fear (5)
        """
        if nifty_df is None or len(nifty_df) < 200:
            return 50

        current_price = float(nifty_df["close"].iloc[-1])
        dma_200 = float(nifty_df["close"].rolling(200).mean().iloc[-1])

        if dma_200 == 0:
            return 50

        distance_pct = (current_price - dma_200) / dma_200 * 100

        if distance_pct > 10:
            return 95
        elif distance_pct > 5:
            return 75
        elif distance_pct > 0:
            return 60
        elif distance_pct > -5:
            return 40
        elif distance_pct > -10:
            return 25
        else:
            return 5

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(self, nifty_df: Optional[pd.DataFrame] = None) -> MoodResult:
        """Compute the composite Market Mood Index.

        Parameters
        ----------
        nifty_df : Optional pre-fetched Nifty 50 DataFrame with 'close'
                   column.  If None the method fetches data via yfinance.

        Returns
        -------
        MoodResult with score, label, component breakdown and contrarian
        interpretation.
        """
        # Resolve data
        if nifty_df is not None:
            self._nifty_df = nifty_df
        else:
            self._nifty_df = self._fetch_nifty()

        self._vix_df = self._fetch_vix()

        # Compute components
        vix_score = self._vix_component(self._vix_df)
        breadth_score = self._breadth_component(self._nifty_df)
        dma_score = self._dma_distance_component(self._nifty_df)

        components = {
            "vix": vix_score,
            "breadth": breadth_score,
            "dma_distance": dma_score,
        }

        # Weighted composite
        composite = (
            vix_score * self.COMPONENT_WEIGHTS["vix"]
            + breadth_score * self.COMPONENT_WEIGHTS["breadth"]
            + dma_score * self.COMPONENT_WEIGHTS["dma_distance"]
        )
        mood_score = max(0, min(100, int(round(composite))))

        label = _mood_label(mood_score)
        interpretation = _contrarian_text(label)

        return MoodResult(
            mood_score=mood_score,
            mood_label=label,
            components=components,
            interpretation=interpretation,
        )
