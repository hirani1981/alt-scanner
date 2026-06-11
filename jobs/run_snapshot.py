"""
Alt Strength Scanner — main entrypoint (Phase 2).

Usage:
  python jobs/run_snapshot.py              # normal run (EOD if hour == 0 UTC)
  python jobs/run_snapshot.py --dry-run    # fetch + compute, print table, no writes
  python jobs/run_snapshot.py --eod        # force canonical EOD semantics
  python jobs/run_snapshot.py --config path/to/config.yaml

The 00:30 UTC run is the canonical EOD snapshot (is_eod=1). Intraday runs
use the live partial candle for current price / volume-so-far only.
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

# Make project root importable when running from jobs/ or from project root
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data.binance import get_klines
from compute.universe import build_universe
from compute.metrics import compute_coin_metrics
from compute.scoring import compute_scores
from compute.regime import compute_regime
from compute.validation import compute_validation_rows
from store.db import (
    init_db,
    get_prev_eod_ranks,
    get_prev_eod_state,
    get_accum_streaks,
    get_eod_snapshot_by_date,
    insert_snapshot,
    insert_validation_rows,
    get_validation_recent,
    get_validation_line,
)
from alerts.digest import emit_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Seconds to pause between klines fetches — keeps weight well below 1200/min
_FETCH_PAUSE = 0.05


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _safe_print(text: str) -> None:
    """Print through narrow-codec consoles (e.g. Windows cp1252) without crashing."""
    sys.stdout.buffer.write(
        text.encode(sys.stdout.encoding or "utf-8", errors="replace") + b"\n"
    )


def _print_ranked_table(df: pd.DataFrame, regime: dict) -> None:
    cols = [
        "rank", "symbol", "stage", "early", "strength", "rank_change",
        "rs_1d", "rs_7d", "rs_30d", "vol_z", "vol_trend", "structure",
    ]
    display = df[cols].copy()

    def rs_pct(v):
        return f"{v*100:+.1f}%" if pd.notna(v) else "n/a"

    display["rs_1d"]  = display["rs_1d"].apply(rs_pct)
    display["rs_7d"]  = display["rs_7d"].apply(rs_pct)
    display["rs_30d"] = display["rs_30d"].apply(rs_pct)
    display["vol_z"] = display["vol_z"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "n/a")
    display["vol_trend"] = display["vol_trend"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "n/a")
    display["early"] = display["early"].apply(lambda v: f"{v:.4f}")
    display["strength"] = display["strength"].apply(lambda v: f"{v:.4f}")
    display["rank_change"] = display["rank_change"].apply(
        lambda v: f"+{int(v)}" if pd.notna(v) and v > 0
        else (str(int(v)) if pd.notna(v) else "-")
    )

    stage_counts = df["stage"].value_counts().to_dict()
    stage_line = "  ".join(f"{k}:{v}" for k, v in stage_counts.items())

    text = f"\nRegime: {regime['line']}\n"
    text += "\n" + display.to_string(index=False)
    text += f"\n\n{len(df)} coins ranked (by Early score)  |  snapshot date: {df['date'].iloc[0]}"
    text += f"\nStages: {stage_line}"
    _safe_print(text)


def run(config_path: str, dry_run: bool, force_eod: bool) -> None:
    cfg = load_config(config_path)

    now = datetime.now(timezone.utc)
    is_eod = force_eod or now.hour == 0
    run_ts = now.strftime("%Y-%m-%dT%H:00:00Z")  # truncated to hour → idempotent
    include_partial = not is_eod
    logger.info("Run %s  (is_eod=%s, partial candle=%s)", run_ts, is_eod, include_partial)

    # ------------------------------------------------------------------ #
    # 1. Universe                                                          #
    # ------------------------------------------------------------------ #
    symbols = build_universe(cfg)
    if not symbols:
        logger.error("Universe is empty — check filters in config.yaml")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # 2. BTC benchmark klines                                              #
    # ------------------------------------------------------------------ #
    logger.info("Fetching BTC klines…")
    btc_df = get_klines(
        cfg["benchmark"], cfg["data"]["interval"], cfg["data"]["history_days"],
        include_partial=include_partial,
    )
    if btc_df is None or btc_df.empty:
        logger.error("Failed to fetch BTC data — aborting")
        sys.exit(1)
    btc_now = float(btc_df["close"].iloc[-1])
    logger.info("BTC: %d candles, last %s, price %.0f", len(btc_df), btc_df.index[-1].date(), btc_now)

    # ------------------------------------------------------------------ #
    # 3. Alt klines                                                        #
    # ------------------------------------------------------------------ #
    logger.info("Fetching klines for %d alts…", len(symbols))
    klines: dict[str, pd.DataFrame] = {}
    for i, sym in enumerate(symbols, 1):
        df = get_klines(
            sym, cfg["data"]["interval"], cfg["data"]["history_days"],
            include_partial=include_partial,
        )
        if df is not None and not df.empty:
            klines[sym] = df
        else:
            logger.warning("Skipping %s — no klines data", sym)
        if i % 50 == 0:
            logger.info("  …fetched %d / %d", i, len(symbols))
        time.sleep(_FETCH_PAUSE)
    logger.info("Klines fetched for %d / %d symbols", len(klines), len(symbols))

    # ------------------------------------------------------------------ #
    # 4. Per-coin metrics                                                  #
    # ------------------------------------------------------------------ #
    metric_rows: list[dict] = []
    for sym, coin_df in klines.items():
        row = compute_coin_metrics(sym, coin_df, btc_df, cfg)
        if row is not None:
            metric_rows.append(row)
    if not metric_rows:
        logger.error("No metrics computed — aborting")
        sys.exit(1)
    logger.info("Metrics computed for %d coins", len(metric_rows))

    # ------------------------------------------------------------------ #
    # 5. Scores, stages, ranks (Early-based)                               #
    # ------------------------------------------------------------------ #
    ranked = compute_scores(metric_rows, cfg)

    # Canonical EOD identity: one EOD snapshot per snapshot date, regardless of
    # the hour the run fires. Ties the run_ts to the candle date so a second
    # --eod the same day collides on the (run_ts, symbol) PK and is ignored.
    snapshot_date = ranked["date"].iloc[0]
    if is_eod:
        run_ts = f"{snapshot_date}T00:30:00Z"
        logger.info("EOD canonical run_ts for %s: %s", snapshot_date, run_ts)
    ranked["run_ts"] = run_ts
    ranked["is_eod"] = int(is_eod)
    ranked["btc_price"] = btc_now

    # ------------------------------------------------------------------ #
    # 6. Regime header                                                     #
    # ------------------------------------------------------------------ #
    regime = compute_regime(btc_df, ranked, cfg)

    # ------------------------------------------------------------------ #
    # 7. ΔRank vs the EOD snapshot nearest to 24h ago                      #
    # ------------------------------------------------------------------ #
    if not dry_run:
        db_path = cfg["output"]["snapshot_db"]
        init_db(db_path)
        prev_ranks = get_prev_eod_ranks(db_path, run_ts)
        if prev_ranks:
            ranked["rank_change"] = pd.to_numeric(
                ranked.apply(
                    lambda r: (prev_ranks[r["symbol"]] - int(r["rank"]))
                    if r["symbol"] in prev_ranks else None,
                    axis=1,
                ),
                errors="coerce",
            )
        else:
            logger.info("No prior Phase 2 EOD snapshot — rank_change will be null")

    # ------------------------------------------------------------------ #
    # 8. Output                                                            #
    # ------------------------------------------------------------------ #
    _print_ranked_table(ranked, regime)

    if dry_run:
        logger.info("DRY RUN — no writes performed")
        return

    insert_snapshot(db_path, ranked)

    # Validation log (EOD runs only): realised forward returns for the EOD
    # snapshots from each configured horizon ago.
    if is_eod:
        snap_date = pd.Timestamp(ranked["date"].iloc[0])
        current_prices = dict(zip(ranked["symbol"], ranked["price"]))
        for horizon in cfg["validation"]["horizons_days"]:
            target_date = (snap_date - pd.Timedelta(days=horizon)).strftime("%Y-%m-%d")
            past_rows = get_eod_snapshot_by_date(db_path, target_date)
            if not past_rows:
                logger.info("Validation: no EOD snapshot for %s (h=%dd)", target_date, horizon)
                continue
            rows = compute_validation_rows(
                target_date, horizon, past_rows, current_prices, btc_now
            )
            insert_validation_rows(db_path, rows)

    # latest.json: regime + validation panel + coins
    json_path = Path(cfg["output"]["dashboard_json"])
    json_path.parent.mkdir(parents=True, exist_ok=True)
    coins = json.loads(
        ranked.where(ranked.notna(), other=None).to_json(orient="records")
    )
    payload = {
        "run_ts": run_ts,
        "is_eod": int(is_eod),
        "regime": regime,
        "validation": get_validation_recent(db_path),
        "coins": coins,
    }
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Dashboard JSON written: %s", json_path)

    # Digest: changes vs the previous EOD snapshot
    prev_state = get_prev_eod_state(db_path, run_ts)
    accum_syms = ranked.loc[ranked["accum_flag"], "symbol"].tolist()
    streaks = get_accum_streaks(db_path, accum_syms)
    if not is_eod:
        # today's run isn't an EOD row; count the live flag itself
        streaks = {s: streaks.get(s, 0) + 1 for s in accum_syms}
    validation_line = get_validation_line(
        db_path, cfg["validation"]["min_days_before_reporting"]
    )
    emit_digest(ranked, cfg, regime, prev_state, streaks, validation_line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Alt Strength Scanner")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and compute only; no writes or alerts")
    parser.add_argument("--eod", action="store_true", help="Force canonical EOD semantics regardless of hour")
    parser.add_argument("--config", default=str(_ROOT / "config.yaml"), help="Path to config.yaml")
    args = parser.parse_args()
    run(args.config, args.dry_run, args.eod)


if __name__ == "__main__":
    main()
