# /trade - Master Trading Signal Orchestrator

## Architecture

This is the MASTER skill that orchestrates CHILD skills in sequence:

```
/trade (Master)
    │
    ├── Step 1: Context Layer
    │   ├── /global → Global market data
    │   ├── /regime → Market regime
    │   └── /sectors → Sector strength
    │
    ├── Step 2: Signal Layer
    │   └── Enhanced scan with multi-model ensemble
    │
    ├── Step 3: Conviction Layer
    │   └── Score signals, filter by conviction
    │
    └── Step 4: Output
        └── Final recommendations with full reasoning
```

## Execution Flow

### Pre-Check
1. Check if Saturday/Sunday → Market CLOSED
2. Check if market hours (9:15 AM - 3:30 PM IST)
3. Check for major holidays

### Step 1: Context Layer (Run in Parallel)

Launch 3 agents using Task tool IN PARALLEL:

**Agent 1 - Global Context:**
```
subagent_type: Bash
prompt: |
  cd /Users/swajanjain/Documents/Projects/nifty-signals
  python3 -c "
  from core.context import MarketContextBuilder
  builder = MarketContextBuilder()
  global_data = builder.fetch_global_data()
  print(f'Risk Score: {global_data.risk_score}')
  print(f'Sentiment: {global_data.sentiment.value}')
  print(f'US: S&P {global_data.sp500_change:+.1f}% | VIX {global_data.us_vix:.1f}')
  print(f'Asia: Nikkei {global_data.nikkei_change:+.1f}%')
  print(f'Crude: {global_data.crude_change:+.1f}%')
  "
Return: Global risk score, sentiment, key market moves
```

**Agent 2 - Market Regime:**
```
subagent_type: Bash
prompt: cd /Users/swajanjain/Documents/Projects/nifty-signals && python3 main.py regime
Return: Regime name, should trade, position size multiplier
```

**Agent 3 - Sector Analysis:**
```
subagent_type: Bash
prompt: cd /Users/swajanjain/Documents/Projects/nifty-signals && python3 main.py sectors
Return: Top 3 sectors, bottom 3 sectors
```

### Step 2: Signal Layer

Wait for context. If regime says NO TRADE → Stop and recommend cash.

Otherwise, run enhanced scan:
```
subagent_type: Bash
prompt: cd /Users/swajanjain/Documents/Projects/nifty-signals && python3 main.py enhanced-scan --top 5
Return: Top 5 actionable signals with conviction levels
```

### Step 3: News Check

For top 3 signals:
```
subagent_type: Explore
prompt: Search news for [STOCK1], [STOCK2], [STOCK3]. Check:
- Earnings dates
- Management changes
- Analyst ratings
- Red flags
Return: News summary, any disqualifiers
```

### Step 4: Final Output

```markdown
# Trading Signal - [DATE] [TIME]

## MARKET CONTEXT

### Global
- Sentiment: [RISK_ON/RISK_OFF/NEUTRAL]
- Risk Score: [X]/5
- US: S&P [X]% | VIX [X]
- Asia: [Summary]
- Crude: [X]%

### Domestic
- Regime: [REGIME] (Score: [X])
- Should Trade: [YES/NO]
- Position Size: [X]% of normal

### Sectors
- Focus: [TOP 3]
- Avoid: [BOTTOM 3]

---

## TOP PICK: [SYMBOL] ₹[PRICE]

### Decision
- **Signal:** [STRONG_BUY/BUY]
- **Conviction:** [A/B/C] ([X]/100)
- **Confidence:** [HIGH/MEDIUM/LOW]

### Context Alignment
| Factor | Score | Notes |
|--------|-------|-------|
| Technical | [X]/25 | [Key signals] |
| Confluence | [X]/20 | [X] models agree |
| Context | [X]/20 | Regime + MTF |
| Sector | [X]/15 | Rank #[X] |
| Timing | [X]/10 | [Entry quality] |

### Trade Setup
| | Value | % |
|-|-------|---|
| Entry | ₹[X] | - |
| Stop Loss | ₹[X] | [X]% |
| Target 1 | ₹[X] | +[X]% |
| Target 2 | ₹[X] | +[X]% |
| R:R | 1:[X] | - |

### Position Sizing
| | Value |
|-|-------|
| Shares | [X] |
| Value | ₹[X] |
| Risk | ₹[X] ([X]%) |
| Portfolio Heat After | [X]% |

### Why This Trade
1. [Technical reason]
2. [Context/Sector reason]
3. [Timing reason]

### Model Votes
- [✓] Momentum: [REASON]
- [✓] TrendFollowing: [REASON]
- [✓] Breakout: [REASON]
- [ ] MeanReversion: [REASON]

---

## ALTERNATIVE: [SYMBOL2]
Brief: [1-2 line setup]

---

## SKIP TODAY
| Stock | Reason |
|-------|--------|
| [X] | [Weak sector/MTF conflict/Low conviction] |

---

## RISK FACTORS
- [Key risk 1]
- [Key risk 2]

---

## AUDIT TRAIL
- Context fetched: [TIME]
- Signals generated: [TIME]
- Decision made: [TIME]
- Models used: [LIST]
```

## Key Rules

1. **Context First** - Never generate signals without fresh context
2. **Regime Override** - CRASH/STRONG_BEAR = No trades, recommend cash
3. **Conviction Threshold** - Skip anything below 40/100
4. **MTF Required** - Weekly + Daily must align
5. **Sector Matters** - Avoid bottom 3 sectors
6. **News Check** - Can veto any technical signal
7. **Audit Everything** - Every decision has reasoning
