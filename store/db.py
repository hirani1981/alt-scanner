"""SQLite snapshot store — append-only, never overwrites historical rows.

Phase 2 schema: one row per (run_ts, symbol). The 00:30 UTC run is the
canonical EOD snapshot (is_eod=1); ΔRank, digest diffs, and validation use
EOD snapshots only. Rank is computed on the Early score from Phase 2 onward.
"""
import sqlite3
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    run_ts          TEXT,     -- ISO UTC, truncated to the hour
    date            TEXT,     -- YYYY-MM-DD UTC of the snapshot candle
    is_eod          INTEGER,  -- 1 for the canonical 00:30 UTC run
    symbol          TEXT,
    price           REAL,
    btc_price       REAL,     -- BTC close at this run (for forward RS validation)
    pct_w           REAL,
    pct_m           REAL,
    pct_q           REAL,
    pct_y           REAL,
    ret_1d          REAL,
    ret_7d          REAL,
    ret_30d         REAL,
    rs_1d           REAL,
    rs_7d           REAL,
    rs_30d          REAL,
    vol_z           REAL,
    vol_trend       REAL,
    structure       INTEGER,
    rs_new_high     INTEGER,
    rs_divergence   INTEGER,
    accum_flag      INTEGER,
    rs_persistence  INTEGER,
    rs_pct          REAL,
    vol_pct         REAL,
    strength        REAL,
    early           REAL,
    stage           TEXT,
    rs_breakdown    INTEGER,
    dist_flag       INTEGER,
    weak_persistence INTEGER,
    weak            REAL,
    short_stage     TEXT,
    down_vol_ratio  REAL,
    rs_below_ma     INTEGER,
    coil_flag       INTEGER,
    rank            INTEGER,
    rank_change     INTEGER,
    PRIMARY KEY (run_ts, symbol)
)
"""

# Columns added after the Phase 2 schema — ALTER TABLE is idempotent via try/except
_MIGRATIONS = [
    ("rs_breakdown", "INTEGER"),
    ("dist_flag", "INTEGER"),
    ("weak_persistence", "INTEGER"),
    ("weak", "REAL"),
    ("short_stage", "TEXT"),
    ("down_vol_ratio", "REAL"),
    ("rs_below_ma", "INTEGER"),
    ("coil_flag", "INTEGER"),
]

_VALIDATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS validation (
    snapshot_date       TEXT,
    horizon_days        INTEGER,
    cohort              TEXT,
    n                   INTEGER,
    median_fwd_ret_usd  REAL,
    median_fwd_rs       REAL,
    PRIMARY KEY (snapshot_date, horizon_days, cohort)
)
"""


def _migrate_v1(conn: sqlite3.Connection) -> None:
    """One-time migration from the Phase 1 (date, symbol) schema.
    Old rows are preserved in snapshots_v1 and copied into the new table as
    EOD snapshots with early/stage NULL (Phase 1 ranks were strength-based;
    the first Phase 2 ΔRank ignores them via the early IS NOT NULL filter)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(snapshots)").fetchall()}
    if not cols or "run_ts" in cols:
        return  # no table yet, or already on the new schema

    logger.info("Migrating snapshot store to Phase 2 schema (run_ts, symbol)")
    conn.execute("ALTER TABLE snapshots RENAME TO snapshots_v1")
    conn.execute(_SCHEMA)
    conn.execute(
        """
        INSERT OR IGNORE INTO snapshots
            (run_ts, date, is_eod, symbol, price,
             pct_w, pct_m, pct_q, pct_y,
             ret_1d, ret_7d, ret_30d, rs_1d, rs_7d, rs_30d,
             vol_z, structure, rs_pct, vol_pct, strength, rank, rank_change)
        SELECT date || 'T00:30:00Z', date, 1, symbol, price,
               pct_w, pct_m, pct_q, pct_y,
               ret_1d, ret_7d, ret_30d, rs_1d, rs_7d, rs_30d,
               vol_z, structure, rs_pct, vol_pct, composite, rank, rank_change
        FROM snapshots_v1
        """
    )


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    _migrate_v1(conn)
    conn.execute(_SCHEMA)
    conn.execute(_VALIDATION_SCHEMA)
    for col, dtype in _MIGRATIONS:
        try:
            conn.execute(f"ALTER TABLE snapshots ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()
    logger.debug("DB ready: %s", db_path)


# ---------------------------------------------------------------------------
# Rank change (ΔRank stays a daily measure)
# ---------------------------------------------------------------------------

def get_prev_eod_ranks(db_path: str, run_ts: str) -> dict[str, int]:
    """
    Return {symbol: rank} from the EOD snapshot nearest to 24h before run_ts.
    Only Phase 2 snapshots count (early IS NOT NULL) — migrated Phase 1 rows
    used strength-based ranks, so comparing against them would be meaningless.
    """
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """
        SELECT run_ts FROM snapshots
        WHERE is_eod = 1 AND early IS NOT NULL AND run_ts < ?
        GROUP BY run_ts
        ORDER BY ABS(julianday(run_ts) - (julianday(?) - 1.0))
        LIMIT 1
        """,
        (run_ts, run_ts),
    ).fetchone()

    if not row:
        conn.close()
        return {}

    prev_ts = row[0]
    rows = conn.execute(
        "SELECT symbol, rank FROM snapshots WHERE run_ts = ?", (prev_ts,)
    ).fetchall()
    conn.close()
    logger.info("DeltaRank baseline: EOD snapshot %s (%d symbols)", prev_ts, len(rows))
    return {sym: rnk for sym, rnk in rows}


# ---------------------------------------------------------------------------
# Digest diffing ("new" = present now, absent in the previous EOD snapshot)
# ---------------------------------------------------------------------------

def get_prev_eod_state(db_path: str, run_ts: str) -> dict[str, dict]:
    """Return {symbol: {stage, rs_divergence, accum_flag, rank}} from the most
    recent Phase 2 EOD snapshot before run_ts. Empty dict if none exists."""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """
        SELECT MAX(run_ts) FROM snapshots
        WHERE is_eod = 1 AND early IS NOT NULL AND run_ts < ?
        """,
        (run_ts,),
    ).fetchone()

    if not row or not row[0]:
        conn.close()
        return {}

    rows = conn.execute(
        """
        SELECT symbol, stage, rs_divergence, accum_flag, rank
        FROM snapshots WHERE run_ts = ?
        """,
        (row[0],),
    ).fetchall()
    conn.close()
    return {
        sym: {
            "stage": stage,
            "rs_divergence": bool(div),
            "accum_flag": bool(acc),
            "rank": rnk,
        }
        for sym, stage, div, acc, rnk in rows
    }


def get_accum_streaks(db_path: str, symbols: list[str]) -> dict[str, int]:
    """Consecutive EOD snapshots (most recent first) with accum_flag=1, per symbol."""
    if not symbols:
        return {}
    conn = sqlite3.connect(db_path)
    placeholders = ",".join("?" * len(symbols))
    rows = conn.execute(
        f"""
        SELECT symbol, run_ts, accum_flag FROM snapshots
        WHERE is_eod = 1 AND symbol IN ({placeholders})
        ORDER BY symbol, run_ts DESC
        """,
        symbols,
    ).fetchall()
    conn.close()

    streaks: dict[str, int] = {}
    current_sym = None
    counting = False
    for sym, _, flag in rows:
        if sym != current_sym:
            current_sym = sym
            streaks[sym] = 0
            counting = True
        if counting and flag:
            streaks[sym] += 1
        else:
            counting = False
    return streaks


# ---------------------------------------------------------------------------
# Snapshot insert
# ---------------------------------------------------------------------------

_INSERT_COLS = [
    "run_ts", "date", "is_eod", "symbol", "price", "btc_price",
    "pct_w", "pct_m", "pct_q", "pct_y",
    "ret_1d", "ret_7d", "ret_30d", "rs_1d", "rs_7d", "rs_30d",
    "vol_z", "vol_trend", "structure",
    "rs_new_high", "rs_divergence", "accum_flag", "rs_persistence",
    "rs_pct", "vol_pct", "strength", "early", "stage",
    "rs_breakdown", "dist_flag", "weak_persistence", "weak", "short_stage",
    "down_vol_ratio", "rs_below_ma", "coil_flag",
    "rank", "rank_change",
]


def insert_snapshot(db_path: str, df: pd.DataFrame) -> None:
    """
    Insert a ranked run into the snapshot table.
    Uses INSERT OR IGNORE so re-running within the same hour is safe.
    rs_spark is intentionally not stored (latest.json only).
    """
    out = df.copy()
    for col in ("rs_new_high", "rs_divergence", "accum_flag", "rs_breakdown",
                "dist_flag", "rs_below_ma", "coil_flag"):
        out[col] = out[col].astype(int)
    rows = out[_INSERT_COLS].to_dict(orient="records")

    run_ts = out["run_ts"].iloc[0]
    date = out["date"].iloc[0]
    is_eod = int(out["is_eod"].iloc[0]) == 1

    conn = sqlite3.connect(db_path)

    # Enforce exactly one EOD snapshot per date. The canonical run_ts makes
    # same-date re-runs idempotent via the PK; this guard additionally refuses
    # any EOD row for a date that already has one under a different run_ts,
    # so history is never duplicated or overwritten (append-only).
    if is_eod:
        existing = conn.execute(
            "SELECT DISTINCT run_ts FROM snapshots WHERE is_eod = 1 AND date = ? AND run_ts <> ?",
            (date, run_ts),
        ).fetchall()
        if existing:
            logger.warning(
                "EOD snapshot for %s already exists (run_ts=%s); refusing to write a "
                "second EOD for this date (append-only).",
                date, existing[0][0],
            )
            conn.close()
            return

    placeholders = ", ".join(f":{c}" for c in _INSERT_COLS)
    conn.executemany(
        f"INSERT OR IGNORE INTO snapshots ({', '.join(_INSERT_COLS)}) VALUES ({placeholders})",
        rows,
    )
    conn.commit()
    conn.close()
    logger.info("Inserted %d rows for run %s", len(rows), run_ts)


# ---------------------------------------------------------------------------
# Validation log (the honesty layer) — append-only, like snapshots
# ---------------------------------------------------------------------------

def get_eod_snapshot_by_date(db_path: str, date: str) -> list[dict]:
    """All rows of the EOD snapshot for a given date ('' list if none)."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT symbol, price, btc_price, early, strength, stage
        FROM snapshots
        WHERE is_eod = 1 AND date = ?
        """,
        (date,),
    ).fetchall()
    conn.close()
    return [
        {"symbol": s, "price": p, "btc_price": bp, "early": e, "strength": st, "stage": stg}
        for s, p, bp, e, st, stg in rows
    ]


def insert_validation_rows(db_path: str, rows: list[dict]) -> None:
    if not rows:
        return
    conn = sqlite3.connect(db_path)
    conn.executemany(
        """
        INSERT OR IGNORE INTO validation
            (snapshot_date, horizon_days, cohort, n, median_fwd_ret_usd, median_fwd_rs)
        VALUES (:snapshot_date, :horizon_days, :cohort, :n, :median_fwd_ret_usd, :median_fwd_rs)
        """,
        rows,
    )
    conn.commit()
    conn.close()
    logger.info("Validation: inserted %d cohort rows", len(rows))


def get_validation_recent(db_path: str, limit: int = 60) -> list[dict]:
    """Most recent validation rows for the dashboard panel."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT snapshot_date, horizon_days, cohort, n, median_fwd_ret_usd, median_fwd_rs
        FROM validation
        ORDER BY snapshot_date DESC, horizon_days, cohort
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {
            "snapshot_date": d, "horizon_days": h, "cohort": c,
            "n": n, "median_fwd_ret_usd": u, "median_fwd_rs": r,
        }
        for d, h, c, n, u, r in rows
    ]


def get_validation_line(db_path: str, min_days: int, window_days: int = 30) -> str | None:
    """One-sentence summary for the digest once >= min_days of data exist.
    Compares Early-top-decile vs universe median 7d forward RS over the window."""
    conn = sqlite3.connect(db_path)
    n_days = conn.execute(
        "SELECT COUNT(DISTINCT snapshot_date) FROM validation"
    ).fetchone()[0]
    if n_days < min_days:
        conn.close()
        return None

    def median_for(cohort: str) -> float | None:
        vals = [
            r[0] for r in conn.execute(
                """
                SELECT median_fwd_rs FROM validation
                WHERE cohort = ? AND horizon_days = 7
                  AND median_fwd_rs IS NOT NULL
                  AND snapshot_date >= date('now', ?)
                """,
                (cohort, f"-{window_days} days"),
            ).fetchall()
        ]
        if not vals:
            return None
        vals.sort()
        mid = len(vals) // 2
        return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2

    early_med = median_for("early_top_decile")
    uni_med = median_for("universe")
    conn.close()

    if early_med is None or uni_med is None:
        return None
    return (
        f"Validation (last {window_days}d): Early-top-decile median 7d fwd RS "
        f"{early_med * 100:+.1f}% vs universe {uni_med * 100:+.1f}%."
    )
