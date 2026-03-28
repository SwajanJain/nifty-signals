# NIFTY SIGNALS — MASTER IMPROVEMENT PLAN

**Updated:** 2026-03-28
**Purpose:** Comprehensive roadmap for turning nifty-signals into a production-grade swing trading + long-term investing system.
**Approach:** Learn from the best open-source trading systems, adapt what works, build what's missing.

---

## TABLE OF CONTENTS

1. [Current System Audit](#1-current-system-audit)
2. [Phase 1: Data Foundation](#2-phase-1-data-foundation--replace-yfinance-fix-gaps)
3. [Phase 2: Swing Trading Patterns](#3-phase-2-swing-trading-patterns--entry-timing)
4. [Phase 3: Market Breadth & Context](#4-phase-3-market-breadth--context)
5. [Phase 4: Factor Scoring System](#5-phase-4-factor-scoring-system-for-investing)
6. [Phase 5: Risk Management Upgrade](#6-phase-5-risk-management-upgrade)
7. [Phase 6: Backtesting Engine](#7-phase-6-backtesting-engine)
8. [Phase 7: Automation & Alerts](#8-phase-7-automation--alerts)
9. [Phase 8: Web Dashboard](#9-phase-8-web-dashboard)
10. [Implementation Priority](#10-implementation-priority)
11. [Reference Repos](#11-reference-repos)

---

## 1. CURRENT SYSTEM AUDIT

### What We Have (Working)

| Module | Files | Status |
|--------|-------|--------|
| OHLCV data | `data/fetcher.py`, `data/reliable_fetcher.py` | Working (yfinance) |
| Technical indicators | `indicators/technical.py`, `indicators/*.py` | Working (pandas_ta) |
| 4 signal models | `models/momentum.py`, `breakout.py`, `trend_following.py`, `mean_reversion.py` | Working |
| Ensemble voting | `models/ensemble.py` | Working |
| Conviction scoring | `core/conviction.py` | Working |
| Market regime | `indicators/market_regime.py` | Working |
| Position sizing | `risk/position_sizing.py` | Working (Minervini/O'Neil/Seykota) |
| Exit strategy | `risk/exit_strategy.py` | Working (Legendary trader edition) |
| Fundamental analysis | `fundamentals/scorer.py`, `fundamentals/screens/*.py` | Working (recently fixed) |
| Tailwind analysis | `tailwinds/analyzer.py` | Working |
| Screener.in integration | `fundamentals/screener_fetcher.py` | Working |
| Deterministic pipeline | `scripts/run_pipeline.py` | Working |
| News/Reddit sentiment | `data/reddit_fetcher.py`, `scripts/build_news_context.py` | Working |

### What's Missing or Broken

| Gap | Impact | Priority |
|-----|--------|----------|
| yfinance unreliable for NSE | Data gaps, symbol failures | CRITICAL |
| No VCP/TTM Squeeze/NR patterns | Missing best swing entries | HIGH |
| FII/DII flow data broken | Druckenmiller gate fails | HIGH |
| Market breadth incomplete | Simons gate unreliable | HIGH |
| No CPR/Pivot levels | Missing key swing levels | MEDIUM |
| No factor scoring (momentum/value/quality) | Investing decisions ad-hoc | MEDIUM |
| No VaR/CVaR portfolio risk | Only per-trade ATR risk | MEDIUM |
| No backtesting validation | Can't prove edge exists | MEDIUM |
| No alerts (Telegram/email) | Manual monitoring only | LOW |
| No web dashboard | CLI-only interface | LOW |

---

## 2. PHASE 1: DATA FOUNDATION — Replace yfinance, Fix Gaps

### 1.1 Add jugaad-data as Primary NSE Data Source

**Why:** yfinance is unreliable for Indian stocks — symbol failures, stale data, rate limiting. jugaad-data fetches directly from NSE with built-in caching.

**Reference:** [jugaad-data](https://github.com/jugaad-py/jugaad-data) (502 stars, MIT)

**File:** `data/nse_fetcher.py` (NEW)

```python
from jugaad_data.nse import stock_df, NSELive
from datetime import date, timedelta

class NSEDataFetcher:
    """Direct NSE data fetcher — replaces yfinance for Indian stocks."""

    def fetch_historical(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """Fetch historical OHLCV from NSE bhavcopy."""
        to_date = date.today()
        from_date = to_date - timedelta(days=days)
        df = stock_df(symbol=symbol, from_date=from_date,
                      to_date=to_date, series="EQ")
        # Normalize column names to match our convention
        df.columns = [c.lower().replace(' ', '_') for c in df.columns]
        return df

    def fetch_live(self, symbol: str) -> dict:
        """Fetch real-time quote from NSE."""
        nse = NSELive()
        return nse.stock_quote(symbol)

    def fetch_index(self, index: str = "NIFTY 50") -> pd.DataFrame:
        """Fetch index historical data."""
        from jugaad_data.nse import index_df
        return index_df(index, from_date, to_date)
```

**Integration points:**
- `data/reliable_fetcher.py` — Add NSE as primary, yfinance as fallback
- `scripts/prepare_data.py` — Use NSE fetcher for pipeline runs
- Eliminates `SYMBOL_NOTES` / `KNOWN_FAILURES` workarounds in config.py

**Dependencies:** `pip install jugaad-data`

### 1.2 Add tvDatafeed as Multi-Timeframe Source

**Why:** Our `indicators/multi_timeframe.py` needs reliable multi-timeframe data. tvDatafeed provides 1min to monthly from TradingView.

**Reference:** [tvDatafeed](https://github.com/rongardF/tvdatafeed) (588 stars)

**File:** `data/tv_fetcher.py` (NEW)

```python
from tvDatafeed import TvDatafeed, Interval

class TradingViewFetcher:
    """TradingView data for multi-timeframe analysis."""

    INTERVALS = {
        '5m': Interval.in_5_minute,
        '15m': Interval.in_15_minute,
        '1h': Interval.in_1_hour,
        '4h': Interval.in_4_hour,
        'D': Interval.in_daily,
        'W': Interval.in_weekly,
        'M': Interval.in_monthly,
    }

    def __init__(self):
        self.tv = TvDatafeed()

    def fetch(self, symbol: str, interval: str = 'D', bars: int = 500) -> pd.DataFrame:
        return self.tv.get_hist(
            symbol=symbol, exchange='NSE',
            interval=self.INTERVALS[interval], n_bars=bars
        )
```

**Integration:** `indicators/multi_timeframe.py` — Replace yfinance MTF data with this.

### 1.3 Fix FII/DII Flow Data

**Why:** Druckenmiller gate — FIIs move Indian markets. Currently returning UNAVAILABLE.

**Reference:** [nsetools](https://github.com/vsjha18/nsetools) (885 stars), [jugaad-data](https://github.com/jugaad-py/jugaad-data)

**File:** `data/fii_dii_fetcher.py` (FIX)

```python
# Use jugaad-data for FII/DII data from NSE reports
from jugaad_data.nse import NSELive

def fetch_fii_dii_data() -> dict:
    nse = NSELive()
    # NSE provides daily FII/DII activity
    data = nse.fii_dii()
    return {
        'fii_buy': data['fii_buy_value'],
        'fii_sell': data['fii_sell_value'],
        'fii_net': data['fii_net_value'],
        'dii_buy': data['dii_buy_value'],
        'dii_sell': data['dii_sell_value'],
        'dii_net': data['dii_net_value'],
    }
```

### 1.4 Add nsetools for Real-Time Breadth

**Reference:** [nsetools](https://github.com/vsjha18/nsetools) (885 stars)

**File:** `data/market_breadth.py` (ENHANCE)

```python
from nsetools import Nse

def fetch_market_breadth() -> dict:
    nse = Nse()
    adv_dec = nse.get_advances_declines()
    top_gainers = nse.get_top_gainers()
    top_losers = nse.get_top_losers()
    high_52w = nse.get_52_week_high()
    low_52w = nse.get_52_week_low()

    return {
        'advances': len([x for x in adv_dec if x['advances'] > x['declines']]),
        'declines': len([x for x in adv_dec if x['declines'] > x['advances']]),
        'new_52w_highs': len(high_52w),
        'new_52w_lows': len(low_52w),
        'top_gainers': top_gainers[:5],
        'top_losers': top_losers[:5],
    }
```

**New dependencies for Phase 1:**
```
jugaad-data>=0.4.0
tvDatafeed>=2.1.0
nsetools>=1.0.0
```

---

## 3. PHASE 2: SWING TRADING PATTERNS & ENTRY TIMING

### 2.1 VCP Scanner (Volatility Contraction Pattern) — Minervini

**Why:** The single best swing trading entry pattern. Price contracts in 2-6 progressively smaller pullbacks before breaking out. Already aligns with our Minervini stop-loss methodology.

**Reference:** [PKScreener](https://github.com/pkjmesra/PKScreener), [TraderLion VCP Guide](https://traderlion.com/technical-analysis/volatility-contraction-pattern/)

**File:** `indicators/vcp.py` (NEW)

**Algorithm:**
1. Stock must be in Stage 2 uptrend (price > 50 EMA > 200 EMA)
2. Identify 2-6 contractions where each pullback is smaller than the previous
3. Volume must decline during contractions
4. Breakout occurs on volume surge above the pivot point

```python
@dataclass
class VCPPattern:
    symbol: str
    contractions: int                # Number of contractions (2-6)
    pullbacks: List[float]           # Pullback percentages [20%, 12%, 5%]
    volume_declining: bool           # Volume decreasing across contractions
    pivot_price: float               # Breakout level
    current_contraction_pct: float   # Latest contraction size
    stage_2: bool                    # In uptrend (price > 50EMA > 200EMA)
    score: int                       # 0-100

def detect_vcp(df: pd.DataFrame, min_contractions: int = 2) -> Optional[VCPPattern]:
    """
    Detect Volatility Contraction Pattern.

    Rules (Minervini):
    - Stock in Stage 2 uptrend
    - Minimum 2 contractions, each smaller than previous
    - Pullback sequence decreasing: e.g., 25% -> 12% -> 5%
    - Volume declining during base formation
    - Price near pivot (within 5% of breakout level)

    Scoring:
    - 3+ contractions: +20
    - Volume declining: +20
    - Latest contraction < 10%: +20 (tight)
    - Price within 3% of pivot: +20 (ready to break)
    - Stage 2 confirmed: +20
    """
    # Implementation uses swing high/low detection to find contractions
    # Compare each successive pullback depth
    # Verify volume profile declining across base
    pass
```

**Parameters:**
- Min contractions: 2
- Max base length: 65 trading days (Minervini)
- Pullback thresholds: First 15-35%, subsequent each 40-60% smaller
- Volume: Must decline 30%+ from first to last contraction

### 2.2 TTM Squeeze Scanner — John Carter

**Why:** Identifies periods of extreme volatility compression before explosive moves. Perfect pre-breakout filter.

**Reference:** [PKScreener](https://github.com/pkjmesra/PKScreener), [ChartSchool TTM Squeeze](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/ttm-squeeze)

**File:** `indicators/ttm_squeeze.py` (NEW)

**Algorithm:**
The squeeze fires when Bollinger Bands (20, 2.0) move inside Keltner Channels (20, 1.5 ATR).

```python
@dataclass
class SqueezeSignal:
    is_squeezing: bool       # BB inside KC = squeeze ON
    squeeze_bars: int        # How many bars in squeeze
    momentum: float          # Linear regression of (close - midline of KC+BB)
    momentum_rising: bool    # Momentum histogram increasing
    momentum_color: str      # 'green' (rising positive), 'red' (falling negative)
    signal: str              # 'FIRE_LONG', 'FIRE_SHORT', 'SQUEEZING', 'NO_SQUEEZE'

def calculate_ttm_squeeze(df: pd.DataFrame,
                           bb_length: int = 20, bb_mult: float = 2.0,
                           kc_length: int = 20, kc_mult: float = 1.5) -> SqueezeSignal:
    """
    TTM Squeeze Indicator (John Carter).

    Components:
    1. Squeeze dots: BB inside KC = squeeze ON (low volatility)
    2. Momentum histogram: Linear regression of (close - avg(KC_mid, BB_mid))

    Signal:
    - Squeeze ON + momentum turning positive = FIRE_LONG
    - Squeeze ON + momentum turning negative = FIRE_SHORT
    - Squeeze has been ON for 6+ bars = high probability
    """
    # Bollinger Bands
    bb_mid = df['close'].rolling(bb_length).mean()
    bb_std = df['close'].rolling(bb_length).std()
    bb_upper = bb_mid + bb_mult * bb_std
    bb_lower = bb_mid - bb_mult * bb_std

    # Keltner Channels
    kc_mid = df['close'].rolling(kc_length).mean()
    atr = ta.atr(df['high'], df['low'], df['close'], length=kc_length)
    kc_upper = kc_mid + kc_mult * atr
    kc_lower = kc_mid - kc_mult * atr

    # Squeeze: BB inside KC
    squeeze = (bb_lower > kc_lower) & (bb_upper < kc_upper)

    # Momentum: Linear regression of delta
    delta = df['close'] - (kc_mid + bb_mid) / 2
    # Use scipy linregress for momentum slope
    pass
```

**Parameters (Carter defaults):**
- BB: 20 period, 2.0 std dev
- KC: 20 period, 1.5 ATR multiplier
- Squeeze threshold: 6+ bars for high probability
- Momentum: Linear regression length 20

### 2.3 NR4/NR7 Narrow Range Scanner

**Why:** Narrow range days (smallest range in 4 or 7 days) predict imminent breakouts. Proven swing entry trigger.

**Reference:** [PKScreener](https://github.com/pkjmesra/PKScreener)

**File:** `indicators/narrow_range.py` (NEW)

```python
def detect_narrow_range(df: pd.DataFrame) -> dict:
    """
    NR4: Today's range is the narrowest of last 4 days.
    NR7: Today's range is the narrowest of last 7 days.

    Combined with inside bar = NR4/IB or NR7/IB (strongest signal).
    """
    ranges = df['high'] - df['low']
    latest_range = ranges.iloc[-1]

    nr4 = latest_range <= ranges.iloc[-4:].min()
    nr7 = latest_range <= ranges.iloc[-7:].min()

    # Inside bar: today's high < yesterday's high AND today's low > yesterday's low
    inside_bar = (df['high'].iloc[-1] < df['high'].iloc[-2] and
                  df['low'].iloc[-1] > df['low'].iloc[-2])

    return {
        'nr4': nr4,
        'nr7': nr7,
        'inside_bar': inside_bar,
        'nr7_ib': nr7 and inside_bar,  # Strongest signal
        'range_pct': latest_range / df['close'].iloc[-1] * 100,
        'signal': 'STRONG' if nr7 and inside_bar else 'MODERATE' if nr7 else 'MILD' if nr4 else 'NONE',
        'entry_long': df['high'].iloc[-1],   # Break above today's high
        'entry_short': df['low'].iloc[-1],   # Break below today's low
    }
```

### 2.4 CPR (Central Pivot Range)

**Why:** Most popular swing/intraday level system among Indian traders. Identifies support, resistance, and trend direction.

**Reference:** [NSE-Stock-Scanner](https://github.com/deshwalmahesh/NSE-Stock-Scanner), [Zerodha Varsity CPR](https://zerodha.com/varsity/chapter/the-central-pivot-range/)

**File:** `indicators/cpr.py` (NEW)

```python
@dataclass
class CPRLevels:
    pivot: float         # P = (H + L + C) / 3
    top_cpr: float       # TC = (P - BC) + P
    bottom_cpr: float    # BC = (H + L) / 2
    r1: float            # R1 = 2*P - L
    r2: float            # R2 = P + (H - L)
    s1: float            # S1 = 2*P - H
    s2: float            # S2 = P - (H - L)
    width_pct: float     # CPR width as % of price (narrow = trending)
    trend: str           # 'BULLISH' if close > TC, 'BEARISH' if close < BC

def calculate_cpr(high: float, low: float, close: float,
                  current_price: float = None) -> CPRLevels:
    """
    Calculate CPR from previous session's HLC.

    For swing trading: Use weekly HLC for next week's levels.
    For intraday: Use daily HLC for next day's levels.

    Narrow CPR (<0.5% width) = strong trending day expected.
    Wide CPR (>1.5% width) = rangebound day expected.
    """
    pivot = (high + low + close) / 3
    bc = (high + low) / 2
    tc = (pivot - bc) + pivot

    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)

    width_pct = abs(tc - bc) / pivot * 100
    trend = 'BULLISH' if current_price and current_price > tc else \
            'BEARISH' if current_price and current_price < bc else 'NEUTRAL'

    return CPRLevels(pivot=pivot, top_cpr=tc, bottom_cpr=bc,
                     r1=r1, r2=r2, s1=s1, s2=s2,
                     width_pct=width_pct, trend=trend)
```

### 2.5 Enhanced Candlestick Patterns

**Why:** Our `indicators/candlestick.py` has basics. NSE-Stock-Scanner adds V-patterns, Three White Soldiers, and Doji variants that we're missing.

**Reference:** [NSE-Stock-Scanner](https://github.com/deshwalmahesh/NSE-Stock-Scanner)

**File:** `indicators/candlestick.py` (ENHANCE)

Add:
- V-Pattern (sharp reversal after steep decline)
- Three White Soldiers / Three Black Crows (strong momentum confirmation)
- Multiple Doji variants (Dragonfly, Gravestone, Long-legged)
- Morning Star / Evening Star (3-candle reversal)

### 2.6 Piped Scanner Architecture

**Why:** PKScreener's most powerful feature — chain multiple scan criteria. "Volume surge + VCP + TTM Squeeze firing" catches the best setups.

**Reference:** [PKScreener](https://github.com/pkjmesra/PKScreener) (21 pre-built piped combinations)

**File:** `signals/piped_scanner.py` (NEW)

```python
class PipedScanner:
    """Chain multiple scan filters sequentially."""

    def __init__(self):
        self.filters = []

    def add(self, filter_fn, name: str):
        """Add a filter stage. Each receives and returns a list of symbols."""
        self.filters.append((name, filter_fn))
        return self  # Chainable

    def run(self, universe: List[str]) -> List[ScanResult]:
        """Run all filters in sequence."""
        candidates = universe
        for name, filter_fn in self.filters:
            candidates = filter_fn(candidates)
            if not candidates:
                break
        return candidates

# Pre-built pipes
SWING_BREAKOUT_PIPE = (
    PipedScanner()
    .add(filter_stage2_uptrend, "Stage 2 Uptrend")
    .add(filter_vcp_forming, "VCP Pattern")
    .add(filter_ttm_squeeze_firing, "TTM Squeeze")
    .add(filter_volume_surge, "Volume Confirmation")
)

MOMENTUM_PIPE = (
    PipedScanner()
    .add(filter_rs_above_70, "Relative Strength > 70")
    .add(filter_above_all_emas, "Above 20/50/200 EMA")
    .add(filter_earnings_acceleration, "Earnings Accelerating")
    .add(filter_fii_buying, "FII Buying")
)

VALUE_PIPE = (
    PipedScanner()
    .add(filter_pe_below_15, "PE < 15")
    .add(filter_roe_above_15, "ROE > 15%")
    .add(filter_consistent_growth, "5Y Consistent Growth")
    .add(filter_near_52w_low, "Near 52-Week Low")
)
```

### 2.7 Bollinger Band Pattern Recognition

**Why:** We use BB as simple bands. quant-trading recognizes W-bottoms and M-tops ON the bands — proven alpha source.

**Reference:** [quant-trading](https://github.com/je-suis-tm/quant-trading) (9,500 stars)

**File:** `indicators/bb_patterns.py` (NEW)

```python
def detect_bb_patterns(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> dict:
    """
    Bollinger Band pattern recognition.

    W-Bottom: Price touches lower BB twice with a higher second low.
    M-Top: Price touches upper BB twice with a lower second high.
    Squeeze: BB width contracts to minimum (< 20-period low of width).
    Walking the bands: Price stays above/below middle band for 5+ bars.
    """
    bb = ta.bbands(df['close'], length=period, std=std)
    # Detect W-bottom: two touches of lower band with rising second touch
    # Detect M-top: two touches of upper band with falling second touch
    # Detect squeeze: bandwidth at N-period low
    pass
```

### 2.8 RSI Divergence Pattern Detection

**Why:** Standard RSI checks OB/OS. Detecting head-shoulder patterns ON the RSI curve itself is more sophisticated and higher win-rate.

**Reference:** [quant-trading](https://github.com/je-suis-tm/quant-trading)

**File:** `indicators/divergence.py` (ENHANCE)

Add to existing divergence detection:
- Bullish divergence: Price makes lower low, RSI makes higher low
- Bearish divergence: Price makes higher high, RSI makes lower high
- Hidden divergence (trend continuation)
- RSI trendline breaks

---

## 4. PHASE 3: MARKET BREADTH & CONTEXT

### 3.1 TICK/TRIN Market Mood Indicators

**Why:** Professional-grade breadth indicators. TICK measures net advancing stocks; TRIN measures volume distribution.

**Reference:** [NSE-Stock-Scanner](https://github.com/deshwalmahesh/NSE-Stock-Scanner)

**File:** `data/market_breadth.py` (ENHANCE)

```python
def calculate_trin(advances: int, declines: int,
                   advancing_volume: float, declining_volume: float) -> dict:
    """
    TRIN (Arms Index) = (Advancing Issues / Declining Issues)
                       / (Advancing Volume / Declining Volume)

    TRIN < 1.0 = Bullish (money flowing into advancing stocks)
    TRIN > 1.0 = Bearish (money flowing into declining stocks)
    TRIN > 2.0 = Panic selling (contrarian buy signal)
    TRIN < 0.5 = Euphoria (contrarian sell signal)
    """
    if declines == 0 or declining_volume == 0:
        return {'trin': 0, 'signal': 'UNDEFINED'}

    ad_ratio = advances / declines
    vol_ratio = advancing_volume / declining_volume
    trin = ad_ratio / vol_ratio

    if trin > 2.0:
        signal = 'PANIC_SELLING'  # Contrarian buy
    elif trin > 1.0:
        signal = 'BEARISH'
    elif trin > 0.5:
        signal = 'BULLISH'
    else:
        signal = 'EUPHORIA'  # Contrarian sell

    return {'trin': round(trin, 2), 'signal': signal}
```

### 3.2 McClellan Oscillator & Summation Index

**Why:** Smoothed breadth momentum. Better than raw A/D ratio for trend confirmation.

**File:** `indicators/mcclellan.py` (NEW)

```python
def mcclellan_oscillator(advances: pd.Series, declines: pd.Series) -> pd.Series:
    """
    McClellan Oscillator = EMA19(A-D) - EMA39(A-D)
    Positive = Bullish breadth momentum
    Crosses zero = Breadth thrust signal
    """
    ad_diff = advances - declines
    ema19 = ad_diff.ewm(span=19).mean()
    ema39 = ad_diff.ewm(span=39).mean()
    return ema19 - ema39
```

---

## 5. PHASE 4: FACTOR SCORING SYSTEM (For Investing)

### 4.1 Multi-Factor Model

**Why:** Systematic factor scoring replaces ad-hoc fundamental analysis. Combine momentum, value, quality, and growth factors into a single composite score for long-term stock selection.

**Reference:** [QuantMuse](https://github.com/0xemmkty/QuantMuse) (2,100 stars), [Automated-Fundamental-Analysis](https://github.com/faizancodes/Automated-Fundamental-Analysis) (224 stars)

**File:** `fundamentals/factor_model.py` (NEW)

```python
@dataclass
class FactorScores:
    symbol: str
    momentum_score: float    # 0-100
    value_score: float       # 0-100
    quality_score: float     # 0-100
    growth_score: float      # 0-100
    low_vol_score: float     # 0-100
    composite_score: float   # Weighted blend
    sector_rank: int         # Rank within sector
    universe_rank: int       # Rank within universe
    percentile: float        # 0-100 percentile

class FactorModel:
    """
    Multi-factor scoring system for long-term investing.

    Factors (each scored 0-100 as percentile within sector):
    1. Momentum: 12M return (skip last month), 6M return, 3M return
    2. Value: PE, PB, EV/EBITDA, FCF yield, earnings yield
    3. Quality: ROE stability, ROCE consistency, low debt, cash generation
    4. Growth: Revenue CAGR, EPS CAGR, earnings acceleration
    5. Low Volatility: 1Y standard deviation, max drawdown, beta

    Scoring methodology (from Automated-Fundamental-Analysis):
    - For each factor, compute sector-wide distribution
    - Remove outliers (>3 std dev)
    - Score each stock relative to sector percentile
    - Inverse scoring for "lower is better" metrics (PE, volatility)
    """

    FACTOR_WEIGHTS = {
        'momentum': 0.25,
        'value': 0.20,
        'quality': 0.25,
        'growth': 0.20,
        'low_vol': 0.10,
    }

    def score_momentum(self, df: pd.DataFrame) -> float:
        """
        Momentum factor (Jegadeesh & Titman, 1993).
        12-1 month return: Skip last month to avoid reversal.
        """
        returns_12m = (df['close'].iloc[-1] / df['close'].iloc[-252] - 1) * 100
        returns_6m = (df['close'].iloc[-1] / df['close'].iloc[-126] - 1) * 100
        returns_1m = (df['close'].iloc[-1] / df['close'].iloc[-21] - 1) * 100
        # 12-1 month: subtract last month to avoid short-term reversal
        momentum_12_1 = returns_12m - returns_1m
        return momentum_12_1  # Will be percentile-ranked later

    def score_value(self, profile: FundamentalProfile) -> float:
        """Value factor — lower PE/PB/EV is better."""
        # Inverse score: PE of 10 > PE of 30
        # Percentile within sector (lower = better = higher score)
        pass

    def score_quality(self, profile: FundamentalProfile) -> float:
        """Quality factor — consistent high returns."""
        # ROE stability (low std dev of 5Y ROE)
        # ROCE consistency (all 5 years > 15%)
        # Debt-free bonus
        # OCF > Net Profit (earnings quality)
        pass

    def compute_composite(self, factor_scores: dict) -> float:
        """Weighted composite with sector-relative percentile normalization."""
        composite = sum(
            self.FACTOR_WEIGHTS[factor] * score
            for factor, score in factor_scores.items()
        )
        return round(composite, 1)
```

### 4.2 Sector-Relative Scoring

**Why:** A PE of 15 means different things for IT vs Banking. Factor scores must be relative to sector peers.

**Reference:** [Automated-Fundamental-Analysis](https://github.com/faizancodes/Automated-Fundamental-Analysis)

**Method:**
1. Group stocks by sector
2. For each metric, compute sector mean and std dev
3. Remove outliers (>3 std dev)
4. Score = percentile rank within sector
5. Inverse for "lower is better" metrics

```python
def sector_relative_score(value: float, sector_values: List[float],
                           lower_is_better: bool = False) -> float:
    """Score a metric relative to sector peers (0-100 percentile)."""
    # Remove outliers
    mean = np.mean(sector_values)
    std = np.std(sector_values)
    filtered = [v for v in sector_values if abs(v - mean) < 3 * std]

    if not filtered:
        return 50  # Neutral

    rank = sum(1 for v in filtered if v <= value) / len(filtered) * 100
    return (100 - rank) if lower_is_better else rank
```

### 4.3 Integrate Factor Scores into Composite Analyzer

**Current:** `tailwinds/analyzer.py` CompositeAnalyzer blends fundamental + tailwind.
**Enhancement:** Add factor scores as a third dimension.

```python
# Updated composite:
# 40% Fundamental quality (from scorer.py)
# 25% Factor momentum+value (from factor_model.py)
# 20% Tailwind (from tailwinds/analyzer.py)
# 15% Technical position (from indicators)
```

---

## 6. PHASE 5: RISK MANAGEMENT UPGRADE

### 5.1 Portfolio-Level VaR/CVaR

**Why:** Our current risk is per-trade ATR. Need portfolio-level risk: "What's the max I can lose in a bad week across ALL positions?"

**Reference:** [QuantMuse](https://github.com/0xemmkty/QuantMuse), [PyQuant VaR Guide](https://www.pyquantnews.com/free-python-resources/risk-metrics-in-python-var-and-cvar-guide)

**File:** `risk/portfolio_risk.py` (NEW)

```python
import numpy as np
from scipy import stats

class PortfolioRiskManager:
    """Portfolio-level risk metrics beyond per-trade ATR."""

    def calculate_var(self, returns: pd.Series, confidence: float = 0.95,
                      method: str = 'historical') -> float:
        """
        Value at Risk — maximum expected loss at given confidence.

        Methods:
        - 'historical': Direct percentile of historical returns
        - 'parametric': Assumes normal distribution (faster, less accurate)

        Example: 95% VaR of -2.5% means there's a 5% chance of losing
        more than 2.5% on any given day.
        """
        if method == 'historical':
            return np.percentile(returns, (1 - confidence) * 100)
        else:
            mean = returns.mean()
            std = returns.std()
            return mean + std * stats.norm.ppf(1 - confidence)

    def calculate_cvar(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """
        Conditional VaR (Expected Shortfall) — average loss beyond VaR.
        Answers: "When things go bad, HOW bad on average?"
        """
        var = self.calculate_var(returns, confidence)
        tail_losses = returns[returns <= var]
        return tail_losses.mean() if len(tail_losses) > 0 else var

    def portfolio_var(self, positions: List[dict], returns_data: Dict[str, pd.Series],
                      confidence: float = 0.95) -> dict:
        """
        Combined portfolio VaR considering correlations.
        Not just sum of individual VaRs — accounts for diversification.
        """
        # Weight by position value
        weights = np.array([p['position_value'] for p in positions])
        weights = weights / weights.sum()

        # Covariance matrix
        symbols = [p['symbol'] for p in positions]
        returns_matrix = pd.DataFrame({s: returns_data[s] for s in symbols})
        cov_matrix = returns_matrix.cov()

        # Portfolio variance = w' * Cov * w
        port_var = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        port_var_amount = port_var * stats.norm.ppf(1 - confidence) * sum(
            p['position_value'] for p in positions
        )

        return {
            'portfolio_var_pct': round(port_var * 100, 2),
            'portfolio_var_amount': round(abs(port_var_amount), 0),
            'confidence': confidence,
            'diversification_benefit': 'YES' if port_var < sum(
                weights * returns_matrix.std()
            ) else 'MINIMAL',
        }
```

### 5.2 Correlation-Aware Position Sizing

**Enhancement to:** `risk/position_sizing.py`

```python
def adjust_for_correlation(self, new_position: dict,
                           existing_positions: List[dict],
                           returns_data: dict) -> float:
    """
    Reduce position size if highly correlated with existing positions.

    If correlation > 0.7 with any existing position:
    - Reduce size by 50%
    If 2+ existing positions in same sector:
    - Reduce to minimum size
    """
    correlations = []
    for pos in existing_positions:
        if pos['symbol'] in returns_data and new_position['symbol'] in returns_data:
            corr = returns_data[pos['symbol']].corr(
                returns_data[new_position['symbol']]
            )
            correlations.append(corr)

    max_corr = max(correlations) if correlations else 0

    if max_corr > 0.7:
        return 0.5  # Half size
    elif max_corr > 0.5:
        return 0.75  # Three-quarter size
    return 1.0  # Full size
```

---

## 7. PHASE 6: BACKTESTING ENGINE

### 6.1 Integrate backtesting.py

**Why:** Validate our strategies with proper backtests. Currently `backtest/engine.py` exists but is basic.

**Reference:** [backtesting.py](https://github.com/kernc/backtesting.py) (8,100 stars)

**File:** `backtest/bt_strategies.py` (NEW)

```python
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import pandas_ta as ta

class MinerviniSwing(Strategy):
    """Backtest our Minervini-inspired swing strategy."""

    atr_period = 14
    atr_stop_mult = 2.0
    target_r = 2.0

    def init(self):
        close = pd.Series(self.data.Close)
        self.ema20 = self.I(ta.ema, close, length=20)
        self.ema50 = self.I(ta.ema, close, length=50)
        self.ema200 = self.I(ta.ema, close, length=200)
        self.atr = self.I(ta.atr, pd.Series(self.data.High),
                          pd.Series(self.data.Low), close, length=self.atr_period)
        self.rsi = self.I(ta.rsi, close, length=14)

    def next(self):
        # Stage 2: Price > 50EMA > 200EMA
        if (self.data.Close[-1] > self.ema50[-1] > self.ema200[-1]
                and self.rsi[-1] > 50
                and not self.position):
            stop = self.data.Close[-1] - self.atr[-1] * self.atr_stop_mult
            target = self.data.Close[-1] + self.atr[-1] * self.atr_stop_mult * self.target_r
            self.buy(sl=stop, tp=target)

# Run backtest
bt = Backtest(data, MinerviniSwing, cash=1000000, commission=0.001)
stats = bt.run()
# Produces: Return %, Sharpe, Sortino, Max DD, Win Rate, # Trades, etc.
bt.plot()  # Interactive HTML chart

# Optimize parameters
stats = bt.optimize(
    atr_period=range(10, 25, 2),
    atr_stop_mult=[1.5, 2.0, 2.5, 3.0],
    target_r=[1.5, 2.0, 3.0, 4.0],
    maximize='Sharpe Ratio'
)
```

**Metrics produced by backtesting.py:**
- Return %, CAGR, Volatility (Ann.)
- Sharpe Ratio, Sortino Ratio, Calmar Ratio
- Max Drawdown %, Avg Drawdown %
- Win Rate %, Best/Worst Trade
- Avg Trade Duration, # Trades
- Kelly Criterion, Profit Factor
- Equity curve visualization

### 6.2 Walk-Forward Validation

**Enhancement to:** `backtest/walk_forward.py`

Use backtesting.py's optimization on in-sample period, then validate on out-of-sample:
- Train: 2 years of data
- Test: 6 months forward
- Roll forward by 3 months
- Average out-of-sample Sharpe must be > 1.0

**New dependency:** `pip install backtesting`

---

## 8. PHASE 7: AUTOMATION & ALERTS

### 7.1 Telegram Alert Bot

**Reference:** [PKScreener](https://github.com/pkjmesra/PKScreener) (Telegram integration)

**File:** `alerts/telegram_bot.py` (NEW)

```python
import requests

class TelegramAlerts:
    def __init__(self, bot_token: str, chat_id: str):
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.chat_id = chat_id

    def send_signal(self, decision: dict):
        """Send trading signal to Telegram."""
        if decision['decision'] == 'NO_TRADE':
            msg = f"No trade today.\nReason: {decision['reason']}"
        else:
            msg = (
                f"SIGNAL: {decision['signal']} {decision['symbol']}\n"
                f"Entry: Rs {decision['entry']}\n"
                f"Stop: Rs {decision['stop']} ({decision['stop_type']})\n"
                f"T1: Rs {decision['targets']['target_1']} (2R)\n"
                f"T2: Rs {decision['targets']['target_2']} (4R)\n"
                f"Conviction: {decision['conviction']}/100\n"
                f"Shares: {decision['position_size']}"
            )
        self.send(msg)

    def send(self, text: str):
        requests.post(f"{self.base_url}/sendMessage",
                      json={'chat_id': self.chat_id, 'text': text})
```

### 7.2 Scheduled Daily Pipeline

**File:** `scripts/daily_cron.sh` (NEW)

```bash
#!/bin/bash
# Run at 8:45 AM IST (before market open)
cd /Users/swajanjain/Documents/Projects/nifty-signals

# 1. Fetch global context
python3 scripts/build_context.py

# 2. Run full pipeline
python3 scripts/run_pipeline.py

# 3. Send alert
python3 scripts/send_report.py --telegram
```

---

## 9. PHASE 8: WEB DASHBOARD

### 8.1 Streamlit Dashboard

**Why:** CLI is powerful but a dashboard provides at-a-glance overview. Minimal effort with Streamlit.

**Reference:** [Screeni-py](https://github.com/pranjal-joshi/Screeni-py) (676 stars, Streamlit-based)

**File:** `dashboard/app.py` (NEW)

```python
import streamlit as st

st.set_page_config(page_title="Nifty Signals", layout="wide")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Scan", "Fundamentals", "Portfolio"])

with tab1:
    # Market regime, breadth, FII/DII, sector strength
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Market Regime", regime, delta=regime_change)
    with col2:
        st.metric("Portfolio Heat", f"{heat}%", delta=f"{heat_change}%")
    with col3:
        st.metric("FII Net", f"Rs {fii_net} Cr", delta=f"{fii_trend}")

with tab2:
    # Scan results with TradingView chart links
    strategy = st.selectbox("Strategy", ["VCP", "TTM Squeeze", "Breakout", "Value"])
    results = run_scan(strategy)
    st.dataframe(results)

with tab3:
    # Fundamental analysis
    symbol = st.text_input("Symbol")
    if symbol:
        display_fundamental_analysis(symbol)

with tab4:
    # Open positions, P&L tracking
    display_portfolio()
```

**New dependency:** `pip install streamlit`

---

## 10. IMPLEMENTATION PRIORITY

### Sprint 1 (Week 1-2): Data Foundation
```
[P0] Add jugaad-data as primary NSE fetcher
[P0] Fix FII/DII data with nsetools/jugaad-data
[P0] Enhance market breadth with real A/D data
[P1] Add tvDatafeed for multi-timeframe
```

### Sprint 2 (Week 3-4): Swing Trading Patterns
```
[P0] Implement VCP scanner
[P0] Implement TTM Squeeze
[P1] Implement NR4/NR7 narrow range
[P1] Add CPR levels
[P1] Build piped scanner architecture
```

### Sprint 3 (Week 5-6): Investing & Risk
```
[P0] Build multi-factor scoring model
[P0] Add sector-relative percentile scoring
[P1] Implement portfolio VaR/CVaR
[P1] Add correlation-aware sizing
```

### Sprint 4 (Week 7-8): Validation & Polish
```
[P0] Integrate backtesting.py, validate strategies
[P1] Walk-forward optimization
[P1] Telegram alerts
[P2] Streamlit dashboard (basic)
```

### Sprint 5 (Week 9-10): Advanced Patterns
```
[P1] Bollinger Band pattern recognition (W/M)
[P1] RSI divergence enhancement
[P2] McClellan Oscillator
[P2] TRIN indicator
[P2] Enhanced candlestick patterns
```

---

## 11. REFERENCE REPOS

### Primary References (Code/Architecture)
| Repo | Stars | What to Take | License |
|------|-------|-------------|---------|
| [PKScreener](https://github.com/pkjmesra/PKScreener) | 325 | VCP, TTM Squeeze, NR4/NR7, piped scanners | MIT |
| [OpenAlgo](https://github.com/marketcalls/openalgo) | 1,600 | Broker abstraction, webhook alerts, sandbox mode | AGPL |
| [quant-trading](https://github.com/je-suis-tm/quant-trading) | 9,500 | BB pattern recognition, RSI patterns, Dual Thrust | - |
| [QuantMuse](https://github.com/0xemmkty/QuantMuse) | 2,100 | Factor models, VaR/CVaR, risk parity | MIT |
| [backtesting.py](https://github.com/kernc/backtesting.py) | 8,100 | Backtesting engine, optimization, metrics | AGPL |
| [NSE-Stock-Scanner](https://github.com/deshwalmahesh/NSE-Stock-Scanner) | 298 | TICK/TRIN, CPR, candlestick patterns | - |

### Data Sources
| Repo | Stars | What to Take | License |
|------|-------|-------------|---------|
| [jugaad-data](https://github.com/jugaad-py/jugaad-data) | 502 | NSE historical data, F&O, RBI rates | MIT |
| [nsetools](https://github.com/vsjha18/nsetools) | 885 | Real-time NSE data, breadth, gainers/losers | MIT |
| [tvDatafeed](https://github.com/rongardF/tvdatafeed) | 588 | Multi-timeframe TradingView data | MIT |

### UI/UX Reference
| Repo | Stars | What to Take | License |
|------|-------|-------------|---------|
| [Screeni-py](https://github.com/pranjal-joshi/Screeni-py) | 676 | Streamlit dashboard pattern, TradingView links | MIT |
| [Automated-Fundamental-Analysis](https://github.com/faizancodes/Automated-Fundamental-Analysis) | 224 | Sector-relative scoring, Streamlit UI | - |

---

## NEW DEPENDENCIES SUMMARY

```
# Data sources
jugaad-data>=0.4.0        # NSE direct data
tvDatafeed>=2.1.0         # TradingView multi-TF
nsetools>=1.0.0           # Real-time NSE breadth

# Backtesting
backtesting>=0.3.3        # Strategy backtesting + optimization

# Risk
riskfolio-lib>=4.0.0      # Portfolio optimization (optional)

# Alerts
python-telegram-bot>=20.0 # Telegram alerts

# Dashboard
streamlit>=1.30.0         # Web dashboard

# Already have
scipy>=1.10.0             # VaR calculations (already installed)
```

---

## CHECKLIST

### Data Foundation
- [ ] Add jugaad-data as primary NSE fetcher (`data/nse_fetcher.py`)
- [ ] Add tvDatafeed for multi-timeframe (`data/tv_fetcher.py`)
- [ ] Fix FII/DII flow data (`data/fii_dii_fetcher.py`)
- [ ] Enhance market breadth with nsetools (`data/market_breadth.py`)

### Swing Trading Patterns
- [ ] VCP scanner (`indicators/vcp.py`)
- [ ] TTM Squeeze (`indicators/ttm_squeeze.py`)
- [ ] NR4/NR7 narrow range (`indicators/narrow_range.py`)
- [ ] CPR levels (`indicators/cpr.py`)
- [ ] Piped scanner architecture (`signals/piped_scanner.py`)
- [ ] BB pattern recognition (`indicators/bb_patterns.py`)
- [ ] RSI divergence enhancement (`indicators/divergence.py`)
- [ ] Enhanced candlestick patterns (`indicators/candlestick.py`)

### Investing
- [ ] Multi-factor scoring model (`fundamentals/factor_model.py`)
- [ ] Sector-relative percentile scoring
- [ ] Integrate factors into composite analyzer
- [ ] McClellan Oscillator (`indicators/mcclellan.py`)

### Risk Management
- [ ] Portfolio VaR/CVaR (`risk/portfolio_risk.py`)
- [ ] Correlation-aware position sizing
- [ ] TRIN indicator for breadth risk

### Backtesting
- [ ] Integrate backtesting.py (`backtest/bt_strategies.py`)
- [ ] Walk-forward validation
- [ ] Validate all strategies on 3+ years of data

### Automation & UI
- [ ] Telegram alert bot (`alerts/telegram_bot.py`)
- [ ] Daily cron pipeline (`scripts/daily_cron.sh`)
- [ ] Streamlit dashboard (`dashboard/app.py`)

---

*Updated by Claude Code — 2026-03-28*
*"The goal is not to predict the future, but to be prepared for it." — Pericles*
