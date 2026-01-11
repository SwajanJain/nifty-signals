# /scan - Technical Stock Scanner

Run the nifty-signals technical scanner:

```bash
cd ~/Documents/Projects/nifty-signals
python3 main.py scan --timeframe daily
```

Then for top 3 buy signals, run detailed analysis:
```bash
python3 main.py analyze [SYMBOL1]
python3 main.py analyze [SYMBOL2]
python3 main.py analyze [SYMBOL3]
```

**Output format:**
```
## Technical Scan Results - [DATE]

### Top Buy Signals
| Rank | Stock | Price | Score | Key Signal |
|------|-------|-------|-------|------------|
| 1 | X | ₹X | +X | [reason] |
...

### Top Sell Signals
| Rank | Stock | Price | Score | Key Signal |
|------|-------|-------|-------|------------|
| 1 | X | ₹X | -X | [reason] |
...

### Detailed Analysis: [TOP PICK]
- Entry: ₹X
- Stop Loss: ₹X (-X%)
- Target 1: ₹X (+X%)
- Target 2: ₹X (+X%)
- Key signals: [list]
```
