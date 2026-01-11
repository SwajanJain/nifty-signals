"""
Earnings Calendar - Track corporate announcements and filter trading signals.

Critical insights:
- NEVER trade 3 days before earnings (binary event risk)
- Post-earnings gaps create momentum opportunities
- Earnings surprises drive multi-week trends
- Miss estimates = avoid for weeks, Beat estimates = potential entry

Rule: Uncertainty is the enemy. Skip earnings plays unless post-announcement.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import requests
from rich.console import Console

console = Console()


class EarningsSurprise(Enum):
    """Earnings surprise classification."""
    BEAT_BIG = "BEAT_BIG"  # > 10% beat
    BEAT = "BEAT"  # 2-10% beat
    INLINE = "INLINE"  # Within 2%
    MISS = "MISS"  # 2-10% miss
    MISS_BIG = "MISS_BIG"  # > 10% miss
    UNKNOWN = "UNKNOWN"


class AnnouncementType(Enum):
    """Type of corporate announcement."""
    QUARTERLY_RESULTS = "QUARTERLY_RESULTS"
    ANNUAL_RESULTS = "ANNUAL_RESULTS"
    BOARD_MEETING = "BOARD_MEETING"
    AGM = "AGM"
    DIVIDEND = "DIVIDEND"
    BONUS = "BONUS"
    SPLIT = "SPLIT"
    BUYBACK = "BUYBACK"
    OTHER = "OTHER"


@dataclass
class EarningsEvent:
    """Single earnings/announcement event."""
    symbol: str
    company_name: str
    event_date: datetime
    event_type: AnnouncementType
    quarter: Optional[str] = None  # Q1, Q2, Q3, Q4
    fiscal_year: Optional[str] = None

    # Post-result data (filled after announcement)
    actual_eps: Optional[float] = None
    expected_eps: Optional[float] = None
    actual_revenue: Optional[float] = None
    expected_revenue: Optional[float] = None
    surprise: EarningsSurprise = EarningsSurprise.UNKNOWN

    # Price impact
    pre_result_price: Optional[float] = None
    post_result_price: Optional[float] = None
    gap_percent: Optional[float] = None

    def days_until(self) -> int:
        """Days until this event."""
        return (self.event_date.date() - datetime.now().date()).days

    def is_upcoming(self, within_days: int = 7) -> bool:
        """Check if event is upcoming within N days."""
        days = self.days_until()
        return 0 <= days <= within_days

    def is_recent(self, within_days: int = 5) -> bool:
        """Check if event happened recently."""
        days = self.days_until()
        return -within_days <= days < 0


@dataclass
class StockEarningsStatus:
    """Earnings status for a single stock."""
    symbol: str
    has_upcoming_earnings: bool
    days_to_earnings: Optional[int]
    should_skip: bool
    skip_reason: Optional[str]

    # Recent earnings
    recent_earnings: Optional[EarningsEvent] = None
    recent_surprise: EarningsSurprise = EarningsSurprise.UNKNOWN

    # Trading implications
    can_trade: bool = True
    position_size_multiplier: float = 1.0
    notes: List[str] = field(default_factory=list)


@dataclass
class EarningsCalendarView:
    """Weekly earnings calendar view."""
    week_start: datetime
    week_end: datetime
    events: List[EarningsEvent]
    stocks_to_avoid: List[str]
    stocks_post_earnings: List[str]

    def get_summary(self) -> str:
        """Get human-readable calendar summary."""
        lines = []
        lines.append("=" * 60)
        lines.append("EARNINGS CALENDAR")
        lines.append(f"Week: {self.week_start.strftime('%Y-%m-%d')} to {self.week_end.strftime('%Y-%m-%d')}")
        lines.append("=" * 60)

        # Group by date
        by_date = {}
        for event in self.events:
            date_str = event.event_date.strftime('%Y-%m-%d (%a)')
            if date_str not in by_date:
                by_date[date_str] = []
            by_date[date_str].append(event)

        for date_str, events in sorted(by_date.items()):
            lines.append(f"\n[{date_str}]")
            for event in events:
                quarter_str = f" ({event.quarter})" if event.quarter else ""
                lines.append(f"  • {event.symbol}: {event.event_type.value}{quarter_str}")

        if self.stocks_to_avoid:
            lines.append(f"\n[AVOID TRADING]")
            lines.append(f"  {', '.join(self.stocks_to_avoid)}")

        if self.stocks_post_earnings:
            lines.append(f"\n[POST-EARNINGS OPPORTUNITIES]")
            lines.append(f"  {', '.join(self.stocks_post_earnings)}")

        lines.append("=" * 60)
        return "\n".join(lines)


class EarningsCalendar:
    """
    Track earnings dates and filter trading signals.

    Data sources:
    - BSE corporate announcements
    - NSE corporate filings
    - Manual calendar for major stocks
    """

    # Buffer days before earnings (no new positions)
    EARNINGS_BUFFER_DAYS = 3

    # Days after earnings to look for momentum
    POST_EARNINGS_WINDOW = 5

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        self._cache: Dict[str, EarningsEvent] = {}
        self._calendar: List[EarningsEvent] = []
        self._last_fetch: Optional[datetime] = None

    def fetch_bse_announcements(self, days_ahead: int = 30) -> List[EarningsEvent]:
        """
        Fetch corporate announcements from BSE.

        Note: BSE API may require specific endpoints/auth.
        Falls back to sample data if unavailable.
        """
        try:
            # BSE corporate announcements endpoint
            url = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"

            from_date = datetime.now().strftime('%Y%m%d')
            to_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y%m%d')

            params = {
                'strCat': 'Board Meeting',
                'strType': 'C',
                'strFromDate': from_date,
                'strToDate': to_date,
            }

            response = requests.get(url, params=params, headers=self.headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                return self._parse_bse_announcements(data)

        except Exception as e:
            console.print(f"[yellow]Could not fetch BSE announcements: {e}[/yellow]")

        # Return sample calendar for development
        return self._get_sample_calendar()

    def _parse_bse_announcements(self, data: Dict) -> List[EarningsEvent]:
        """Parse BSE announcement response."""
        events = []

        try:
            table = data.get('Table', [])

            for item in table:
                symbol = item.get('scrip_cd', '')
                company = item.get('slongname', '')
                date_str = item.get('meeting_date', '')
                purpose = item.get('purpose', '').lower()

                # Parse date
                try:
                    event_date = datetime.strptime(date_str, '%d/%m/%Y')
                except:
                    continue

                # Determine event type
                if 'quarterly' in purpose or 'results' in purpose:
                    event_type = AnnouncementType.QUARTERLY_RESULTS
                elif 'annual' in purpose:
                    event_type = AnnouncementType.ANNUAL_RESULTS
                elif 'dividend' in purpose:
                    event_type = AnnouncementType.DIVIDEND
                elif 'bonus' in purpose:
                    event_type = AnnouncementType.BONUS
                elif 'buyback' in purpose:
                    event_type = AnnouncementType.BUYBACK
                else:
                    event_type = AnnouncementType.BOARD_MEETING

                # Determine quarter from purpose or date
                quarter = self._extract_quarter(purpose, event_date)

                events.append(EarningsEvent(
                    symbol=symbol,
                    company_name=company,
                    event_date=event_date,
                    event_type=event_type,
                    quarter=quarter,
                    fiscal_year=self._get_fiscal_year(event_date)
                ))

        except Exception as e:
            console.print(f"[yellow]Error parsing BSE data: {e}[/yellow]")

        return events

    def _extract_quarter(self, purpose: str, date: datetime) -> Optional[str]:
        """Extract quarter from purpose string or date."""
        purpose_lower = purpose.lower()

        if 'q1' in purpose_lower or 'first quarter' in purpose_lower:
            return 'Q1'
        elif 'q2' in purpose_lower or 'second quarter' in purpose_lower:
            return 'Q2'
        elif 'q3' in purpose_lower or 'third quarter' in purpose_lower:
            return 'Q3'
        elif 'q4' in purpose_lower or 'fourth quarter' in purpose_lower:
            return 'Q4'

        # Guess from date (Indian FY: Apr-Mar)
        month = date.month
        if 4 <= month <= 6:
            return 'Q1'
        elif 7 <= month <= 9:
            return 'Q2'
        elif 10 <= month <= 12:
            return 'Q3'
        else:
            return 'Q4'

    def _get_fiscal_year(self, date: datetime) -> str:
        """Get fiscal year string (e.g., FY25)."""
        year = date.year
        if date.month < 4:  # Jan-Mar belongs to previous FY
            year -= 1
        return f"FY{str(year + 1)[-2:]}"

    def _get_sample_calendar(self) -> List[EarningsEvent]:
        """
        Generate sample earnings calendar for development.

        Based on typical Nifty 100 quarterly results schedule.
        """
        events = []
        base_date = datetime.now()

        # Major companies and their typical result dates
        # Results typically cluster around 15th-25th of earnings month
        sample_schedule = [
            # IT companies (usually first to report)
            ("TCS", "Tata Consultancy Services", 3),
            ("INFY", "Infosys", 5),
            ("WIPRO", "Wipro", 7),
            ("HCLTECH", "HCL Technologies", 8),

            # Banks (mid-month)
            ("HDFCBANK", "HDFC Bank", 12),
            ("ICICIBANK", "ICICI Bank", 14),
            ("KOTAKBANK", "Kotak Mahindra Bank", 15),
            ("SBIN", "State Bank of India", 18),

            # Large caps
            ("RELIANCE", "Reliance Industries", 20),
            ("HINDUNILVR", "Hindustan Unilever", 22),
            ("ITC", "ITC Limited", 23),
            ("BHARTIARTL", "Bharti Airtel", 25),

            # Auto
            ("MARUTI", "Maruti Suzuki", 26),
            ("TATAMTRDVR", "Tata Motors", 27),
            ("M&M", "Mahindra & Mahindra", 28),
        ]

        # Current quarter results window
        for symbol, name, day_offset in sample_schedule:
            event_date = base_date + timedelta(days=day_offset)

            # Skip weekends
            while event_date.weekday() >= 5:
                event_date += timedelta(days=1)

            events.append(EarningsEvent(
                symbol=symbol,
                company_name=name,
                event_date=event_date,
                event_type=AnnouncementType.QUARTERLY_RESULTS,
                quarter=self._extract_quarter("", event_date),
                fiscal_year=self._get_fiscal_year(event_date)
            ))

        return events

    def refresh_calendar(self, days_ahead: int = 30) -> None:
        """Refresh earnings calendar from sources."""
        self._calendar = self.fetch_bse_announcements(days_ahead)
        self._last_fetch = datetime.now()

        # Build cache by symbol
        for event in self._calendar:
            self._cache[event.symbol] = event

        console.print(f"[green]Loaded {len(self._calendar)} earnings events[/green]")

    def get_stock_status(self, symbol: str) -> StockEarningsStatus:
        """
        Get earnings status for a stock.

        Returns whether to skip and position size adjustments.
        """
        # Ensure calendar is loaded
        if not self._calendar:
            self.refresh_calendar()

        # Find upcoming earnings
        event = self._cache.get(symbol)

        if not event:
            # No earnings found - safe to trade
            return StockEarningsStatus(
                symbol=symbol,
                has_upcoming_earnings=False,
                days_to_earnings=None,
                should_skip=False,
                skip_reason=None,
                can_trade=True,
                position_size_multiplier=1.0,
                notes=["No upcoming earnings in calendar"]
            )

        days_to_earnings = event.days_until()

        # Check if within buffer period
        if 0 <= days_to_earnings <= self.EARNINGS_BUFFER_DAYS:
            return StockEarningsStatus(
                symbol=symbol,
                has_upcoming_earnings=True,
                days_to_earnings=days_to_earnings,
                should_skip=True,
                skip_reason=f"Earnings in {days_to_earnings} days - binary event risk",
                can_trade=False,
                position_size_multiplier=0.0,
                notes=[
                    f"Results on {event.event_date.strftime('%Y-%m-%d')}",
                    f"Quarter: {event.quarter}",
                    "Rule: Never trade 3 days before earnings"
                ]
            )

        # Check if earnings just happened (post-earnings momentum window)
        if -self.POST_EARNINGS_WINDOW <= days_to_earnings < 0:
            return StockEarningsStatus(
                symbol=symbol,
                has_upcoming_earnings=False,
                days_to_earnings=days_to_earnings,
                should_skip=False,
                skip_reason=None,
                recent_earnings=event,
                recent_surprise=event.surprise,
                can_trade=True,
                position_size_multiplier=0.7,  # Reduced size post-earnings
                notes=[
                    f"Earnings {abs(days_to_earnings)} days ago",
                    "Post-earnings momentum window",
                    "Look for gap continuation or reversal"
                ]
            )

        # Earnings upcoming but outside buffer
        if days_to_earnings > self.EARNINGS_BUFFER_DAYS:
            # Reduce position size as we approach earnings
            if days_to_earnings <= 7:
                multiplier = 0.5
                notes = ["Earnings within week - half position"]
            elif days_to_earnings <= 14:
                multiplier = 0.7
                notes = ["Earnings within 2 weeks - reduced position"]
            else:
                multiplier = 1.0
                notes = [f"Earnings in {days_to_earnings} days"]

            return StockEarningsStatus(
                symbol=symbol,
                has_upcoming_earnings=True,
                days_to_earnings=days_to_earnings,
                should_skip=False,
                skip_reason=None,
                can_trade=True,
                position_size_multiplier=multiplier,
                notes=notes
            )

        # Default - safe to trade
        return StockEarningsStatus(
            symbol=symbol,
            has_upcoming_earnings=False,
            days_to_earnings=None,
            should_skip=False,
            skip_reason=None,
            can_trade=True,
            position_size_multiplier=1.0,
            notes=[]
        )

    def get_weekly_calendar(self) -> EarningsCalendarView:
        """Get this week's earnings calendar."""
        if not self._calendar:
            self.refresh_calendar()

        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())  # Monday
        week_end = week_start + timedelta(days=6)  # Sunday

        # Filter events for this week
        week_events = [
            e for e in self._calendar
            if week_start.date() <= e.event_date.date() <= week_end.date()
        ]

        # Stocks to avoid (earnings within buffer)
        stocks_to_avoid = []
        for event in self._calendar:
            if event.is_upcoming(self.EARNINGS_BUFFER_DAYS):
                stocks_to_avoid.append(event.symbol)

        # Stocks with recent earnings (momentum opportunity)
        stocks_post_earnings = []
        for event in self._calendar:
            if event.is_recent(self.POST_EARNINGS_WINDOW):
                stocks_post_earnings.append(event.symbol)

        return EarningsCalendarView(
            week_start=week_start,
            week_end=week_end,
            events=week_events,
            stocks_to_avoid=list(set(stocks_to_avoid)),
            stocks_post_earnings=list(set(stocks_post_earnings))
        )

    def filter_signals(
        self,
        signals: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter trading signals based on earnings calendar.

        Returns (tradable_signals, filtered_out)
        """
        tradable = []
        filtered = []

        for signal in signals:
            symbol = signal.get('symbol', '')
            status = self.get_stock_status(symbol)

            if status.should_skip:
                signal['filter_reason'] = status.skip_reason
                filtered.append(signal)
            else:
                # Adjust position size multiplier
                signal['earnings_multiplier'] = status.position_size_multiplier
                signal['earnings_notes'] = status.notes
                tradable.append(signal)

        return tradable, filtered

    def has_upcoming_earnings(self, symbol: str, within_days: int = 3) -> bool:
        """Quick check if stock has earnings within N days."""
        status = self.get_stock_status(symbol)
        if status.days_to_earnings is None:
            return False
        return 0 <= status.days_to_earnings <= within_days


def get_earnings_filter() -> Dict:
    """Quick function to get earnings filter for dashboard."""
    calendar = EarningsCalendar()
    weekly = calendar.get_weekly_calendar()

    return {
        'stocks_to_avoid': weekly.stocks_to_avoid,
        'stocks_post_earnings': weekly.stocks_post_earnings,
        'events_this_week': len(weekly.events),
        'calendar': weekly
    }
