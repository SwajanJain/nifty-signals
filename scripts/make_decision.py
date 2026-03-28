#!/usr/bin/env python3
"""
Stage D: Make Decision (Deterministic)

THIS IS THE SACRED SCRIPT.

Properties:
- Network-free (no API calls)
- Time-independent (no datetime.now() affecting thresholds)
- Deterministic given pinned inputs + portfolio snapshot

Reads:
- data_health.json
- market_context.json
- candidates.json
- config/trading_config.json
- journal/positions.json (snapshotted into run_dir)

Outputs:
- decision.json (THE DECISION)
- manifest.json (pins all inputs for reproducibility)

HARD KILL SWITCHES (in code, not Claude):
- Portfolio heat > max → NO NEW TRADE
- Sector exposure > max → SKIP THIS SECTOR
- No candidate >= min conviction → NO TRADE
"""

import json
import sys
import hashlib
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from journal.position_manager import PortfolioRiskLimits, PositionManager


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    if not filepath.exists():
        return ""
    with open(filepath, 'rb') as f:
        return f"sha256:{hashlib.sha256(f.read()).hexdigest()[:16]}"


def get_git_info() -> dict:
    """Get current git commit info for versioning."""
    try:
        sha = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL
        ).decode().strip()[:12]

        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL
        ).decode().strip()

        # Check if dirty
        status = subprocess.check_output(
            ['git', 'status', '--porcelain'],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL
        ).decode().strip()
        dirty = len(status) > 0

        return {
            'git_sha': sha,
            'git_branch': branch,
            'git_dirty': dirty
        }
    except Exception:
        return {
            'git_sha': 'unknown',
            'git_branch': 'unknown',
            'git_dirty': True
        }


def load_json(filepath: Path) -> dict:
    """Load JSON file."""
    with open(filepath) as f:
        return json.load(f)


def _get_capital(config: dict) -> float:
    """Get pinned portfolio capital from config (never from env)."""
    portfolio = config.get("portfolio") or {}
    capital = float(portfolio.get("capital", 1_000_000))
    if capital <= 0:
        raise ValueError(f"Invalid portfolio capital: {capital}")
    return capital


def _data_quality_multiplier(data_health: dict) -> float:
    """
    Convert data_health.json quality score into a sizing multiplier.

    This intentionally FAILS CLOSED on low quality.
    """
    score = float(data_health.get("quality_score", 0))

    # Stage A already hard-stops <80%, but we still scale size within [80,100].
    if score >= 95:
        return 1.0
    if score >= 90:
        return 0.9
    if score >= 85:
        return 0.75
    if score >= 80:
        return 0.5
    return 0.0


def _snapshot_positions(run_dir: Path, pm: PositionManager) -> Path:
    """Copy current positions file into the run folder for audit/repro."""
    snapshot = run_dir / "positions_snapshot.json"
    try:
        if pm.positions_file.exists():
            shutil.copyfile(pm.positions_file, snapshot)
        else:
            snapshot.write_text("{}", encoding="utf-8")
    except Exception:
        # Do not crash the decision for snapshot failures; keep best-effort.
        return snapshot
    return snapshot


def _load_symbol_meta(run_dir: Path) -> dict:
    """Load pinned earnings/fundamentals meta (Stage A2), if present."""
    path = run_dir / "symbol_meta.json"
    if not path.exists():
        return {}
    try:
        return load_json(path)
    except Exception:
        return {}


def _load_snapshot_df(run_dir: Path, symbol: str) -> Optional[pd.DataFrame]:
    """Load OHLCV snapshot for a symbol from the run folder."""
    path = run_dir / "data" / "daily" / f"{symbol}.csv"
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        expected = {"open", "high", "low", "close", "volume"}
        if not expected.issubset(set(df.columns)):
            return None
        return df[["open", "high", "low", "close", "volume"]].sort_index()
    except Exception:
        return None


def _gap_95pct(df: Optional[pd.DataFrame]) -> float:
    """
    Conservative 95th percentile absolute open gap (as %).

    gap% = |open / prev_close - 1| * 100
    """
    if df is None or len(df) < 30:
        return 0.0
    closes = df["close"].astype(float)
    opens = df["open"].astype(float)
    prev_close = closes.shift(1)
    gaps = (opens / prev_close - 1.0).abs() * 100.0
    gaps = gaps.replace([np.inf, -np.inf], np.nan).dropna()
    if len(gaps) < 10:
        return 0.0
    return float(np.nanpercentile(gaps.values, 95))


def make_decision(run_dir: Path) -> dict:
    """
    Make trading decision based on pinned inputs.

    THIS IS A PURE FUNCTION.
    Same inputs will ALWAYS produce the same outputs.
    """
    # =========================================================================
    # LOAD ALL INPUTS (from pinned files only)
    # =========================================================================

    config_path = PROJECT_ROOT / "config" / "trading_config.json"
    data_health_path = run_dir / "data_health.json"
    market_context_path = run_dir / "market_context.json"
    candidates_path = run_dir / "candidates.json"
    symbol_meta_path = run_dir / "symbol_meta.json"

    config = load_json(config_path)
    data_health = load_json(data_health_path)
    market_context = load_json(market_context_path)
    candidates_data = load_json(candidates_path)
    symbol_meta = _load_symbol_meta(run_dir)

    candidates = candidates_data.get('candidates', [])
    meta_by_symbol = (symbol_meta.get("symbols") or {}) if isinstance(symbol_meta, dict) else {}

    # Pinned portfolio + portfolio-aware risk limits (never from env)
    capital = _get_capital(config)
    limits = PortfolioRiskLimits(
        max_portfolio_heat=float(config["risk_limits"]["max_portfolio_heat_pct"]),
        max_position_pct=float(config["risk_limits"]["max_single_position_pct"]),
        max_sector_pct=float(config["risk_limits"]["max_sector_exposure_pct"]),
        max_positions_per_sector=int(config["risk_limits"]["max_correlated_positions"]),
        min_liquidity_cr=float(config["risk_limits"]["min_liquidity_cr"]),
    )
    position_manager = PositionManager(capital=capital, limits=limits)

    regime_multiplier = float(market_context.get("regime_multiplier", 0.5))
    breadth_multiplier = float(market_context.get("breadth_multiplier", 1.0))
    position_size_multiplier = float(
        market_context.get("position_size_multiplier", regime_multiplier * breadth_multiplier)
    )
    dq_multiplier = _data_quality_multiplier(data_health)
    combined_multiplier = dq_multiplier * position_size_multiplier

    positions_snapshot_path = _snapshot_positions(run_dir, position_manager)

    # Risk allocation by conviction (percent), sourced from pinned config
    risk_by_conviction = {"D": 0.0}
    for k, v in (config.get("conviction", {}).get("grades", {}) or {}).items():
        try:
            risk_by_conviction[str(k)] = float(v.get("risk_pct", 0))
        except Exception:
            risk_by_conviction[str(k)] = 0.0

    # =========================================================================
    # KILL SWITCHES (Code-enforced, not Claude-discretionary)
    # =========================================================================

    # Kill switch 1: Data health
    if not data_health.get('can_proceed', False):
        return create_no_trade_decision(
            run_dir, config, data_health, market_context,
            reason=f"Data health check failed: {data_health.get('kill_reason', 'Unknown')}"
        )

    # Kill switch 2: Market regime
    if not market_context.get('should_trade', False):
        return create_no_trade_decision(
            run_dir, config, data_health, market_context,
            reason=f"Market context check failed: {market_context.get('kill_reason', 'Unknown')}"
        )

    # Kill switch 2b: Data/regime multiplier kills sizing (fail-closed)
    if combined_multiplier <= 0:
        return create_no_trade_decision(
            run_dir, config, data_health, market_context,
            reason=f"Risk sizing disabled (data_multiplier={dq_multiplier:.2f}, regime_multiplier={regime_multiplier:.2f})"
        )

    # Kill switch 2c: Portfolio already beyond limits
    portfolio_status = position_manager.get_portfolio_status(data_quality_multiplier=combined_multiplier)
    if not portfolio_status.within_limits:
        return create_no_trade_decision(
            run_dir, config, data_health, market_context,
            reason="Portfolio limits exceeded (heat/sector exposure)"
        )

    # Kill switch 3: No tradeable candidates
    tradeable = [c for c in candidates if not c.get('should_skip', True)]
    if not tradeable:
        return create_no_trade_decision(
            run_dir, config, data_health, market_context,
            reason="No tradeable candidates found"
        )

    # Kill switch 4: No candidates meet minimum conviction
    min_conviction = config['conviction']['min_for_trade']
    qualified = [
        c for c in tradeable
        if c.get('conviction', 0) >= min_conviction
        and c.get('signal') in ('BUY', 'STRONG_BUY')
    ]

    if not qualified:
        return create_no_trade_decision(
            run_dir, config, data_health, market_context,
            reason=f"No candidates meet minimum conviction ({min_conviction})"
        )

    # =========================================================================
    # SELECT BEST CANDIDATE (Deterministic - by conviction, then R:R)
    # =========================================================================

    # Sort by conviction (primary) and R:R ratio (secondary)
    qualified.sort(
        key=lambda x: (
            x.get('conviction', 0),
            x.get('setup', {}).get('rr_ratio', 0),
            x.get('symbol', '')
        ),
        reverse=True
    )

    # Portfolio-aware selection: first candidate that passes portfolio gates + sizing
    best = None
    best_sizing = None
    rejected: List[Dict[str, str]] = []
    rejected_diagnostics: List[Dict[str, Any]] = []

    costs = config.get("execution_costs", {}) or {}
    cost_bps = float(costs.get("round_trip_bps", 0)) + float(costs.get("slippage_bps", 0))
    min_net_rr = float((config.get("execution_rules") or {}).get("min_net_rr", 1.5))

    event_cfg = config.get("event_risk", {}) or {}
    unknown_earnings_multiplier = float(event_cfg.get("unknown_earnings_multiplier", 0.7))
    fundamentals_cfg = config.get("fundamentals", {}) or {}
    unknown_fundamentals_multiplier = float(fundamentals_cfg.get("unknown_multiplier", 0.8))

    best_meta: Dict[str, Any] = {}
    best_gap: Dict[str, Any] = {}

    for candidate in qualified:
        symbol = candidate.get("symbol")
        sector = candidate.get("sector") or "Unknown"

        meta = meta_by_symbol.get(symbol) if symbol else None
        if isinstance(meta, dict):
            earnings = meta.get("earnings") or {}
            fundamentals = meta.get("fundamentals") or {}
        else:
            earnings = {"status": "UNKNOWN", "multiplier": unknown_earnings_multiplier}
            fundamentals = {"status": "UNKNOWN", "multiplier": unknown_fundamentals_multiplier}

        # Hard blocks: earnings blackout or fundamentals multiplier 0
        if earnings.get("status") == "BLOCK":
            reason = f"Earnings blackout ({earnings.get('days_to')} days)"
            rejected.append({"symbol": symbol, "reason": reason})
            rejected_diagnostics.append(
                {
                    "symbol": symbol,
                    "sector": sector,
                    "signal": candidate.get("signal"),
                    "conviction": candidate.get("conviction", 0),
                    "grade": candidate.get("grade"),
                    "reason": reason,
                }
            )
            continue
        if fundamentals.get("multiplier") == 0.0 or fundamentals.get("grade") == "D":
            reason = f"Fundamentals blocked ({fundamentals.get('grade')})"
            rejected.append({"symbol": symbol, "reason": reason})
            rejected_diagnostics.append(
                {
                    "symbol": symbol,
                    "sector": sector,
                    "signal": candidate.get("signal"),
                    "conviction": candidate.get("conviction", 0),
                    "grade": candidate.get("grade"),
                    "reason": reason,
                }
            )
            continue

        can_take, reason = position_manager.can_take_new_position(
            sector=sector,
            data_quality_multiplier=combined_multiplier,
        )
        if not can_take:
            rejected.append({"symbol": symbol, "reason": reason})
            rejected_diagnostics.append(
                {
                    "symbol": symbol,
                    "sector": sector,
                    "signal": candidate.get("signal"),
                    "conviction": candidate.get("conviction", 0),
                    "grade": candidate.get("grade"),
                    "reason": reason,
                }
            )
            continue

        setup = candidate.get("setup") or {}
        entry = float(setup.get("entry", 0))
        stop_loss = float(setup.get("stop_loss", 0))
        target1 = float(setup.get("target1", 0))
        rr_ratio = float(setup.get("rr_ratio", 0.0) or 0.0)

        if entry <= 0 or stop_loss <= 0 or entry <= stop_loss:
            reason = "Invalid setup (entry/stop)"
            rejected.append({"symbol": symbol, "reason": reason})
            rejected_diagnostics.append(
                {
                    "symbol": symbol,
                    "sector": sector,
                    "signal": candidate.get("signal"),
                    "conviction": candidate.get("conviction", 0),
                    "grade": candidate.get("grade"),
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "target1": target1,
                    "rr_ratio": rr_ratio,
                    "reason": reason,
                }
            )
            continue

        df = _load_snapshot_df(run_dir, symbol)
        gap95 = _gap_95pct(df)
        gap_buffer = entry * (gap95 / 100.0) if gap95 > 0 else 0.0
        base_risk_per_share = abs(entry - stop_loss)
        risk_per_share = float(max(base_risk_per_share, gap_buffer))

        # Net R:R (after conservative execution costs)
        cost_per_share = entry * (cost_bps / 10000.0) if cost_bps > 0 else 0.0
        net_reward = max(0.0, (target1 - entry) - cost_per_share)
        net_risk = risk_per_share + cost_per_share
        net_rr = (net_reward / net_risk) if net_risk > 0 else 0.0
        if net_rr < min_net_rr:
            reason = f"Net R:R too low ({net_rr:.2f} < {min_net_rr:.2f})"
            rejected.append({"symbol": symbol, "reason": reason})
            rejected_diagnostics.append(
                {
                    "symbol": symbol,
                    "sector": sector,
                    "signal": candidate.get("signal"),
                    "conviction": candidate.get("conviction", 0),
                    "grade": candidate.get("grade"),
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "target1": target1,
                    "rr_ratio": rr_ratio,
                    "gap_95pct": round(float(gap95), 3),
                    "risk_per_share_used": round(float(risk_per_share), 4),
                    "cost_bps": round(float(cost_bps), 2),
                    "cost_per_share": round(float(cost_per_share), 4),
                    "net_rr": round(float(net_rr), 3),
                    "min_net_rr": round(float(min_net_rr), 3),
                    "reason": reason,
                }
            )
            continue

        earnings_mult = float(earnings.get("multiplier", unknown_earnings_multiplier))
        fundamentals_mult = float(fundamentals.get("multiplier", unknown_fundamentals_multiplier))
        meta_multiplier = max(0.0, earnings_mult * fundamentals_mult)

        sizing = position_manager.calculate_position_size(
            entry_price=entry,
            stop_loss=stop_loss,
            conviction_level=candidate.get("grade", "B"),
            data_quality_multiplier=combined_multiplier,
            risk_by_conviction=risk_by_conviction,
            risk_per_share_override=risk_per_share,
            risk_multiplier=meta_multiplier,
        )
        if not sizing.get("can_trade", False):
            reason = sizing.get("reason", "Sizing rejected")
            rejected.append({"symbol": symbol, "reason": reason})
            rejected_diagnostics.append(
                {
                    "symbol": symbol,
                    "sector": sector,
                    "signal": candidate.get("signal"),
                    "conviction": candidate.get("conviction", 0),
                    "grade": candidate.get("grade"),
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "target1": target1,
                    "rr_ratio": rr_ratio,
                    "gap_95pct": round(float(gap95), 3),
                    "risk_per_share_used": round(float(risk_per_share), 4),
                    "cost_bps": round(float(cost_bps), 2),
                    "cost_per_share": round(float(cost_per_share), 4),
                    "net_rr": round(float(net_rr), 3),
                    "min_net_rr": round(float(min_net_rr), 3),
                    "risk_pct": round(float(sizing.get("risk_pct", 0.0) or 0.0), 3),
                    "shares": int(sizing.get("shares", 0) or 0),
                    "position_value": round(float(sizing.get("value", 0.0) or 0.0), 2),
                    "reason": reason,
                }
            )
            continue

        best = candidate
        best_sizing = sizing
        best_meta = {
            "earnings": earnings,
            "fundamentals": fundamentals,
            "meta_multiplier": meta_multiplier,
        }
        best_gap = {
            "gap_95pct": gap95,
            "base_risk_per_share": base_risk_per_share,
            "gap_buffer_per_share": gap_buffer,
            "risk_per_share_used": risk_per_share,
            "cost_bps": cost_bps,
            "cost_per_share": cost_per_share,
            "net_rr": net_rr,
            "min_net_rr": min_net_rr,
        }
        break

    if not best or not best_sizing:
        # Provide a deterministic "watchlist" even if no trade is allowed.
        watchlist_n = int((config.get("execution_rules") or {}).get("watchlist_top_n", 5))
        watchlist: List[Dict[str, Any]] = []
        if rejected_diagnostics:
            # Keep ordering aligned with the candidate selection ordering.
            diag_by_symbol = {d.get("symbol"): d for d in rejected_diagnostics if d.get("symbol")}
            ordered_symbols = [c.get("symbol") for c in qualified if c.get("symbol")]
            for sym in ordered_symbols:
                if sym in diag_by_symbol:
                    watchlist.append(diag_by_symbol[sym])
                if len(watchlist) >= watchlist_n:
                    break

        reason = "No candidate passes portfolio/sizing gates"
        if rejected:
            reason = f"{reason} (top reject: {rejected[0]['symbol']} - {rejected[0]['reason']})"
        return create_no_trade_decision(
            run_dir,
            config,
            data_health,
            market_context,
            reason=reason,
            watchlist=watchlist if watchlist else None,
            execution_assumptions={
                "cost_bps": round(float(cost_bps), 2),
                "min_net_rr": round(float(min_net_rr), 3),
                "gap_rule": "risk_per_share = max(|entry-stop|, entry*gap95%)",
            }
            if watchlist
            else None,
        )

    # =========================================================================
    # POSITION SIZE (Deterministic, portfolio-aware)
    # =========================================================================

    grade = best.get("grade", "C")

    setup = best.get("setup", {}) or {}
    entry = float(setup.get("entry", 0))
    stop_loss = float(setup.get("stop_loss", 0))

    shares = int(best_sizing["shares"])
    position_value = float(best_sizing["value"])
    risk_amount = float(best_sizing["risk_amount"])
    adjusted_risk_pct = float(best_sizing["risk_pct"])

    # =========================================================================
    # BUILD EXECUTION RULES (Deterministic)
    # =========================================================================

    exec_rules = config['execution_rules']

    entry_type = setup.get('entry_type', 'market')

    if entry_type == 'breakout':
        # Breakout entry: trigger above yesterday's high
        entry_rules = {
            'type': 'limit_above_trigger',
            'trigger': entry,
            'limit': round(entry * 1.002, 2),  # 0.2% above trigger
            'valid_until_hours': exec_rules['entry_valid_until_hours'],
            'chase_limit': round(entry * (1 + exec_rules['chase_limit_pct'] / 100), 2),
            'notes': f"Buy only if price crosses {entry}. Do not chase above chase_limit."
        }
    else:
        # Market entry
        entry_rules = {
            'type': 'market_at_open',
            'target_price': entry,
            'limit': round(entry * 1.005, 2),  # 0.5% slippage allowed
            'valid_until_hours': exec_rules['entry_valid_until_hours'],
            'chase_limit': round(entry * (1 + exec_rules['chase_limit_pct'] / 100), 2),
            'notes': f"Enter at market open near {entry}. Do not chase above chase_limit."
        }

    # Gap rules
    gap_rules = {
        'max_gap_up_pct': exec_rules['gap_up_max_pct'],
        'max_gap_down_pct': exec_rules['gap_down_max_pct'],
        'gap_up_invalidation': round(entry * (1 + exec_rules['gap_up_max_pct'] / 100), 2),
        'gap_down_invalidation': round(entry * (1 - exec_rules['gap_down_max_pct'] / 100), 2),
        'action_if_exceeded': 'SKIP',
        'notes': f"Skip if opens >{exec_rules['gap_up_max_pct']}% above or >{exec_rules['gap_down_max_pct']}% below entry."
    }

    # Overnight risk
    overnight_gap_pct = exec_rules['overnight_gap_assumption_pct']
    overnight_risk = shares * entry * (overnight_gap_pct / 100)

    overnight_rules = {
        'worst_case_gap_pct': overnight_gap_pct,
        'worst_case_loss': round(overnight_risk, 2),
        'notes': f"If holding overnight, assume {overnight_gap_pct}% gap risk."
    }

    # =========================================================================
    # BUILD DECISION (THE SACRED OUTPUT)
    # =========================================================================

    decision = {
        'action': best.get('signal', 'HOLD'),
        'symbol': best['symbol'],
        'conviction': best.get('conviction', 0),
        'grade': grade,

        'entry': entry,
        'stop_loss': stop_loss,
        'target1': setup.get('target1', 0),
        'target2': setup.get('target2', 0),

        'shares': shares,
        'position_value': round(position_value, 2),
        'risk_amount': round(risk_amount, 2),
        'risk_pct': round(adjusted_risk_pct, 3),
        'meta_gates': best_meta,
        'gap_risk': best_gap,

        'portfolio': {
            'capital': capital,
            'current_heat_pct': round(portfolio_status.current_heat, 2),
            'heat_available_pct': round(portfolio_status.heat_available, 2),
            'projected_heat_pct': round(portfolio_status.current_heat + adjusted_risk_pct, 2),
            'projected_heat_available_pct': round(max(0.0, portfolio_status.heat_available - adjusted_risk_pct), 2),
            'positions': portfolio_status.total_positions,
            'positions_by_sector': portfolio_status.positions_by_sector,
            'warnings': portfolio_status.warnings,
            'multiplier': {
                'data_quality': round(dq_multiplier, 3),
                'regime': round(regime_multiplier, 3),
                'breadth': round(breadth_multiplier, 3),
                'position_size': round(position_size_multiplier, 3),
                'combined': round(combined_multiplier, 3),
            },
        },

        'entry_rules': entry_rules,
        'gap_rules': gap_rules,
        'overnight_rules': overnight_rules,

        'stop_rules': {
            'initial_stop': stop_loss,
            'stop_type': 'hard',
            'notes': f"Hard stop at {stop_loss}. No mental stops. Exit immediately if hit."
        },

        'reasoning': {
            'votes': best.get('votes', {}),
            'bullish_votes': best.get('bullish_votes', 0),
            'technicals': best.get('technicals', {}),
            'meta': best.get('meta', {}),
            'regime': market_context.get('regime'),
            'regime_multiplier': regime_multiplier,
            'breadth_multiplier': breadth_multiplier,
            'position_size_multiplier': position_size_multiplier,
            'data_quality_multiplier': dq_multiplier,
            'combined_multiplier': combined_multiplier
        },

        'alternatives': [
            {'symbol': c['symbol'], 'conviction': c['conviction'], 'grade': c.get('grade', 'D')}
            for c in qualified[1:4]  # Next 3 best candidates
        ],

        'gates_passed': [
            'data_health',
            'market_regime',
            'min_conviction',
            'portfolio_limits',
            'position_sizing'
        ],

        'gates_failed': [],
        'rejected_candidates': rejected[:10],
    }

    # =========================================================================
    # CREATE MANIFEST (Pins everything for reproducibility)
    # =========================================================================

    manifest = {
        'run_id': run_dir.name,
        'asof_date': data_health.get('last_trading_day'),

        'code_version': get_git_info(),

        'config': {
            'min_conviction': config['conviction']['min_for_trade'],
            'risk_limits': config['risk_limits'],
            'execution_rules': config['execution_rules'],
            'regime_multipliers': config['regime_multipliers'],
            'portfolio': config.get('portfolio', {}),
        },

        'input_hashes': {
            'trading_config.json': compute_file_hash(config_path),
            'data_health.json': compute_file_hash(data_health_path),
            'market_context.json': compute_file_hash(market_context_path),
            'candidates.json': compute_file_hash(candidates_path),
            'symbol_meta.json': compute_file_hash(symbol_meta_path),
            'internals.json': compute_file_hash(run_dir / "internals.json"),
            'sector_strength.json': compute_file_hash(run_dir / "sector_strength.json"),
            'positions_snapshot.json': compute_file_hash(positions_snapshot_path),
        },

        'decision_summary': {
            'action': decision['action'],
            'symbol': decision['symbol'],
            'conviction': decision['conviction']
        }
    }

    # =========================================================================
    # SAVE OUTPUTS
    # =========================================================================

    decision_path = run_dir / "decision.json"
    with open(decision_path, 'w') as f:
        json.dump(decision, f, indent=2)

    manifest_path = run_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Add decision hash to manifest
    manifest['output_hashes'] = {
        'decision.json': compute_file_hash(decision_path)
    }
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"DECISION: {decision['action']} {decision['symbol']}")
    print(f"{'='*60}")
    print(f"  Conviction: {decision['conviction']}/100 ({decision['grade']})")
    print(f"  Entry: ₹{decision['entry']:,.2f}")
    print(f"  Stop Loss: ₹{decision['stop_loss']:,.2f}")
    print(f"  Target 1: ₹{decision['target1']:,.2f}")
    print(f"  Target 2: ₹{decision['target2']:,.2f}")
    print(f"  Shares: {decision['shares']}")
    print(f"  Position Value: ₹{decision['position_value']:,.2f}")
    print(f"  Risk Amount: ₹{decision['risk_amount']:,.2f} ({decision['risk_pct']:.2f}%)")
    print(f"{'='*60}")

    return decision


def create_no_trade_decision(
    run_dir: Path,
    config: dict,
    data_health: dict,
    market_context: dict,
    reason: str,
    watchlist: Optional[List[Dict[str, Any]]] = None,
    execution_assumptions: Optional[Dict[str, Any]] = None,
) -> dict:
    """Create a NO_TRADE decision with proper documentation."""

    # Include portfolio state for audit, even on NO_TRADE
    try:
        capital = _get_capital(config)
        limits = PortfolioRiskLimits(
            max_portfolio_heat=float(config["risk_limits"]["max_portfolio_heat_pct"]),
            max_position_pct=float(config["risk_limits"]["max_single_position_pct"]),
            max_sector_pct=float(config["risk_limits"]["max_sector_exposure_pct"]),
            max_positions_per_sector=int(config["risk_limits"]["max_correlated_positions"]),
            min_liquidity_cr=float(config["risk_limits"]["min_liquidity_cr"]),
        )
        pm = PositionManager(capital=capital, limits=limits)
        regime_multiplier = float(market_context.get("regime_multiplier", 0.5))
        dq_multiplier = _data_quality_multiplier(data_health)
        combined_multiplier = dq_multiplier * regime_multiplier
        portfolio_status = pm.get_portfolio_status(data_quality_multiplier=combined_multiplier)
        portfolio_block = {
            "capital": capital,
            "current_heat_pct": round(portfolio_status.current_heat, 2),
            "heat_available_pct": round(portfolio_status.heat_available, 2),
            "positions": portfolio_status.total_positions,
            "positions_by_sector": portfolio_status.positions_by_sector,
            "warnings": portfolio_status.warnings,
            "multiplier": {
                "data_quality": round(dq_multiplier, 3),
                "regime": round(regime_multiplier, 3),
                "combined": round(combined_multiplier, 3),
            },
        }
    except Exception:
        portfolio_block = None

    decision = {
        'action': 'NO_TRADE',
        'symbol': None,
        'conviction': 0,
        'grade': None,

        'entry': 0,
        'stop_loss': 0,
        'target1': 0,
        'target2': 0,

        'shares': 0,
        'position_value': 0,
        'risk_amount': 0,
        'risk_pct': 0,

        'reason': reason,
        'portfolio': portfolio_block,

        'reasoning': {
            'data_health': data_health.get('can_proceed', False),
            'market_regime': market_context.get('should_trade', False),
            'regime': market_context.get('regime'),
            'kill_reason': reason
        },

        'gates_passed': [],
        'gates_failed': [reason]
    }

    if watchlist:
        decision["watchlist"] = watchlist
    if execution_assumptions:
        decision["execution_assumptions"] = execution_assumptions

    # Create manifest
    config_path = PROJECT_ROOT / "config" / "trading_config.json"

    manifest = {
        'run_id': run_dir.name,
        'asof_date': data_health.get('last_trading_day'),
        'code_version': get_git_info(),
        'config': {
            'min_conviction': config['conviction']['min_for_trade'],
            'risk_limits': config['risk_limits'],
            'portfolio': config.get('portfolio', {}),
        },
        'input_hashes': {
            'trading_config.json': compute_file_hash(config_path),
            'data_health.json': compute_file_hash(run_dir / "data_health.json"),
            'market_context.json': compute_file_hash(run_dir / "market_context.json"),
            'candidates.json': compute_file_hash(run_dir / "candidates.json"),
            'positions_snapshot.json': compute_file_hash(run_dir / "positions_snapshot.json"),
        },
        'decision_summary': {
            'action': 'NO_TRADE',
            'reason': reason
        }
    }

    # Save outputs
    decision_path = run_dir / "decision.json"
    with open(decision_path, 'w') as f:
        json.dump(decision, f, indent=2)

    manifest['output_hashes'] = {
        'decision.json': compute_file_hash(decision_path)
    }

    manifest_path = run_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*60}")
    print(f"DECISION: NO_TRADE")
    print(f"{'='*60}")
    print(f"  Reason: {reason}")
    print(f"{'='*60}")

    return decision


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python make_decision.py <run_dir>")
        print("Example: python make_decision.py journal/runs/2026-01-17_0830")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    # Check required inputs exist
    required = ['data_health.json', 'market_context.json', 'candidates.json']
    for req in required:
        if not (run_dir / req).exists():
            print(f"Error: {req} not found. Run previous stages first.")
            sys.exit(1)

    decision = make_decision(run_dir)

    # Exit with appropriate code
    if decision['action'] == 'NO_TRADE':
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
