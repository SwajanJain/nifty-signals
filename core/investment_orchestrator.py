"""
Investment Orchestrator — The Master Brain.

Takes a natural language-style request like "give me one multibagger,
one hedge, and one steady compounder" and orchestrates ALL 21 modules
+ 47 commands into a single unified recommendation with full thesis.

Pipeline:
  1. REGIME  — Market context (bull/bear/crash)
  2. SCREEN  — Filter Nifty 100 through relevant screens per bucket
  3. RANK    — Score + valuation + composite for survivors
  4. DEEP    — Inflection, smart money, catalysts, themes for top picks
  5. THESIS  — Assemble investment thesis per pick
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Result models ────────────────────────────────────────────────────

@dataclass
class StockThesis:
    """Complete investment thesis for a single stock."""

    symbol: str
    company_name: str
    sector: str
    bucket: str  # MULTIBAGGER, HEDGE, COMPOUNDER

    # Price & valuation
    current_price: float = 0.0
    market_cap: float = 0.0  # Cr
    fair_value: float = 0.0
    margin_of_safety: float = 0.0  # %
    valuation_signal: str = ""

    # Scores
    fundamental_score: int = 0
    fundamental_grade: str = ""
    composite_score: int = 0
    composite_grade: str = ""

    # Scoring models
    piotroski: Optional[int] = None
    piotroski_zone: str = ""
    altman_z: Optional[float] = None
    altman_zone: str = ""
    beneish_m: Optional[float] = None
    beneish_flag: bool = False

    # Valuation model results (all 4)
    valuation_models: List[Dict[str, Any]] = field(default_factory=list)

    # Inflection
    inflection_stage: str = ""
    inflection_score: int = 0
    inflection_signals: List[str] = field(default_factory=list)

    # Smart money
    smart_money_signal: str = ""
    smart_money_score: int = 0
    smart_money_convergence: bool = False

    # Catalysts
    catalyst_signal: str = ""
    catalyst_score: int = 0
    catalysts: List[str] = field(default_factory=list)

    # Theme exposure
    theme_exposures: List[str] = field(default_factory=list)

    # Screen matches
    screens_passed: List[str] = field(default_factory=list)

    # Key metrics
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    roe: float = 0.0
    roce: float = 0.0
    debt_to_equity: float = 0.0
    promoter_holding: float = 0.0
    revenue_growth_3y: float = 0.0
    profit_growth_3y: float = 0.0

    # Flags
    green_flags: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)

    # Thesis narrative
    thesis_summary: str = ""
    bull_case: List[str] = field(default_factory=list)
    bear_case: List[str] = field(default_factory=list)
    conviction: str = ""  # HIGH, MEDIUM, LOW


@dataclass
class RecommendationResult:
    """Full orchestrator output with 3 picks + market context."""

    # Market context
    regime: str = ""
    regime_should_trade: bool = True
    regime_position_size: str = ""
    regime_details: Dict[str, Any] = field(default_factory=dict)

    # Picks
    multibagger: Optional[StockThesis] = None
    hedge: Optional[StockThesis] = None
    compounder: Optional[StockThesis] = None

    # Alternates (runner-ups)
    multibagger_alternates: List[str] = field(default_factory=list)
    hedge_alternates: List[str] = field(default_factory=list)
    compounder_alternates: List[str] = field(default_factory=list)

    # Scan stats
    universe_size: int = 0
    stocks_fetched: int = 0
    errors: List[str] = field(default_factory=list)


# ─── Bucket definitions ──────────────────────────────────────────────

# Which screens to use per bucket, and how to rank survivors.
BUCKET_CONFIG = {
    "MULTIBAGGER": {
        "screens": ["multibagger", "growth", "canslim"],
        "description": "High-growth inflection candidates with multi-bagger potential",
        "rank_by": "growth_score",  # from FundamentalScore
        "min_mcap": 500,  # Cr
        "max_mcap": 200000,  # Cr — allow mid-to-large caps
    },
    "HEDGE": {
        "screens": ["coffee_can", "dividend", "quality", "value"],
        "description": "Defensive compounders for capital protection",
        "rank_by": "total_score",
        "min_mcap": 10000,
        "prefer_traits": ["is_debt_free", "dividend_growing", "roce_consistent_above_15"],
    },
    "COMPOUNDER": {
        "screens": ["compounder", "garp", "magic_formula"],
        "description": "Steady quality-at-reasonable-price compounders",
        "rank_by": "composite_score",
        "min_mcap": 5000,
    },
}


# ─── Orchestrator ─────────────────────────────────────────────────────

class InvestmentOrchestrator:
    """Master orchestrator that chains all modules into one recommendation."""

    def __init__(self, universe: str = "nifty_100"):
        self.universe_name = universe

    # ── 1. Load universe ──────────────────────────────────────────────

    def _load_universe(self) -> List[Dict[str, str]]:
        # NOTE: Nifty 100/500 universe has inherent survivorship bias — only
        # currently successful large/mid-caps are included. Historical screening
        # results may not reflect real-time performance since delisted or
        # demoted stocks are excluded from the current constituent list.
        from config import get_nifty500_stocks
        stocks = get_nifty500_stocks()
        if self.universe_name == "nifty_100":
            # Nifty 100 = top ~100 by market cap.  stocks.json nifty_500
            # has them all; we take the first ~120 or use a dedicated list.
            import json
            from config import STOCKS_FILE
            try:
                with open(STOCKS_FILE) as f:
                    data = json.load(f)
                nifty100 = data.get("nifty_100", [])
                if nifty100:
                    return nifty100
            except Exception:
                pass
            # Fallback: take first 100 from nifty_500
            return stocks[:100]
        return stocks

    # ── 2. Market regime ──────────────────────────────────────────────

    def _assess_regime(self) -> Dict[str, Any]:
        """Run regime analysis and return summary dict."""
        try:
            from indicators.market_regime import RegimeDetector
            detector = RegimeDetector()
            result = detector.detect_regime()
            strategy = result.get("strategy", {})
            size_mult = result.get("position_size_multiplier", 0.5)
            return {
                "name": result.get("regime_name", "UNKNOWN"),
                "score": result.get("total_score", 0),
                "should_trade": result.get("should_trade", True),
                "position_size_pct": int(size_mult * 100),
                "rationale": strategy.get("notes", ""),
            }
        except Exception as e:
            logger.warning(f"Regime detection failed: {e}")
            return {
                "name": "UNKNOWN",
                "score": 0,
                "should_trade": True,
                "position_size_pct": 50,
                "rationale": f"Regime unavailable ({e}); defaulting to cautious",
            }

    # ── 3. Fetch + profile + score ────────────────────────────────────

    def _fetch_and_score(
        self, symbols: List[str], force_refresh: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch raw data, build profiles, score fundamentals.

        Returns {symbol: {raw, profile, fs, sector}} for each success.
        """
        from fundamentals.screener_fetcher import ScreenerFetcher
        from fundamentals.scorer import ProfileBuilder, FundamentalScorer

        fetcher = ScreenerFetcher()
        raw_batch = fetcher.fetch_batch(symbols, force_refresh=force_refresh)

        builder = ProfileBuilder()
        scorer = FundamentalScorer()

        results = {}
        for sym, raw in raw_batch.items():
            try:
                profile = builder.build(raw)
                fs = scorer.score(profile, raw=raw)
                results[sym] = {
                    "raw": raw,
                    "profile": profile,
                    "fs": fs,
                    "sector": profile.sector or "",
                }
            except Exception as e:
                logger.warning(f"Score failed for {sym}: {e}")
        return results

    # ── 4. Screen into buckets ────────────────────────────────────────

    def _screen_bucket(
        self,
        bucket_name: str,
        scored_data: Dict[str, Dict[str, Any]],
        stock_sectors: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """Run bucket's screens and return ranked list of candidates."""
        from fundamentals.screens import SCREENS

        config = BUCKET_CONFIG[bucket_name]
        screen_names = config["screens"]
        min_mcap = config.get("min_mcap", 0)
        max_mcap = config.get("max_mcap", float("inf"))

        candidates = []

        for sym, data in scored_data.items():
            profile = data["profile"]
            raw = data["raw"]
            fs = data["fs"]

            # Market cap filter
            if profile.market_cap < min_mcap or profile.market_cap > max_mcap:
                continue

            # Run screens
            passed_screens = []
            best_score = 0
            for sname in screen_names:
                screen_cls = SCREENS.get(sname)
                if not screen_cls:
                    continue
                try:
                    scr = screen_cls()
                    if sname == "multibagger":
                        result = scr.screen(profile, raw)
                    else:
                        result = scr.screen(profile)
                    if result.passes:
                        passed_screens.append(sname)
                        best_score = max(best_score, result.score)
                except Exception:
                    continue

            if not passed_screens:
                continue

            # Prefer traits for HEDGE bucket
            trait_bonus = 0
            prefer = config.get("prefer_traits", [])
            for trait in prefer:
                if getattr(profile, trait, False):
                    trait_bonus += 5

            # Build composite ranking score
            rank_field = config["rank_by"]
            if rank_field == "composite_score":
                rank_score = best_score + fs.total_score + trait_bonus
            elif rank_field == "growth_score":
                rank_score = fs.growth_score * 3 + best_score + trait_bonus
            else:
                rank_score = fs.total_score + trait_bonus

            candidates.append({
                "symbol": sym,
                "profile": profile,
                "raw": raw,
                "fs": fs,
                "sector": stock_sectors.get(sym, profile.sector or ""),
                "passed_screens": passed_screens,
                "screen_score": best_score,
                "rank_score": rank_score,
            })

        candidates.sort(key=lambda c: c["rank_score"], reverse=True)
        return candidates

    # ── 5. Deep analysis for a single pick ────────────────────────────

    def _deep_analyze(
        self,
        candidate: Dict[str, Any],
        bucket_name: str,
    ) -> StockThesis:
        """Run full deep analysis on a single candidate."""
        profile = candidate["profile"]
        raw = candidate["raw"]
        fs = candidate["fs"]

        thesis = StockThesis(
            symbol=profile.symbol,
            company_name=profile.company_name,
            sector=candidate["sector"],
            bucket=bucket_name,
            current_price=profile.current_price,
            market_cap=profile.market_cap,
            fundamental_score=fs.total_score,
            fundamental_grade=fs.grade,
            screens_passed=candidate["passed_screens"],
            pe_ratio=profile.pe_ratio or 0.0,
            pb_ratio=profile.pb_ratio or 0.0,
            roe=profile.roe or 0.0,
            roce=profile.roce or 0.0,
            debt_to_equity=profile.debt_to_equity,
            promoter_holding=profile.promoter_holding,
            revenue_growth_3y=profile.revenue_growth_3y,
            profit_growth_3y=profile.profit_growth_3y,
            green_flags=list(fs.green_flags),
            red_flags=list(fs.red_flags),
            piotroski=fs.piotroski_score,
            piotroski_zone=fs.piotroski_zone,
            altman_z=fs.altman_z_score,
            altman_zone=fs.altman_zone,
            beneish_m=fs.beneish_m_score,
            beneish_flag=fs.beneish_flag,
        )

        # --- Valuation models ---
        for vname, vpath in [
            ("DCF", "fundamentals.valuation.dcf.DCFValuation"),
            ("DDM", "fundamentals.valuation.ddm.DDMValuation"),
            ("Peer", "fundamentals.valuation.peer_relative.PeerRelativeValuation"),
            ("MonteCarlo", "fundamentals.valuation.monte_carlo.MonteCarloValuation"),
        ]:
            try:
                parts = vpath.rsplit(".", 1)
                mod = __import__(parts[0], fromlist=[parts[1]])
                cls = getattr(mod, parts[1])
                vr = cls().value(profile, raw)
                thesis.valuation_models.append({
                    "model": vname,
                    "fair_value": round(vr.fair_value, 2) if vr.fair_value else 0,
                    "margin_of_safety": round(vr.margin_of_safety_pct, 2),
                    "signal": vr.signal,
                    "confidence": vr.confidence,
                })
                # Use DCF as primary fair value
                if vname == "DCF" and vr.fair_value and vr.fair_value > 0:
                    thesis.fair_value = round(vr.fair_value, 2)
                    thesis.margin_of_safety = round(vr.margin_of_safety_pct, 2)
                    thesis.valuation_signal = vr.signal
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Valuation model {vname} failed for {thesis.symbol}: {e}")

        # NOTE: DCF, Monte Carlo, and Graham models share similar inputs
        # (FCF, growth assumptions, discount rates) and are correlated.
        # Counting them as independent "votes" overstates confidence.
        # The margin_of_safety from a single model (DCF preferred) is
        # more reliable than vote-counting across correlated models.

        # If DCF didn't produce a value, try Monte Carlo median
        if thesis.fair_value == 0:
            for vm in thesis.valuation_models:
                if vm["fair_value"] > 0:
                    thesis.fair_value = vm["fair_value"]
                    thesis.margin_of_safety = vm["margin_of_safety"]
                    thesis.valuation_signal = vm["signal"]
                    break

        # --- Composite score (fundamental + tailwind) ---
        try:
            from tailwinds.analyzer import TailwindAnalyzer, CompositeAnalyzer
            tw_analyzer = TailwindAnalyzer()
            tw_score = tw_analyzer.score_stock(profile.symbol, thesis.sector)
            if tw_score:
                composite_analyzer = CompositeAnalyzer()
                composite = composite_analyzer.compute(fs, tw_score, profile)
                thesis.composite_score = composite.composite_score
                thesis.composite_grade = composite.composite_grade
        except Exception:
            thesis.composite_score = fs.total_score
            thesis.composite_grade = fs.grade

        # --- Inflection detection ---
        try:
            from fundamentals.inflection import InflectionDetector
            inf = InflectionDetector().detect(profile, raw)
            thesis.inflection_stage = inf.stage
            thesis.inflection_score = inf.inflection_score
            thesis.inflection_signals = [
                f"{s.signal_type} ({s.strength})" for s in inf.signals
            ]
        except Exception:
            pass

        # --- Smart money ---
        try:
            from data.smart_money import SmartMoneyTracker
            sm = SmartMoneyTracker().analyze(profile, raw)
            thesis.smart_money_signal = sm.signal
            thesis.smart_money_score = sm.composite_score
            thesis.smart_money_convergence = sm.convergence
        except Exception:
            pass

        # --- Catalysts ---
        try:
            from data.catalyst_scanner import CatalystScanner
            cat = CatalystScanner().scan(profile.symbol, profile.company_name)
            thesis.catalyst_signal = cat.signal
            thesis.catalyst_score = cat.catalyst_score
            thesis.catalysts = [
                f"[{c.catalyst_type}] {c.headline[:80]}"
                for c in cat.catalysts[:5]
            ]
        except Exception:
            pass

        # --- Theme exposure ---
        try:
            from tailwinds.supply_chain import SupplyChainMapper
            scm = SupplyChainMapper().map_stock(profile.symbol)
            if scm.theme_count > 0:
                thesis.theme_exposures = [
                    f"{te['theme']} ({te['role']})"
                    for te in scm.theme_exposures
                ]
        except Exception:
            pass

        # --- Build thesis narrative ---
        thesis.bull_case, thesis.bear_case = self._build_bull_bear(thesis)
        thesis.thesis_summary = self._build_summary(thesis)
        thesis.conviction = self._assess_conviction(thesis)

        return thesis

    # ── 6. Thesis helpers ─────────────────────────────────────────────

    def _build_bull_bear(self, t: StockThesis):
        bull = []
        bear = []

        # Bull case
        if t.roce > 15:
            bull.append(f"Strong ROCE at {t.roce:.1f}%")
        if t.revenue_growth_3y > 15:
            bull.append(f"Revenue growing at {t.revenue_growth_3y:.1f}% CAGR (3Y)")
        if t.profit_growth_3y > 20:
            bull.append(f"Profit growing at {t.profit_growth_3y:.1f}% CAGR (3Y)")
        if t.piotroski and t.piotroski >= 7:
            bull.append(f"Piotroski F-Score {t.piotroski}/9 — strong financials")
        if t.margin_of_safety > 20:
            bull.append(f"Undervalued with {t.margin_of_safety:.0f}% margin of safety")
        if t.inflection_stage in ("CONFIRMED_INFLECTION", "EARLY_INFLECTION"):
            bull.append(f"Inflection detected: {t.inflection_stage}")
        if t.smart_money_signal in ("STRONG_ACCUMULATION", "ACCUMULATION"):
            bull.append(f"Smart money: {t.smart_money_signal}")
        if t.catalyst_score > 30:
            bull.append(f"Active catalysts (score {t.catalyst_score})")
        if t.theme_exposures:
            bull.append(f"Theme tailwinds: {', '.join(t.theme_exposures[:2])}")
        for f in t.green_flags[:3]:
            if f not in str(bull):
                bull.append(f)

        # Bear case
        if t.debt_to_equity > 1.0:
            bear.append(f"High debt (D/E: {t.debt_to_equity:.1f})")
        if t.pe_ratio > 40:
            bear.append(f"Expensive valuation (PE: {t.pe_ratio:.1f})")
        if t.margin_of_safety < -20:
            bear.append(f"Overvalued by {abs(t.margin_of_safety):.0f}%")
        if t.beneish_flag:
            bear.append("Beneish M-Score flags potential manipulation")
        if t.promoter_holding < 30:
            bear.append(f"Low promoter holding ({t.promoter_holding:.1f}%)")
        if t.smart_money_signal in ("DISTRIBUTION", "STRONG_DISTRIBUTION"):
            bear.append(f"Smart money distributing")
        for f in t.red_flags[:3]:
            if f not in str(bear):
                bear.append(f)

        return bull[:6], bear[:4]

    def _build_summary(self, t: StockThesis) -> str:
        bucket_desc = {
            "MULTIBAGGER": "multibagger candidate",
            "HEDGE": "defensive hedge",
            "COMPOUNDER": "steady compounder",
        }
        desc = bucket_desc.get(t.bucket, t.bucket.lower())

        parts = [f"{t.company_name} ({t.symbol}) as a {desc}."]

        if t.bucket == "MULTIBAGGER":
            if t.inflection_stage in ("CONFIRMED_INFLECTION", "EARLY_INFLECTION"):
                parts.append(f"Showing {t.inflection_stage.lower().replace('_', ' ')} with {len(t.inflection_signals)} signals.")
            if t.revenue_growth_3y > 15:
                parts.append(f"Revenue CAGR {t.revenue_growth_3y:.0f}% over 3Y.")
        elif t.bucket == "HEDGE":
            if t.roce > 15:
                parts.append(f"Consistent compounder with {t.roce:.0f}% ROCE.")
            if t.debt_to_equity < 0.1:
                parts.append("Debt-free balance sheet.")
        elif t.bucket == "COMPOUNDER":
            parts.append(f"Quality score {t.fundamental_score}/100 ({t.fundamental_grade}).")
            if t.margin_of_safety > 0:
                parts.append(f"Trading at {t.margin_of_safety:.0f}% discount to fair value.")

        val_signals = [vm["signal"] for vm in t.valuation_models if vm["signal"] != "NOT_APPLICABLE"]
        undervalued_count = sum(1 for s in val_signals if s == "UNDERVALUED")
        if undervalued_count >= 2:
            parts.append(f"{undervalued_count}/{len(val_signals)} valuation models say UNDERVALUED.")

        return " ".join(parts)

    def _assess_conviction(self, t: StockThesis) -> str:
        score = 0

        # Fundamental quality
        if t.fundamental_score >= 70:
            score += 3
        elif t.fundamental_score >= 55:
            score += 2
        elif t.fundamental_score >= 40:
            score += 1

        # Piotroski
        if t.piotroski and t.piotroski >= 7:
            score += 2
        elif t.piotroski and t.piotroski >= 5:
            score += 1

        # Valuation
        if t.margin_of_safety > 25:
            score += 2
        elif t.margin_of_safety > 0:
            score += 1

        # Smart money
        if t.smart_money_signal in ("STRONG_ACCUMULATION", "ACCUMULATION"):
            score += 1

        # Catalysts
        if t.catalyst_score > 30:
            score += 1

        # Negatives
        if t.beneish_flag:
            score -= 2
        if t.margin_of_safety < -30:
            score -= 1

        if score >= 7:
            return "HIGH"
        elif score >= 4:
            return "MEDIUM"
        return "LOW"

    # ── MAIN ENTRY POINT ──────────────────────────────────────────────

    def recommend(
        self,
        force_refresh: bool = False,
        progress_callback=None,
    ) -> RecommendationResult:
        """Run the full orchestration pipeline and return picks."""
        from rich.console import Console
        console = Console()

        result = RecommendationResult()

        # --- Step 1: Market Regime ---
        console.print("\n[bold cyan]Step 1/5:[/bold cyan] Assessing market regime...")
        regime = self._assess_regime()
        result.regime = regime["name"]
        result.regime_should_trade = regime["should_trade"]
        result.regime_position_size = f"{regime['position_size_pct']}%"
        result.regime_details = regime

        if regime["name"] == "CRASH":
            console.print(
                "[bold red]CRASH regime detected — 100% cash recommended. "
                "Generating picks for watchlist only.[/bold red]"
            )
            result.errors.append(
                "CRASH regime — picks are for watchlist only, NOT for immediate entry"
            )

        # --- Step 2: Fetch universe ---
        console.print("[bold cyan]Step 2/5:[/bold cyan] Fetching universe data...")
        stocks = self._load_universe()
        result.universe_size = len(stocks)
        symbols = [s["symbol"] for s in stocks]
        stock_sectors = {s["symbol"]: s.get("sector", "") for s in stocks}

        scored_data = self._fetch_and_score(symbols, force_refresh=force_refresh)
        result.stocks_fetched = len(scored_data)

        if len(scored_data) < 10:
            result.errors.append(f"Only fetched {len(scored_data)} stocks — results may be unreliable")

        # --- Step 3: Screen into buckets ---
        console.print("[bold cyan]Step 3/5:[/bold cyan] Screening into investment buckets...")

        bucket_candidates = {}
        for bucket_name in ("MULTIBAGGER", "HEDGE", "COMPOUNDER"):
            candidates = self._screen_bucket(bucket_name, scored_data, stock_sectors)
            bucket_candidates[bucket_name] = candidates
            console.print(
                f"  {bucket_name}: {len(candidates)} candidates"
            )

        # --- Step 4: Deduplicate across buckets ---
        # A stock should only appear in its best-fit bucket.
        # Also enforce sector diversification: avoid all 3 picks from same sector.
        used_symbols = set()
        used_sectors = {}  # sector -> count
        final_picks = {}

        for bucket_name in ("MULTIBAGGER", "HEDGE", "COMPOUNDER"):
            candidates = bucket_candidates[bucket_name]
            for c in candidates:
                sym = c["symbol"]
                sector = c.get("sector", "Unknown")
                if sym not in used_symbols:
                    # Skip if this would be the 3rd pick from the same sector
                    if used_sectors.get(sector, 0) >= 2:
                        continue
                    final_picks[bucket_name] = c
                    used_symbols.add(sym)
                    used_sectors[sector] = used_sectors.get(sector, 0) + 1
                    break

        # Collect alternates (exclude already-used symbols AND the primary pick)
        for bucket_name in ("MULTIBAGGER", "HEDGE", "COMPOUNDER"):
            primary_sym = final_picks.get(bucket_name, {}).get("symbol")
            alts = [
                c["symbol"] for c in bucket_candidates[bucket_name]
                if c["symbol"] not in used_symbols
                and c["symbol"] != primary_sym
            ][:3]
            if bucket_name == "MULTIBAGGER":
                result.multibagger_alternates = alts
            elif bucket_name == "HEDGE":
                result.hedge_alternates = alts
            else:
                result.compounder_alternates = alts

        # --- Step 5: Deep analysis on top picks ---
        console.print("[bold cyan]Step 4/5:[/bold cyan] Running deep analysis on top picks...")

        for bucket_name, candidate in final_picks.items():
            console.print(f"  Analyzing {candidate['symbol']} ({bucket_name})...")
            thesis = self._deep_analyze(candidate, bucket_name)

            if bucket_name == "MULTIBAGGER":
                result.multibagger = thesis
            elif bucket_name == "HEDGE":
                result.hedge = thesis
            else:
                result.compounder = thesis

        console.print("[bold cyan]Step 5/5:[/bold cyan] Building investment thesis...")

        return result
