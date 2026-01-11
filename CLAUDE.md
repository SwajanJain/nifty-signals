# Nifty Signals - Legendary Trading System

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MASTER SIGNAL ORCHESTRATOR                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      1. CONTEXT LAYER                                │   │
│  │   Global Macro ─── Market Regime ─── Sector Strength                 │   │
│  │   (US, Asia, VIX)  (Bull/Bear/Crash) (Relative Strength)             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────▼───────────────────────────────────┐   │
│  │                      2. SIGNAL LAYER                                 │   │
│  │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐           │   │
│  │   │ Momentum │ │ Breakout │ │  Trend   │ │    Mean      │           │   │
│  │   │  Model   │ │  Model   │ │ Following│ │  Reversion   │           │   │
│  │   └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘           │   │
│  │        └────────────┴────────────┴──────────────┘                    │   │
│  │                          │                                           │   │
│  │                   ENSEMBLE VOTING                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────▼───────────────────────────────────┐   │
│  │                      3. CONVICTION LAYER                             │   │
│  │   Technical ── Confluence ── Context ── Sector ── Timing            │   │
│  │   (0-25)       (0-20)       (0-20)     (0-15)    (0-10)              │   │
│  │                          │                                           │   │
│  │              Conviction Score (0-100) → Level (A/B/C/D)              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────▼───────────────────────────────────┐   │
│  │                      4. RISK LAYER                                   │   │
│  │   Portfolio Heat ─── Correlation ─── Liquidity ─── Drawdown          │   │
│  │   (Max 6%)          (Max 3/sector)  (Min 10Cr ADV) (Scale down)      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────▼───────────────────────────────────┐   │
│  │                      5. EXECUTION LAYER                              │   │
│  │   Entry ─── Stop Loss ─── Targets ─── Position Size ─── Exit Rules   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python3 main.py scan` | Basic technical scan |
| `python3 main.py enhanced-scan` | Full enhanced scan with all features |
| `python3 main.py regime` | Market regime analysis |
| `python3 main.py sectors` | Sector relative strength |
| `python3 main.py analyze STOCK` | Basic stock analysis |
| `python3 main.py analyze-enhanced STOCK` | Enhanced stock analysis |

## User Commands

| Command | Action |
|---------|--------|
| `trade` or `daily` | Full orchestrated trading analysis |
| `macro` or `regime` | Market regime + global context |
| `scan` | Enhanced multi-model scan |
| `sectors` | Sector strength ranking |
| `analyze STOCK` | Enhanced stock analysis |

---

## /trade - Master Orchestrator

### Flow
1. **Context First** - Fetch global + domestic + sector data
2. **Regime Check** - If CRASH/STRONG_BEAR → Recommend cash
3. **Signal Generation** - Multi-model ensemble voting
4. **Conviction Scoring** - Filter by conviction (min 40/100)
5. **Risk Checks** - Portfolio limits, correlation, liquidity
6. **Final Decision** - With full reasoning and audit trail

### Context Layer (Run in Parallel)

**Agent 1 - Global:**
```bash
python3 main.py regime  # Includes global data
```

**Agent 2 - Sectors:**
```bash
python3 main.py sectors
```

**Agent 3 - Scan:**
```bash
python3 main.py enhanced-scan --top 5
```

### Output Format

```markdown
# Trading Signal - [DATE]

## MARKET CONTEXT
- Global: [RISK_ON/OFF] | Risk Score: [X]/5
- Regime: [NAME] | Should Trade: [YES/NO]
- Position Size: [X]% of normal
- Top Sectors: [LIST]

## TOP PICK: [SYMBOL] ₹[PRICE]

### Conviction: [A/B/C] ([X]/100)
| Component | Score |
|-----------|-------|
| Technical | [X]/25 |
| Confluence | [X]/20 |
| Context | [X]/20 |
| Sector | [X]/15 |
| Timing | [X]/10 |

### Trade Setup
- Entry: ₹[X]
- Stop: ₹[X] ([X]%)
- T1: ₹[X] (+[X]%)
- T2: ₹[X] (+[X]%)
- Position: [X] shares (₹[X])
- Risk: ₹[X] ([X]% of capital)

### Model Votes
- [✓/✗] Momentum: [reason]
- [✓/✗] Breakout: [reason]
- [✓/✗] TrendFollowing: [reason]
- [✓/✗] MeanReversion: [reason]
```

---

## Key Principles (From Legends)

### Jim Simons (Renaissance)
- Multiple independent models
- Ensemble voting, not single signal
- Statistical edge over gut feeling

### Ray Dalio (Bridgewater)
- Risk parity - correlation-aware sizing
- Systematic principles
- Regime-aware allocation

### Stanley Druckenmiller
- Conviction-based sizing (A = 2%, C = 0.5%)
- Concentrate when right
- Cut fast when wrong

### Paul Tudor Jones
- Defense first - never blow up
- Global macro awareness
- Position sizing based on conviction

### Ed Seykota
- Trend following with judgment
- Let winners run
- Cut losers short

---

## Conviction Levels & Risk

| Level | Score | Risk/Trade | When |
|-------|-------|------------|------|
| A+ | 85+ | 2.5% | Exceptional - all factors aligned |
| A | 70+ | 2.0% | High conviction |
| B | 55+ | 1.0% | Standard setup |
| C | 40+ | 0.5% | Lower conviction |
| D | <40 | 0% | No trade |

---

## Risk Rules

1. **Portfolio Heat** - Max 6% total risk
2. **Single Position** - Max 15% of capital
3. **Sector Exposure** - Max 30% per sector
4. **Correlated Positions** - Max 3 per sector
5. **Liquidity** - Min 10 Cr ADV
6. **Position Cap** - Max 2% of ADV
7. **Drawdown Scaling** - Reduce size after 5% drawdown

---

## Regime Actions

| Regime | Action | Position Size |
|--------|--------|---------------|
| STRONG_BULL | Aggressive longs, breakouts | 100% |
| BULL | Normal longs, pullback entries | 80% |
| NEUTRAL | Reduced size, mean reversion | 50% |
| BEAR | Defensive, quick profits | 30% |
| STRONG_BEAR | Mostly cash | 20% |
| CRASH | 100% cash | 0% |

---

## Files Structure

```
nifty-signals/
├── core/
│   ├── orchestrator.py    # Master decision engine
│   ├── conviction.py      # Conviction scoring
│   └── context.py         # Global + domestic context
├── models/
│   ├── ensemble.py        # Multi-model voting
│   ├── momentum.py        # Momentum model
│   ├── breakout.py        # Breakout model
│   ├── trend_following.py # Trend following model
│   └── mean_reversion.py  # Mean reversion model
├── indicators/
│   ├── market_regime.py   # Regime detection
│   ├── multi_timeframe.py # MTF alignment
│   ├── sector_strength.py # Sector RS
│   └── [other indicators]
├── risk/
│   ├── position_sizing.py # ATR-based sizing
│   └── exit_strategy.py   # Exit rules
├── backtest/
│   ├── engine.py          # Backtest engine
│   └── metrics.py         # Performance metrics
└── signals/
    ├── generator.py       # Basic generator
    └── enhanced_generator.py # Enhanced with all features
```

---

## Quick Reference

### Daily Workflow
1. Run `/trade` or `trade`
2. Check regime - if bearish, stay cash
3. Review top pick conviction score
4. Verify news doesn't disqualify
5. Execute if conviction ≥ B

### Emergency Rules
- VIX > 20: Half position size
- Regime = CRASH: No new trades
- Earnings in 3 days: Skip stock
- FII selling > 2000 Cr: Reduce exposure
