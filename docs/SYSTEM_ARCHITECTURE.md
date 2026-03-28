# Nifty Signals - Complete System Architecture

**Version:** 1.0
**Date:** January 2026
**Repository:** https://github.com/SwajanJain/nifty-signals

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Phase-by-Phase Flow](#phase-by-phase-flow)
3. [Component Interaction Map](#component-interaction-map)
4. [Data Flow Summary](#data-flow-summary)
5. [Conviction Scoring System](#conviction-scoring-system)
6. [Position Sizing Engine](#position-sizing-engine)
7. [Risk Management Gates](#risk-management-gates)
8. [Output Format](#output-format)
9. [File Structure](#file-structure)
10. [Legendary Principles Applied](#legendary-principles-applied)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                         NIFTY SIGNALS - SYSTEM ARCHITECTURE                             │
│                                                                                         │
│   User: "trade" or "/trade"                                                             │
│            │                                                                            │
│            ▼                                                                            │
│   ┌─────────────────┐                                                                   │
│   │  CLAUDE SKILL   │  ← Reads .claude/skills/trade.md                                  │
│   │   ORCHESTRATOR  │  ← Knows execution sequence                                       │
│   └────────┬────────┘                                                                   │
│            │                                                                            │
│            ▼                                                                            │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                  │  │
│   │                         ENHANCED ORCHESTRATOR                                    │  │
│   │                                                                                  │  │
│   │   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐                │  │
│   │   │  CONTEXT  │   │  SIGNAL   │   │ CONVICTION│   │   RISK    │                │  │
│   │   │   LAYER   │──▶│   LAYER   │──▶│   LAYER   │──▶│   LAYER   │──▶ OUTPUT     │  │
│   │   └───────────┘   └───────────┘   └───────────┘   └───────────┘                │  │
│   │                                                                                  │  │
│   │   Tier 1: Core     Tier 1: Models   Tier 1+2:     Tier 1+3:                     │  │
│   │   + Tier 2: Data   (Ensemble)       Scoring       Checks                        │  │
│   │                                                                                  │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase-by-Phase Flow

### PHASE 1: Context Gathering (Parallel Execution)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                            PHASE 1: CONTEXT GATHERING                                   │
│                              (Run in PARALLEL)                                          │
│                                                                                         │
│   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐                   │
│   │   AGENT 1        │   │   AGENT 2        │   │   AGENT 3        │                   │
│   │   Global Macro   │   │   Market Regime  │   │   Sector Rank    │                   │
│   └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘                   │
│            │                      │                      │                              │
│            ▼                      ▼                      ▼                              │
│   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐                   │
│   │ • US S&P change  │   │ • NIFTY trend    │   │ • IT: Rank #1    │                   │
│   │ • VIX level      │   │ • 50/200 MA      │   │ • Banks: Rank #2 │                   │
│   │ • Asia sentiment │   │ • Breadth        │   │ • Auto: Rank #8  │                   │
│   │ • Crude/Gold     │   │ • Volatility     │   │ • Metals: Rank #9│                   │
│   │ • DXY/USDINR     │   │                  │   │                  │                   │
│   │                  │   │ Output:          │   │ Output:          │                   │
│   │ Output:          │   │ BULL (Score: +3) │   │ Top 3 / Bottom 3 │                   │
│   │ Risk Score: 2/5  │   │ Multiplier: 0.8x │   │                  │                   │
│   └──────────────────┘   └──────────────────┘   └──────────────────┘                   │
│                                                                                         │
│   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐                   │
│   │   AGENT 4        │   │   AGENT 5        │   │   AGENT 6        │                   │
│   │   FII/DII Flows  │   │   F&O Data       │   │  Regime Warning  │                   │
│   └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘                   │
│            │                      │                      │                              │
│            ▼                      ▼                      ▼                              │
│   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐                   │
│   │ • FII today      │   │ • PCR: 1.2       │   │ • Breadth check  │                   │
│   │ • FII 5-day      │   │ • Max Pain: 24500│   │ • Distribution   │                   │
│   │ • DII absorbing? │   │ • OI buildup     │   │ • VIX spike?     │                   │
│   │                  │   │                  │   │                  │                   │
│   │ Output:          │   │ Output:          │   │ Output:          │                   │
│   │ Score: +2        │   │ Sentiment: BULL  │   │ Warning: LOW     │                   │
│   │ Trend: INFLOW    │   │ Score: +3        │   │ Prob: 15%        │                   │
│   └──────────────────┘   └──────────────────┘   └──────────────────┘                   │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### PHASE 2: Regime Gate Check

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                         PHASE 2: REGIME GATE CHECK                                      │
│                                                                                         │
│                          ┌─────────────────────┐                                        │
│                          │   REGIME = CRASH?   │                                        │
│                          └──────────┬──────────┘                                        │
│                                     │                                                   │
│                    ┌────────────────┴────────────────┐                                  │
│                    │                                 │                                  │
│                    ▼                                 ▼                                  │
│             ┌─────────────┐                  ┌─────────────┐                            │
│             │     YES     │                  │     NO      │                            │
│             └──────┬──────┘                  └──────┬──────┘                            │
│                    │                                │                                   │
│                    ▼                                ▼                                   │
│   ┌────────────────────────────┐        Continue to Phase 3                            │
│   │  STOP - RECOMMEND CASH     │                                                        │
│   │  "No trades in CRASH mode" │                                                        │
│   └────────────────────────────┘                                                        │
│                                                                                         │
│   REGIME MULTIPLIERS:                                                                   │
│   ┌─────────────────┬────────────────┬──────────────────────────────────────────────┐  │
│   │     Regime      │   Multiplier   │   Action                                     │  │
│   ├─────────────────┼────────────────┼──────────────────────────────────────────────┤  │
│   │   STRONG_BULL   │     1.0x       │   Full positions, aggressive entries         │  │
│   │   BULL          │     0.8x       │   Normal positions                           │  │
│   │   NEUTRAL       │     0.5x       │   Half positions, selective                  │  │
│   │   BEAR          │     0.3x       │   Small positions, quick profits             │  │
│   │   STRONG_BEAR   │     0.2x       │   Minimal positions                          │  │
│   │   CRASH         │     0.0x       │   NO TRADES - 100% cash                      │  │
│   └─────────────────┴────────────────┴──────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### PHASE 3: Signal Generation (Multi-Model Ensemble)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                          PHASE 3: SIGNAL GENERATION                                     │
│                                                                                         │
│                    ┌─────────────────────────────────────┐                              │
│                    │      ENHANCED SCAN (main.py)        │                              │
│                    │      Scans Nifty 100 stocks         │                              │
│                    └─────────────────┬───────────────────┘                              │
│                                      │                                                  │
│                                      ▼                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                        MULTI-MODEL ENSEMBLE                                      │  │
│   │                                                                                  │  │
│   │   For each stock, run 4 independent models:                                      │  │
│   │                                                                                  │  │
│   │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐│  │
│   │   │    MOMENTUM     │  │    BREAKOUT     │  │     TREND       │  │    MEAN     ││  │
│   │   │     MODEL       │  │     MODEL       │  │   FOLLOWING     │  │  REVERSION  ││  │
│   │   ├─────────────────┤  ├─────────────────┤  ├─────────────────┤  ├─────────────┤│  │
│   │   │                 │  │                 │  │                 │  │             ││  │
│   │   │ Criteria:       │  │ Criteria:       │  │ Criteria:       │  │ Criteria:   ││  │
│   │   │ • RSI momentum  │  │ • Range breakout│  │ • ADX > 25      │  │ • RSI < 30  ││  │
│   │   │ • ROC > 0       │  │ • Volume confirm│  │ • Price > EMAs  │  │ • BB touch  ││  │
│   │   │ • Volume surge  │  │ • New high/low  │  │ • DI+ > DI-     │  │ • Oversold  ││  │
│   │   │                 │  │                 │  │                 │  │   bounce    ││  │
│   │   │ Regime Weight:  │  │ Regime Weight:  │  │ Regime Weight:  │  │ Regime Wt:  ││  │
│   │   │ BULL = 1.2x     │  │ BULL = 1.3x     │  │ ALL = 1.0x      │  │ NEUTRAL=1.3x││  │
│   │   │ BEAR = 0.7x     │  │ BEAR = 0.5x     │  │                 │  │ BULL = 0.7x ││  │
│   │   │                 │  │                 │  │                 │  │             ││  │
│   │   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘│  │
│   │            │                    │                    │                  │        │  │
│   │            └────────────────────┴────────────────────┴──────────────────┘        │  │
│   │                                         │                                        │  │
│   │                                         ▼                                        │  │
│   │                            ┌─────────────────────────┐                           │  │
│   │                            │    ENSEMBLE VOTING      │                           │  │
│   │                            │                         │                           │  │
│   │                            │  • Weighted average     │                           │  │
│   │                            │  • Regime adjustments   │                           │  │
│   │                            │  • Confidence = models  │                           │  │
│   │                            │    agreeing             │                           │  │
│   │                            │                         │                           │  │
│   │                            │  If 3+ agree = HIGH     │                           │  │
│   │                            │  If 2 agree = MEDIUM    │                           │  │
│   │                            │  If <2 agree = LOW      │                           │  │
│   │                            └─────────────────────────┘                           │  │
│   │                                                                                  │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   Output: Top 5 candidates ranked by ensemble score                                     │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### PHASE 4: Candidate Filtering

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                           PHASE 4: CANDIDATE FILTERING                                  │
│                                                                                         │
│   For each candidate, apply sequential filters:                                         │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                  │  │
│   │   FILTER 1: EARNINGS CHECK                                                       │  │
│   │   ┌──────────────────────────────────────────────────────────────────────────┐  │  │
│   │   │  • Fetch earnings calendar                                               │  │  │
│   │   │  • If earnings within 3 days → REJECT (binary event risk)                │  │  │
│   │   │  • If earnings within 7 days → Position multiplier = 0.5x                │  │  │
│   │   │  • If earnings within 14 days → Position multiplier = 0.7x               │  │  │
│   │   └──────────────────────────────────────────────────────────────────────────┘  │  │
│   │                                         │                                        │  │
│   │                                         ▼                                        │  │
│   │   FILTER 2: FUNDAMENTALS CHECK                                                   │  │
│   │   ┌──────────────────────────────────────────────────────────────────────────┐  │  │
│   │   │  Quality metrics checked:                                                │  │  │
│   │   │  • ROE > 10%                    (profitability)                          │  │  │
│   │   │  • Debt/Equity < 2.0            (leverage)                               │  │  │
│   │   │  • Promoter holding > 25%       (skin in game)                           │  │  │
│   │   │  • Promoter pledge < 30%        (stress indicator)                       │  │  │
│   │   │  • Free cash flow positive      (sustainability)                         │  │  │
│   │   │                                                                          │  │  │
│   │   │  Grade D or F → REJECT                                                   │  │  │
│   │   │  Grade C → Position multiplier = 0.7x                                    │  │  │
│   │   │  Grade B → Position multiplier = 0.9x                                    │  │  │
│   │   │  Grade A → Position multiplier = 1.0x                                    │  │  │
│   │   └──────────────────────────────────────────────────────────────────────────┘  │  │
│   │                                         │                                        │  │
│   │                                         ▼                                        │  │
│   │   FILTER 3: LIQUIDITY CHECK                                                      │  │
│   │   ┌──────────────────────────────────────────────────────────────────────────┐  │  │
│   │   │  • Average Daily Volume (ADV) must be > ₹10 Cr                           │  │  │
│   │   │  • Position size must be < 2% of ADV                                     │  │  │
│   │   │  • Ensures we can exit in 1 day without impact                           │  │  │
│   │   └──────────────────────────────────────────────────────────────────────────┘  │  │
│   │                                                                                  │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   Output: Filtered candidates that pass all checks                                      │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### PHASE 5: Conviction Scoring

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                           PHASE 5: CONVICTION SCORING                                   │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                  │  │
│   │                    CONVICTION CALCULATOR (0-100 Scale)                           │  │
│   │                                                                                  │  │
│   │   ┌────────────────────────────────────────────────────────────────────────┐    │  │
│   │   │                                                                        │    │  │
│   │   │   COMPONENT              WEIGHT    SCORE     CRITERIA                  │    │  │
│   │   │   ─────────────────────────────────────────────────────────────────── │    │  │
│   │   │                                                                        │    │  │
│   │   │   TECHNICAL SCORE        0-30      [22]      RSI, MACD, MA alignment   │    │  │
│   │   │   ████████████████████████░░░░░░░                                      │    │  │
│   │   │                                                                        │    │  │
│   │   │   CONFLUENCE             0-20      [16]      # of models agreeing      │    │  │
│   │   │   ████████████████████████░░░░░░                                       │    │  │
│   │   │                                                                        │    │  │
│   │   │   CONTEXT/REGIME         0-20      [12]      Market regime score       │    │  │
│   │   │   ████████████████░░░░░░░░░░░░                                         │    │  │
│   │   │                                                                        │    │  │
│   │   │   SECTOR STRENGTH        0-15      [13]      Sector rank (1-10)        │    │  │
│   │   │   ██████████████████████████░░░░                                       │    │  │
│   │   │                                                                        │    │  │
│   │   │   TIMING/MTF             0-10      [6]       Weekly+Daily alignment    │    │  │
│   │   │   ████████████░░░░░░░░░░░░░░░░                                         │    │  │
│   │   │                                                                        │    │  │
│   │   │   ─────────────────────────────────────────────────────────────────── │    │  │
│   │   │   BASE TOTAL             0-95      [69]                                │    │  │
│   │   │                                                                        │    │  │
│   │   │   BONUSES:                                                             │    │  │
│   │   │   FII Flow Bonus         ±5        [+5]      FII buying → +5           │    │  │
│   │   │   F&O Sentiment Bonus    ±3        [+3]      Bullish PCR → +3          │    │  │
│   │   │                                                                        │    │  │
│   │   │   ═══════════════════════════════════════════════════════════════════ │    │  │
│   │   │                                                                        │    │  │
│   │   │   FINAL CONVICTION       0-100     [77]      GRADE: A                  │    │  │
│   │   │   ██████████████████████████████████████████████████████████░░░░░░░░  │    │  │
│   │   │                                                                        │    │  │
│   │   └────────────────────────────────────────────────────────────────────────┘    │  │
│   │                                                                                  │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   CONVICTION LEVEL MAPPING:                                                             │
│   ┌──────────┬─────────┬─────────────┬──────────────────────────────────────────────┐  │
│   │  Level   │  Score  │  Risk/Trade │  Description                                 │  │
│   ├──────────┼─────────┼─────────────┼──────────────────────────────────────────────┤  │
│   │    A+    │  85+    │    2.5%     │  Exceptional - all factors perfectly aligned │  │
│   │    A     │  70-84  │    2.0%     │  High conviction - strong setup              │  │
│   │    B     │  55-69  │    1.0%     │  Standard setup - normal position            │  │
│   │    C     │  40-54  │    0.5%     │  Lower conviction - reduced size             │  │
│   │    D     │  <40    │    0%       │  NO TRADE - insufficient conviction          │  │
│   └──────────┴─────────┴─────────────┴──────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### PHASE 6: Position Sizing & Risk Management

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                           PHASE 6: RISK MANAGEMENT                                      │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                  │  │
│   │                         POSITION SIZING ENGINE                                   │  │
│   │                                                                                  │  │
│   │   INPUTS:                                                                        │  │
│   │   ┌─────────────────────────────────────────────────────────────────────────┐   │  │
│   │   │ Capital              : ₹5,00,000                                        │   │  │
│   │   │ Conviction Level     : A (base risk = 2%)                               │   │  │
│   │   │ Entry Price          : ₹2,500                                           │   │  │
│   │   │ Stop Loss            : ₹2,425 (2x ATR below entry)                      │   │  │
│   │   │ Regime Multiplier    : 0.8x (BULL regime)                               │   │  │
│   │   │ Transition Adjustment: 1.0x (no warning)                                │   │  │
│   │   │ Earnings Multiplier  : 1.0x (no earnings soon)                          │   │  │
│   │   │ Fundamental Mult     : 0.9x (Grade B)                                   │   │  │
│   │   │ Correlation Factor   : 0.8x (1 same-sector position)                    │   │  │
│   │   └─────────────────────────────────────────────────────────────────────────┘   │  │
│   │                                                                                  │  │
│   │   CALCULATION:                                                                   │  │
│   │   ┌─────────────────────────────────────────────────────────────────────────┐   │  │
│   │   │                                                                         │   │  │
│   │   │   Step 1: Base Risk Amount                                              │   │  │
│   │   │           = Capital × Base Risk %                                       │   │  │
│   │   │           = ₹5,00,000 × 2%                                              │   │  │
│   │   │           = ₹10,000                                                     │   │  │
│   │   │                                                                         │   │  │
│   │   │   Step 2: Apply All Multipliers                                         │   │  │
│   │   │           = ₹10,000 × 0.8 × 1.0 × 1.0 × 0.9 × 0.8                       │   │  │
│   │   │           = ₹5,760                                                      │   │  │
│   │   │                                                                         │   │  │
│   │   │   Step 3: Calculate Risk Per Share                                      │   │  │
│   │   │           = Entry - Stop Loss                                           │   │  │
│   │   │           = ₹2,500 - ₹2,425                                             │   │  │
│   │   │           = ₹75                                                         │   │  │
│   │   │                                                                         │   │  │
│   │   │   Step 4: Position Size                                                 │   │  │
│   │   │           = Adjusted Risk ÷ Risk Per Share                              │   │  │
│   │   │           = ₹5,760 ÷ ₹75                                                │   │  │
│   │   │           = 76 shares                                                   │   │  │
│   │   │                                                                         │   │  │
│   │   │   Step 5: Position Value                                                │   │  │
│   │   │           = 76 × ₹2,500                                                 │   │  │
│   │   │           = ₹1,90,000 (38% of capital)                                  │   │  │
│   │   │                                                                         │   │  │
│   │   └─────────────────────────────────────────────────────────────────────────┘   │  │
│   │                                                                                  │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                  │  │
│   │                         RISK CHECK GATES (Veto Power)                            │  │
│   │                                                                                  │  │
│   │   Each check can VETO the trade:                                                 │  │
│   │                                                                                  │  │
│   │   ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐     │  │
│   │   │   PORTFOLIO HEAT    │  │   SECTOR EXPOSURE   │  │    CORRELATION      │     │  │
│   │   ├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤     │  │
│   │   │ Current: 2.1%       │  │ Current: 15%        │  │ Same sector: 1      │     │  │
│   │   │ After:   3.2%       │  │ After:   23%        │  │ Max allowed: 3      │     │  │
│   │   │ Max:     6%         │  │ Max:     30%        │  │                     │     │  │
│   │   │                     │  │                     │  │                     │     │  │
│   │   │ ✓ PASS              │  │ ✓ PASS              │  │ ✓ PASS              │     │  │
│   │   └─────────────────────┘  └─────────────────────┘  └─────────────────────┘     │  │
│   │                                                                                  │  │
│   │   ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐     │  │
│   │   │     LIQUIDITY       │  │     EVENT RISK      │  │    GLOBAL RISK      │     │  │
│   │   ├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤     │  │
│   │   │ ADV: ₹2500 Cr       │  │ Earnings: 15 days   │  │ Score: 2/5          │     │  │
│   │   │ Position: 0.08%     │  │ Buffer: 3 days      │  │ Threshold: 4/5      │     │  │
│   │   │ Max: 2%             │  │                     │  │                     │     │  │
│   │   │                     │  │                     │  │                     │     │  │
│   │   │ ✓ PASS              │  │ ✓ PASS              │  │ ✓ PASS              │     │  │
│   │   └─────────────────────┘  └─────────────────────┘  └─────────────────────┘     │  │
│   │                                                                                  │  │
│   │   ALL CHECKS PASSED ──────────────────────────────────────────▶ PROCEED         │  │
│   │                                                                                  │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   RISK LIMITS SUMMARY:                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  • Portfolio Heat      : Max 6% total risk across all positions                 │  │
│   │  • Single Position     : Max 15% of capital                                     │  │
│   │  • Sector Exposure     : Max 30% per sector                                     │  │
│   │  • Correlated Positions: Max 3 per sector                                       │  │
│   │  • Liquidity           : Min ₹10 Cr ADV, Max 2% of ADV                          │  │
│   │  • Drawdown Scaling    : Reduce size after 5% drawdown                          │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### PHASE 7: Final Output

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                           PHASE 7: FINAL OUTPUT                                         │
│                                                                                         │
│   ══════════════════════════════════════════════════════════════════════════════════   │
│   TRADING SIGNAL - Monday 2026-01-13                                                    │
│   ══════════════════════════════════════════════════════════════════════════════════   │
│                                                                                         │
│   MARKET CONTEXT                                                                        │
│   ├── Regime: BULL (Score: +3) | Position Size: 80% of normal                          │
│   ├── Global: Risk Score 2/5 | VIX: 14.2 | US: +0.3%                                   │
│   ├── Flows: FII +₹1,200 Cr (5D) | Trend: INFLOW | Score: +2                           │
│   ├── F&O: PCR 1.2 | Max Pain: 24,500 | Sentiment: BULLISH                             │
│   └── Transition Warning: LOW (15% probability)                                         │
│                                                                                         │
│   ────────────────────────────────────────────────────────────────────────────────────  │
│                                                                                         │
│   TOP PICK: RELIANCE ₹2,500                                                             │
│                                                                                         │
│   CONVICTION: A (77/100)                                                                │
│   ┌────────────────┬────────┬───────────────────────────────────────────────────────┐  │
│   │ Component      │ Score  │ Notes                                                 │  │
│   ├────────────────┼────────┼───────────────────────────────────────────────────────┤  │
│   │ Technical      │ 22/30  │ RSI bullish, MACD crossover, above EMAs              │  │
│   │ Confluence     │ 16/20  │ 3 models agree (Momentum ✓, Breakout ✓, Trend ✓)     │  │
│   │ Context        │ 12/20  │ BULL regime, supportive environment                  │  │
│   │ Sector         │ 13/15  │ Energy sector - Rank #2                              │  │
│   │ Timing         │  6/10  │ Weekly + Daily aligned                               │  │
│   │ Flow Bonus     │ +5     │ FII buying                                           │  │
│   │ F&O Bonus      │ +3     │ Bullish PCR                                          │  │
│   └────────────────┴────────┴───────────────────────────────────────────────────────┘  │
│                                                                                         │
│   TRADE SETUP                                                                           │
│   ┌────────────────┬────────────┬─────────┬─────────────────────────────────────────┐  │
│   │ Level          │ Price      │ %       │ Notes                                   │  │
│   ├────────────────┼────────────┼─────────┼─────────────────────────────────────────┤  │
│   │ Entry          │ ₹2,500     │    -    │                                         │  │
│   │ Stop Loss      │ ₹2,425     │  -3.0%  │ 2x ATR below entry                      │  │
│   │ Target 1       │ ₹2,612     │  +4.5%  │ Book 50% here                           │  │
│   │ Target 2       │ ₹2,687     │  +7.5%  │ Trail remaining                         │  │
│   │ R:R Ratio      │ 1:2.5      │         │                                         │  │
│   └────────────────┴────────────┴─────────┴─────────────────────────────────────────┘  │
│                                                                                         │
│   POSITION SIZING                                                                       │
│   ┌────────────────┬────────────┬───────────────────────────────────────────────────┐  │
│   │ Metric         │ Value      │ Notes                                             │  │
│   ├────────────────┼────────────┼───────────────────────────────────────────────────┤  │
│   │ Shares         │ 76         │                                                   │  │
│   │ Position Value │ ₹1,90,000  │ 38% of capital                                    │  │
│   │ Risk Amount    │ ₹5,760     │ 1.15% of capital                                  │  │
│   │ Portfolio Heat │ 3.2%       │ After this trade (max 6%)                         │  │
│   └────────────────┴────────────┴───────────────────────────────────────────────────┘  │
│                                                                                         │
│   EXIT STRATEGY                                                                         │
│   └── STANDARD: 2.5% trailing stop from high, book 50% at T1, hold rest for T2        │
│                                                                                         │
│   KEY LEVELS                                                                            │
│   ├── Pivot: ₹2,485 | Resistance: ₹2,520 | Support: ₹2,450                            │
│   └── Max Pain: ₹2,500 (at the money)                                                  │
│                                                                                         │
│   ────────────────────────────────────────────────────────────────────────────────────  │
│                                                                                         │
│   ALTERNATIVE: HDFCBANK                                                                 │
│   Conviction: B (62/100) | Entry: ₹1,650 | Stop: ₹1,600 | Target: ₹1,725              │
│                                                                                         │
│   ────────────────────────────────────────────────────────────────────────────────────  │
│                                                                                         │
│   AVOID TODAY                                                                           │
│   ┌────────────────┬────────────────────────────────────────────────────────────────┐  │
│   │ Stock          │ Reason                                                         │  │
│   ├────────────────┼────────────────────────────────────────────────────────────────┤  │
│   │ TCS            │ Earnings in 2 days                                             │  │
│   │ VEDL           │ High promoter pledge (25%)                                     │  │
│   │ TATASTEEL      │ Weak sector (Metals - Rank #9)                                 │  │
│   └────────────────┴────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   ══════════════════════════════════════════════════════════════════════════════════   │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                              DATA SOURCES & FLOW                                        │
│                                                                                         │
│   EXTERNAL APIs                         INTERNAL PROCESSING          OUTPUT             │
│   ─────────────                         ───────────────────          ──────             │
│                                                                                         │
│   ┌──────────────┐                                                                      │
│   │   Yahoo      │──┐                                                                   │
│   │   Finance    │  │                                                                   │
│   │   (yfinance) │  │     ┌─────────────────────────────────────────────────┐          │
│   └──────────────┘  │     │                                                 │          │
│                     ├────▶│              ENHANCED                           │          │
│   ┌──────────────┐  │     │            ORCHESTRATOR                         │          │
│   │   NSE India  │  │     │                                                 │          │
│   │   (FII/DII,  │──┤     │  ┌───────────┐  ┌───────────┐  ┌───────────┐   │          │
│   │    F&O data) │  │     │  │  Context  │  │  Signal   │  │  Risk     │   │          │
│   └──────────────┘  │     │  │  Layer    │─▶│  Layer    │─▶│  Layer    │───┼────────▶ │
│                     │     │  └───────────┘  └───────────┘  └───────────┘   │          │
│   ┌──────────────┐  │     │       │              │              │          │          │
│   │   Global     │  │     │       ▼              ▼              ▼          │    ┌─────┴─────┐
│   │   Markets    │──┤     │  ┌─────────────────────────────────────────┐   │    │  TRADING  │
│   │   (VIX, S&P) │  │     │  │           DECISION ENGINE               │   │    │  SIGNAL   │
│   └──────────────┘  │     │  │                                         │   │    │           │
│                     │     │  │  Conviction + Position Size + Exit      │   │    │  • Entry  │
│   ┌──────────────┐  │     │  │                                         │   │    │  • Stop   │
│   │   BSE        │──┘     │  └─────────────────────────────────────────┘   │    │  • Target │
│   │   (Earnings) │        │                                                 │    │  • Size   │
│   └──────────────┘        └─────────────────────────────────────────────────┘    └───────────┘
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Interaction Map

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                           COMPONENT DEPENDENCIES                                        │
│                                                                                         │
│                        ┌──────────────────────────────┐                                │
│                        │     ENHANCED ORCHESTRATOR     │                                │
│                        │     (core/enhanced_orch.py)   │                                │
│                        └──────────────┬───────────────┘                                │
│                                       │                                                 │
│              ┌────────────────────────┼────────────────────────┐                       │
│              │                        │                        │                        │
│              ▼                        ▼                        ▼                        │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐                │
│   │    TIER 1        │    │    TIER 2        │    │    TIER 3        │                │
│   │    (Core)        │    │    (Data)        │    │    (Advanced)    │                │
│   └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘                │
│            │                       │                       │                           │
│            │                       │                       │                           │
│   Components:              Components:              Components:                         │
│   • Orchestrator           • F&O Data               • Regime Transition                │
│   • Conviction Scorer      • FII/DII Tracker        • Adaptive Exits                   │
│   • Context Builder        • Earnings Calendar      • Walk-Forward Backtest            │
│   • Regime Detector        • Fundamentals Filter    • Intraday Levels                  │
│   • Position Sizing                                 • Trade Journal                    │
│                                                                                         │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              MODELS (Ensemble)                                   │  │
│   │                                                                                  │  │
│   │    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐                │  │
│   │    │ Momentum │    │ Breakout │    │  Trend   │    │   Mean   │                │  │
│   │    │  Model   │    │  Model   │    │Following │    │Reversion │                │  │
│   │    └──────────┘    └──────────┘    └──────────┘    └──────────┘                │  │
│   │                                                                                  │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              INDICATORS                                          │  │
│   │                                                                                  │  │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │  │
│   │  │Technical │ │  Price   │ │  Sector  │ │   MTF    │ │   Trend  │              │  │
│   │  │(RSI,MACD)│ │  Action  │ │ Strength │ │Alignment │ │ Strength │              │  │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘              │  │
│   │                                                                                  │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              DATA LAYER                                          │  │
│   │                                                                                  │  │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐                                        │  │
│   │  │ Fetcher  │ │  Cache   │ │  Config  │                                        │  │
│   │  │(yfinance)│ │ (SQLite) │ │(stocks)  │                                        │  │
│   │  └──────────┘ └──────────┘ └──────────┘                                        │  │
│   │                                                                                  │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
nifty-signals/
│
├── core/                              # TIER 1 - Core Brain
│   ├── __init__.py
│   ├── orchestrator.py                # Master decision engine
│   ├── enhanced_orchestrator.py       # Enhanced with Tier 2/3
│   ├── conviction.py                  # Conviction scoring (0-100)
│   └── context.py                     # Global + domestic context
│
├── models/                            # TIER 1 - Signal Models
│   ├── __init__.py
│   ├── ensemble.py                    # Multi-model voting
│   ├── momentum.py                    # Momentum model
│   ├── breakout.py                    # Breakout model
│   ├── trend_following.py             # Trend following model
│   └── mean_reversion.py              # Mean reversion model
│
├── indicators/                        # Technical Analysis
│   ├── __init__.py
│   ├── technical.py                   # RSI, MACD, MAs, Bollinger
│   ├── price_action.py                # Support/Resistance
│   ├── market_regime.py               # Regime detection
│   ├── multi_timeframe.py             # MTF alignment
│   ├── sector_strength.py             # Sector rankings
│   ├── regime_transition.py           # TIER 3 - Transition warning
│   └── intraday_levels.py             # TIER 3 - Pivot points
│
├── data/
│   ├── __init__.py
│   ├── fetcher.py                     # yfinance wrapper
│   ├── cache.py                       # SQLite caching
│   └── sources/                       # TIER 2 - Data Sources
│       ├── __init__.py
│       ├── fo_data.py                 # F&O: PCR, Max Pain, OI
│       ├── fii_dii.py                 # Institutional flows
│       ├── earnings.py                # Earnings calendar
│       └── fundamentals.py            # Quality filter
│
├── risk/                              # Risk Management
│   ├── __init__.py
│   ├── position_sizing.py             # ATR-based sizing
│   ├── exit_strategy.py               # Exit rules
│   └── adaptive_exits.py              # TIER 3 - Dynamic exits
│
├── backtest/                          # Validation
│   ├── __init__.py
│   ├── engine.py                      # Backtest engine
│   ├── metrics.py                     # Performance metrics
│   └── walk_forward.py                # TIER 3 - OOS validation
│
├── journal/                           # TIER 3 - Trade Tracking
│   └── trade_journal.py               # Full trade journal
│
├── signals/                           # Signal Generation
│   ├── __init__.py
│   ├── generator.py                   # Basic generator
│   └── enhanced_generator.py          # Enhanced with all features
│
├── output/                            # Display
│   ├── __init__.py
│   └── cli.py                         # Rich table output
│
├── .claude/skills/                    # Claude Skills
│   ├── trade.md                       # Master /trade skill
│   ├── scan.md                        # Quick scan
│   ├── macro.md                       # Macro analysis
│   └── news.md                        # News check
│
├── main.py                            # CLI entry point
├── config.py                          # Configuration
├── stocks.json                        # Nifty 100 symbols
├── requirements.txt                   # Dependencies
└── CLAUDE.md                          # System documentation
```

---

## Legendary Principles Applied

### Jim Simons (Renaissance Technologies)
- **Multi-model ensemble**: 4 independent models vote
- **Statistical edge**: Conviction scoring, not gut feeling
- **Walk-forward validation**: Proper out-of-sample testing

### Ray Dalio (Bridgewater)
- **Systematic principles**: Every decision has rules
- **Risk parity**: Correlation-aware position sizing
- **Regime awareness**: Adjust to market conditions

### Stanley Druckenmiller
- **Conviction-based sizing**: A = 2%, B = 1%, C = 0.5%
- **Concentrate when right**: Higher conviction = larger size
- **Cut fast when wrong**: Tight stops, adaptive exits

### Paul Tudor Jones
- **Defense first**: Max 6% portfolio heat
- **Global macro awareness**: VIX, US, Asia, flows
- **Never blow up**: Multiple risk gates

### Ed Seykota
- **Trend following with judgment**: Models + regime context
- **Let winners run**: Trailing stops in trends
- **Cut losers short**: Time decay exits

---

## Quick Reference

### When You Type "trade"

```
User: "trade"
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  1. CONTEXT    →  What's the market environment?                 │
│  2. REGIME     →  Should we trade at all?                        │
│  3. SCAN       →  Which stocks have signals?                     │
│  4. FILTER     →  Remove earnings/weak fundamentals              │
│  5. SCORE      →  How confident are we? (A/B/C/D)                │
│  6. SIZE       →  How much to risk?                              │
│  7. CHECK      →  Any portfolio limits hit?                      │
│  8. OUTPUT     →  Final recommendation with full reasoning       │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
"BUY RELIANCE @ ₹2,500 | Stop: ₹2,425 | Target: ₹2,612 | 76 shares"
```

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Files | 57 |
| Lines of Code | ~16,000 |
| Models | 4 (Ensemble) |
| Indicators | 15+ |
| Data Sources | 4 (Tier 2) |
| Advanced Systems | 5 (Tier 3) |
| Risk Checks | 6 gates |
| Conviction Levels | 5 (A+ to D) |

---

*Document generated for Nifty Signals Trading System*
*Repository: https://github.com/SwajanJain/nifty-signals*
