"""RSS-based news fetcher for sector-level tailwind analysis."""

import time
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from rich.console import Console

from config import (
    BULLISH_KEYWORDS,
    BEARISH_KEYWORDS,
    POLICY_KEYWORDS,
    TAILWIND_NEWS_RATE_LIMIT_DELAY,
    TAILWIND_SECTOR_KEYWORDS,
    get_nifty500_symbols,
)
from .cache import TailwindCache
from .models import NewsItem

console = Console()

# RSS feed sources
NEWS_SOURCES = {
    'moneycontrol': [
        'https://www.moneycontrol.com/rss/MCtopnews.xml',
        'https://www.moneycontrol.com/rss/marketreports.xml',
    ],
    'economictimes': [
        'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
    ],
    'livemint': [
        'https://www.livemint.com/rss/markets',
    ],
    'pib': [
        'https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3',
    ],
}


class NewsFetcher:
    """Fetches and analyzes financial news from RSS feeds."""

    def __init__(self):
        self.cache = TailwindCache()
        self._stock_symbols = set()
        self._last_request_time = 0.0

    @property
    def stock_symbols(self) -> set:
        if not self._stock_symbols:
            self._stock_symbols = set(get_nifty500_symbols())
        return self._stock_symbols

    def fetch_all(self, force_refresh: bool = False) -> List[NewsItem]:
        """Fetch news from all sources."""
        all_items = []

        for source_name, urls in NEWS_SOURCES.items():
            # Check cache
            if not force_refresh:
                cached = self.cache.get_news(source_name)
                if cached:
                    all_items.extend(
                        [self._dict_to_item(d) for d in cached]
                    )
                    continue

            # Fetch from RSS
            source_items = []
            for url in urls:
                items = self._fetch_rss(url, source_name)
                source_items.extend(items)

            if source_items:
                self.cache.set_news(
                    source_name,
                    [self._item_to_dict(item) for item in source_items],
                )
                all_items.extend(source_items)

        return all_items

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < TAILWIND_NEWS_RATE_LIMIT_DELAY:
            time.sleep(TAILWIND_NEWS_RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _fetch_rss(self, url: str, source: str) -> List[NewsItem]:
        """Fetch and parse an RSS feed."""
        self._rate_limit()

        try:
            feed = feedparser.parse(url)

            if feed.bozo and not feed.entries:
                console.print(f"[dim]  {source}: RSS feed unavailable[/dim]")
                return []

            items = []
            for entry in feed.entries[:30]:
                headline = entry.get('title', '').strip()
                if not headline:
                    continue

                # Combine title + summary for better detection
                full_text = headline
                summary = entry.get('summary', '') or entry.get('description', '')
                if summary:
                    # Strip HTML tags from summary
                    import re
                    summary_clean = re.sub(r'<[^>]+>', '', summary).strip()
                    full_text = f"{headline} {summary_clean}"

                item = NewsItem(
                    headline=headline,
                    source=source,
                    url=entry.get('link', ''),
                    published_at=entry.get('published', ''),
                    sectors_detected=self._detect_sectors(full_text),
                    stocks_detected=self._detect_stocks(full_text),
                    sentiment=self._detect_sentiment(full_text),
                    policy_related=self._is_policy_related(full_text),
                    fetched_at=datetime.now().isoformat(),
                )
                items.append(item)

            return items

        except Exception as e:
            console.print(f"[dim]  {source}: fetch error: {e}[/dim]")
            return []

    def _detect_sectors(self, text: str) -> List[str]:
        """Detect mentioned sectors using keyword matching."""
        text_lower = text.lower()
        detected = []

        for sector, keywords in TAILWIND_SECTOR_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    detected.append(sector)
                    break

        return detected

    def _detect_stocks(self, text: str) -> List[str]:
        """Detect mentioned stock symbols."""
        text_upper = text.upper()
        detected = []

        for symbol in self.stock_symbols:
            # Check for symbol as a word boundary
            if f" {symbol} " in f" {text_upper} " or f" {symbol}," in f" {text_upper},":
                detected.append(symbol)

        return detected

    def _detect_sentiment(self, text: str) -> str:
        """Simple keyword-based sentiment detection."""
        text_lower = text.lower()

        bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)

        if bullish_count > bearish_count + 1:
            return "BULLISH"
        elif bearish_count > bullish_count + 1:
            return "BEARISH"
        return "NEUTRAL"

    def _is_policy_related(self, text: str) -> bool:
        """Check if headline is related to government policy."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in POLICY_KEYWORDS)

    # --- Aggregation helpers ---

    def get_sector_news(self, items: List[NewsItem], sector: str) -> List[NewsItem]:
        """Filter news items relevant to a sector."""
        return [item for item in items if sector in item.sectors_detected]

    def get_sentiment_by_sector(
        self, items: List[NewsItem]
    ) -> Dict[str, Dict[str, int]]:
        """Aggregate sentiment counts per sector."""
        result = {}

        for item in items:
            for sector in item.sectors_detected:
                if sector not in result:
                    result[sector] = {"bullish": 0, "bearish": 0, "neutral": 0}
                result[sector][item.sentiment.lower()] += 1

        return result

    def get_policy_news(self, items: List[NewsItem]) -> List[NewsItem]:
        """Filter policy-related news."""
        return [item for item in items if item.policy_related]

    def get_news_signal_by_sector(
        self, items: List[NewsItem]
    ) -> Dict[str, Dict[str, Dict[str, int]]]:
        """Aggregate news signals per sector, broken down by component type.

        Returns: {sector: {component: {bullish: N, bearish: N}}}
        Components: 'policy', 'demand', 'global', 'cycle'
        """
        result: Dict[str, Dict[str, Dict[str, int]]] = {}

        for item in items:
            for sector in item.sectors_detected:
                if sector not in result:
                    result[sector] = {
                        "policy": {"bullish": 0, "bearish": 0},
                        "demand": {"bullish": 0, "bearish": 0},
                        "global": {"bullish": 0, "bearish": 0},
                        "cycle": {"bullish": 0, "bearish": 0},
                    }

                component = self._classify_news_component(item)
                sentiment_key = "bullish" if item.sentiment == "BULLISH" else (
                    "bearish" if item.sentiment == "BEARISH" else None
                )
                if sentiment_key:
                    result[sector][component][sentiment_key] += 1

        return result

    def _classify_news_component(self, item: NewsItem) -> str:
        """Classify a news item into one of the 4 scoring components."""
        text = item.headline.lower()

        # Policy: government action, regulation, subsidies
        if item.policy_related:
            return "policy"

        # Demand: consumer behavior, market size, penetration
        demand_kw = [
            'demand', 'consumption', 'sales volume', 'market share',
            'penetration', 'adoption', 'customer', 'order book',
            'order win', 'capacity utilization', 'occupancy',
            'footfall', 'subscriber', 'user growth', 'rural',
            'urban', 'middle class', 'premium',
        ]
        if any(kw in text for kw in demand_kw):
            return "demand"

        # Global: international, macro, technology shifts
        global_kw = [
            'global', 'international', 'us market', 'europe',
            'china', 'export', 'import', 'forex', 'dollar',
            'fed ', 'ai ', 'artificial intelligence', 'cloud',
            'digital transformation', 'esg', 'climate',
            'semiconductor', 'chip', 'ev ', 'electric',
            'renewable', 'green', 'sustainability',
        ]
        if any(kw in text for kw in global_kw):
            return "global"

        # Default: cycle (commodity, interest rate, liquidity)
        return "cycle"

    # --- Serialization ---

    @staticmethod
    def _item_to_dict(item: NewsItem) -> Dict:
        return {
            'headline': item.headline,
            'source': item.source,
            'url': item.url,
            'published_at': item.published_at,
            'sectors_detected': item.sectors_detected,
            'stocks_detected': item.stocks_detected,
            'sentiment': item.sentiment,
            'policy_related': item.policy_related,
            'fetched_at': item.fetched_at,
        }

    @staticmethod
    def _dict_to_item(d: Dict) -> NewsItem:
        return NewsItem(
            headline=d.get('headline', ''),
            source=d.get('source', ''),
            url=d.get('url', ''),
            published_at=d.get('published_at', ''),
            sectors_detected=d.get('sectors_detected', []),
            stocks_detected=d.get('stocks_detected', []),
            sentiment=d.get('sentiment', 'NEUTRAL'),
            policy_related=d.get('policy_related', False),
            fetched_at=d.get('fetched_at', ''),
        )
