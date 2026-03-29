# AUDIT REPORT — Nifty Signals

**Auditor:** Codex (independent)
**Date:** 2026-03-29
**Codebase reviewed:** All Python files in nifty-signals/

**Note:** `AUDIT.md` currently contains 98 explicit checklist items across 8 sections, not 85. The totals below reflect the 98 checklist items actually present in that file.

---

## Section I: Data Integrity

### A1. Screener.in scraping correctness
**Verdict:** FAIL
**Evidence:** `fundamentals/screener_fetcher.py:307-324` parses `High / Low`, sector, and industry with brittle text/anchor lookups; local cache audit of `.cache/fundamental_cache.db` found `high_52w=0` and `low_52w=0` for all 521 cached rows.
**Impact:** Top-ratio fields are being scraped unreliably, so downstream models run with missing market context.

### A2. Symbol mapping completeness
**Verdict:** WARN
**Evidence:** `config.py:176-201` defines only 22 explicit screener symbol remaps for a 520-name Nifty 500 list; `fundamentals/screener_fetcher.py:138-145` only learns about bad symbols after a live 404 and has no pre-validation pass.
**Impact:** Unmapped or renamed companies can silently fall out of coverage until runtime.

### A3. yfinance data alignment
**Verdict:** WARN
**Evidence:** `data/fetcher.py:57-85` fetches Yahoo Finance data and returns it directly; there is no tolerance check against screener price, no stale-data detection, and no cross-source reconciliation.
**Impact:** Technical signals can run on stale or mismatched price data without raising a quality flag.

### A4. Data freshness
**Verdict:** FAIL
**Evidence:** `fundamentals/cache.py:12-14` and `config.py:168-173` set a 168-hour cache TTL for all fundamental fields; cache stats show raw rows spanning `2026-03-24` to `2026-03-29`.
**Impact:** Quarterly statements can tolerate this, but `current_price`, `market_cap`, and 52-week range fields can be materially stale.

### A5. Consolidated vs standalone
**Verdict:** WARN
**Evidence:** `config.py:169-170` defaults to the consolidated URL; `fundamentals/screener_fetcher.py:133-145` falls back to standalone only after a 404.
**Impact:** The system has no issuer-specific accounting policy for cases where standalone statements are the economically correct choice.

### B1. Missing fields don't silently become zero
**Verdict:** FAIL
**Evidence:** `fundamentals/models.py:17-27` and `fundamentals/models.py:71-150` default most numeric fields to `0.0`; `fundamentals/screener_fetcher.py:183-194` and `fundamentals/scorer.py:47-58` repeatedly use `.get(..., 0)`.
**Impact:** Missing data is collapsed into real zero values, which corrupts valuation, quality, and screen logic.

### B2. Negative values handled correctly
**Verdict:** WARN
**Evidence:** `fundamentals/scorer.py:43-45` sets earnings yield to `0` whenever PE is non-positive; `fundamentals/screens/value.py:30-57` and `fundamentals/screens/garp.py:70-92` mostly reject bad values but do not distinguish loss-making from unavailable cleanly.
**Impact:** Some negative fundamentals are filtered, but others are flattened into neutral zeros rather than being explicitly treated as distress.

### B3. Banking/NBFC financial statement structure
**Verdict:** FAIL
**Evidence:** `fundamentals/scorer.py:152-257` still derives price/sales, margins, current ratio, and cash-flow health from industrial-company line items; only selected modules skip banks, such as `fundamentals/scores/altman.py:68-72` and `fundamentals/valuation/dcf.py:194-197`.
**Impact:** Banking and NBFC names can receive distorted metrics in modules that still assume manufacturing-style statements.

### B4. New listing / IPO stocks
**Verdict:** WARN
**Evidence:** `fundamentals/scorer.py:368-405` requires at least five quarterly values for YoY checks; `fundamentals/inflection.py:238-246` requires eight quarters before it will assess acceleration.
**Impact:** IPOs and short-history listings are not handled explicitly; they are usually under-scored through missing-history fallbacks.

### B5. Demerger/restructuring data continuity
**Verdict:** WARN
**Evidence:** `config.py:183-200` contains a few ticker rename remaps such as `ONE97 -> PAYTM` and `ZOMATO -> ETERNAL`, but there is no historical stitching layer anywhere in `fundamentals/` or `data/`.
**Impact:** Demergers and renamed entities can show broken historical continuity without any warning.

### B6. Currency and unit consistency
**Verdict:** WARN
**Evidence:** `fundamentals/valuation/dcf.py:199-204` and `fundamentals/valuation/monte_carlo.py:176-181` convert market cap from crore via `* 1e7`; `fundamentals/scorer.py:166-171` computes shares in crore units for EPS fallback. There is no centralized unit-normalization contract.
**Impact:** The current math often works, but unit assumptions are spread across modules and are easy to break silently.

### C1. Which fields are actually populated?
**Verdict:** FAIL
**Evidence:** `fundamentals/screener_fetcher.py:307-324` is the only source for 52-week and sector fields; local cache audit found all 521 raw rows had blank sector plus `high_52w=0` and `low_52w=0`. Also, `fundamentals/scorer.py:320-353` never populates `pledge` even though `fundamentals/models.py:127-130` defines `promoter_pledge`.
**Impact:** Several profile fields are effectively dead code, which weakens models that assume they are populated.

### C2. Quarterly data depth
**Verdict:** PASS
**Evidence:** `fundamentals/scorer.py:362-405` and `fundamentals/inflection.py:238-246` guard insufficient-history cases instead of exploding; local cache audit found quarterly depth `min/median/max = 12/12/14`.
**Impact:** In the current cache snapshot, quarterly depth is sufficient for 2-year comparisons and the code degrades safely if depth drops.

### C3. Shareholding data availability
**Verdict:** PASS
**Evidence:** `fundamentals/screener_fetcher.py:214-216` parses shareholding for every fetch; local cache audit found shareholding depth `min/median/max = 4/5/7` across all 521 cached rows.
**Impact:** Shareholding availability is materially present in the current dataset.

---

## Section II: Financial Models

### A1. Piotroski F-Score
**Verdict:** FAIL
**Evidence:** `fundamentals/scores/piotroski.py:61-64` proxies current ratio with `Other Assets / Other Liabilities`; `fundamentals/scores/piotroski.py:126-150` and `fundamentals/scores/piotroski.py:178-197` use `<=` or `>=` thresholds rather than strict improvement in several criteria.
**Impact:** The implementation is not faithful to the original 2000 Piotroski paper, so reported F-Scores are not academically correct.

### A2. Altman Z-Score
**Verdict:** FAIL
**Evidence:** `fundamentals/scores/altman.py:85-107` approximates working capital, retained earnings, EBIT, and liabilities from proxy rows; `fundamentals/scores/altman.py:132-137` chooses the model variant with a simple sector-keyword heuristic.
**Impact:** The Z-Score is only a rough distress heuristic here, not a correct Altman implementation.

### A3. Beneish M-Score
**Verdict:** FAIL
**Evidence:** `fundamentals/scores/beneish.py:20-21` explicitly states missing variables default to neutral values; `fundamentals/scores/beneish.py:211-219` implements that by substituting `1.0` or `0.0`.
**Impact:** Missing data pushes the model toward “clean” rather than “unknown,” which creates false comfort.

### A4. Scoring model boundary conditions
**Verdict:** WARN
**Evidence:** `fundamentals/scores/piotroski.py:126-150` and `fundamentals/scores/piotroski.py:178-197` use non-strict comparisons for multiple “improved” tests; `fundamentals/scores/altman.py:144-150` puts `Z = 2.99` in `GREY`, not `SAFE`.
**Impact:** Threshold handling is not fully standardized across models, so edge cases do not behave consistently.

### B1. DCF — WACC calculation
**Verdict:** WARN
**Evidence:** `fundamentals/valuation/dcf.py:15-22` hardcodes India assumptions; `fundamentals/valuation/dcf.py:100-117` uses `DEFAULT_BETA = 1.0`, `ERP = 6%`, and a simple blended debt/equity formula.
**Impact:** WACC is easy to compute but not company-specific enough for high-confidence valuation work.

### B2. DCF — Growth rate selection
**Verdict:** WARN
**Evidence:** `fundamentals/valuation/dcf.py:159-178` picks the first positive growth metric from profit or revenue CAGR and caps it at 30%.
**Impact:** This is a defensible heuristic, but it can overfit noisy CAGR figures and ignores business-specific reinvestment capacity.

### B3. DCF — Terminal value dominance
**Verdict:** FAIL
**Evidence:** `fundamentals/valuation/dcf.py:255-264` computes terminal value and present value; `fundamentals/valuation/dcf.py:317-318` stores both pieces in details, but no flag is raised when terminal value dominates the enterprise value.
**Impact:** Users can receive fragile DCF outputs that are mostly perpetuity math without being warned.

### B4. DCF — Net debt calculation
**Verdict:** FAIL
**Evidence:** `fundamentals/valuation/dcf.py:269-276` uses `cash equivalents`, then falls back to `investments * 0.3` as a liquidity proxy before computing net debt.
**Impact:** Net debt is not derived from actual cash consistently, so equity value can be materially wrong.

### B5. DDM — Applicability
**Verdict:** PASS
**Evidence:** `fundamentals/valuation/ddm.py:120-132` returns `NOT_APPLICABLE` when current DPS is non-positive.
**Impact:** Non-dividend-paying stocks are correctly excluded from DDM.

### B6. DDM — Dividend growth assumption
**Verdict:** WARN
**Evidence:** `fundamentals/valuation/ddm.py:42-47` computes sustainable growth from ROE and payout, but `fundamentals/valuation/ddm.py:152-170` still picks stage-1 growth from the maximum of profit-growth and sustainable-growth candidates, then floors terminal growth at 4%.
**Impact:** The model is directionally sensible, but stage assumptions can still exceed realistic dividend capacity.

### B7. Peer Relative — Sector benchmarks
**Verdict:** FAIL
**Evidence:** `fundamentals/valuation/peer_relative.py:20-45` hardcodes approximate sector medians and comments that they “should be refreshed periodically.”
**Impact:** Stale benchmark multiples directly distort premium/discount conclusions.

### B8. Peer Relative — Sector classification accuracy
**Verdict:** FAIL
**Evidence:** `fundamentals/valuation/peer_relative.py:57-68` uses fuzzy string matching; local cache audit found the raw sector field blank in all 521 cached rows.
**Impact:** If sector tagging is missing or fuzzy, peer-relative valuation can fall back to the wrong benchmark or the generic default.

### B9. Monte Carlo — Parameter distributions
**Verdict:** WARN
**Evidence:** `fundamentals/valuation/monte_carlo.py:22-29` defines fixed WACC and terminal-growth ranges; `fundamentals/valuation/monte_carlo.py:123-133` samples normal growth and uniform WACC/terminal growth, then clips them.
**Impact:** The simulation is reproducible, but it is not calibrated to issuer-specific risk distributions.

### B10. Monte Carlo — Extreme values
**Verdict:** PASS
**Evidence:** `fundamentals/valuation/monte_carlo.py:130-133` forces `WACC > terminal growth`; `fundamentals/valuation/monte_carlo.py:154-157` floors negative equity-based fair values at zero.
**Impact:** Infinite and negative fair values are clamped before they leak to the user.

### B11. Cross-model consistency
**Verdict:** WARN
**Evidence:** `main.py:2069-2098` and `main.py:2461-2481` display model outputs side by side, but there is no cross-model sanity check or disagreement flag anywhere in `fundamentals/valuation/`.
**Impact:** Large valuation disagreements are shown without interpretation, which can make bad model outputs look equally credible.

### C1. Value Screen (Graham/Buffett)
**Verdict:** WARN
**Evidence:** `fundamentals/screens/value.py:30-57` scores best at `PE <= 15` and `PB <= 2.0`; `fundamentals/screens/value.py:114-121` hard-passes only up to `PE <= 20`.
**Impact:** Thresholds are unusually strict for India and risk excluding many genuinely high-quality Indian compounders.

### C2. CANSLIM — Hard gates
**Verdict:** PASS
**Evidence:** `fundamentals/screens/canslim.py:144-145` explicitly sets `passes = c_pass and a_pass`.
**Impact:** The `C` and `A` criteria are implemented as real gates, not soft offsets.

### C3. Coffee Can — 10Y consistency
**Verdict:** FAIL
**Evidence:** `fundamentals/screens/coffee_can.py:36-39` explicitly says only 5-year data is available and uses a tighter current-ROCE proxy for 10-year consistency.
**Impact:** The screen is marketed as Coffee Can but is structurally a 5-year proxy, not a 10-year implementation.

### C4. Multibagger Screen — Circular dependency
**Verdict:** FAIL
**Evidence:** `fundamentals/screens/multibagger.py:181-197`, `fundamentals/screens/multibagger.py:215-234`, `fundamentals/screens/multibagger.py:367-379`, and `fundamentals/screens/multibagger.py:486-514` all swallow sub-module failures and continue scoring.
**Impact:** Hidden module failures silently change multibagger scores without telling the user what evidence is missing.

### C5. Screen overlap
**Verdict:** WARN
**Evidence:** Local cache audit across 521 cached profiles found `quality`/`compounder` overlap of 69 stocks and `quality`/`coffee_can` overlap of 36; the relevant rules live in `fundamentals/screens/quality.py:31-119`, `fundamentals/screens/compounder.py`, and `fundamentals/screens/coffee_can.py:36-145`.
**Impact:** Several screens are not orthogonal, so the system offers less strategic differentiation than the labels imply.

### C6. Market cap bias
**Verdict:** WARN
**Evidence:** `fundamentals/screens/value.py:83-95`, `fundamentals/screens/canslim.py:89-98`, and `fundamentals/screens/coffee_can.py:83-95` all add explicit market-cap floors; local cache audit found the passing median market cap was ₹39,220.5 Cr for `growth` and ₹38,201 Cr for `canslim` versus ₹20,183 Cr for the full universe.
**Impact:** The screens systematically lean toward larger names, whether intended or not.

---

## Section III: Signal Quality

### A1. Enhanced signal scoring range
**Verdict:** WARN
**Evidence:** `signals/enhanced_generator.py:194-218` builds the score as a raw sum of heterogeneous indicator subscores; a local run over 106 cached Nifty-100 symbols produced `min/median/max = -16/-8/18`, with 92 of 106 scores below zero.
**Impact:** The score is not on a normalized 0-100 scale and is heavily skewed bearish in the current implementation.

### A2. Buy signal frequency
**Verdict:** PASS
**Evidence:** `signals/scorer.py:88-97` and `signals/enhanced_generator.py:439-459` define the buy thresholds; a local run over 106 cached symbols produced 5 actionable `BUY/STRONG_BUY` recommendations.
**Impact:** In the cached sample, the system is selective rather than indiscriminately bullish.

### A3. Signal stability
**Verdict:** FAIL
**Evidence:** `signals/enhanced_generator.py:194-218` re-sums many fast-moving technical components each bar; a one-bar rollback probe on 20 cached symbols changed the final recommendation for 13 of them, including flips such as `ABB: SELL -> STRONG_BUY` and `ADANIENSOL: STRONG_SELL -> STRONG_BUY`.
**Impact:** Recommendations are highly unstable and can flip on a single new bar.

### A4. Regime gating effectiveness
**Verdict:** WARN
**Evidence:** `main.py:283-285` stops `enhanced-scan` entirely when market regime says stay in cash, but `signals/enhanced_generator.py:259` still assigns a raw `signal_type` from score and `signals/enhanced_generator.py:423-441` only downgrades the final recommendation to `SKIP`.
**Impact:** Regime suppression is only partially consistent across commands and data structures.

### B1. Weight reasonableness
**Verdict:** WARN
**Evidence:** `config.py:281-285` uses `internal=50%`, `external=30%`, `valuation=20%`; `tailwinds/analyzer.py:515-560` implements those weights exactly.
**Impact:** The deployed weights differ materially from the audit checklist’s assumed split and are not backed by calibration evidence.

### B2. Normalization across components
**Verdict:** PASS
**Evidence:** `tailwinds/analyzer.py:525-527` normalizes the non-valuation fundamental score from `0-80` to `0-100`; `tailwinds/analyzer.py:555-560` converts the valuation component to `0-100` before weighting.
**Impact:** The tailwind composite itself is normalized sensibly before mixing components.

### B3. Grade inflation
**Verdict:** PASS
**Evidence:** `fundamentals/scorer.py:575-585` computes total score and grade; a local cache audit over 521 names produced only 70 `A/A+/B` grades total (`13.4%`).
**Impact:** The fundamental grading layer is not obviously inflated in the current cache sample.

### C1. Diversification across buckets
**Verdict:** FAIL
**Evidence:** `core/investment_orchestrator.py:647-656` deduplicates picks only by first-seen symbol; there is no sector diversification logic and no fallback to “best fit” scoring by bucket.
**Impact:** Final picks can still be concentrated by sector or chosen by bucket ordering rather than portfolio construction quality.

### C2. Conviction assessment calibration
**Verdict:** FAIL
**Evidence:** `core/investment_orchestrator.py:548-589` defines conviction entirely as a hand-built point system; no backtest or calibration layer exists anywhere in `backtest/`.
**Impact:** `HIGH` conviction is a label, not a validated edge estimate.

### C3. Alternates quality
**Verdict:** FAIL
**Evidence:** `core/investment_orchestrator.py:660-664` uses `or` in the alternate filter, which allows symbols already used in other buckets to leak into alternates.
**Impact:** Alternates are not reliably “next best diversified options”; they can repeat already-used names and defeat bucket separation.

---

## Section IV: Risk Management

### A1. ATR stop-loss calculation
**Verdict:** WARN
**Evidence:** `risk/position_sizing.py:61-64` calculates ATR from the passed-in price frame; `signals/enhanced_generator.py:230-233` always passes daily data, and `risk/position_sizing.py:111-118` uses fixed VIX-based multipliers.
**Impact:** The stop framework is coherent, but the multiplier policy is heuristic and not calibrated for Indian mid-cap gap risk.

### A2. Position size vs liquidity
**Verdict:** FAIL
**Evidence:** `config.py:117-120` defines `min_liquidity_cr` and `max_adv_pct`, but `risk/position_sizing.py:236-293` never references volume or ADV when sizing positions.
**Impact:** The system can size trades into names that are too illiquid to enter or exit safely.

### A3. Portfolio heat limit
**Verdict:** FAIL
**Evidence:** `risk/position_sizing.py:489-540` enforces heat only inside `can_take_trade`; `signals/enhanced_generator.py:237-244` checks that method but nowhere calls `PortfolioRiskManager.add_position`, and `rg` found only the method definitions.
**Impact:** Portfolio heat is advisory, not statefully enforced across sequential recommendations.

### B1. VaR methodology
**Verdict:** FAIL
**Evidence:** `risk/portfolio_risk.py:143-145` and `risk/portfolio_risk.py:203-204` allow VaR with only 30 observations; `risk/portfolio_risk.py:217-231` always computes portfolio VaR parametrically even when config says `historical`.
**Impact:** Reported VaR is methodologically inconsistent and too short-windowed for Indian equity tail risk.

### B2. CVaR (Expected Shortfall)
**Verdict:** PASS
**Evidence:** `risk/portfolio_risk.py:174-177` computes CVaR as the mean of returns beyond the VaR threshold.
**Impact:** Expected shortfall is implemented in the standard way.

### B3. Stress test scenarios
**Verdict:** WARN
**Evidence:** `risk/portfolio_risk.py:81-117` includes `covid_2020`, `rate_hike_2022`, and `il_fs_2018`, but no demonetization or other India-specific policy shock scenario.
**Impact:** Stress coverage is directionally useful but incomplete for India-specific macro shocks.

### C1. Correlation calculation
**Verdict:** PASS
**Evidence:** `risk/portfolio_risk.py:246-271` computes Pearson correlation on aligned return series, not on raw prices.
**Impact:** The correlation math is materially correct.

### C2. Sector concentration
**Verdict:** FAIL
**Evidence:** `risk/position_sizing.py:512-528` can warn on sector concentration only if positions are already tracked; `core/investment_orchestrator.py:645-670` never uses sector caps when constructing bucket picks.
**Impact:** Concentration risk is not enforced in the main recommendation flow.

---

## Section V: Technical Indicators

### A1. RSI calculation
**Verdict:** PASS
**Evidence:** `indicators/technical.py:40-41` uses `pandas_ta.rsi`, which implements Wilder-style smoothing by default.
**Impact:** No material defect found in the RSI implementation.

### A2. MACD
**Verdict:** PASS
**Evidence:** `indicators/technical.py:44-47` uses standard `12/26/9` MACD parameters and the EMA-based signal line from `pandas_ta.macd`.
**Impact:** No material defect found in the MACD implementation.

### A3. Bollinger Bands
**Verdict:** WARN
**Evidence:** `indicators/technical.py:55-64` delegates to `pandas_ta.bbands` without an explicit standard-deviation convention; `indicators/ttm_squeeze.py:74-77` uses Pandas rolling standard deviation directly.
**Impact:** The implementation is conventional, but the std-dev convention is implicit rather than pinned.

### A4. EMA calculations
**Verdict:** PASS
**Evidence:** `indicators/technical.py:49-52` uses `pandas_ta.ema`; `indicators/multi_timeframe.py:41-43` does the same for 10/20/50 EMA structure.
**Impact:** EMA calculations use standard library implementations rather than custom code.

### B1. VCP (Volatility Contraction Pattern)
**Verdict:** FAIL
**Evidence:** `indicators/vcp.py:101-143` and `indicators/vcp.py:206-239` implement a heuristic contraction detector plus score, but there is no check for classic Minervini preconditions such as prior uptrend structure, base geometry, or true pivot quality beyond simple proximity.
**Impact:** The module detects “declining volatility” patterns, not a rigorously defined Minervini VCP.

### B2. TTM Squeeze
**Verdict:** PASS
**Evidence:** `indicators/ttm_squeeze.py:73-89` correctly defines squeeze-on as Bollinger Bands inside Keltner Channels; `indicators/ttm_squeeze.py:91-111` uses linear regression momentum rather than a MACD shortcut.
**Impact:** The TTM Squeeze implementation matches the intended indicator logic reasonably well.

### B3. Multi-timeframe alignment
**Verdict:** WARN
**Evidence:** `indicators/multi_timeframe.py:189-264` combines the latest daily bar with the latest available weekly bar, but it does not explicitly synchronize “today’s” daily bar against a completed weekly candle.
**Impact:** End-of-week and mid-week alignment can be off by one unfinished weekly bar.

### C1. Regime classification thresholds
**Verdict:** FAIL
**Evidence:** `indicators/market_regime.py:240-255` maps the combined score into regimes with fixed cutoffs like `>=5`, `>=2`, and `>=-1`; no calibration dataset or fit process exists anywhere in the repo.
**Impact:** Regime labels are heuristic and unvalidated rather than statistically grounded.

### C2. VIX thresholds
**Verdict:** WARN
**Evidence:** `indicators/market_regime.py:150-164` buckets VIX as `<12`, `<15`, `<20`, `<25`, and `>=25`; `risk/position_sizing.py:111-118` separately uses `12/18/25` for ATR multipliers.
**Impact:** Volatility thresholds are hardcoded and inconsistent across modules.

### C3. Regime lag
**Verdict:** WARN
**Evidence:** `indicators/market_regime.py:67-68`, `indicators/market_regime.py:97-113`, and `indicators/market_regime.py:144-145` use 5-day and 22-day momentum plus 20-day VIX averaging.
**Impact:** The detector will necessarily lag sudden market breaks and reversals.

---

## Section VI: Investor Safety

### A1. Universe composition
**Verdict:** FAIL
**Evidence:** `data/fetcher.py:24-28` loads only `nifty_100` for the technical engine; `core/investment_orchestrator.py:160-183` defaults recommendations to `nifty_100`; historical membership is never versioned.
**Impact:** The system is not consistently operating on the claimed Nifty 500 universe, and historical analysis is survivorship-biased.

### A2. Screen backtesting validity
**Verdict:** FAIL
**Evidence:** `config.py:249-267` and `data/fetcher.py:24-28` use present-day universe files; `backtest/walk_forward.py:343-353` and `backtest/engine.py:160-208` have no historical-constituent reconstruction layer.
**Impact:** Any backtest run on today’s universe overstates robustness by excluding names that later dropped out.

### B1. Precision theater
**Verdict:** FAIL
**Evidence:** `fundamentals/valuation/dcf.py:307`, `fundamentals/valuation/ddm.py:210`, `fundamentals/valuation/peer_relative.py:258`, and `fundamentals/valuation/monte_carlo.py:281` emit rupee-level fair values; `main.py:2089-2091` and `main.py:2475-2477` display them without confidence intervals.
**Impact:** The UI implies far more precision than the model inputs justify.

### B2. Model count as conviction
**Verdict:** FAIL
**Evidence:** `core/investment_orchestrator.py:541-545` summarizes valuation support as “`X/Y valuation models say UNDERVALUED`” with no note that the models share the same raw fundamentals.
**Impact:** Correlated models are presented like independent votes, which overstates confidence.

### B3. Inflection detection false positive rate
**Verdict:** FAIL
**Evidence:** `fundamentals/inflection.py:174-221` classifies stages purely from heuristic signal counts and weights; there is no backtest or false-positive measurement for `CONFIRMED_INFLECTION`.
**Impact:** The label looks predictive but is not empirically validated.

### C1. Loss-making companies
**Verdict:** WARN
**Evidence:** Most fundamental screens block weak profitability, e.g. `fundamentals/screens/value.py:76-82` and `fundamentals/screens/growth.py:93-112`, but `signals/enhanced_generator.py:194-307` can still issue technical buy recommendations with no earnings or FCF gate.
**Impact:** Depending on the command used, users can still receive bullish signals on financially weak companies.

### C2. Penny stock / micro-cap risk
**Verdict:** WARN
**Evidence:** Some screens enforce floors, such as `fundamentals/screens/value.py:83-95` and `fundamentals/screens/multibagger.py:158-160`, but the system has no universal market-cap gate across all commands.
**Impact:** Micro-cap protections are partial and path-dependent.

### C3. Liquidity trap
**Verdict:** FAIL
**Evidence:** `risk/position_sizing.py:236-293` sizes trades without any volume or ADV check despite liquidity rules in `config.py:117-120`.
**Impact:** The system can recommend trades that are difficult to exit in real size.

### C4. Sector rotation timing
**Verdict:** WARN
**Evidence:** `signals/enhanced_generator.py:360-405` turns sector rank/strength directly into score bonuses, but there is no user-facing caveat that these are current-state heuristics rather than forward forecasts.
**Impact:** Users may over-read sector strength outputs as predictive timing tools.

### D1. Is it clear this is not investment advice?
**Verdict:** FAIL
**Evidence:** `main.py:2653-2655` prints a disclaimer only in `recommend`; `main.py:2049-2098`, `main.py:2405-2545`, and `main.py:255-320` emit substantive outputs without any disclaimer.
**Impact:** Many user-facing commands present investment conclusions without the required safety framing.

### D2. Are model limitations documented?
**Verdict:** WARN
**Evidence:** Valuation models attach assumption lists, e.g. `fundamentals/valuation/dcf.py:324` and `fundamentals/valuation/ddm.py:223`, but `main.py:2061-2098` and `main.py:2455-2481` do not surface those limitations in the main UI.
**Impact:** Limitations exist in code but are not consistently delivered to the user.

### D3. Data source attribution
**Verdict:** FAIL
**Evidence:** `main.py` output commands print analyses and scores but do not name screener.in, yfinance, or Google News RSS in the rendered results; only code comments and docstrings mention the sources.
**Impact:** Users do not see where the data came from or how trustworthy each input source is.

---

## Section VII: Code Quality & Reliability

### A1. Graceful degradation
**Verdict:** WARN
**Evidence:** `fundamentals/screener_fetcher.py:56-60` uses cached raw data on fetch, and `core/investment_orchestrator.py:202-210` falls back on regime failure, but many deeper modules still swallow exceptions and return partial outputs.
**Impact:** Some graceful degradation exists, but it is inconsistent and can hide degraded recommendation quality.

### A2. Exception swallowing
**Verdict:** FAIL
**Evidence:** `fundamentals/scorer.py:595-628`, `core/investment_orchestrator.py:371-459`, and `fundamentals/screens/multibagger.py:196-197` / `233-234` / `378-379` / `512-514` all contain silent `except` blocks or `pass`.
**Impact:** Financial-model failures can disappear without surfacing to the user or to tests.

### A3. Division by zero
**Verdict:** WARN
**Evidence:** Many modules use guards such as `fundamentals/valuation/dcf.py:25-28`, `fundamentals/valuation/ddm.py:22-25`, and `fundamentals/scores/piotroski.py:68-69`, but there is no centralized invariant or audit that all divisions are protected consistently.
**Impact:** The code is partially hardened, but division safety depends on local discipline rather than a shared framework.

### B1. Row lookup pattern
**Verdict:** FAIL
**Evidence:** `fundamentals/valuation/dcf.py:38-50` and `fundamentals/valuation/monte_carlo.py:45-60` strip trailing `+` from screener labels; `fundamentals/scorer.py:506-513`, `fundamentals/scores/piotroski.py:227-236`, `fundamentals/scores/altman.py:184-193`, and `fundamentals/scores/beneish.py:395-404` do not.
**Impact:** The same screener table row can be found in one module and missed in another.

### B2. Shares outstanding calculation
**Verdict:** PASS
**Evidence:** `fundamentals/valuation/dcf.py:199-204` and `fundamentals/valuation/monte_carlo.py:176-181` both use `market_cap * 1e7 / current_price`; `fundamentals/scorer.py:166-171` computes the equivalent value in crore-share units for EPS fallback.
**Impact:** Share-count math is materially consistent across the current implementations.

### B3. Net debt calculation
**Verdict:** WARN
**Evidence:** `fundamentals/valuation/dcf.py:269-276` and `fundamentals/valuation/monte_carlo.py:205-211` both use borrowings minus a cash proxy, while `fundamentals/scorer.py:175-190` uses a different `Other Assets` fallback in EV/EBITDA.
**Impact:** Net-debt and EV math are not defined in one canonical place, so module drift is likely.

### B4. Growth rate interpretation
**Verdict:** WARN
**Evidence:** Profiles store growth as percentages, e.g. `fundamentals/models.py:95-100`; DCF converts with `/100` in `fundamentals/valuation/dcf.py:170-175`, while DDM defensively accepts either percent or decimal in `fundamentals/valuation/ddm.py:42-47`.
**Impact:** The codebase is aware of mixed conventions, which means mixed conventions are a live risk.

### C1. Nifty 500 full scan time
**Verdict:** FAIL
**Evidence:** `config.py:171` sets a 2-second screener delay; `fundamentals/screener_fetcher.py:113-119` enforces it per request. A fresh 520-stock run is therefore >17 minutes before retries or parsing overhead.
**Impact:** A full fresh Nifty 500 scan cannot realistically meet a sub-10-minute target.

### C2. Rate limiting
**Verdict:** WARN
**Evidence:** `fundamentals/screener_fetcher.py:113-119` uses `2s ± 0.5s` jitter and `data/catalyst_scanner.py:199` uses 3 seconds for RSS, but there is no evidence of end-to-end soak testing against 520 sequential requests.
**Impact:** The rate limit is thoughtful, but its real-world safety margin is unproven.

### C3. Memory usage
**Verdict:** WARN
**Evidence:** The code relies on SQLite caches (`fundamentals/cache.py`, `.cache/*.db`) and mostly processes one symbol at a time, but there is no benchmark or instrumentation for peak memory during large scans.
**Impact:** There is no immediate OOM smell, but memory behavior is not measured.

### D1. Unit test coverage
**Verdict:** WARN
**Evidence:** `rg --files -g 'test*.py'` found several test scripts, but `rg -n "Piotroski|Altman|Beneish|DCF|Monte Carlo|Valuation" test*.py -S` returned nothing; `test_integration.py:31-177` focuses on integration smoke checks.
**Impact:** Some testing exists, but core financial models are largely uncovered.

### D2. Known-answer tests
**Verdict:** FAIL
**Evidence:** No published-example tests exist for Piotroski, Altman, or Beneish; `rg -n "Piotroski|Altman|Beneish|DCF|Monte Carlo|Valuation" test*.py -S` returned no matches.
**Impact:** Formula regressions can ship without any paper-based benchmark catching them.

### D3. Regression tests
**Verdict:** FAIL
**Evidence:** There is no golden-output or model-regression suite anywhere under the `test*.py` files; the existing tests are mostly integration or fund-related scripts.
**Impact:** Model behavior can drift silently after code changes.

---

## Section VIII: Additional Dimensions

### A1. News source reliability
**Verdict:** WARN
**Evidence:** `data/catalyst_scanner.py:308-330` deduplicates only by exact title string and scans multiple Google News RSS queries for the same company.
**Impact:** The same underlying event can still be counted multiple times if headlines differ slightly across publishers.

### A2. Keyword classification accuracy
**Verdict:** FAIL
**Evidence:** `data/catalyst_scanner.py:27-99` defines keyword buckets; `data/catalyst_scanner.py:178-185` matches them by substring; `data/catalyst_scanner.py:408-414` only discounts negative context instead of reclassifying it.
**Impact:** A negative headline can still be labeled as a positive catalyst type and only receive a smaller score, which is misleading.

### A3. News staleness
**Verdict:** WARN
**Evidence:** `data/catalyst_scanner.py:156-169` still gives 30-day-old articles a non-zero recency weight of `0.1`.
**Impact:** Old news can continue to influence current catalyst scoring.

### B1. Shareholding data lag
**Verdict:** WARN
**Evidence:** `data/smart_money.py:100-131` and `data/smart_money.py:281-304` compute quarterly velocity and acceleration directly from successive holdings snapshots with no disclosure-lag adjustment.
**Impact:** The “smart money” signal can look more timely than the underlying quarterly filing cadence allows.

### B2. Promoter holding interpretation
**Verdict:** WARN
**Evidence:** `data/smart_money.py:195-265` and `data/smart_money.py:337-383` interpret higher promoter holding as accumulation and lower holding as distribution, with no distinction for OFS, tax planning, or pledged-share release mechanics.
**Impact:** Promoter activity is reduced to a simplistic signal that can misread benign events as bearish.

### C1. Theme beneficiary accuracy
**Verdict:** FAIL
**Evidence:** `tailwinds/supply_chain.py:50-56` maps `APOLLOHOSP` into `defense_indigenization` supply chain; `tailwinds/supply_chain.py:73-79` maps `JIO` into `digital_payments` infra even though that is not a listed Nifty 500 trading symbol.
**Impact:** Hardcoded theme mappings are factually shaky enough to contaminate theme-exposure conclusions.

### C2. Theme lifecycle staleness
**Verdict:** WARN
**Evidence:** `tailwinds/theme_momentum.py:441-522` updates lifecycle stages automatically from heuristic price/valuation/flow rules, but there is no validation or review loop.
**Impact:** Lifecycle labels are not manually stale, but they can still drift into arbitrary classifications.

### D1. Look-ahead bias
**Verdict:** FAIL
**Evidence:** `backtest/walk_forward.py:371-399` merges the signal onto the same row and enters/exits at that row’s close.
**Impact:** The walk-forward backtest uses information from the bar it is trading on, which is classic look-ahead bias.

### D2. Transaction costs
**Verdict:** FAIL
**Evidence:** `backtest/engine.py:177-208` and `backtest/walk_forward.py:377-400` compute PnL directly from entry/exit price with no brokerage, taxes, STT, GST, or fees.
**Impact:** Backtest returns are overstated versus Indian real-world execution.

### D3. Slippage
**Verdict:** FAIL
**Evidence:** `backtest/engine.py:247-337` assumes exact fills at stop, target, or close; `backtest/walk_forward.py:377-395` also enters and exits exactly at close.
**Impact:** Simulated execution is materially better than what small/mid-cap trading will actually achieve.

---

## Summary

| Section | PASS | FAIL | WARN | Total |
|---------|------|------|------|-------|
| I. Data Integrity | 2 | 5 | 7 | 14 |
| II. Financial Models | 3 | 9 | 9 | 21 |
| III. Signal Quality | 3 | 4 | 3 | 10 |
| IV. Risk Management | 2 | 4 | 2 | 8 |
| V. Technical Indicators | 4 | 2 | 4 | 10 |
| VI. Investor Safety | 0 | 8 | 4 | 12 |
| VII. Code Quality & Reliability | 1 | 5 | 7 | 13 |
| VIII. Additional Dimensions | 0 | 5 | 5 | 10 |
| **Total** | **15** | **42** | **41** | **98** |

## Critical Findings (FAIL items that cause real harm)

1. Missing screener fields are silently coerced to zero across models, so “unknown” fundamentals are often treated like real zero values.
2. Banking and NBFC names are only partially special-cased; many modules still apply industrial-company ratios to financial firms.
3. Top-ratio scraping is broken enough that all cached names have zero 52-week highs/lows and blank sectors, which poisons downstream logic.
4. Piotroski, Altman, and Beneish are all materially heuristic rather than faithful implementations of the underlying models.
5. DCF fair values are heavily assumption-driven, do not warn on terminal-value dominance, and use proxy cash for net debt.
6. Liquidity limits and portfolio heat are not truly enforced in live recommendation flows.
7. The backtesting stack has look-ahead bias and excludes transaction costs and slippage.
8. The main output surfaces valuation/model conclusions without consistent disclaimers, source attribution, or limitation disclosure.

## High Priority Warnings (WARN items worth fixing)

1. The system does not proactively validate all 520 screener symbol mappings before runtime.
2. A flat 7-day TTL is too stale for fast-moving top-ratio fields even if it is acceptable for quarterly statements.
3. Peer-relative valuation relies on static sector medians and fuzzy sector matching.
4. Composite score weights and market-regime thresholds are heuristic and uncalibrated.
5. Enhanced technical recommendations are highly bar-sensitive and can flip on one new candle.
6. The codebase has partial safeguards for negatives and divide-by-zero, but consistency is still module-specific rather than systemic.
7. There are tests in the repo, but no known-answer or regression suite for the core financial models.
