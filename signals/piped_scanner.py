"""Piped Scanner — Chain multiple scan filters sequentially.

Inspired by PKScreener's piped combinations.  Each filter stage receives
a list of symbols, fetches data, applies a test, and returns survivors.

Usage:
    pipe = (PipedScanner()
        .add(filter_stage2_uptrend, "Stage 2 Uptrend")
        .add(filter_vcp_forming, "VCP Pattern")
        .add(filter_volume_surge, "Volume Surge"))
    results = pipe.run(symbols, fetcher)

Pre-built pipes:
    SWING_BREAKOUT_PIPE — VCP + squeeze + volume
    MOMENTUM_PIPE — relative strength + EMA alignment + earnings
    VALUE_PIPE — PE + ROE + 52w low
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
import logging

import pandas as pd
import pandas_ta as ta

from config import EMA_SHORT, EMA_MEDIUM, EMA_LONG, VOLUME_MULTIPLIER

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of a single filter stage."""
    name: str
    input_count: int
    output_count: int
    survivors: List[str] = field(default_factory=list)
    eliminated: List[str] = field(default_factory=list)


@dataclass
class PipeReport:
    """Full report from a piped scan run."""
    pipe_name: str
    stages: List[FilterResult] = field(default_factory=list)
    final_survivors: List[str] = field(default_factory=list)
    details: Dict[str, Dict] = field(default_factory=dict)  # symbol → per-symbol info


FilterFn = Callable[[List[str], object], Tuple[List[str], Dict[str, Dict]]]


class PipedScanner:
    """Chain multiple scan filters sequentially."""

    def __init__(self, name: str = "custom"):
        self.name = name
        self.filters: List[Tuple[str, FilterFn]] = []

    def add(self, filter_fn: FilterFn, name: str) -> 'PipedScanner':
        """Add a filter stage. Chainable."""
        self.filters.append((name, filter_fn))
        return self

    def run(self, symbols: List[str], fetcher=None) -> PipeReport:
        """Run all filters in sequence. Returns a PipeReport."""
        report = PipeReport(pipe_name=self.name)
        candidates = list(symbols)
        all_details: Dict[str, Dict] = {}

        for stage_name, filter_fn in self.filters:
            input_count = len(candidates)
            if not candidates:
                report.stages.append(FilterResult(
                    name=stage_name, input_count=0, output_count=0))
                break

            try:
                survivors, stage_details = filter_fn(candidates, fetcher)
            except Exception as e:
                logger.warning(f"Filter '{stage_name}' failed: {e}")
                survivors = candidates  # on error, pass all through
                stage_details = {}

            eliminated = [s for s in candidates if s not in survivors]

            report.stages.append(FilterResult(
                name=stage_name,
                input_count=input_count,
                output_count=len(survivors),
                survivors=list(survivors),
                eliminated=eliminated,
            ))

            # Merge details
            for sym, detail in stage_details.items():
                all_details.setdefault(sym, {}).update(detail)

            candidates = survivors

        report.final_survivors = candidates
        report.details = all_details
        return report


# =============================================================================
# Helper: fetch data with error handling
# =============================================================================
def _fetch_daily(symbol: str, fetcher) -> Optional[pd.DataFrame]:
    """Fetch daily DataFrame using whatever fetcher is provided."""
    try:
        df = fetcher.fetch_stock_data(symbol, "daily")
        if df is not None and len(df) >= 50:
            return df
    except Exception:
        pass
    return None


# =============================================================================
# Filter functions
# =============================================================================

def filter_stage2_uptrend(symbols: List[str], fetcher) -> Tuple[List[str], Dict]:
    """Stage 2 uptrend: price > 50 EMA > 200 EMA."""
    survivors = []
    details = {}
    for sym in symbols:
        df = _fetch_daily(sym, fetcher)
        if df is None:
            continue
        ema50 = ta.ema(df['close'], length=EMA_MEDIUM)
        ema200 = ta.ema(df['close'], length=EMA_LONG)
        if ema50 is None or ema200 is None:
            continue
        close = df['close'].iloc[-1]
        e50 = ema50.iloc[-1]
        e200 = ema200.iloc[-1]
        if pd.notna(e50) and pd.notna(e200) and close > e50 > e200:
            survivors.append(sym)
            details[sym] = {'stage2': True, 'close': close, 'ema50': round(e50, 2), 'ema200': round(e200, 2)}
    return survivors, details


def filter_vcp_forming(symbols: List[str], fetcher) -> Tuple[List[str], Dict]:
    """VCP pattern detected (score >= 30)."""
    from indicators.vcp import VCPScanner
    survivors = []
    details = {}
    for sym in symbols:
        df = _fetch_daily(sym, fetcher)
        if df is None:
            continue
        scanner = VCPScanner(df)
        pattern = scanner.detect_vcp()
        if pattern and pattern.score >= 30:
            survivors.append(sym)
            details[sym] = {
                'vcp_score': pattern.score,
                'contractions': pattern.contractions,
                'pivot': pattern.pivot_price,
            }
    return survivors, details


def filter_ttm_squeeze_firing(symbols: List[str], fetcher) -> Tuple[List[str], Dict]:
    """TTM Squeeze is squeezing or has fired long."""
    from indicators.ttm_squeeze import TTMSqueeze
    survivors = []
    details = {}
    for sym in symbols:
        df = _fetch_daily(sym, fetcher)
        if df is None:
            continue
        squeeze = TTMSqueeze(df).analyze()
        if squeeze.signal in ('FIRE_LONG', 'SQUEEZING') and squeeze.momentum > 0:
            survivors.append(sym)
            details[sym] = {'squeeze_signal': squeeze.signal, 'momentum': squeeze.momentum}
    return survivors, details


def filter_volume_surge(symbols: List[str], fetcher) -> Tuple[List[str], Dict]:
    """Today's volume > 1.5x 20-day average."""
    survivors = []
    details = {}
    for sym in symbols:
        df = _fetch_daily(sym, fetcher)
        if df is None:
            continue
        vol_sma = ta.sma(df['volume'].astype(float), length=20)
        if vol_sma is None:
            continue
        latest_vol = df['volume'].iloc[-1]
        avg_vol = vol_sma.iloc[-1]
        if pd.notna(avg_vol) and avg_vol > 0:
            ratio = latest_vol / avg_vol
            if ratio >= VOLUME_MULTIPLIER:
                survivors.append(sym)
                details[sym] = {'volume_ratio': round(ratio, 2)}
    return survivors, details


def filter_above_all_emas(symbols: List[str], fetcher) -> Tuple[List[str], Dict]:
    """Price above 20, 50, and 200 EMA."""
    survivors = []
    details = {}
    for sym in symbols:
        df = _fetch_daily(sym, fetcher)
        if df is None:
            continue
        ema20 = ta.ema(df['close'], length=EMA_SHORT)
        ema50 = ta.ema(df['close'], length=EMA_MEDIUM)
        ema200 = ta.ema(df['close'], length=EMA_LONG)
        close = df['close'].iloc[-1]
        if (ema20 is not None and ema50 is not None and ema200 is not None and
                pd.notna(ema20.iloc[-1]) and pd.notna(ema50.iloc[-1]) and pd.notna(ema200.iloc[-1]) and
                close > ema20.iloc[-1] and close > ema50.iloc[-1] and close > ema200.iloc[-1]):
            survivors.append(sym)
            details[sym] = {'above_all_emas': True}
    return survivors, details


def filter_near_52w_high(symbols: List[str], fetcher) -> Tuple[List[str], Dict]:
    """Price within 10% of 52-week high."""
    survivors = []
    details = {}
    for sym in symbols:
        df = _fetch_daily(sym, fetcher)
        if df is None:
            continue
        high_52w = df['high'].tail(252).max()
        close = df['close'].iloc[-1]
        if high_52w > 0:
            pct_from_high = (high_52w - close) / high_52w * 100
            if pct_from_high <= 10:
                survivors.append(sym)
                details[sym] = {'pct_from_52w_high': round(pct_from_high, 1)}
    return survivors, details


def filter_narrow_range(symbols: List[str], fetcher) -> Tuple[List[str], Dict]:
    """NR7 or NR4+IB detected."""
    from indicators.narrow_range import NarrowRangeDetector
    survivors = []
    details = {}
    for sym in symbols:
        df = _fetch_daily(sym, fetcher)
        if df is None:
            continue
        nr = NarrowRangeDetector(df).detect()
        if nr['nr7'] or (nr['nr4'] and nr['inside_bar']):
            survivors.append(sym)
            details[sym] = {'nr_signal': nr['signal'], 'entry_long': nr['entry_long']}
    return survivors, details


def filter_rs_above_70(symbols: List[str], fetcher) -> Tuple[List[str], Dict]:
    """Relative Strength (3-month return percentile) > 70th percentile."""
    # Compute 3-month return for all symbols, then filter top 30%
    returns = {}
    for sym in symbols:
        df = _fetch_daily(sym, fetcher)
        if df is None or len(df) < 63:
            continue
        ret_3m = (df['close'].iloc[-1] / df['close'].iloc[-63] - 1) * 100
        returns[sym] = ret_3m

    if not returns:
        return [], {}

    sorted_syms = sorted(returns, key=returns.get, reverse=True)
    cutoff_idx = max(1, int(len(sorted_syms) * 0.30))
    top_30 = set(sorted_syms[:cutoff_idx])

    survivors = [s for s in symbols if s in top_30]
    details = {s: {'rs_3m_return': round(returns[s], 1)} for s in survivors if s in returns}
    return survivors, details


# =============================================================================
# Pre-built pipes
# =============================================================================

def create_swing_breakout_pipe() -> PipedScanner:
    """VCP + squeeze + volume confirmation."""
    return (PipedScanner("Swing Breakout")
            .add(filter_stage2_uptrend, "Stage 2 Uptrend")
            .add(filter_vcp_forming, "VCP Pattern")
            .add(filter_ttm_squeeze_firing, "TTM Squeeze")
            .add(filter_volume_surge, "Volume Surge"))


def create_momentum_pipe() -> PipedScanner:
    """Relative strength + EMA alignment."""
    return (PipedScanner("Momentum")
            .add(filter_rs_above_70, "Relative Strength > 70th pctile")
            .add(filter_above_all_emas, "Above All EMAs")
            .add(filter_near_52w_high, "Near 52W High"))


def create_narrow_range_pipe() -> PipedScanner:
    """NR7/IB setups in uptrending stocks."""
    return (PipedScanner("Narrow Range Breakout")
            .add(filter_stage2_uptrend, "Stage 2 Uptrend")
            .add(filter_narrow_range, "Narrow Range")
            .add(filter_above_all_emas, "Above All EMAs"))


PIPE_REGISTRY = {
    'swing_breakout': create_swing_breakout_pipe,
    'momentum': create_momentum_pipe,
    'narrow_range': create_narrow_range_pipe,
}
