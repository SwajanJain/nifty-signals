# /news [STOCK] - Stock News Analysis

Search for recent news about the specified stock.

**Queries to run:**
- "[STOCK] stock news today"
- "[STOCK] quarterly results 2026"
- "[STOCK] analyst rating"

**Check for:**
1. **Earnings** - Any upcoming results? Recent results beat/miss?
2. **Management** - CEO/CFO changes? Board reshuffles?
3. **Business** - Order wins? New contracts? Expansions?
4. **Ratings** - Analyst upgrades/downgrades?
5. **Red Flags** - Fraud? Regulatory issues? Promoter selling?

**Output format:**
```
## News Analysis: [STOCK] - [DATE]

### Recent Headlines
- [headline 1] - [source]
- [headline 2] - [source]

### Key Events
| Event | Impact | Date |
|-------|--------|------|
| [X] | 🟢/🔴 | [X] |

### Earnings
- Next results: [DATE]
- Last quarter: Beat/Miss by X%

### Analyst View
- Consensus: BUY/HOLD/SELL
- Target: ₹X

### Red Flags
- ⚠️ [if any] or ✅ None found

### Verdict
NEWS SUPPORTS TRADE / NEWS IS NEUTRAL / NEWS BLOCKS TRADE
```
