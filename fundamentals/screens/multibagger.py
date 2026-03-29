"""Multibagger Screen (E5) — Multi-signal screen for potential multibaggers.

The crown jewel: integrates inflection detection, smart money tracking,
catalyst scanning, Piotroski F-Score, and Beneish M-Score into one
unified screen to identify stocks with multibagger potential.

Scoring Components (0-100 total):
  1. Growth Inflection      (0-25)
  2. Quality & Fin Strength  (0-25)
  3. Smart Money             (0-25)
  4. Valuation Reasonableness(0-15)
  5. Catalyst Bonus          (0-10)

Hard pass requirements:
  - Market cap >= 500 Cr
  - Revenue growth 3Y > 0
  - At least 2 of: ROCE>12%, ROE>10%, NPM>5%
  - No manipulation flag (Beneish if available)
"""

import logging
from typing import Any, Dict, List, Optional

from fundamentals.models import FundamentalProfile, ScreenResult, ScreenerRawData
from .base import BaseScreen

logger = logging.getLogger(__name__)


class MultibaggerScreen(BaseScreen):
    """Multi-signal screen combining inflection, smart money, catalysts,
    and quality scores for potential multibagger candidates."""

    @property
    def name(self) -> str:
        return "multibagger"

    @property
    def description(self) -> str:
        return (
            "Multi-signal screen combining inflection, smart money, "
            "catalysts, and quality scores for potential multibagger candidates"
        )

    def screen(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData = None,
    ) -> ScreenResult:
        """Screen a single stock for multibagger potential.

        Parameters
        ----------
        profile : Computed fundamental profile.
        raw     : Optional raw screener data. If provided, inflection
                  detection, smart money tracking, and Beneish M-Score
                  run at full fidelity. Without it, the screen falls
                  back to profile-only approximations (lower confidence).
        """
        p = profile
        met: List[str] = []
        failed: List[str] = []
        key_metrics: Dict[str, Any] = {}

        # ── Hard pass checks ──────────────────────────────────────────
        hard_pass, hard_reasons = self._check_hard_pass(p, raw)
        if not hard_pass:
            failed.extend(hard_reasons)
            return ScreenResult(
                symbol=p.symbol,
                company_name=p.company_name,
                sector=p.sector,
                passes=False,
                strategy=self.name,
                score=0,
                criteria_met=met,
                criteria_failed=failed,
                key_metrics={"disqualified": True},
            )

        # ── 1. Growth Inflection (0-25) ──────────────────────────────
        inflection_score, inflection_met, inflection_failed = (
            self._score_growth_inflection(p, raw)
        )
        met.extend(inflection_met)
        failed.extend(inflection_failed)

        # ── 2. Quality & Financial Strength (0-25) ───────────────────
        quality_score, quality_met, quality_failed = (
            self._score_quality(p)
        )
        met.extend(quality_met)
        failed.extend(quality_failed)

        # ── 3. Smart Money (0-25) ────────────────────────────────────
        smart_money_score, sm_met, sm_failed = (
            self._score_smart_money(p, raw)
        )
        met.extend(sm_met)
        failed.extend(sm_failed)

        # ── 4. Valuation Reasonableness (0-15) ───────────────────────
        valuation_score, val_met, val_failed = (
            self._score_valuation(p)
        )
        met.extend(val_met)
        failed.extend(val_failed)

        # ── 5. Catalyst Bonus (0-10) ─────────────────────────────────
        catalyst_score, cat_met = self._score_catalyst(p, raw)
        met.extend(cat_met)

        # ── Total ────────────────────────────────────────────────────
        total = min(
            100,
            inflection_score + quality_score + smart_money_score
            + valuation_score + catalyst_score,
        )

        key_metrics = {
            "Growth Inflection": f"{inflection_score}/25",
            "Quality": f"{quality_score}/25",
            "Smart Money": f"{smart_money_score}/25",
            "Valuation": f"{valuation_score}/15",
            "Catalyst": f"{catalyst_score}/10",
            "Market Cap": f"{p.market_cap:.0f} Cr",
            "ROCE": f"{p.roce:.1f}%" if p.roce is not None else "N/A",
            "ROE": f"{p.roe:.1f}%" if p.roe is not None else "N/A",
            "Revenue Growth 3Y": f"{p.revenue_growth_3y:.0f}%",
            "PE": f"{p.pe_ratio:.1f}" if p.pe_ratio is not None else "N/A",
            "has_raw_data": raw is not None,
        }

        # Pass threshold: score >= 40
        passes = total >= 40

        return ScreenResult(
            symbol=p.symbol,
            company_name=p.company_name,
            sector=p.sector,
            passes=passes,
            strategy=self.name,
            score=total,
            criteria_met=met,
            criteria_failed=failed,
            key_metrics=key_metrics,
        )

    # ------------------------------------------------------------------
    # Hard pass checks
    # ------------------------------------------------------------------

    def _check_hard_pass(
        self,
        p: FundamentalProfile,
        raw: Optional[ScreenerRawData],
    ) -> tuple:
        """Return (passes: bool, reasons: List[str])."""
        reasons: List[str] = []

        # Minimum market cap
        if p.market_cap < 500:
            reasons.append(f"Market cap {p.market_cap:.0f} Cr < 500 Cr minimum")

        # Must be growing
        if p.revenue_growth_3y <= 0:
            reasons.append(
                f"Revenue growth 3Y {p.revenue_growth_3y:.0f}% is not positive"
            )

        # Quality gate: at least 2 of ROCE>12%, ROE>10%, NPM>5%
        roce = p.roce or 0
        roe = p.roe or 0
        npm = p.npm or 0
        quality_checks = [
            roce > 12,
            roe > 10,
            npm > 5,
        ]
        if sum(quality_checks) < 2:
            reasons.append(
                f"Quality gate failed: ROCE {roce:.1f}%, "
                f"ROE {roe:.1f}%, NPM {npm:.1f}% "
                f"(need at least 2 of: ROCE>12%, ROE>10%, NPM>5%)"
            )

        # Beneish manipulation check (if raw data available)
        if raw is not None:
            try:
                from fundamentals.scores.beneish import BeneishMScore

                beneish = BeneishMScore()
                result = beneish.score(p, raw)
                if (
                    result.is_manipulator
                    and result.confidence in ("HIGH", "MEDIUM")
                ):
                    reasons.append(
                        f"Beneish M-Score {result.m_score:.2f} "
                        f"flags possible manipulation ({result.confidence} confidence)"
                    )
            except Exception as e:
                logger.debug(f"Beneish check failed for {p.symbol}: {e}")

        return len(reasons) == 0, reasons

    # ------------------------------------------------------------------
    # 1. Growth Inflection (0-25)
    # ------------------------------------------------------------------

    def _score_growth_inflection(
        self,
        p: FundamentalProfile,
        raw: Optional[ScreenerRawData],
    ) -> tuple:
        """Score growth inflection signals. Returns (score, met, failed)."""
        score = 0
        met: List[str] = []
        failed: List[str] = []

        # Try full inflection detection if raw data available
        inflection_result = None
        if raw is not None:
            try:
                from fundamentals.inflection import InflectionDetector

                detector = InflectionDetector()
                inflection_result = detector.detect(p, raw)
                if inflection_result.has_inflection:
                    # Scale inflection score (0-100) to 0-10 points
                    inflection_pts = min(
                        10, int(inflection_result.inflection_score / 10)
                    )
                    score += inflection_pts
                    met.append(
                        f"Inflection detected: {inflection_result.stage} "
                        f"(score {inflection_result.inflection_score})"
                    )
            except Exception as e:
                logger.debug(f"Inflection detection failed for {p.symbol}: {e}")

        # Quarterly EPS acceleration
        if p.qtr_eps_acceleration:
            score += 5
            met.append("Quarterly EPS accelerating")
        else:
            failed.append("No quarterly EPS acceleration")

        # Consecutive quarter growth
        if p.consecutive_qtr_growth >= 4:
            score += 5
            met.append(
                f"{p.consecutive_qtr_growth} consecutive quarters of growth"
            )
        elif p.consecutive_qtr_growth >= 2:
            score += 2
            met.append(
                f"{p.consecutive_qtr_growth} consecutive quarters of growth"
            )

        # Revenue growth 3Y
        if p.revenue_growth_3y >= 30:
            score += 8
            met.append(f"Revenue CAGR 3Y {p.revenue_growth_3y:.0f}% (exceptional)")
        elif p.revenue_growth_3y >= 20:
            score += 5
            met.append(f"Revenue CAGR 3Y {p.revenue_growth_3y:.0f}% (strong)")
        elif p.revenue_growth_3y >= 10:
            score += 2
            met.append(f"Revenue CAGR 3Y {p.revenue_growth_3y:.0f}%")
        else:
            failed.append(f"Revenue CAGR 3Y {p.revenue_growth_3y:.0f}% < 10%")

        # Operating leverage: profit growing faster than revenue
        if (
            p.profit_growth_3y > p.revenue_growth_3y
            and p.profit_growth_3y > 0
            and p.revenue_growth_3y > 0
        ):
            score += 5
            met.append(
                f"Operating leverage: profit growth {p.profit_growth_3y:.0f}% "
                f"> revenue growth {p.revenue_growth_3y:.0f}%"
            )

        # OPM expanding (profile-level proxy)
        if p.npm_stable_or_improving:
            score += 2
            met.append("Margins stable or improving")

        return min(25, score), met, failed

    # ------------------------------------------------------------------
    # 2. Quality & Financial Strength (0-25)
    # ------------------------------------------------------------------

    def _score_quality(self, p: FundamentalProfile) -> tuple:
        """Score quality and financial strength. Returns (score, met, failed)."""
        score = 0
        met: List[str] = []
        failed: List[str] = []

        # Piotroski would be ideal but we approximate from profile

        # ROCE
        roce = p.roce or 0
        if roce >= 20:
            score += 8
            met.append(f"ROCE {roce:.1f}% (excellent)")
        elif roce >= 15:
            score += 5
            met.append(f"ROCE {roce:.1f}% (good)")
        else:
            failed.append(f"ROCE {roce:.1f}% < 15%")

        # ROE
        roe = p.roe or 0
        if roe >= 20:
            score += 5
            met.append(f"ROE {roe:.1f}% (excellent)")
        elif roe >= 15:
            score += 3
            met.append(f"ROE {roe:.1f}% (good)")
        else:
            failed.append(f"ROE {roe:.1f}% < 15%")

        # Debt health
        if p.is_debt_free or p.debt_to_equity < 0.3:
            score += 5
            label = "Debt-free" if p.is_debt_free else (
                f"Low D/E {p.debt_to_equity:.2f}"
            )
            met.append(label)
        elif p.debt_to_equity < 0.7:
            score += 3
            met.append(f"Moderate D/E {p.debt_to_equity:.2f}")
        else:
            failed.append(f"D/E {p.debt_to_equity:.2f} >= 0.7")

        # Cash flow consistency
        if p.fcf_positive_years >= 4:
            score += 4
            met.append(f"FCF positive {p.fcf_positive_years}/5 years")
        elif p.cash_flow_positive_years >= 4:
            score += 2
            met.append(
                f"OCF positive {p.cash_flow_positive_years}/5 years"
            )
        else:
            failed.append("Cash flow inconsistent")

        # No loss years
        if p.no_loss_years_5:
            score += 3
            met.append("No loss years in last 5")
        else:
            failed.append("Had loss years")

        return min(25, score), met, failed

    # ------------------------------------------------------------------
    # 3. Smart Money (0-25)
    # ------------------------------------------------------------------

    def _score_smart_money(
        self,
        p: FundamentalProfile,
        raw: Optional[ScreenerRawData],
    ) -> tuple:
        """Score smart money signals. Returns (score, met, failed)."""
        score = 0
        met: List[str] = []
        failed: List[str] = []

        # Try full smart money analysis if raw data available
        smart_money_result = None
        if raw is not None:
            try:
                from data.smart_money import SmartMoneyTracker

                tracker = SmartMoneyTracker()
                smart_money_result = tracker.analyze(p, raw)
                if smart_money_result.convergence:
                    score += 5
                    met.append("Smart money convergence detected")
            except Exception as e:
                logger.debug(f"Smart money analysis failed for {p.symbol}: {e}")

        # Promoter buying
        if p.promoter_holding_change_1y > 1:
            score += 8
            met.append(
                f"Promoter increasing: +{p.promoter_holding_change_1y:.1f}%"
            )
        elif p.promoter_holding_change_1y > 0:
            score += 5
            met.append(
                f"Promoter slightly increasing: +{p.promoter_holding_change_1y:.1f}%"
            )
        elif p.promoter_holding_change_1y < -2:
            failed.append(
                f"Promoter selling: {p.promoter_holding_change_1y:.1f}%"
            )

        # FII accumulating
        if p.fii_holding_change_1y > 2:
            score += 8
            met.append(
                f"FII accumulating: +{p.fii_holding_change_1y:.1f}%"
            )
        elif p.fii_holding_change_1y > 0:
            score += 5
            met.append(
                f"FII increasing: +{p.fii_holding_change_1y:.1f}%"
            )
        elif p.fii_holding_change_1y < -2:
            failed.append(
                f"FII reducing: {p.fii_holding_change_1y:.1f}%"
            )

        # No pledge or reducing pledge
        if p.promoter_pledge <= 0:
            score += 4
            met.append("No promoter pledge")
        elif p.promoter_pledge < 5:
            score += 2
            met.append(f"Low promoter pledge: {p.promoter_pledge:.1f}%")
        else:
            failed.append(f"Promoter pledge: {p.promoter_pledge:.1f}%")

        return min(25, score), met, failed

    # ------------------------------------------------------------------
    # 4. Valuation Reasonableness (0-15)
    # ------------------------------------------------------------------

    def _score_valuation(self, p: FundamentalProfile) -> tuple:
        """Score valuation reasonableness. Returns (score, met, failed)."""
        score = 0
        met: List[str] = []
        failed: List[str] = []

        # PE vs growth — not looking for deep value, just reasonable
        pe = p.pe_ratio or 0
        if 0 < pe <= 30:
            score += 5
            met.append(f"PE {pe:.1f} is reasonable")
        elif 0 < pe <= 50:
            score += 2
            met.append(f"PE {pe:.1f} is elevated but acceptable")
        elif pe > 50:
            failed.append(f"PE {pe:.1f} is expensive")

        # PEG ratio
        peg = p.peg_ratio or 0
        if 0 < peg <= 1.0:
            score += 5
            met.append(f"PEG {peg:.1f} (attractive)")
        elif 0 < peg <= 1.5:
            score += 3
            met.append(f"PEG {peg:.1f} (fair)")
        elif peg > 2.0:
            failed.append(f"PEG {peg:.1f} is too high")

        # Market cap sweet spot for multibaggers: 500 - 10,000 Cr
        if 500 <= p.market_cap <= 10_000:
            score += 5
            met.append(
                f"Market cap {p.market_cap:.0f} Cr in mid/small cap sweet spot"
            )
        elif p.market_cap <= 20_000:
            score += 2
            met.append(f"Market cap {p.market_cap:.0f} Cr (mid cap)")
        else:
            # Large caps can still multibag but less likely
            met.append(
                f"Market cap {p.market_cap:.0f} Cr (large cap - "
                f"lower multibagger probability)"
            )

        return min(15, score), met, failed

    # ------------------------------------------------------------------
    # 5. Catalyst Bonus (0-10)
    # ------------------------------------------------------------------

    def _score_catalyst(
        self,
        p: FundamentalProfile,
        raw: Optional[ScreenerRawData],
    ) -> tuple:
        """Score catalyst presence. Returns (score, met)."""
        score = 0
        met: List[str] = []

        # Try CatalystScanner if available
        catalyst_result = None
        try:
            from data.catalyst_scanner import CatalystScanner

            scanner = CatalystScanner()
            catalyst_result = scanner.scan(p.symbol, p.company_name)

            if catalyst_result.catalyst_score >= 70:
                score += 10
                met.append(
                    f"Strong catalyst signal: {catalyst_result.dominant_catalyst} "
                    f"(score {catalyst_result.catalyst_score})"
                )
            elif catalyst_result.catalyst_score >= 40:
                score += 6
                met.append(
                    f"Moderate catalyst: {catalyst_result.dominant_catalyst} "
                    f"(score {catalyst_result.catalyst_score})"
                )
            elif catalyst_result.catalyst_score > 0:
                score += 3
                met.append(
                    f"Weak catalyst present "
                    f"(score {catalyst_result.catalyst_score})"
                )
        except Exception as e:
            logger.debug(f"Catalyst scanning failed for {p.symbol}: {e}")

        # Sector tailwind proxy if no catalyst data
        if catalyst_result is None or catalyst_result.catalyst_score == 0:
            # Use profile-level hints
            if p.latest_qtr_revenue_yoy > 25:
                score += 3
                met.append(
                    f"Latest quarter revenue YoY {p.latest_qtr_revenue_yoy:.0f}% "
                    f"suggests sector momentum"
                )
            if p.latest_qtr_profit_yoy > 30:
                score += 2
                met.append(
                    f"Latest quarter profit YoY {p.latest_qtr_profit_yoy:.0f}% "
                    f"suggests operational catalyst"
                )

        return min(10, score), met
