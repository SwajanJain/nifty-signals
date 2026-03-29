"""Nifty Signals — Streamlit Dashboard.

Run with: streamlit run dashboard/app.py

4 tabs:
  1. Dashboard — Market regime, breadth, FII/DII overview
  2. Scan — Run piped scans interactively
  3. Fundamentals — Single stock fundamental analysis
  4. Portfolio — Position risk, VaR, correlations
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd


st.set_page_config(
    page_title="Nifty Signals",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Nifty Signals Dashboard")


# ---------------------------------------------------------------------------
# Tab setup
# ---------------------------------------------------------------------------

tab_dashboard, tab_scan, tab_fundamentals, tab_portfolio = st.tabs([
    "🏠 Dashboard", "🔍 Scan", "📊 Fundamentals", "💼 Portfolio Risk"
])


# ---------------------------------------------------------------------------
# Tab 1: Dashboard
# ---------------------------------------------------------------------------

with tab_dashboard:
    st.header("Market Overview")

    col1, col2, col3 = st.columns(3)

    # Regime
    with col1:
        st.subheader("Market Regime")
        if st.button("Refresh Regime", key="regime_btn"):
            with st.spinner("Analyzing regime..."):
                try:
                    from indicators.market_regime import MarketRegimeDetector
                    from data.fetcher import StockDataFetcher

                    fetcher = StockDataFetcher()
                    nifty_df = fetcher.fetch_stock_data("^NSEI", "daily")
                    if nifty_df is not None:
                        detector = MarketRegimeDetector()
                        regime = detector.detect_regime(nifty_df)
                        st.metric("Regime", regime.get('regime', 'UNKNOWN'))
                        st.metric("Should Trade", "YES" if regime.get('should_trade', True) else "NO")
                        st.metric("Position Multiplier", f"{regime.get('position_multiplier', 1.0):.1f}x")
                    else:
                        st.warning("Could not fetch Nifty data")
                except Exception as e:
                    st.error(f"Regime detection failed: {e}")
        else:
            st.info("Click 'Refresh Regime' to load market data")

    # Breadth
    with col2:
        st.subheader("Market Breadth")
        if st.button("Calculate Breadth", key="breadth_btn"):
            with st.spinner("Calculating breadth (this may take a minute)..."):
                try:
                    from data.market_breadth import calculate_market_breadth
                    result = calculate_market_breadth()
                    metrics = result.get('metrics', {})
                    st.metric("% Above EMA20", f"{metrics.get('pct_above_ema20', 0):.1f}%")
                    st.metric("% Above EMA50", f"{metrics.get('pct_above_ema50', 0):.1f}%")
                    st.metric("A/D Ratio", f"{metrics.get('ad_ratio', 0):.2f}")
                    analysis = result.get('analysis', {})
                    st.metric("Breadth Signal", analysis.get('breadth_signal', 'N/A'))
                except Exception as e:
                    st.error(f"Breadth calculation failed: {e}")
        else:
            st.info("Click 'Calculate Breadth' to analyze")

    # FII/DII
    with col3:
        st.subheader("FII/DII Flow")
        if st.button("Fetch FII/DII", key="fii_btn"):
            with st.spinner("Fetching FII/DII data..."):
                try:
                    from data.fii_dii_fetcher import FIIDIIFetcher
                    fetcher = FIIDIIFetcher()
                    data = fetcher.fetch()
                    if data:
                        fii_net = data.get('fii_net', 0)
                        dii_net = data.get('dii_net', 0)
                        color_fii = "normal" if fii_net >= 0 else "inverse"
                        color_dii = "normal" if dii_net >= 0 else "inverse"
                        st.metric("FII Net", f"₹{fii_net:,.0f} Cr", delta_color=color_fii)
                        st.metric("DII Net", f"₹{dii_net:,.0f} Cr", delta_color=color_dii)
                    else:
                        st.warning("FII/DII data unavailable")
                except Exception as e:
                    st.error(f"FII/DII fetch failed: {e}")
        else:
            st.info("Click 'Fetch FII/DII' to load")


# ---------------------------------------------------------------------------
# Tab 2: Scan
# ---------------------------------------------------------------------------

with tab_scan:
    st.header("Piped Scanner")

    col_a, col_b = st.columns([1, 3])

    with col_a:
        scan_strategy = st.selectbox(
            "Strategy",
            ["swing_breakout", "momentum", "narrow_range"],
            index=0,
        )
        scan_top = st.number_input("Top N", min_value=1, max_value=50, value=10)
        run_scan = st.button("Run Scan", key="scan_btn", type="primary")

    with col_b:
        if run_scan:
            with st.spinner(f"Running {scan_strategy} pipe..."):
                try:
                    from signals.piped_scanner import PIPE_REGISTRY
                    from data.fetcher import StockDataFetcher
                    from config import get_nifty100_symbols

                    symbols = get_nifty100_symbols()
                    if not symbols:
                        st.error("No symbols found in stocks.json")
                    else:
                        pipe = PIPE_REGISTRY[scan_strategy]()
                        fetcher = StockDataFetcher()
                        report = pipe.run(symbols, fetcher)

                        # Funnel
                        funnel_data = []
                        for stage in report.stages:
                            funnel_data.append({
                                'Stage': stage.name,
                                'In': stage.input_count,
                                'Out': stage.output_count,
                                'Eliminated': stage.input_count - stage.output_count,
                            })
                        st.subheader("Filter Funnel")
                        st.dataframe(pd.DataFrame(funnel_data), use_container_width=True)

                        # Survivors
                        if report.final_survivors:
                            st.subheader(f"Survivors ({len(report.final_survivors)})")
                            surv_data = []
                            for sym in report.final_survivors[:scan_top]:
                                details = report.details.get(sym, {})
                                surv_data.append({'Symbol': sym, **details})
                            st.dataframe(pd.DataFrame(surv_data), use_container_width=True)
                        else:
                            st.warning("No stocks passed all filters")
                except Exception as e:
                    st.error(f"Scan failed: {e}")
        else:
            st.info("Select a strategy and click 'Run Scan'")


# ---------------------------------------------------------------------------
# Tab 3: Fundamentals
# ---------------------------------------------------------------------------

with tab_fundamentals:
    st.header("Fundamental Analysis")

    symbol = st.text_input("Stock Symbol", value="RELIANCE", key="fund_symbol").upper()

    if st.button("Analyze", key="fund_btn", type="primary"):
        with st.spinner(f"Analyzing {symbol}..."):
            try:
                from fundamentals.screener_fetcher import ScreenerFetcher
                from fundamentals.scorer import ProfileBuilder, FundamentalScorer

                fetcher = ScreenerFetcher()
                raw = fetcher.fetch_stock(symbol)

                if not raw:
                    st.error(f"Could not fetch data for {symbol}")
                else:
                    builder = ProfileBuilder()
                    profile = builder.build(raw)
                    scorer = FundamentalScorer()
                    fs = scorer.score(profile)

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Score", f"{fs.total_score}/100")
                    col2.metric("PE", f"{profile.pe_ratio or 0:.1f}")
                    col3.metric("ROE", f"{profile.roe or 0:.1f}%")
                    col4.metric("D/E", f"{profile.debt_to_equity:.2f}")

                    col5, col6, col7, col8 = st.columns(4)
                    col5.metric("Revenue Growth 3Y", f"{profile.revenue_growth_3y:.1f}%")
                    col6.metric("Profit Growth 3Y", f"{profile.profit_growth_3y:.1f}%")
                    col7.metric("ROCE", f"{profile.roce or 0:.1f}%")
                    col8.metric("Market Cap", f"₹{profile.market_cap_cr:,.0f} Cr")

                    if fs.green_flags:
                        st.success("**Green Flags:** " + " | ".join(fs.green_flags))
                    if fs.red_flags:
                        st.error("**Red Flags:** " + " | ".join(fs.red_flags))

                    # Sub-scores
                    st.subheader("Score Breakdown")
                    scores_df = pd.DataFrame([{
                        'Valuation': fs.valuation_score,
                        'Profitability': fs.profitability_score,
                        'Growth': fs.growth_score,
                        'Financial Health': fs.financial_health_score,
                        'Quality': fs.quality_score,
                    }])
                    st.bar_chart(scores_df.T, horizontal=True)

            except Exception as e:
                st.error(f"Analysis failed: {e}")


# ---------------------------------------------------------------------------
# Tab 4: Portfolio Risk
# ---------------------------------------------------------------------------

with tab_portfolio:
    st.header("Portfolio Risk Analysis")

    stocks_input = st.text_input(
        "Portfolio Symbols (comma-separated)",
        value="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        key="port_stocks",
    )
    capital = st.number_input("Total Capital (₹)", value=500000, step=50000, key="port_capital")

    if st.button("Analyze Risk", key="port_btn", type="primary"):
        symbols = [s.strip().upper() for s in stocks_input.split(",") if s.strip()]
        if len(symbols) < 2:
            st.warning("Enter at least 2 symbols")
        else:
            with st.spinner("Computing portfolio risk..."):
                try:
                    from data.fetcher import StockDataFetcher
                    from risk.portfolio_risk import PortfolioRiskCalculator
                    from config import get_nifty500_stocks

                    fetcher = StockDataFetcher()
                    all_info = get_nifty500_stocks()
                    sector_map = {s['symbol']: s.get('sector', 'Unknown') for s in all_info}
                    per_stock = capital / len(symbols)

                    positions = {}
                    returns_data = {}
                    for sym in symbols:
                        df = fetcher.fetch_stock_data(sym, "daily")
                        if df is not None and len(df) >= 60:
                            returns_data[sym] = df['close'].pct_change().dropna()
                            positions[sym] = {'value': per_stock, 'sector': sector_map.get(sym, 'Unknown')}

                    if len(positions) < 2:
                        st.error("Need data for at least 2 symbols")
                    else:
                        calc = PortfolioRiskCalculator()
                        report = calc.full_report(positions, returns_data)

                        # VaR metrics
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Undiversified VaR", f"{report.var.var_pct}%")
                        col2.metric("Diversified VaR", f"{report.diversified_var.var_pct}%")
                        div_benefit = report.var.var_amount - report.diversified_var.var_amount
                        col3.metric("Diversification Benefit", f"₹{div_benefit:,.0f}")

                        # Individual VaR
                        st.subheader("Individual Position VaR")
                        ind_data = []
                        for sym, v in report.individual_var.items():
                            ind_data.append({
                                'Symbol': sym,
                                'Value': f"₹{positions[sym]['value']:,.0f}",
                                'VaR %': v.var_pct,
                                'VaR ₹': f"₹{v.var_amount:,.0f}",
                                'CVaR %': v.cvar_pct,
                            })
                        st.dataframe(pd.DataFrame(ind_data), use_container_width=True)

                        # Correlation
                        if report.correlation.matrix is not None:
                            st.subheader("Correlation Matrix")
                            st.dataframe(report.correlation.matrix, use_container_width=True)

                        # Stress tests
                        st.subheader("Stress Test Scenarios")
                        stress_data = [{
                            'Scenario': s.scenario,
                            'Loss %': f"{s.portfolio_loss_pct}%",
                            'Loss ₹': f"₹{s.portfolio_loss_amount:,.0f}",
                        } for s in report.stress_tests]
                        st.dataframe(pd.DataFrame(stress_data), use_container_width=True)

                        # Warnings
                        if report.warnings:
                            for w in report.warnings:
                                st.warning(w)

                except Exception as e:
                    st.error(f"Risk analysis failed: {e}")
