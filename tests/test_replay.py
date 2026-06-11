"""Replay engine tests (brief A5.1 and A5.4).

A5.1: replay path (as_of=D) and live path (pre-sliced data, no as_of) must
produce IDENTICAL scores — a backtest of different code is a backtest of nothing.
A5.4: a constructed coin whose RS divergence precedes a +10% move appears
correctly in the divergence resolution stats.

Run with:  python -m unittest tests.test_replay -v
"""
import unittest
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pandas.testing as pdt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compute.metrics import compute_coin_metrics
from compute.scoring import compute_scores
from compute.replay import run_replay
from compute.backtest_report import flag_resolution
from tests.test_signals import _make_df, _TEST_CONFIG


def _replay_config():
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in _TEST_CONFIG.items()}
    cfg["universe"] = {**cfg["universe"], "max_universe": 12}
    cfg["backtest"] = {
        "warmup_days": 70,
        "min_universe_for_replay": 5,
        "horizons_days": [3, 7, 14],
        "min_cell_n": 30,
        "cache_dir": "unused",
        "universe_vol_window_days": 7,
    }
    return cfg


def _filler_universe(n_days: int, n_coins: int = 8) -> dict[str, pd.DataFrame]:
    """Deterministic mildly-varying coins so percentiles have a spread."""
    rng = np.random.default_rng(42)
    out = {}
    for i in range(n_coins):
        drift = 1 + (i - 4) * 0.0005
        noise = rng.normal(0, 0.004, n_days)
        closes = 50.0 * (1 + 0.02 * i) * np.cumprod(drift + noise)
        vols = 1_000_000.0 * (1 + 0.1 * i) * (1 + rng.uniform(-0.05, 0.05, n_days))
        out[f"FILL{i}USDT"] = _make_df(list(closes), volumes=list(vols))
    return out


class TestReplayLiveIdentity(unittest.TestCase):
    """A5.1 — the single-code-path proof."""

    def test_identical_scores_for_same_date(self):
        cfg = _replay_config()
        n_days = 120
        klines = _filler_universe(n_days)
        btc_df = _make_df([100.0 + 0.1 * i for i in range(n_days)])
        cutoff = btc_df.index[90]   # a historical date D

        # Replay path: full data, as_of=D
        replay_rows = [
            compute_coin_metrics(sym, df, btc_df, cfg, as_of=cutoff)
            for sym, df in klines.items()
        ]
        # Live path: data manually pre-sliced to D, no as_of (what a live run
        # at date D would have seen)
        live_rows = [
            compute_coin_metrics(sym, df.loc[:cutoff], btc_df.loc[:cutoff], cfg)
            for sym, df in klines.items()
        ]

        self.assertEqual(replay_rows, live_rows, "per-coin metrics must be identical")

        replay_scores = compute_scores(replay_rows, cfg)
        live_scores = compute_scores(live_rows, cfg)
        pdt.assert_frame_equal(replay_scores, live_scores)


class TestDivergenceResolution(unittest.TestCase):
    """A5.4 — synthetic divergence preceding a +10% move shows up in the stats."""

    def test_divergence_precedes_move(self):
        cfg = _replay_config()
        n_days = 160

        # DIVCOIN: flat 100; spikes to 120 around day 80 (the in-window price
        # high); settles at 105. BTC declines days 120-140, lifting DIVCOIN's
        # RS line to fresh 60d highs while its price stays below 120 →
        # rs_divergence fires through that window. Then +10% over days 141-148.
        coin = (
            [100.0] * 78
            + [110.0, 120.0, 115.0]               # days 78-80: price spike
            + [105.0] * 60                        # hold below the high
            + [105.0 * (1 + 0.10 * (i + 1) / 8) for i in range(8)]  # +10% rally
            + [115.5] * (n_days - 78 - 3 - 60 - 8)
        )
        coin = coin[:n_days]
        btc = (
            [100.0] * 120
            + [100.0 - 1.0 * (i + 1) for i in range(20)]   # decline to 80
            + [80.0] * (n_days - 140)
        )
        btc = btc[:n_days]

        klines = _filler_universe(n_days)
        klines["DIVCOINUSDT"] = _make_df(coin)
        btc_df = _make_df(btc)

        bt = run_replay(klines, btc_df, cfg)
        self.assertFalse(bt.empty, "replay must produce rows")

        div_rows = bt[(bt["symbol"] == "DIVCOINUSDT") & bt["rs_divergence"]]
        self.assertGreater(len(div_rows), 0, "the constructed divergence must be detected")

        # The divergence dates sit in the BTC-decline window, before the rally
        last_div = pd.to_datetime(div_rows["date"]).max()
        rally_start = btc_df.index[140].tz_localize(None)
        self.assertLessEqual(last_div, rally_start + pd.Timedelta(days=2))

        # And the +10% move shows up in its forward returns: at least one
        # divergence row sees ~+10% USD over 7-14d
        best_fwd = pd.concat([div_rows["fwd_usd_7"], div_rows["fwd_usd_14"]]).max()
        self.assertGreaterEqual(best_fwd, 0.08, "divergence should precede the +10% move")

        # ...and in the aggregate resolution stats the median outcome is positive
        stats = flag_resolution(div_rows, "rs_divergence", [7, 14])
        self.assertGreater(stats["horizons"]["7"]["median_fwd_rs"], 0)


if __name__ == "__main__":
    unittest.main()
