"""Project 5: Standalone, read-only Streamlit BTC chart explorer."""
from __future__ import annotations
from datetime import datetime, timedelta, time, timezone
from pathlib import Path
import pandas as pd
import streamlit as st
from chart_lab.config import SYMBOL, TIMEFRAMES, OVERLAYS
from chart_lab.sources import locate_root, latest_timestamp, load_range, combine_candles_and_indicators, candle_price_conflicts
from chart_lab.analytics import audit_window, signal_summary
from chart_lab.figures import make_price_figure, make_oscillators

st.set_page_config(page_title="BTC Chart Explorer | Project 5", page_icon="📊", layout="wide")
st.title("📊 BTC Chart & Signal Explorer")
st.caption("Mini-Project 5 · Read-only charting · Delta Exchange India BTCUSD · Five timeframes")

with st.sidebar:
    st.header("Data source")
    source_choice = st.radio("Source", ["Bundled synthetic demo", "My Project 1–4 JSON folders"])
    if source_choice == "Bundled synthetic demo":
        source = str(Path(__file__).resolve().parent / "demo_data")
        candle_src = indicator_src = signal_src = source
        st.info("Synthetic demonstration prices. Not real BTCUSD market data.")
    else:
        st.caption("Enter the PROJECT OUTPUT FOLDER, not an individual monthly JSON file.")
        candle_src = st.text_input("Candles root (Project 1 or 2)", value="", placeholder=r"C:\Projects\Project_02\data_real")
        indicator_src = st.text_input("Indicators root (Project 3)", value="", placeholder=r"C:\Projects\Project_03\data_real")
        signal_src = st.text_input("Signals root (Project 4)", value="", placeholder=r"C:\Projects\Project_04\data_real")
        st.caption("You can supply just one folder; additional overlays depend on the selected source.")
    timeframe = st.selectbox("Candle timeframe", list(TIMEFRAMES), index=1)

candle_root = locate_root(candle_src, "candles")
indicator_root = locate_root(indicator_src, "indicators")
signal_root = locate_root(signal_src, "signals")
last = latest_timestamp(candle_root, timeframe) or latest_timestamp(indicator_root, timeframe)
if last is None:
    st.error("No candle files found for this timeframe. Check your paths or choose the included synthetic demo.")
    st.code("data/candles/BTCUSD/5m/2026-10.json\ndata/indicators/BTCUSD/5m/2026-10.json")
    st.stop()

with st.sidebar:
    st.header("Display range (UTC)")
    defaults = {"1m": 2, "5m": 4, "15m": 8, "1h": 20, "4h": 45}
    start_date = st.date_input("From date (inclusive)", value=(last - timedelta(days=defaults[timeframe])).date())
    end_date = st.date_input("Through date (inclusive)", value=last.date())
    cap = st.slider("Max recent candles to display", min_value=100, max_value=5000, value=1500, step=100)
    st.caption("Only monthly files overlapping this UTC date range are read. When too many candles match, the most recent N are displayed.")

if start_date > end_date:
    st.error("The start date must be on or before the end date.")
    st.stop()
start_utc = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
end_utc = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)

try:
    candles, cstats = load_range(candle_root, timeframe, start_utc, end_utc, cap)
    indicators, istats = load_range(indicator_root, timeframe, start_utc, end_utc, cap)
    signals, sstats = load_range(signal_root, timeframe, start_utc, end_utc, cap)
    mismatch = candle_price_conflicts(candles, indicators)
    data = combine_candles_and_indicators(candles, indicators)
except (ValueError, OSError, pd.errors.ParserError) as exc:
    st.error(f"Could not read JSON candle files: {exc}")
    st.stop()
if data.empty:
    st.warning("No candle records were found within the selected date range.")
    st.stop()

if source_choice == "Bundled synthetic demo":
    st.warning("DEMO: All displayed prices, indicators and trading labels are synthetic. Do not use these for trading.", icon="🧪")
if mismatch:
    st.warning(f"{mismatch} matching timestamps contain inconsistent candle close prices between the candle and indicator sources. Verify you selected outputs from the same market/data run.")
if (cstats["rows"] >= cap or istats["rows"] >= cap):
    st.info(f"Displaying a maximum of {cap:,} most recent records in the selected date window. This is a visualization limit, not a full-history data audit.")

counts = signal_summary(signals)
q = audit_window(data, timeframe)
cols = st.columns(5)
cols[0].metric("Candles shown", f"{len(data):,}")
cols[1].metric("Latest BTCUSD close", f"${data.close.iloc[-1]:,.2f}" if "close" in data else "N/A")
cols[2].metric("BUY labels", counts["BUY"])
cols[3].metric("SELL labels", counts["SELL"])
cols[4].metric("Missing slots in view", q["gap_slots"])

chart_tab, signals_tab, quality_tab, guide_tab = st.tabs(["📈 Interactive Chart", "🔍 Signals Explorer", "🛡 Data Quality", "📘 Learning Guide"])
with chart_tab:
    selected_overlays = st.multiselect("Trend overlays", options=[c for c in OVERLAYS if c in data.columns],
                                        default=[k for k in ("ema_9", "ema_21") if k in data.columns])
    show_volume = st.checkbox("Show volume bars", value=True)
    show_markers = st.checkbox("Show BUY/SELL decision-time markers", value=True)
    price_fig = make_price_figure(data, signals if show_markers else None, selected_overlays, show_volume)
    st.plotly_chart(price_fig, use_container_width=True)
    st.caption("Candle timestamps mark OPEN time. BUY/SELL markers are placed at decision_time_utc (after the source candle closes), not at the time the candle opened. Markers are educational labels, not executable orders.")
    osc = st.multiselect("Indicator panels", ["RSI", "MACD", "ATR"], default=["RSI", "MACD"])
    if osc:
        st.plotly_chart(make_oscillators(data, osc), use_container_width=True)
    st.download_button("Download this interactive chart as HTML", data=price_fig.to_html(full_html=True, include_plotlyjs=True),
                       file_name=f"BTCUSD_{timeframe}_interactive_chart.html", mime="text/html")
    st.download_button("Download shown candles + indicators as CSV", data=data.to_csv(index=False).encode("utf-8"),
                       file_name=f"BTCUSD_{timeframe}_shown.csv", mime="text/csv")
with signals_tab:
    st.subheader("BUY, SELL and HOLD labels")
    st.caption("Signals are read from Project 4 output. This app does NOT generate signals or place orders.")
    if signals.empty or "signal" not in signals:
        st.info("No Project 4 signal files were found for this timeframe and window. Enter the Project 4 output folder in the sidebar.")
    else:
        selected = st.multiselect("Filter labels", ["BUY", "SELL", "HOLD"], default=["BUY", "SELL"])
        subset = signals[signals.signal.isin(selected)]
        st.dataframe(subset.sort_values("timestamp_utc", ascending=False), use_container_width=True, hide_index=True)
        st.download_button("Download filtered signals JSON", data=subset.to_json(orient="records", date_format="iso", indent=2),
                           file_name=f"BTCUSD_{timeframe}_signals.json", mime="application/json")
with quality_tab:
    st.subheader("Quality of the displayed window")
    st.caption("A window check is NOT a full-year audit. For full-year validation use the Project 2 data-quality pipeline.")
    st.write({**q, "candle_month_files_read": cstats["files_read"], "indicator_month_files_read": istats["files_read"],
              "signal_month_files_read": sstats["files_read"], "source_close_mismatches": mismatch})
    if q["invalid_ohlc"] or q["invalid_volume"]:
        st.error("The displayed candles contain invalid values. Clean your input using Project 2 before research or backtesting.")
    if q["gap_slots"]:
        st.warning("Missing timestamps detected. This chart does not invent or forward-fill candles.")
    st.caption("The currently displayed rows may be truncated to the max-candles setting.")
with guide_tab:
    st.subheader("What you learn in Project 5")
    st.markdown("""
    1. **Candlesticks:** each bar represents Open, High, Low and Close during one UTC interval.
    2. **Volume:** how much trading activity occurred in that interval.
    3. **Moving averages and bands:** display outputs generated in Project 3 without recomputing them here.
    4. **RSI, MACD and ATR:** inspect momentum and volatility in separate panels.
    5. **BUY/SELL markers:** visualize Project 4's labels at **decision time**, the earliest time the signal can be known.
    6. **Data safety:** confirm signal timestamps and candle gaps before starting a backtest.

    **Project 1:** JSON candle output (`candles/BTCUSD/...`)  
    **Project 2:** cleaned candles (`clean/BTCUSD/...`)  
    **Project 3:** indicators (`indicators/BTCUSD/...`)  
    **Project 4:** signals (`signals/BTCUSD/...`)

    **No orders, no broker credentials, no trading profit calculations.** Project 6 begins strategy backtesting.
    """)
