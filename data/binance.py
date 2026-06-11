"""Binance public market-data client — universe discovery, klines, prices.

Host selection: api.binance.com returns HTTP 451 to cloud IPs (e.g. GitHub
Actions runners) for legal/geo reasons. data-api.binance.vision is Binance's
public market-data mirror; it serves the identical /api/v3/* endpoints and
does NOT geo-block cloud IPs, so it is the default. Hosts are tried in order
and a 451 from one host advances to the next. Override with the
BINANCE_API_BASE env var (comma-separated list) without a code change.
"""
import os
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

# Tried in order; same /api/v3 schema on every host. The .vision mirror is
# first because it is not geo-blocked from cloud IPs.
_DEFAULT_HOSTS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
]


def _hosts() -> list[str]:
    env = os.environ.get("BINANCE_API_BASE")
    if env:
        return [h.strip().rstrip("/") for h in env.split(",") if h.strip()]
    return _DEFAULT_HOSTS


def _get(path: str, params: dict = None) -> dict | list:
    """GET a public endpoint, trying each host in turn. A 451 (geo-block)
    advances immediately to the next host; 429 retries the same host with
    backoff. Raises the last error if every host fails."""
    hosts = _hosts()
    last_exc: Exception | None = None

    for host in hosts:
        url = f"{host}{path}"
        for attempt in range(3):
            if attempt > 0:
                delay = 2 ** attempt  # 2, 4 seconds
                logger.warning("Retrying %s on %s in %ds (attempt %d)", path, host, delay, attempt + 1)
                time.sleep(delay)
            try:
                resp = httpx.get(url, params=params, timeout=30)
                if resp.status_code == 451:
                    logger.warning("HTTP 451 (geo-block) from %s — trying next host", host)
                    last_exc = httpx.HTTPStatusError(
                        "451 geo-block", request=resp.request, response=resp
                    )
                    break  # do not retry this host; move to the next
                if resp.status_code == 429:
                    logger.warning("Rate limited on %s", host)
                    last_exc = httpx.HTTPStatusError(
                        "429 rate limit", request=resp.request, response=resp
                    )
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response is not None and exc.response.status_code == 451:
                    break
                logger.warning("HTTP error on %s%s: %s", host, path, exc)
            except httpx.HTTPError as exc:  # connect/timeout/transport errors
                last_exc = exc
                logger.warning("Transport error on %s%s: %s", host, path, exc)

    raise last_exc or RuntimeError(f"Failed to fetch {path} from all hosts")


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
