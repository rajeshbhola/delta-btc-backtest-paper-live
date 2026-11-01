"""Small read-only chart/audit helpers. No trading signals generated here."""
import pandas as pd
from .config import TIMEFRAMES


def audit_window(df: pd.DataFrame, timeframe: str) -> dict:
    if timeframe not in TIMEFRAMES:
        raise ValueError("Unknown timeframe")
    if df.empty:
        return {"rows": 0, "gap_slots": 0, "gap_examples_utc": [], "invalid_ohlc": 0, "invalid_volume": 0}
    timestamps = pd.to_datetime(df.timestamp_utc, utc=True).sort_values().drop_duplicates()
    delta = pd.Timedelta(seconds=TIMEFRAMES[timeframe])
    diffs = timestamps.diff().dropna()
    counts = [max(0, int(round(d / delta)) - 1) for d in diffs if d > delta]
    gap_examples = [t.isoformat() for t, d in zip(timestamps.iloc[1:], diffs) if d > delta][:10]
    invalid_ohlc = 0
    if all(c in df for c in ("open", "high", "low", "close")):
        x = df[["open", "high", "low", "close"]]
        invalid_ohlc = int((
            x.isna().any(axis=1) |
            (x <= 0).any(axis=1) |
            (x.high < x[["open", "close", "low"]].max(axis=1)) |
            (x.low > x[["open", "close", "high"]].min(axis=1))
        ).sum())
    invalid_volume = int((df.volume.isna() | (df.volume < 0)).sum()) if "volume" in df else 0
    return {"rows": len(df), "gap_slots": sum(counts), "gap_examples_utc": gap_examples,
            "invalid_ohlc": invalid_ohlc, "invalid_volume": invalid_volume}


def signal_summary(signals: pd.DataFrame) -> dict:
    if signals.empty or "signal" not in signals:
        return {"BUY": 0, "SELL": 0, "HOLD": 0}
    counts = signals.signal.astype(str).str.upper().value_counts()
    return {key: int(counts.get(key, 0)) for key in ("BUY", "SELL", "HOLD")}


def decisions_for_chart(signals: pd.DataFrame, earliest, latest) -> pd.DataFrame:
    if signals.empty or not {"signal", "decision_time_utc", "close"}.issubset(signals.columns):
        return pd.DataFrame()
    result = signals[signals.signal.isin(["BUY", "SELL"])].copy()
    result["decision_time_utc"] = pd.to_datetime(result.decision_time_utc, utc=True, errors="coerce")
    result = result.dropna(subset=["decision_time_utc", "close"])
    return result[(result.decision_time_utc >= earliest) & (result.decision_time_utc <= latest)].copy()
