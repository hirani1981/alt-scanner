"""Unit tests for the short-side mirror signals (brief B6.1).

Run with:  python -m unittest tests.test_short_signals -v
"""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compute.metrics import compute_rs_line, compute_rs_line_signals
from compute.scoring import compute_scores
from tests.test_signals import _make_df, _TEST_CONFIG, make_metric_row


class TestRSBreakdown(unittest.TestCase):
    """RS at a 60d LOW while price is NOT at its 60d low → rs_breakdown."""

    def test_breakdown_fires(self):
        # Coin: dips to 80 at day 50, recovers to 95 and holds — its 60d price
        # low (80) is in the window, so today (95) is not a price low.
        coin_closes = (
            [100.0] * 45
            + [90.0, 85.0, 80.0, 85.0, 90.0]   # the dip, days 45-49
            + [95.0] * 50                       # recovery hold
        )
        # BTC: flat 100, then rallies to 130 over the last 20 days —
        # coin/BTC falls to a fresh 60d low while coin price holds.
        btc_closes = [100.0] * 80 + [100.0 + 1.5 * i for i in range(1, 21)]

        coin_df = _make_df(coin_closes)
        btc_df = _make_df(btc_closes)

        rs_line = compute_rs_line(coin_df, btc_df)
        sig = compute_rs_line_signals(rs_line, coin_df["close"], 60, 10, 30)

        self.assertTrue(sig["rs_new_low"], "RS line should be at a 60d low")
        self.assertFalse(sig["price_new_low"], "price should be above its 60d low")
        self.assertTrue(sig["rs_breakdown"], "breakdown flag must fire")

    def test_no_breakdown_when_price_also_at_low(self):
        # Coin collapsing in USD too — price at its low, so no divergent breakdown.
        coin_closes = [100.0 - 0.5 * i for i in range(100)]
        btc_closes = [100.0] * 100
        coin_df = _make_df(coin_closes)
        rs_line = compute_rs_line(coin_df, _make_df(btc_closes))
        sig = compute_rs_line_signals(rs_line, coin_df["close"], 60, 10, 30)

        self.assertTrue(sig["rs_new_low"])
        self.assertTrue(sig["price_new_low"])
        self.assertFalse(sig["rs_breakdown"])

    def test_weak_persistence_counts(self):
        # RS line strictly falling → always below its 10d SMA → hits the cap.
        coin_closes = [100.0 * 0.99 ** i for i in range(100)]
        btc_closes = [100.0] * 100
        coin_df = _make_df(coin_closes)
        rs_line = compute_rs_line(coin_df, _make_df(btc_closes))
        sig = compute_rs_line_signals(rs_line, coin_df["close"], 60, 10, 30)
        self.assertEqual(sig["weak_persistence"], 30)
        self.assertEqual(sig["rs_persistence"], 0)


class TestDistributionAsymmetry(unittest.TestCase):
    """DIST v2 requires EXTENDED *and evidence of supply* (down-volume
    dominance + RS below its 10d MA). The same footprint with buyers
    dominating is a coil — the bullish continuation the old DIST
    accidentally captured. Test both asymmetries explicitly."""

    @staticmethod
    def _universe(profile_extended: bool, down_vol: float, rs_below: bool):
        """One tight-range / building-volume coin among 9 trending fillers."""
        rs_30d = 3.0 if profile_extended else 0.005
        rows = [make_metric_row("TARGET", rs_30d=rs_30d, vol_trend=2.0,
                                range_pct_10d=0.03, down_vol_ratio=down_vol,
                                rs_below_ma=rs_below)]
        for i in range(9):
            rows.append(make_metric_row(
                f"FILL{i}", rs_30d=0.02 + i * 0.03,
                vol_trend=1.0, range_pct_10d=0.25 + i * 0.02,
            ))
        return rows

    def test_supply_dominance_sets_dist_v2(self):
        """Extended + quiet + building + DOWN-volume dominance + RS below MA → DIST."""
        ranked = compute_scores(
            self._universe(profile_extended=True, down_vol=0.70, rs_below=True),
            _TEST_CONFIG,
        )
        target = ranked[ranked["symbol"] == "TARGET"].iloc[0]
        self.assertTrue(target["dist_flag"], "supply evidence at the highs = distribution")
        self.assertFalse(target["coil_flag"])
        self.assertFalse(target["accum_flag"], "an extended coin must not flag ACCUM")
        self.assertEqual(target["short_stage"], "DIST")
        self.assertEqual(target["stage"], "EXT", "EXT long stage + DIST short stage = topping profile")

    def test_up_volume_dominance_sets_coil_not_dist(self):
        """The asymmetry that bit us: same shape with UP-volume dominance must
        NOT set dist_flag — buyers dominating at highs is a coil."""
        ranked = compute_scores(
            self._universe(profile_extended=True, down_vol=0.20, rs_below=False),
            _TEST_CONFIG,
        )
        target = ranked[ranked["symbol"] == "TARGET"].iloc[0]
        self.assertFalse(target["dist_flag"], "buyers dominating must not flag distribution")
        self.assertTrue(target["coil_flag"], "up-volume dominance at highs = coil")
        self.assertNotEqual(target["short_stage"], "DIST")

    def test_supply_without_rs_weakness_is_not_dist(self):
        """Down-volume dominance alone is insufficient — DIST v2 also needs
        the RS line below its 10d MA."""
        ranked = compute_scores(
            self._universe(profile_extended=True, down_vol=0.70, rs_below=False),
            _TEST_CONFIG,
        )
        target = ranked[ranked["symbol"] == "TARGET"].iloc[0]
        self.assertFalse(target["dist_flag"])

    def test_same_profile_not_extended_flags_accum_not_dist(self):
        """Accum/dist asymmetry from v1 still holds under v2."""
        ranked = compute_scores(
            self._universe(profile_extended=False, down_vol=0.70, rs_below=True),
            _TEST_CONFIG,
        )
        target = ranked[ranked["symbol"] == "TARGET"].iloc[0]
        self.assertFalse(target["dist_flag"], "non-extended coins must not flag distribution")
        self.assertTrue(target["accum_flag"], "same footprint when not extended = accumulation")
        self.assertEqual(target["stage"], "ACCUM")

    def test_oversold_penalty_halves_weak(self):
        """The most-collapsed coin gets OVERSOLD and its weak score is halved."""
        # 13 coins so the bottom coin's percentile rank (1/13 ~ 0.077) falls
        # under the oversold_pctile cut of 8%
        rows = [make_metric_row("COLLAPSED", rs_30d=-0.8, weak_persistence=20,
                                rs_new_low=True, rs_breakdown=False)]
        for i in range(12):
            rows.append(make_metric_row(f"FILL{i}", rs_30d=0.05 + i * 0.02))
        ranked = compute_scores(rows, _TEST_CONFIG)
        c = ranked[ranked["symbol"] == "COLLAPSED"].iloc[0]
        self.assertEqual(c["short_stage"], "OVERSOLD")

        # Recompute without the penalty by flipping config
        cfg = {**_TEST_CONFIG, "shorts": {**_TEST_CONFIG["shorts"], "weak_oversold_penalty": 1.0}}
        unpenalised = compute_scores(rows, cfg)
        u = unpenalised[unpenalised["symbol"] == "COLLAPSED"].iloc[0]
        self.assertAlmostEqual(c["weak"], u["weak"] * 0.5, places=10)


if __name__ == "__main__":
    unittest.main()
