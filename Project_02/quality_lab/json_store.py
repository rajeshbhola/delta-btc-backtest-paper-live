"""Monthly JSON file storage; no database and no Parquet dependency."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from collections import defaultdict
from typing import Iterable

from .config import SYMBOL, TIMEFRAMES

MONTH_PATTERN = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])\.json$")


def atomic_json(path: Path, data: object) -> None:
    """Write valid JSON to a temporary file, then atomically replace destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".writing-", suffix=".tmp", delete=False) as f:
            name = f.name
            json.dump(data, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def read_list(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, list):
        raise ValueError(f"Expected a JSON array in {path}")
    if any(not isinstance(row, dict) for row in value):
        raise ValueError(f"Expected candle objects in {path}")
    return value


class JsonStore:
    def __init__(self, root: str | Path = "data"):
        self.root = Path(root)

    def folder(self, layer: str, timeframe: str) -> Path:
        if layer not in ("raw", "clean", "repairs"):
            raise ValueError("Invalid data layer")
        if timeframe not in TIMEFRAMES:
            raise ValueError("Invalid timeframe")
        return self.root / layer / SYMBOL / timeframe

    def files(self, layer: str, timeframe: str) -> list[Path]:
        directory = self.folder(layer, timeframe)
        return sorted(p for p in directory.glob("*.json") if MONTH_PATTERN.fullmatch(p.name))

    def read(self, layer: str, timeframe: str) -> list[dict]:
        rows = []
        for p in self.files(layer, timeframe):
            rows.extend(read_list(p))
        return rows

    def replace_months(self, layer: str, timeframe: str, rows: Iterable[dict], *, clear_old: bool = False) -> int:
        """Writes exact input rows, preserving raw duplicates/invalid fields for analysis.

        Each row must have a parseable timestamp_utc for monthly routing.
        """
        from .config import parse_utc
        groups: dict[str, list[dict]] = defaultdict(list)
        total = 0
        for row in rows:
            month = parse_utc(str(row["timestamp_utc"])).strftime("%Y-%m")
            groups[month].append(row)
            total += 1
        folder = self.folder(layer, timeframe)
        for month, group in groups.items():
            atomic_json(folder / f"{month}.json", group)
        if clear_old:
            for path in self.files(layer, timeframe):
                if path.stem not in groups:
                    path.unlink()
        return total

    def merge_by_timestamp(self, layer: str, timeframe: str, rows: list[dict]) -> int:
        """Upsert API-fetched rows into raw/repairs using their UTC timestamps.

        No user-supplied raw file is modified by the cleaner. The explicit
        download command can update raw, while repair writes only to repairs.
        """
        from .config import parse_utc
        by_month: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            month = parse_utc(str(row["timestamp_utc"])).strftime("%Y-%m")
            by_month[month].append(row)
        for month, new_rows in by_month.items():
            path = self.folder(layer, timeframe) / f"{month}.json"
            existing = read_list(path) if path.exists() else []
            keyed = {str(r.get("timestamp_utc")): r for r in existing}
            for item in new_rows:
                keyed[str(item["timestamp_utc"])] = item
            atomic_json(path, list(keyed.values()))
        return len(rows)

    def report_path(self, timeframe: str) -> Path:
        return self.root / "reports" / f"{SYMBOL}_{timeframe}_quality.json"

    def read_report(self, timeframe: str) -> dict | None:
        path = self.report_path(timeframe)
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as f:
            return json.load(f)


def import_project1(source: str | Path, store: JsonStore, *, overwrite: bool = False) -> dict[str, int]:
    """Copy Project 1's BTCUSD/<tf>/YYYY-MM.json without changing source files."""
    import shutil
    source = Path(source).expanduser().resolve()
    candidates = [source / "BTCUSD", source / "candles" / "BTCUSD", source / "data" / "candles" / "BTCUSD"]
    base = next((p for p in candidates if p.is_dir()), None)
    if base is None:
        raise FileNotFoundError("Expected <source>/BTCUSD, <source>/candles/BTCUSD, or <source>/data/candles/BTCUSD")
    result = {}
    for tf in TIMEFRAMES:
        copied = 0
        for path in sorted((base / tf).glob("*.json")):
            if not MONTH_PATTERN.fullmatch(path.name):
                continue
            read_list(path)  # fail clearly on corrupt source files
            destination = store.folder("raw", tf) / path.name
            if destination.resolve() == path.resolve():
                raise ValueError("Source and destination must be separate directories")
            if destination.exists() and not overwrite:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            copied += 1
        result[tf] = copied
    return result
