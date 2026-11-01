"""Read-only Streamlit performance dashboard for Project 9 reports.

Run: python -m streamlit run dashboard.py
"""
from pathlib import Path
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from performance_lab.files import available_timeframes, load_report

st.set_page_config(page_title='BTC Strategy Performance Analyzer', page_icon='📊', layout='wide')
st.title('📊 BTC Strategy Performance Analyzer')
st.caption('Mini-Project 9 · Historical simulation · Delta BTCUSD · Data only, no broker connection')

with st.sidebar:
    st.header('Analysis dataset')
    source = st.radio('Choose reports', ['Bundled demonstration', 'My own reports'], label_visibility='visible')
    root = 'demo_reports' if source.startswith('Bundled') else st.text_input('Output/report folder', value='reports')
    tfs = available_timeframes(root)
    if not tfs:
        st.warning('No reports found. Run: python main.py analyze --input demo_project8 --output reports --timeframes 1m 5m 15m 1h 4h')
        st.stop()
    timeframe=st.selectbox('Timeframe', tfs, index=tfs.index('5m') if '5m' in tfs else 0)
    st.caption('Synthetic demonstration data is not historical BTC performance.')

try:
    report=load_report(root,timeframe)
except (ValueError, OSError, KeyError, TypeError) as exc:
    st.error(f'Unable to read report: {exc}')
    st.stop()

em=report['equity_metrics']; tm=report['trade_metrics']

def value(x,format_string='.2f',suffix=''):
    return f'{x:{format_string}}{suffix}' if isinstance(x,(int,float)) else 'N/A'

st.subheader(f'BTCUSD · {timeframe} · Performance summary')
cols=st.columns(5)
cols[0].metric('Total return', value(em['total_return_pct'],suffix='%'))
cols[1].metric('Max drawdown', value(em['max_drawdown_pct'],suffix='%'))
cols[2].metric('Sharpe', value(em['sharpe_ratio']))
cols[3].metric('Sortino', value(em['sortino_ratio']))
cols[4].metric('Profit factor', value(tm['profit_factor']))
cols=st.columns(5)
cols[0].metric('Closed trades', tm['closed_trades'])
cols[1].metric('Win rate', value(tm['win_rate_pct'],suffix='%'))
cols[2].metric('Expectancy / trade', '$'+value(tm['expectancy_usd_per_trade']))
cols[3].metric('Ending equity', '$'+value(em['ending_equity_usd']))
cols[4].metric('Data gaps', em['irregular_intervals'])

if report['warnings']:
    with st.expander(f'⚠️ {len(report["warnings"])} analysis notes and limitations', expanded=True):
        for message in report['warnings']:
            st.warning(message)

tab1,tab2,tab3,tab4,tab5=st.tabs(['Equity & drawdown','Trade analysis','Monthly returns','Compare timeframes','Learning guide'])

with tab1:
    equity=pd.DataFrame(report['equity_series'])
    equity['time_utc']=pd.to_datetime(equity['time_utc'],utc=True)
    chart=go.Figure()
    chart.add_trace(go.Scatter(x=equity['time_utc'],y=equity['equity_usd'],mode='lines',name='Strategy equity'))
    if equity['benchmark_equity_usd'].notna().any():
        chart.add_trace(go.Scatter(x=equity['time_utc'],y=equity['benchmark_equity_usd'],mode='lines',name='Zero-cost hold benchmark',line=dict(dash='dash')))
    chart.update_layout(title='Strategy equity vs illustrative gross buy-and-hold',xaxis_title='UTC time',yaxis_title='USD-equivalent equity',height=400)
    st.plotly_chart(chart,use_container_width=True)
    dd=go.Figure(go.Scatter(x=equity['time_utc'],y=equity['drawdown_pct'],fill='tozeroy',mode='lines',name='Drawdown'))
    dd.update_layout(title='Drawdown from previous equity peak',xaxis_title='UTC time',yaxis_title='Drawdown (%)',height=300)
    st.plotly_chart(dd,use_container_width=True)
    st.caption('Benchmark has no commissions, funding, slippage or leverage; it is context, not an investable Delta execution estimate.')
    st.download_button('Download analyzed equity JSON',data=json.dumps(report['equity_series'],indent=2),file_name=f'BTCUSD_{timeframe}_equity_analysis.json',mime='application/json')

with tab2:
    trades=pd.DataFrame(report['closed_trades'])
    if trades.empty:
        st.info('No closed trades in this dataset. Trade-based metrics are N/A.')
    else:
        a,b=st.columns(2)
        with a:
            fig=px.histogram(trades,x='net_pnl_usd',nbins=20,title='Closed trade PnL distribution')
            st.plotly_chart(fig,use_container_width=True)
        with b:
            bar=px.box(trades,x='side',y='net_pnl_usd',points='all',title='Closed trade PnL by direction')
            st.plotly_chart(bar,use_container_width=True)
        st.dataframe(trades,use_container_width=True,hide_index=True)
        st.download_button('Download closed trades JSON',data=json.dumps(report['closed_trades'],indent=2),file_name=f'BTCUSD_{timeframe}_closed_trades.json',mime='application/json')

with tab3:
    months=pd.DataFrame(report['monthly_returns'])
    if not months.empty:
        months[['year','month_number']]=months['month'].str.split('-',expand=True)
        pivot=months.pivot(index='year',columns='month_number',values='return_pct')
        fig=px.imshow(pivot, text_auto='.2f', aspect='auto',title='Monthly observed equity change (%)',color_continuous_scale='RdYlGn',color_continuous_midpoint=0)
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(months[['month','return_pct','start_equity_usd','end_equity_usd']],hide_index=True,use_container_width=True)
    st.caption('First month is measured from first observation; later months use the previous month-end equity. Partial months are not normalized.')

with tab4:
    compare=[]
    for tf in tfs:
        record=load_report(root,tf)
        e,t=record['equity_metrics'],record['trade_metrics']
        compare.append({'Timeframe':tf,'Return %':e['total_return_pct'],'Max DD %':e['max_drawdown_pct'],
                        'Sharpe':e['sharpe_ratio'],'Sortino':e['sortino_ratio'],
                        'Profit factor':t['profit_factor'],'Trades':t['closed_trades'],
                        'Interval gaps':e['irregular_intervals'],'Duration (days)':e['duration_days']})
    st.dataframe(pd.DataFrame(compare),use_container_width=True,hide_index=True)
    st.info('Different candle counts, backtest configurations, and data histories can make cross-timeframe comparisons misleading. Use aligned history and matching assumptions.')

with tab5:
    st.markdown('''### Formulas and interpretations

**Total return** = (last equity / first equity − 1) × 100. Uses the actual stored portfolio equity, not merely closed trades.

**Maximum drawdown** = most negative decline from a historical equity peak.

**Sharpe** = mean excess per-candle return / sample standard deviation × √(365 × 24 × 60 / timeframe minutes). Crypto annualization assumes 24/7 candles. Risk-free rate defaults to 0% annual. Missing intervals are excluded from this ratio rather than fabricating returns.

**Sortino** = mean excess return / downside deviation × the same annualization multiplier. Downside deviation uses negative excess returns against the risk-free target.

**Profit factor** = sum positive *net* closed-trade PnL / absolute sum negative *net* closed-trade PnL. Undefined when there are no losing trades.

**Expectancy** = average net closed-trade PnL. Win rate alone does not determine profitability.

**Calmar** = CAGR / absolute maximum drawdown (%). CAGR is suppressed for histories shorter than 30 days.

**Key limitations:** The ratios are highly unstable for short, synthetic, non-independent or very small samples. Project 8 already has simplified fills and does not model funding, liquidation or actual exchange settlement. Project 9 does not fix those limitations.
''')

st.caption('Educational analytics. No guarantee of returns. No exchange keys and no orders.')
