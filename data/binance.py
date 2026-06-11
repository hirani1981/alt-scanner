"""Binance public API client — universe discovery, klines, prices."""
import time
import logging
from typing import Optional

import httpx
import pandas as pd

# Use the OS certificate store (Windows Schannel / macOS Keychain) so that
# corporate or self-signed root CAs are trusted without extra configuration.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

logger = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com"


def _get(path: str, params: dict = None) -> dict | list:
    url = f"{BASE_URL}{path}"
    for attempt in range(4):
        if attempt > 0:
            delay = 2 ** attempt  # 2, 4, 8 seconds
            logger.warning("Retrying %s in %ds (attempt %d)", path, delay, attempt + 1)
            time.sleep(delay)
        try:
            resp = httpx.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                logger.warning("Rate limited on %s", path)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            if attempt == 3:
                raise
            logger.warning("HTTP %s on %s: %s", exc.response.status_code, path, exc)
    raise RuntimeError(f"Failed to fetch {path} after retries")


def get_usdt_pairs() -> list[dict]:
    """Return all active USDT spot pairs with symbol metadata."""
    data = _get("/api/v3/exchangeInfo")
    return [
        s for s in data["symbols"]
        if s["quoteAsset"] == "USDT"
        and s["status"] == "TRADING"
        and s["isSpotTradingAllowed"]
    ]


def get_24h_tickers() -> dict[str, dict]:
    """Return 24h ticker stats keyed by symbol."""
    data = _get("/api/v3/ticker/24hr")
    return {item["symbol"]: item for item in data}


# Binance hard cap on candles per klines request
_MAX_KLINES_PER_REQUEST = 1000


def _parse_klines(raw: list) -> pd.DataFrame:
    """Parse a raw klines payload into a date-indexed OHLCV frame."""
    df = pd.DataFrame(raw, columns=[
        "open_time", "open", "high", "low", "close",
        "base_volume", "close_time", "quote_volume",
        "num_trades", "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["date"] = df["open_time"].dt.normalize()

    for col in ("open", "high", "low", "close", "quote_volume"):
        df[col] = df[col].astype(float)

    df = df.set_index("date")[["open", "high", "low", "close", "quote_volume"]]
    df = df[~df.index.duplicated(keep="last")]
    return df.sort_index()


def _fetch_klines_paginated(
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: Optional[int] = None,
) -> list:
    """Page through /klines via startTime until the range is exhausted —
    the request cap is Binance's (1000), the total is the caller's."""
    out: list = []
    cursor = start_ms
    while True:
        params = {
            "symbol": symbol, "interval": interval,
            "startTime": cursor, "limit": _MAX_KLINES_PER_REQUEST,
        }
        if end_ms is not None:
            params["endTime"] = end_ms
        batch = _get("/api/v3/klines", params)
        if not batch:
            break
        out.extend(batch)
        if len(batch) < _MAX_KLINES_PER_REQUEST:
            break
        cursor = batch[-1][0] + 1
    return out


def get_klines(
    symbol: str,
    interval: str = "1d",
    limit: int = 400,
    include_partial: bool = False,
) -> Optional[pd.DataFrame]:
    """
    Fetch the last `limit` daily candles for symbol (paginated — `limit` may
    exceed Binance's 1000-per-request cap; the config drives history depth).

    Returns a DataFrame indexed by UTC date (open_time normalised to midnight)
    with columns: open, high, low, close, quote_volume.

    include_partial=False (EOD runs): the current partial candle is dropped —
    only fully closed candles are returned (no look-ahead).
    include_partial=True (intraday runs): today's live candle is kept as the
    final row; the metrics layer uses it for current price / volume-so-far
    only and excludes it from completed-candle lookback aggregates.

    Returns None on any fetch or parse error.
    """
    start_ms = int(
        (pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=limit)).timestamp() * 1000
    )
    try:
        raw = _fetch_klines_paginated(symbol, interval, start_ms)
    except Exception as exc:
        logger.warning("Failed to fetch klines for %s: %s", symbol, exc)
        return None

    if not raw:
        logger.warning("Empty klines response for %s", symbol)
        return None

    try:
        df = _parse_klines(raw)

        # The current partial candle has open_time == today 00:00 UTC
        if not include_partial:
            today_start = pd.Timestamp.now(tz="UTC").normalize()
            df = df[df.index < today_start]

        # Honour `limit` as a row cap (pagination may slightly overshoot)
        max_rows = limit + 1 if include_partial else limit
        return df.iloc[-max_rows:]
    except Exception as exc:
        logger.warning("Failed to parse klines for %s: %s", symbol, exc)
        return None


def get_klines_window(
    symbol: str,
    interval: str,
    start: pd.Timestamp,
    end: Optional[pd.Timestamp] = None,
) -> Optional[pd.DataFrame]:
    """
    Fetch completed candles in [start, end] (end inclusive; defaults to now).
    Used by the disk cache to back-fill older history or extend the tail
    without re-downloading what is already cached. Partial candles are
    always dropped — cached data must be completed candles only.
    """
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000) if end is not None else None
    try:
        raw = _fetch_klines_paginated(symbol, interval, start_ms, end_ms)
    except Exception as exc:
        logger.warning("Failed to fetch klines window for %s: %s", symbol, exc)
        return None
    if not raw:
        return pd.DataFrame()
    try:
        df = _parse_klines(raw)
        today_start = pd.Timestamp.now(tz="UTC").normalize()
        return df[df.index < today_start]
    except Exception as exc:
        logger.warning("Failed to parse klines window for %s: %s", symbol, exc)
        return None
