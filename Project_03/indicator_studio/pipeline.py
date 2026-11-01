"""Calculate indicators from Project 2 clean monthly JSON, without changing source."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from .config import INDICATOR_FIELDS, SYMBOL, TIMEFRAMES
from .indicators import IndicatorEngine
from .json_files import find_candle_base, monthly_files, read_rows, utc_timestamp, write_json


def analyze(source: str | Path, output: str | Path = "data", *, timeframes: list[str] | None = None) -> list[dict]:
    base = find_candle_base(source)
    source_root = Path(source).expanduser().resolve()
    destination = Path(output).expanduser().resolve()
    if destination == source_root or destination.is_relative_to(source_root):
        raise ValueError("Output must be a separate folder, outside the input source directory.")
    selected = timeframes or list(TIMEFRAMES)
    reports = []
    for tf in selected:
        if tf not in TIMEFRAMES:
            raise ValueError(f"Unknown timeframe: {tf}")
        files = monthly_files(base, tf)
        if not files:
            print(f"{tf}: no monthly input files; skipped")
            continue
        engine = IndicatorEngine()
        prev_time = None
        first_time = None
        gaps = 0
        gap_ranges = []
        rows_processed = 0
        ready = {field: 0 for field in INDICATOR_FIELDS}
        generated = set()
        for path in files:
            results = []
            for index, row in enumerate(read_rows(path)):
                try:
                    timestamp = utc_timestamp(row, tf)
                    if timestamp.strftime("%Y-%m") != path.stem:
                        raise ValueError("timestamp belongs to a different month")
                    if prev_time is not None:
                        seconds = int((timestamp - prev_time).total_seconds())
                        interval = TIMEFRAMES[tf]
                        if seconds <= 0:
                            raise ValueError("duplicate or out-of-order timestamp")
                        if seconds != interval:
                            if seconds % interval != 0:
                                raise ValueError("inconsistent timestamp interval")
                            missing = seconds // interval - 1
                            gaps += missing
                            if len(gap_ranges) < 100:
                                gap_ranges.append({
                                    "after": prev_time.isoformat().replace("+00:00", "Z"),
                                    "before": timestamp.isoformat().replace("+00:00", "Z"),
                                    "missing_candles": missing,
                                })
                            engine = IndicatorEngine()  # avoid indicators silently spanning missing candles
                    if first_time is None:
                        first_time = timestamp
                    prev_time = timestamp
                    indicators = engine.update(row)
                    normalized = {
                        "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
                        **{k: float(row[k]) for k in ("open", "high", "low", "close", "volume")},
                        **indicators,
                    }
                    results.append(normalized)
                    rows_processed += 1
                    for name, value in indicators.items():
                        if value is not None:
                            ready[name] += 1
                except (ValueError, TypeError, KeyError) as error:
                    raise ValueError(f"{path.name} row {index + 1}: {error}") from error
            target = destination / "indicators" / SYMBOL / tf / path.name
            write_json(target, results)
            generated.add(path.name)
        # Remove stale generated output months if input was shortened on a rerun.
        result_folder = destination / "indicators" / SYMBOL / tf
        for p in monthly_files(destination / "indicators" / SYMBOL, tf):
            if p.name not in generated:
                p.unlink()
        is_demo = (source_root / "SYNTHETIC_DATA_NOTICE.json").exists() or (source_root.parent / "SYNTHETIC_DATA_NOTICE.json").exists() or "demo" in source_root.name.lower()
        report = {
            "data_origin": "SYNTHETIC_DEMO" if is_demo else "EXTERNAL_JSON_NOT_VERIFIED",
            "symbol": SYMBOL, "timeframe": tf, "source": str(base),
            "rows": rows_processed, "missing_candle_slots": gaps,
            "gap_examples": gap_ranges, "indicator_ready_rows": ready,
            "first_candle": first_time.isoformat().replace("+00:00", "Z") if first_time else None,
            "last_candle": prev_time.isoformat().replace("+00:00", "Z") if prev_time else None,
            "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "notes": "Warm-up values are null. Indicator calculations restart after missing intervals. Synthetic demo prices are NOT live Delta prices.",
        }
        write_json(destination / "reports" / f"{SYMBOL}_{tf}_indicators.json", report)
        reports.append(report)
        print(f"{tf}: processed {rows_processed:,} candles, {gaps:,} missing slots; output -> {result_folder}")
    return reports
