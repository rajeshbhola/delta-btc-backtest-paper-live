"""Offline Streamlit UI for BTC futures fee, slippage and funding scenarios.

Run: python -m streamlit run dashboard.py
No broker connectivity, secrets, or order placement.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from cost_lab.model import Costs, Trade, calculate
from cost_lab.demo import make_demo_trades
from cost_lab.portfolio import load_trades, run_portfolio

st.set_page_config(page_title="BTC Trading Cost Lab", page_icon="📊", layout="wide")
st.title("BTC Futures — Trading Cost Lab")
st.caption("Mini-Project 7 · Delta Exchange India · Simulation only · No orders or API keys")
st.info("USD-equivalent scenario model. INR uses a manually assumed FX rate; actual Delta India margin/settlement is in INR. Fees and funding may differ in real executions.")

with st.sidebar:
    st.header("Trading cost assumptions")
    maker = st.number_input("Maker fee (bps)", min_value=0.0, max_value=100.0, value=2.0, step=0.5)
    taker = st.number_input("Taker fee (bps)", min_value=0.0, max_value=100.0, value=5.0, step=0.5)
    gst = st.number_input("GST on fees (%)", min_value=0.0, max_value=100.0, value=18.0, step=1.0)
    spread = st.number_input("Full bid–ask spread (bps)", min_value=0.0, max_value=100.0, value=2.0, step=0.5)
    slip = st.number_input("Adverse slippage per side (bps)", min_value=0.0, max_value=100.0, value=1.0, step=0.5)
    funding = st.number_input("Assumed signed funding per event (%)", value=0.01, step=0.005, format="%.4f",
                              help="Positive: longs pay shorts; negative: shorts pay longs.")
    fx = st.number_input("Assumed USD to INR (display only)", min_value=1.0, value=85.0, step=0.5)
    leverage = st.number_input("Leverage for margin estimate", min_value=1.0, max_value=200.0, value=2.0, step=1.0)

costs = Costs(maker_fee_bps=maker, taker_fee_bps=taker, gst_pct=gst, spread_bps=spread,
              slippage_bps=slip, funding_rate_pct=funding, fx_usd_inr=fx, leverage=leverage)
one, batch, guide = st.tabs(["Single trade calculator", "Strategy trade comparison", "Learn the model"])

with one:
    st.subheader("Simulate one BTCUSD futures trade")
    a, b, c = st.columns(3)
    with a:
        side = st.selectbox("Trade direction", ["LONG", "SHORT"])
        entry = st.number_input("Reference entry (USD)", min_value=1.0, value=100000.0, step=100.0)
        eorder = st.selectbox("Entry order", ["taker", "maker"])
    with b:
        exit_price = st.number_input("Reference exit (USD)", min_value=1.0, value=101000.0, step=100.0)
        contracts = st.number_input("BTCUSD contracts (1 = 0.001 BTC)", min_value=1, value=10, step=1)
        xorder = st.selectbox("Exit order", ["taker", "maker"])
    with c:
        events = st.number_input("Funding snapshots while open", min_value=0, value=0, step=1)
        st.caption("0 is appropriate when the position does not cross a funding snapshot. Exchange schedules/rates must be verified separately.")
    result = calculate(Trade(side=side, entry_price=entry, exit_price=exit_price, contracts=int(contracts),
                             entry_order=eorder, exit_order=xorder, funding_events=int(events)), costs)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gross reference PnL", f"${result['gross_reference_pnl_usd']:+,.2f}")
    m2.metric("Total signed costs", f"${result['total_costs_usd']:+,.2f}")
    m3.metric("Net estimated PnL", f"${result['net_pnl_usd']:+,.2f}")
    m4.metric("Net PnL in INR (indicative)", f"₹{result['net_pnl_inr_estimate']:+,.2f}")
    st.caption(f"Quantity {result['quantity_btc']:.4f} BTC · Entry fill ${result['modeled_entry_fill_usd']:,.2f} · Exit fill ${result['modeled_exit_fill_usd']:,.2f} · Approx margin ${result['estimated_initial_margin_usd']:,.2f} (fees and reserve not included)")
    data = {"Spread": result["spread_cost_usd"], "Slippage": result["slippage_cost_usd"],
            "Trading fees": result["commission_usd"], "GST": result["gst_usd"],
            "Funding (+paid / −received)": result["funding_paid_usd"]}
    chart = pd.DataFrame({"Cost type": list(data), "USD": list(data.values())})
    st.plotly_chart(px.bar(chart, x="Cost type", y="USD", title="What changed the reference PnL?"), use_container_width=True)
    st.dataframe(pd.DataFrame([{
        "reference_notional_usd": result["reference_notional_usd"],
        "gross_pnl_usd": result["gross_reference_pnl_usd"],
        "spread_cost_usd": result["spread_cost_usd"], "slippage_cost_usd": result["slippage_cost_usd"],
        "entry_commission_usd": result["entry_fee_usd"], "exit_commission_usd": result["exit_fee_usd"],
        "gst_usd": result["gst_usd"], "funding_paid_usd": result["funding_paid_usd"],
        "net_pnl_usd": result["net_pnl_usd"]}]), hide_index=True, use_container_width=True)
    st.download_button("Download calculation JSON", json.dumps(result, indent=2), "trade_cost_calculation.json", "application/json")

with batch:
    st.subheader("Compare gross vs net PnL for historical trades")
    origin = st.radio("Trade data", ["Built-in demo trades", "Project 6 folder or JSON path", "Upload a trade JSON file"], horizontal=True)
    rows = None
    try:
        if origin == "Built-in demo trades":
            rows = make_demo_trades()
            st.caption("Synthetic illustration: 14 long/short trades, not real Bitcoin data.")
        elif origin == "Project 6 folder or JSON path":
            folder = st.text_input("Project 6 results folder or trade file path", "demo_data/trades.json")
            tf = st.selectbox("Timeframe (if selecting Project 6 results folder)", ["1m", "5m", "15m", "1h", "4h"])
            rows = load_trades(folder, timeframe=tf)
        else:
            uploaded = st.file_uploader("Trade JSON array", type=["json"])
            if uploaded is not None:
                rows = json.load(uploaded)
                if not isinstance(rows, list):
                    raise ValueError("Expected JSON array")
        if rows:
            p1, p2, p3 = st.columns(3)
            with p1:
                starting = st.number_input("Simulated starting capital (USD)", min_value=1.0, value=10000.0, step=1000.0)
                sizing = st.selectbox("Contract sizing", ["fixed", "one_x"], help="one_x = whole contracts affordable with current net equity, 1x notional (not leverage)")
            with p2:
                fixed = st.number_input("Contracts per trade (fixed mode)", min_value=1, value=10, step=1)
                batch_entry = st.selectbox("Entry execution type", ["taker", "maker"], key="batch_entry")
            with p3:
                use_funding = st.checkbox("Estimate funding snapshots from timestamps", value=True)
                batch_exit = st.selectbox("Exit execution type", ["taker", "maker"], key="batch_exit")
            portfolio = run_portfolio(rows, costs, capital=starting, sizing=sizing, contracts=int(fixed),
                                      estimate_funding=use_funding, entry_order=batch_entry, exit_order=batch_exit)
            info = portfolio["summary"]
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Trades", info["trade_count"])
            q2.metric("Gross PnL", f"${info['gross_pnl_usd']:+,.2f}")
            q3.metric("Net PnL", f"${info['net_pnl_usd']:+,.2f}")
            q4.metric("Max net drawdown", f"{info['max_net_drawdown_pct']:.2f}%")
            df = pd.DataFrame(portfolio["trades"])
            plot_df = pd.DataFrame({"Trade": [0] + df["trade_number"].tolist(),
                                   "Gross": [starting] + df["gross_equity_usd"].tolist(),
                                   "Net": [starting] + df["net_equity_usd"].tolist()})
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=plot_df["Trade"], y=plot_df["Gross"], name="Before costs"))
            fig.add_trace(go.Scatter(x=plot_df["Trade"], y=plot_df["Net"], name="After costs"))
            fig.update_layout(title="Cost-adjusted equity (scenario, fixed lots)", xaxis_title="Trade number", yaxis_title="USD-equivalent equity")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.warning(info["note"])
            st.download_button("Download trade comparison JSON", json.dumps(portfolio, indent=2), "trade_comparison.json", "application/json")
    except (ValueError, FileNotFoundError, KeyError, json.JSONDecodeError) as error:
        st.error(f"Cannot analyze trade input: {error}")

with guide:
    st.markdown("""
    ### What this project teaches
    - **Contract size:** BTCUSD is modeled as 0.001 BTC per contract. Ten contracts = 0.01 BTC.
    - **Maker/taker:** applied independently to entry and exit. Limit orders are *not guaranteed* maker fills.
    - **Bid–ask spread:** the full quoted spread is split into a half-spread on each side.
    - **Slippage:** modeled separately as adverse execution movement on each side.
    - **GST:** calculated on trading commission, **not** on the whole notional or profit.
    - **Funding:** positive rate means longs pay shorts; negative means shorts pay longs. Funding is only charged for assumed snapshots while the position is open.
    - **Leverage:** changes the approximate margin estimate, not PnL for a fixed number of contracts.
    - **Project 6:** this is trade-price cost sensitivity, not an exact replication of its bar-by-bar rebalanced backtester.

    ### What the model intentionally does not provide
    No real exchange settlement quote, variable funding history, bid–ask/order-book snapshots, liquidation, maker fill probability, tier-dependent fees, currency conversion charges or income tax.

    ### Exchange references
    - https://www.delta.exchange/fees
    - https://www.delta.exchange/en/contracts
    - https://www.delta.exchange/support/solutions?articleId=80001183756
    """)
