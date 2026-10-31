"""Compatibility entry point for the original Project 1 function."""
from datetime import datetime
from delta_collector.rest import DeltaRestClient


def fetch_candles(symbol: str, timeframe: str, start: datetime, end: datetime):
    """Download closed public candles for [start, end) as a pandas DataFrame."""
    with DeltaRestClient() as client:
        return client.fetch_candles(symbol, timeframe, start, end)


if __name__ == "__main__":
    from main import main
    main()
