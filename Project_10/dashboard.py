"""Read-only Streamlit dashboard for saved walk-forward JSON reports."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="BTC Walk-Forward Lab",page_icon="📊",layout="wide")
st.title("📊 BTC Walk-Forward Strategy Optimizer")
st.caption("Mini-Project 10 | Offline historical study | BTCUSD | No orders or API credentials")

with st.sidebar:
    st.header("Load results")
    root=st.text_input("Report folder",value="demo_reports",help="A folder containing BTCUSD/{timeframe}/walk_forward.json")
    timeframe=st.selectbox("Timeframe",["1m","5m","15m","1h","4h"],index=1)
    if st.button("Reload reports"):
        st.rerun()
    st.info("To create new reports, run `python main.py optimize ...` from a terminal. Dashboard is read-only.")

path=Path(root)/"BTCUSD"/timeframe/"walk_forward.json"
if not path.is_file():
    st.warning(f"No report found: {path}")
    st.code("python main.py optimize --source demo_data --output results --timeframes 5m")
    st.stop()
try:
    obj=json.loads(path.read_text(encoding="utf-8"))
except (OSError,json.JSONDecodeError) as exc:
    st.error(f"Cannot read the report: {exc}")
    st.stop()

summary=obj["summary"]
a,b,c,d=st.columns(4)
a.metric("Evaluated folds",f"{summary['folds_evaluated']} / {summary['folds_total']}")
b.metric("Compounded test return",f"{summary['oos_compounded_return_pct']:+.2f}%")
c.metric("Positive test folds",f"{summary['oos_positive_fold_pct']:.1f}%" if summary['oos_positive_fold_pct'] is not None else "N/A")
d.metric("Average train–test gap",f"{summary['average_train_to_test_gap_pct_points']:+.2f} pp" if summary['average_train_to_test_gap_pct_points'] is not None else "N/A")

if obj.get("data_origin") == "SYNTHETIC_DEMO":
    st.warning("SYNTHETIC example prices — these are NOT real BTC market results. The model omits funding, liquidation, real fills, and Delta settlement.")
else:
    st.warning("User-supplied historical data (not independently verified). This simplified backtest omits funding, liquidation, real fills, and Delta settlement. No profitability claim.")

tabs=st.tabs(["Out-of-Sample Equity","Fold Comparison","Chosen Parameters","Methodology & JSON"])
with tabs[0]:
    st.subheader("Stitched out-of-sample test equity")
    curve=pd.DataFrame(obj.get("oos_equity_curve",[]))
    if curve.empty:
        st.info("No folds passed the minimum-trades validation requirement.")
    else:
        fig=go.Figure()
        for fold,frame in curve.groupby("fold",sort=True):
            fig.add_trace(go.Scatter(x=frame["time_utc"],y=frame["oos_equity_usd"],mode="lines",name=f"Test fold {fold}"))
        fig.update_layout(xaxis_title="UTC",yaxis_title="Simulated equity (USD)",hovermode="x unified",height=440)
        st.plotly_chart(fig,use_container_width=True)
        st.caption("Each test segment compounds on the previous test segment. Only evaluated test windows are included; a skipped fold means the curve is discontinuous in time.")
with tabs[1]:
    st.subheader("Training vs validation vs unseen testing")
    selected=[]
    for f in obj["folds"]:
        if f["status"]!="EVALUATED": continue
        selected.append({"fold":f["fold"],"train_pct":f["train"]["net_return_pct"],"validation_pct":f["validation"]["net_return_pct"],"test_pct":f["test"]["net_return_pct"],"test_drawdown_pct":f["test"]["max_drawdown_pct"],"test_trades":f["test"]["closed_trades"]})
    if selected:
        frame=pd.DataFrame(selected)
        st.dataframe(frame,use_container_width=True,hide_index=True)
        melted=frame.melt(id_vars=["fold"],value_vars=["train_pct","validation_pct","test_pct"],var_name="split",value_name="return_pct")
        bars=go.Figure()
        for split_name,grp in melted.groupby("split",sort=True):
            bars.add_trace(go.Bar(x=grp["fold"],y=grp["return_pct"],name=split_name))
        bars.update_layout(barmode="group",xaxis_title="Fold",yaxis_title="Return (%)",height=360)
        st.plotly_chart(bars,use_container_width=True)
    else:
        st.info("No evaluated folds to display.")
with tabs[2]:
    st.subheader("Parameters chosen without looking at test data")
    rows=[]
    for f in obj["folds"]:
        if f["status"]!="EVALUATED": continue
        p=f["parameters"]
        rows.append({"fold":f["fold"],"fast EMA":p["fast_ema"],"slow EMA":p["slow_ema"],"RSI threshold":p["rsi_threshold"],"train bars":f["ranges"]["train"]["bars"],"validation bars":f["ranges"]["validation"]["bars"],"test bars":f["ranges"]["test"]["bars"]})
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    if rows:
        fold_idx=st.selectbox("Inspect fold",[r["fold"] for r in rows])
        record=next(f for f in obj["folds"] if f["fold"]==fold_idx)
        st.json({"ranges":record["ranges"],"selected":record["parameters"],"shortlisted":record["shortlisted"]})
with tabs[3]:
    st.markdown("""**Rolling walk-forward sequence**

1. Optimize 8 EMA + RSI candidates on the **training** block only.
2. Select the best of the top 3 training candidates based on the **validation** block.
3. Freeze the chosen settings and evaluate them exactly once on the **test** block.
4. Roll forward; do not reuse test results for parameter tuning.

Signals use **closed candle** data; entries occur on the **following candle open**. Fees, GST, half-spread and slippage are charged per change of exposure. Each split starts flat, and any position closes at its final candle close. Models are simplified and illustrative.

A large positive training return with a negative test return is a potential sign of overfitting. A single successful test period does not establish trading edge.""")
    st.json({"config":obj["config"],"costs":obj["costs"],"candidate_grid":obj["candidate_grid"],"notes":obj["notes"]})
    st.download_button("Download full JSON report",data=json.dumps(obj,indent=2),file_name=f"BTCUSD_{timeframe}_walk_forward.json",mime="application/json")
