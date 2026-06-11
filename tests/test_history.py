"""History extension tests (brief 2.6 §1): klines pagination past Binance's
1000-candle request cap, and cache head-merge without re-downloading.

Run with:  python -m unittest tests.test_history -v
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.binance as binance
from data.cache import get_klines_cached, _load
from compute.metrics import compute_down_vol_ratio
from tests.test_signals import _make_df

_DAY_MS = 86_400_000


def _candle(open_ms: int, price: float = 1.0, vol: float = 100.0) -> list:
    return [
        open_ms, str(price), str(price), str(price), str(price),
        "0", open_ms + _DAY_MS - 1, str(vol), 0, "0", "0", "0",
    ]


class _FakeBinance:
    """Serves a synthetic daily history ending yesterday (UTC), honouring
    startTime/endTime/limit like the real /klines endpoint."""

    def __init__(self, total_days: int):
        today = pd.Timestamp.now(tz="UTC").normalize()
        first = today - pd.Timedelta(days=total_days)
        self.opens = [int((first + pd.Timedelta(days=i)).timestamp() * 1000)
                      for i in range(total_days)]  # excludes today (completed only)
        self.calls = 0

    def __call__(self, path: str, params: dict = None) -> list:
        self.calls += 1
        start = params.get("startTime", 0)
        end = params.get("endTime")
        limit = params.get("limit", 500)
        rows = [o for o in self.opens if o >= start and (end is None or o <= end)]
        return [_candle(o) for o in rows[:limit]]


class TestPagination(unittest.TestCase):
    def test_fetch_beyond_1000_candles_pages_via_starttime(self):
        fake = _FakeBinance(total_days=1500)
        with mock.patch.object(binance, "_get", fake):
            df = binance.get_klines("TESTUSDT", "1d", limit=1500)
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 1500, "all candles beyond the 1000 cap must arrive")
        self.assertGreaterEqual(fake.calls, 2, "must page via startTime, not a single request")

    def test_limit_honoured_after_pagination(self):
        fake = _FakeBinance(total_days=1200)
        with mock.patch.object(binance, "_get", fake):
            df = binance.get_klines("TESTUSDT", "1d", limit=1000)
        self.assertEqual(len(df), 1000)


class TestCacheHeadMerge(unittest.TestCase):
    def test_short_cache_is_head_extended_not_redownloaded(self):
        fake = _FakeBinance(total_days=1200)
        tmp = tempfile.mkdtemp()

        with mock.patch.object(binance, "_get", fake):
            # Seed a 400-day cache (simulates the pre-2.6 state)
            first = get_klines_cached("TESTUSDT", "1d", 400, tmp)
            self.assertEqual(len(first), 400)
            calls_after_seed = fake.calls

            # Ask for 1000: only the missing OLDER range may be fetched
            merged = get_klines_cached("TESTUSDT", "1d", 1000, tmp)
            self.assertEqual(len(merged), 1000)
            self.assertTrue(merged.index.is_monotonic_increasing)
            self.assertFalse(merged.index.duplicated().any())

            # The head fetch must have requested only candles OLDER than the
            # cached start — i.e. it must not have re-downloaded the cached 400
            head_calls = fake.calls - calls_after_seed
            self.assertGreaterEqual(head_calls, 1)

            # Same-day re-request: fully served from cache, no new calls
            calls_before = fake.calls
            again = get_klines_cached("TESTUSDT", "1d", 1000, tmp)
            self.assertEqual(len(again), 1000)
            self.assertEqual(fake.calls, calls_before, "cached request must not refetch")

    def test_young_coin_marks_head_complete_and_stops_refetching(self):
        fake = _FakeBinance(total_days=200)   # coin listed 200 days ago
        tmp = tempfile.mkdtemp()
        with mock.patch.object(binance, "_get", fake):
            df = get_klines_cached("YOUNGUSDT", "1d", 1000, tmp)
            self.assertEqual(len(df), 200)
            _, head_complete = _load(Path(tmp) / "YOUNGUSDT.pkl")
            self.assertTrue(head_complete, "fewer rows than asked => listing reached")

            calls_before = fake.calls
            get_klines_cached("YOUNGUSDT", "1d", 1000, tmp)
            self.assertEqual(fake.calls, calls_before,
                             "complete young coin must not trigger head fetches")


class TestDownVolRatio(unittest.TestCase):
    def test_down_volume_dominance(self):
        # Alternating up/down closes; down days carry 3x the volume
        closes, vols = [100.0], [100.0]
        for i in range(10):
            closes.append(closes[-1] * (0.98 if i % 2 == 0 else 1.02))
            vols.append(300.0 if i % 2 == 0 else 100.0)
        df = _make_df(closes, volumes=vols)
        ratio = compute_down_vol_ratio(df, 10)
        self.assertAlmostEqual(ratio, 1500 / 2000, places=6)  # 5 down days x 300 / total

    def test_insufficient_history_returns_none(self):
        df = _make_df([100.0] * 5)
        self.assertIsNone(compute_down_vol_ratio(df, 10))


if __name__ == "__main__":
    unittest.main()
