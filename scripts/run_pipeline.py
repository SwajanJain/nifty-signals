#!/usr/bin/env python3
"""
Trading Pipeline Orchestrator

Runs the complete trading pipeline in sequence:
1. Stage A: Data Preparation → data_health.json
2. Stage A2: Symbol Meta → symbol_meta.json (earnings, fundamentals)
3. Stage A3: Market Internals → internals.json (breadth)
4. Stage A4: Sector Strength → sector_strength.json (relative strength)
5. Stage A5: Flow Data → flow_data.json (FII/DII flows)
6. Stage A6: F&O Sentiment → fo_sentiment.json (PCR, max pain, OI)
7. Stage A7: News Context → news_context.json (macro events, earnings calendar)
8. Stage B: Build Context → market_context.json
9. Stage C: Scan Universe → candidates.json
10. Stage D: Make Decision → decision.json + manifest.json
11. Stage E: Enrich Report → symbol/*.json
12. Stage F1: Claude Analysis → claude_analysis.json (AI insights)
13. Stage F0: Review Run → review.json
14. Stage F: Generate Report → final.md

Creates a new run folder for each execution.
Logs all steps to audit.jsonl.

Usage:
    python run_pipeline.py              # Creates new run
    python run_pipeline.py --dry-run    # Shows what would run
"""

import json
import sys
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
RUNS_DIR = PROJECT_ROOT / "journal" / "runs"


def create_run_id() -> str:
    """Create a unique run ID based on current timestamp."""
    return datetime.now().strftime("%Y-%m-%d_%H%M")


def log_audit(run_dir: Path, stage: str, status: str, details: dict = None):
    """Append to audit log."""
    audit_path = run_dir / "audit.jsonl"

    entry = {
        'ts': datetime.now().strftime("%H:%M:%S"),
        'stage': stage,
        'status': status
    }
    if details:
        entry.update(details)

    with open(audit_path, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def run_stage(run_dir: Path, stage_name: str, script_name: str, stop_on_fail: bool = True) -> bool:
    """
    Run a pipeline stage.

    Returns:
        True if stage passed, False if failed
    """
    script_path = SCRIPTS_DIR / script_name

    print(f"\n{'='*60}")
    print(f"STAGE {stage_name}")
    print(f"{'='*60}")

    log_audit(run_dir, stage_name, 'started')

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), str(run_dir)],
            cwd=PROJECT_ROOT,
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            log_audit(run_dir, stage_name, 'passed')
            return True
        else:
            log_audit(run_dir, stage_name, 'failed', {'exit_code': result.returncode})
            if stop_on_fail:
                print(f"\nStage {stage_name} failed with exit code {result.returncode}")
                print("Pipeline halted.")
            return False

    except Exception as e:
        log_audit(run_dir, stage_name, 'error', {'error': str(e)})
        print(f"\nError running stage {stage_name}: {e}")
        return False


def generate_final_report(run_dir: Path) -> str:
    """
    Generate final.md report summarizing the run.

    This is where Claude would normally write the explanation,
    but we provide a structured template.
    """
    from typing import Optional, Any, List

    def _load(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_optional(path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            return _load(path)
        except Exception:
            return None

    def _regime_score(regime: Optional[str]) -> int:
        return {
            "STRONG_BULL": 5,
            "BULL": 3,
            "NEUTRAL": 0,
            "BEAR": -3,
            "STRONG_BEAR": -5,
            "CRASH": -8,
        }.get(regime or "NEUTRAL", 0)

    def _fmt_inr(x: Any) -> str:
        try:
            return f"₹{float(x):,.2f}"
        except Exception:
            return "N/A"

    def _fmt_pct(x: Any, digits: int = 1) -> str:
        try:
            return f"{float(x):.{digits}f}%"
        except Exception:
            return "N/A"

    def _company_name(symbol: str) -> str:
        stocks = _load_optional(PROJECT_ROOT / "stocks.json") or {}
        for item in stocks.get("nifty_100", []) if isinstance(stocks, dict) else []:
            if item.get("symbol") == symbol:
                return item.get("name") or symbol
        return symbol

    def _find_candidate(cands: List[dict], symbol: str) -> Optional[dict]:
        for c in cands:
            if c.get("symbol") == symbol:
                return c
        return None

    decision = _load(run_dir / "decision.json")
    context = _load(run_dir / "market_context.json")
    health = _load(run_dir / "data_health.json")
    candidates_data = _load(run_dir / "candidates.json")
    sector_strength = _load_optional(run_dir / "sector_strength.json") or {}
    flow_data = _load_optional(run_dir / "flow_data.json") or {}
    fo_sentiment = _load_optional(run_dir / "fo_sentiment.json") or {}
    news_context = _load_optional(run_dir / "news_context.json") or {}
    claude_analysis = _load_optional(run_dir / "claude_analysis.json") or {}
    config = _load(PROJECT_ROOT / "config" / "trading_config.json")

    candidates = candidates_data.get("candidates", []) or []
    asof = health.get("last_trading_day") or run_dir.name

    lines: List[str] = []
    lines.append(f"# Trading Signal - {asof}")
    lines.append(f"\nRun: `{run_dir.name}`")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # ---------------------------
    # MARKET CONTEXT
    # ---------------------------
    regime = context.get("regime")
    should_trade = bool(context.get("should_trade", False))
    kill_reason = context.get("kill_reason")
    vix = context.get("vix")
    vix_level = context.get("vix_level")
    pos_mult = float(context.get("position_size_multiplier", context.get("regime_multiplier", 0.5)))

    nifty = context.get("nifty") or {}
    golden_cross = False
    try:
        golden_cross = bool(float(nifty.get("ema50", 0)) > float(nifty.get("ema200", 0)))
    except Exception:
        golden_cross = False

    breadth = context.get("breadth") or {}
    breadth_state = breadth.get("state") if isinstance(breadth, dict) else "UNKNOWN"

    lines.append("\n## MARKET CONTEXT")
    lines.append("")
    lines.append("| Factor | Status | Details |")
    lines.append("|---|---|---|")
    lines.append(f"| Regime | {regime} | Score {_regime_score(regime)}/5, Golden Cross: {'YES' if golden_cross else 'NO'} |")
    lines.append(f"| Should Trade | {'YES' if should_trade else 'NO'} | {kill_reason or 'Normal conditions'} |")
    lines.append(
        f"| Position Size | {int(round(pos_mult*100))}% of normal | Multipliers: regime={context.get('regime_multiplier')}, breadth={context.get('breadth_multiplier')} |"
    )
    lines.append(f"| VIX | {vix} ({vix_level}) | {'Favorable' if (vix is not None and float(vix) < 20) else 'Caution'} |")
    if isinstance(breadth, dict) and breadth:
        lines.append(
            f"| Breadth | {breadth_state} | Adv/Dec {breadth.get('advancers')}/{breadth.get('decliners')}, Up days {breadth.get('up_days_last_10')}/10 |"
        )
    else:
        lines.append("| Breadth | UNKNOWN | internals.json missing |")

    # ---------------------------
    # SECTOR ROTATION
    # ---------------------------
    sector_rows = (sector_strength.get("sectors") or []) if isinstance(sector_strength, dict) else []
    avoid_sectors = (sector_strength.get("summary") or {}).get("avoid_sectors") if isinstance(sector_strength, dict) else []

    if not sector_rows:
        sector_rows = context.get("sectors") or []
        avoid_sectors = context.get("avoid_sectors") or []

    if sector_rows:
        lines.append("\n**Top Sectors**")
        for s in [x for x in sector_rows if isinstance(x, dict)][:4]:
            rank = int(s.get("rank", 0) or 0)
            star = " ⭐" if rank == 1 else ""
            rs = s.get("rs_score")
            mom = s.get("monthly_return")
            details = []
            if rs is not None:
                details.append(f"RS {rs}")
            if isinstance(mom, (int, float)):
                details.append(f"{mom:+.1f}% monthly")
            lines.append(f"{rank}. {s.get('sector')}{star} - {', '.join(details)}")

    if avoid_sectors:
        lines.append("\n**Avoid**")
        if isinstance(avoid_sectors, list) and avoid_sectors:
            lines.append(f"- {', '.join(avoid_sectors)}")
        else:
            lines.append("- None")

    # ---------------------------
    # FII/DII FLOWS
    # ---------------------------
    if flow_data and flow_data.get("status") == "OK":
        metrics = flow_data.get("metrics", {})
        fii = metrics.get("fii", {})
        dii = metrics.get("dii", {})
        combined = metrics.get("combined", {})

        lines.append("\n## INSTITUTIONAL FLOWS")
        lines.append("")
        lines.append("| Metric | Value | Assessment |")
        lines.append("|---|---|---|")
        lines.append(f"| FII Net | ₹{fii.get('net', 0):+,.0f} Cr | {fii.get('trend', 'N/A')} |")
        lines.append(f"| DII Net | ₹{dii.get('net', 0):+,.0f} Cr | {dii.get('trend', 'N/A')} |")
        lines.append(f"| Total | ₹{combined.get('total_net', 0):+,.0f} Cr | {combined.get('net_impact', 'N/A')} |")
        lines.append(f"| Flow Multiplier | {combined.get('flow_multiplier', 1.0)} | {'Reduce size' if combined.get('flow_multiplier', 1.0) < 1.0 else 'Normal'} |")

        if dii.get("absorbing_fii"):
            lines.append("\n*DII absorbing FII selling - suggests consolidation, not panic*")

    # ---------------------------
    # F&O SENTIMENT
    # ---------------------------
    if fo_sentiment and fo_sentiment.get("status") == "OK":
        analysis = fo_sentiment.get("analysis", {})
        pcr = analysis.get("pcr", {})
        max_pain = analysis.get("max_pain", {})
        sentiment_assessment = analysis.get("sentiment_assessment", {})

        lines.append("\n## F&O SENTIMENT")
        lines.append("")
        lines.append("| Metric | Value | Interpretation |")
        lines.append("|---|---|---|")
        lines.append(f"| PCR | {pcr.get('value', 0):.2f} | {pcr.get('interpretation', 'N/A')} |")
        lines.append(f"| Max Pain | {max_pain.get('strike', 'N/A')} | {max_pain.get('direction', 'N/A')} ({max_pain.get('distance_pct', 0):+.1f}%) |")
        lines.append(f"| Sentiment | {sentiment_assessment.get('sentiment', 'NEUTRAL')} | Score: {sentiment_assessment.get('score', 0)}/5 |")
        lines.append(f"| F&O Multiplier | {sentiment_assessment.get('multiplier', 1.0)} | |")

    # ---------------------------
    # EVENT RISK
    # ---------------------------
    if news_context and news_context.get("status") == "OK":
        risk_assessment = news_context.get("risk_assessment", {})
        signal_impact = news_context.get("signal_impact", {})

        lines.append("\n## EVENT RISK")
        lines.append("")
        lines.append(f"**Risk Level:** {risk_assessment.get('risk_level', 'UNKNOWN')}")
        lines.append(f"**News Multiplier:** {risk_assessment.get('risk_multiplier', 1.0)}")

        risk_factors = risk_assessment.get("risk_factors", [])
        if risk_factors:
            lines.append("")
            for rf in risk_factors:
                lines.append(f"- {rf}")

        avoid_symbols = signal_impact.get("avoid_symbols", [])
        if avoid_symbols:
            lines.append(f"\n**Avoid (earnings):** {', '.join(avoid_symbols[:5])}")

    # ---------------------------
    # DECISION
    # ---------------------------
    action = decision.get("action")
    if action == "NO_TRADE":
        lines.append("\n---\n")
        lines.append("## DECISION: NO TRADE")
        lines.append("")
        lines.append(f"**Reason:** {decision.get('reason', 'Unknown')}")
    else:
        symbol = decision.get("symbol")
        candidate = _find_candidate(candidates, symbol) if symbol else None

        company = _company_name(symbol) if symbol else ""
        sector = candidate.get("sector") if isinstance(candidate, dict) else None
        sector_rank = None
        if isinstance(candidate, dict):
            sector_rank = candidate.get("sector_rank")
            if isinstance(candidate.get("sector_meta"), dict) and candidate["sector_meta"].get("rank"):
                sector_rank = candidate["sector_meta"].get("rank")

        lines.append("\n---\n")
        lines.append(f"## TOP PICK: {symbol} {_fmt_inr(candidate.get('price') if isinstance(candidate, dict) else decision.get('entry'))}")
        if sector:
            lines.append(f"{company} | {sector} Sector (Rank #{sector_rank})")

        lines.append("")
        lines.append(f"Conviction: {decision.get('grade')} ({decision.get('conviction')}/100)")

        factors = candidate.get("conviction_factors") if isinstance(candidate, dict) else {}
        if isinstance(factors, dict) and factors:
            mtf = candidate.get("mtf") if isinstance(candidate, dict) else {}
            lines.append("")
            lines.append("| Component | Score | Notes |")
            lines.append("|---|---:|---|")
            lines.append(f"| Technical | {factors.get('technical')}/25 | indicators + key signals |")
            lines.append(f"| Confluence | {factors.get('confluence')}/20 | MTF: {(mtf or {}).get('recommendation', 'N/A')} |")
            lines.append(f"| Context | {factors.get('context')}/20 | {regime} regime, size {int(round(pos_mult*100))}% |")
            lines.append(f"| Sector | {factors.get('sector')}/15 | Sector rank #{sector_rank} |")
            lines.append(f"| Timing | {factors.get('timing')}/10 | distance + volume |")

        capital = float((decision.get("portfolio") or {}).get("capital", 0) or 0)
        pos_val = float(decision.get("position_value", 0) or 0)
        pos_pct = (pos_val / capital * 100) if capital > 0 else 0.0

        lines.append("\n### Trade Setup")
        lines.append("")
        lines.append("| Parameter | Value |")
        lines.append("|---|---|")
        lines.append(f"| Entry | {_fmt_inr(decision.get('entry'))} |")
        lines.append(f"| Stop Loss | {_fmt_inr(decision.get('stop_loss'))} |")
        lines.append(f"| Target 1 | {_fmt_inr(decision.get('target1'))} |")
        lines.append(f"| Target 2 | {_fmt_inr(decision.get('target2'))} |")
        lines.append(f"| Position | {decision.get('shares')} shares |")
        lines.append(f"| Capital Used | {_fmt_inr(pos_val)} ({pos_pct:.1f}% of capital) |")
        lines.append(f"| Risk | {_fmt_inr(decision.get('risk_amount'))} ({_fmt_pct(decision.get('risk_pct'), 2)}) |")

        # Model Votes
        votes = (decision.get("reasoning") or {}).get("votes", {}) or {}
        lines.append("\n### Model Votes")
        lines.append("")
        for model in ["momentum", "breakout", "trend", "mean_reversion"]:
            mark = "✓" if votes.get(model) else "✗"
            lines.append(f"- {mark} {model.capitalize()}")

        # Alternatives
        alternatives = decision.get("alternatives") or []
        if isinstance(alternatives, list) and alternatives:
            lines.append("\n### Alternative")
            alt = alternatives[0]
            alt_symbol = alt.get("symbol")
            alt_cand = _find_candidate(candidates, alt_symbol) if alt_symbol else None
            if isinstance(alt_cand, dict):
                setup = alt_cand.get("setup") or {}
                lines.append("")
                lines.append(f"- {alt_symbol} ({alt.get('conviction')}/100 {alt.get('grade')})")
                lines.append(f"  - Entry: {_fmt_inr(setup.get('entry'))} | Stop: {_fmt_inr(setup.get('stop_loss'))} | T1: {_fmt_inr(setup.get('target1'))} | T2: {_fmt_inr(setup.get('target2'))}")
            else:
                lines.append(f"- {alt_symbol} ({alt.get('conviction')}/100 {alt.get('grade')})")

        # Risk Checklist
        portfolio = decision.get("portfolio") or {}
        meta_gates = decision.get("meta_gates") or {}
        gap_risk = decision.get("gap_risk") or {}
        lines.append("\n### Risk Checklist")
        lines.append("")
        lines.append(f"- Portfolio heat: {portfolio.get('current_heat_pct')}% (limit 6%)")
        lines.append(f"- Single position: {pos_pct:.1f}% (limit 15%)")
        if isinstance(candidate, dict):
            lines.append(f"- Liquidity (ADV Cr): {(candidate.get('technicals') or {}).get('adv_value_cr')}")
        if isinstance(meta_gates, dict) and meta_gates:
            e = meta_gates.get("earnings") or {}
            f = meta_gates.get("fundamentals") or {}
            lines.append(f"- Earnings: {(e or {}).get('status')} ({(e or {}).get('days_to')} days)")
            lines.append(f"- Fundamentals: {(f or {}).get('grade')}")
        lines.append(f"- Net R:R: {gap_risk.get('net_rr')} (min {config.get('execution_rules', {}).get('min_net_rr', 1.5)})")

        lines.append("\n### ACTION")
        lines.append("")
        lines.append(
            f"{decision.get('action')} {symbol} at {_fmt_inr(decision.get('entry'))} | SL {_fmt_inr(decision.get('stop_loss'))} | Size: {decision.get('shares')} shares"
        )

    # ---------------------------
    # CLAUDE ANALYSIS
    # ---------------------------
    if claude_analysis and claude_analysis.get("status") == "OK":
        lines.append("\n---\n")
        lines.append("## AI ANALYSIS")
        lines.append("")
        lines.append(claude_analysis.get("analysis", "*Analysis not available*"))
        lines.append("")
        lines.append(f"*Model: {claude_analysis.get('model', 'Unknown')} | Tokens: {claude_analysis.get('completion_tokens', 0)}*")

    lines.append("\n---\n")
    lines.append("*Generated by deterministic pipeline (code decides; Claude narrates).*")

    report = "\n".join(lines)
    report_path = run_dir / "final.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report


def run_pipeline(dry_run: bool = False) -> Path:
    """
    Run the complete trading pipeline.

    Returns:
        Path to the run directory
    """
    # Create run directory
    run_id = create_run_id()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'#'*60}")
    print(f"# TRADING PIPELINE")
    print(f"# Run ID: {run_id}")
    print(f"# Directory: {run_dir}")
    print(f"{'#'*60}")

    if dry_run:
        print("\n[DRY RUN] Would execute the following stages:")
        print("  A: prepare_data.py → data_health.json")
        print("  A2: build_symbol_meta.py → symbol_meta.json")
        print("  A3: build_internals.py → internals.json")
        print("  A4: build_sector_strength.py → sector_strength.json")
        print("  A5: build_flow_data.py → flow_data.json (FII/DII)")
        print("  A6: build_fo_sentiment.py → fo_sentiment.json (F&O)")
        print("  A7: build_news_context.py → news_context.json (News/Events)")
        print("  B: build_context.py → market_context.json")
        print("  C: scan_universe.py → candidates.json")
        print("  D: make_decision.py → decision.json + manifest.json")
        print("  E: enrich_report.py → symbol/*.json")
        print("  F1: claude_analysis.py → claude_analysis.json (AI insights)")
        print("  F0: review_run.py → review.json")
        print("  F: generate_final_report → final.md")
        return run_dir

    # Initialize audit log
    log_audit(run_dir, 'PIPELINE', 'started', {'run_id': run_id})

    # Stage A: Data Preparation
    if not run_stage(run_dir, 'A', 'prepare_data.py', stop_on_fail=True):
        log_audit(run_dir, 'PIPELINE', 'halted', {'reason': 'Stage A failed'})
        return run_dir

    # Stage A2: Symbol Meta (earnings + fundamentals) - optional but recommended
    run_stage(run_dir, 'A2', 'build_symbol_meta.py', stop_on_fail=False)

    # Stage A3: Market Internals (breadth) - optional but recommended
    run_stage(run_dir, 'A3', 'build_internals.py', stop_on_fail=False)

    # Stage A4: Sector RS/rotation (from snapshots) - optional but recommended
    run_stage(run_dir, 'A4', 'build_sector_strength.py', stop_on_fail=False)

    # Stage A5: FII/DII Flow Data - critical for institutional sentiment
    run_stage(run_dir, 'A5', 'build_flow_data.py', stop_on_fail=False)

    # Stage A6: F&O Sentiment - PCR, max pain, OI analysis
    run_stage(run_dir, 'A6', 'build_fo_sentiment.py', stop_on_fail=False)

    # Stage A7: News/Events Context - macro events, earnings calendar
    run_stage(run_dir, 'A7', 'build_news_context.py', stop_on_fail=False)

    # Stage B: Build Context
    if not run_stage(run_dir, 'B', 'build_context.py', stop_on_fail=True):
        log_audit(run_dir, 'PIPELINE', 'halted', {'reason': 'Stage B failed'})
        return run_dir

    # Stage C: Scan Universe
    if not run_stage(run_dir, 'C', 'scan_universe.py', stop_on_fail=True):
        log_audit(run_dir, 'PIPELINE', 'halted', {'reason': 'Stage C failed'})
        return run_dir

    # Stage D: Make Decision (THE SACRED STAGE)
    if not run_stage(run_dir, 'D', 'make_decision.py', stop_on_fail=False):
        # Decision might be NO_TRADE, which is still valid
        pass

    # Stage E: Enrich Report (optional, doesn't fail pipeline)
    run_stage(run_dir, 'E', 'enrich_report.py', stop_on_fail=False)

    # Stage F1: Claude Analysis (intelligent market commentary)
    run_stage(run_dir, 'F1', 'claude_analysis.py', stop_on_fail=False)

    # Stage F0: Run Review (optional)
    run_stage(run_dir, 'F0', 'review_run.py', stop_on_fail=False)

    # Stage F: Generate Final Report
    print(f"\n{'='*60}")
    print("STAGE F: Generate Report")
    print(f"{'='*60}")

    try:
        report = generate_final_report(run_dir)
        log_audit(run_dir, 'F', 'passed')
        print(f"Report saved to: {run_dir / 'final.md'}")
    except Exception as e:
        log_audit(run_dir, 'F', 'error', {'error': str(e)})
        print(f"Error generating report: {e}")

    # Pipeline complete
    log_audit(run_dir, 'PIPELINE', 'completed')

    print(f"\n{'#'*60}")
    print(f"# PIPELINE COMPLETE")
    print(f"# Run ID: {run_id}")
    print(f"# Outputs: {run_dir}")
    print(f"{'#'*60}")

    # Print decision summary
    decision_path = run_dir / "decision.json"
    if decision_path.exists():
        with open(decision_path) as f:
            decision = json.load(f)

        print(f"\n{'='*60}")
        if decision['action'] == 'NO_TRADE':
            print(f"FINAL DECISION: NO TRADE")
            print(f"Reason: {decision.get('reason', 'Unknown')}")
        else:
            print(f"FINAL DECISION: {decision['action']} {decision['symbol']}")
            print(f"Conviction: {decision['conviction']}/100 ({decision['grade']})")
            print(f"Entry: ₹{decision['entry']:,.2f}")
            print(f"Stop: ₹{decision['stop_loss']:,.2f}")
            print(f"Shares: {decision['shares']}")
        print(f"{'='*60}")

    return run_dir


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run trading pipeline')
    parser.add_argument('--dry-run', action='store_true', help='Show what would run without executing')
    args = parser.parse_args()

    run_dir = run_pipeline(dry_run=args.dry_run)

    # Print final files
    print(f"\nOutput files in {run_dir}:")
    for f in sorted(run_dir.iterdir()):
        if f.is_file():
            print(f"  {f.name}")
        elif f.is_dir():
            print(f"  {f.name}/")
            for sf in sorted(f.iterdir()):
                print(f"    {sf.name}")


if __name__ == "__main__":
    main()
