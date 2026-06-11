"""Disk cache for klines — backtest re-runs must not re-fetch the exchange.

Merge semantics (Phase 2.6): if a cached coin has fewer days than requested,
only the MISSING OLDER range is fetched and merged in front; if the cache is
from a previous day, only the missing newer tail is fetched and appended.
Cached candles are never re-downloaded.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from data.binance import get_klines, get_klines_window

logger = logging.getLogger(__name__)


def _is_fresh(path: Path) -> bool:
    """Cache entry is fresh if written today (UTC) — completed daily candles
    only change at the UTC day boundary."""
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return mtime.date() == datetime.now(timezone.utc).date()


def _load(path: Path) -> tuple[Optional[pd.DataFrame], bool]:
    """Returns (df, head_complete). head_complete=True means the coin's full
    listing history is already cached — no older candles exist to fetch.
    Tolerates the pre-2.6 format (bare DataFrame)."""
    try:
        obj = pd.read_pickle(path)
    except Exception as exc:
        logger.warning("Corrupt cache at %s (%s)", path, exc)
        return None, False
    if isinstance(obj, dict):
        return obj.get("df"), bool(obj.get("head_complete", False))
    return obj, False  # legacy format: assume more history may exist


def _save(path: Path, df: pd.DataFrame, head_complete: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({"df": df, "head_complete": head_complete}, path)


def _merge(*frames: pd.DataFrame) -> pd.DataFrame:
    out = pd.concat([f for f in frames if f is not None and not f.empty])
    out = out[~out.index.duplicated(keep="last")]
    return out.sort_index()


def get_klines_cached(
    symbol: str,
    interval: str,
    limit: int,
    cache_dir: str,
    refresh: bool = False,
) -> Optional[pd.DataFrame]:
    """
    Completed-candle klines with a per-symbol pickle cache and range merging.
    Pass refresh=True to force a full re-fetch. Partial candles are never
    cached (backtests use completed data only — no look-ahead).
    """
    cache_path = Path(cache_dir) / f"{symbol}.pkl"

    cached, head_complete = (None, False)
    if not refresh and cache_path.exists():
        cached, head_complete = _load(cache_path)

    # Cold cache (or forced refresh): one paginated fetch
    if cached is None or cached.empty:
        df = get_klines(symbol, interval, limit, include_partial=False)
        if df is None or df.empty:
            return df
        # Fewer rows than asked → we reached the coin's listing date
        _save(cache_path, df, head_complete=len(df) < limit - 2)
        return df

    want_start = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=limit)

    # 1. Tail extension: cache from a previous day → fetch only newer candles
    if not _is_fresh(cache_path):
        tail = get_klines_window(
            symbol, interval, start=cached.index[-1] + pd.Timedelta(days=1)
        )
        if tail is not None and not tail.empty:
            cached = _merge(cached, tail)

    # 2. Head extension: cache shorter than requested and listing not reached
    #    → fetch only the missing OLDER range
    if not head_complete and len(cached) < limit and cached.index[0] > want_start:
        gap_end = cached.index[0] - pd.Timedelta(milliseconds=1)
        older = get_klines_window(symbol, interval, start=want_start, end=gap_end)
        if older is None or older.empty:
            head_complete = True  # nothing before the cached start: listing reached
        else:
            gap_days = (cached.index[0] - want_start).days
            head_complete = len(older) < gap_days - 2
            cached = _merge(older, cached)
        logger.debug("%s: head-extended by %d rows (complete=%s)",
                     symbol, 0 if older is None else len(older), head_complete)

    _save(cache_path, cached, head_complete)
    return cached.iloc[-limit:]
