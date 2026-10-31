"""Read-only Streamlit UI for Delta BTCUSD historical + streaming data.

Start separately via: streamlit run dashboard.py
No private endpoints, credentials, or trading calls.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from delta_collector.config import DEFAULT_TIMEFRAMES, INTERVAL_SECONDS
from delta_collector.status import read_status
from delta_collector.storage import CandleStore

st.set_page_config(page_title="Delta BTC Market Lab", page_icon="📈", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""<style>
.stApp {background: #090f1d; color: #edf3ff;}
[data-testid="stSidebar"] {background: #0f192c;}
[data-testid="stMetric"] {background:#142139; padding:12px; border-radius:12px;
 border:1px solid #273958;}
h1, h2, h3 {letter-spacing: -.025em;}
[data-testid="stTabs"] {margin-top: 10px;}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=12, show_spinner=False)
def recent_candles(root: str, symbol: str, timeframe: str, n: int):
    return CandleStore(root).tail(symbol, timeframe, n)


@st.cache_data(ttl=20, show_spinner=False)
def monthly_coverage(root: str, symbol: str, timeframe: str) -> dict:
    store = CandleStore(root)
    files = store._files(symbol, timeframe)
    # Per-month reads keep peak memory bounded; only summary metrics are cached.
    count, first, last = 0, None, None
    for path in files:
        with path.open(encoding="utf-8") as fp:
            rows = json.load(fp)
        if not rows:
            continue
        timestamps = [x["timestamp_utc"] for x in rows]
        count += len(rows)
        lo, hi = min(timestamps), max(timestamps)
        first = lo if first is None or lo < first else first
        last = hi if last is None or hi > last else last
    return {"timeframe": timeframe, "candles": count, "months": len(files),
            "first": first, "last": last}


def chart_for(df: pd.DataFrame, timeframe: str, show_ema: bool):
    fig = make_subplots(rows=2, cols=1, row_heights=[.78, .22], shared_xaxes=True,
                        vertical_spacing=.045)
    fig.add_trace(go.Candlestick(x=df["timestamp_utc"], open=df["open"],
                                high=df["high"], low=df["low"], close=df["close"],
                                increasing_line_color="#16c784", decreasing_line_color="#ef5350",
                                name=f"BTCUSD {timeframe}"), row=1, col=1)
    if show_ema:
        for window, color in [(9, "#eab308"), (21, "#22d3ee")]:
            series = df["close"].ewm(span=window, adjust=False).mean()
            fig.add_trace(go.Scatter(x=df["timestamp_utc"], y=series, name=f"EMA {window}",
                                     line={"color": color, "width": 1.6}), row=1, col=1)
    colors = ["#16c784" if c >= o else "#ef5350"
              for o, c in zip(df["open"], df["close"])]
    fig.add_trace(go.Bar(x=df["timestamp_utc"], y=df["volume"],
                         marker_color=colors, name="Volume", showlegend=False), row=2, col=1)
    fig.update_layout(template="plotly_dark", paper_bgcolor="#090f1d",
                      plot_bgcolor="#101b2e", height=570, margin=dict(l=10,r=10,t=35,b=10),
                      xaxis_rangeslider_visible=False, legend_orientation="h",
                      legend_y=1.07, hovermode="x unified")
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1, gridcolor="#24364c")
    fig.update_yaxes(title_text="Volume", row=2, col=1, gridcolor="#24364c")
    fig.update_xaxes(gridcolor="#24364c")
    return fig


@st.fragment(run_every="15s")
def render_overview(root: str, symbol: str):
    status = read_status(Path(root).parent / "status.json")
    ws = status.get("websocket", {})
    a, b, c, d = st.columns(4)
    a.metric("Collector mode", str(status.get("mode", "Not started")).upper())
    b.metric("Collector state", str(status.get("state", "Offline")).upper())
    c.metric("WebSocket", str(ws.get("state", "Not started")).upper())
    d.metric("Last WS candle price", f"${ws['last_price']:,.2f}" if
             isinstance(ws.get("last_price"), (float, int)) else "—")
    st.caption(f"Snapshot updated (UTC): {status.get('updated_utc', '—')}  ·  "
               f"Last WS message (UTC): {ws.get('last_message_utc', '—')}")
    if status.get("last_error"):
        st.error(f"Collector error: {status['last_error']}")
    st.subheader("Stored candle coverage")
    entries = []
    for tf in DEFAULT_TIMEFRAMES:
        try:
            coverage = monthly_coverage(root, symbol, tf)
            extra = status.get("timeframes", {}).get(tf, {})
            coverage.update({"progress_pct": extra.get("progress_pct"),
                             "last_backfill_missing": extra.get("missing"),
                             "sync_state": extra.get("state", "—")})
            entries.append(coverage)
        except (OSError, ValueError, KeyError) as exc:
            entries.append({"timeframe": tf, "error": str(exc)})
    st.dataframe(pd.DataFrame(entries), hide_index=True, use_container_width=True)
    st.info("WebSocket candles are provisional. Only REST-confirmed, completed candles are written to monthly JSON files.")


@st.fragment(run_every="15s")
def render_chart(root: str, symbol: str, timeframe: str, n: int, show_ema: bool):
    try:
        df = recent_candles(root, symbol, timeframe, n)
    except (OSError, ValueError) as exc:
        st.error(f"Unable to read candle data: {exc}")
        return
    if df.empty:
        st.warning("No saved candles yet. Run the REST backfill from a terminal first.")
        return
    latest = df.iloc[-1]
    ca, cb, cc, cd = st.columns(4)
    ca.metric("Last closed price", f"${latest['close']:,.2f}")
    cb.metric("Last high", f"${latest['high']:,.2f}")
    cc.metric("Last low", f"${latest['low']:,.2f}")
    cd.metric("Candles shown", f"{len(df):,}")
    st.plotly_chart(chart_for(df, timeframe, show_ema), use_container_width=True,
                    config={"displaylogo": False})
    st.caption("Historical candle opens shown in UTC; indicator overlays are illustrative, not trading signals.")
    with st.expander("View last 50 OHLCV rows"):
        st.dataframe(df.tail(50).iloc[::-1], hide_index=True, use_container_width=True)
    st.download_button("Download viewed candles (JSON)",
                       data=df.to_json(orient="records", date_format="iso", date_unit="ms", indent=2),
                       file_name=f"{symbol}_{timeframe}_recent.json", mime="application/json")


def render_quality(root: str, symbol: str):
    reports = Path(root).parent / "reports"
    rows = []
    for tf in DEFAULT_TIMEFRAMES:
        path = reports / f"{symbol}_{tf}_missing.json"
        if not path.exists():
            rows.append({"timeframe": tf, "status": "Run audit", "expected": None,
                         "actual": None, "missing": None})
            continue
        try:
            with path.open(encoding="utf-8") as fp:
                obj = json.load(fp)
            summary = obj["summary"]
            rows.append({"timeframe": tf, "status": "Report available",
                         "expected": summary["expected"], "actual": summary["actual"],
                         "missing": summary["missing"],
                         "first_missing": summary["first_missing"]})
        except (OSError, ValueError, KeyError) as exc:
            rows.append({"timeframe": tf, "status": f"Invalid report: {exc}"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("Missing slots are never automatically filled. Run `main.py audit --days 365` to update these reports.")
    selected = st.selectbox("Inspect gap-report JSON", DEFAULT_TIMEFRAMES, key="audit_tf")
    report = reports / f"{symbol}_{selected}_missing.json"
    if report.exists():
        st.download_button("Download gap report", data=report.read_bytes(),
                           file_name=report.name, mime="application/json")


def render_system(root: str):
    status = read_status(Path(root).parent / "status.json")
    st.subheader("Collector status JSON")
    st.json(status if status else {"message": "Collector has not run"})
    st.subheader("Run from separate terminals")
    st.code("python main.py backfill --days 365", language="powershell")
    st.code("python main.py live --poll-seconds 60", language="powershell")
    st.code("python main.py audit --days 365", language="powershell")
    st.caption("Read-only dashboard. Run only one backfill/live writer per data directory.")


def main():
    with st.sidebar:
        st.markdown("### ◈ Delta Market Lab")
        st.caption("India · Public BTCUSD futures data")
        root = st.text_input("Candle data folder", "data/candles")
        symbol = st.text_input("Symbol", "BTCUSD").strip().upper()
        timeframe = st.selectbox("Timeframe", DEFAULT_TIMEFRAMES, index=1)
        n = st.slider("Chart candle count", min_value=50, max_value=1000, value=250, step=50)
        show_ema = st.toggle("Show EMA 9 / EMA 21", value=True)
        st.divider()
        st.success("READ-ONLY · NO API KEYS")
        if st.button("Refresh dashboard", use_container_width=True):
            recent_candles.clear()
            monthly_coverage.clear()
            st.rerun()
    if symbol != "BTCUSD":
        st.warning("This learning project is designed and tested for BTCUSD. Choose BTCUSD to continue.")
        return
    st.title("BTCUSD  /  Market Data Studio")
    st.caption("Delta Exchange India  •  REST backfill + WebSocket  •  Monthly JSON storage")
    overview, candles, quality, system = st.tabs(["📊 Overview", "🕯️ Candles", "🧪 Data quality", "⚙️ Collector"])
    with overview:
        render_overview(root, symbol)
    with candles:
        render_chart(root, symbol, timeframe, n, show_ema)
    with quality:
        render_quality(root, symbol)
    with system:
        render_system(root)
    st.caption("Overview and chart refresh automatically about every 15 seconds. Data comes from saved JSON, not direct exchange access.")


if __name__ == "__main__":
    main()
