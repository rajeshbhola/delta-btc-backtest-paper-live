"""Read-only Streamlit dashboard for Project 3 indicator JSON data."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from indicator_studio.config import TIMEFRAMES
from indicator_studio.json_files import read_latest

st.set_page_config(page_title="BTC Technical Indicator Studio", page_icon="📈", layout="wide")
st.title("📈 BTC Technical Indicator Studio")
st.caption("Project 3  •  BTCUSD Futures  •  JSON data  •  No trading or exchange credentials")

def default_output() -> str:
    if Path("data/reports").exists():
        return "data"
    return "demo_results"

@st.cache_data(ttl=15, show_spinner=False)
def load_report(output: str, tf: str) -> dict:
    path = Path(output) / "reports" / f"BTCUSD_{tf}_indicators.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

@st.cache_data(ttl=15, show_spinner=False)
def load_candles(output: str, tf: str, rows: int) -> list[dict]:
    return read_latest(output, tf, rows)

with st.sidebar:
    st.header("Data settings")
    output = st.text_input("Project 3 output folder", value=default_output(),
                           help="Use demo_results, data or data_real; do not point at Project 2's clean files.")
    tf = st.selectbox("Timeframe", list(TIMEFRAMES), index=1)
    nrows = st.slider("Recent candles to display", min_value=100, max_value=2000, value=300, step=100)
    st.caption("This dashboard reads finished output files. Run `main.py analyze` in a separate terminal to update them.")

reports = {timeframe: load_report(output, timeframe) for timeframe in TIMEFRAMES}
rows = load_candles(output, tf, nrows)
current_report = reports.get(tf, {})
if any(r.get("data_origin") == "SYNTHETIC_DEMO" for r in reports.values()):
    st.warning("SYNTHETIC DEMO DATA — all prices and indicator readings are examples, not actual Delta BTCUSD history.")
if not any(reports.values()):
    st.error("No indicator reports found. First run: `python main.py analyze --source demo_data --output data`")
    st.stop()

st.subheader("Dataset overview")
summary = []
for timeframe, report in reports.items():
    summary.append({
        "Timeframe": timeframe,
        "Candles": report.get("rows", 0),
        "Missing slots": report.get("missing_candle_slots", 0),
        "RSI ready": report.get("indicator_ready_rows", {}).get("rsi_14", 0),
        "Last candle (UTC)": report.get("last_candle") or "—",
    })
st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)

if not rows:
    st.warning("No indicator rows found for this timeframe. Run the analyzer with this timeframe enabled.")
    st.stop()

frame = pd.DataFrame(rows)
frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
for name in frame.columns:
    if name != "timestamp_utc":
        frame[name] = pd.to_numeric(frame[name], errors="coerce")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Selected timeframe", tf)
col2.metric("Candles in dataset", f"{current_report.get('rows', 0):,}")
col3.metric("Missing candle slots", f"{current_report.get('missing_candle_slots', 0):,}")
last_close = frame["close"].iloc[-1]
col4.metric("Last stored close (USD)", f"${last_close:,.2f}")
st.caption("Stored close is historical and not necessarily the current market price.")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Price & Trends", "⚡ Momentum", "🛡️ Volatility", "📁 Data & Learning"])

with tab1:
    st.subheader("BTC candles + moving averages")
    overlays = st.multiselect("Choose indicators", ["EMA 9", "EMA 21", "EMA 50", "SMA 20", "SMA 50", "Bollinger Bands"],
                              default=["EMA 9", "EMA 21"])
    chart = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.76, 0.24], vertical_spacing=0.05)
    chart.add_trace(go.Candlestick(
        x=frame.timestamp_utc, open=frame.open, high=frame.high,
        low=frame.low, close=frame.close, name="BTCUSD", increasing_line_color="#24c48e",
        decreasing_line_color="#f47272"), row=1, col=1)
    for name, field, color in [
        ("EMA 9", "ema_9", "#ffd166"), ("EMA 21", "ema_21", "#60a5fa"),
        ("EMA 50", "ema_50", "#c4b5fd"), ("SMA 20", "sma_20", "#e879f9"),
        ("SMA 50", "sma_50", "#fbbf24"),
    ]:
        if name in overlays:
            chart.add_trace(go.Scatter(x=frame.timestamp_utc, y=frame[field],
                                       mode="lines", name=name, line=dict(color=color, width=1.5)), row=1, col=1)
    if "Bollinger Bands" in overlays:
        for label, field, color in [("BB upper", "bb_upper", "#a78bfa"),
                                    ("BB middle", "bb_middle", "#93c5fd"),
                                    ("BB lower", "bb_lower", "#a78bfa")]:
            chart.add_trace(go.Scatter(x=frame.timestamp_utc, y=frame[field], mode="lines",
                                       name=label, line=dict(color=color, width=1, dash="dot")), row=1, col=1)
    chart.add_trace(go.Bar(x=frame.timestamp_utc, y=frame.volume, name="Volume",
                           marker_color="#7c8fa8"), row=2, col=1)
    chart.update_layout(height=650, xaxis_rangeslider_visible=False, hovermode="x unified",
                        legend=dict(orientation="h", y=1.10), margin=dict(l=20, r=20, t=20, b=20))
    chart.update_yaxes(title_text="USD", row=1, col=1)
    chart.update_yaxes(title_text="Volume", row=2, col=1)
    st.plotly_chart(chart, use_container_width=True)
    st.info("EMA reacts more strongly to recent closing prices. SMA gives equal weight to every price in the lookback window. These are descriptive indicators, not guaranteed trade signals.")

with tab2:
    st.subheader("RSI 14 — Relative Strength Index")
    rsi_fig = go.Figure()
    rsi_fig.add_trace(go.Scatter(x=frame.timestamp_utc, y=frame.rsi_14, mode="lines", name="RSI 14", line=dict(color="#7dd3fc")))
    rsi_fig.add_hline(y=70, line_dash="dot", line_color="#f87171", annotation_text="70")
    rsi_fig.add_hline(y=30, line_dash="dot", line_color="#34d399", annotation_text="30")
    rsi_fig.update_layout(height=300, yaxis=dict(range=[0, 100]), margin=dict(l=15, r=15, t=15, b=15))
    st.plotly_chart(rsi_fig, use_container_width=True)
    st.caption("RSI above 70 is often called overbought and below 30 oversold; neither is a reliable standalone reversal signal.")
    st.subheader("MACD (12, 26, 9)")
    macd_fig = go.Figure()
    macd_fig.add_trace(go.Bar(x=frame.timestamp_utc, y=frame.macd_histogram,
                              marker_color=["#22c55e" if (pd.notna(v) and v >= 0) else "#fb7185" for v in frame.macd_histogram],
                              name="Histogram"))
    macd_fig.add_trace(go.Scatter(x=frame.timestamp_utc, y=frame.macd, name="MACD", line=dict(color="#60a5fa")))
    macd_fig.add_trace(go.Scatter(x=frame.timestamp_utc, y=frame.macd_signal, name="Signal", line=dict(color="#fbbf24")))
    macd_fig.update_layout(height=340, legend=dict(orientation="h"), margin=dict(l=15, r=15, t=15, b=15))
    st.plotly_chart(macd_fig, use_container_width=True)

with tab3:
    st.subheader("Bollinger Bands (20, 2)")
    fig = go.Figure()
    for label, field, color in [("Close", "close", "#e2e8f0"), ("Upper", "bb_upper", "#c4b5fd"),
                                ("Middle", "bb_middle", "#60a5fa"), ("Lower", "bb_lower", "#c4b5fd")]:
        fig.add_trace(go.Scatter(x=frame.timestamp_utc, y=frame[field], mode="lines", name=label, line=dict(color=color)))
    fig.update_layout(height=340, margin=dict(l=15, r=15, t=15, b=15))
    st.plotly_chart(fig, use_container_width=True)
    st.subheader("ATR 14 — Average True Range")
    fig2 = go.Figure(go.Scatter(x=frame.timestamp_utc, y=frame.atr_14, mode="lines",
                                 name="ATR 14", line=dict(color="#fbbf24")))
    fig2.update_layout(height=280, yaxis_title="Price units (USD)", margin=dict(l=15, r=15, t=15, b=15))
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("ATR measures movement size, not market direction. It is not an automatic stop-loss level.")

with tab4:
    st.subheader("Latest computed candles")
    st.dataframe(frame.tail(100), hide_index=True, use_container_width=True)
    st.download_button("Download visible rows as JSON", data=json.dumps(rows, indent=2),
                       file_name=f"BTCUSD_{tf}_indicators.json", mime="application/json")
    st.download_button("Download visible rows as CSV", data=frame.to_csv(index=False).encode("utf-8"),
                       file_name=f"BTCUSD_{tf}_indicators.csv", mime="text/csv")
    st.subheader("Data continuity & indicator readiness")
    if current_report.get("missing_candle_slots", 0):
        st.warning(f"Detected {current_report['missing_candle_slots']:,} missing candle slots. Indicator warm-up restarts after every gap. Fix gaps in Project 2 first.")
    else:
        st.success("No gaps detected between stored candles for this timeframe.")
    st.json({"ready_row_counts": current_report.get("indicator_ready_rows", {}),
             "gap_examples": current_report.get("gap_examples", [])[:15]})
    st.subheader("How the indicators are calculated")
    st.markdown("""
    - **SMA(20), SMA(50):** average of the last 20 or 50 closing prices.
    - **EMA(9), EMA(21), EMA(50):** exponential average with `alpha = 2 / (period + 1)`, seeded using the first period's SMA.
    - **RSI(14):** Wilder-smoothed average price gains versus losses (first valid result after 15 candles).
    - **MACD:** EMA(12) minus EMA(26); signal = EMA(9) of the MACD; histogram = MACD − signal.
    - **Bollinger Bands:** SMA(20) ± 2 × population standard deviation of the last 20 closes.
    - **ATR(14):** Wilder-smoothed true range; true range also considers the prior close.
    
    Indicators use only the **current and earlier candles**, never future prices. Initial values are `null` until a calculation has enough observations.
    """)
    st.caption("No real orders, broker account access, forecasting or advice. Project 4 introduces signal generation.")
