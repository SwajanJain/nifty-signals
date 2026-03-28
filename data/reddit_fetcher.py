"""Reddit fetcher for Indian investment subreddit discussions.

Uses Reddit's public .json endpoints (no auth required).
Fetches posts from Indian investment subreddits and extracts
stock mentions, sentiment, and budget-related discussions.
"""

import re
import time
import json
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pathlib import Path

from config import CACHE_DIR, STOCKS_FILE


# Subreddits focused on Indian markets
SUBREDDITS = [
    'IndiaInvestments',
    'IndianStreetBets',
    'IndianStockMarket',
    'StockMarketIndia',
    'indianstocks',
]

# Sort modes to fetch
SORT_MODES = ['hot', 'new']

# Rate limit: Reddit allows ~10 requests/minute without auth
REQUEST_DELAY = 6  # seconds between requests

# Budget-related keywords for filtering
BUDGET_KEYWORDS = [
    'budget', 'union budget', 'nirmala', 'sitharaman', 'finance minister',
    'fiscal', 'capex', 'infrastructure', 'tax', 'income tax', 'gst',
    'customs duty', 'deficit', 'disinvestment', 'subsidy', 'cess',
    'surcharge', 'allocation', 'expenditure', 'revenue',
    'slab', 'rebate', 'deduction', 'exemption',
]

# Common NSE stock tickers mentioned on Reddit
# We'll also load from stocks.json dynamically
COMMON_TICKERS = {
    'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN',
    'BHARTIARTL', 'ITC', 'KOTAKBANK', 'LT', 'AXISBANK', 'MARUTI',
    'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 'WIPRO', 'HCLTECH',
    'ADANIENT', 'ADANIPORTS', 'BAJFINANCE', 'BAJAJFINSV', 'TITAN',
    'NTPC', 'POWERGRID', 'ONGC', 'COALINDIA', 'BPCL', 'IOC',
    'HINDUNILVR', 'ASIANPAINT', 'ULTRACEMCO', 'GRASIM', 'NESTLEIND',
    'BRITANNIA', 'CIPLA', 'DRREDDY', 'DIVISLAB', 'HEROMOTOCO',
    'EICHERMOT', 'BAJAJ-AUTO', 'M&M', 'TECHM', 'JSWSTEEL',
    'HINDALCO', 'TATAPOWER', 'BEL', 'HAL', 'DLF', 'IRCTC',
    'ZOMATO', 'NAUKRI', 'INDIGO', 'TRENT', 'POLYCAB', 'SIEMENS',
}

# Sector keywords to detect sector discussions
SECTOR_KEYWORDS = {
    'Banking': ['bank', 'banking', 'npa', 'credit growth', 'deposit', 'nbfc', 'lending'],
    'IT': ['it sector', 'software', 'tech', 'digital', 'saas', 'ai ', 'artificial intelligence'],
    'Pharma': ['pharma', 'healthcare', 'hospital', 'drug', 'api ', 'medical', 'biotech'],
    'Auto': ['auto', 'automobile', 'ev ', 'electric vehicle', 'car ', 'two-wheeler', 'suv'],
    'Infra': ['infra', 'infrastructure', 'construction', 'road', 'highway', 'railway', 'cement'],
    'Metal': ['metal', 'steel', 'aluminium', 'copper', 'mining', 'iron ore'],
    'Energy': ['energy', 'oil', 'gas', 'solar', 'wind', 'renewable', 'power', 'coal'],
    'FMCG': ['fmcg', 'consumer', 'food', 'beverage', 'personal care', 'retail'],
    'Realty': ['real estate', 'realty', 'housing', 'property', 'affordable housing'],
    'Defence': ['defence', 'defense', 'military', 'ammunition', 'hal ', 'bel '],
    'Telecom': ['telecom', 'jio', 'airtel', 'vodafone', '5g', 'spectrum'],
    'Capital Goods': ['capital goods', 'capex', 'engineering', 'manufacturing', 'pli'],
}


class RedditFetcher:
    """Fetches and analyzes Reddit posts from Indian investment subreddits."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NiftySignals/1.0 (Budget Analysis Bot)',
            'Accept': 'application/json',
        })
        self._all_tickers = None
        self._cache_file = CACHE_DIR / 'reddit_posts.json'

    @property
    def all_tickers(self) -> set:
        """Load all tickers from stocks.json + common tickers."""
        if self._all_tickers is None:
            tickers = set(COMMON_TICKERS)
            try:
                with open(STOCKS_FILE) as f:
                    data = json.load(f)
                for stock in data.get('nifty_100', []):
                    tickers.add(stock['symbol'])
            except Exception:
                pass
            self._all_tickers = tickers
        return self._all_tickers

    def fetch_subreddit(self, subreddit: str, sort: str = 'hot',
                        limit: int = 25) -> List[Dict]:
        """Fetch posts from a subreddit using public JSON endpoint.

        Args:
            subreddit: Subreddit name (without r/)
            sort: Sort mode - 'hot', 'new', 'top', 'rising'
            limit: Number of posts to fetch (max 100)

        Returns:
            List of post dicts with title, score, comments, url, etc.
        """
        url = f'https://www.reddit.com/r/{subreddit}/{sort}.json'
        params = {'limit': min(limit, 100), 'raw_json': 1}

        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            print(f"  [!] Failed to fetch r/{subreddit}/{sort}: {e}")
            return []
        except json.JSONDecodeError:
            print(f"  [!] Invalid JSON from r/{subreddit}/{sort}")
            return []

        posts = []
        for child in data.get('data', {}).get('children', []):
            post = child.get('data', {})
            posts.append({
                'id': post.get('id', ''),
                'subreddit': subreddit,
                'title': post.get('title', ''),
                'selftext': post.get('selftext', '')[:2000],  # Truncate long posts
                'score': post.get('score', 0),
                'upvote_ratio': post.get('upvote_ratio', 0),
                'num_comments': post.get('num_comments', 0),
                'created_utc': post.get('created_utc', 0),
                'url': post.get('url', ''),
                'permalink': f"https://www.reddit.com{post.get('permalink', '')}",
                'flair': post.get('link_flair_text', ''),
                'author': post.get('author', ''),
                'is_self': post.get('is_self', True),
            })

        return posts

    def fetch_post_comments(self, subreddit: str, post_id: str,
                            limit: int = 50) -> List[Dict]:
        """Fetch top comments for a specific post.

        Args:
            subreddit: Subreddit name
            post_id: Reddit post ID
            limit: Max comments to fetch

        Returns:
            List of comment dicts
        """
        url = f'https://www.reddit.com/r/{subreddit}/comments/{post_id}.json'
        params = {'limit': limit, 'sort': 'best', 'raw_json': 1}

        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            return []

        comments = []
        if len(data) > 1:
            self._extract_comments(data[1].get('data', {}).get('children', []),
                                   comments, limit)
        return comments

    def _extract_comments(self, children: list, comments: list, limit: int):
        """Recursively extract comments from Reddit JSON."""
        for child in children:
            if len(comments) >= limit:
                break
            if child.get('kind') != 't1':
                continue
            cdata = child.get('data', {})
            comments.append({
                'body': cdata.get('body', '')[:1000],
                'score': cdata.get('score', 0),
                'author': cdata.get('author', ''),
            })
            # Get replies
            replies = cdata.get('replies', '')
            if isinstance(replies, dict):
                self._extract_comments(
                    replies.get('data', {}).get('children', []),
                    comments, limit
                )

    def fetch_all_subreddits(self, limit_per_sub: int = 25) -> List[Dict]:
        """Fetch posts from all configured subreddits.

        Respects rate limiting between requests.

        Returns:
            Combined list of posts from all subreddits, deduplicated.
        """
        all_posts = []
        seen_ids = set()

        for subreddit in SUBREDDITS:
            for sort in SORT_MODES:
                print(f"  Fetching r/{subreddit}/{sort}...")
                posts = self.fetch_subreddit(subreddit, sort, limit_per_sub)
                for post in posts:
                    if post['id'] not in seen_ids:
                        seen_ids.add(post['id'])
                        all_posts.append(post)
                time.sleep(REQUEST_DELAY)

        return all_posts

    def filter_budget_posts(self, posts: List[Dict]) -> List[Dict]:
        """Filter posts related to budget discussions.

        Args:
            posts: List of all fetched posts

        Returns:
            Posts matching budget keywords, sorted by relevance score
        """
        budget_posts = []

        for post in posts:
            text = (post['title'] + ' ' + post['selftext']).lower()
            matched_keywords = []

            for kw in BUDGET_KEYWORDS:
                if kw in text:
                    matched_keywords.append(kw)

            if matched_keywords:
                post['budget_keywords'] = matched_keywords
                post['budget_relevance'] = len(matched_keywords)
                budget_posts.append(post)

        # Sort by relevance (keyword matches) then by score
        budget_posts.sort(key=lambda p: (p['budget_relevance'], p['score']),
                          reverse=True)
        return budget_posts

    def extract_stock_mentions(self, posts: List[Dict]) -> Dict[str, Dict]:
        """Extract stock ticker mentions from posts.

        Args:
            posts: List of posts to analyze

        Returns:
            Dict mapping ticker -> {count, sentiment_hints, posts}
        """
        mentions = {}

        for post in posts:
            text = post['title'] + ' ' + post['selftext']

            for ticker in self.all_tickers:
                # Match ticker as whole word (case-insensitive for common ones,
                # exact for short ones to avoid false positives)
                if len(ticker) <= 3:
                    # Short tickers: require exact case or $TICKER format
                    pattern = rf'(?:\$|\b){re.escape(ticker)}\b'
                    if not re.search(pattern, text):
                        continue
                else:
                    pattern = rf'\b{re.escape(ticker)}\b'
                    if not re.search(pattern, text, re.IGNORECASE):
                        continue

                if ticker not in mentions:
                    mentions[ticker] = {
                        'count': 0,
                        'total_score': 0,
                        'posts': [],
                        'sentiment_words': {'bullish': 0, 'bearish': 0, 'neutral': 0},
                    }

                mentions[ticker]['count'] += 1
                mentions[ticker]['total_score'] += post['score']
                mentions[ticker]['posts'].append({
                    'title': post['title'],
                    'score': post['score'],
                    'subreddit': post['subreddit'],
                    'permalink': post['permalink'],
                })

                # Simple sentiment from context
                self._detect_sentiment(text, ticker, mentions[ticker])

        # Sort by mention count
        return dict(sorted(mentions.items(),
                           key=lambda x: x[1]['count'], reverse=True))

    def _detect_sentiment(self, text: str, ticker: str, mention_data: Dict):
        """Simple keyword-based sentiment detection around ticker mentions."""
        text_lower = text.lower()

        bullish_words = [
            'buy', 'bullish', 'long', 'undervalued', 'breakout', 'accumulate',
            'strong', 'growth', 'upside', 'moon', 'rocket', 'gem', 'multibagger',
            'outperform', 'overweight', 'target', 'rally', 'positive',
        ]
        bearish_words = [
            'sell', 'bearish', 'short', 'overvalued', 'breakdown', 'avoid',
            'weak', 'decline', 'downside', 'crash', 'dump', 'exit', 'cut',
            'underperform', 'underweight', 'negative', 'risk', 'fall',
        ]

        for word in bullish_words:
            if word in text_lower:
                mention_data['sentiment_words']['bullish'] += 1

        for word in bearish_words:
            if word in text_lower:
                mention_data['sentiment_words']['bearish'] += 1

    def detect_sectors(self, posts: List[Dict]) -> Dict[str, Dict]:
        """Detect which sectors are being discussed.

        Returns:
            Dict mapping sector -> {count, posts, sentiment}
        """
        sector_data = {}

        for post in posts:
            text = (post['title'] + ' ' + post['selftext']).lower()

            for sector, keywords in SECTOR_KEYWORDS.items():
                matched = [kw for kw in keywords if kw in text]
                if matched:
                    if sector not in sector_data:
                        sector_data[sector] = {
                            'mention_count': 0,
                            'total_score': 0,
                            'keywords_matched': set(),
                            'top_posts': [],
                        }
                    sector_data[sector]['mention_count'] += 1
                    sector_data[sector]['total_score'] += post['score']
                    sector_data[sector]['keywords_matched'].update(matched)
                    if len(sector_data[sector]['top_posts']) < 5:
                        sector_data[sector]['top_posts'].append({
                            'title': post['title'],
                            'score': post['score'],
                            'subreddit': post['subreddit'],
                        })

        # Convert sets to lists for JSON serialization
        for sector in sector_data:
            sector_data[sector]['keywords_matched'] = list(
                sector_data[sector]['keywords_matched']
            )

        return dict(sorted(sector_data.items(),
                           key=lambda x: x[1]['mention_count'], reverse=True))

    def get_top_discussions(self, posts: List[Dict], n: int = 10) -> List[Dict]:
        """Get top N most engaging posts by combined score.

        Score = upvotes + (comments * 2) to weight discussion-heavy posts.
        """
        for post in posts:
            post['engagement_score'] = post['score'] + (post['num_comments'] * 2)

        sorted_posts = sorted(posts, key=lambda p: p['engagement_score'],
                              reverse=True)
        return sorted_posts[:n]

    def fetch_and_analyze(self, limit_per_sub: int = 25,
                          fetch_comments: bool = False) -> Dict:
        """Full pipeline: fetch, filter, analyze.

        Args:
            limit_per_sub: Posts per subreddit per sort mode
            fetch_comments: Whether to fetch comments for top posts (slower)

        Returns:
            Complete analysis dict
        """
        print("\n[Reddit Agent] Fetching from Indian investment subreddits...")

        # Fetch all posts
        all_posts = self.fetch_all_subreddits(limit_per_sub)
        print(f"  Fetched {len(all_posts)} unique posts")

        # Filter budget posts
        budget_posts = self.filter_budget_posts(all_posts)
        print(f"  Found {len(budget_posts)} budget-related posts")

        # Extract stock mentions from all posts
        stock_mentions = self.extract_stock_mentions(all_posts)
        budget_stock_mentions = self.extract_stock_mentions(budget_posts)

        # Detect sector discussions
        sector_buzz = self.detect_sectors(all_posts)
        budget_sector_buzz = self.detect_sectors(budget_posts)

        # Top discussions
        top_discussions = self.get_top_discussions(all_posts, n=15)
        top_budget = self.get_top_discussions(budget_posts, n=10)

        # Optionally fetch comments for top budget posts
        top_comments = {}
        if fetch_comments and budget_posts:
            print("  Fetching comments for top budget posts...")
            for post in budget_posts[:5]:  # Top 5 budget posts
                time.sleep(REQUEST_DELAY)
                comments = self.fetch_post_comments(
                    post['subreddit'], post['id'], limit=20
                )
                if comments:
                    top_comments[post['id']] = {
                        'title': post['title'],
                        'comments': comments,
                    }

        analysis = {
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'total_posts': len(all_posts),
            'budget_posts_count': len(budget_posts),
            'subreddits': SUBREDDITS,
            'top_discussions': self._clean_for_output(top_discussions),
            'top_budget_discussions': self._clean_for_output(top_budget),
            'stock_mentions': stock_mentions,
            'budget_stock_mentions': budget_stock_mentions,
            'sector_buzz': sector_buzz,
            'budget_sector_buzz': budget_sector_buzz,
            'top_comments': top_comments,
        }

        # Cache results
        self._save_cache(analysis)

        return analysis

    def _clean_for_output(self, posts: List[Dict]) -> List[Dict]:
        """Clean posts for output (remove long selftext)."""
        cleaned = []
        for post in posts:
            p = dict(post)
            if len(p.get('selftext', '')) > 300:
                p['selftext'] = p['selftext'][:300] + '...'
            cleaned.append(p)
        return cleaned

    def _save_cache(self, data: Dict):
        """Save analysis to cache."""
        try:
            with open(self._cache_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass

    def load_cache(self) -> Optional[Dict]:
        """Load cached analysis if recent."""
        try:
            if self._cache_file.exists():
                with open(self._cache_file) as f:
                    return json.load(f)
        except Exception:
            pass
        return None


def format_reddit_report(analysis: Dict) -> str:
    """Format Reddit analysis as a readable report.

    Args:
        analysis: Output from RedditFetcher.fetch_and_analyze()

    Returns:
        Formatted string report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("REDDIT SENTIMENT REPORT - Indian Investment Community")
    lines.append(f"Fetched: {analysis['fetched_at']}")
    lines.append(f"Posts Analyzed: {analysis['total_posts']} | "
                 f"Budget-Related: {analysis['budget_posts_count']}")
    lines.append("=" * 70)

    # Top Budget Discussions
    lines.append("\n## TOP BUDGET DISCUSSIONS")
    lines.append("-" * 40)
    for i, post in enumerate(analysis.get('top_budget_discussions', [])[:10], 1):
        score = post.get('score', 0)
        comments = post.get('num_comments', 0)
        sub = post.get('subreddit', '')
        title = post.get('title', '')
        lines.append(f"  {i}. [{score:>4} pts | {comments:>3} comments] r/{sub}")
        lines.append(f"     {title}")
        lines.append(f"     {post.get('permalink', '')}")
        lines.append("")

    # Stock Mentions in Budget Posts
    budget_mentions = analysis.get('budget_stock_mentions', {})
    if budget_mentions:
        lines.append("\n## STOCK MENTIONS (Budget Posts)")
        lines.append("-" * 40)
        lines.append(f"  {'Ticker':<15} {'Mentions':>8} {'Score':>8} {'Sentiment':>12}")
        for ticker, data in list(budget_mentions.items())[:20]:
            s = data['sentiment_words']
            if s['bullish'] > s['bearish']:
                sentiment = 'BULLISH'
            elif s['bearish'] > s['bullish']:
                sentiment = 'BEARISH'
            else:
                sentiment = 'NEUTRAL'
            lines.append(f"  {ticker:<15} {data['count']:>8} {data['total_score']:>8} "
                         f"{sentiment:>12}")

    # Overall Stock Mentions
    all_mentions = analysis.get('stock_mentions', {})
    if all_mentions:
        lines.append("\n## TOP STOCK MENTIONS (All Posts)")
        lines.append("-" * 40)
        lines.append(f"  {'Ticker':<15} {'Mentions':>8} {'Score':>8} {'Sentiment':>12}")
        for ticker, data in list(all_mentions.items())[:20]:
            s = data['sentiment_words']
            if s['bullish'] > s['bearish']:
                sentiment = 'BULLISH'
            elif s['bearish'] > s['bullish']:
                sentiment = 'BEARISH'
            else:
                sentiment = 'NEUTRAL'
            lines.append(f"  {ticker:<15} {data['count']:>8} {data['total_score']:>8} "
                         f"{sentiment:>12}")

    # Sector Buzz
    sector_buzz = analysis.get('budget_sector_buzz', {})
    if sector_buzz:
        lines.append("\n## SECTOR BUZZ (Budget Posts)")
        lines.append("-" * 40)
        for sector, data in sector_buzz.items():
            kws = ', '.join(data['keywords_matched'][:5])
            lines.append(f"  {sector:<18} {data['mention_count']:>3} mentions | "
                         f"Keywords: {kws}")

    # Overall Top Discussions
    lines.append("\n## TOP DISCUSSIONS (All)")
    lines.append("-" * 40)
    for i, post in enumerate(analysis.get('top_discussions', [])[:10], 1):
        score = post.get('score', 0)
        comments = post.get('num_comments', 0)
        sub = post.get('subreddit', '')
        title = post.get('title', '')
        lines.append(f"  {i}. [{score:>4} pts | {comments:>3} comments] r/{sub}")
        lines.append(f"     {title}")
        lines.append("")

    # Top Comments
    top_comments = analysis.get('top_comments', {})
    if top_comments:
        lines.append("\n## TOP COMMENTS ON BUDGET POSTS")
        lines.append("-" * 40)
        for post_id, cdata in top_comments.items():
            lines.append(f"\n  Post: {cdata['title']}")
            for j, comment in enumerate(cdata['comments'][:5], 1):
                body = comment['body'][:200].replace('\n', ' ')
                lines.append(f"    [{comment['score']:>3} pts] {body}")
            lines.append("")

    lines.append("=" * 70)
    return '\n'.join(lines)


# CLI entry point
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Reddit Investment Sentiment Fetcher')
    parser.add_argument('--limit', type=int, default=25,
                        help='Posts per subreddit per sort mode (default: 25)')
    parser.add_argument('--comments', action='store_true',
                        help='Also fetch comments for top budget posts (slower)')
    parser.add_argument('--cached', action='store_true',
                        help='Use cached results if available')
    args = parser.parse_args()

    fetcher = RedditFetcher()

    if args.cached:
        cached = fetcher.load_cache()
        if cached:
            print(format_reddit_report(cached))
            exit(0)
        print("No cache found, fetching fresh data...")

    analysis = fetcher.fetch_and_analyze(
        limit_per_sub=args.limit,
        fetch_comments=args.comments,
    )
    print(format_reddit_report(analysis))
