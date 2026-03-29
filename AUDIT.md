# NIFTY SIGNALS — PRODUCT AUDIT CHECKLIST

**Auditor:** External independent review
**Scope:** End-to-end product audit — technical correctness, financial accuracy, and investor safety
**Method:** Each item will be verified against the actual codebase. Status will be marked after review.

> Legend: `[ ]` = Not checked | `[PASS]` = Verified correct | `[FAIL]` = Issue found | `[WARN]` = Works but has concerns

---

## I. DATA INTEGRITY AUDIT

The foundation. If the data is wrong, every model built on top is wrong.

### A. Data Source Reliability

- [ ] **A1. Screener.in scraping correctness** — Are we parsing the HTML tables correctly? Do column headers map to the right year? Are trailing `+` in labels (e.g., `"Borrowings+"`) handled everywhere, not just in some modules?
- [ ] **A2. Symbol mapping completeness** — All 520 Nifty 500 symbols resolve to valid screener.in pages (no silent 404s returning empty data).
- [ ] **A3. yfinance data alignment** — Does yfinance price data match screener.in's current price? Tolerance check (should be <2% for same-day data). Detect cases where yfinance returns stale/empty data.
- [ ] **A4. Data freshness** — Cache expiry is 7 days. Is 7 days acceptable for quarterly results, shareholding patterns? Are there fields that go stale faster (e.g., current_price, market_cap)?
- [ ] **A5. Consolidated vs standalone** — Does the fetcher correctly prefer consolidated financials? Are there companies where standalone is the correct choice (e.g., holding companies)?

### B. Data Parsing Edge Cases

- [ ] **B1. Missing fields don't silently become zero** — If screener.in doesn't report a field (e.g., FCF, dividend yield), does it become `0.0` and then get treated as "zero value" rather than "missing"? This is critical — a PE of 0 means "not available," not "free stock."
- [ ] **B2. Negative values handled correctly** — Negative PE (loss-making), negative FCF, negative book value (eroded net worth). Are these filtered or do they produce garbage scores?
- [ ] **B3. Banking/NBFC financial statement structure** — Banks don't have "Sales" or "EBITDA." They have NII, provisions, NPA. Does every module that reads P&L handle this, or do banking stocks silently get wrong numbers?
- [ ] **B4. New listing / IPO stocks** — Stocks with <3 years of data. Do 5Y CAGR calculations blow up? Do screens that require "consistent 5Y ROCE" correctly handle partial data?
- [ ] **B5. Demerger/restructuring data continuity** — Companies like Jio Financial (demerged from RIL) or Eternal/Zomato (renamed). Is historical data continuous or does it have a cliff?
- [ ] **B6. Currency and unit consistency** — Market cap is in Cr, but some screener fields may be in lakhs or absolute numbers. Is the Cr → absolute conversion (×1e7) applied uniformly and correctly?

### C. Data Completeness (Cross-Module)

- [ ] **C1. Which fields are actually populated?** — For a sample of 20 stocks across sectors: how many of the ~50 FundamentalProfile fields are non-zero? Are there fields that are always zero (dead code)?
- [ ] **C2. Quarterly data depth** — How many quarters are available? Some modules assume 8 quarters (2Y). What if only 4 are present?
- [ ] **C3. Shareholding data availability** — Is promoter/FII/DII holding available for all 520 stocks? What about quarterly change data?

---

## II. FINANCIAL MODEL CORRECTNESS AUDIT

Does the system implement the published academic/practitioner models correctly?

### A. Scoring Models (Piotroski, Altman, Beneish)

- [ ] **A1. Piotroski F-Score** — Compare implementation against the original 2000 paper. All 9 criteria correct? Specifically: is "change in current ratio" computed as current year vs prior year (not absolute level)? Is "change in gross margin" the margin delta (not the margin itself)?
- [ ] **A2. Altman Z-Score** — Correct formula variant used? Manufacturing vs non-manufacturing vs private company? India-specific adjustments needed? Is it correctly skipped for banks?
- [ ] **A3. Beneish M-Score** — All 8 variables (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) implemented? The summary said DSRI and GMI use "neutral defaults" — does this materially bias the score toward "clean" when data is missing?
- [ ] **A4. Scoring model boundary conditions** — What happens when a stock has exactly the threshold value? (e.g., Altman Z = 1.81 or 2.99). Consistent >= vs > usage?

### B. Valuation Models (DCF, DDM, Peer, Monte Carlo)

- [ ] **B1. DCF — WACC calculation** — Is the cost of equity (Ke = Rf + β×ERP) reasonable for India? Is beta assumed or calculated? Is the equity risk premium (6%) current and appropriate?
- [ ] **B2. DCF — Growth rate selection** — Which growth rate is used (revenue vs profit vs EPS)? Is there a cap? The summary says 30% cap — is that reasonable for high-growth India companies?
- [ ] **B3. DCF — Terminal value dominance** — What percentage of the total DCF value comes from terminal value vs projected cash flows? If >70%, the model is essentially just a perpetuity calculation with extra steps. Flag stocks where TV > 80% of EV.
- [ ] **B4. DCF — Net debt calculation** — Verified that net debt = borrowings - cash (not borrowings - total assets). Spot check 5 stocks against annual reports.
- [ ] **B5. DDM — Applicability** — Is DDM only applied to dividend-paying stocks? What happens for a growth stock with 0 dividend — does it return 0 fair value or N/A?
- [ ] **B6. DDM — Dividend growth assumption** — Where does the growth rate come from? Is it sustainable (not exceeding ROE × retention ratio)?
- [ ] **B7. Peer Relative — Sector benchmarks** — Are the sector median PE/PB/EV-EBITDA benchmarks current? Hardcoded or dynamically computed? How many sectors are covered?
- [ ] **B8. Peer Relative — Sector classification accuracy** — Is every stock in the right sector? Does the system use its own classification or screener.in's? Misclassification directly skews the "premium/discount" signal.
- [ ] **B9. Monte Carlo — Parameter distributions** — Are the distributions (growth, WACC, terminal growth) reasonable? Is the seed fixed (reproducible but not random across runs)?
- [ ] **B10. Monte Carlo — Extreme values** — Are there simulations producing negative fair value? Infinite fair value (WACC ≈ terminal growth)? Are these clamped or filtered?
- [ ] **B11. Cross-model consistency** — For the same stock, do DCF/DDM/Peer/MC produce fair values in the same order of magnitude? If DCF says ₹500 and Peer says ₹5000, something is structurally wrong in one model.

### C. Screening Strategies

- [ ] **C1. Value Screen (Graham/Buffett)** — PE/PB thresholds reasonable for Indian market? (Indian market trades at higher multiples than US — PE < 15 may exclude most quality stocks.)
- [ ] **C2. CANSLIM — Hard gates** — Does the C (current quarterly earnings) and A (annual earnings) gate actually function as hard pass/fail? Or are they soft scores that can be compensated by other criteria?
- [ ] **C3. Coffee Can — 10Y consistency** — Does the system actually have 10 years of data? If only 5Y is available, is the screen silently relaxed?
- [ ] **C4. Multibagger Screen — Circular dependency** — The multibagger screen uses inflection + smart money + catalysts + Beneish. If any sub-module fails, does the screen still produce a score, or does it fail silently and pass fewer stocks?
- [ ] **C5. Screen overlap** — How many stocks pass multiple screens simultaneously? If most stocks that pass "quality" also pass "compounder," the screens aren't adding differentiation.
- [ ] **C6. Market cap bias** — Do screens systematically favor large caps (more data, more stable ratios) over small/mid caps? Is this intentional?

---

## III. SIGNAL QUALITY AUDIT

Are the buy/sell signals actionable and not misleading?

### A. Signal Generation

- [ ] **A1. Enhanced signal scoring range** — What is the actual distribution of scores? If 90% of stocks score between 40-60, the system has poor discrimination.
- [ ] **A2. Buy signal frequency** — On any given day, how many stocks get a BUY signal? If it's >50 out of 500, the system is not selective enough. If it's 0, it's too strict.
- [ ] **A3. Signal stability** — Does the same stock flip between BUY and SELL on consecutive days? High-frequency flipping = unreliable signal.
- [ ] **A4. Regime gating effectiveness** — In CRASH regime, does the system actually suppress buy signals? Or does it still recommend stocks with a "warning"?

### B. Composite Scoring

- [ ] **B1. Weight reasonableness** — Fundamental (40%) + Factor (25%) + Tailwind (20%) + Technical (15%). Is 20% for tailwinds (macro themes) justified? Themes are subjective and slow-moving — do they add signal or noise?
- [ ] **B2. Normalization across components** — Are all component scores on the same 0-100 scale? If fundamental score ranges 30-80 but tailwind ranges 40-60, the fundamental score dominates by range, not by weight.
- [ ] **B3. Grade inflation** — What percentage of stocks get grade A or B? If >50%, the grading is inflated and not useful for differentiation.

### C. Recommendation Engine (Orchestrator)

- [ ] **C1. Diversification across buckets** — Does the deduplication logic actually prevent the same stock from appearing in multiple buckets? What if there's only 1 candidate that passes screens?
- [ ] **C2. Conviction assessment calibration** — Is "HIGH conviction" actually predictive of better outcomes? Without backtesting the conviction levels, this is just a label.
- [ ] **C3. Alternates quality** — Are alternate picks actually good, or just "whatever else passed the screen"? Are they in the same sector (defeating diversification)?

---

## IV. RISK MANAGEMENT AUDIT

Does the system actually protect capital?

### A. Position Sizing

- [ ] **A1. ATR stop-loss calculation** — Is ATR calculated on daily or weekly data? Is the multiplier (2× ATR) appropriate for Indian mid-caps (which can gap 5-10%)?
- [ ] **A2. Position size vs liquidity** — Does the system check that position size < 2% of average daily volume? Is ADV calculated on a sufficient lookback (20 days minimum)?
- [ ] **A3. Portfolio heat limit** — The 6% max total risk — is it enforced in the orchestrator or only advisory?

### B. VaR / CVaR

- [ ] **B1. VaR methodology** — Historical or parametric? Is the lookback period sufficient (min 252 trading days)? Does it account for fat tails (Indian markets have higher kurtosis)?
- [ ] **B2. CVaR (Expected Shortfall)** — Correctly computed as the average of losses beyond VaR? Not just VaR at a different confidence level?
- [ ] **B3. Stress test scenarios** — Are the stress scenarios relevant to India (not just 2008 GFC US data)? Should include: 2020 COVID crash, 2022 rate hike, 2018 NBFC crisis, demonetization.

### C. Correlation & Concentration

- [ ] **C1. Correlation calculation** — Using returns correlation (correct) or price correlation (wrong)? Pearson or rank correlation?
- [ ] **C2. Sector concentration** — If the system recommends MULTIBAGGER=Solar Industries, HEDGE=Eicher, COMPOUNDER=Coal India — that's 3 different sectors. But what if all 3 are from IT?

---

## V. TECHNICAL INDICATOR AUDIT

Are the indicators computed correctly and producing meaningful signals?

### A. Standard Indicators

- [ ] **A1. RSI calculation** — Wilder's smoothing (correct) or simple SMA (incorrect but common)?
- [ ] **A2. MACD** — Correct EMA periods (12, 26, 9)? Signal line is EMA of MACD line (not SMA)?
- [ ] **A3. Bollinger Bands** — Using 20-period SMA and 2 standard deviations? Population vs sample std dev?
- [ ] **A4. EMA calculations** — Correct exponential smoothing factor? Sufficient lookback for initialization?

### B. Advanced Indicators

- [ ] **B1. VCP (Volatility Contraction Pattern)** — Correct implementation of Minervini's criteria? Does it detect genuine contracting bases or just any declining volatility?
- [ ] **B2. TTM Squeeze** — Bollinger Bands inside Keltner Channels correctly detected? Momentum component using linear regression (not just MACD)?
- [ ] **B3. Multi-timeframe alignment** — How are daily and weekly signals combined? Is there a lookback mismatch (daily signal from today vs weekly signal from last Friday)?

### C. Market Regime Detection

- [ ] **C1. Regime classification thresholds** — Are the score ranges (STRONG_BULL ≥ 5, BULL ≥ 2, etc.) calibrated against historical Indian market data? Or arbitrary?
- [ ] **C2. VIX thresholds** — India VIX > 20 = reduce size. Is this threshold valid? India VIX averages ~14-16; 20 is already elevated but not crash territory.
- [ ] **C3. Regime lag** — How quickly does the system detect a regime change? If it takes 5 days of data, you've already missed the crash.

---

## VI. INVESTOR SAFETY AUDIT

Would a retail investor using this system be harmed?

### A. Survivorship Bias

- [ ] **A1. Universe composition** — The Nifty 500 is rebalanced periodically. Stocks that dropped out (due to poor performance) are not in the current list. Historical screens on the current universe are biased.
- [ ] **A2. Screen backtesting validity** — If we say "Coffee Can screen picks outperform," that's only valid if tested on the universe as it existed at each historical point, not today's universe.

### B. Overconfidence Signals

- [ ] **B1. Precision theater** — Fair value shown as "₹2,419.37" implies precision to the rupee. The real confidence interval is probably ±30%. Are confidence intervals shown?
- [ ] **B2. Model count as conviction** — "4/4 valuation models say UNDERVALUED" sounds strong. But all 4 models use the same FCF input — they're correlated, not independent. Is this disclosed?
- [ ] **B3. Inflection detection false positive rate** — How often does "CONFIRMED_INFLECTION" actually lead to sustained growth? Without backtesting, this is pattern-matching on noise.

### C. Harmful Recommendations

- [ ] **C1. Loss-making companies** — Can the system recommend a stock with negative earnings, negative FCF, and no dividend? If so, under what screens?
- [ ] **C2. Penny stock / micro-cap risk** — Minimum market cap filters — are they enforced universally? Nifty 500 floor is ~₹2,000 Cr, but after rebalancing, some may be smaller.
- [ ] **C3. Liquidity trap** — Small-cap stocks with low volume. Can the system recommend a stock where you can't exit within a day?
- [ ] **C4. Sector rotation timing** — RRG quadrants tell you where sectors ARE, not where they're going. "Leading" sector can reverse next week. Is this nuance conveyed?

### D. Disclaimer & Transparency

- [ ] **D1. Is it clear this is not investment advice?** — Every output should carry a disclaimer.
- [ ] **D2. Are model limitations documented?** — DCF sensitivity to growth assumption, Beneish data gaps, etc.
- [ ] **D3. Data source attribution** — screener.in, yfinance, Google News RSS — are these attributed?

---

## VII. CODE QUALITY & RELIABILITY AUDIT

### A. Error Handling

- [ ] **A1. Graceful degradation** — If screener.in is down, does the system crash or use cached data? If one module fails (e.g., catalyst scanner), does it poison the entire recommendation?
- [ ] **A2. Exception swallowing** — Are there bare `except: pass` blocks that silently hide errors? Critical in financial code — a hidden divide-by-zero can produce a garbage fair value.
- [ ] **A3. Division by zero** — FCF/shares, WACC-terminal_growth, PE calculation — every division needs a guard. Are all guarded consistently?

### B. Consistency Across Modules

- [ ] **B1. Row lookup pattern** — Multiple modules have their own `_find_row()` / `_extract_latest_row()`. Do they all handle the `+` suffix? Do they all use the same matching logic (exact vs partial vs contains)?
- [ ] **B2. Shares outstanding calculation** — Used in DCF, DDM, Monte Carlo, and scorer. Is it computed the same way everywhere (market_cap × 1e7 / current_price)?
- [ ] **B3. Net debt calculation** — Used in DCF, Monte Carlo, and possibly others. Same formula everywhere?
- [ ] **B4. Growth rate interpretation** — Some places store growth as percentage (15.0 means 15%), others as decimal (0.15 means 15%). Is this consistent?

### C. Performance & Scalability

- [ ] **C1. Nifty 500 full scan time** — How long does a full recommend command take for 520 stocks? Is it under 10 minutes?
- [ ] **C2. Rate limiting** — screener.in will block aggressive scraping. Is the rate limit (2s + jitter) sufficient? Has it been tested with 520 sequential requests?
- [ ] **C3. Memory usage** — Loading 520 stocks with full financial data. Any OOM risk?

### D. Testing

- [ ] **D1. Unit test coverage** — Are there any tests at all? For financial calculations, even basic sanity tests (known input → expected output) would catch regressions.
- [ ] **D2. Known-answer tests** — For Piotroski, Altman, Beneish: test against published examples from the original papers.
- [ ] **D3. Regression tests** — If a code change breaks the DCF model, is there a test that catches it before production?

---

## VIII. ADDITIONAL AUDIT DIMENSIONS

### A. Catalyst / News Analysis

- [ ] **A1. News source reliability** — Google News RSS is a meta-aggregator. Are duplicates filtered? Can a single event (e.g., an order win) be counted multiple times from different sources?
- [ ] **A2. Keyword classification accuracy** — Does keyword matching correctly categorize news? "Solar Industries share price TARGET CUT" matched as `TURNAROUND` is misleading — it's actually negative news.
- [ ] **A3. News staleness** — How old can a news article be and still count as a "catalyst"? A 30-day-old article is not a current catalyst.

### B. Smart Money Tracking

- [ ] **B1. Shareholding data lag** — SEBI mandates quarterly disclosure. Data can be 0-90 days old. Is the "velocity" calculation (change per quarter) meaningful given this lag?
- [ ] **B2. Promoter holding interpretation** — Promoter selling is not always negative (tax planning, diversification, OFS). Does the system distinguish between bulk deals and gradual reduction?

### C. Theme / Supply Chain Mapping

- [ ] **C1. Theme beneficiary accuracy** — Are the hardcoded stock-to-theme mappings correct and current? If Solar Industries is mapped to "defence" theme, is that still their primary revenue driver?
- [ ] **C2. Theme lifecycle staleness** — Theme stages (NASCENT → ACCELERATING → CONSENSUS → CROWDED → FADING) — how are these updated? Manually or automatically?

### D. Backtesting Validity

- [ ] **D1. Look-ahead bias** — Do any backtests use future data? (e.g., using today's sector classification to backtest 2020 picks)
- [ ] **D2. Transaction costs** — Are brokerage, STT, stamp duty, GST included in backtest returns? Indian transaction costs are ~0.1-0.3% per trade.
- [ ] **D3. Slippage** — Are backtests using close price? Real execution may be 0.2-0.5% worse. Especially for small caps.

---

## AUDIT EXECUTION PLAN

We will check each item above against the actual code. Priority order:

1. **Data Integrity (I)** — Foundation. Do first.
2. **Financial Model Correctness (II)** — Core value proposition.
3. **Investor Safety (VI)** — Harm prevention.
4. **Risk Management (IV)** — Capital protection.
5. **Signal Quality (III)** — Output quality.
6. **Technical Indicators (V)** — Input quality.
7. **Code Quality (VII)** — Reliability.
8. **Additional Dimensions (VIII)** — Edge cases.

Total items: **~85 checkpoints**

---

*This audit checklist was prepared based on the system's architecture, CLI commands, module inventory, and documented improvement plan — without reading implementation code. Each item will be verified against the codebase in the next phase.*
