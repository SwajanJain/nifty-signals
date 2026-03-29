"""Catalyst News Scanner (E3) — Scan news for company-specific catalysts.

Detects actionable catalysts from news: new orders, regulatory approvals,
capacity expansions, management changes, rating upgrades, partnerships,
acquisitions, and turnaround signals. These are event-driven triggers
that can kick off a multibagger move.

Uses Google News RSS feeds via feedparser (same dependency already in use
by the tailwinds news fetcher).
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import feedparser

from config import CACHE_DIR


# ---------------------------------------------------------------------------
# Catalyst keyword taxonomy
# ---------------------------------------------------------------------------

CATALYST_KEYWORDS: Dict[str, List[str]] = {
    "ORDER_WIN": [
        "order win", "order book", "contract win", "new order",
        "order inflow", "order received", "bag order", "wins order",
        "awarded contract", "order worth", "bags order", "secures order",
        "order pipeline", "wins contract",
    ],
    "EXPANSION": [
        "capacity expansion", "new plant", "capex", "greenfield",
        "brownfield", "commissioning", "expansion plan", "new facility",
        "production capacity", "new unit", "capex plan", "capacity addition",
        "new factory", "manufacturing unit",
    ],
    "REGULATORY": [
        "approval", "clearance", "licence", "license", "fda approval",
        "anda", "patent", "nod", "regulatory approval", "permission",
        "patent grant", "regulatory nod", "dcgi", "fda nod",
    ],
    "PRODUCT_LAUNCH": [
        "launch", "new product", "product launch", "introduce",
        "unveil", "roll out", "new model", "product range",
        "launched", "new offering",
    ],
    "PARTNERSHIP": [
        "partnership", "joint venture", "collaboration", "tie-up",
        "strategic alliance", "mou", "memorandum", "agreement signed",
        "tie up", "pact", "strategic partnership",
    ],
    "ACQUISITION": [
        "acquisition", "acquire", "takeover", "merger",
        "buy stake", "purchase", "bought", "acquires",
        "merger with", "amalgamation",
    ],
    "MANAGEMENT": [
        "new ceo", "new md", "management change", "appoint",
        "key hire", "leadership change", "new chairman",
        "new director", "appointed as",
    ],
    "RATING_UPGRADE": [
        "upgrade", "target price", "outperform", "overweight",
        "buy rating", "price target raised", "initiated coverage",
        "target raised", "upgrades to buy", "top pick",
        "price target hiked",
    ],
    "TURNAROUND": [
        "turnaround", "return to profit", "first profit",
        "positive quarter", "breakeven", "recovery",
        "back in black", "profit after loss", "debt free",
        "debt reduction",
    ],
}

# Catalyst types ranked by multibagger relevance (higher = more impactful)
CATALYST_WEIGHTS: Dict[str, float] = {
    "ORDER_WIN": 1.3,
    "EXPANSION": 1.4,
    "REGULATORY": 1.2,
    "PRODUCT_LAUNCH": 1.0,
    "PARTNERSHIP": 1.1,
    "ACQUISITION": 1.1,
    "MANAGEMENT": 0.8,
    "RATING_UPGRADE": 0.9,
    "TURNAROUND": 1.5,
}

# Negative keywords that flip a catalyst to negative/noise
NEGATIVE_MODIFIERS = [
    "cancel", "delay", "postpone", "reject", "fail", "loss",
    "suspend", "revoke", "withdraw", "downgrade", "sell",
    "underperform", "underweight", "target cut", "target reduced",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CatalystEvent:
    """A single detected catalyst from a news headline."""

    catalyst_type: str  # Key from CATALYST_KEYWORDS
    headline: str = ""
    source: str = ""
    date: str = ""
    relevance_score: float = 0.0  # 0-1
    is_positive: bool = True


@dataclass
class CatalystResult:
    """Composite catalyst scan result for a single stock."""

    symbol: str
    company_name: str = ""
    catalyst_score: int = 0  # 0-100
    catalysts: List[CatalystEvent] = field(default_factory=list)
    catalyst_density: float = 0.0  # catalysts per week
    dominant_catalyst: str = ""  # most frequent type
    signal: str = "NO_CATALYST"
    # "STRONG_CATALYST", "MODERATE_CATALYST", "WEAK_CATALYST", "NO_CATALYST"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_published_date(published_str: str) -> Optional[datetime]:
    """Best-effort parse of RSS published date strings."""
    if not published_str:
        return None

    # feedparser usually provides struct_time via entry.published_parsed
    # but when we get a string, try common formats
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(published_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _recency_weight(date_str: str, max_days: int = 30) -> float:
    """Compute a 0-1 weight based on recency. More recent = higher weight."""
    dt = _parse_published_date(date_str)
    if dt is None:
        return 0.5  # Unknown date gets middle weight

    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    age_days = (now - dt).days

    if age_days <= 0:
        return 1.0
    if age_days >= max_days:
        return 0.1
    return round(1.0 - (age_days / max_days) * 0.9, 3)


def _is_negative_context(headline: str) -> bool:
    """Check if headline contains negative modifiers that flip sentiment."""
    headline_lower = headline.lower()
    return any(neg in headline_lower for neg in NEGATIVE_MODIFIERS)


def _match_catalysts(headline: str) -> List[str]:
    """Return all catalyst types that match the headline."""
    headline_lower = headline.lower()
    matched = []
    for catalyst_type, keywords in CATALYST_KEYWORDS.items():
        if any(kw in headline_lower for kw in keywords):
            matched.append(catalyst_type)
    return matched


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class CatalystScanner:
    """Scan Google News RSS for company-specific catalyst events."""

    GOOGLE_NEWS_RSS = (
        "https://news.google.com/rss/search?"
        "q={query}+NSE+stock&hl=en-IN&gl=IN&ceid=IN:en"
    )
    RATE_LIMIT_DELAY = 3.0  # seconds between RSS requests
    MAX_ENTRIES = 40

    def __init__(self):
        self._last_request_time = 0.0

    def scan(
        self,
        symbol: str,
        company_name: str = "",
    ) -> CatalystResult:
        """Scan news for a single stock and detect catalysts.

        Parameters
        ----------
        symbol       : NSE symbol (e.g. "RELIANCE").
        company_name : Optional full company name for broader search.
        """
        entries = self._fetch_news(symbol, company_name)
        catalysts = self._extract_catalysts(entries, symbol, company_name)

        # Compute catalyst density (catalysts per week over last 30 days)
        if catalysts:
            dates = [_parse_published_date(c.date) for c in catalysts]
            valid_dates = [d for d in dates if d is not None]
            if valid_dates:
                span_days = max(
                    1,
                    (max(valid_dates) - min(valid_dates)).days,
                )
                density = len(catalysts) / max(1, span_days / 7)
            else:
                density = len(catalysts) / 4.0  # assume ~4 weeks
        else:
            density = 0.0

        # Dominant catalyst type
        type_counts: Dict[str, int] = {}
        for c in catalysts:
            type_counts[c.catalyst_type] = type_counts.get(c.catalyst_type, 0) + 1
        dominant = max(type_counts, key=type_counts.get) if type_counts else ""

        # Score computation
        score = self._compute_score(catalysts, density)

        # Signal classification — check if sentiment is predominantly negative
        positive_count = sum(1 for c in catalysts if c.is_positive)
        negative_count = sum(1 for c in catalysts if not c.is_positive)
        mostly_negative = negative_count > positive_count and negative_count >= 2

        if mostly_negative:
            signal = "HEADWIND"
        elif score >= 70:
            signal = "STRONG_CATALYST"
        elif score >= 40:
            signal = "MODERATE_CATALYST"
        elif score > 0:
            signal = "WEAK_CATALYST"
        else:
            signal = "NO_CATALYST"

        return CatalystResult(
            symbol=symbol,
            company_name=company_name,
            catalyst_score=score,
            catalysts=catalysts,
            catalyst_density=round(density, 2),
            dominant_catalyst=dominant,
            signal=signal,
        )

    def scan_batch(
        self,
        stocks: List[Dict[str, str]],
    ) -> List[CatalystResult]:
        """Scan multiple stocks for catalysts.

        Parameters
        ----------
        stocks : List of dicts with keys "symbol" and optionally "company_name".
        """
        results = []
        for stock in stocks:
            symbol = stock.get("symbol", "")
            name = stock.get("company_name", "")
            if not symbol:
                continue
            result = self.scan(symbol, name)
            results.append(result)

        # Sort by score descending
        results.sort(key=lambda r: r.catalyst_score, reverse=True)
        return results

    # ------------------------------------------------------------------
    # News fetching
    # ------------------------------------------------------------------

    def _rate_limit(self):
        """Enforce rate limiting between RSS requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _fetch_news(
        self,
        symbol: str,
        company_name: str = "",
    ) -> List[Dict[str, Any]]:
        """Fetch news entries from Google News RSS for a stock.

        Fetches up to 2 queries: one for the NSE symbol and one for the
        company name (if provided and different from the symbol).
        """
        all_entries: List[Dict[str, Any]] = []
        seen_titles: set = set()

        queries = [symbol]
        if company_name and company_name.lower() != symbol.lower():
            # Use first 3 words of company name to avoid overly broad matches
            name_query = " ".join(company_name.split()[:3])
            queries.append(name_query)

        for query in queries:
            self._rate_limit()
            url = self.GOOGLE_NEWS_RSS.format(query=query.replace(" ", "+"))

            try:
                feed = feedparser.parse(url)
                if feed.bozo and not feed.entries:
                    continue

                for entry in feed.entries[: self.MAX_ENTRIES]:
                    title = entry.get("title", "").strip()
                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)

                    # Verify the headline actually mentions the stock
                    if not self._headline_mentions_stock(
                        title, symbol, company_name
                    ):
                        continue

                    all_entries.append({
                        "title": title,
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "source": self._extract_source(entry),
                    })

            except Exception:
                continue

        return all_entries

    def _headline_mentions_stock(
        self,
        headline: str,
        symbol: str,
        company_name: str,
    ) -> bool:
        """Verify headline is actually about this stock."""
        headline_upper = headline.upper()
        headline_lower = headline.lower()

        # Check symbol as word boundary
        if re.search(rf'\b{re.escape(symbol.upper())}\b', headline_upper):
            return True

        # Check company name (first 2 significant words)
        if company_name:
            name_words = [
                w for w in company_name.split()
                if len(w) > 2 and w.lower() not in ("ltd", "ltd.", "limited", "the", "and")
            ]
            if name_words:
                # Match if at least the first significant word appears
                if name_words[0].lower() in headline_lower:
                    return True

        return False

    def _extract_source(self, entry: Dict[str, Any]) -> str:
        """Extract source name from RSS entry."""
        source = entry.get("source", {})
        if isinstance(source, dict):
            return source.get("title", "Unknown")
        # Google News often puts source in the title after " - "
        title = entry.get("title", "")
        if " - " in title:
            return title.rsplit(" - ", 1)[-1].strip()
        return "Unknown"

    # ------------------------------------------------------------------
    # Catalyst extraction
    # ------------------------------------------------------------------

    def _extract_catalysts(
        self,
        entries: List[Dict[str, Any]],
        symbol: str,
        company_name: str,
    ) -> List[CatalystEvent]:
        """Match news entries against catalyst keywords and score them."""
        catalysts: List[CatalystEvent] = []

        for entry in entries:
            headline = entry.get("title", "")
            matched_types = _match_catalysts(headline)

            if not matched_types:
                continue

            is_negative = _is_negative_context(headline)
            recency = _recency_weight(entry.get("published", ""))

            for ctype in matched_types:
                weight = CATALYST_WEIGHTS.get(ctype, 1.0)
                relevance = round(recency * weight * (0.3 if is_negative else 1.0), 3)
                relevance = min(1.0, relevance)

                catalysts.append(CatalystEvent(
                    catalyst_type=ctype,
                    headline=headline,
                    source=entry.get("source", "Unknown"),
                    date=entry.get("published", ""),
                    relevance_score=relevance,
                    is_positive=not is_negative,
                ))

        # Sort by relevance descending
        catalysts.sort(key=lambda c: c.relevance_score, reverse=True)
        return catalysts

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _compute_score(
        self,
        catalysts: List[CatalystEvent],
        density: float,
    ) -> int:
        """Compute 0-100 catalyst score from detected events.

        Scoring factors:
        - Number of positive catalysts (more = higher)
        - Relevance scores (recency + type weight)
        - Catalyst density (frequency)
        - Diversity of catalyst types
        - Negative catalysts reduce score
        """
        if not catalysts:
            return 0

        positive = [c for c in catalysts if c.is_positive]
        negative = [c for c in catalysts if not c.is_positive]

        # Base: sum of relevance scores for positive catalysts (capped)
        pos_relevance = sum(c.relevance_score for c in positive[:10])
        base_score = min(50, pos_relevance * 12)

        # Negative penalty
        neg_penalty = sum(c.relevance_score for c in negative[:5]) * 8
        base_score = max(0, base_score - neg_penalty)

        # Density bonus: more frequent catalysts = higher conviction
        density_bonus = min(15, density * 5)

        # Diversity bonus: different catalyst types hitting = stronger signal
        unique_types = len(set(c.catalyst_type for c in positive))
        diversity_bonus = min(15, unique_types * 4)

        # High-impact type bonus
        high_impact_types = {"ORDER_WIN", "EXPANSION", "TURNAROUND", "REGULATORY"}
        has_high_impact = any(
            c.catalyst_type in high_impact_types for c in positive
        )
        impact_bonus = 10 if has_high_impact else 0

        total = int(round(base_score + density_bonus + diversity_bonus + impact_bonus))
        return min(100, max(0, total))
