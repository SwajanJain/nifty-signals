# LEGENDARY TRADER IMPROVEMENT PLAN
## Nifty Signals System - Production Hardening

**Created:** 2026-01-18
**Goal:** Transform from "promising prototype" to "production-ready daily trading system"
**Principle:** Real money demands real rigor

---

## EXECUTIVE SUMMARY

### Current State
| Metric | Value | Target |
|--------|-------|--------|
| Data Availability | 43% | >90% |
| Legend Gates Passed | 0/5 | 5/5 |
| Decision Confidence | Low | High |
| Global Context | None | Full |
| Flow Data | Missing | Real-time |

### The 5 Legend Gates (Must Pass ALL)

1. **SIMONS GATE**: >80% data sources available
2. **DALIO GATE**: Economic thesis defined
3. **DRUCKENMILLER GATE**: FII/DII flow confirms direction
4. **PTJ GATE**: Global context checked (US, Asia, Dollar, Crude)
5. **SEYKOTA GATE**: Market in clear trend (NIFTY > EMA50 for longs)

---

## PHASE 1: FIX DATA GAPS (Priority: CRITICAL)

### 1.1 FII/DII Flow Data - MUST HAVE

**Why Critical (Druckenmiller):** FIIs move Indian markets. Without this, you're blind.

**Current:** build_flow_data.py exists but returning UNAVAILABLE

**Action Items:**
```
[ ] Fix NSE FII/DII scraper - daily provisional data at 6 PM
[ ] Add moneycontrol.com as backup source
[ ] Historical 10-day rolling flow trend
[ ] Alert if FII selling > 2000 Cr consecutive 3 days
```

**Data Points Needed:**
- FII Cash: Buy, Sell, Net
- DII Cash: Buy, Sell, Net
- FII F&O: Index Futures, Stock Futures, Options
- 5-day trend direction

**Source Priority:**
1. NSE Official (nse-india.com/reports)
2. MoneyControl FII/DII page
3. Economic Times Markets

---

### 1.2 Market Breadth - MUST HAVE

**Why Critical (Simons):** Confirms if move is broad-based or narrow.

**Current:** "Breadth data not available"

**Action Items:**
```
[ ] Calculate from NIFTY 50 constituents (you have data)
[ ] Advance/Decline ratio
[ ] % stocks above 20/50/200 EMA
[ ] New Highs vs New Lows
```

**Simple Implementation:**
```python
def calculate_breadth(nifty50_data: Dict[str, pd.DataFrame]) -> Dict:
    """Calculate breadth from constituent data you already fetch."""
    above_ema20 = sum(1 for df in nifty50_data.values()
                      if df['close'].iloc[-1] > ta.ema(df['close'], 20).iloc[-1])
    above_ema50 = sum(1 for df in nifty50_data.values()
                      if df['close'].iloc[-1] > ta.ema(df['close'], 50).iloc[-1])

    return {
        'pct_above_ema20': above_ema20 / 50 * 100,
        'pct_above_ema50': above_ema50 / 50 * 100,
        'breadth_signal': 'BULLISH' if above_ema50 > 60 else 'BEARISH' if above_ema50 < 40 else 'NEUTRAL'
    }
```

---

### 1.3 Global Context - MUST HAVE (PTJ Gate)

**Why Critical (PTJ):** Indian markets don't exist in isolation.

**Current:** No global context at all

**Action Items:**
```
[ ] Pre-market check: SGX Nifty, US futures, Asian indices
[ ] Dollar/INR trend (impacts FII flows)
[ ] Crude oil price (India imports 85%)
[ ] US 10Y yield (risk-on/risk-off indicator)
```

**Data Sources (Free):**
- Yahoo Finance: ^GSPC (S&P), ^DJI (Dow), ^IXIC (Nasdaq)
- Yahoo Finance: CL=F (Crude), GC=F (Gold)
- Yahoo Finance: USDINR=X
- Investing.com: SGX Nifty (scrape)

**Implementation:**
```python
def get_global_context() -> Dict:
    """Fetch global market context before Indian market opens."""
    symbols = {
        'sp500': '^GSPC',
        'nasdaq': '^IXIC',
        'dow': '^DJI',
        'crude': 'CL=F',
        'gold': 'GC=F',
        'usdinr': 'USDINR=X',
        'dxy': 'DX-Y.NYB',  # Dollar index
    }

    context = {}
    for name, symbol in symbols.items():
        df = yf.download(symbol, period='5d', progress=False)
        if len(df) >= 2:
            change_pct = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100
            context[name] = {
                'price': df['Close'].iloc[-1],
                'change_1d': round(change_pct, 2),
                'trend_5d': 'UP' if df['Close'].iloc[-1] > df['Close'].iloc[0] else 'DOWN'
            }

    # Risk-on/Risk-off signal
    risk_score = 0
    if context.get('sp500', {}).get('change_1d', 0) > 0: risk_score += 1
    if context.get('crude', {}).get('change_1d', 0) < 2: risk_score += 1  # Stable crude is good
    if context.get('usdinr', {}).get('change_1d', 0) < 0.5: risk_score += 1  # Stable INR is good
    if context.get('dxy', {}).get('change_1d', 0) < 0: risk_score += 1  # Weak dollar is good for EMs

    context['risk_sentiment'] = 'RISK_ON' if risk_score >= 3 else 'RISK_OFF' if risk_score <= 1 else 'NEUTRAL'

    return context
```

---

### 1.4 Sector Rotation Data - SHOULD HAVE

**Why Important (Druckenmiller):** Only trade leaders in leading sectors.

**Current:** "Sector data not available"

**Action Items:**
```
[ ] Calculate sector relative strength from NIFTY sectoral indices
[ ] Rank sectors by 1-month momentum
[ ] Only long stocks in top 3 sectors
```

**Sectoral Indices (NSE):**
- NIFTY IT, NIFTY BANK, NIFTY PHARMA, NIFTY AUTO
- NIFTY FMCG, NIFTY METAL, NIFTY REALTY, NIFTY ENERGY

---

## PHASE 2: ADD TREND FILTER (Priority: HIGH)

### 2.1 Seykota Trend Gate

**Why Critical:** "Trade with the trend, not against it"

**Current Problem:**
- NIFTY at 25,694
- EMA50 at 25,875
- Price BELOW EMA50 = NO TREND for longs

**Implementation:**
```python
def check_seykota_gate(nifty_data: pd.DataFrame) -> Dict:
    """Seykota Gate: Only trade with the trend."""
    close = nifty_data['close'].iloc[-1]
    ema20 = ta.ema(nifty_data['close'], 20).iloc[-1]
    ema50 = ta.ema(nifty_data['close'], 50).iloc[-1]
    ema200 = ta.ema(nifty_data['close'], 200).iloc[-1]

    # Trend strength
    above_ema20 = close > ema20
    above_ema50 = close > ema50
    above_ema200 = close > ema200
    ema20_above_50 = ema20 > ema50

    # Seykota Gate
    if above_ema50 and ema20_above_50:
        trend = 'STRONG_UP'
        long_allowed = True
        short_allowed = False
    elif above_ema50:
        trend = 'UP'
        long_allowed = True
        short_allowed = False
    elif not above_ema50 and not above_ema200:
        trend = 'STRONG_DOWN'
        long_allowed = False
        short_allowed = True
    elif not above_ema50:
        trend = 'DOWN'
        long_allowed = False
        short_allowed = True
    else:
        trend = 'NEUTRAL'
        long_allowed = False
        short_allowed = False

    return {
        'trend': trend,
        'long_allowed': long_allowed,
        'short_allowed': short_allowed,
        'price': close,
        'ema20': ema20,
        'ema50': ema50,
        'ema200': ema200,
        'gate_passed': long_allowed or short_allowed,
        'reason': f"Price {'above' if above_ema50 else 'below'} EMA50"
    }
```

**Rule:**
- If `long_allowed = False`, **DO NOT GENERATE ANY LONG SIGNALS**
- This is non-negotiable (Seykota)

---

## PHASE 3: CONTEXT MANAGEMENT (Priority: HIGH)

### 3.1 The Intelligence Layer Architecture

**Problem:** Each run is stateless. No memory of:
- Previous signals and outcomes
- Running positions
- Historical accuracy
- Pattern learning

**Solution: Claude Code as Persistent Intelligence Layer**

```
┌─────────────────────────────────────────────────────────────┐
│                    DAILY WORKFLOW                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  6:00 AM  ─── Global Context Fetch ───────────────────────► │
│                     │                                       │
│  7:00 AM  ─── Indian Pre-market Data ─────────────────────► │
│                     │                                       │
│  8:30 AM  ─── FII/DII Provisional (previous day) ─────────► │
│                     │                                       │
│  8:45 AM  ─── Run Pipeline ───────────────────────────────► │
│                     │                                       │
│            ┌────────▼────────┐                              │
│            │  CLAUDE CODE    │◄── Historical Context        │
│            │  Intelligence   │◄── Position Journal          │
│            │  Layer          │◄── Win/Loss Tracking         │
│            └────────┬────────┘                              │
│                     │                                       │
│  9:00 AM  ─── Trading Decision ───────────────────────────► │
│                     │                                       │
│  9:15 AM  ─── Market Opens ───────────────────────────────► │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Context Files Structure

```
journal/
├── context/
│   ├── positions.json          # Current open positions
│   ├── trade_history.json      # All historical trades
│   ├── signal_accuracy.json    # Track signal outcomes
│   ├── market_memory.json      # Recent market patterns
│   └── learning.json           # What worked, what didn't
├── runs/
│   └── YYYY-MM-DD_HHMM/
│       ├── raw_data/           # All fetched data
│       ├── analysis/           # Generated analysis
│       └── decision.json       # Final decision + reasoning
└── daily_digest/
    └── YYYY-MM-DD.md           # Human-readable daily summary
```

### 3.3 Position Tracking (Critical for Real Money)

```python
# journal/context/positions.json
{
  "open_positions": [
    {
      "symbol": "WIPRO",
      "entry_date": "2026-01-15",
      "entry_price": 265.50,
      "current_price": 267.45,
      "stop_loss": 257.25,
      "target_1": 282.75,
      "target_2": 297.50,
      "target_3": 320.00,
      "position_size": 100,
      "remaining_size": 100,
      "current_r": 0.38,
      "days_held": 3,
      "partial_exits": [],
      "notes": "IT sector play post-results"
    }
  ],
  "portfolio_heat": 1.2,  # % of capital at risk
  "available_risk": 4.8,  # % remaining risk budget
  "sector_exposure": {
    "IT": 15.0,
    "Banking": 0,
    "FMCG": 0
  }
}
```

### 3.4 Signal Accuracy Tracking (Simons Requirement)

```python
# journal/context/signal_accuracy.json
{
  "overall": {
    "total_signals": 47,
    "winning_signals": 28,
    "win_rate": 59.6,
    "avg_win_r": 2.3,
    "avg_loss_r": -0.8,
    "expectancy": 0.89,  # (win_rate * avg_win) + (loss_rate * avg_loss)
    "sharpe_estimate": 1.4
  },
  "by_conviction": {
    "A+": {"signals": 5, "win_rate": 80.0, "avg_r": 3.2},
    "A": {"signals": 12, "win_rate": 66.7, "avg_r": 1.8},
    "B": {"signals": 20, "win_rate": 55.0, "avg_r": 1.2},
    "C": {"signals": 10, "win_rate": 40.0, "avg_r": 0.5}
  },
  "by_regime": {
    "STRONG_BULL": {"signals": 8, "win_rate": 75.0},
    "BULL": {"signals": 15, "win_rate": 66.7},
    "NEUTRAL": {"signals": 18, "win_rate": 50.0},
    "BEAR": {"signals": 6, "win_rate": 33.3}
  },
  "recent_10": [
    {"date": "2026-01-10", "symbol": "TCS", "result": "WIN", "r": 2.1},
    {"date": "2026-01-08", "symbol": "HDFCBANK", "result": "LOSS", "r": -1.0}
  ]
}
```

---

## PHASE 4: ECONOMIC CONTEXT (Dalio Gate)

### 4.1 Simple Economic Regime Classifier

**Why Needed:** Dalio says "understand the machine"

```python
def classify_economic_regime() -> Dict:
    """
    Simple economic regime classification.
    Not as sophisticated as Bridgewater, but better than nothing.
    """
    # Indicators (can be fetched from RBI, MOSPI)
    indicators = {
        'inflation': get_india_cpi(),  # RBI data
        'rates': get_rbi_repo_rate(),
        'gdp_growth': get_india_gdp_growth(),
        'credit_growth': get_bank_credit_growth(),
        'iip': get_iip_data(),  # Industrial production
    }

    # Simple regime classification
    # Quadrant: Growth vs Inflation

    high_growth = indicators['gdp_growth'] > 6.0
    high_inflation = indicators['inflation'] > 5.0

    if high_growth and not high_inflation:
        regime = 'GOLDILOCKS'  # Best for equities
        equity_bias = 'BULLISH'
    elif high_growth and high_inflation:
        regime = 'OVERHEATING'  # Be selective
        equity_bias = 'NEUTRAL'
    elif not high_growth and high_inflation:
        regime = 'STAGFLATION'  # Worst for equities
        equity_bias = 'BEARISH'
    else:
        regime = 'DEFLATION_RISK'  # Bonds better
        equity_bias = 'CAUTIOUS'

    return {
        'regime': regime,
        'equity_bias': equity_bias,
        'indicators': indicators,
        'recommendation': f"Economic regime is {regime} - {equity_bias} on equities"
    }
```

### 4.2 Simplified Version (No External Data)

If RBI API is complex, use proxy indicators:

```python
def simple_economic_proxy() -> Dict:
    """Use market data as economic proxy."""

    # Bank Nifty vs Nifty ratio (credit proxy)
    # Nifty vs Gold ratio (risk appetite)
    # Bond yields from NSE (rate expectations)

    bank_nifty = yf.download('^NSEBANK', period='3mo')
    nifty = yf.download('^NSEI', period='3mo')
    gold = yf.download('GC=F', period='3mo')

    # Bank/Nifty ratio trend
    bank_ratio = bank_nifty['Close'] / nifty['Close']
    bank_ratio_trend = 'UP' if bank_ratio.iloc[-1] > bank_ratio.iloc[-20] else 'DOWN'

    # Risk appetite (Nifty/Gold)
    risk_ratio = nifty['Close'].iloc[-1] / gold['Close'].iloc[-1]

    return {
        'credit_proxy': bank_ratio_trend,  # UP = credit expanding
        'risk_appetite': risk_ratio,
        'interpretation': 'Banks outperforming = economy expanding' if bank_ratio_trend == 'UP' else 'Defensive mode'
    }
```

---

## PHASE 5: ENHANCED DECISION FRAMEWORK

### 5.1 The 5 Legend Gates (Implemented)

```python
def check_all_legend_gates(context: Dict) -> Dict:
    """
    All 5 gates must pass before ANY trade is considered.
    """
    gates = {}

    # 1. SIMONS GATE: Data availability
    data_sources = ['regime', 'breadth', 'fii_dii', 'fo_sentiment', 'sector', 'global', 'news']
    available = sum(1 for s in data_sources if context.get(s, {}).get('status') == 'OK')
    gates['simons'] = {
        'passed': available / len(data_sources) >= 0.80,
        'score': f"{available}/{len(data_sources)} sources available",
        'required': '>80% data availability'
    }

    # 2. DALIO GATE: Economic thesis
    economic = context.get('economic_regime', {})
    gates['dalio'] = {
        'passed': economic.get('equity_bias') in ['BULLISH', 'NEUTRAL'],
        'score': economic.get('regime', 'UNKNOWN'),
        'required': 'Not in STAGFLATION or severe DEFLATION'
    }

    # 3. DRUCKENMILLER GATE: FII flow confirms
    flows = context.get('fii_dii', {})
    fii_trend = flows.get('fii_5d_trend', 'UNKNOWN')
    gates['druckenmiller'] = {
        'passed': fii_trend != 'HEAVY_SELLING',
        'score': f"FII 5-day: {fii_trend}",
        'required': 'FII not in heavy selling mode (>2000Cr/day for 3+ days)'
    }

    # 4. PTJ GATE: Global context OK
    global_ctx = context.get('global', {})
    risk_sentiment = global_ctx.get('risk_sentiment', 'UNKNOWN')
    gates['ptj'] = {
        'passed': risk_sentiment != 'RISK_OFF',
        'score': f"Global: {risk_sentiment}",
        'required': 'Global markets not in risk-off mode'
    }

    # 5. SEYKOTA GATE: Trend confirmed
    trend = context.get('trend', {})
    gates['seykota'] = {
        'passed': trend.get('long_allowed', False) or trend.get('short_allowed', False),
        'score': f"Trend: {trend.get('trend', 'UNKNOWN')}",
        'required': 'Clear trend direction (NIFTY above/below EMA50)'
    }

    # Final verdict
    all_passed = all(g['passed'] for g in gates.values())
    passed_count = sum(1 for g in gates.values() if g['passed'])

    return {
        'gates': gates,
        'all_passed': all_passed,
        'passed_count': f"{passed_count}/5",
        'verdict': 'TRADE ALLOWED' if all_passed else 'NO TRADE - GATES FAILED',
        'failed_gates': [name for name, g in gates.items() if not g['passed']]
    }
```

### 5.2 Decision Output Format

```python
def generate_daily_decision(context: Dict, candidates: List[Dict]) -> Dict:
    """Generate the final trading decision with full audit trail."""

    # Check gates first
    gates = check_all_legend_gates(context)

    if not gates['all_passed']:
        return {
            'decision': 'NO_TRADE',
            'reason': f"Legend gates failed: {gates['failed_gates']}",
            'gates': gates,
            'action': 'WAIT',
            'message': "Market conditions do not meet legendary trader standards."
        }

    # If gates pass, evaluate candidates
    qualified = []
    for candidate in candidates:
        # Apply structure-based stop
        stop, stop_type = calculate_structure_stop(candidate['df'], candidate['entry'])

        # Calculate Seykota targets (2R, 4R, 8R)
        targets = calculate_targets(candidate['entry'], stop)

        # Check R:R with new targets
        risk = candidate['entry'] - stop
        reward = targets['target_1'] - candidate['entry']
        rr = reward / risk if risk > 0 else 0

        if rr >= 2.0:  # Seykota minimum
            qualified.append({
                **candidate,
                'stop': stop,
                'stop_type': stop_type,
                'targets': targets,
                'rr': rr
            })

    if not qualified:
        return {
            'decision': 'NO_TRADE',
            'reason': 'No candidates meet minimum 2:1 R:R after structure-based stop',
            'gates': gates,
            'action': 'WATCHLIST',
            'candidates_reviewed': len(candidates)
        }

    # Rank by conviction and take best
    best = max(qualified, key=lambda x: x['conviction_score'])

    return {
        'decision': 'TRADE',
        'symbol': best['symbol'],
        'entry': best['entry'],
        'stop': best['stop'],
        'stop_type': best['stop_type'],
        'targets': best['targets'],
        'conviction': best['conviction_score'],
        'position_size': calculate_position_size(best, context),
        'gates': gates,
        'reasoning': generate_reasoning(best, context),
        'exit_plan': {
            'at_t1': '25% at 2R',
            'at_t2': '25% at 4R',
            'trail': '50% with 3x ATR Chandelier'
        }
    }
```

---

## PHASE 6: IMPLEMENTATION PRIORITY

### Week 1: Critical Fixes
```
Day 1-2: Fix FII/DII data fetch (Druckenmiller Gate)
Day 3-4: Add global context (PTJ Gate)
Day 5-6: Calculate breadth from existing data (Simons Gate)
Day 7: Add trend filter (Seykota Gate)
```

### Week 2: Context Management
```
Day 1-2: Set up position tracking (positions.json)
Day 3-4: Set up signal accuracy tracking
Day 5-6: Build daily workflow automation
Day 7: Test full pipeline
```

### Week 3: Polish
```
Day 1-2: Add economic proxy (Dalio Gate)
Day 3-4: Sector rotation data
Day 5-6: Backtest legend gates on historical data
Day 7: Go live with small size
```

---

## IMPLEMENTATION CHECKLIST

### Data Sources (Priority Order)
- [x] OHLCV data (yfinance) - WORKING
- [x] Technical indicators (pandas-ta) - WORKING
- [x] News/Events context - WORKING
- [ ] FII/DII flows - NEEDS FIX
- [ ] Market breadth - NEEDS IMPLEMENTATION
- [ ] Global context - NEEDS IMPLEMENTATION
- [ ] F&O sentiment - NEEDS FIX
- [ ] Sector rotation - NEEDS IMPLEMENTATION
- [ ] Economic regime - OPTIONAL

### Legend Gates
- [ ] Simons Gate (data availability check)
- [ ] Dalio Gate (economic thesis)
- [ ] Druckenmiller Gate (FII flow check)
- [ ] PTJ Gate (global context check)
- [ ] Seykota Gate (trend filter)

### Context Management
- [ ] positions.json - track open positions
- [ ] trade_history.json - all trades
- [ ] signal_accuracy.json - win/loss tracking
- [ ] Daily decision journal

### Automation
- [ ] Pre-market data fetch script
- [ ] Pipeline runner (cron job)
- [ ] Alert system (Telegram/Email)
- [ ] Position monitoring

---

## RISK MANAGEMENT RULES (Non-Negotiable)

### From the Legends:

**PTJ Rule:** Never risk more than 2% on any single trade
```python
MAX_RISK_PER_TRADE = 0.02  # 2% of capital
```

**Simons Rule:** If data quality < 80%, no trade
```python
MIN_DATA_QUALITY = 0.80  # 80% of sources must be available
```

**Druckenmiller Rule:** Cut immediately if FII turns to heavy selling
```python
FII_SELLING_THRESHOLD = -2000  # Cr per day
FII_SELLING_DAYS = 3  # Consecutive days
```

**Seykota Rule:** Never trade against the trend
```python
TREND_FILTER = True  # NIFTY must be above EMA50 for longs
```

**Dalio Rule:** Reduce exposure in stagflation
```python
STAGFLATION_MULTIPLIER = 0.3  # 30% of normal size
```

---

## SUCCESS METRICS

### After 1 Month:
- All 5 legend gates implemented
- Data availability > 80%
- Full position tracking working
- 0 untracked trades

### After 3 Months:
- Win rate tracked and > 50%
- Expectancy positive (> 0.5)
- Sharpe ratio estimate > 1.0
- No max drawdown > 10%

### After 6 Months:
- Backtest validates legend gates
- Refinements based on accuracy data
- Consistent daily operation
- Potential to increase size

---

## FINAL THOUGHT

> "Risk comes from not knowing what you're doing." - Warren Buffett

Your system knows WHAT to do (technicals are solid).
It doesn't know WHEN to do it (missing macro context).
It doesn't know IF to do it (missing legend gates).

Fix the IF and WHEN. The WHAT will take care of itself.

---

*Plan created by Claude Code - Intelligence Layer*
*Real money demands real rigor*
