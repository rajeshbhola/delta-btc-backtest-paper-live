"""Read-only Streamlit UI for Project 2; all candle changes happen via CLI."""
from __future__ import annotations

from pathlib import Path
import json
import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from quality_lab.config import TIMEFRAMES, SYMBOL
from quality_lab.json_store import JsonStore

st.set_page_config(page_title="Project 2 | BTC Data Quality", page_icon="🧹", layout="wide")
st.title("🧹 Project 2 — BTC Data Quality Lab")
st.caption("Standalone Delta Exchange India OHLCV cleaner • JSON only • No trading credentials")

default_dir = "data" if Path("data/clean").exists() else "demo_data"
root = st.sidebar.text_input("JSON data directory", value=os.environ.get("QUALITY_DATA_DIR", default_dir))
if Path(root).resolve() == Path("demo_data").resolve():
    st.sidebar.info("Showing bundled SYNTHETIC example data. For real data use data or data_real.")
timeframe = st.sidebar.selectbox("Timeframe", list(TIMEFRAMES), index=1)
store = JsonStore(Path(root))
report = store.read_report(timeframe)


def load_tail(layer: str, tf: str, max_candles: int) -> pd.DataFrame:
    records = []
    count = 0
    # Load only last months to avoid parsing a year of 1m data in the browser.
    for path in reversed(store.files(layer, tf)):
        try:
            with path.open(encoding="utf-8") as f:
                month = json.load(f)
            if isinstance(month, list):
                records = month + records
                count += len(month)
            if count >= max_candles:
                break
        except (json.JSONDecodeError, OSError) as exc:
            st.warning(f"Could not load {path.name}: {exc}")
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    required = {"timestamp_utc", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        st.warning("Selected JSON file does not have all OHLCV fields. Run 'process'.")
        return pd.DataFrame()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], errors="coerce", utc=True)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=list(required)).sort_values("timestamp_utc").tail(max_candles)


tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Clean Candles", "🔎 Quality Issues", "📘 How to Use"])

with tab1:
    st.subheader(f"{SYMBOL} · {timeframe} · Data quality")
    if report:
        q = report["quality"]
        c = report["coverage"]
        a, b, d, e = st.columns(4)
        a.metric("Raw records", f"{q['raw_rows']:,}")
        b.metric("Clean candles", f"{q['clean_rows']:,}")
        d.metric("Rejected rows", f"{q['rejected_rows']:,}")
        e.metric("Missing candle slots", f"{c['missing']:,}")
        st.progress(min(1.0, max(0.0, c["coverage_pct"] / 100)), text=f"Coverage: {c['coverage_pct']:.2f}%")
        st.caption("Audit window: " + c["window_start_utc"] + " to " + c["window_end_exclusive_utc"] + " (exclusive)")
        st.info("A missing candle is reported, not synthesized. Low coverage may mean Project 1 has not downloaded that time period.")
    else:
        st.warning("No quality report yet. First run `python main.py demo`, then `python main.py process --days 2`.")
    st.subheader("All timeframes")
    table_rows = []
    for tf in TIMEFRAMES:
        r = store.read_report(tf)
        if r:
            table_rows.append({"Timeframe": tf, "Raw": r["quality"]["raw_rows"],
                               "Clean": r["quality"]["clean_rows"],
                               "Invalid": r["quality"]["rejected_rows"],
                               "Missing": r["coverage"]["missing"],
                               "Coverage %": r["coverage"]["coverage_pct"]})
        else:
            table_rows.append({"Timeframe": tf, "Raw": "—", "Clean": "—", "Invalid": "—", "Missing": "—", "Coverage %": "—"})
    st.dataframe(pd.DataFrame(table_rows), hide_index=True, use_container_width=True)

with tab2:
    st.subheader(f"Clean {SYMBOL} {timeframe} chart")
    count = st.slider("Candles on chart", min_value=50, max_value=2000, value=300, step=50)
    df = load_tail("clean", timeframe, count)
    if df.empty:
        st.info("No cleaned candles. Run `python main.py process --days 2` first.")
    else:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.05,
                            row_heights=[.75, .25])
        fig.add_trace(go.Candlestick(x=df["timestamp_utc"], open=df["open"], high=df["high"],
                                     low=df["low"], close=df["close"], name="BTCUSD"), row=1, col=1)
        fig.add_trace(go.Bar(x=df["timestamp_utc"], y=df["volume"], name="Volume"), row=2, col=1)
        fig.update_layout(height=560, xaxis_rangeslider_visible=False, margin=dict(t=24, b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df.tail(30).iloc[::-1], use_container_width=True, hide_index=True)
        st.download_button("Download displayed candles (JSON)",
                           df.assign(timestamp_utc=df["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")).to_json(orient="records", indent=2),
                           file_name=f"{SYMBOL}_{timeframe}_clean_preview.json", mime="application/json")

with tab3:
    st.subheader("Validation problems and historical gaps")
    if not report:
        st.info("Run the `process` command to generate a report.")
    else:
        issues = report["quality"]["rejections_by_reason"]
        if issues:
            st.dataframe(pd.DataFrame([{"Problem": k, "Count": v} for k, v in issues.items()]),
                         use_container_width=True, hide_index=True)
        else:
            st.success("No invalid OHLCV fields found in the processed data.")
        st.write(f"Duplicate rows removed: **{report['quality']['duplicate_rows']}**")
        st.write(f"Out-of-order raw rows: **{report['quality']['out_of_order_raw_rows']}**")
        st.write(f"Suspicious >10% price moves (warnings, not removed): **{len(report['quality']['large_price_move_warnings'])}**")
        st.subheader("Missing candle ranges")
        gaps = report["coverage"]["missing_ranges"]
        if gaps:
            st.dataframe(pd.DataFrame(gaps[:200]), use_container_width=True, hide_index=True)
            if len(gaps) > 200:
                st.caption("Showing first 200 gap ranges; download the report for the stored complete list.")
        else:
            st.success("No gaps in the chosen audit window.")
        if report["coverage"].get("gap_ranges_truncated"):
            st.warning("Gap list limited to 1,000 ranges. Use shorter audit windows for more detail.")
        with st.expander("Rejected row examples"):
            st.json(report["quality"]["bad_row_examples"])
        st.download_button("Download full quality report", json.dumps(report, indent=2),
                           file_name=f"{SYMBOL}_{timeframe}_quality.json", mime="application/json")

with tab4:
    st.markdown("""
    ### First run: completely offline
    ```powershell
    py -m venv .venv
    .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
    .\\.venv\\Scripts\\python.exe main.py demo
    .\\.venv\\Scripts\\python.exe main.py process --days 2
    .\\.venv\\Scripts\\python.exe -m streamlit run dashboard.py
    ```
    ### Use Project 1 JSON files
    ```powershell
    .\\.venv\\Scripts\\python.exe main.py import --source "C:\\path\\to\\Project_01\\data\\candles"
    .\\.venv\\Scripts\\python.exe main.py process --days 365
    ```
    ### Or download without Project 1
    ```powershell
    .\\.venv\\Scripts\\python.exe main.py download --days 365
    .\\.venv\\Scripts\\python.exe main.py process --days 365
    ```
    ### Repair missing data (optional internet required)
    ```powershell
    .\\.venv\\Scripts\\python.exe main.py repair --timeframes 5m --max-gaps 5 --max-candles 2000
    .\\.venv\\Scripts\\python.exe main.py process --days 365
    ```
    **Safety:** Only public REST market-data endpoints are used. Source raw data
    is preserved during cleaning. No simulated candles, no API keys, no order placement.
    """)
