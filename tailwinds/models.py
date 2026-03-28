"""Data models for tailwind / external factors analysis."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ThemeCategory(str, Enum):
    GOVERNMENT_POLICY = "GOVERNMENT_POLICY"
    DEMAND_SHIFT = "DEMAND_SHIFT"
    GLOBAL_MACRO = "GLOBAL_MACRO"
    REGULATORY = "REGULATORY"
    COMMODITY_CYCLE = "COMMODITY_CYCLE"
    TECHNOLOGY = "TECHNOLOGY"
    DEMOGRAPHIC = "DEMOGRAPHIC"


@dataclass
class Theme:
    """A macro theme / tailwind / headwind in the registry."""

    id: str
    name: str
    category: str  # ThemeCategory value
    description: str
    direction: str  # "TAILWIND" or "HEADWIND"
    strength: int  # 1-5

    # Sector impact mapping: sector_name -> impact_weight (0.0 to 1.0)
    affected_sectors: Dict[str, float] = field(default_factory=dict)

    # Optional stock-specific impacts
    affected_stocks: List[str] = field(default_factory=list)

    # Evidence / reasoning
    evidence: List[str] = field(default_factory=list)

    # Temporal
    started: str = ""  # ISO date or "2023-Q1"
    expected_duration: str = ""  # "2-3 years", "ongoing"
    last_reviewed: str = ""

    active: bool = True


@dataclass
class NewsItem:
    """A scraped news headline with detected metadata."""

    headline: str
    source: str  # "moneycontrol", "economictimes", "livemint", "pib"
    url: str = ""
    published_at: str = ""

    sectors_detected: List[str] = field(default_factory=list)
    stocks_detected: List[str] = field(default_factory=list)
    sentiment: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    policy_related: bool = False

    fetched_at: str = ""


@dataclass
class SectorTailwind:
    """Per-sector tailwind analysis result."""

    sector: str
    total_score: int = 50  # 0-100 (50 = neutral)

    # Component scores (0-25 each)
    policy_support_score: int = 12
    demand_dynamics_score: int = 12
    global_alignment_score: int = 12
    sector_cycle_score: int = 12

    grade: str = "Neutral"

    # Contributing themes
    contributing_themes: List[Dict[str, Any]] = field(default_factory=list)

    # News sentiment
    news_sentiment: Dict[str, int] = field(
        default_factory=lambda: {"bullish": 0, "bearish": 0, "neutral": 0}
    )
    news_highlights: List[str] = field(default_factory=list)


@dataclass
class TailwindScore:
    """Per-stock tailwind score."""

    symbol: str
    sector: str = ""
    sector_tailwind_score: int = 50
    stock_specific_adjustment: int = 0
    total_score: int = 50  # 0-100
    grade: str = "Neutral"
    key_themes: List[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class CompositeScore:
    """Blended internal (fundamental) + external (tailwind) score."""

    symbol: str
    company_name: str = ""
    sector: str = ""

    fundamental_score: int = 0  # 0-100
    fundamental_grade: str = ""
    tailwind_score: int = 50  # 0-100
    tailwind_grade: str = ""

    composite_score: int = 0  # Weighted blend
    composite_grade: str = ""
