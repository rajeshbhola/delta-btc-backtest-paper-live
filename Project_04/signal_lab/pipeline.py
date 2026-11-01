"""One-file-at-a-time processing, spanning monthly boundaries safely."""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .config import SYMBOL, TIMEFRAMES, SignalConfig
from .json_files import find_indicator_base, monthly_files, read_rows, parse_candle, save_json
from .strategy import SignalGenerator


def _iso(t: datetime | None) -> str | None:
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if t else None


def data_origin(source: Path) -> str:
    marker = source / "SYNTHETIC_DATA_NOTICE.json"
    if marker.exists():
        return "SYNTHETIC_DEMO"
    for p in sorted((source / "reports").glob("BTCUSD_*_indicators.json")):
        try:
            value = json.loads(p.read_text(encoding="utf-8")).get("data_origin")
            if value == "SYNTHETIC_DEMO":
                return value
        except (ValueError, OSError):
            pass
    return "EXTERNAL_INDICATOR_JSON_NOT_VERIFIED"


def generate(
    source: str | Path,
    output: str | Path = "output",
    *,
    timeframes: list[str] | None = None,
    config: SignalConfig | None = None,
    as_of: datetime | None = None,
) -> list[dict]:
    source = Path(source).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    if source == output or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Source and output folders must be separate, non-overlapping directories")
    base = find_indicator_base(source)
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("--as-of-utc must include an explicit UTC time offset")
    as_of = as_of.astimezone(timezone.utc)
    selected = timeframes or list(TIMEFRAMES)
    config = config or SignalConfig()
    origin = data_origin(source)
    summaries: list[dict] = []
    for tf in selected:
        if tf not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {tf}")
        files = monthly_files(base, tf)
        if not files:
            print(f"{tf}: no data found; skipped")
            continue
        seconds = TIMEFRAMES[tf]
        strategy = SignalGenerator(config)
        prev_time: datetime | None = None
        first_time: datetime | None = None
        last_time: datetime | None = None
        counts = Counter()
        reasons = Counter()
        gap_count = 0
        incomplete_count = 0
        examples = []
        saved_months = set()
        for file in files:
            values = []
            for i, row in enumerate(read_rows(file), start=1):
                try:
                    timestamp = parse_candle(row, tf)
                    if timestamp.strftime("%Y-%m") != file.stem:
                        raise ValueError("Candle stored under the wrong month")
                    if prev_time is not None and timestamp <= prev_time:
                        raise ValueError("Timestamp duplicate or out of order")
                    if timestamp + timedelta(seconds=seconds) > as_of:
                        incomplete_count += 1
                        continue
                    gap = prev_time is not None and (timestamp - prev_time).total_seconds() != seconds
                    if gap:
                        delta = int((timestamp - prev_time).total_seconds())
                        if delta % seconds:
                            raise ValueError("Timestamp separation not aligned with timeframe")
                        gap_count += delta // seconds - 1
                    signal_row = strategy.update(row, timestamp, seconds, gap=gap)
                    if signal_row["signal"] in ("BUY", "SELL") and len(examples) < 100:
                        examples.append({
                            "time": signal_row["decision_time_utc"],
                            "signal": signal_row["signal"],
                            "reason": signal_row["reason"],
                        })
                    values.append(signal_row)
                    counts[signal_row["signal"]] += 1
                    reasons[signal_row["reason"]] += 1
                    first_time = first_time or timestamp
                    last_time = prev_time = timestamp
                except (KeyError, TypeError, ValueError, OverflowError) as error:
                    raise ValueError(f"{file} row {i}: {error}") from error
            save_json(output / "signals" / SYMBOL / tf / file.name, values)
            saved_months.add(file.name)
        for stale in monthly_files(output / "signals" / SYMBOL, tf):
            if stale.name not in saved_months:
                stale.unlink()
        report = {
            "symbol": SYMBOL, "timeframe": tf, "data_origin": origin,
            "first_candle": _iso(first_time), "last_candle": _iso(last_time),
            "as_of_utc": _iso(as_of),
            "total_rows": sum(counts.values()),
            "signals": {kind: counts[kind] for kind in ("BUY", "SELL", "HOLD")},
            "reasons": dict(sorted(reasons.items())),
            "missing_candle_slots": gap_count,
            "incomplete_candles_skipped": incomplete_count,
            "signal_examples": examples,
            "rules": {
                "ema_fast": 9, "ema_slow": 21, "rsi_period": 14,
                "buy_rsi_min": config.rsi_buy_min, "buy_rsi_max": config.rsi_buy_max,
                "sell_rsi_min": config.rsi_sell_min, "sell_rsi_max": config.rsi_sell_max,
            },
            "generated_at_utc": _iso(datetime.now(timezone.utc)),
            "note": "Signals use completed candles only. BUY/SELL are research labels, NOT orders, profits or position instructions.",
        }
        save_json(output / "reports" / f"{SYMBOL}_{tf}_signals.json", report)
        summaries.append(report)
        print(f"{tf:>3}: rows={report['total_rows']:,} BUY={counts['BUY']} SELL={counts['SELL']} gaps={gap_count}")
    return summaries
