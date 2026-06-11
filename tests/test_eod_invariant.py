"""Invariant: at most one EOD snapshot may exist per date, regardless of when
the EOD run fires (brief section 9 — the EOD snapshot is canonical per date).

Run with:  python -m unittest tests.test_eod_invariant -v
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from store.db import init_db, insert_snapshot, _INSERT_COLS


def _eod_frame(run_ts: str, date: str, symbols=("BTCUSDT", "ETHUSDT")) -> pd.DataFrame:
    """Minimal ranked frame carrying every column insert_snapshot needs."""
    rows = []
    for i, sym in enumerate(symbols):
        row = {c: 0 for c in _INSERT_COLS}
        row.update({
            "run_ts": run_ts, "date": date, "is_eod": 1, "symbol": sym,
            "rs_new_high": False, "rs_divergence": False, "accum_flag": False,
            "stage": "-", "rank": i + 1,
        })
        rows.append(row)
    return pd.DataFrame(rows)


class TestOneEODPerDate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = str(Path(self.tmp) / "snap.db")
        init_db(self.db)

    def _eod_run_ts_count(self, date: str) -> int:
        conn = sqlite3.connect(self.db)
        n = conn.execute(
            "SELECT COUNT(DISTINCT run_ts) FROM snapshots WHERE is_eod=1 AND date=?",
            (date,),
        ).fetchone()[0]
        conn.close()
        return n

    def test_same_canonical_run_ts_is_idempotent(self):
        """Two EOD runs that resolve to the same canonical run_ts insert once."""
        f = _eod_frame("2026-06-09T00:30:00Z", "2026-06-09")
        insert_snapshot(self.db, f)
        insert_snapshot(self.db, f)  # re-run, same canonical ts
        self.assertEqual(self._eod_run_ts_count("2026-06-09"), 1)

    def test_different_run_ts_same_date_is_refused(self):
        """A second EOD for the same date under a DIFFERENT run_ts is rejected,
        even if the first one used a non-canonical timestamp."""
        # First EOD lands with a non-canonical (hour-truncated) run_ts
        insert_snapshot(self.db, _eod_frame("2026-06-10T11:00:00Z", "2026-06-09"))
        # Later EOD the same day at a different hour
        insert_snapshot(self.db, _eod_frame("2026-06-10T14:00:00Z", "2026-06-09"))
        self.assertEqual(self._eod_run_ts_count("2026-06-09"), 1)

    def test_distinct_dates_each_keep_their_own_eod(self):
        insert_snapshot(self.db, _eod_frame("2026-06-08T00:30:00Z", "2026-06-08"))
        insert_snapshot(self.db, _eod_frame("2026-06-09T00:30:00Z", "2026-06-09"))
        self.assertEqual(self._eod_run_ts_count("2026-06-08"), 1)
        self.assertEqual(self._eod_run_ts_count("2026-06-09"), 1)


if __name__ == "__main__":
    unittest.main()
