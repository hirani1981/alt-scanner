"""Validation log computation — do high scores actually precede gains?

For an EOD snapshot taken `horizon` days ago, compute each coin's realised
forward return (USD and BTC-relative) from then to now, and the median per
cohort. Cohorts: top decile by Early, top decile by Strength, ACCUM stage,
IGNITE stage, and the whole universe.
"""
import logging
import statistics

logger = logging.getLogger(__name__)


def _median(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def _top_decile_symbols(rows: list[dict], key: str) -> set[str]:
    scored = [(r["symbol"], r[key]) for r in rows if r.get(key) is not None]
    if not scored:
        return set()
    scored.sort(key=lambda x: x[1], reverse=True)
    n = max(1, len(scored) // 10)
    return {sym for sym, _ in scored[:n]}


def compute_validation_rows(
    snapshot_date: str,
    horizon_days: int,
    past_rows: list[dict],
    current_prices: dict[str, float],
    btc_price_now: float,
) -> list[dict]:
    """
    past_rows: EOD snapshot rows from `horizon_days` ago
               (symbol, price, btc_price, early, strength, stage).
    Returns one row per cohort with median forward returns.
    """
    # Per-coin forward returns
    fwd: dict[str, dict] = {}
    for r in past_rows:
        sym = r["symbol"]
        then_price = r.get("price")
        now_price = current_prices.get(sym)
        if not then_price or not now_price:
            continue
        fwd_usd = now_price / then_price - 1

        fwd_rs = None
        then_btc = r.get("btc_price")
        if then_btc and btc_price_now:
            btc_fwd = btc_price_now / then_btc - 1
            fwd_rs = (1 + fwd_usd) / (1 + btc_fwd) - 1

        fwd[sym] = {"usd": fwd_usd, "rs": fwd_rs}

    if not fwd:
        return []

    cohorts: dict[str, set[str]] = {
        "early_top_decile": _top_decile_symbols(past_rows, "early"),
        "strength_top_decile": _top_decile_symbols(past_rows, "strength"),
        "stage_accum": {r["symbol"] for r in past_rows if r.get("stage") == "ACCUM"},
        "stage_ignite": {r["symbol"] for r in past_rows if r.get("stage") == "IGNITE"},
        "universe": {r["symbol"] for r in past_rows},
    }

    out = []
    for cohort, symbols in cohorts.items():
        members = [fwd[s] for s in symbols if s in fwd]
        if not members:
            continue
        out.append({
            "snapshot_date": snapshot_date,
            "horizon_days": horizon_days,
            "cohort": cohort,
            "n": len(members),
            "median_fwd_ret_usd": _median([m["usd"] for m in members]),
            "median_fwd_rs": _median([m["rs"] for m in members]),
        })
    return out
