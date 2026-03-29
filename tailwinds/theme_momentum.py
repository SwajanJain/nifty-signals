"""Theme Momentum Tracker (E6) — Track lifecycle stage of investment themes.

A theme goes through five stages:
    Nascent -> Accelerating -> Consensus -> Crowded -> Fading

Best to invest at Nascent/Accelerating, hold at Consensus,
reduce at Crowded, and exit at Fading.

Lifecycle determination uses multiple signals:
  1. Price momentum of theme basket (average stock returns)
  2. Valuation stretch (PE of theme stocks vs market/sector median)
  3. Flow data (FII/DII accumulation in theme stocks)
  4. Fundamental quality (ROCE, growth rates of basket)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from fundamentals.models import FundamentalProfile
from tailwinds.supply_chain import THEME_BENEFICIARIES, ROLE_PRIORITY


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Market median PE used as baseline when sector data is unavailable
DEFAULT_MARKET_PE = 22.0

# Lifecycle stage thresholds
LIFECYCLE_STAGES = [
    "NASCENT",
    "ACCELERATING",
    "CONSENSUS",
    "CROWDED",
    "FADING",
]

# Signal mapping: lifecycle -> recommended action
LIFECYCLE_SIGNALS = {
    "NASCENT": "ENTER",
    "ACCELERATING": "ENTER",
    "CONSENSUS": "HOLD",
    "CROWDED": "REDUCE",
    "FADING": "EXIT",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ThemeMomentum:
    """Lifecycle and momentum analysis for a single investment theme."""

    theme: str
    description: str = ""
    lifecycle_stage: str = "NASCENT"
    momentum_score: int = 0  # 0-100
    conviction: str = "LOW"  # "HIGH", "MEDIUM", "LOW"
    basket_return_3m: float = 0.0  # %
    basket_return_6m: float = 0.0  # %
    basket_avg_pe: float = 0.0
    basket_vs_market_pe: float = 0.0  # ratio
    stocks: List[str] = field(default_factory=list)
    best_picks: List[str] = field(default_factory=list)
    signal: str = "HOLD"  # "ENTER", "HOLD", "REDUCE", "EXIT"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class ThemeMomentumTracker:
    """Track lifecycle stage and momentum of investment themes.

    Uses THEME_BENEFICIARIES from supply_chain.py for stock baskets
    and combines price momentum, valuation, and institutional flow
    signals to determine lifecycle stage.
    """

    def __init__(
        self,
        beneficiaries: Optional[Dict[str, Dict]] = None,
        market_pe: float = DEFAULT_MARKET_PE,
    ):
        self.beneficiaries = beneficiaries or THEME_BENEFICIARIES
        self.market_pe = market_pe

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_theme(
        self,
        theme: str,
        stock_dfs: Optional[Dict[str, pd.DataFrame]] = None,
        profiles: Optional[Dict[str, FundamentalProfile]] = None,
    ) -> ThemeMomentum:
        """Analyze a single theme's lifecycle stage and momentum.

        Parameters
        ----------
        theme     : Key in THEME_BENEFICIARIES (e.g. "ev_adoption").
        stock_dfs : {symbol: DataFrame} with columns including 'Close'
                    and a DatetimeIndex. Used for price momentum.
        profiles  : {symbol: FundamentalProfile} for valuation and
                    flow analysis.

        If stock_dfs is not provided, returns a simplified result based
        on profiles only. If both are missing, returns a minimal result.
        """
        theme_lower = theme.lower()
        mapping = self.beneficiaries.get(theme_lower)
        if mapping is None:
            return ThemeMomentum(
                theme=theme,
                description=f"Unknown theme: {theme}",
                lifecycle_stage="NASCENT",
                momentum_score=0,
                conviction="LOW",
                signal="HOLD",
            )

        description = mapping.get("description", theme)

        # Collect all stocks in this theme basket
        all_stocks = self._get_theme_stocks(mapping)

        # Compute individual signal components
        price_momentum = self._compute_price_momentum(
            all_stocks, stock_dfs
        )
        valuation_analysis = self._compute_valuation_stretch(
            all_stocks, profiles
        )
        flow_analysis = self._compute_flow_signals(
            all_stocks, profiles
        )

        # Determine lifecycle stage
        lifecycle = self._determine_lifecycle(
            price_momentum, valuation_analysis, flow_analysis,
        )

        # Compute momentum score (0-100)
        momentum_score = self._compute_momentum_score(
            price_momentum, valuation_analysis, flow_analysis, lifecycle,
        )

        # Determine conviction
        conviction = self._determine_conviction(
            momentum_score, lifecycle, price_momentum, valuation_analysis,
        )

        # Pick best stocks from the basket
        best_picks = self._select_best_picks(
            all_stocks, stock_dfs, profiles,
        )

        signal = LIFECYCLE_SIGNALS.get(lifecycle, "HOLD")

        return ThemeMomentum(
            theme=theme_lower,
            description=description,
            lifecycle_stage=lifecycle,
            momentum_score=momentum_score,
            conviction=conviction,
            basket_return_3m=price_momentum.get("return_3m", 0.0),
            basket_return_6m=price_momentum.get("return_6m", 0.0),
            basket_avg_pe=valuation_analysis.get("avg_pe", 0.0),
            basket_vs_market_pe=valuation_analysis.get("pe_ratio_vs_market", 0.0),
            stocks=all_stocks,
            best_picks=best_picks[:3],
            signal=signal,
        )

    def analyze_all_themes(
        self,
        stock_dfs: Optional[Dict[str, pd.DataFrame]] = None,
        profiles: Optional[Dict[str, FundamentalProfile]] = None,
    ) -> List[ThemeMomentum]:
        """Analyze all themes in THEME_BENEFICIARIES.

        Returns a list sorted by momentum_score descending.
        """
        results = []
        for theme_key in self.beneficiaries:
            result = self.analyze_theme(theme_key, stock_dfs, profiles)
            results.append(result)

        results.sort(key=lambda r: r.momentum_score, reverse=True)
        return results

    def get_actionable_themes(
        self,
        stock_dfs: Optional[Dict[str, pd.DataFrame]] = None,
        profiles: Optional[Dict[str, FundamentalProfile]] = None,
    ) -> List[ThemeMomentum]:
        """Return only NASCENT and ACCELERATING themes.

        These are the actionable buy opportunities.
        """
        all_themes = self.analyze_all_themes(stock_dfs, profiles)
        return [
            t for t in all_themes
            if t.lifecycle_stage in ("NASCENT", "ACCELERATING")
        ]

    # ------------------------------------------------------------------
    # Theme stock extraction
    # ------------------------------------------------------------------

    def _get_theme_stocks(self, mapping: Dict[str, Any]) -> List[str]:
        """Extract all unique stock symbols from a theme mapping."""
        seen = set()
        ordered: List[str] = []
        for role in ROLE_PRIORITY:
            for symbol in mapping.get(role, []):
                symbol_upper = symbol.upper()
                if symbol_upper not in seen:
                    seen.add(symbol_upper)
                    ordered.append(symbol_upper)
        return ordered

    # ------------------------------------------------------------------
    # 1. Price Momentum
    # ------------------------------------------------------------------

    def _compute_price_momentum(
        self,
        stocks: List[str],
        stock_dfs: Optional[Dict[str, pd.DataFrame]],
    ) -> Dict[str, Any]:
        """Compute average basket returns for 3m and 6m periods.

        Returns dict with: return_3m, return_6m, momentum_accelerating,
        stocks_with_data.
        """
        if not stock_dfs:
            return {
                "return_3m": 0.0,
                "return_6m": 0.0,
                "momentum_accelerating": False,
                "stocks_with_data": 0,
                "has_data": False,
            }

        returns_3m: List[float] = []
        returns_6m: List[float] = []

        for symbol in stocks:
            df = stock_dfs.get(symbol) or stock_dfs.get(symbol.upper())
            if df is None or df.empty:
                continue

            close_col = None
            for col in ("Close", "close", "Adj Close"):
                if col in df.columns:
                    close_col = col
                    break
            if close_col is None:
                continue

            try:
                closes = df[close_col].dropna()
                if len(closes) < 2:
                    continue

                latest = closes.iloc[-1]

                # 3-month return (~63 trading days)
                if len(closes) >= 63:
                    price_3m_ago = closes.iloc[-63]
                    if price_3m_ago > 0:
                        returns_3m.append(
                            (latest - price_3m_ago) / price_3m_ago * 100
                        )

                # 6-month return (~126 trading days)
                if len(closes) >= 126:
                    price_6m_ago = closes.iloc[-126]
                    if price_6m_ago > 0:
                        returns_6m.append(
                            (latest - price_6m_ago) / price_6m_ago * 100
                        )
            except (IndexError, KeyError, TypeError):
                continue

        avg_3m = sum(returns_3m) / len(returns_3m) if returns_3m else 0.0
        avg_6m = sum(returns_6m) / len(returns_6m) if returns_6m else 0.0

        # Momentum is accelerating if 3m annualized > 6m annualized
        # (more recent returns are stronger)
        annualized_3m = avg_3m * 4  # rough annualization
        annualized_6m = avg_6m * 2
        accelerating = annualized_3m > annualized_6m and avg_3m > 0

        return {
            "return_3m": round(avg_3m, 2),
            "return_6m": round(avg_6m, 2),
            "momentum_accelerating": accelerating,
            "stocks_with_data": max(len(returns_3m), len(returns_6m)),
            "has_data": len(returns_3m) > 0 or len(returns_6m) > 0,
        }

    # ------------------------------------------------------------------
    # 2. Valuation Stretch
    # ------------------------------------------------------------------

    def _compute_valuation_stretch(
        self,
        stocks: List[str],
        profiles: Optional[Dict[str, FundamentalProfile]],
    ) -> Dict[str, Any]:
        """Compute average PE and PE-vs-market ratio for theme stocks.

        Returns dict with: avg_pe, pe_ratio_vs_market, valuation_zone,
        stocks_with_pe.
        """
        if not profiles:
            return {
                "avg_pe": 0.0,
                "pe_ratio_vs_market": 0.0,
                "valuation_zone": "UNKNOWN",
                "stocks_with_pe": 0,
                "has_data": False,
            }

        pe_values: List[float] = []

        for symbol in stocks:
            profile = profiles.get(symbol) or profiles.get(symbol.upper())
            if profile is None:
                continue
            if profile.pe_ratio and profile.pe_ratio > 0:
                pe_values.append(profile.pe_ratio)

        if not pe_values:
            return {
                "avg_pe": 0.0,
                "pe_ratio_vs_market": 0.0,
                "valuation_zone": "UNKNOWN",
                "stocks_with_pe": 0,
                "has_data": False,
            }

        avg_pe = sum(pe_values) / len(pe_values)
        pe_ratio = avg_pe / self.market_pe if self.market_pe > 0 else 0.0

        # Valuation zone
        if pe_ratio < 1.0:
            zone = "BELOW_MARKET"
        elif pe_ratio < 1.5:
            zone = "SLIGHTLY_ABOVE"
        elif pe_ratio < 2.0:
            zone = "PREMIUM"
        else:
            zone = "EXTREME_PREMIUM"

        return {
            "avg_pe": round(avg_pe, 1),
            "pe_ratio_vs_market": round(pe_ratio, 2),
            "valuation_zone": zone,
            "stocks_with_pe": len(pe_values),
            "has_data": True,
        }

    # ------------------------------------------------------------------
    # 3. Flow Signals
    # ------------------------------------------------------------------

    def _compute_flow_signals(
        self,
        stocks: List[str],
        profiles: Optional[Dict[str, FundamentalProfile]],
    ) -> Dict[str, Any]:
        """Analyze FII/DII flow direction across theme stocks.

        Returns dict with: avg_fii_change, avg_promoter_change,
        flow_direction, stocks_with_data.
        """
        if not profiles:
            return {
                "avg_fii_change": 0.0,
                "avg_promoter_change": 0.0,
                "flow_direction": "NEUTRAL",
                "stocks_with_data": 0,
                "has_data": False,
            }

        fii_changes: List[float] = []
        promoter_changes: List[float] = []

        for symbol in stocks:
            profile = profiles.get(symbol) or profiles.get(symbol.upper())
            if profile is None:
                continue

            if profile.fii_holding_change_1y != 0:
                fii_changes.append(profile.fii_holding_change_1y)
            if profile.promoter_holding_change_1y != 0:
                promoter_changes.append(profile.promoter_holding_change_1y)

        avg_fii = (
            sum(fii_changes) / len(fii_changes)
            if fii_changes else 0.0
        )
        avg_promoter = (
            sum(promoter_changes) / len(promoter_changes)
            if promoter_changes else 0.0
        )

        # Flow direction
        if avg_fii > 1.0 and avg_promoter > 0:
            direction = "STRONG_INFLOW"
        elif avg_fii > 0.5:
            direction = "INFLOW"
        elif avg_fii < -1.0:
            direction = "OUTFLOW"
        elif avg_fii < -0.5:
            direction = "MILD_OUTFLOW"
        else:
            direction = "NEUTRAL"

        return {
            "avg_fii_change": round(avg_fii, 2),
            "avg_promoter_change": round(avg_promoter, 2),
            "flow_direction": direction,
            "stocks_with_data": len(fii_changes),
            "has_data": len(fii_changes) > 0,
        }

    # ------------------------------------------------------------------
    # Lifecycle Determination
    # ------------------------------------------------------------------

    def _determine_lifecycle(
        self,
        price: Dict[str, Any],
        valuation: Dict[str, Any],
        flows: Dict[str, Any],
    ) -> str:
        """Determine theme lifecycle stage from combined signals.

        Decision matrix:
        ---------------------------------------------------------------
        Price Momentum   | Valuation     | Flows         | Stage
        ---------------------------------------------------------------
        Low/early rising | Below market  | Neutral/early | NASCENT
        Accelerating     | Slight premium| Inflow        | ACCELERATING
        High but stable  | Premium       | Strong inflow | CONSENSUS
        High, decelerating| Extreme prem | Outflow starts| CROWDED
        Declining        | Premium fading| Outflow       | FADING
        ---------------------------------------------------------------
        """
        ret_3m = price.get("return_3m", 0.0)
        ret_6m = price.get("return_6m", 0.0)
        accelerating = price.get("momentum_accelerating", False)
        has_price_data = price.get("has_data", False)

        val_zone = valuation.get("valuation_zone", "UNKNOWN")
        has_val_data = valuation.get("has_data", False)

        flow_dir = flows.get("flow_direction", "NEUTRAL")

        # If no data at all, default to NASCENT (assume undiscovered)
        if not has_price_data and not has_val_data:
            return "NASCENT"

        # Score each dimension for lifecycle placement
        # Price signal
        if ret_6m > 80 and not accelerating:
            price_signal = "LATE"
        elif ret_6m > 50 and accelerating:
            price_signal = "PEAK"
        elif ret_3m > 15 and accelerating:
            price_signal = "ACCELERATING"
        elif ret_3m > 5 or ret_6m > 10:
            price_signal = "EARLY"
        elif ret_3m < -10:
            price_signal = "DECLINING"
        else:
            price_signal = "FLAT"

        # Combine signals into lifecycle
        if price_signal == "DECLINING":
            return "FADING"

        if price_signal == "LATE" and val_zone in (
            "PREMIUM", "EXTREME_PREMIUM"
        ):
            if flow_dir in ("OUTFLOW", "MILD_OUTFLOW"):
                return "FADING"
            return "CROWDED"

        if price_signal == "PEAK" and val_zone == "EXTREME_PREMIUM":
            return "CROWDED"

        if price_signal in ("PEAK", "LATE") and val_zone in (
            "SLIGHTLY_ABOVE", "PREMIUM"
        ):
            return "CONSENSUS"

        if price_signal == "ACCELERATING":
            if val_zone in ("BELOW_MARKET", "SLIGHTLY_ABOVE"):
                return "ACCELERATING"
            if flow_dir in ("INFLOW", "STRONG_INFLOW"):
                return "ACCELERATING"
            return "CONSENSUS"

        if price_signal in ("EARLY", "FLAT"):
            if val_zone in ("BELOW_MARKET", "UNKNOWN"):
                return "NASCENT"
            if flow_dir in ("NEUTRAL", "INFLOW"):
                return "NASCENT"
            return "ACCELERATING"

        return "NASCENT"

    # ------------------------------------------------------------------
    # Momentum Score
    # ------------------------------------------------------------------

    def _compute_momentum_score(
        self,
        price: Dict[str, Any],
        valuation: Dict[str, Any],
        flows: Dict[str, Any],
        lifecycle: str,
    ) -> int:
        """Compute a 0-100 momentum score for the theme.

        Higher score = stronger current momentum.
        """
        score = 0

        # Price momentum component (0-40)
        ret_3m = price.get("return_3m", 0.0)
        ret_6m = price.get("return_6m", 0.0)

        if ret_3m > 20:
            score += 25
        elif ret_3m > 10:
            score += 18
        elif ret_3m > 5:
            score += 12
        elif ret_3m > 0:
            score += 6
        elif ret_3m < -10:
            score += 0
        else:
            score += 3

        if price.get("momentum_accelerating", False):
            score += 15
        elif ret_6m > 20:
            score += 8

        # Valuation attractiveness (0-25)
        # Lower valuation = more attractive = higher score for NASCENT/ACCEL
        val_zone = valuation.get("valuation_zone", "UNKNOWN")
        if val_zone == "BELOW_MARKET":
            score += 25
        elif val_zone == "SLIGHTLY_ABOVE":
            score += 18
        elif val_zone == "PREMIUM":
            score += 10
        elif val_zone == "EXTREME_PREMIUM":
            score += 3
        else:
            score += 12  # Unknown = neutral

        # Flow component (0-20)
        flow_dir = flows.get("flow_direction", "NEUTRAL")
        flow_scores = {
            "STRONG_INFLOW": 20,
            "INFLOW": 15,
            "NEUTRAL": 8,
            "MILD_OUTFLOW": 3,
            "OUTFLOW": 0,
        }
        score += flow_scores.get(flow_dir, 8)

        # Lifecycle stage bonus (0-15)
        # Nascent/Accelerating get a bonus (opportunity), Crowded/Fading get
        # a penalty (risk).
        lifecycle_bonus = {
            "NASCENT": 12,
            "ACCELERATING": 15,
            "CONSENSUS": 8,
            "CROWDED": 3,
            "FADING": 0,
        }
        score += lifecycle_bonus.get(lifecycle, 5)

        return min(100, max(0, score))

    # ------------------------------------------------------------------
    # Conviction
    # ------------------------------------------------------------------

    def _determine_conviction(
        self,
        momentum_score: int,
        lifecycle: str,
        price: Dict[str, Any],
        valuation: Dict[str, Any],
    ) -> str:
        """Determine conviction level for the theme.

        HIGH: Strong momentum + attractive valuation + early lifecycle
        MEDIUM: Decent momentum or mixed signals
        LOW: Weak momentum, late lifecycle, or insufficient data
        """
        if not price.get("has_data", False) and not valuation.get(
            "has_data", False
        ):
            return "LOW"

        if (
            momentum_score >= 65
            and lifecycle in ("NASCENT", "ACCELERATING")
        ):
            return "HIGH"

        if momentum_score >= 50 and lifecycle != "FADING":
            return "MEDIUM"

        if (
            momentum_score >= 40
            and lifecycle in ("NASCENT", "ACCELERATING")
        ):
            return "MEDIUM"

        return "LOW"

    # ------------------------------------------------------------------
    # Best Picks Selection
    # ------------------------------------------------------------------

    def _select_best_picks(
        self,
        stocks: List[str],
        stock_dfs: Optional[Dict[str, pd.DataFrame]],
        profiles: Optional[Dict[str, FundamentalProfile]],
    ) -> List[str]:
        """Select top 3 stocks from the theme basket by combined score.

        Ranks by: momentum (price) + fundamentals (ROCE, growth) +
        institutional interest (FII change).
        """
        if not profiles:
            # Without profiles, return first 3 direct stocks
            return stocks[:3]

        scored: List[tuple] = []

        for symbol in stocks:
            profile = profiles.get(symbol) or profiles.get(symbol.upper())
            if profile is None:
                continue

            stock_score = 0.0

            # Fundamental quality (0-40)
            roce = profile.roce or 0
            if roce >= 20:
                stock_score += 20
            elif roce >= 15:
                stock_score += 14
            elif roce >= 10:
                stock_score += 8

            if profile.revenue_growth_3y >= 20:
                stock_score += 15
            elif profile.revenue_growth_3y >= 10:
                stock_score += 8

            if profile.no_loss_years_5:
                stock_score += 5

            # Institutional interest (0-25)
            if profile.fii_holding_change_1y > 2:
                stock_score += 15
            elif profile.fii_holding_change_1y > 0:
                stock_score += 8

            if profile.promoter_holding_change_1y > 0:
                stock_score += 10
            elif profile.promoter_holding_change_1y > -1:
                stock_score += 5

            # Price momentum (0-20)
            if stock_dfs:
                df = stock_dfs.get(symbol) or stock_dfs.get(
                    symbol.upper()
                )
                if df is not None and not df.empty:
                    try:
                        close_col = None
                        for col in ("Close", "close", "Adj Close"):
                            if col in df.columns:
                                close_col = col
                                break
                        if close_col and len(df) >= 63:
                            latest = df[close_col].iloc[-1]
                            price_3m = df[close_col].iloc[-63]
                            if price_3m > 0:
                                ret = (latest - price_3m) / price_3m * 100
                                if ret > 15:
                                    stock_score += 20
                                elif ret > 5:
                                    stock_score += 12
                                elif ret > 0:
                                    stock_score += 6
                    except (IndexError, KeyError, TypeError):
                        pass

            # Valuation (0-15)
            pe = profile.pe_ratio or 0
            if 0 < pe <= 20:
                stock_score += 15
            elif 0 < pe <= 30:
                stock_score += 10
            elif 0 < pe <= 45:
                stock_score += 5

            scored.append((symbol, stock_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:3]]
