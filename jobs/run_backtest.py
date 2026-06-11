"""
Historical replay backtest — entrypoint.

Usage:
  python jobs/run_backtest.py                       # full replay, default config
  python jobs/run_backtest.py --config alt.yaml     # compare a candidate config (manual review only)
  python jobs/run_backtest.py --refresh-cache       # force re-fetch of klines
  python jobs/run_backtest.py --max-dates 30        # dev aid: replay only the last N dates

Outputs: store/backtest.db, backtest_report.md, dashboard/backtest.json.
Rules: hypothesis generator only — the live validation table is the verdict.
No automated parameter optimisation against these results.
"""
import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data.cache import get_klines_cached
from compute.universe import get_candidate_pairs
from compute.replay import run_replay
from compute.backtest_report import build_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _safe_print(text: str) -> None:
    sys.stdout.buffer.write(
        text.encode(sys.stdout.encoding or "utf-8", errors="replace") + b"\n"
    )


def write_backtest_db(db_path: str, bt: pd.DataFrame) -> None:
    """backtest.db is derived data (recomputable from klines) — unlike the
    live snapshot store it is rebuilt on every run, not appended."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS backtest_daily")
    out = bt.copy()
    for col in ("rs_divergence", "rs_new_high", "accum_flag", "rs_breakdown", "dist_flag", "coil_flag"):
        out[col] = out[col].astype(int)
    out.to_sql("backtest_daily", conn, index=False)
    conn.execute("CREATE INDEX idx_bt_date ON backtest_daily(date)")
    conn.execute("CREATE INDEX idx_bt_symbol ON backtest_daily(symbol)")
    conn.commit()
    conn.close()
    logger.info("backtest.db written: %d rows", len(out))


def run(config_path: str, refresh_cache: bool, max_dates: int | None) -> None:
    cfg = load_config(config_path)
    bt_cfg = cfg["backtest"]

    # ------------------------------------------------------------------ #
    # 1. Candidate pool (today's listings — survivorship caveat applies)   #
    # ------------------------------------------------------------------ #
    candidates = get_candidate_pairs(cfg)
    logger.info("Candidate pool: %d symbols (static exclusions applied)", len(candidates))

    # ------------------------------------------------------------------ #
    # 2. Klines, disk-cached                                               #
    # ------------------------------------------------------------------ #
    interval = cfg["data"]["interval"]
    limit = cfg["data"]["history_days"]
    cache_dir = bt_cfg["cache_dir"]

    btc_df = get_klines_cached(cfg["benchmark"], interval, limit, cache_dir, refresh_cache)
    if btc_df is None or btc_df.empty:
        logger.error("Failed to fetch BTC data — aborting")
        sys.exit(1)

    klines: dict[str, pd.DataFrame] = {}
    for i, sym in enumerate(candidates, 1):
        df = get_klines_cached(sym, interval, limit, cache_dir, refresh_cache)
        if df is not None and not df.empty:
            klines[sym] = df
        if i % 50 == 0:
            logger.info("  ...klines %d / %d", i, len(candidates))
    logger.info("Klines loaded for %d / %d candidates", len(klines), len(candidates))

    # ------------------------------------------------------------------ #
    # 3. Replay (single code path: same compute functions as live)         #
    # ------------------------------------------------------------------ #
    bt = run_replay(klines, btc_df, cfg, max_dates=max_dates)
    if bt.empty:
        logger.error("Replay produced no rows — aborting")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # 4. Storage + report                                                  #
    # ------------------------------------------------------------------ #
    write_backtest_db("store/backtest.db", bt)

    meta = {
        "date_from": bt["date"].min(),
        "date_to": bt["date"].max(),
        "n_dates": int(bt["date"].nunique()),
        "n_symbols": int(bt["symbol"].nunique()),
        "config_path": config_path,
    }
    md, payload = build_report(bt, cfg, meta)

    # Keep an honest record of what each hypothesis version was judged on
    report_path = Path("backtest_report.md")
    if report_path.exists():
        from datetime import datetime, timezone
        archive = Path(f"backtest_report_v1_{datetime.now(timezone.utc).date()}.md")
        if not archive.exists():
            report_path.rename(archive)
            logger.info("Previous report archived: %s", archive)
    report_path.write_text(md, encoding="utf-8")
    logger.info("Report written: %s", report_path)

    json_path = Path("dashboard/backtest.json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Dashboard JSON written: %s", json_path)

    _safe_print("\n" + md)


def main() -> None:
    parser = argparse.ArgumentParser(description="Alt Scanner historical replay backtest")
    parser.add_argument("--config", default=str(_ROOT / "config.yaml"), help="Path to config.yaml")
    parser.add_argument("--refresh-cache", action="store_true", help="Force re-fetch of klines")
    parser.add_argument("--max-dates", type=int, default=None, help="Dev aid: replay only the last N dates")
    args = parser.parse_args()
    run(args.config, args.refresh_cache, args.max_dates)


if __name__ == "__main__":
    main()
