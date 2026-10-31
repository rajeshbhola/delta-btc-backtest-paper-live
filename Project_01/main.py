"""Project 1 (JSON + dashboard): historical REST backfill + live WebSocket monitoring.

No trading permissions, private endpoints, credentials or order placement.
"""
from __future__ import annotations

import argparse
import logging
import queue
import time
from datetime import timedelta
from pathlib import Path

from delta_collector.config import DEFAULT_TIMEFRAMES, INTERVAL_SECONDS, closed_end, utc_now
from delta_collector.live import DeltaPublicCandleWebSocket
from delta_collector.rest import DeltaRestClient
from delta_collector.service import CandleService
from delta_collector.storage import CandleStore
from delta_collector.status import CollectorStatus, now_iso

LOG = logging.getLogger("delta_btc")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delta India public BTCUSD candle collector")
    parser.add_argument("command", choices=["backfill", "live", "audit", "export-csv"],
                        help="REST historical backfill, WS+REST live, gap audit, or CSV export")
    parser.add_argument("--symbol", default="BTCUSD")
    parser.add_argument("--timeframes", nargs="+", choices=DEFAULT_TIMEFRAMES, default=list(DEFAULT_TIMEFRAMES))
    parser.add_argument("--days", type=int, default=365,
                        help="Backfill/audit window in days; default=365")
    parser.add_argument("--data-dir", type=Path, default=Path("data/candles"))
    parser.add_argument("--report-dir", type=Path, default=Path("data/reports"))
    parser.add_argument("--csv-dir", type=Path, default=Path("data/csv"))
    parser.add_argument("--export-csv", action="store_true", help="Optional CSV export; primary storage is JSON")
    parser.add_argument("--pause", type=float, default=0.25,
                        help="Pause between successful REST requests in seconds")
    parser.add_argument("--poll-seconds", type=int, default=60,
                        help="Periodic REST reconciliation interval during live mode")
    parser.add_argument("--warmup-days", type=int, default=1,
                        help="Live startup lookback when no saved candles exist")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.days <= 0 or args.warmup_days <= 0 or args.poll_seconds < 10 or args.pause < 0:
        parser.error("days, warmup-days must be positive; poll-seconds >= 10; pause >= 0")
    args.timeframes = tuple(dict.fromkeys(args.timeframes))
    return args


def export_csv(store: CandleStore, symbol: str, timeframes: tuple[str, ...], csv_dir: Path):
    csv_dir.mkdir(parents=True, exist_ok=True)
    for tf in timeframes:
        df = store.load(symbol, tf)
        path = csv_dir / f"{symbol}_{tf}.csv"
        df.to_csv(path, index=False)
        LOG.info("Exported %s candles -> %s", len(df), path)


def audit(store: CandleStore, symbol: str, timeframes: tuple[str, ...], days: int,
          report_dir: Path):
    now = utc_now()
    for tf in timeframes:
        end = closed_end(now, tf)
        start = end - timedelta(days=days)
        report = store.audit(symbol, tf, start, end, report_dir=report_dir)
        LOG.info("AUDIT %-3s %s/%s candles; missing=%s; first_missing=%s", tf,
                 report["actual"], report["expected"], report["missing"],
                 report["first_missing"])
    LOG.info("Missing-timestamp JSON reports written under %s", report_dir)


def run_live(service: CandleService, timeframes: tuple[str, ...], poll_seconds: int,
             warmup_days: int):
    for tf in timeframes:
        LOG.info("Initial REST sync: %s", tf)
        service.sync_recent(tf, lookback_days_if_empty=warmup_days)

    status = service.status
    refresh_queue: queue.Queue[str] = queue.Queue(maxsize=100)
    last_preview: dict[str, float] = {}
    last_status: dict[str, float] = {}

    def preview(event: dict):
        tf = event["timeframe"]
        if status and time.monotonic() - last_status.get(tf, 0) >= 5:
            status.websocket(last_message_utc=event["event_time_utc"].isoformat(),
                             last_price=event["close"], timeframe=tf)
            last_status[tf] = time.monotonic()
        if time.monotonic() - last_preview.get(tf, 0) >= 60:
            LOG.info("WS provisional %s close=%.2f at %s (NOT persisted as final)",
                     tf, event["close"], event["event_time_utc"].isoformat())
            last_preview[tf] = time.monotonic()

    ws = DeltaPublicCandleWebSocket(service.symbol, timeframes, refresh_queue, callback=preview,
                                   connection_callback=(lambda state: status.websocket(state=state))
                                   if status else None)
    ws.start()
    next_safety_poll = time.monotonic() + poll_seconds
    last_refresh: dict[str, float] = {}
    LOG.info("WS started; REST will reconcile completed candles at boundaries and every %ss", poll_seconds)
    try:
        while True:
            timeout = max(0, next_safety_poll - time.monotonic())
            try:
                tf = refresh_queue.get(timeout=timeout)
                # A small cooldown avoids bursts when reconnection crosses a boundary.
                if time.monotonic() - last_refresh.get(tf, 0) > 5:
                    service.sync_recent(tf, lookback_days_if_empty=warmup_days)
                    last_refresh[tf] = time.monotonic()
            except queue.Empty:
                pass
            if time.monotonic() >= next_safety_poll:
                for tf in timeframes:
                    service.sync_recent(tf, lookback_days_if_empty=warmup_days)
                next_safety_poll = time.monotonic() + poll_seconds
    except KeyboardInterrupt:
        LOG.info("Stopping live collector safely...")
    finally:
        ws.stop()


def main():
    args = parse_args()
    logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s",
                        level=logging.DEBUG if args.verbose else logging.INFO)
    store = CandleStore(args.data_dir)
    status = CollectorStatus(args.data_dir.parent / "status.json")
    status.update(symbol=args.symbol, mode=args.command, state="running", started_utc=now_iso(),
                  last_error=None, current_timeframe=None,
                  websocket={"state": "disconnected"}, timeframes={})
    try:
        execute(args, store, status)
    except KeyboardInterrupt:
        status.update(state="stopped")
        raise
    except Exception as exc:
        status.update(state="error", last_error=str(exc))
        raise
    else:
        status.update(state="completed" if args.command != "live" else "stopped")


def execute(args, store, status):
    if args.command == "export-csv":
        export_csv(store, args.symbol, args.timeframes, args.csv_dir)
        return
    if args.command == "audit":
        audit(store, args.symbol, args.timeframes, args.days, args.report_dir)
        return
    with DeltaRestClient(request_pause=args.pause) as rest:
        service = CandleService(rest, store, symbol=args.symbol, status=status)
        if args.command == "backfill":
            service.backfill(args.timeframes, days=args.days)
            audit(store, args.symbol, args.timeframes, args.days, args.report_dir)
            if args.export_csv:
                export_csv(store, args.symbol, args.timeframes, args.csv_dir)
        elif args.command == "live":
            run_live(service, args.timeframes, args.poll_seconds, args.warmup_days)


if __name__ == "__main__":
    main()
