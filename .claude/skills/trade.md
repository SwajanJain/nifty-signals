# /trade - Deterministic Trading Orchestrator (Claude Orchestrates, Code Decides)

This skill runs the **artifact-based deterministic pipeline** and then produces a clear, auditable execution plan.

Claude’s role:
- **Orchestrator**: run scripts, read JSON artifacts, present results.
- **Narrator**: explain *why* the system chose the trade (using the artifacts only).
- **Risk spotter**: optional news/macro checks as **advisory only**.

Claude **must not** change the trade decision produced by `decision.json`.

---

## Run (Preferred)

```bash
cd /Users/swajanjain/Documents/Projects/nifty-signals
python3 scripts/run_pipeline.py
```

This creates: `journal/runs/<run_id>/`

Key outputs:
- `journal/runs/<run_id>/data_health.json`
- `journal/runs/<run_id>/symbol_meta.json` (earnings + fundamentals pinned for the run)
- `journal/runs/<run_id>/internals.json` (market breadth from snapshots)
- `journal/runs/<run_id>/sector_strength.json` (sector RS/rotation from snapshots)
- `journal/runs/<run_id>/market_context.json`
- `journal/runs/<run_id>/candidates.json`
- `journal/runs/<run_id>/data/daily/*.csv` (OHLCV snapshot used by Stage C/E)
- `journal/runs/<run_id>/positions_snapshot.json` (portfolio state pinned for the run)
- `journal/runs/<run_id>/decision.json` (**sacred decision**)
- `journal/runs/<run_id>/review.json` (run diagnostics: skip reasons, top candidates)
- `journal/runs/<run_id>/final.md` (code-generated summary)
- `journal/runs/<run_id>/symbol/*.json` (enrichment for chosen symbol + alternatives)

---

## Capital / Portfolio State (Critical)

- Set capital in `config/trading_config.json` → `portfolio.capital`.
- The decision stage reads current positions from `journal/positions.json` and snapshots it to `journal/runs/<run_id>/positions_snapshot.json`.
- If portfolio heat/sector limits are exceeded, the system returns `NO_TRADE`.

---

## Rules (Non-Negotiable)

1. **Decision is code**: the trade is whatever `journal/runs/<run_id>/decision.json` says.
2. **Fail-closed**: if `data_health.can_proceed=false` or `market_context.should_trade=false`, stop.
3. **No discretionary overrides**: news/macro checks can only produce an explicit “manual veto advisory”; they do not change `decision.json`.

---

## Claude Output (Use Artifacts Only)

Read:
- `journal/runs/<run_id>/decision.json`
- `journal/runs/<run_id>/market_context.json`
- `journal/runs/<run_id>/data_health.json`
- `journal/runs/<run_id>/symbol/<SYMBOL>.json` (if present)

Respond in this structure:

1) **Decision**
- If `NO_TRADE`: quote `decision.reason` and the failing gate(s).
- If `BUY/STRONG_BUY`: summarize symbol, conviction, entry/stop/targets, shares, risk amount, and portfolio heat (current + projected).

2) **Execution Plan**
- Use `decision.entry_rules`, `decision.gap_rules`, `decision.stop_rules`, `decision.overnight_rules`.
- State invalidations (gap rules / chase limit / time window).

3) **Why This Trade (From Data)**
- Use `decision.reasoning` and the chosen symbol entry in `candidates.json`.

4) **Alternatives**
- Use `decision.alternatives` (do not invent symbols).

5) **Advisory Checks (Optional)**
- You may run `/news <SYMBOL>` and `/macro` for context, but treat this as commentary only.

---

## Safety Notes

- This system is designed for **repeatability and auditability**: same run artifacts ⇒ same `decision.json`.
- Execution and updating `journal/positions.json` is outside this pipeline.
