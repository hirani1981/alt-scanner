"""Backtest report builder — markdown + JSON from backtest_daily rows.

Pure functions: take the replay DataFrame, return stats. No fetching, no DB.
Success for LONG cohorts = positive forward RS; for SHORT cohorts = negative.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)

_LONG_STAGES = ["ACCUM", "IGNITE", "RUN", "EXT", "COOL", "-"]
_SHORT_COHORT_STAGES = ["DIST", "BREAK"]


def _med(s: pd.Series):
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.median()) if len(s) else None


def _pos_share(s: pd.Series, sign: int = 1):
    """Share of values whose sign matches `sign` (+1 long success, -1 short)."""
    s = pd.to_numeric(s, errors="coerce").dropna()
    if not len(s):
        return None
    return float((s * sign > 0).mean())


def _fmt_pct(v, digits=1):
    return "n/a" if v is None else f"{v * 100:+.{digits}f}%"


def _fmt_share(v):
    return "n/a" if v is None else f"{v * 100:.0f}%"


def _cell_stats(rows: pd.DataFrame, horizon: int, sign: int = 1) -> dict:
    rs = rows[f"fwd_rs_{horizon}"]
    usd = rows[f"fwd_usd_{horizon}"]
    n = int(pd.to_numeric(rs, errors="coerce").notna().sum())
    return {
        "n": n,
        "success_share": _pos_share(rs, sign),
        "median_fwd_rs": _med(rs),
        "median_fwd_usd": _med(usd),
    }


# ---------------------------------------------------------------------------
# Section builders (each returns a JSON-able dict)
# ---------------------------------------------------------------------------

def stage_outcomes(bt: pd.DataFrame, horizons: list[int], stage_col: str,
                   stages: list[str], sign: int = 1) -> dict:
    out: dict = {}
    for stage in stages + ["universe"]:
        rows = bt if stage == "universe" else bt[bt[stage_col] == stage]
        out[stage] = {str(h): _cell_stats(rows, h, sign) for h in horizons}
    return out


def decile_spread(bt: pd.DataFrame, score_col: str, horizon: int = 7) -> dict:
    """Median fwd RS of top decile vs bottom decile vs universe.
    Deciles are taken per date (cross-sectional, like the live ranking)."""
    frames_top, frames_bot = [], []
    for _, day in bt.groupby("date"):
        scores = pd.to_numeric(day[score_col], errors="coerce")
        hi = scores.quantile(0.9)
        lo = scores.quantile(0.1)
        frames_top.append(day[scores >= hi])
        frames_bot.append(day[scores <= lo])
    top = pd.concat(frames_top) if frames_top else bt.iloc[0:0]
    bot = pd.concat(frames_bot) if frames_bot else bt.iloc[0:0]
    col = f"fwd_rs_{horizon}"
    return {
        "horizon": horizon,
        "top_decile": {"n": int(top[col].notna().sum()), "median_fwd_rs": _med(top[col])},
        "bottom_decile": {"n": int(bot[col].notna().sum()), "median_fwd_rs": _med(bot[col])},
        "universe": {"n": int(bt[col].notna().sum()), "median_fwd_rs": _med(bt[col])},
    }


def flag_resolution(bt: pd.DataFrame, flag_col: str, horizons: list[int],
                    sign: int = 1) -> dict:
    rows = bt[bt[flag_col].astype(bool)]
    return {
        "n_flags": len(rows),
        "horizons": {str(h): _cell_stats(rows, h, sign) for h in horizons},
    }


def accum_resolution(bt: pd.DataFrame) -> dict:
    """Median consecutive days a coin stayed in ACCUM, and where it went next."""
    run_lengths: list[int] = []
    destinations: dict[str, int] = {}

    for _, g in bt.sort_values("date").groupby("symbol"):
        stages = g["stage"].tolist()
        dates = pd.to_datetime(g["date"]).tolist()
        i = 0
        while i < len(stages):
            if stages[i] != "ACCUM":
                i += 1
                continue
            j = i
            while j + 1 < len(stages) and stages[j + 1] == "ACCUM" \
                    and (dates[j + 1] - dates[j]).days <= 3:
                j += 1
            run_lengths.append(j - i + 1)
            if j + 1 < len(stages) and (dates[j + 1] - dates[j]).days <= 3:
                dest = stages[j + 1]
            else:
                dest = "left universe / end of data"
            destinations[dest] = destinations.get(dest, 0) + 1
            i = j + 1

    return {
        "n_runs": len(run_lengths),
        "median_days_in_accum": float(pd.Series(run_lengths).median()) if run_lengths else None,
        "destinations": dict(sorted(destinations.items(), key=lambda x: -x[1])),
    }


def short_cohorts(bt: pd.DataFrame, horizons: list[int]) -> dict:
    """DIST / BREAK stages + Weak top decile; success = NEGATIVE forward RS."""
    out = stage_outcomes(bt, horizons, "short_stage", _SHORT_COHORT_STAGES, sign=-1)
    # Weak top decile (per-date cross-sectional, like the Early spread)
    frames = []
    for _, day in bt.groupby("date"):
        w = pd.to_numeric(day["weak"], errors="coerce")
        frames.append(day[w >= w.quantile(0.9)])
    top = pd.concat(frames) if frames else bt.iloc[0:0]
    out["weak_top_decile"] = {str(h): _cell_stats(top, h, sign=-1) for h in horizons}
    return out


def regime_timeline(bt: pd.DataFrame, cfg: dict) -> dict:
    """Count of ALT_LED / NEUTRAL / BTC_LED days across the window
    (operational definitions: alt share of positive RS_7d vs config cuts)."""
    per_date = bt.groupby("date")["alt_share"].first()
    hi = cfg["regime"]["alt_led_min"] / 100.0
    lo = cfg["regime"]["btc_led_max"] / 100.0
    return {
        "n_dates": int(len(per_date)),
        "ALT_LED": int((per_date >= hi).sum()),
        "NEUTRAL": int(((per_date > lo) & (per_date < hi)).sum()),
        "BTC_LED": int((per_date <= lo).sum()),
    }


def stability_by_quarter(bt: pd.DataFrame, score_col: str = "early",
                         horizon: int = 7) -> list[dict]:
    """Early top-decile-vs-universe spread per calendar quarter — the
    anti-overfitting check: a signal that only worked in one quarter is noise."""
    quarters = pd.PeriodIndex(pd.to_datetime(bt["date"]), freq="Q").astype(str)
    out = []
    for q, g in bt.groupby(quarters):
        ds = decile_spread(g, score_col, horizon)
        top_med = ds["top_decile"]["median_fwd_rs"]
        uni_med = ds["universe"]["median_fwd_rs"]
        spread = (top_med - uni_med) if top_med is not None and uni_med is not None else None
        out.append({
            "quarter": str(q),
            "n_dates": int(g["date"].nunique()),
            "top_decile_median_fwd_rs": top_med,
            "universe_median_fwd_rs": uni_med,
            "spread": spread,
        })
    return out


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _mark_n(n: int, min_n: int) -> str:
    return f"{n}" if n >= min_n else f"{n} (insufficient sample)"


def _stage_table_md(stats: dict, horizons: list[int], min_n: int,
                    success_label: str) -> list[str]:
    lines = [
        f"| Stage | Horizon | n | {success_label} | median fwd RS | median fwd USD |",
        "|---|---|---|---|---|---|",
    ]
    for stage, by_h in stats.items():
        for h in horizons:
            c = by_h[str(h)]
            lines.append(
                f"| {stage} | {h}d | {_mark_n(c['n'], min_n)} | "
                f"{_fmt_share(c['success_share'])} | {_fmt_pct(c['median_fwd_rs'])} | "
                f"{_fmt_pct(c['median_fwd_usd'])} |"
            )
    return lines


def build_report(bt: pd.DataFrame, cfg: dict, meta: dict) -> tuple[str, dict]:
    """Returns (markdown, json_payload). meta: date_from, date_to, n_dates,
    n_symbols, config_path."""
    horizons = cfg["backtest"]["horizons_days"]
    min_n = cfg["backtest"]["min_cell_n"]

    # ---- compute all stats (full sample + regime splits)
    def all_stats(frame: pd.DataFrame) -> dict:
        return {
            "stage_outcomes": stage_outcomes(frame, horizons, "stage", _LONG_STAGES),
            "early_decile_spread": decile_spread(frame, "early", 7),
            "divergence_resolution": flag_resolution(frame, "rs_divergence", [7, 14]),
            "accum_outcomes": flag_resolution(frame, "accum_flag", horizons),
            "short_cohorts": short_cohorts(frame, horizons),
        }

    full = all_stats(bt)
    full["accum_resolution"] = accum_resolution(bt)
    full["coil_cohort"] = flag_resolution(bt, "coil_flag", horizons)
    full["regime_timeline"] = regime_timeline(bt, cfg)
    full["stability_by_quarter"] = stability_by_quarter(bt)
    alt_led = all_stats(bt[bt["alt_led"] == 1]) if (bt["alt_led"] == 1).any() else None
    btc_led = all_stats(bt[bt["alt_led"] == 0]) if (bt["alt_led"] == 0).any() else None

    n_alt_days = int(bt[bt["alt_led"] == 1]["date"].nunique())
    n_btc_days = int(bt[bt["alt_led"] == 0]["date"].nunique())

    payload = {
        "meta": meta,
        "full_sample": full,
        "regime_split": {
            "alt_led": {"n_dates": n_alt_days, "stats": alt_led},
            "btc_led": {"n_dates": n_btc_days, "stats": btc_led},
        },
    }

    # ---- markdown
    L: list[str] = []
    L.append("# Backtest Report — Alt Strength Scanner")
    L.append("")
    L.append("## 1. Read this first (honesty block)")
    L.append(f"- Date range: **{meta['date_from']} to {meta['date_to']}** "
             f"({meta['n_dates']} evaluable dates, {meta['n_symbols']} candidate symbols).")
    L.append("- **Survivorship bias:** the universe is reconstructed per-date, but only "
             "from coins listed TODAY. Delisted and dead coins are absent, so results "
             "are flattered — real-time performance will be worse than shown here.")
    L.append(f"- This report describes the CURRENT config ({meta['config_path']}); "
             "no parameters were tuned against these results.")
    L.append("- The backtest is a hypothesis generator; the LIVE validation table "
             "remains the verdict.")
    L.append("")

    tl = full["regime_timeline"]
    L.append("## 1b. Regime timeline")
    L.append(f"Of {tl['n_dates']} evaluable dates: **ALT_LED {tl['ALT_LED']}** "
             f"(alt share >= {cfg['regime']['alt_led_min']}%), "
             f"**NEUTRAL {tl['NEUTRAL']}**, "
             f"**BTC_LED {tl['BTC_LED']}** (alt share <= {cfg['regime']['btc_led_max']}%).")
    L.append("")

    L.append("## 2. Per-stage outcomes (long side; success = positive forward RS)")
    L += _stage_table_md(full["stage_outcomes"], horizons, min_n, "% positive fwd RS")
    L.append("")

    d = full["early_decile_spread"]
    L.append("## 3. Early-score decile spread (median 7d forward RS)")
    L.append("| Cohort | n | median 7d fwd RS |")
    L.append("|---|---|---|")
    L.append(f"| Early top decile | {_mark_n(d['top_decile']['n'], min_n)} | {_fmt_pct(d['top_decile']['median_fwd_rs'])} |")
    L.append(f"| Early bottom decile | {_mark_n(d['bottom_decile']['n'], min_n)} | {_fmt_pct(d['bottom_decile']['median_fwd_rs'])} |")
    L.append(f"| Universe | {_mark_n(d['universe']['n'], min_n)} | {_fmt_pct(d['universe']['median_fwd_rs'])} |")
    L.append("")

    L.append("### 3b. Stability by calendar quarter (anti-overfitting check)")
    L.append("Early top-decile-vs-universe spread, 7d fwd RS, per quarter. "
             "A signal that only worked in one quarter is noise.")
    L.append("| Quarter | dates | top decile median | universe median | spread |")
    L.append("|---|---|---|---|---|")
    for q in full["stability_by_quarter"]:
        L.append(f"| {q['quarter']} | {q['n_dates']} | "
                 f"{_fmt_pct(q['top_decile_median_fwd_rs'])} | "
                 f"{_fmt_pct(q['universe_median_fwd_rs'])} | "
                 f"{_fmt_pct(q['spread'], 2)} |")
    L.append("")

    dv = full["divergence_resolution"]
    L.append("## 4. RS-divergence resolution")
    L.append(f"Flags: {dv['n_flags']}")
    L.append("| Horizon | n | % positive fwd RS | median fwd RS | median fwd USD |")
    L.append("|---|---|---|---|---|")
    for h in (7, 14):
        c = dv["horizons"][str(h)]
        L.append(f"| {h}d | {_mark_n(c['n'], min_n)} | {_fmt_share(c['success_share'])} | "
                 f"{_fmt_pct(c['median_fwd_rs'])} | {_fmt_pct(c['median_fwd_usd'])} |")
    L.append("")

    ac = full["accum_outcomes"]
    res = full["accum_resolution"]
    L.append("## 5. ACCUM outcomes")
    L.append(f"Flags: {ac['n_flags']}")
    L.append("| Horizon | n | % positive fwd RS | median fwd RS | median fwd USD |")
    L.append("|---|---|---|---|---|")
    for h in horizons:
        c = ac["horizons"][str(h)]
        L.append(f"| {h}d | {_mark_n(c['n'], min_n)} | {_fmt_share(c['success_share'])} | "
                 f"{_fmt_pct(c['median_fwd_rs'])} | {_fmt_pct(c['median_fwd_usd'])} |")
    L.append("")
    L.append(f"ACCUM runs: {res['n_runs']}; median days in ACCUM: {res['median_days_in_accum']}")
    L.append("Resolution destinations (stage after leaving ACCUM):")
    for dest, cnt in res["destinations"].items():
        L.append(f"- {dest}: {cnt}")
    L.append("")

    L.append("## 6. Short-side cohorts (success = NEGATIVE forward RS)")
    L.append("Computed for Part B review; UI remains OFF (shorts.enabled: false). "
             "DIST here is v2 (requires down-volume dominance + RS below its 10d MA).")
    L += _stage_table_md(full["short_cohorts"], horizons, min_n, "% negative fwd RS")
    L.append("")

    co = full["coil_cohort"]
    L.append("## 6b. Coil cohort (measured, NOT scored; hypothesized bullish "
             "continuation — success = POSITIVE forward RS)")
    L.append(f"Flags: {co['n_flags']}. Joins no stage and no score in hypothesis v2; "
             "earns a place in v3 only if this evidence holds.")
    L.append("| Horizon | n | % positive fwd RS | median fwd RS | median fwd USD |")
    L.append("|---|---|---|---|---|")
    for h in horizons:
        c = co["horizons"][str(h)]
        L.append(f"| {h}d | {_mark_n(c['n'], min_n)} | {_fmt_share(c['success_share'])} | "
                 f"{_fmt_pct(c['median_fwd_rs'])} | {_fmt_pct(c['median_fwd_usd'])} |")
    L.append("")

    L.append("## 7. Regime split")
    L.append(f"Alt-led days (>50% of universe beating BTC over 7d): {n_alt_days}; "
             f"BTC-led days: {n_btc_days}.")
    for name, stats, n_days in (("Alt-led", alt_led, n_alt_days), ("BTC-led", btc_led, n_btc_days)):
        L.append("")
        L.append(f"### 7.{1 if name == 'Alt-led' else 2} {name} tape ({n_days} dates)")
        if stats is None:
            L.append("No dates in this regime.")
            continue
        L.append("")
        L.append(f"**Per-stage outcomes (7d):**")
        L.append("| Stage | n | % positive fwd RS | median fwd RS | median fwd USD |")
        L.append("|---|---|---|---|---|")
        for stage, by_h in stats["stage_outcomes"].items():
            c = by_h["7"]
            L.append(f"| {stage} | {_mark_n(c['n'], min_n)} | {_fmt_share(c['success_share'])} | "
                     f"{_fmt_pct(c['median_fwd_rs'])} | {_fmt_pct(c['median_fwd_usd'])} |")
        ds = stats["early_decile_spread"]
        L.append("")
        L.append(f"**Early decile spread (7d):** top {_fmt_pct(ds['top_decile']['median_fwd_rs'])} "
                 f"(n={ds['top_decile']['n']}) vs bottom {_fmt_pct(ds['bottom_decile']['median_fwd_rs'])} "
                 f"(n={ds['bottom_decile']['n']}) vs universe {_fmt_pct(ds['universe']['median_fwd_rs'])}.")
        dvr = stats["divergence_resolution"]
        c7 = dvr["horizons"]["7"]
        L.append(f"**Divergence (7d):** n={_mark_n(c7['n'], min_n)}, "
                 f"{_fmt_share(c7['success_share'])} positive, median {_fmt_pct(c7['median_fwd_rs'])}.")
        sc = stats["short_cohorts"]
        for cohort in ("DIST", "BREAK", "weak_top_decile"):
            c7 = sc[cohort]["7"]
            L.append(f"**{cohort} (7d, short):** n={_mark_n(c7['n'], min_n)}, "
                     f"{_fmt_share(c7['success_share'])} negative, median {_fmt_pct(c7['median_fwd_rs'])}.")
    L.append("")

    return "\n".join(L), payload
