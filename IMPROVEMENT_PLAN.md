# NIFTY SIGNALS — IMPROVEMENT PLAN v2

**Updated:** 2026-03-29
**Status:** Phase 1 AND Phase 2 fully implemented. All 21 modules complete.

---

## What We Have (Completed in Phase 1)

| Layer | Capabilities | Key Files |
|-------|-------------|-----------|
| **Data** | yfinance + jugaad-data (NSE), TradingView, FII/DII multi-source | `data/fetcher.py`, `nse_fetcher.py`, `reliable_fetcher.py` |
| **Technical** | RSI, MACD, EMA, BB, VCP, TTM Squeeze, NR4/NR7, CPR, divergence, candlestick | `indicators/*.py` |
| **Fundamental** | 5-component scorer (0-100), DuPont, FCF, quarterly momentum, ownership | `fundamentals/scorer.py`, `fundamentals/models.py` |
| **Screens** | Value, Growth, Quality, GARP, Dividend | `fundamentals/screens/*.py` |
| **Factor Model** | 5-factor (Momentum, Value, Quality, Growth, Low Vol), sector-relative | `fundamentals/factor_model.py` |
| **Context** | Market regime, sector strength, breadth, McClellan, FII/DII, tailwinds | `indicators/market_regime.py`, `data/market_breadth.py` |
| **Risk** | ATR/structure stops, VaR/CVaR, correlation, stress tests | `risk/position_sizing.py`, `risk/portfolio_risk.py` |
| **Signals** | 4-model ensemble, piped scanner, enhanced generator | `models/*.py`, `signals/piped_scanner.py` |
| **Infra** | Backtesting (walk-forward), Telegram alerts, Streamlit dashboard | `backtest/`, `alerts/`, `dashboard/` |

---

## What's Missing — Phase 2: Investor-Grade Scoring & Valuation

### A. Classic Financial Scoring Models

These are well-researched, academically validated scoring systems. Each takes our existing `FundamentalProfile` + `ScreenerRawData` and produces a single score. They fit naturally as new modules alongside our existing scorer.

| # | Model | Score Range | What It Answers | Where It Lives |
|---|-------|------------|-----------------|----------------|
| A1 | **Piotroski F-Score** | 0-9 | "Is this company financially strong?" (profitability, leverage, efficiency) | `fundamentals/scores/piotroski.py` |
| A2 | **Altman Z-Score** | Continuous | "Is this company at risk of bankruptcy?" (safe / grey / distress zones) | `fundamentals/scores/altman.py` |
| A3 | **Beneish M-Score** | Continuous | "Is this company likely manipulating earnings?" (8-variable model) | `fundamentals/scores/beneish.py` |
| A4 | **Greenblatt Magic Formula** | Rank | "Which stocks are cheap + high quality?" (Earnings Yield × ROIC ranking) | `fundamentals/screens/magic_formula.py` |

**Reference repos:**
- [valinvest](https://github.com/astro30/valinvest) — cleanest Piotroski implementation
- [lseffer/stock_screener](https://github.com/lseffer/stock_screener) — Piotroski + Magic Formula + NCAV unified
- [financial-indicators](https://github.com/JavierSanz91/financial-indicators) — Piotroski + Altman Z + Beneish M + Graham Number (pip library, 120+ indicators)
- [LSEG Beneish & Altman](https://github.com/LSEG-API-Samples/Article.DataLib.Python.BeneishMScoreAndAltmanZScoreForAnalyzingStockReturnsOfSP500Companies)

### B. Valuation Models

These compute a fair value / intrinsic value for a stock. We currently only have the Graham Number (in `screens/value.py`). These add real valuation depth.

| # | Model | What It Computes | Where It Lives |
|---|-------|-----------------|----------------|
| B1 | **DCF (Discounted Cash Flow)** | Fair value per share from projected FCF, WACC, terminal value | `fundamentals/valuation/dcf.py` |
| B2 | **Dividend Discount Model (DDM)** | Fair value from projected dividends (Gordon Growth) — for banking/utility stocks | `fundamentals/valuation/ddm.py` |
| B3 | **Peer Relative Valuation** | Premium/discount vs sector median PE, PB, EV/EBITDA | `fundamentals/valuation/peer_relative.py` |
| B4 | **Monte Carlo Fair Value** | Probabilistic DCF — confidence intervals on fair value (10th/50th/90th percentile) | `fundamentals/valuation/monte_carlo.py` |

**Reference repos:**
- [DCF-Valuation-Tool](https://github.com/dafahentra/dcf-valuation-tool) — DCF + Monte Carlo, Streamlit UI
- [Stock-Valuation](https://github.com/scfengv/Stock-Valuation) — 5-year DCF model with WACC, FCFF, terminal value
- [Intrinsic-Value-Calculator](https://github.com/akashaero/Intrinsic-Value-Calculator) — batch DCF with growth assumptions

### C. Investing Lens Screens

These are new screens inspired by legendary investors. They fit into our existing `fundamentals/screens/` pattern (extend `BaseScreen`, return `ScreenResult`).

| # | Screen | Investor/Method | Key Criteria | Where It Lives |
|---|--------|----------------|-------------|----------------|
| C1 | **CANSLIM** | William O'Neil | Current EPS ↑25%+, Annual EPS ↑25%+ (5Y), New highs, Supply (float), Leader (RS>80), Institutional, Market direction | `fundamentals/screens/canslim.py` |
| C2 | **Coffee Can** | Saurabh Mukherjea / Indian LT investing | ROCE>15% for 10Y, Revenue growth>10% for 10Y, Market cap>1000Cr | `fundamentals/screens/coffee_can.py` |
| C3 | **Compounder** | Quality-at-reasonable-price | ROE>18%, D/E<0.5, Rev growth>12%, PE<40, FCF positive 5Y | `fundamentals/screens/compounder.py` |

**Reference repos:**
- [xang1234/stock-screener](https://github.com/xang1234/stock-screener) — most complete CANSLIM implementation (7 criteria + IBD groups)
- [growth-stock-screener](https://github.com/starboi-63/growth-stock-screener) — O'Neil RS Rating with 40/20/20/20 weighting

### D. Market Intelligence

New data/analysis capabilities that add context to investment decisions.

| # | Feature | What It Does | Where It Lives |
|---|---------|-------------|----------------|
| D1 | **Relative Rotation Graph (RRG)** | Visual sector rotation — Leading/Lagging/Improving/Weakening quadrants via RS-Ratio × RS-Momentum | `indicators/rrg.py` |
| D2 | **Insider / Bulk Deal Tracker** | Track promoter buys/sells and large block trades from NSE corporate filings | `data/insider_tracker.py` |
| D3 | **Live Market Mood Index** | Composite real-time sentiment from breadth + options OI + FII flow + VIX | `indicators/market_mood.py` |
| D4 | **O'Neil RS Rating** | Weighted relative strength (40% latest quarter price change, 20/20/20 prior quarters) — ranks all stocks 1-99 | `indicators/rs_rating.py` |

**Reference repos:**
- [RRG-Lite](https://github.com/BennyThadikaran/RRG-Lite) — Python CLI for RRG charts, Indian market support
- [NSE-Stock-Scanner](https://github.com/deshwalmahesh/NSE-Stock-Scanner) — live market mood, Zerodha integration
- [growth-stock-screener](https://github.com/starboi-63/growth-stock-screener) — O'Neil RS Rating implementation

---

## Architecture: Where Everything Fits

```
fundamentals/
├── models.py                    # FundamentalProfile, ScreenerRawData (EXISTS)
├── scorer.py                    # ProfileBuilder, FundamentalScorer (EXISTS)
├── factor_model.py              # Multi-factor scoring (EXISTS)
├── screener_fetcher.py          # Screener.in data (EXISTS)
├── scores/                      # NEW — standalone scoring models
│   ├── __init__.py              #   Registry: {piotroski, altman, beneish}
│   ├── piotroski.py             #   A1: F-Score (0-9)
│   ├── altman.py                #   A2: Z-Score (safe/grey/distress)
│   └── beneish.py               #   A3: M-Score (manipulation flag)
├── valuation/                   # NEW — intrinsic value models
│   ├── __init__.py              #   Registry: {dcf, ddm, peer, monte_carlo}
│   ├── dcf.py                   #   B1: DCF fair value
│   ├── ddm.py                   #   B2: Dividend Discount Model
│   ├── peer_relative.py         #   B3: Peer comparison valuation
│   └── monte_carlo.py           #   B4: Probabilistic fair value
└── screens/                     # EXISTING — strategy screens
    ├── base.py                  #   BaseScreen ABC (EXISTS)
    ├── value.py                 #   Graham value (EXISTS)
    ├── growth.py                #   Growth (EXISTS)
    ├── quality.py               #   Quality (EXISTS)
    ├── garp.py                  #   GARP (EXISTS)
    ├── dividend.py              #   Dividend (EXISTS)
    ├── magic_formula.py         #   A4: Greenblatt Magic Formula (NEW)
    ├── canslim.py               #   C1: O'Neil CANSLIM (NEW)
    ├── coffee_can.py            #   C2: Coffee Can investing (NEW)
    └── compounder.py            #   C3: Quality compounder (NEW)

indicators/
├── rrg.py                       #   D1: Relative Rotation Graph (NEW)
├── rs_rating.py                 #   D4: O'Neil RS Rating (NEW)
├── market_mood.py               #   D3: Live Market Mood Index (NEW)
└── [existing indicators]        #   VCP, TTM, CPR, BB, etc.

data/
├── insider_tracker.py           #   D2: Insider / Bulk Deal Tracker (NEW)
└── [existing fetchers]
```

## Integration Points

**Scoring models (A1-A3)** produce standalone scores that attach to `FundamentalProfile`:
- Added as fields to `FundamentalScore` dataclass: `piotroski_score`, `altman_zone`, `beneish_flag`
- Displayed in `fundamental-analyze` and `fundamental-scan` output
- Used as red/green flags: Beneish M > -1.78 → red flag, Piotroski < 3 → red flag, Altman Z < 1.8 → red flag

**Valuation models (B1-B4)** produce a `ValuationResult` dataclass:
- `fair_value`, `margin_of_safety_pct`, `valuation_signal` (UNDERVALUED / FAIR / OVERVALUED)
- Surfaced in `full-analyze` output alongside technical + fundamental scores
- Fed into composite score (currently 50% internal, 30% external, 20% valuation)

**New screens (A4, C1-C3)** extend `BaseScreen`:
- Auto-registered in `SCREENS` dict
- Available via `python3 main.py screen --strategy magic_formula`
- Integrated into `pipe-scan` as filter functions

**Market intelligence (D1-D4)** integrate into context layer:
- RRG feeds into sector strength analysis
- RS Rating used by CANSLIM screen and piped scanner
- Insider tracker creates bullish/bearish signals for conviction scoring
- Market Mood feeds into regime detection

---

## New CLI Commands

| Command | Description |
|---------|-------------|
| `python3 main.py valuation SYMBOL` | Show DCF + DDM + peer + Monte Carlo fair values |
| `python3 main.py scoring SYMBOL` | Show Piotroski + Altman + Beneish scores |
| `python3 main.py rrg` | Relative Rotation Graph for Nifty sectors |
| `python3 main.py insiders` | Recent insider/bulk deals with signal interpretation |
| `python3 main.py screen --strategy canslim` | Run CANSLIM screen on Nifty 500 |
| `python3 main.py screen --strategy magic_formula` | Run Magic Formula screen |
| `python3 main.py screen --strategy coffee_can` | Run Coffee Can screen |

---

## E. Catalyst Engine — Finding Multibaggers Early

This is the most important section. Scoring models tell you "is this stock good?" — but catalysts tell you "will this stock move NOW?" The best investors (Jhunjhunwala, Druckenmiller, Lynch) find asymmetric bets by connecting data points before the crowd.

### E1. Fundamental Inflection Detector
**File:** `fundamentals/inflection.py`
**What it does:** Scans quarterly results for stocks showing sudden acceleration — the earliest sign of a multibagger.

| Signal | How To Detect | Why It Matters |
|--------|--------------|----------------|
| Revenue inflection | QoQ revenue growth jumps from <15% to >25% | First sign the business is scaling |
| Operating leverage | Profit growing 2x+ faster than revenue for 2+ quarters | Fixed costs absorbed, margin expansion = earnings explosion |
| Margin expansion | OPM improving 200bps+ QoQ for 2+ quarters | Pricing power or efficiency kicking in |
| Earnings acceleration | EPS growth accelerating each quarter (10→15→25→40%) | Compounding narrative = PE re-rating |
| Cash flow inflection | FCF turns positive after years of negative (capex phase ending) | Market re-rates from "cash burner" to "cash generator" |
| Turnaround | Loss narrowing → breakeven → first profit quarter | Maximum asymmetry — goes from "uninvestable" to "investable" |

*We already have quarterly data in `ScreenerRawData.quarterly_results` — just need to compute inflection signals.*

### E2. Smart Money Tracker
**File:** `data/smart_money.py`
**What it does:** Tracks what informed participants are doing — promoter buys, FII accumulation, bulk deals.

| Signal | Data Source | Why It Matters |
|--------|-----------|----------------|
| Promoter buying | NSE SAST filings / screener.in shareholding | CEO buying with own money = highest conviction signal |
| FII accumulation (3+ quarters) | Shareholding pattern trend | Smart money building position before re-rating |
| DII accumulation | Shareholding pattern trend | Mutual funds adding = institutional validation |
| Bulk/block deals | NSE corporate filings | Large players taking positions |
| Promoter pledge reduction | Shareholding data | Reducing pledge = improving financial health |

*We already track `promoter_holding_change_1y` and `fii_holding_change_1y` but as snapshots — need to track as trends (direction + velocity).*

### E3. Catalyst News Scanner
**File:** `data/catalyst_scanner.py`
**What it does:** Monitors news specifically for company-level catalysts that create multibagger setups.

| Catalyst Type | Keywords to Track | Impact |
|--------------|-------------------|--------|
| Order win / contract award | "order", "contract", "awarded", "bagged", "L1" | Revenue visibility → PE re-rating |
| Capacity expansion | "capex", "capacity", "new plant", "expansion", "greenfield" | Future growth locked in |
| New product / market entry | "launched", "entered", "new segment", "export" | Addressable market expanding |
| Regulatory approval | "approved", "license", "clearance", "USFDA", "certification" | Barrier removed → growth unlocked |
| Strategic partnership | "partnership", "JV", "joint venture", "MoU", "collaboration" | Credibility + growth |
| Management upgrade | "CEO", "appointed", "MD", "leadership" | Turnaround signal |
| Demerger / spin-off | "demerger", "spin-off", "hive off", "subsidiary listing" | Hidden value unlock |
| Government policy beneficiary | PLI-specific, budget allocation, subsidy | Tailwind becoming tailwind + money |

*Extends `tailwinds/news_fetcher.py` but focused on company-level (not sector-level) catalysts.*

### E4. Supply Chain Mapper
**File:** `tailwinds/supply_chain.py`
**What it does:** Maps macro themes to specific beneficiary companies — the "picks and shovels" approach.

```
Theme: "Data Center Boom"
├── Direct: POWERGRID, NTPC, ADANIGREEN (power supply)
├── Supply chain: POLYCAB, KEI (cables), BLUESTAR (cooling)
├── Picks & shovels: DIXON (electronics), AFFLE (digital infra)
└── Second-order: Real estate near data center hubs

Theme: "EV Transition"
├── Direct: TATAMOTORS, M&M (OEMs)
├── Battery: EXIDEIND, AMARAJABAT → new entrants
├── Components: MOTHERSON, BHARATFORG, SUNDRMFAST
├── Charging: TATAPOWER, ADANIGREEN
└── Raw materials: HINDALCO (aluminium), NALCO
```

*Stored as JSON mapping in `tailwinds/supply_chains.json`. When a theme scores high, automatically surface all beneficiary stocks — especially the less-obvious ones.*

### E5. Multibagger Screen
**File:** `fundamentals/screens/multibagger.py`
**What it does:** Combines inflection + smart money + catalyst into a single "multibagger probability" screen.

**Criteria (all must align):**
1. Revenue growth accelerating (E1 inflection signal)
2. Operating leverage present (profit growing faster than revenue)
3. Promoter OR FII accumulating for 2+ quarters (E2 smart money)
4. At least one active catalyst (E3 news) OR strong sector tailwind (existing)
5. Not overvalued: PE < 40 or PEG < 2.0 (valuation sanity)
6. Market cap < 50,000 Cr (enough room to grow — small/mid preferred)
7. Piotroski F-Score >= 6 (A1 — financially sound)
8. No Beneish M-Score red flag (A3 — not cooking books)

**Output:** Ranked list with "Catalyst Score" (0-100) combining all signals.

### E6. Thematic Momentum Tracker
**File:** `tailwinds/theme_momentum.py`
**What it does:** Tracks how fast a theme is accelerating in news + price action + institutional flow.

| Metric | How | Why |
|--------|-----|-----|
| News velocity | Count of theme-related articles per week, track trend | Accelerating coverage = growing narrative |
| Price momentum | Average return of theme beneficiaries vs Nifty | Money flowing into the theme |
| Institutional flow | Average FII/DII change in theme stocks | Smart money validating the theme |
| Retail buzz | Reddit/social mention velocity | Retail catching on (late but adds fuel) |
| Theme lifecycle | Nascent → Accelerating → Consensus → Crowded → Fading | "Accelerating" = sweet spot; "Consensus" = too late |

*This turns our static theme scoring into a dynamic signal — catching themes when they're accelerating, not when they're consensus.*

---

## Architecture: Catalyst Engine Integration

```
                    ┌─────────────────────────────────┐
                    │     CATALYST ENGINE (NEW)        │
                    │                                   │
                    │  E1: Inflection Detector          │
                    │  E2: Smart Money Tracker          │
                    │  E3: Catalyst News Scanner        │
                    │  E4: Supply Chain Mapper           │
                    │  E5: Multibagger Screen            │
                    │  E6: Theme Momentum Tracker        │
                    └──────────┬──────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌────────────┐   ┌──────────────┐  ┌────────────┐
     │ Conviction  │   │  Composite   │  │   Piped    │
     │  Scoring    │   │   Analyzer   │  │  Scanner   │
     │ (existing)  │   │  (existing)  │  │ (existing) │
     └────────────┘   └──────────────┘  └────────────┘
```

---

## Summary: 21 New Modules

| Category | Count | Items |
|----------|-------|-------|
| Scoring Models | 3 | Piotroski, Altman Z, Beneish M |
| Valuation Models | 4 | DCF, DDM, Peer Relative, Monte Carlo |
| Investing Screens | 4 | Magic Formula, CANSLIM, Coffee Can, Compounder |
| Market Intelligence | 4 | RRG, Insider Tracker, Market Mood, RS Rating |
| Catalyst Engine | 6 | Inflection Detector, Smart Money Tracker, Catalyst Scanner, Supply Chain Mapper, Multibagger Screen, Theme Momentum |
| **Total** | **21** | |

---

## Reference Repos

| Repo | Stars | What We Learn |
|------|-------|---------------|
| [valinvest](https://github.com/astro30/valinvest) | 188 | Piotroski scoring implementation |
| [lseffer/stock_screener](https://github.com/lseffer/stock_screener) | 142 | Piotroski + Magic Formula + NCAV unified |
| [financial-indicators](https://github.com/JavierSanz91/financial-indicators) | new | 120+ indicators, pip-installable (Piotroski + Altman + Beneish) |
| [haga8905/magic-formula-screener](https://github.com/haga8905/magic-formula-screener) | new | Magic Formula with Nifty 500 support |
| [xang1234/stock-screener](https://github.com/xang1234/stock-screener) | 13 | Full CANSLIM (7 criteria) + Minervini + IBD groups |
| [growth-stock-screener](https://github.com/starboi-63/growth-stock-screener) | 33 | O'Neil RS Rating (40/20/20/20 weighting) |
| [DCF-Valuation-Tool](https://github.com/dafahentra/dcf-valuation-tool) | — | DCF + Monte Carlo, Streamlit |
| [Stock-Valuation](https://github.com/scfengv/Stock-Valuation) | — | 5-year DCF: WACC, FCFF, terminal value |
| [RRG-Lite](https://github.com/BennyThadikaran/RRG-Lite) | — | RRG for Indian markets |
| [NSE-Stock-Scanner](https://github.com/deshwalmahesh/NSE-Stock-Scanner) | — | Live market mood, Zerodha integration |
| [PKScreener](https://github.com/pkjmesra/PKScreener) | 325 | 40+ scanners, Telegram bot, 12k+ commits |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | 63k | Gold standard data platform architecture |
| [Qlib](https://github.com/microsoft/qlib) | 39k | ML-driven factor mining (future direction) |
