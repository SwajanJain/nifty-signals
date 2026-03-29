"""Insider / Smart-Money Tracker — Promoter, FII, DII accumulation signals.

Analyses shareholding-pattern data from screener.in (via ScreenerRawData) and
computed FundamentalProfile fields to detect institutional accumulation,
promoter buying/selling, and pledge changes.

Data sources
------------
- FundamentalProfile: promoter_holding, fii_holding, dii_holding,
  promoter_holding_change_1y, fii_holding_change_1y, promoter_pledge
- ScreenerRawData.shareholding: list of dicts with 'label' key
  (e.g. 'Promoters', 'FIIs', 'DIIs', 'Public') and quarter columns
  (e.g. 'Mar 2024', 'Dec 2023') containing percentage values.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fundamentals.models import FundamentalProfile, ScreenerRawData


@dataclass
class InsiderSignal:
    """A single insider/smart-money signal."""

    symbol: str
    signal_type: str
    # "PROMOTER_BUYING", "PROMOTER_SELLING", "FII_ACCUMULATING",
    # "FII_EXITING", "DII_ACCUMULATING", "PLEDGE_INCREASE", "PLEDGE_DECREASE"
    strength: str  # "STRONG", "MODERATE", "WEAK"
    details: Dict[str, Any] = field(default_factory=dict)
    score: int = 0  # -100 to +100


# ── Helpers ──────────────────────────────────────────────────────────────

def _parse_quarter_series(
    shareholding: List[Dict[str, Any]],
    label_keyword: str,
) -> List[float]:
    """Extract chronological quarterly holding percentages for *label_keyword*.

    The shareholding list from screener has rows like:
        {"label": "Promoters", "Mar 2024": 52.3, "Dec 2023": 51.8, ...}

    We locate the row whose 'label' contains *label_keyword* (case-insensitive),
    pull out all quarter columns, and return values **oldest-first**.
    """
    if not shareholding:
        return []

    target_row: Optional[Dict[str, Any]] = None
    keyword_lower = label_keyword.lower()
    for row in shareholding:
        row_label = str(row.get("label", "")).lower()
        if keyword_lower in row_label:
            target_row = row
            break

    if target_row is None:
        return []

    # Collect quarter columns — anything that is not 'label'
    quarters: List[str] = [k for k in target_row if k.lower() != "label"]

    # Best-effort chronological ordering: screener usually lists newest first
    # We reverse so that index 0 = oldest, index -1 = newest
    values: List[float] = []
    for q in reversed(quarters):
        try:
            values.append(float(target_row[q]))
        except (ValueError, TypeError):
            continue

    return values


def _detect_trend(values: List[float], min_quarters: int = 2) -> str:
    """Detect trend direction from a chronological series of percentages.

    Returns one of: "INCREASING", "DECREASING", "FLAT", "INSUFFICIENT".
    """
    if len(values) < min_quarters:
        return "INSUFFICIENT"

    recent = values[-min_quarters:]
    diffs = [recent[i] - recent[i - 1] for i in range(1, len(recent))]

    if all(d > 0 for d in diffs):
        return "INCREASING"
    elif all(d < 0 for d in diffs):
        return "DECREASING"
    else:
        return "FLAT"


def _total_change(values: List[float], quarters: int = 2) -> float:
    """Net change over the last *quarters* data points."""
    if len(values) < quarters:
        return 0.0
    return values[-1] - values[-quarters]


# ── Main class ───────────────────────────────────────────────────────────

class InsiderTracker:
    """Detect insider and institutional accumulation/distribution patterns."""

    def analyze(
        self,
        profile: FundamentalProfile,
        raw: ScreenerRawData,
    ) -> List[InsiderSignal]:
        """Analyse shareholding data and return a list of signals.

        Parameters
        ----------
        profile : Computed fundamental profile (has holding % and 1y changes).
        raw     : Raw screener data (has quarterly shareholding table).

        Returns
        -------
        List[InsiderSignal] — may be empty if data is insufficient.
        """
        signals: List[InsiderSignal] = []
        symbol = profile.symbol

        # ── 1. Promoter signals ──────────────────────────────────────
        promoter_series = _parse_quarter_series(raw.shareholding, "promoter")
        promoter_trend = _detect_trend(promoter_series)
        promoter_change_2q = _total_change(promoter_series, quarters=2)
        promoter_change_4q = _total_change(promoter_series, quarters=4)

        if promoter_trend == "INCREASING" or promoter_change_2q > 0.3:
            strength = "STRONG" if promoter_change_2q > 1.0 else (
                "MODERATE" if promoter_change_2q > 0.5 else "WEAK"
            )
            score = min(100, int(promoter_change_2q * 40))
            signals.append(InsiderSignal(
                symbol=symbol,
                signal_type="PROMOTER_BUYING",
                strength=strength,
                details={
                    "current_holding": profile.promoter_holding,
                    "change_2q": round(promoter_change_2q, 2),
                    "change_1y": profile.promoter_holding_change_1y,
                    "trend": promoter_trend,
                    "quarterly_series": promoter_series[-4:],
                },
                score=score,
            ))
        elif promoter_trend == "DECREASING" or promoter_change_2q < -0.3:
            strength = "STRONG" if promoter_change_2q < -1.0 else (
                "MODERATE" if promoter_change_2q < -0.5 else "WEAK"
            )
            score = max(-100, int(promoter_change_2q * 40))
            signals.append(InsiderSignal(
                symbol=symbol,
                signal_type="PROMOTER_SELLING",
                strength=strength,
                details={
                    "current_holding": profile.promoter_holding,
                    "change_2q": round(promoter_change_2q, 2),
                    "change_1y": profile.promoter_holding_change_1y,
                    "trend": promoter_trend,
                    "quarterly_series": promoter_series[-4:],
                },
                score=score,
            ))

        # ── 2. Promoter pledge ───────────────────────────────────────
        if profile.promoter_pledge > 5.0:
            strength = "STRONG" if profile.promoter_pledge > 20 else (
                "MODERATE" if profile.promoter_pledge > 10 else "WEAK"
            )
            signals.append(InsiderSignal(
                symbol=symbol,
                signal_type="PLEDGE_INCREASE",
                strength=strength,
                details={
                    "pledge_pct": profile.promoter_pledge,
                    "promoter_holding": profile.promoter_holding,
                },
                score=-int(min(100, profile.promoter_pledge * 3)),
            ))
        elif 0 < profile.promoter_pledge <= 2.0:
            signals.append(InsiderSignal(
                symbol=symbol,
                signal_type="PLEDGE_DECREASE",
                strength="WEAK",
                details={
                    "pledge_pct": profile.promoter_pledge,
                    "promoter_holding": profile.promoter_holding,
                },
                score=10,
            ))

        # ── 3. FII signals ──────────────────────────────────────────
        fii_series = _parse_quarter_series(raw.shareholding, "fii")
        fii_trend = _detect_trend(fii_series)
        fii_change_2q = _total_change(fii_series, quarters=2)

        if fii_trend == "INCREASING" or fii_change_2q > 0.5:
            strength = "STRONG" if fii_change_2q > 2.0 else (
                "MODERATE" if fii_change_2q > 1.0 else "WEAK"
            )
            score = min(100, int(fii_change_2q * 30))
            signals.append(InsiderSignal(
                symbol=symbol,
                signal_type="FII_ACCUMULATING",
                strength=strength,
                details={
                    "current_holding": profile.fii_holding,
                    "change_2q": round(fii_change_2q, 2),
                    "change_1y": profile.fii_holding_change_1y,
                    "trend": fii_trend,
                    "quarterly_series": fii_series[-4:],
                },
                score=score,
            ))
        elif fii_trend == "DECREASING" or fii_change_2q < -0.5:
            strength = "STRONG" if fii_change_2q < -2.0 else (
                "MODERATE" if fii_change_2q < -1.0 else "WEAK"
            )
            score = max(-100, int(fii_change_2q * 30))
            signals.append(InsiderSignal(
                symbol=symbol,
                signal_type="FII_EXITING",
                strength=strength,
                details={
                    "current_holding": profile.fii_holding,
                    "change_2q": round(fii_change_2q, 2),
                    "change_1y": profile.fii_holding_change_1y,
                    "trend": fii_trend,
                    "quarterly_series": fii_series[-4:],
                },
                score=score,
            ))

        # ── 4. DII signals ──────────────────────────────────────────
        dii_series = _parse_quarter_series(raw.shareholding, "dii")
        dii_trend = _detect_trend(dii_series)
        dii_change_2q = _total_change(dii_series, quarters=2)

        if dii_trend == "INCREASING" or dii_change_2q > 0.5:
            strength = "STRONG" if dii_change_2q > 2.0 else (
                "MODERATE" if dii_change_2q > 1.0 else "WEAK"
            )
            score = min(80, int(dii_change_2q * 25))
            signals.append(InsiderSignal(
                symbol=symbol,
                signal_type="DII_ACCUMULATING",
                strength=strength,
                details={
                    "current_holding": profile.dii_holding,
                    "change_2q": round(dii_change_2q, 2),
                    "trend": dii_trend,
                    "quarterly_series": dii_series[-4:],
                },
                score=score,
            ))

        return signals

    def get_composite_score(self, signals: List[InsiderSignal]) -> int:
        """Aggregate individual signal scores into a single -100 to +100 score.

        Weights
        -------
        - Promoter buying/selling carries highest weight (smart money, skin in game).
        - Pledge is a strong negative.
        - FII and DII are secondary confirmations.

        The raw sum is clamped to [-100, +100].
        """
        if not signals:
            return 0

        weighted_sum = 0.0
        for sig in signals:
            if sig.signal_type in ("PROMOTER_BUYING", "PROMOTER_SELLING"):
                weighted_sum += sig.score * 1.5
            elif sig.signal_type in ("PLEDGE_INCREASE", "PLEDGE_DECREASE"):
                weighted_sum += sig.score * 1.2
            elif sig.signal_type in ("FII_ACCUMULATING", "FII_EXITING"):
                weighted_sum += sig.score * 1.0
            elif sig.signal_type == "DII_ACCUMULATING":
                weighted_sum += sig.score * 0.8
            else:
                weighted_sum += sig.score

        return max(-100, min(100, int(weighted_sum)))
