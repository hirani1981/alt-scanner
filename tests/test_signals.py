"""Unit tests for the Phase 2 leading signals (brief §13.1).

Run with:  python -m unittest tests.test_signals -v
"""
import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compute.metrics import (
    compute_rs_line,
    compute_rs_line_signals,
    compute_vol_trend,
    compute_range_pct,
)
from compute.scoring import compute_scores


def _make_df(closes, highs=None, lows=None, volumes=None):
    """Build a klines-style DataFrame indexed by consecutive UTC dates."""
    n = len(closes)
    idx = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": closes,
            "high": highs if highs is not None else [c * 1.01 for c in closes],
            "low": lows if lows is not None else [c * 0.99 for c in closes],
            "close": closes,
            "quote_volume": volumes if volumes is not None else [1_000_000.0] * n,
        },
        index=idx,
    )


_TEST_CONFIG = {
    "universe": {"min_listing_days": 30},
    "signals": {
        "returns_windows_days": [1, 7, 30],
        "volume_baseline_days": 30,
        "volume_z_clamp": 10,
        "rs_high_lookback_days": 60,
        "rs_persistence_ma_days": 10,
        "rs_persistence_cap": 30,
        "rs_spark_days": 30,
        "vol_trend_fast_days": 5,
        "vol_trend_slow_days": 30,
        "vol_trend_min": 1.5,
        "quiet_range_days": 10,
        "quiet_range_pctile": 35,
        "extended_pctile": 80,
        "dist_down_vol_min": 0.60,
        "coil_up_vol_max": 0.40,
    },
    "scoring": {
        "strength_weights": {"relative_strength": 0.50, "volume_surge": 0.35, "structure": 0.15},
        "rs_window_weights": {1: 0.2, 7: 0.5, 30: 0.3},
        "early_weights": {"divergence": 0.35, "accumulation": 0.30, "persistence": 0.20, "extension_penalty": 0.15},
        "rs_new_high_partial": 0.6,
        "accum_partial_scale": 0.6,
        "early_ext_penalty": 0.5,
    },
    "stages": {
        "ext_rs30_pctile": 92,
        "ignite_volz_min": 1.5,
        "run_strength_pctile": 70,
        "run_persistence_min": 5,
    },
    "shorts": {
        "enabled": False,
        "oversold_pctile": 8,
        "weak_oversold_penalty": 0.5,
        "weak_weights": {"breakdown": 0.35, "distribution": 0.30, "persistence": 0.20, "lateness_penalty": 0.15},
    },
}


def make_metric_row(symbol, **overrides):
    """A complete compute_coin_metrics-shaped row with neutral defaults."""
    row = {
        "symbol": symbol, "date": "2026-06-05", "price": 1.0,
        "pct_w": 0.0, "pct_m": 0.0, "pct_q": 0.0, "pct_y": 0.0,
        "ret_1d": 0.0, "ret_7d": 0.0, "ret_30d": 0.0,
        "rs_1d": 0.0, "rs_7d": 0.01, "rs_30d": 0.0,
        "vol_z": 0.5, "structure": 2,
        "rs_new_high": False, "price_new_high": False,
        "rs_divergence": False, "rs_persistence": 3,
        "rs_new_low": False, "price_new_low": False,
        "rs_breakdown": False, "weak_persistence": 3,
        "rs_below_ma": False,
        "vol_trend": 1.0, "range_pct_10d": 0.25,
        "down_vol_ratio": 0.5,
        "rs_spark": [1.0] * 30,
    }
    row.update(overrides)
    return row


class TestRSDivergence(unittest.TestCase):
    """§13.1a: RS at a 60d high while price is below its 60d high → rs_divergence."""

    def test_divergence_fires(self):
        # Coin: peaks at 120 on day 50, settles at 105 for the rest.
        coin_closes = (
            [100.0 + i * 0.4 for i in range(50)]     # drift up to ~120
            + [120.0]
            + [105.0] * 49                            # below the day-50 peak
        )
        # BTC: flat at 100, then declines to 80 over the last 20 days —
        # so coin/BTC rises to a fresh 60d high while coin price does not.
        btc_closes = [100.0] * 80 + [100.0 - i for i in range(1, 21)]

        coin_df = _make_df(coin_closes)
        btc_df = _make_df(btc_closes)

        rs_line = compute_rs_line(coin_df, btc_df)
        sig = compute_rs_line_signals(rs_line, coin_df["close"], 60, 10, 30)

        self.assertTrue(sig["rs_new_high"], "RS line should be at a 60d high")
        self.assertFalse(sig["price_new_high"], "price should be below its 60d high")
        self.assertTrue(sig["rs_divergence"], "divergence flag must fire")

    def test_no_divergence_when_price_also_breaks_out(self):
        # Both coin and RS line at new highs → new high, but no divergence.
        coin_closes = [100.0 + i for i in range(100)]   # steady rise; today is the high
        btc_closes = [100.0] * 100
        coin_df = _make_df(coin_closes)
        btc_df = _make_df(btc_closes)

        rs_line = compute_rs_line(coin_df, btc_df)
        sig = compute_rs_line_signals(rs_line, coin_df["close"], 60, 10, 30)

        self.assertTrue(sig["rs_new_high"])
        self.assertTrue(sig["price_new_high"])
        self.assertFalse(sig["rs_divergence"])

    def test_persistence_counts_and_caps(self):
        # RS line strictly rising → always above its 10d SMA → hits the cap.
        coin_closes = [100.0 * 1.01 ** i for i in range(100)]
        btc_closes = [100.0] * 100
        rs_line = compute_rs_line(_make_df(coin_closes), _make_df(btc_closes))
        sig = compute_rs_line_signals(rs_line, _make_df(coin_closes)["close"], 60, 10, 30)
        self.assertEqual(sig["rs_persistence"], 30)


class TestQuietAccumulation(unittest.TestCase):
    """§13.1b: flat price + rising volume → accum_flag."""

    def test_vol_trend_rises_on_building_volume(self):
        # 25 quiet days at 100k, then 5 days at 300k → fast/slow well above 1.5
        volumes = [100_000.0] * 25 + [300_000.0] * 5
        df = _make_df([50.0] * 30, volumes=volumes)
        vt = compute_vol_trend(df, 5, 30)
        self.assertIsNotNone(vt)
        self.assertGreaterEqual(vt, 1.5)

    def test_range_pct_small_when_flat(self):
        df = _make_df([50.0] * 40, highs=[50.5] * 40, lows=[49.5] * 40)
        rp = compute_range_pct(df, 10)
        self.assertAlmostEqual(rp, 0.02, places=6)

    def test_accum_flag_set_in_cross_section(self):
        """One flat/building coin among trending noisy ones gets ACCUM."""
        rows = [make_metric_row("QUIET", rs_30d=0.01, vol_trend=2.0, range_pct_10d=0.03)]
        # 9 trending coins: wide ranges, normal volume, varied extension
        for i in range(9):
            rows.append(make_metric_row(f"TREND{i}", rs_30d=0.05 + i * 0.05,
                                        vol_trend=1.0, range_pct_10d=0.25 + i * 0.02))

        ranked = compute_scores(rows, _TEST_CONFIG)
        quiet = ranked[ranked["symbol"] == "QUIET"].iloc[0]

        self.assertTrue(quiet["accum_flag"], "flat price + building volume must flag ACCUM")
        self.assertEqual(quiet["stage"], "ACCUM")

    def test_extended_coin_cannot_flag_accum(self):
        """A coin in the top extension percentile is excluded even if quiet."""
        # EXTENDED has the highest rs_30d of the universe AND is quiet/building
        rows = [make_metric_row("EXTENDED", rs_30d=3.0, vol_trend=2.0, range_pct_10d=0.03)]
        for i in range(9):
            rows.append(make_metric_row(f"COIN{i}", rs_30d=0.01 * i, vol_trend=1.0,
                                        range_pct_10d=0.25 + i * 0.02))

        ranked = compute_scores(rows, _TEST_CONFIG)
        ext = ranked[ranked["symbol"] == "EXTENDED"].iloc[0]
        self.assertFalse(ext["accum_flag"], "extended coins must not flag ACCUM")
        self.assertEqual(ext["stage"], "EXT")


if __name__ == "__main__":
    unittest.main()
