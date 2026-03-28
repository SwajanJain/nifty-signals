"""Tailwind analyzer and composite scorer."""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from config import COMPOSITE_WEIGHTS
from fundamentals.models import FundamentalProfile, FundamentalScore
from .models import (
    CompositeScore,
    NewsItem,
    SectorTailwind,
    TailwindScore,
    Theme,
    ThemeCategory,
)
from .news_fetcher import NewsFetcher
from .registry import ThemeRegistry


# Category groupings for the 4 scoring components
POLICY_CATEGORIES = {
    ThemeCategory.GOVERNMENT_POLICY.value,
    ThemeCategory.REGULATORY.value,
}
DEMAND_CATEGORIES = {
    ThemeCategory.DEMAND_SHIFT.value,
    ThemeCategory.DEMOGRAPHIC.value,
}
GLOBAL_CATEGORIES = {
    ThemeCategory.GLOBAL_MACRO.value,
    ThemeCategory.TECHNOLOGY.value,
}
CYCLE_CATEGORIES = {
    ThemeCategory.COMMODITY_CYCLE.value,
}

# Map component names to category sets
COMPONENT_MAP = {
    "policy": POLICY_CATEGORIES,
    "demand": DEMAND_CATEGORIES,
    "global": GLOBAL_CATEGORIES,
    "cycle": CYCLE_CATEGORIES,
}


class TailwindAnalyzer:
    """Combines theme registry + news data into tailwind scores."""

    def __init__(
        self,
        registry: Optional[ThemeRegistry] = None,
        fetcher: Optional[NewsFetcher] = None,
    ):
        self.registry = registry or ThemeRegistry()
        self.fetcher = fetcher or NewsFetcher()
        self._news_items: Optional[List[NewsItem]] = None
        self._sector_sentiment: Optional[Dict] = None
        self._sector_news_signals: Optional[Dict] = None

    def _ensure_news(self, force_refresh: bool = False):
        """Fetch news if not already loaded."""
        if self._news_items is None or force_refresh:
            self._news_items = self.fetcher.fetch_all(force_refresh=force_refresh)
            self._sector_sentiment = self.fetcher.get_sentiment_by_sector(
                self._news_items
            )
            self._sector_news_signals = self.fetcher.get_news_signal_by_sector(
                self._news_items
            )

    def analyze_all_sectors(
        self, force_refresh: bool = False
    ) -> Dict[str, SectorTailwind]:
        """Analyze all sectors and return tailwind scores."""
        self._ensure_news(force_refresh)

        sectors = self.registry.get_all_sectors()
        results = {}

        for sector in sectors:
            results[sector] = self.analyze_sector(sector)

        return dict(
            sorted(results.items(), key=lambda x: x[1].total_score, reverse=True)
        )

    def analyze_sector(self, sector: str) -> SectorTailwind:
        """Analyze tailwinds/headwinds for a specific sector."""
        self._ensure_news()

        themes = self.registry.get_themes_for_sector(sector)

        # Apply freshness decay to theme strengths
        adjusted_themes = [self._apply_freshness_decay(t) for t in themes]

        # Get news signals for this sector
        news_signals = {}
        if self._sector_news_signals and sector in self._sector_news_signals:
            news_signals = self._sector_news_signals[sector]

        # Compute 4 component scores (themes + news for each)
        policy_score = self._compute_component_with_news(
            sector, adjusted_themes, POLICY_CATEGORIES, news_signals.get("policy", {})
        )
        demand_score = self._compute_component_with_news(
            sector, adjusted_themes, DEMAND_CATEGORIES, news_signals.get("demand", {})
        )
        global_score = self._compute_component_with_news(
            sector, adjusted_themes, GLOBAL_CATEGORIES, news_signals.get("global", {})
        )
        cycle_score = self._compute_component_with_news(
            sector, adjusted_themes, CYCLE_CATEGORIES, news_signals.get("cycle", {})
        )

        total = policy_score + demand_score + global_score + cycle_score
        total = max(0, min(100, total))

        # Contributing themes with freshness info
        contributing = []
        for t, orig in zip(adjusted_themes, themes):
            freshness = self._get_freshness_status(orig)
            contributing.append({
                "theme_id": t.id,
                "name": t.name,
                "direction": t.direction,
                "impact": t.strength * t.affected_sectors.get(sector, 0),
                "original_strength": orig.strength,
                "effective_strength": t.strength,
                "category": t.category,
                "freshness": freshness,
            })
        contributing.sort(key=lambda x: abs(x["impact"]), reverse=True)

        # News sentiment for this sector
        sentiment = {"bullish": 0, "bearish": 0, "neutral": 0}
        highlights = []
        if self._sector_sentiment and sector in self._sector_sentiment:
            sentiment = self._sector_sentiment[sector]

        if self._news_items:
            sector_news = self.fetcher.get_sector_news(self._news_items, sector)
            highlights = [n.headline for n in sector_news[:5]]

        return SectorTailwind(
            sector=sector,
            total_score=total,
            policy_support_score=policy_score,
            demand_dynamics_score=demand_score,
            global_alignment_score=global_score,
            sector_cycle_score=cycle_score,
            grade=self._assign_grade(total),
            contributing_themes=contributing,
            news_sentiment=sentiment,
            news_highlights=highlights,
        )

    def score_stock(self, symbol: str, sector: str) -> TailwindScore:
        """Get tailwind score for a specific stock.

        Uses sector score as base, then applies:
        1. Stock-specific theme adjustments (from affected_stocks)
        2. Stock-specific news mentions (bullish/bearish headlines mentioning the stock)
        3. Company exposure profile adjustments (if available)
        """
        sector_result = self.analyze_sector(sector)
        stock_themes = self.registry.get_themes_for_stock(symbol)

        # 1. Theme-based stock adjustment
        theme_adjustment = 0
        key_themes = []

        for t in stock_themes:
            decayed = self._apply_freshness_decay(t)
            if decayed.direction == "TAILWIND":
                theme_adjustment += min(decayed.strength * 2, 5)
            else:
                theme_adjustment -= min(decayed.strength * 2, 5)
            key_themes.append(t.name)

        # 2. News mentions adjustment: if this stock is mentioned in
        # bullish/bearish news, adjust accordingly
        news_adjustment = 0
        if self._news_items:
            stock_news = [
                item for item in self._news_items if symbol in item.stocks_detected
            ]
            if stock_news:
                bullish = sum(1 for n in stock_news if n.sentiment == "BULLISH")
                bearish = sum(1 for n in stock_news if n.sentiment == "BEARISH")
                total_mentions = len(stock_news)
                if total_mentions > 0:
                    news_adjustment = int(
                        (bullish - bearish) / total_mentions * 5
                    )
                    news_adjustment = max(-5, min(5, news_adjustment))

        # 3. Company exposure profile adjustment
        exposure_adjustment = self._compute_exposure_adjustment(symbol, sector)

        # Also include sector-level themes in key_themes
        sector_themes = self.registry.get_themes_for_sector(sector)
        for t in sector_themes:
            if t.name not in key_themes:
                key_themes.append(t.name)

        total_adjustment = theme_adjustment + news_adjustment + exposure_adjustment
        total_adjustment = max(-15, min(15, total_adjustment))
        total = max(0, min(100, sector_result.total_score + total_adjustment))

        # Build explanation
        if total >= 70:
            explanation = f"Strong external tailwinds for {sector} sector"
        elif total >= 55:
            explanation = f"Favorable external environment for {sector}"
        elif total >= 45:
            explanation = f"Neutral external environment for {sector}"
        elif total >= 30:
            explanation = f"Headwinds present for {sector} sector"
        else:
            explanation = f"Severe headwinds for {sector} sector"

        parts = []
        if stock_themes:
            parts.append(", ".join(t.name for t in stock_themes[:2]))
        if news_adjustment != 0:
            direction = "positive" if news_adjustment > 0 else "negative"
            parts.append(f"{direction} news mentions")
        if exposure_adjustment != 0:
            parts.append(f"exposure profile {'boost' if exposure_adjustment > 0 else 'drag'}")
        if parts:
            explanation += ". " + "; ".join(parts)

        return TailwindScore(
            symbol=symbol,
            sector=sector,
            sector_tailwind_score=sector_result.total_score,
            stock_specific_adjustment=total_adjustment,
            total_score=total,
            grade=self._assign_grade(total),
            key_themes=key_themes[:5],
            explanation=explanation,
        )

    # --- Component scoring ---

    def _compute_component_with_news(
        self,
        sector: str,
        themes: List[Theme],
        categories: set,
        news_signal: Dict[str, int],
    ) -> int:
        """Compute a component score (0-25) from themes + live news signals.

        News can push a component score by up to +/- 4 points.
        """
        base = 12.5  # Neutral center

        # Theme contribution
        for theme in themes:
            if theme.category not in categories:
                continue

            impact_weight = theme.affected_sectors.get(sector, 0)
            contribution = theme.strength * impact_weight * 2.5

            if theme.direction == "TAILWIND":
                base += contribution
            else:
                base -= contribution

        # News signal contribution (max +/- 4 points)
        if news_signal:
            bullish = news_signal.get("bullish", 0)
            bearish = news_signal.get("bearish", 0)
            total = bullish + bearish
            if total > 0:
                news_delta = (bullish - bearish) / total * 4
                base += news_delta

        return max(0, min(25, int(round(base))))

    # --- Theme freshness decay ---

    def _apply_freshness_decay(self, theme: Theme) -> Theme:
        """Return a copy of the theme with strength decayed based on age.

        Decay rules:
        - Themes with 'ongoing' or 'structural' duration: no decay
        - Themes past expected_duration: strength reduced by 40%
        - Themes not reviewed in 90+ days: strength reduced by 20%
        - Both penalties stack multiplicatively
        """
        decay_factor = 1.0

        # Check if past expected duration
        duration_years = self._parse_duration_years(theme.expected_duration)
        start_date = self._parse_start_date(theme.started)

        if duration_years and start_date:
            expected_end = start_date + timedelta(days=int(duration_years * 365))
            if datetime.now() > expected_end:
                decay_factor *= 0.6  # 40% reduction

        # Check review freshness
        if theme.last_reviewed:
            try:
                reviewed = datetime.fromisoformat(theme.last_reviewed)
                days_since = (datetime.now() - reviewed).days
                if days_since > 180:
                    decay_factor *= 0.6  # Very stale
                elif days_since > 90:
                    decay_factor *= 0.8  # Somewhat stale
            except (ValueError, TypeError):
                pass

        if decay_factor >= 1.0:
            return theme

        # Return a copy with decayed strength
        decayed_strength = max(1, int(round(theme.strength * decay_factor)))
        return Theme(
            id=theme.id,
            name=theme.name,
            category=theme.category,
            description=theme.description,
            direction=theme.direction,
            strength=decayed_strength,
            affected_sectors=theme.affected_sectors,
            affected_stocks=theme.affected_stocks,
            evidence=theme.evidence,
            started=theme.started,
            expected_duration=theme.expected_duration,
            last_reviewed=theme.last_reviewed,
            active=theme.active,
        )

    def _get_freshness_status(self, theme: Theme) -> str:
        """Get human-readable freshness status for a theme."""
        issues = []

        duration_years = self._parse_duration_years(theme.expected_duration)
        start_date = self._parse_start_date(theme.started)

        if duration_years and start_date:
            expected_end = start_date + timedelta(days=int(duration_years * 365))
            if datetime.now() > expected_end:
                issues.append("past expected duration")

        if theme.last_reviewed:
            try:
                reviewed = datetime.fromisoformat(theme.last_reviewed)
                days_since = (datetime.now() - reviewed).days
                if days_since > 180:
                    issues.append(f"stale ({days_since}d since review)")
                elif days_since > 90:
                    issues.append(f"aging ({days_since}d since review)")
            except (ValueError, TypeError):
                pass

        return "; ".join(issues) if issues else "fresh"

    @staticmethod
    def _parse_duration_years(duration: str) -> Optional[float]:
        """Parse expected_duration string into years. Returns None for 'ongoing'."""
        if not duration:
            return None
        d = duration.lower()
        if 'ongoing' in d or 'structural' in d or 'long-term' in d:
            return None

        # Try to extract number of years: "5 years", "2-3 years", "5-7 years"
        match = re.search(r'(\d+)(?:\s*-\s*(\d+))?\s*year', d)
        if match:
            if match.group(2):
                return (int(match.group(1)) + int(match.group(2))) / 2
            return float(match.group(1))

        # "6 months", "12-18 months"
        match = re.search(r'(\d+)(?:\s*-\s*(\d+))?\s*month', d)
        if match:
            if match.group(2):
                return (int(match.group(1)) + int(match.group(2))) / 2 / 12
            return int(match.group(1)) / 12

        return None

    @staticmethod
    def _parse_start_date(started: str) -> Optional[datetime]:
        """Parse started string into datetime."""
        if not started:
            return None

        # Try ISO format: "2021-01-01"
        try:
            return datetime.fromisoformat(started)
        except (ValueError, TypeError):
            pass

        # Try quarter format: "2021-Q1", "2021-Q3"
        match = re.match(r'(\d{4})-Q(\d)', started)
        if match:
            year = int(match.group(1))
            quarter = int(match.group(2))
            month = (quarter - 1) * 3 + 1
            return datetime(year, month, 1)

        return None

    # --- Company exposure profiles ---

    def _compute_exposure_adjustment(self, symbol: str, sector: str) -> int:
        """Compute stock-level adjustment based on company exposure profile.

        Loads from tailwinds/exposure.json if available.
        Returns -5 to +5 adjustment.
        """
        profile = self._load_exposure_profile(symbol)
        if not profile:
            return 0

        adjustment = 0.0

        # Pricing power amplifies tailwinds (company can capture margin)
        pricing_power = profile.get("pricing_power", 3)  # 1-5 scale
        if pricing_power >= 4:
            adjustment += 2
        elif pricing_power <= 2:
            adjustment -= 1

        # Export sensitivity: benefits from global demand themes
        export_pct = profile.get("export_pct", 0)
        if export_pct >= 40:
            # High export = more sensitive to global tailwinds
            adjustment += 1
        elif export_pct <= 10:
            adjustment -= 0.5

        # Government order dependence: benefits from policy themes
        govt_dependence = profile.get("govt_order_dependence", 3)
        if govt_dependence >= 4:
            adjustment += 1.5

        # Raw material sensitivity: headwind amplifier
        rm_sensitivity = profile.get("raw_material_sensitivity", 3)
        if rm_sensitivity >= 4:
            adjustment -= 1.5
        elif rm_sensitivity <= 2:
            adjustment += 1

        # Capex cycle exposure
        capex_exposure = profile.get("capex_cycle_exposure", 3)
        if capex_exposure >= 4:
            adjustment += 1

        return max(-5, min(5, int(round(adjustment))))

    def _load_exposure_profile(self, symbol: str) -> Optional[Dict]:
        """Load company exposure profile from exposure.json."""
        if not hasattr(self, '_exposure_cache'):
            self._exposure_cache = self._load_all_exposures()
        return self._exposure_cache.get(symbol)

    def _load_all_exposures(self) -> Dict:
        """Load all exposure profiles from JSON."""
        import json
        from config import PROJECT_ROOT

        path = PROJECT_ROOT / "tailwinds" / "exposure.json"
        try:
            with open(path) as f:
                data = json.load(f)
            return data.get("stocks", {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    # --- Grading ---

    def _assign_grade(self, score: int) -> str:
        if score >= 80:
            return "Strong Tailwind"
        elif score >= 60:
            return "Favorable"
        elif score >= 40:
            return "Neutral"
        elif score >= 20:
            return "Headwind"
        return "Severe Headwind"


class CompositeAnalyzer:
    """Blends fundamental score + tailwind score into composite."""

    def __init__(
        self,
        internal_weight: float = None,
        external_weight: float = None,
        valuation_weight: float = None,
    ):
        weights = COMPOSITE_WEIGHTS
        self.internal_weight = internal_weight or weights['internal']
        self.external_weight = external_weight or weights['external']
        self.valuation_weight = valuation_weight or weights['valuation']

    def compute(
        self,
        fundamental_score: FundamentalScore,
        tailwind_score: TailwindScore,
        profile: Optional[FundamentalProfile] = None,
    ) -> CompositeScore:
        """Compute weighted composite score."""
        valuation_normalized = fundamental_score.valuation_score * 5

        composite = int(round(
            self.internal_weight * fundamental_score.total_score
            + self.external_weight * tailwind_score.total_score
            + self.valuation_weight * valuation_normalized
        ))
        composite = max(0, min(100, composite))

        return CompositeScore(
            symbol=fundamental_score.symbol,
            company_name=fundamental_score.company_name,
            sector=fundamental_score.sector,
            fundamental_score=fundamental_score.total_score,
            fundamental_grade=fundamental_score.grade,
            tailwind_score=tailwind_score.total_score,
            tailwind_grade=tailwind_score.grade,
            composite_score=composite,
            composite_grade=self._grade(composite),
        )

    def _grade(self, score: int) -> str:
        if score >= 85:
            return "A+"
        elif score >= 75:
            return "A"
        elif score >= 60:
            return "B"
        elif score >= 45:
            return "C"
        elif score >= 30:
            return "D"
        return "F"
