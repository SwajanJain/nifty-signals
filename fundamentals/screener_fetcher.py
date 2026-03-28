"""Screener.in scraper for fundamental data."""

import random
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from config import (
    SCREENER_BASE_URL,
    SCREENER_STANDALONE_URL,
    SCREENER_MAX_RETRIES,
    SCREENER_RATE_LIMIT_DELAY,
    SCREENER_SYMBOL_MAP,
    SCREENER_TIMEOUT,
)
from .cache import FundamentalCache
from .models import ScreenerRawData

console = Console()

# Stocks known to be missing or problematic on screener.in
SCREENER_SKIP_LIST = set()


class ScreenerFetcher:
    """Scrapes financial data from screener.in."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.cache = FundamentalCache()
        self._last_request_time = 0.0

    # --- Public API ---

    def fetch_stock(
        self, symbol: str, force_refresh: bool = False
    ) -> Optional[ScreenerRawData]:
        """Fetch all fundamental data for a single stock."""
        if symbol in SCREENER_SKIP_LIST:
            return None

        # Check cache
        if not force_refresh:
            cached = self.cache.get_raw(symbol)
            if cached:
                return self._dict_to_raw(cached)

        # Fetch from screener.in
        soup = self._fetch_page(symbol)
        if soup is None:
            return None

        raw = self._parse_page(symbol, soup)
        if raw:
            self.cache.set_raw(symbol, self._raw_to_dict(raw))
        return raw

    def fetch_batch(
        self,
        symbols: List[str],
        force_refresh: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, ScreenerRawData]:
        """Fetch data for multiple stocks with rate limiting and progress."""
        results = {}
        total = len(symbols)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching fundamentals...", total=total)

            for i, symbol in enumerate(symbols):
                progress.update(
                    task,
                    description=f"[cyan]{symbol}[/cyan] ({i+1}/{total})",
                )

                raw = self.fetch_stock(symbol, force_refresh=force_refresh)
                if raw:
                    results[symbol] = raw

                progress.advance(task)

                if progress_callback:
                    progress_callback(symbol, i + 1, total)

        console.print(
            f"[green]Fetched {len(results)}/{total} stocks successfully[/green]"
        )
        return results

    # --- Page fetching ---

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        delay = SCREENER_RATE_LIMIT_DELAY + random.uniform(-0.5, 0.5)
        delay = max(1.0, delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_time = time.time()

    def _get_screener_url(self, symbol: str) -> str:
        mapped = SCREENER_SYMBOL_MAP.get(symbol, symbol)
        return SCREENER_BASE_URL.format(symbol=mapped)

    def _get_standalone_url(self, symbol: str) -> str:
        mapped = SCREENER_SYMBOL_MAP.get(symbol, symbol)
        return SCREENER_STANDALONE_URL.format(symbol=mapped)

    def _fetch_page(self, symbol: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a single screener.in company page."""
        self._rate_limit()

        for attempt in range(SCREENER_MAX_RETRIES):
            try:
                url = self._get_screener_url(symbol)
                resp = self.session.get(url, timeout=SCREENER_TIMEOUT)

                if resp.status_code == 404:
                    # Try standalone
                    url = self._get_standalone_url(symbol)
                    resp = self.session.get(url, timeout=SCREENER_TIMEOUT)
                    if resp.status_code == 404:
                        console.print(f"[dim]  {symbol}: not found on screener.in[/dim]")
                        SCREENER_SKIP_LIST.add(symbol)
                        return None

                if resp.status_code == 429:
                    wait = 60 * (attempt + 1)
                    console.print(f"[yellow]Rate limited. Waiting {wait}s...[/yellow]")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                return BeautifulSoup(resp.text, 'html.parser')

            except requests.exceptions.Timeout:
                if attempt < SCREENER_MAX_RETRIES - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                console.print(f"[red]  {symbol}: timeout after {SCREENER_MAX_RETRIES} attempts[/red]")
                return None

            except requests.exceptions.RequestException as e:
                if attempt < SCREENER_MAX_RETRIES - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                console.print(f"[red]  {symbol}: request error: {e}[/red]")
                return None

        return None

    # --- Page parsing ---

    def _parse_page(self, symbol: str, soup: BeautifulSoup) -> Optional[ScreenerRawData]:
        """Parse all sections of a screener.in company page."""
        try:
            company_name = self._parse_company_name(soup)
            top_ratios = self._parse_top_ratios(soup)

            raw = ScreenerRawData(
                symbol=symbol,
                company_name=company_name,
                sector=top_ratios.get('sector', ''),
                industry=top_ratios.get('industry', ''),
                market_cap=top_ratios.get('market_cap', 0),
                current_price=top_ratios.get('current_price', 0),
                pe_ratio=top_ratios.get('pe_ratio', 0),
                book_value=top_ratios.get('book_value', 0),
                dividend_yield=top_ratios.get('dividend_yield', 0),
                roce=top_ratios.get('roce', 0),
                roe=top_ratios.get('roe', 0),
                face_value=top_ratios.get('face_value', 10),
                high_52w=top_ratios.get('high_52w', 0),
                low_52w=top_ratios.get('low_52w', 0),
                fetched_at=datetime.now(),
            )

            # Parse each section, catch errors per section
            raw.quarterly_results = self._safe_parse(
                lambda: self._parse_section_table(soup, 'quarters'), 'quarters'
            )
            raw.annual_pl = self._safe_parse(
                lambda: self._parse_section_table(soup, 'profit-loss'), 'profit-loss'
            )
            raw.balance_sheet = self._safe_parse(
                lambda: self._parse_section_table(soup, 'balance-sheet'), 'balance-sheet'
            )
            raw.cash_flow = self._safe_parse(
                lambda: self._parse_section_table(soup, 'cash-flow'), 'cash-flow'
            )
            raw.ratios = self._safe_parse(
                lambda: self._parse_section_table(soup, 'ratios'), 'ratios'
            )
            raw.shareholding = self._safe_parse(
                lambda: self._parse_shareholding(soup), 'shareholding'
            )

            # Parse growth rates from P&L section
            growth = self._safe_parse(
                lambda: self._parse_growth_rates(soup), 'growth'
            )
            if growth:
                raw.compounded_sales_growth = growth.get('sales_growth', {})
                raw.compounded_profit_growth = growth.get('profit_growth', {})
                raw.stock_price_cagr = growth.get('price_cagr', {})
                raw.return_on_equity = growth.get('roe_history', {})

            # Determine data quality
            sections_present = sum([
                bool(raw.quarterly_results),
                bool(raw.annual_pl),
                bool(raw.balance_sheet),
                bool(raw.cash_flow),
            ])
            if sections_present >= 3:
                raw.data_quality = "GOOD"
            elif sections_present >= 1:
                raw.data_quality = "PARTIAL"
            else:
                raw.data_quality = "MISSING"

            return raw

        except Exception as e:
            console.print(f"[red]  {symbol}: parse error: {e}[/red]")
            return None

    def _safe_parse(self, parser_fn, section_name: str):
        """Run a parser function, return empty on error."""
        try:
            return parser_fn()
        except Exception as e:
            console.print(f"[dim]    Warning: could not parse {section_name}: {e}[/dim]")
            return [] if section_name != 'growth' else {}

    def _parse_company_name(self, soup: BeautifulSoup) -> str:
        """Extract company name from page header."""
        # Try the h1 tag
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        return ""

    def _parse_top_ratios(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Parse top-level ratios from the company info section."""
        ratios = {}

        # Parse the key-value pairs in the company ratios section
        # Screener uses <li> or <span> elements with "name" and "value" classes
        # or a #top-ratios section
        ratio_list = soup.find('ul', id='top-ratios')
        if not ratio_list:
            # Try finding by class
            ratio_list = soup.find('ul', class_='ratios-top')

        if ratio_list:
            items = ratio_list.find_all('li')
            for item in items:
                name_el = item.find('span', class_='name')
                value_el = item.find('span', class_='value') or item.find('span', class_='number')
                if name_el and value_el:
                    name = name_el.get_text(strip=True).lower()
                    value = self._clean_number(value_el.get_text(strip=True))
                    if value is not None:
                        if 'market cap' in name:
                            ratios['market_cap'] = value
                        elif 'current price' in name:
                            ratios['current_price'] = value
                        elif 'stock p/e' in name or 'p/e' in name:
                            ratios['pe_ratio'] = value
                        elif 'book value' in name:
                            ratios['book_value'] = value
                        elif 'dividend yield' in name:
                            ratios['dividend_yield'] = value
                        elif 'roce' in name:
                            ratios['roce'] = value
                        elif 'roe' in name:
                            ratios['roe'] = value
                        elif 'face value' in name:
                            ratios['face_value'] = value

        # Alternative: parse from the company-info section
        if not ratios:
            ratios = self._parse_ratios_from_warehouses(soup)

        # Parse high/low
        high_low = soup.find(string=lambda t: t and 'High / Low' in str(t) if t else False)
        if high_low:
            parent = high_low.find_parent()
            if parent:
                nums = parent.get_text()
                parts = nums.replace('High / Low', '').strip().split('/')
                if len(parts) == 2:
                    ratios['high_52w'] = self._clean_number(parts[0]) or 0
                    ratios['low_52w'] = self._clean_number(parts[1]) or 0

        # Parse sector/industry from company info
        sector_el = soup.find('a', href=lambda h: h and '/sector/' in h if h else False)
        if sector_el:
            ratios['sector'] = sector_el.get_text(strip=True)

        industry_el = soup.find('a', href=lambda h: h and '/industry/' in h if h else False)
        if industry_el:
            ratios['industry'] = industry_el.get_text(strip=True)

        return ratios

    def _parse_ratios_from_warehouses(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Alternative parsing for top ratios from warehouse-style elements."""
        ratios = {}
        # Screener sometimes uses data-warehouse attributes or
        # the company-ratios div
        company_info = soup.find('div', class_='company-info')
        if not company_info:
            company_info = soup.find('div', id='company-info')

        if company_info:
            for li in company_info.find_all('li'):
                text = li.get_text(strip=True)
                name_span = li.find('span', class_='name')
                val_span = li.find('span', class_='number') or li.find('span', class_='value')
                if name_span and val_span:
                    name = name_span.get_text(strip=True).lower()
                    val = self._clean_number(val_span.get_text(strip=True))
                    if val is not None:
                        if 'market cap' in name:
                            ratios['market_cap'] = val
                        elif 'price' in name and 'stock' not in name:
                            ratios['current_price'] = val
                        elif 'p/e' in name:
                            ratios['pe_ratio'] = val
                        elif 'book value' in name:
                            ratios['book_value'] = val
                        elif 'dividend' in name:
                            ratios['dividend_yield'] = val
                        elif 'roce' in name:
                            ratios['roce'] = val
                        elif 'roe' in name:
                            ratios['roe'] = val
                        elif 'face value' in name:
                            ratios['face_value'] = val

        return ratios

    def _parse_section_table(self, soup: BeautifulSoup, section_id: str) -> List[Dict[str, Any]]:
        """Parse a financial data table from a named section.

        Returns a list of dicts, one per row, with 'label' and period-keyed values.
        """
        section = soup.find('section', id=section_id)
        if not section:
            return []

        table = section.find('table')
        if not table:
            return []

        return self._parse_html_table(table)

    def _parse_html_table(self, table) -> List[Dict[str, Any]]:
        """Generic HTML table parser for screener.in tables.

        Returns list of dicts with 'label' key and period columns.
        """
        rows = table.find_all('tr')
        if not rows:
            return []

        # Extract headers from first row
        header_row = rows[0]
        headers = []
        for th in header_row.find_all(['th', 'td']):
            text = th.get_text(strip=True)
            headers.append(text)

        # Parse data rows
        data = []
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue

            row_data = {}
            # First cell is the label/metric name
            label = cells[0].get_text(strip=True)
            if not label or label == '+':
                continue

            row_data['label'] = label

            # Remaining cells are period values
            for j, cell in enumerate(cells[1:], 1):
                if j < len(headers):
                    period = headers[j]
                else:
                    period = f"col_{j}"

                val = self._clean_number(cell.get_text(strip=True))
                row_data[period] = val

            data.append(row_data)

        return data

    def _parse_shareholding(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse shareholding pattern table."""
        section = soup.find('section', id='shareholding')
        if not section:
            return []

        table = section.find('table')
        if not table:
            return []

        return self._parse_html_table(table)

    def _parse_growth_rates(self, soup: BeautifulSoup) -> Dict[str, Dict[str, float]]:
        """Parse compounded growth rates from the P&L section."""
        growth = {
            'sales_growth': {},
            'profit_growth': {},
            'price_cagr': {},
            'roe_history': {},
        }

        section = soup.find('section', id='profit-loss')
        if not section:
            return growth

        # Growth rates are typically in a separate div/table within the P&L section
        # Look for text patterns like "Compounded Sales Growth"
        all_text_blocks = section.find_all(['table', 'div'])

        for block in all_text_blocks:
            text = block.get_text()
            if 'Compounded Sales Growth' in text:
                growth['sales_growth'] = self._extract_growth_values(block, 'Compounded Sales Growth')
            if 'Compounded Profit Growth' in text:
                growth['profit_growth'] = self._extract_growth_values(block, 'Compounded Profit Growth')
            if 'Stock Price CAGR' in text:
                growth['price_cagr'] = self._extract_growth_values(block, 'Stock Price CAGR')
            if 'Return on Equity' in text:
                growth['roe_history'] = self._extract_growth_values(block, 'Return on Equity')

        return growth

    def _extract_growth_values(self, block, heading: str) -> Dict[str, float]:
        """Extract growth rate key-value pairs from a block."""
        values = {}
        text = block.get_text(separator='|')

        # Try to find table rows within the block
        rows = block.find_all('tr')
        if rows:
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    val = self._clean_number(cells[1].get_text(strip=True))
                    if val is not None:
                        # Normalize label
                        if '10' in label:
                            values['10yr'] = val
                        elif '5' in label:
                            values['5yr'] = val
                        elif '3' in label:
                            values['3yr'] = val
                        elif '1' in label:
                            values['1yr'] = val
                        elif 'ttm' in label:
                            values['ttm'] = val
                        elif 'last' in label:
                            values['last_yr'] = val

        return values

    # --- Serialization helpers ---

    @staticmethod
    def _raw_to_dict(raw: ScreenerRawData) -> Dict:
        """Convert ScreenerRawData to a JSON-serializable dict."""
        return {
            'symbol': raw.symbol,
            'company_name': raw.company_name,
            'sector': raw.sector,
            'industry': raw.industry,
            'market_cap': raw.market_cap,
            'current_price': raw.current_price,
            'pe_ratio': raw.pe_ratio,
            'book_value': raw.book_value,
            'dividend_yield': raw.dividend_yield,
            'roce': raw.roce,
            'roe': raw.roe,
            'face_value': raw.face_value,
            'high_52w': raw.high_52w,
            'low_52w': raw.low_52w,
            'quarterly_results': raw.quarterly_results,
            'annual_pl': raw.annual_pl,
            'compounded_sales_growth': raw.compounded_sales_growth,
            'compounded_profit_growth': raw.compounded_profit_growth,
            'stock_price_cagr': raw.stock_price_cagr,
            'return_on_equity': raw.return_on_equity,
            'balance_sheet': raw.balance_sheet,
            'cash_flow': raw.cash_flow,
            'ratios': raw.ratios,
            'shareholding': raw.shareholding,
            'fetched_at': raw.fetched_at.isoformat() if raw.fetched_at else None,
            'is_consolidated': raw.is_consolidated,
            'data_quality': raw.data_quality,
        }

    @staticmethod
    def _dict_to_raw(d: Dict) -> ScreenerRawData:
        """Convert a cached dict back to ScreenerRawData."""
        fetched_at = None
        if d.get('fetched_at'):
            try:
                fetched_at = datetime.fromisoformat(d['fetched_at'])
            except (ValueError, TypeError):
                fetched_at = datetime.now()

        return ScreenerRawData(
            symbol=d.get('symbol', ''),
            company_name=d.get('company_name', ''),
            sector=d.get('sector', ''),
            industry=d.get('industry', ''),
            market_cap=d.get('market_cap', 0),
            current_price=d.get('current_price', 0),
            pe_ratio=d.get('pe_ratio', 0),
            book_value=d.get('book_value', 0),
            dividend_yield=d.get('dividend_yield', 0),
            roce=d.get('roce', 0),
            roe=d.get('roe', 0),
            face_value=d.get('face_value', 10),
            high_52w=d.get('high_52w', 0),
            low_52w=d.get('low_52w', 0),
            quarterly_results=d.get('quarterly_results', []),
            annual_pl=d.get('annual_pl', []),
            compounded_sales_growth=d.get('compounded_sales_growth', {}),
            compounded_profit_growth=d.get('compounded_profit_growth', {}),
            stock_price_cagr=d.get('stock_price_cagr', {}),
            return_on_equity=d.get('return_on_equity', {}),
            balance_sheet=d.get('balance_sheet', []),
            cash_flow=d.get('cash_flow', []),
            ratios=d.get('ratios', []),
            shareholding=d.get('shareholding', []),
            fetched_at=fetched_at,
            is_consolidated=d.get('is_consolidated', True),
            data_quality=d.get('data_quality', 'GOOD'),
        )

    # --- Number cleaning ---

    @staticmethod
    def _clean_number(text: str) -> Optional[float]:
        """Convert screener.in number strings to float.

        Handles:
          '19,26,956'  -> 1926956.0  (Indian comma notation)
          '25.1'       -> 25.1
          '-3.5%'      -> -3.5
          '₹ 648'      -> 648.0
          ''           -> None
          '--'         -> None
          'Cr.'        -> stripped
        """
        if not text:
            return None

        text = (
            text.strip()
            .replace('₹', '')
            .replace('Cr.', '')
            .replace('Cr', '')
            .replace('%', '')
            .replace('\u20b9', '')  # ₹ unicode
            .strip()
        )

        # Remove Indian-style commas
        text = text.replace(',', '')

        if not text or text in ('--', '-', 'NA', 'N/A', ''):
            return None

        try:
            return float(text)
        except ValueError:
            return None
