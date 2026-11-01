"""Project 4 interactive and READ-ONLY research dashboard (no live trading)."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from signal_lab.config import TIMEFRAMES
from signal_lab.json_files import latest_rows

st.set_page_config(page_title="BTC Signal Studio | Project 4", page_icon="📊", layout="wide")
st.title("📊 Project 4 · BTC Trading Signal Studio")
st.caption("Offline educational research: EMA(9/21) crossover + RSI(14). No broker keys, orders, PnL or price predictions.")

root = st.sidebar.text_input("Signal output folder", value="demo_results" if Path("demo_results").exists() else "output")
tf = st.sidebar.selectbox("Timeframe", list(TIMEFRAMES), index=1)
limit = st.sidebar.slider("Recent completed candles to display", 100, 2000, 600, 100)
st.sidebar.info("Import and process Project 3 JSON using the terminal command in README.md. The dashboard only reads files.")
report_path = Path(root) / "reports" / f"BTCUSD_{tf}_signals.json"
if not report_path.exists():
    st.error(f"Report not found: {report_path}. Run python main.py generate --source demo_input --output {root}")
    st.stop()
try:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    data = latest_rows(root, tf, limit=limit)
except (OSError, ValueError, KeyError) as error:
    st.error(f"Cannot read JSON: {error}")
    st.stop()
if not data:
    st.warning("No completed candles found for this timeframe.")
    st.stop()
if report.get("data_origin") == "SYNTHETIC_DEMO":
    st.warning("DEMO MODE — all displayed historical prices and signals are synthetic, not actual BTCUSD market data.")
else:
    st.info("Input source is external indicator JSON. Confirm that it contains clean, authentic exchange data from Project 3.")

counts = report.get("signals", {})
a, b, c, d, e = st.columns(5)
a.metric("Completed candles", f"{report.get('total_rows', 0):,}")
b.metric("BUY signals", f"{counts.get('BUY', 0):,}")
c.metric("SELL signals", f"{counts.get('SELL', 0):,}")
d.metric("HOLD bars", f"{counts.get('HOLD', 0):,}")
e.metric("Missing candle slots", f"{report.get('missing_candle_slots', 0):,}")

frame = pd.DataFrame(data)
frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
frame["decision_time_utc"] = pd.to_datetime(frame["decision_time_utc"], utc=True)
for col in ["close", "ema_9", "ema_21", "rsi_14"]:
    frame[col] = pd.to_numeric(frame[col], errors="coerce")

page1, page2, page3, page4 = st.tabs(["📈 Price & Signals", "🧭 Signal Explorer", "🛡️ Data Quality", "📘 Learn the Rules"])
with page1:
    st.subheader(f"BTCUSD · {tf} · Most recent {len(frame):,} completed candles")
    chart = go.Figure()
    chart.add_trace(go.Scatter(x=frame["timestamp_utc"], y=frame["close"], name="Close", line=dict(color="#93c5fd", width=1.5)))
    chart.add_trace(go.Scatter(x=frame["timestamp_utc"], y=frame["ema_9"], name="EMA 9", line=dict(color="#f59e0b", width=1.4)))
    chart.add_trace(go.Scatter(x=frame["timestamp_utc"], y=frame["ema_21"], name="EMA 21", line=dict(color="#a78bfa", width=1.4)))
    for signal, color, marker in (("BUY", "#22c55e", "triangle-up"), ("SELL", "#ef4444", "triangle-down")):
        filtered = frame[frame["signal"] == signal]
        chart.add_trace(go.Scatter(x=filtered["timestamp_utc"], y=filtered["close"], mode="markers",
                                   name=signal, marker=dict(color=color, size=13, symbol=marker),
                                   customdata=filtered["decision_time_utc"].astype(str),
                                   hovertemplate="Candle start: %{x}<br>Close: %{y}<br>Decision after candle ends: %{customdata}<extra></extra>"))
    chart.update_layout(height=450, xaxis_title="Candle start (UTC)", yaxis_title="BTCUSD price", hovermode="x unified")
    st.plotly_chart(chart, use_container_width=True)
    st.caption("Markers are drawn at candle start for chart alignment. A signal becomes known only at decision_time_utc (when that candle has closed). It is not an order.")
    rsi_chart = go.Figure()
    rsi_chart.add_trace(go.Scatter(x=frame["timestamp_utc"], y=frame["rsi_14"], name="RSI(14)", line=dict(color="#22c55e")))
    for level in (25, 30, 50, 70, 75):
        rsi_chart.add_hline(y=level, line_dash="dot", opacity=.35)
    rsi_chart.update_layout(height=250, yaxis_title="RSI", yaxis_range=[0, 100], xaxis_title="Candle start (UTC)")
    st.plotly_chart(rsi_chart, use_container_width=True)
with page2:
    st.subheader("Explore BUY / SELL / HOLD signals")
    show = st.multiselect("Filter", ["BUY", "SELL", "HOLD"], default=["BUY", "SELL"])
    filtered = frame[frame["signal"].isin(show)].sort_values("decision_time_utc", ascending=False)
    st.write(f"{len(filtered):,} matching rows within the displayed recent window")
    st.dataframe(filtered[["decision_time_utc", "close", "signal", "reason", "ema_9", "ema_21", "rsi_14"]],
                 hide_index=True, use_container_width=True)
    st.download_button("Download filtered CSV", filtered.to_csv(index=False).encode("utf-8"),
                       file_name=f"BTCUSD_{tf}_signals_recent.csv", mime="text/csv")
    st.download_button("Download filtered JSON", filtered.assign(
        timestamp_utc=filtered["timestamp_utc"].astype(str),
        decision_time_utc=filtered["decision_time_utc"].astype(str)
    ).to_json(orient="records", indent=2), file_name=f"BTCUSD_{tf}_signals_recent.json", mime="application/json")
with page3:
    st.subheader("Data coverage and reason counts")
    st.write(f"**First candle:** {report.get('first_candle')} | **Last candle:** {report.get('last_candle')}")
    st.write(f"**As-of:** {report.get('as_of_utc')} | **Incomplete candles excluded:** {report.get('incomplete_candles_skipped')}")
    st.write(f"**Data origin:** {report.get('data_origin')}")
    st.json(report.get("reasons", {}))
    if report.get("missing_candle_slots", 0):
        st.warning("Historical gaps exist. The signal state is reset at a gap; repair data in Project 2, then rerun Projects 3 and 4.")
    st.download_button("Download full quality / signal report", json.dumps(report, indent=2),
                       file_name=f"BTCUSD_{tf}_signal_report.json", mime="application/json")
with page4:
    st.subheader("Strategy rules")
    rules = report.get("rules", {})
    st.write(f"**BUY:** EMA 9 crosses ABOVE EMA 21; RSI(14) is between {rules.get('buy_rsi_min')} and {rules.get('buy_rsi_max')} (inclusive).")
    st.write(f"**SELL:** EMA 9 crosses BELOW EMA 21; RSI(14) is between {rules.get('sell_rsi_min')} and {rules.get('sell_rsi_max')} (inclusive).")
    st.write("**HOLD:** No crossover, RSI rejects the crossover, missing indicator warm-up, or a detected gap.")
    st.info("Candle timestamp is the OPEN time. The earliest a signal can be known is the CLOSE time, stored as decision_time_utc. A future backtester must simulate execution after this moment, not at a price already known at the signal candle close.")
    st.write("**What this project does not do:** Position tracking, order placement, backtesting, realistic fills, risk budgeting, fees or live execution.")
    st.code("python main.py generate --source demo_input --output output\npython main.py summary --output output", language="powershell")
