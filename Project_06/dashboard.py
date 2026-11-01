"""Read-only Streamlit visualizer for Project 6 backtests (no Delta API)."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from backtest_lab.config import TIMEFRAMES
from backtest_lab.pipeline import read_saved
from backtest_lab.data import load_json_months

st.set_page_config(page_title="BTC Backtesting Lab | Project 6", page_icon="📈", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 2rem; max-width: 1600px}
[data-testid="stMetric"] {background: #151e32; border-radius: 12px; padding: 12px 16px;}
</style>""", unsafe_allow_html=True)
st.title("📈 BTC Vectorized Backtesting Lab")
st.caption("Project 6 of 30 · Bitcoin futures research · No live data, no broker connection, no orders · All bundled data is SYNTHETIC")

with st.sidebar:
    st.header("Backtest results")
    output = st.text_input("Results directory", value="demo_results")
    possible = [tf for tf in TIMEFRAMES if (Path(output).expanduser() / "reports" / f"BTCUSD_{tf}.json").exists()]
    if not possible:
        st.warning("No results found. Run: python main.py run --output results")
        st.stop()
    tf = st.selectbox("Timeframe", options=possible, index=possible.index("5m") if "5m" in possible else 0)
    displayed = st.slider("Candles to display", min_value=100, max_value=1500, value=400, step=100)
    st.info("The dashboard only READS saved JSON backtests. Change strategy settings through main.py run, then choose that output folder.")

@st.cache_data(show_spinner=False, ttl=20)
def load_results(folder: str, timeframe: str):
    return read_saved(folder, timeframe)

try:
    report, curve, trades = load_results(output, tf)
except (ValueError, OSError, KeyError) as exc:
    st.error(f"Cannot read results: {exc}")
    st.stop()

curve["timestamp_utc"] = pd.to_datetime(curve["timestamp_utc"], utc=True)
curve["mark_time_utc"] = pd.to_datetime(curve.get("mark_time_utc", curve["timestamp_utc"]), utc=True)
if not trades.empty:
    trades["entry_time_utc"] = pd.to_datetime(trades["entry_time_utc"], utc=True)
    trades["exit_time_utc"] = pd.to_datetime(trades["exit_time_utc"], utc=True)

mode_label = "LONG ONLY" if report["mode"] == "long_only" else "LONG / SHORT"
if report.get("data_origin") == "SYNTHETIC_DEMO":
    st.warning("This view uses intentionally SYNTHETIC demonstration candles and signals. Results do not show historical Delta trading performance.")
st.caption(f"**BTCUSD · {tf} · {mode_label} · Starting capital USD {report['starting_capital_usd']:,.0f}** · Fee assumption {report['fee_bps_per_side']} bps per side")
col = st.columns(5)
col[0].metric("Net return", f"{report['net_return_pct']:+.2f}%")
col[1].metric("Ending equity", f"${report['ending_capital_usd']:,.2f}")
col[2].metric("Max drawdown", f"{report['max_drawdown_pct']:.2f}%")
col[3].metric("Trades", f"{report['trade_count']:,}")
col[4].metric("Win rate", f"{report['win_rate_pct']:.1f}%")

ov, trade_tab, chart_tab, quality_tab = st.tabs(["📊 Performance", "📋 Trades", "🕯️ Price & Signals", "🔍 Quality & Learning"])
with ov:
    eq = curve.iloc[-min(len(curve), 20000):].copy()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.1, row_heights=[.7,.3])
    fig.add_trace(go.Scatter(x=eq["mark_time_utc"], y=eq["equity"], mode="lines", name="Equity (USD)", line=dict(color="#60A5FA", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=eq["mark_time_utc"], y=eq["drawdown_pct"], fill="tozeroy", name="Drawdown %", line=dict(color="#F97373", width=1)), row=2, col=1)
    fig.update_layout(template="plotly_dark", height=550, paper_bgcolor="#0B1220", plot_bgcolor="#0B1220", margin=dict(l=20,r=20,t=30,b=20))
    fig.update_yaxes(title_text="USD", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown %", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)
    if len(curve) > 20000:
        st.caption("Showing the most recent 20,000 equity points for responsive charting. Summary metrics use the whole backtest.")
    st.subheader("How to read these metrics")
    st.write("Net return measures the change in the simulated account. Maximum drawdown measures the worst peak-to-trough equity decline. Win rate is the percentage of closed position runs with positive net PnL; it does not measure the magnitude of wins or losses.")
    st.warning("Costs are simplified: spread, slippage, funding, liquidation and actual India tax treatment are NOT included. Results are NOT real-trading predictions.")

with trade_tab:
    if trades.empty:
        st.info("No trades in this period. Try another timeframe, a longer period, or long_short mode.")
    else:
        option = st.selectbox("Show trades", ["All", "Winners", "Losers"])
        if option == "Winners":
            view = trades[trades["net_pnl"] > 0]
        elif option == "Losers":
            view = trades[trades["net_pnl"] < 0]
        else:
            view = trades
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button("Download all trades CSV", trades.to_csv(index=False).encode(), file_name=f"BTCUSD_{tf}_trades.csv", mime="text/csv")
        st.caption("A trade closes at the next signal's actionable bar open, after a missing-data gap, or at the final historical close. No stops or liquidation in this mini-project.")

with chart_tab:
    source = report.get("candles_root", "demo_data")
    try:
        @st.cache_data(show_spinner=False, ttl=20)
        def load_candles(root, timeframe):
            return load_json_months(root, "candles", timeframe)
        candles = load_candles(source, tf)
        candles["timestamp_utc"] = pd.to_datetime(candles["timestamp_utc"], utc=True)
        recent = candles.merge(curve[["timestamp_utc", "signal", "position"]], on="timestamp_utc", how="inner").tail(displayed)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=recent["timestamp_utc"], open=recent["open"], high=recent["high"], low=recent["low"], close=recent["close"], name="BTCUSD"))
        for label, color, symbol, shift in [("BUY", "#22C55E", "triangle-up", -1), ("SELL", "#FB7185", "triangle-down", 1)]:
            pts = recent[recent["signal"] == label]
            if not pts.empty:
                fig.add_trace(go.Scatter(x=pts["timestamp_utc"], y=pts["low"] if shift==-1 else pts["high"], mode="markers", marker=dict(color=color, symbol=symbol, size=12), name=f"{label} (signal at close)"))
        fig.update_layout(template="plotly_dark", height=590, xaxis_rangeslider_visible=False, paper_bgcolor="#0B1220", plot_bgcolor="#0B1220", margin=dict(l=20,r=20,t=30,b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("BUY/SELL markers are placed on signal candles for study. Any entry or reversal is simulated at the *following contiguous candle open*, never at the marked candle opening.")
    except (OSError, KeyError, ValueError) as exc:
        st.warning(f"Could not show price candles: {exc}. Use the path to the original candles/indicators in the report.")

with quality_tab:
    st.subheader("Input audit")
    di = report.get("data_info", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("Candles", f"{di.get('rows', 0):,}")
    c2.metric("Gaps detected", f"{di.get('gaps', 0):,}")
    c3.metric("Unmatched signal rows", f"{di.get('missing_signal_rows', 0):,}")
    st.json({k:v for k,v in report.items() if k != "note"})
    st.markdown("""**Important timing rules:**

    - A bar's opening time is **not** the signal decision time. The strategy knows the signal only after bar close.
    - An order is modeled at the next contiguous bar's **open**. No same-candle look-ahead.
    - Gaps flatten the strategy at the first available open; exposure through the missing interval is still reflected in the preceding open-to-open return.
    - **SELL means exit** in long-only mode. In long/short mode, SELL means enter or flip to a short. Both are purely hypothetical.
    - No broker orders, no Delta API keys, and no trading account are used.
    """)
    st.warning(report["note"])
