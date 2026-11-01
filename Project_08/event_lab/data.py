"""Read monthly JSON candle and Project 4 signal files without broker access."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

INTERVALS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}


def parse_dt(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def source_folder(root, tf, kind):
    root = Path(root).expanduser()
    prefixes = (["candles", "clean", "indicators"] if kind == "candles" else ["signals"])
    choices = [root / prefix / "BTCUSD" / tf for prefix in prefixes]
    choices += [root / "BTCUSD" / tf, root / tf]
    for path in choices:
        if path.is_dir() and any(path.glob("*.json")):
            return path
    raise FileNotFoundError(f"No {kind} JSON for {tf} found under {root}; checked {choices}")


def read_rows(root, tf, kind):
    folder = source_folder(root, tf, kind)
    rows = []
    for path in sorted(folder.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected JSON list in {path}")
        rows.extend(payload)
    return rows


def load_candles(root, tf, max_candles=3000):
    if tf not in INTERVALS:
        raise ValueError(f"Unsupported timeframe: {tf}")
    rows = read_rows(root, tf, "candles")
    by_time = {}
    for row in rows:
        t = parse_dt(row["timestamp_utc"])
        if t.timestamp() % INTERVALS[tf] != 0:
            raise ValueError(f"Unaligned candle time {iso(t)}")
        o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
        v = float(row.get("volume", 0))
        if min(o, h, l, c) <= 0 or v < 0 or h < max(o, c, l) or l > min(o, c, h):
            raise ValueError(f"Invalid OHLCV candle: {iso(t)}; clean with Project 2 first")
        if t in by_time:
            raise ValueError(f"Duplicate candle timestamp: {iso(t)}; clean with Project 2 first")
        by_time[t] = {"timestamp_utc": iso(t), "open": o, "high": h, "low": l, "close": c, "volume": v}
    ordered = [by_time[t] for t in sorted(by_time)]
    if max_candles and max_candles > 0:
        ordered = ordered[-max_candles:]
    if not ordered:
        raise ValueError("No candles available")
    return ordered


def load_signals(root, tf, candles):
    # Signal values are keyed by candle opening time, with decision at candle close.
    interval = timedelta(seconds=INTERVALS[tf])
    allowed_times = {row["timestamp_utc"] for row in candles}
    signals = {}
    for row in read_rows(root, tf, "signals"):
        signal = str(row.get("signal", "HOLD")).upper()
        if signal not in {"BUY", "SELL", "HOLD"}:
            raise ValueError(f"Unsupported signal {signal}")
        begin = parse_dt(row["timestamp_utc"])
        timestamp = iso(begin)
        if timestamp not in allowed_times:
            continue
        expected_decision = begin + interval
        if row.get("decision_time_utc") is not None and parse_dt(row["decision_time_utc"]) != expected_decision:
            raise ValueError(f"Signal decision timestamp mismatch at {timestamp}")
        if timestamp in signals:
            raise ValueError(f"Duplicate signal at {timestamp}")
        signals[timestamp] = {"signal": signal, "reason": row.get("reason", ""), "gap_before": bool(row.get("gap_before", False))}
    return signals


def dump_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(path)
