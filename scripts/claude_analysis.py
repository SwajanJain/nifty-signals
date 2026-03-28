#!/usr/bin/env python3
"""
Stage F1: Prepare Data for Claude Code Analysis

Instead of calling Claude API separately, this stage:
1. Collects all artifacts from the pipeline run
2. Outputs a comprehensive summary to stdout
3. Claude Code (the CLI) can then analyze this directly

This leverages the fact that Claude Code is already running a powerful
model (Opus 4.5) and can provide intelligent analysis interactively.

Benefits:
- No separate API costs
- Uses the smartest available model
- Enables interactive follow-up questions
- Simpler architecture (no API key needed)

Outputs:
- claude_context.md (saved for reference)
- Prints summary to stdout for Claude Code to analyze

Usage:
    python claude_analysis.py <run_dir>
    python claude_analysis.py <run_dir> --quiet  # Just save, don't print
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_optional(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return _load_json(path)
    except Exception:
        return None


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def build_context_summary(run_dir: Path) -> str:
    """
    Build a comprehensive context summary for Claude Code analysis.
    """
    # Load all artifacts
    data_health = _load_optional(run_dir / "data_health.json") or {}
    symbol_meta = _load_optional(run_dir / "symbol_meta.json") or {}
    internals = _load_optional(run_dir / "internals.json") or {}
    sector_strength = _load_optional(run_dir / "sector_strength.json") or {}
    flow_data = _load_optional(run_dir / "flow_data.json") or {}
    fo_sentiment = _load_optional(run_dir / "fo_sentiment.json") or {}
    news_context = _load_optional(run_dir / "news_context.json") or {}
    market_context = _load_optional(run_dir / "market_context.json") or {}
    candidates = _load_optional(run_dir / "candidates.json") or {}
    decision = _load_optional(run_dir / "decision.json") or {}

    lines = []

    # Header
    lines.append("=" * 70)
    lines.append("TRADING SIGNAL ANALYSIS - DATA FOR CLAUDE CODE")
    lines.append("=" * 70)
    lines.append(f"Run: {run_dir.name}")
    lines.append(f"Data Date: {data_health.get('last_trading_day', 'Unknown')}")
    lines.append("")

    # =========================================================================
    # MARKET REGIME
    # =========================================================================
    lines.append("-" * 70)
    lines.append("1. MARKET REGIME")
    lines.append("-" * 70)
    regime = market_context.get("regime", "UNKNOWN")
    should_trade = market_context.get("should_trade", False)
    vix = market_context.get("vix", "N/A")
    vix_level = market_context.get("vix_level", "N/A")
    pos_mult = market_context.get("position_size_multiplier", 1.0)

    lines.append(f"Regime: {regime}")
    lines.append(f"Should Trade: {'YES' if should_trade else 'NO'}")
    lines.append(f"VIX: {vix} ({vix_level})")
    lines.append(f"Position Multiplier: {pos_mult}")

    nifty = market_context.get("nifty", {})
    if nifty:
        close = nifty.get("close", 0)
        ema50 = nifty.get("ema50", 0)
        ema200 = nifty.get("ema200", 0)
        golden_cross = "YES" if ema50 > ema200 else "NO"
        lines.append(f"NIFTY: {close:,.0f} | EMA50: {ema50:,.0f} | EMA200: {ema200:,.0f}")
        lines.append(f"Golden Cross (50>200): {golden_cross}")
    lines.append("")

    # =========================================================================
    # MARKET BREADTH
    # =========================================================================
    lines.append("-" * 70)
    lines.append("2. MARKET BREADTH")
    lines.append("-" * 70)
    breadth = internals.get("breadth", {}) if internals else {}
    if breadth:
        lines.append(f"State: {breadth.get('state', 'UNKNOWN')}")
        lines.append(f"Advancers/Decliners: {breadth.get('advancers', 0)}/{breadth.get('decliners', 0)}")
        lines.append(f"A/D Ratio: {breadth.get('ad_ratio', 0):.2f}")
        lines.append(f"Up Days (last 10): {breadth.get('up_days_last_10', 0)}/10")
        lines.append(f"Breadth Multiplier: {breadth.get('breadth_multiplier', 1.0)}")
    else:
        lines.append("Breadth data not available")
    lines.append("")

    # =========================================================================
    # FII/DII FLOWS (NEW)
    # =========================================================================
    lines.append("-" * 70)
    lines.append("3. INSTITUTIONAL FLOWS (FII/DII)")
    lines.append("-" * 70)
    if flow_data and flow_data.get("status") == "OK":
        metrics = flow_data.get("metrics", {})
        fii = metrics.get("fii", {})
        dii = metrics.get("dii", {})
        combined = metrics.get("combined", {})

        lines.append(f"FII Net: Rs {fii.get('net', 0):+,.0f} Cr | Trend: {fii.get('trend', 'UNKNOWN')}")
        lines.append(f"FII Severity: {fii.get('severity', 'UNKNOWN')} | 5D Avg: Rs {fii.get('5d_avg', 0):+,.0f} Cr")
        lines.append(f"DII Net: Rs {dii.get('net', 0):+,.0f} Cr | Trend: {dii.get('trend', 'UNKNOWN')}")
        lines.append(f"DII Absorbing FII: {'YES' if dii.get('absorbing_fii') else 'NO'}")
        lines.append(f"Combined Net: Rs {combined.get('total_net', 0):+,.0f} Cr | Impact: {combined.get('net_impact', 'UNKNOWN')}")
        lines.append(f"Flow Multiplier: {combined.get('flow_multiplier', 1.0)}")

        reasoning = flow_data.get("signal_impact", {}).get("reasoning", "")
        if reasoning:
            lines.append(f"Assessment: {reasoning}")
    else:
        lines.append("FII/DII data: UNAVAILABLE (using conservative 0.8x multiplier)")
    lines.append("")

    # =========================================================================
    # F&O SENTIMENT (NEW)
    # =========================================================================
    lines.append("-" * 70)
    lines.append("4. F&O SENTIMENT (NIFTY OPTIONS)")
    lines.append("-" * 70)
    if fo_sentiment and fo_sentiment.get("status") == "OK":
        analysis = fo_sentiment.get("analysis", {})
        pcr = analysis.get("pcr", {})
        max_pain = analysis.get("max_pain", {})
        oi_analysis = analysis.get("oi_analysis", {})
        sentiment_assessment = analysis.get("sentiment_assessment", {})

        lines.append(f"PCR: {pcr.get('value', 0):.2f} ({pcr.get('interpretation', 'N/A')})")
        lines.append(f"Max Pain: {max_pain.get('strike', 'N/A')} | Distance: {max_pain.get('distance_pct', 0):+.1f}% | Direction: {max_pain.get('direction', 'N/A')}")
        lines.append(f"Highest Call OI: {oi_analysis.get('highest_call_oi_strike', 'N/A')}")
        lines.append(f"Highest Put OI: {oi_analysis.get('highest_put_oi_strike', 'N/A')}")
        lines.append(f"OI Bias: {oi_analysis.get('oi_bias', 'N/A')}")
        lines.append(f"Sentiment: {sentiment_assessment.get('sentiment', 'NEUTRAL')} | Score: {sentiment_assessment.get('score', 0)}/5")
        lines.append(f"F&O Multiplier: {sentiment_assessment.get('multiplier', 1.0)}")

        factors = sentiment_assessment.get("factors", [])
        if factors:
            lines.append("Factors:")
            for f in factors[:5]:
                lines.append(f"  - {f}")
    else:
        lines.append("F&O data: UNAVAILABLE (using neutral assumptions)")
    lines.append("")

    # =========================================================================
    # NEWS & EVENTS (NEW)
    # =========================================================================
    lines.append("-" * 70)
    lines.append("5. NEWS & EVENTS CONTEXT")
    lines.append("-" * 70)
    if news_context and news_context.get("status") == "OK":
        risk_assessment = news_context.get("risk_assessment", {})
        lines.append(f"Event Risk Level: {risk_assessment.get('risk_level', 'UNKNOWN')}")
        lines.append(f"Risk Score: {risk_assessment.get('risk_score', 0)}")
        lines.append(f"News Multiplier: {risk_assessment.get('risk_multiplier', 1.0)}")

        risk_factors = risk_assessment.get("risk_factors", [])
        if risk_factors:
            lines.append("Risk Factors:")
            for rf in risk_factors:
                lines.append(f"  - {rf}")

        # Macro events
        macro = news_context.get("macro_events", {})
        high_impact = macro.get("high_impact_next_7d", [])
        if high_impact:
            lines.append("High Impact Events (next 7 days):")
            for event in high_impact[:3]:
                lines.append(f"  - {event.get('event')} in {event.get('days_away')} days")

        # Earnings
        earnings = news_context.get("earnings_calendar", {})
        near_earnings = earnings.get("next_3_days", [])
        if near_earnings:
            lines.append(f"Earnings in 3 days: {len(near_earnings)} stocks")
            symbols = [e.get("symbol") for e in near_earnings[:8]]
            lines.append(f"  AVOID: {', '.join(symbols)}")
    else:
        lines.append("News context: UNAVAILABLE")
    lines.append("")

    # =========================================================================
    # SECTOR STRENGTH
    # =========================================================================
    lines.append("-" * 70)
    lines.append("6. SECTOR ROTATION")
    lines.append("-" * 70)
    sectors = sector_strength.get("sectors", []) if sector_strength else []
    if sectors:
        lines.append("Rank | Sector          | RS Score | Monthly Return")
        lines.append("-" * 50)
        for s in sectors[:6]:
            rank = s.get("rank", 0)
            sector = s.get("sector", "Unknown")[:15].ljust(15)
            rs = s.get("rs_score", 0)
            mom = s.get("monthly_return", 0)
            lines.append(f"  {rank}  | {sector} | {rs:6.1f}   | {mom:+6.1f}%")

        avoid = (sector_strength.get("summary", {}) or {}).get("avoid_sectors", [])
        if avoid:
            lines.append(f"Avoid Sectors: {', '.join(avoid)}")
    else:
        lines.append("Sector data not available")
    lines.append("")

    # =========================================================================
    # TOP CANDIDATES
    # =========================================================================
    lines.append("-" * 70)
    lines.append("7. TOP CANDIDATES")
    lines.append("-" * 70)
    cands = [c for c in candidates.get("candidates", [])[:10] if not c.get("should_skip")]

    if cands:
        for i, c in enumerate(cands[:5], 1):
            symbol = c.get("symbol", "?")
            grade = c.get("grade", "?")
            conv = c.get("conviction", 0)
            price = c.get("price", 0)
            sector = c.get("sector", "?")
            setup = c.get("setup", {})

            lines.append(f"\n{i}. {symbol} - Grade {grade} ({conv}/100)")
            lines.append(f"   Price: Rs {price:,.2f} | Sector: {sector}")
            lines.append(f"   Entry: Rs {setup.get('entry', 0):,.2f} | Stop: Rs {setup.get('stop_loss', 0):,.2f} ({setup.get('stop_pct', 0):.1f}%)")
            lines.append(f"   T1: Rs {setup.get('target1', 0):,.2f} | T2: Rs {setup.get('target2', 0):,.2f}")

            # Model votes
            models = c.get("models", {})
            votes = []
            for model in ["momentum", "breakout", "trend_following", "mean_reversion"]:
                if models.get(model, {}).get("signal") == "BUY":
                    votes.append(model.replace("_", " ").title())
            if votes:
                lines.append(f"   Model Votes: {', '.join(votes)}")

            # Conviction breakdown
            factors = c.get("conviction_factors", {})
            if factors:
                lines.append(f"   Conviction: Tech={factors.get('technical', 0)}/25, Conf={factors.get('confluence', 0)}/20, Ctx={factors.get('context', 0)}/20, Sec={factors.get('sector', 0)}/15, Tim={factors.get('timing', 0)}/10")
    else:
        lines.append("No candidates found")
    lines.append("")

    # =========================================================================
    # DETERMINISTIC DECISION
    # =========================================================================
    lines.append("-" * 70)
    lines.append("8. DETERMINISTIC DECISION (Stage D)")
    lines.append("-" * 70)
    if decision:
        action = decision.get("action", "UNKNOWN")
        if action == "NO_TRADE":
            lines.append(f"Decision: NO TRADE")
            lines.append(f"Reason: {decision.get('reason', 'Unknown')}")
        else:
            symbol = decision.get("symbol", "?")
            conv = decision.get("conviction", 0)
            grade = decision.get("grade", "?")

            lines.append(f"Decision: {action} {symbol}")
            lines.append(f"Conviction: {conv}/100 ({grade})")
            lines.append(f"Entry: Rs {decision.get('entry', 0):,.2f}")
            lines.append(f"Stop Loss: Rs {decision.get('stop_loss', 0):,.2f}")
            lines.append(f"Target 1: Rs {decision.get('target1', 0):,.2f}")
            lines.append(f"Target 2: Rs {decision.get('target2', 0):,.2f}")
            lines.append(f"Shares: {decision.get('shares', 0)}")
            lines.append(f"Position Value: Rs {decision.get('position_value', 0):,.2f}")
            lines.append(f"Risk Amount: Rs {decision.get('risk_amount', 0):,.2f} ({decision.get('risk_pct', 0):.2f}%)")

            gap_risk = decision.get("gap_risk", {})
            if gap_risk:
                lines.append(f"Gap Risk (95%): {gap_risk.get('gap_95_pct', 0):.1f}%")
                lines.append(f"Net R:R: {gap_risk.get('net_rr', 0):.2f}")

            # Alternatives
            alts = decision.get("alternatives", [])
            if alts:
                lines.append(f"\nAlternative: {alts[0].get('symbol')} ({alts[0].get('conviction')}/100 {alts[0].get('grade')})")
    else:
        lines.append("Decision data not available")
    lines.append("")

    # =========================================================================
    # COMBINED MULTIPLIERS
    # =========================================================================
    lines.append("-" * 70)
    lines.append("9. COMBINED POSITION SIZE ADJUSTMENT")
    lines.append("-" * 70)

    regime_mult = market_context.get("regime_multiplier", 1.0)
    breadth_mult = breadth.get("breadth_multiplier", 1.0) if breadth else 1.0
    flow_mult = flow_data.get("metrics", {}).get("combined", {}).get("flow_multiplier", 1.0) if flow_data.get("status") == "OK" else 0.8
    fo_mult = fo_sentiment.get("analysis", {}).get("sentiment_assessment", {}).get("multiplier", 1.0) if fo_sentiment.get("status") == "OK" else 1.0
    news_mult = news_context.get("risk_assessment", {}).get("risk_multiplier", 1.0) if news_context.get("status") == "OK" else 1.0

    combined_mult = regime_mult * breadth_mult * flow_mult * fo_mult * news_mult

    lines.append(f"Regime Multiplier:  {regime_mult:.2f}")
    lines.append(f"Breadth Multiplier: {breadth_mult:.2f}")
    lines.append(f"Flow Multiplier:    {flow_mult:.2f}")
    lines.append(f"F&O Multiplier:     {fo_mult:.2f}")
    lines.append(f"News Multiplier:    {news_mult:.2f}")
    lines.append(f"-" * 30)
    lines.append(f"COMBINED:           {combined_mult:.2f} ({int(combined_mult * 100)}% of normal size)")
    lines.append("")

    # Footer
    lines.append("=" * 70)
    lines.append("END OF DATA - CLAUDE CODE CAN NOW ANALYZE")
    lines.append("=" * 70)

    return "\n".join(lines)


def prepare_for_claude_code(run_dir: Path, quiet: bool = False) -> dict:
    """
    Prepare context for Claude Code analysis.

    Args:
        run_dir: Path to the run directory
        quiet: If True, don't print to stdout

    Returns:
        Status dict
    """
    print("Preparing context for Claude Code analysis...")

    # Build context summary
    context_summary = build_context_summary(run_dir)

    # Save for reference
    context_path = run_dir / "claude_context.md"
    with open(context_path, "w", encoding="utf-8") as f:
        f.write(context_summary)
    print(f"  Saved context to: {context_path}")

    # Print to stdout for Claude Code to analyze
    if not quiet:
        print("\n")
        print(context_summary)

    output = {
        "build_timestamp": datetime.now().isoformat(),
        "status": "OK",
        "context_path": str(context_path),
        "method": "claude_code_terminal",
        "note": "Data output to terminal for Claude Code analysis"
    }

    # Write status
    out_path = run_dir / "claude_analysis.json"
    _write_json(out_path, output)

    return output


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Prepare data for Claude Code analysis')
    parser.add_argument('run_dir', type=str, help='Path to run directory')
    parser.add_argument('--quiet', action='store_true', help='Save context without printing to stdout')
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    prepare_for_claude_code(run_dir, quiet=args.quiet)
    sys.exit(0)


if __name__ == "__main__":
    main()
