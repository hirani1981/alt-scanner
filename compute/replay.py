"""Historical replay engine — sweeps the LIVE compute path over past dates.

Single code path (critical): every signal/score/stage is produced by
compute_coin_metrics(..., as_of=D) and compute_scores — the exact functions
the live run uses. This module only reconstructs the per-date universe and
measures forward returns. Never reimplement signal logic here.
"""
import logging

import pandas as pd

from compute.metrics import compute_coin_metrics
from compute.scoring import compute_scores

logger = logging.getLogger(__name__)

# Columns carried into backtest_daily (rs_spark and display fields dropped)
_ROW_COLS = [
    "symbol", "stage", "early", "strength",
    "rs_divergence", "rs_new_high", "accum_flag", "rs_persistence",
    "short_stage", "weak", "rs_breakdown", "dist_flag", "weak_persistence",
    "coil_flag", "down_vol_ratio",
    "rs_7d", "rs_30d", "vol_z", "vol_trend",
]


def _fwd_return(closes, pos_map: dict, date: pd.Timestamp, horizon: int):
    """Forward return close[D+h]/close[D]-1 using row offsets (daily candles
    are continuous in crypto, so row offset == calendar days)."""
    i = pos_map.get(date)
    if i is None:
        return None
    j = i + horizon
    if j >= len(closes):
        return None
    base = closes[i]
    if not base:
        return None
    return closes[j] / base - 1


def evaluable_dates(
    klines: dict[str, pd.DataFrame],
    btc_df: pd.DataFrame,
    cfg: dict,
) -> list[pd.Timestamp]:
    """Dates D where >= min_universe_for_replay coins have >= warmup_days of
    history up to D, and D has >= max(horizons) days of data after it."""
    bt = cfg["backtest"]
    warmup = bt["warmup_days"]
    min_uni = bt["min_universe_for_replay"]
    max_h = max(bt["horizons_days"])

    # Date at which each coin first has `warmup` candles
    eligibility: list[pd.Timestamp] = []
    for df in klines.values():
        if len(df) >= warmup:
            eligibility.append(df.index[warmup - 1])
    if not eligibility:
        return []
    eligibility.sort()

    last_evaluable = btc_df.index[-(max_h + 1)]
    out = []
    for d in btc_df.index:
        if d > last_evaluable:
            break
        # coins eligible at d = eligibility dates <= d (sorted → bisect-like count)
        n_eligible = sum(1 for e in eligibility if e <= d)
        if n_eligible >= min_uni:
            out.append(d)
    return out


def run_replay(
    klines: dict[str, pd.DataFrame],
    btc_df: pd.DataFrame,
    cfg: dict,
    max_dates: int | None = None,
) -> pd.DataFrame:
    """
    Replay the signal engine over every evaluable date.
    Returns one row per (date, symbol) with stages, scores, flags,
    forward returns (USD and BTC-relative) and the regime marker.
    """
    bt = cfg["backtest"]
    warmup = bt["warmup_days"]
    min_uni = bt["min_universe_for_replay"]
    horizons = bt["horizons_days"]
    vol_window = bt["universe_vol_window_days"]
    max_universe = cfg["universe"]["max_universe"]

    dates = evaluable_dates(klines, btc_df, cfg)
    if max_dates:
        dates = dates[-max_dates:]
    if not dates:
        logger.error("No evaluable dates — not enough history")
        return pd.DataFrame()
    logger.info("Replaying %d dates: %s -> %s", len(dates), dates[0].date(), dates[-1].date())

    # Precompute per symbol: trailing-volume series, close arrays, date->row maps
    vol_ma: dict[str, pd.Series] = {}
    closes: dict[str, list[float]] = {}
    pos_maps: dict[str, dict] = {}
    elig_date: dict[str, pd.Timestamp] = {}
    for sym, df in klines.items():
        if len(df) < warmup:
            continue
        vol_ma[sym] = df["quote_volume"].rolling(vol_window).mean()
        closes[sym] = df["close"].to_list()
        pos_maps[sym] = {ts: i for i, ts in enumerate(df.index)}
        elig_date[sym] = df.index[warmup - 1]

    btc_closes = btc_df["close"].to_list()
    btc_pos = {ts: i for i, ts in enumerate(btc_df.index)}

    records: list[dict] = []
    for n_done, d in enumerate(dates, 1):
        # ---- per-date universe: top max_universe by trailing volume as of d
        ranked_syms = sorted(
            (
                (sym, float(vol_ma[sym].get(d)))
                for sym in vol_ma
                if elig_date[sym] <= d and pd.notna(vol_ma[sym].get(d))
            ),
            key=lambda x: x[1],
            reverse=True,
        )
        universe = [sym for sym, _ in ranked_syms[:max_universe]]
        if len(universe) < min_uni:
            continue

        # ---- same compute path as the live run, cut off at d
        rows = []
        for sym in universe:
            m = compute_coin_metrics(sym, klines[sym], btc_df, cfg, as_of=d)
            if m is not None:
                rows.append(m)
        if len(rows) < min_uni:
            continue
        ranked = compute_scores(rows, cfg)

        # ---- regime marker: share of the universe beating BTC over 7d
        rs7 = pd.to_numeric(ranked["rs_7d"], errors="coerce")
        alt_share = float((rs7 > 0).mean())
        alt_led = int(alt_share > 0.5)

        # ---- forward returns (> d only)
        btc_fwd = {h: _fwd_return(btc_closes, btc_pos, d, h) for h in horizons}

        date_str = d.strftime("%Y-%m-%d")
        for _, r in ranked.iterrows():
            rec = {c: r[c] for c in _ROW_COLS}
            rec["date"] = date_str
            rec["alt_share"] = alt_share
            rec["alt_led"] = alt_led
            sym = r["symbol"]
            for h in horizons:
                u = _fwd_return(closes[sym], pos_maps[sym], d, h)
                rec[f"fwd_usd_{h}"] = u
                b = btc_fwd[h]
                rec[f"fwd_rs_{h}"] = (
                    (1 + u) / (1 + b) - 1 if u is not None and b is not None else None
                )
            records.append(rec)

        if n_done % 25 == 0 or n_done == len(dates):
            logger.info("  ...replayed %d / %d dates", n_done, len(dates))

    out = pd.DataFrame(records)
    logger.info("Replay complete: %d rows across %d dates", len(out), out["date"].nunique() if not out.empty else 0)
    return out
