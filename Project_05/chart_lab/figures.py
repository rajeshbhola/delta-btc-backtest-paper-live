"""Plotly figures. No external API calls and no trading actions."""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .analytics import decisions_for_chart

COLORS = {"ema_9": "#38bdf8", "ema_21": "#f59e0b", "ema_50": "#a78bfa", "sma_20": "#34d399", "sma_50": "#f472b6",
          "bb_upper": "#94a3b8", "bb_middle": "#64748b", "bb_lower": "#94a3b8"}


def make_price_figure(data: pd.DataFrame, signals: pd.DataFrame | None = None,
                      overlays: list[str] | None = None, volume: bool = True) -> go.Figure:
    overlays = overlays or []
    if data.empty or not {"timestamp_utc", "open", "high", "low", "close"}.issubset(data.columns):
        return go.Figure(layout={"title": "No OHLC candles in selected window"})
    fig = make_subplots(rows=2 if volume else 1, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=[0.78, 0.22] if volume else None)
    fig.add_trace(go.Candlestick(
        x=data.timestamp_utc, open=data.open, high=data.high, low=data.low, close=data.close,
        name="BTCUSD candles", increasing_line_color="#22c55e", decreasing_line_color="#ef4444"
    ), row=1, col=1)
    for col in overlays:
        if col in data:
            fig.add_trace(go.Scatter(x=data.timestamp_utc, y=data[col], name=col.upper(), mode="lines",
                                     line={"width": 1.5, "color": COLORS.get(col)}), row=1, col=1)
    if signals is not None and not signals.empty and len(data):
        displayed = decisions_for_chart(signals, data.timestamp_utc.min(),
                                        data.timestamp_utc.max() + pd.Timedelta(hours=4))
        for sig, color, marker in [("BUY", "#16a34a", "triangle-up"), ("SELL", "#dc2626", "triangle-down")]:
            items = displayed[displayed.signal == sig]
            if len(items):
                reasons = items.reason.fillna("") if "reason" in items else [""] * len(items)
                fig.add_trace(go.Scatter(x=items.decision_time_utc, y=items.close, mode="markers", name=sig,
                              marker={"color": color, "symbol": marker, "size": 13,
                                      "line": {"color": "white", "width": 1}},
                              customdata=list(zip(items.timestamp_utc.astype(str), reasons)),
                              hovertemplate="Decision: %{x}<br>Signal price: %{y:.2f}<br>Source candle: %{customdata[0]}<br>Reason: %{customdata[1]}<extra></extra>"),
                              row=1, col=1)
    if volume and "volume" in data:
        rising = data.close >= data.open
        colors = ["#22c55e" if x else "#ef4444" for x in rising]
        fig.add_trace(go.Bar(x=data.timestamp_utc, y=data.volume, name="Volume",
                             marker_color=colors, opacity=0.65), row=2, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="BTCUSD price", row=1, col=1)
    fig.update_xaxes(title_text="UTC time", row=2 if volume else 1, col=1)
    fig.update_layout(template="plotly_dark", height=730 if volume else 590,
                      xaxis_rangeslider_visible=False, hovermode="x unified", legend={"orientation": "h", "y": 1.09})
    return fig


def make_oscillators(data: pd.DataFrame, selected: list[str]) -> go.Figure:
    specs = [name for name in ["RSI", "MACD", "ATR"] if name in selected]
    if not specs or data.empty:
        return go.Figure(layout={"title": "No oscillator selected"})
    fig = make_subplots(rows=len(specs), cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=specs)
    for r, name in enumerate(specs, 1):
        if name == "RSI" and "rsi_14" in data:
            fig.add_trace(go.Scatter(x=data.timestamp_utc, y=data.rsi_14, name="RSI 14", line_color="#facc15"), row=r, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="#fb7185", row=r, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="#34d399", row=r, col=1)
            fig.update_yaxes(range=[0,100], row=r, col=1)
        elif name == "MACD" and "macd" in data:
            for k, color in [("macd", "#38bdf8"), ("macd_signal", "#f59e0b")]:
                if k in data:
                    fig.add_trace(go.Scatter(x=data.timestamp_utc, y=data[k], name=k, line_color=color), row=r, col=1)
            if "macd_histogram" in data:
                fig.add_trace(go.Bar(x=data.timestamp_utc, y=data.macd_histogram, name="MACD histogram",
                                     marker_color="#64748b", opacity=0.65), row=r, col=1)
        elif name == "ATR" and "atr_14" in data:
            fig.add_trace(go.Scatter(x=data.timestamp_utc, y=data.atr_14, name="ATR 14", line_color="#c084fc"), row=r, col=1)
    fig.update_layout(template="plotly_dark", height=260 * len(specs) + 80, hovermode="x unified",
                      legend={"orientation": "h", "y": 1.09})
    return fig
