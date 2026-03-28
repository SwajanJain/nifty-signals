# Budget Live Analysis Playbook
## Reference for Every Announcement During FM's Speech

---

## STEP 0: PRE-BUDGET BASELINE (Run BEFORE speech starts)

### 0A. Macro Scoreboard

Capture the live snapshot BEFORE the speech. Update AFTER speech ends.

```bash
# Get current regime, VIX, Nifty level:
python3 main.py regime

# Get sector positioning:
python3 main.py sectors
```

| Metric | Pre-Speech | Post-Speech | Delta |
|--------|-----------|-------------|-------|
| **Nifty** | _____ | _____ | _____ |
| **VIX** | _____ | _____ | _____ |
| **Regime** | _____ | _____ | _____ |
| **FII Net (Today)** | _____ | _____ | _____ |
| **SGX Nifty / Gift Nifty** | _____ | _____ | _____ |

#### VIX Thresholds (Dynamic - Always Check Live)
```
VIX < 14     → NORMAL     → Full position sizes per conviction
VIX 14-18    → ELEVATED   → 75% of normal position sizes
VIX 18-22    → HIGH       → 50% of normal position sizes
VIX > 22     → EXTREME    → 25% of normal or CASH ONLY
```
> **NEVER hard-code VIX.** Always run `python3 main.py regime` for live value.

---

### 0B. Expectations Baseline (The "Priced-In" Map)

**Before the speech, document what the street ALREADY expects.** This is the single most important step for avoiding "buy the news that was already priced in" traps.

#### How to Build the Expectations Map:
```
# Web search for consensus:
"union budget [YEAR] expectations consensus analysts"
"budget [YEAR] sectors expected to benefit brokerages"
"budget [YEAR] fiscal deficit capex expected"

# Sources to check:
- Brokerage pre-budget notes (Kotak, ICICI Sec, Motilal Oswal, Jefferies, JM Financial)
- Moneycontrol / ET / Livemint budget expectations pages
- Bloomberg Quint pre-budget analysis
```

#### Record the Consensus:

| Theme | Street Expectation | Confidence |
|-------|-------------------|------------|
| Fiscal Deficit FY27 | ___% of GDP | HIGH/MED/LOW |
| Capex Target | Rs ___ Lakh Cr | HIGH/MED/LOW |
| Income Tax Changes | Slab change / No change | HIGH/MED/LOW |
| Defence Allocation | ___% growth | HIGH/MED/LOW |
| Sector #1 Expected Winner | _____ | HIGH/MED/LOW |
| Sector #2 Expected Winner | _____ | HIGH/MED/LOW |
| Key Policy Expected | _____ | HIGH/MED/LOW |

#### Pre-Budget Rally Tracker:

| Sector/Stock | 1-Month Pre-Budget Move | "Priced-In" Risk |
|-------------|------------------------|-----------------|
| _____ | +___% | HIGH/MED/LOW |

> **RULE: If a stock/sector rallied >15% in the month before budget on anticipation of exactly what was announced, the REAL move is likely a sell-the-news fade.**

---

## STEP 1: CLASSIFY THE ANNOUNCEMENT

| Type | Examples | Urgency |
|------|----------|---------|
| TAX_CHANGE | Income tax slabs, corporate tax, LTCG, STT, customs duty | HIGH - multi-year trend |
| CAPEX_ALLOCATION | Defence, railway, infra, housing spend numbers | HIGH - order book impact |
| POLICY_SCHEME | PLI, FAME, PM-KISAN, Ayushman, new schemes | MEDIUM - execution dependent |
| FISCAL_NUMBER | Deficit target, borrowing, debt-to-GDP | MEDIUM - market sentiment |
| REGULATORY | FDI limits, sector deregulation, banking reforms | MEDIUM-HIGH |
| DUTY_CHANGE | Customs duty up/down on specific items | HIGH - immediate P&L impact |

### 1B. Delta vs Expectations (For EVERY Announcement)

**The market doesn't trade news. It trades the DELTA between expectations and reality.**

For each announcement, immediately ask:

| Question | Answer |
|----------|--------|
| Was this expected by the street? | YES / PARTIALLY / NO |
| How does the ACTUAL number compare to consensus? | ABOVE / IN-LINE / BELOW |
| Surprise Score (1-10) | 1 = fully priced in, 10 = total shock |
| Pre-budget rally in beneficiary stocks? | YES (___%) / NO |
| Net surprise direction | POSITIVE / NEGATIVE / NEUTRAL |

#### Surprise Score Guide:
```
1-2:  Fully priced in. Every brokerage note predicted this exact thing.
3-4:  Mostly expected. The direction was known, quantum is close to consensus.
5-6:  Partial surprise. Direction expected but quantum or specific stocks surprised.
7-8:  Genuine surprise. Theme wasn't in top-5 consensus expectations.
9-10: Total shock. Nobody saw this coming. Sector wasn't even discussed.
```

> **GATE: If Surprise Score < 3 AND stock rallied >10% pre-budget, cap conviction at B regardless of other scores. The alpha is gone.**

---

### 1C. Fine Print Verification (For EVERY Announcement)

Before getting excited by a headline number, verify:

| Check | Answer |
|-------|--------|
| What is the ACTUAL Rs number? (not just "increased") | Rs _____ Cr |
| Effective from when? (This FY / Next FY / Phased) | _____ |
| Over what period? (Annual / 5-year / 10-year) | _____ |
| Annual run-rate (if multi-year) | Rs _____ Cr/year |
| Is this NEW money or repackaged from existing scheme? | NEW / REPACKAGED |
| Any fine print conditions? (State matching, private co-invest) | _____ |
| Previous scheme performance? (If expansion of existing) | Utilization ___% |

#### Red Flags:
- **"Up to Rs X Cr"** → May never reach full allocation
- **"Over 5 years"** → Annual impact is 1/5th of headline
- **"Subject to state participation"** → Execution dependent on state govts
- **"To be notified"** → Rules not yet written, actual implementation unclear
- **No specific Rs number mentioned** → Aspirational, not allocated

> **RULE: Trade the ANNUAL run-rate, not the headline number. Rs 50,000 Cr over 10 years = Rs 5,000 Cr/year = modest.**

---

## STEP 2: MAP THE VALUE CHAIN (For Every Announcement)

```
ANNOUNCEMENT
  │
  ├─ 1ST ORDER (Direct) ── Who receives the money / policy benefit directly?
  │   Examples: Defence capex → HAL, BEL get orders directly
  │
  ├─ 2ND ORDER (Supply Chain) ── Who supplies to the direct beneficiaries?
  │   Examples: Defence capex → steel suppliers, electronics component makers,
  │             raw material providers, testing labs
  │
  ├─ 3RD ORDER (Enablers) ── Who finances, transports, enables delivery?
  │   Examples: Defence capex → defence-focused NBFCs, logistics companies,
  │             IT services for defence, training companies
  │
  ├─ 4TH ORDER (Demand Ripple) ── Consumer/market behavior shifts?
  │   Examples: Income tax cut → more disposable income → retail, auto,
  │             travel, discretionary spending, EMI affordability → housing
  │
  └─ NEGATIVE IMPACT ── Who LOSES from this announcement?
      Examples: Duty cut on imports → domestic manufacturers hurt
               Tax on F&O → brokers, exchanges lose volume
```

---

## STEP 3: STOCK SELECTION CRITERIA

### A. Qualitative Analysis (Jhunjhunwala + Damani Framework)

For each candidate stock, evaluate:

| Factor | Question | Weight |
|--------|----------|--------|
| **Moat** | Does this company have pricing power, monopoly, or network effects? | 25% |
| **Management** | Is management aligned with shareholders? Capital allocation track record? | 20% |
| **Market Share** | Is this the #1 or #2 player? Can they capture govt spending? | 20% |
| **Order Book** | Does this announcement directly add to their order pipeline? | 15% |
| **Execution** | Can they deliver? Past govt contract execution history? | 10% |
| **Valuation** | Is the stock fairly valued or already pricing in the budget benefit? | 10% |

### Key Questions (Think Like the Legends):
- **Jhunjhunwala**: "Which company will CAPTURE the most revenue from this policy? Who has the MOAT?"
- **Damani**: "Which boring, under-the-radar company will quietly compound from this for 5 years?"
- **Druckenmiller**: "Where is the ASYMMETRIC bet? Low downside, massive upside if this plays out?"
- **PTJ**: "What can go WRONG? What's the risk I'm not seeing?"
- **Seykota**: "Is this stock already in a TREND? Don't fight the tape."

---

### B. Quantitative Analysis (Run These Tools)

#### Technical Analysis (from nifty-signals system)
```bash
# Run for each candidate stock:
python3 main.py analyze-enhanced SYMBOL --capital 1000000

# This gives:
# - Signal: STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
# - Score: -15 to +15
# - RSI(14): Overbought >70, Oversold <30
# - MACD: Bullish/Bearish crossover
# - ADX: Trend strength (>25 = strong trend)
# - Bollinger: Position relative to bands
# - Volume: Confirmation of price action
# - Multi-timeframe: Daily + Weekly alignment
# - Support/Resistance: Key levels
# - ATR-based stop loss and targets
# - Position sizing based on conviction
```

#### Fundamental Metrics (via WebSearch or screener.in)
```
For each stock, search and record:
- Market Cap
- PE Ratio (vs sector avg, vs own 5yr avg)
- Revenue Growth (3yr CAGR)
- Profit Growth (3yr CAGR)
- ROE / ROCE
- Debt-to-Equity
- Promoter Holding (and recent changes)
- FII/DII holding (and recent changes)
- Order Book / Revenue Visibility (for capex plays)
- Free Cash Flow
- Dividend Yield
```

#### Sector Context
```bash
# Check sector relative strength:
python3 main.py sectors

# Key metrics:
# - Sector RS Score (>1.0 = outperforming Nifty)
# - 1-month momentum
# - Strength classification: STRONG / MODERATE / WEAK / VERY WEAK
```

---

## STEP 4: SCORING & CONVICTION

### Conviction Score (0-100)

| Component | Max Score | How to Calculate |
|-----------|-----------|-----------------|
| **Technical** | 20 | From analyze-enhanced score. +15 = 20/20, +10 = 16/20, +5 = 10/20 |
| **Budget Impact** | 15 | Direct allocation = 13-15. Indirect = 8-11. Marginal = 3-7 |
| **Surprise Factor** | 15 | Surprise Score x 1.5. Fully priced-in (1-2) = 2-3. Shock (9-10) = 14-15 |
| **Sector Strength** | 15 | RS > 1.05 = 15. RS 1.0-1.05 = 10. RS < 1.0 = 5 |
| **Fundamental Quality** | 15 | ROE>15 + Low Debt + Growth = 15. Mixed = 8-10. Poor = 3-5 |
| **Moat & Mgmt** | 10 | Monopoly/Duopoly = 10. Strong brand = 7. Commodity = 3 |
| **Timing** | 10 | Not near earnings + Good MTF + Volume confirm = 10 |
| **TOTAL** | **100** | |

### GATES (Hard Filters - Any ONE can block a trade)

| Gate | Condition | Action |
|------|-----------|--------|
| **Priced-In Gate** | Surprise Score < 3 AND stock up >10% pre-budget | Cap at B, max 1% risk |
| **VIX Gate** | VIX > 22 | No new positions |
| **Regime Gate** | Regime = CRASH or STRONG_BEAR | Cash only |
| **Technical Gate** | Score < 0 (negative) | Skip regardless of catalyst |
| **Liquidity Gate** | ADV < 10 Cr | Skip |

### Conviction Grades
| Grade | Score | Risk Per Trade | Action |
|-------|-------|---------------|--------|
| A+ | 85+ | 2.5% of capital | Max conviction - concentrate |
| A | 70-84 | 2.0% | High conviction - full size |
| B | 55-69 | 1.0% | Standard setup |
| C | 40-54 | 0.5% | Small position |
| D | <40 | 0% | NO TRADE |

---

## STEP 5: TRADE SETUP (For Final Picks)

### Entry, Stop, Targets
```
Entry:     Current price (or pullback level if chasing)
Stop Loss: ATR-based (2x ATR below entry) OR budget-day low
Target 1:  1.5x risk (R:R = 1.5:1)
Target 2:  3x risk (R:R = 3:1)
Position:  Based on conviction grade and capital
Max Risk:  Per conviction table above
```

### Gap & Whipsaw Handling (Budget Day Specific)

```
BUDGET DAY GAP RULES:
─────────────────────
Gap Up > 5%:   DO NOT CHASE. Wait for first 30-min pullback.
               Use VWAP as intraday anchor. Enter only if stock
               holds above VWAP after pullback.

Gap Up 2-5%:   Acceptable entry if conviction A or A+.
               Reduce size by 25%. Use budget-day low as stop.

Gap Down:      If your thesis is intact and the gap is sector-wide
               (not stock-specific bad news), this is OPPORTUNITY.
               Scale in at 50% size, add on VWAP reclaim.

WHIPSAW DEFENSE:
─────────────────
- Budget day = maximum whipsaw risk
- First 30 minutes after speech ends: OBSERVE ONLY
- Wait for institutional flow direction (post-1:30 PM)
- If stock reverses >3% from budget-day high within 2 hours,
  the initial move was likely retail euphoria. Stand aside.

VWAP RULES:
- Stock above VWAP = institutional buying, safe to enter
- Stock below VWAP = selling pressure, wait
- VWAP cross from below = entry signal
- VWAP rejection from above = exit/reduce signal
```

### Position Sizing Formula
```
Risk Amount = Capital x Risk% (from conviction grade)
Position Size = Risk Amount / (Entry - Stop Loss)
Position Value = Position Size x Entry Price
Check: Position Value < 15% of Capital (hard limit)
Check: Sector total < 30% of Capital
```

---

## STEP 6: OUTPUT FORMAT (For Each Announcement)

```markdown
## BUDGET ANNOUNCEMENT: [What FM Said]

### Impact Classification: [TAX_CHANGE / CAPEX / POLICY / DUTY / etc.]
### Market Impact: [BULLISH / BEARISH / NEUTRAL] for [sectors]
### Surprise Score: [X]/10 — [Was this expected? How does it compare to consensus?]

### Value Chain Analysis:
**1st Order (Direct):** [Stocks] - [Why]
**2nd Order (Supply):** [Stocks] - [Why]
**3rd Order (Enable):** [Stocks] - [Why]
**Negative Impact:** [Stocks] - [Why]

### Fine Print Check:
- Actual Rs amount: [X]
- Effective from: [date]
- Annual run-rate: [X]
- New or repackaged: [X]

### TOP PICK: [SYMBOL] @ Rs [PRICE]
| Metric | Value |
|--------|-------|
| Technical Score | [X]/20 |
| Budget Impact | [X]/15 |
| Surprise Factor | [X]/15 |
| Sector RS | [X]/15 |
| Fundamentals | [X]/15 |
| Moat & Mgmt | [X]/10 |
| Timing | [X]/10 |
| **CONVICTION** | **[X]/100 = [GRADE]** |
| **Gates Passed?** | [All clear / Which gate failed?] |

**Trade Setup:**
- Entry: Rs [X]
- Stop: Rs [X] ([X]%)
- T1: Rs [X] (+[X]%)
- T2: Rs [X] (+[X]%)
- Position: [X] shares (Rs [X])
- Risk: Rs [X] ([X]% of capital)

**Jhunjhunwala View:** [Why this stock captures the budget theme]
**Damani View:** [Hidden compounder angle]
**Risk Warning:** [What could go wrong]
```

---

## STEP 7: CUMULATIVE TRACKER

After each announcement, update the running scorecard:

```markdown
| # | Announcement | Top Stock | Conv. | Grade | Surprise | Sector |
|---|-------------|-----------|-------|-------|----------|--------|
| 1 | [news]      | [SYMBOL]  | [X]   | [A/B] | [X]/10   | [sect] |
| 2 | [news]      | [SYMBOL]  | [X]   | [A/B] | [X]/10   | [sect] |
...

PORTFOLIO HEAT CHECK:
- Total positions considered: [X]
- Total risk if all taken: [X]% (max 6%)
- Sector concentration: [check 30% limit]
- Correlated positions: [check 3/sector limit]
- Average surprise score: [X]/10 (if <4, portfolio is mostly "priced-in" plays)

MACRO SCOREBOARD (Updated):
- VIX: [X] → Position sizing at [X]% of normal
- Regime: [X]
- Nifty move since speech start: [X]%
```

---

## QUICK REFERENCE: TOOLS TO RUN

```bash
# Single stock deep analysis (MOST USED):
python3 main.py analyze-enhanced SYMBOL --capital 1000000

# Scan specific stocks (batch):
python3 main.py enhanced-scan --stocks "STOCK1,STOCK2,STOCK3" --capital 1000000

# Full universe scan:
python3 main.py enhanced-scan --top 10 --capital 1000000

# Market regime (INCLUDES LIVE VIX):
python3 main.py regime

# Sector strength:
python3 main.py sectors

# Reddit sentiment:
python3 main.py reddit --cached
```

## QUICK REFERENCE: WEB SEARCHES TO RUN

```
# For fundamental data:
"[STOCK] market cap PE ratio ROE 2026"
"[STOCK] order book revenue visibility FY26"
"[STOCK] promoter holding FII DII latest"
"[STOCK] quarterly results Q3 FY26"

# For value chain mapping:
"[SECTOR] value chain India listed companies"
"[POLICY] beneficiary stocks India NSE"
"who supplies to [COMPANY] India"
"[SECTOR] ancillary companies India stock market"

# For competitive analysis:
"[SECTOR] market share India top companies"
"[STOCK] vs [COMPETITOR] comparison"

# For expectations baseline (PRE-BUDGET):
"union budget [YEAR] expectations consensus analysts"
"budget [YEAR] sectors expected to benefit brokerages"
"[SECTOR] pre-budget rally stocks"
```

---

## BUDGET DAY SPECIFIC RULES

1. **HALF position sizes** - Budget day = event risk
2. **No trades before 12:30 PM** - Let speech complete
3. **Max 3 new positions today** - Don't scatter capital
4. **Monday is the REAL opportunity** - Institutions act then
5. **Check VIX LIVE** - Run `python3 main.py regime` for current VIX and apply thresholds above
6. **Follow the MONEY, not the WORDS** - Actual numbers > promises
7. **Avoid losers > Chase winners** - Negative surprises drop 10-20%
8. **Trade the DELTA, not the headline** - Surprise vs expectation is what moves stocks
9. **Don't chase gaps >5%** - Wait for VWAP pullback, enter on institutional confirmation
10. **Watch for sell-the-news** - Sectors with >15% pre-budget rally + in-line announcement = fade

---

## STOCK UNIVERSE

**Effective: Feb 1, 2026 ~11:45 AM IST**

Universe expanded from **Nifty 100 → Nifty 500** during live session to capture mid-cap budget beneficiaries.

### Universe Rules
```
PRIMARY:    Nifty 500 constituents (for budget analysis stock picks)
TECHNICAL:  Run analyze-enhanced for any candidate before adding to portfolio
LIQUIDITY:  ADV > 10 Cr (hard filter, same as before)
POSITION:   Mid-caps (outside Nifty 100) → cap at 10% of capital per position (vs 15% for large-caps)
SECTOR:     Max 30% per sector still applies
```

### Newly Active Candidates (Previously Watchlist/Midcap Gems)

#### Electronics / EMS (Rs 40K Cr Scheme)
| Stock | Theme | Conviction Estimate | Priority |
|-------|-------|-------------------|----------|
| **KAYNES** | Only listed PCB fabricator in India. End-to-end EMS. | A (fundamental) | HIGH - run analyze-enhanced |
| DIXON | India's largest EMS by revenue | AVOID (Score -5, SKIP) | DO NOT BUY - technically broken |

#### Infrastructure / CIE / Construction Equipment
| Stock | Theme | Conviction Estimate | Priority |
|-------|-------|-------------------|----------|
| **ACE** | India's #1 crane maker. Direct CIE beneficiary. | A | HIGH - run analyze-enhanced |
| **BEML** | Heavy earthmoving PSU. CIE + mining equipment. | A | MEDIUM |
| **BRAITHWAITE** | Only listed container manufacturer (Rs 10K Cr scheme) | A | HIGH - monopoly play |

#### High-Speed Rail (7 Corridors)
| Stock | Theme | Conviction Estimate | Priority |
|-------|-------|-------------------|----------|
| **IRCON** | Rail EPC contractor - executes HSR corridor projects | A | HIGH |
| **RVNL** | Rail project executor - DPR + execution | A | HIGH |
| **TITAGARH** | Rolling stock manufacturer for HSR coaches | A | HIGH |
| **RITES** | Railway consultancy PSU - DPR prep for all 7 corridors | B+ | MEDIUM |
| JUPITERWAG | Wagons + expanding to passenger coaches | B | LOW |

#### Textiles (Mega Parks + India-EU FTA)
| Stock | Theme | Conviction Estimate | Priority |
|-------|-------|-------------------|----------|
| **KPRMILL** | Most vertically integrated textile co. Best margins. | A | HIGH - Damani pick |
| LAXMIMACH | Monopoly textile machinery maker (picks-and-shovels) | B+ | MEDIUM |
| WELSPUNLIV | Export champion, home textiles | B | LOW |
| VARDHMAN | Cheapest PE in textiles | B | LOW |

#### CCUS / Carbon Capture (Rs 20K Cr + Rs 38.9K Cr Programme)
| Stock | Theme | Conviction Estimate | Priority |
|-------|-------|-------------------|----------|
| **ALKYLAMINE** | HIDDEN GEM - Amine solvents used in EVERY CCUS plant. Recurring demand. | B+ | HIGH - unique angle |
| **THERMAX** | CCUS emission control equipment manufacturer | B+ | MEDIUM |
| WELCORP | CO2 pipeline manufacturer (if pipeline network announced) | B+ | LOW - conditional |

#### Chemical Parks (Rs 600 Cr, 3 Parks)
| Stock | Theme | Conviction Estimate | Priority |
|-------|-------|-------------------|----------|
| SRF | Specialty chemicals, fluorochemicals | B+ | MEDIUM |
| AARTIIND | Specialty chemicals, benzene chain | B+ | MEDIUM |
| NAVINFLUOR | Fluorine chemistry | B | LOW |
| PIIND | Agrochemicals CSM | B | LOW |

### Screening Protocol for New Candidates
```bash
# Step 1: Run technical analysis
python3 main.py analyze-enhanced SYMBOL --capital 1000000

# Step 2: Check result
# Score > 0 → Proceed to Step 3
# Score < 0 → SKIP regardless of budget catalyst

# Step 3: Fundamental check via screener.in or WebSearch
# PE, ROE, Debt, Promoter holding, Order book

# Step 4: Apply full conviction scoring (Step 4 of this playbook)
# Including Surprise Factor and Gates

# Step 5: If conviction >= B (55+), add to confirmed buys
# If conviction < B, keep on watchlist
```

### Mid-Cap Risk Adjustments
```
POSITION SIZE:  Max 10% of capital (vs 15% for Nifty 100 large-caps)
LIQUIDITY:      Must have ADV > 10 Cr (check before entry)
STOP LOSS:      Wider stops for mid-caps (2.5x ATR vs 2x for large-caps)
SLIPPAGE:       Budget for 0.5% slippage on entry/exit (vs 0.1% for large-caps)
CONCENTRATION:  Max 2 mid-cap positions per sector
TOTAL MID-CAP:  Max 40% of portfolio in mid-caps (rest in Nifty 100 large-caps)
```

---

*This playbook is the single source of truth for every announcement analysis.*
*Created: Feb 1, 2026 | Budget Day Live Session*
*Patched: Feb 1, 2026 | Post-Codex Review - Added Steps 0, 1B, 1C, Gates, Gap Rules, Live VIX*
*Patched: Feb 1, 2026 | Universe expanded Nifty 100 → Nifty 500. Mid-cap candidates, screening protocol, risk adjustments added.*
