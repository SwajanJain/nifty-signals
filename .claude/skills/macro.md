# /macro - Market Macro Analysis

Search and summarize current market conditions:

1. **Search these queries:**
   - "Indian stock market today Nifty Sensex"
   - "FII DII data India today"
   - "US stock market overnight"
   - "India VIX today"
   - "SGX Nifty"

2. **Return structured data:**
   ```
   ## Macro Snapshot - [DATE/TIME]

   | Indicator | Value | Signal |
   |-----------|-------|--------|
   | Nifty | [level] ([%]) | 🟢/🔴 |
   | Sensex | [level] ([%]) | 🟢/🔴 |
   | FII | ₹[X] Cr | Buying/Selling |
   | DII | ₹[X] Cr | Buying/Selling |
   | VIX | [X] | Low(<12)/Med(12-18)/High(>18) |
   | SGX Nifty | [level] | Gap Up/Down |
   | US (S&P) | [%] | 🟢/🔴 |

   **Bias:** BULLISH / BEARISH / NEUTRAL
   **Risk Level:** LOW / MEDIUM / HIGH
   ```

3. **Include sources as markdown links**
