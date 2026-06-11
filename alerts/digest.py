"""Daily digest -- changes first (brief section 8).

Order: regime line, new ACCUM flags, new IGNITE/divergence flags,
new entrants to the Early top-20, volume-z alerts, top 10 by Early,
then the validation line once enough data exists.

"New" = present in this run, absent in the previous EOD snapshot.
"""
import logging
import sys
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def _pct(val) -> str:
    if val is None or pd.isna(val):
        return "n/a"
    return f"{val * 100:+.1f}%"


def _num(val, fmt="{:.2f}") -> str:
    if val is None or pd.isna(val):
        return "n/a"
    return fmt.format(val)


def build_digest(
    df: pd.DataFrame,
    config: dict,
    regime: dict,
    prev_state: dict[str, dict],
    accum_streaks: dict[str, int],
    validation_line: str | None,
) -> str:
    """Return the digest as a markdown string (ASCII-safe for cp1252 consoles)."""
    acfg = config["alerts"]
    top_n = acfg["top_n"]
    vol_threshold = acfg["volume_z_alert"]

    snapshot_date = df["date"].iloc[0]
    lines: list[str] = [
        f"# Alt Strength Digest - {snapshot_date}",
        "",
        f"**Regime [{regime.get('regime_class', '-')}]:** {regime['line']}",
        "_Default view sorts by ACCUM intensity, not Early or divergence (config v2). "
        "Regime is context only._",
        f"Breadth: {regime['breadth']['week']}/{regime['universe_size']} above W, "
        f"{regime['breadth']['month']} above M, {regime['breadth']['quarter']} above Q, "
        f"{regime['breadth']['year']} above Y."
        + (f"  BTC {_pct(regime['btc_pct_month'] / 100)} vs monthly open."
           if regime.get("btc_pct_month") is not None else ""),
        "",
    ]

    def was(sym: str, key: str):
        return prev_state.get(sym, {}).get(key)

    # --- 1. New ACCUM flags ---
    new_accum = df[
        df["accum_flag"]
        & df["symbol"].map(lambda s: not prev_state.get(s, {}).get("accum_flag", False))
    ]
    lines.append("## New ACCUM flags (quiet accumulation, newly flagged)")
    if new_accum.empty:
        lines.append("  none")
    else:
        for _, r in new_accum.iterrows():
            days = accum_streaks.get(r["symbol"], 1) or 1
            lines.append(
                f"  {r['symbol']:<14} vol_trend={_num(r['vol_trend'])}  "
                f"10d range={_num(r['range_pct_10d'], '{:.1%}')}  days flagged={days}"
            )
    lines.append("")

    # --- 2. New IGNITE / RS-divergence flags ---
    newly_ignite = df[
        (df["stage"] == "IGNITE") & df["symbol"].map(lambda s: was(s, "stage") != "IGNITE")
    ]
    newly_diverging = df[
        df["rs_divergence"]
        & df["symbol"].map(lambda s: not prev_state.get(s, {}).get("rs_divergence", False))
    ]
    new_fire = pd.concat([newly_ignite, newly_diverging]).drop_duplicates(subset="symbol")
    lines.append("## New IGNITE / RS-divergence flags")
    if new_fire.empty:
        lines.append("  none")
    else:
        for _, r in new_fire.iterrows():
            tag = "IGNITE" if r["stage"] == "IGNITE" else "RS-divergence"
            lines.append(
                f"  {r['symbol']:<14} {tag:<14} RS_7d={_pct(r['rs_7d'])}  vol_z={_num(r['vol_z'], '{:.1f}')}"
            )
    lines.append("")

    # --- 3. New entrants to the Early top-20 ---
    top20 = df[df["rank"] <= 20]
    entrants = top20[top20["symbol"].map(
        lambda s: (prev_state.get(s, {}).get("rank") or 999) > 20
    )]
    lines.append("## New entrants to the Early top-20")
    if entrants.empty:
        lines.append("  none")
    else:
        for _, r in entrants.iterrows():
            lines.append(
                f"  #{int(r['rank']):<3} {r['symbol']:<14} early={r['early']:.3f}  stage={r['stage']}"
            )
    lines.append("")

    # --- 4. Volume surge alerts ---
    vol_alerts = df[df["vol_z"] >= vol_threshold].sort_values("vol_z", ascending=False)
    lines.append(f"## Volume surge alerts (vol_z >= {vol_threshold})")
    if vol_alerts.empty:
        lines.append("  none")
    else:
        for _, r in vol_alerts.iterrows():
            lines.append(
                f"  {r['symbol']:<14} vol_z={_num(r['vol_z'], '{:.1f}')}  rank=#{int(r['rank'])}  stage={r['stage']}"
            )
    lines.append("")

    # --- 5. The standings: top N by Early (last, not first) ---
    lines.append(f"## Top {top_n} by Early score")
    lines.append(
        f"{'#':<4} {'Symbol':<14} {'Stage':<7} {'Early':>6} {'Strgth':>7} "
        f"{'RS 24h':>7} {'RS 7d':>7} {'RS 30d':>7} {'VolZ':>5} {'VolTr':>6}"
    )
    lines.append("-" * 84)
    for _, r in df.nsmallest(top_n, "rank").iterrows():
        lines.append(
            f"{int(r['rank']):<4} {r['symbol']:<14} {r['stage']:<7} "
            f"{r['early']:>6.3f} {r['strength']:>7.3f} "
            f"{_pct(r['rs_1d']):>7} {_pct(r['rs_7d']):>7} {_pct(r['rs_30d']):>7} "
            f"{_num(r['vol_z'], '{:.1f}'):>5} {_num(r['vol_trend']):>6}"
        )
    lines.append("")

    # --- 6. Validation line (once enough history exists) ---
    if validation_line:
        lines.append(validation_line)
        lines.append("")

    # --- Footer: cite the frozen hypothesis version ---
    hyp = config.get("hypothesis", {})
    lines.append("---")
    lines.append(
        f"_config {hyp.get('version', '?')} (frozen {hyp.get('frozen', '?')}) — "
        "see HYPOTHESIS.md. Stored rank & validation cohorts remain Early-based._"
    )

    return "\n".join(lines)


def emit_digest(
    df: pd.DataFrame,
    config: dict,
    regime: dict,
    prev_state: dict[str, dict],
    accum_streaks: dict[str, int],
    validation_line: str | None,
) -> None:
    """Print digest to console and optionally write to file / Telegram."""
    text = build_digest(df, config, regime, prev_state, accum_streaks, validation_line)
    channel = config["alerts"]["channel"]

    # Console: encode safely for narrow-codec terminals (e.g. Windows cp1252)
    out = ("\n" + text).encode(sys.stdout.encoding or "utf-8", errors="replace")
    sys.stdout.buffer.write(out + b"\n")

    if channel in ("file", "telegram"):
        out_path = Path(config["output"]["digest_file"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        logger.info("Digest written to %s", out_path)

    if channel == "telegram":
        try:
            from alerts.telegram import send_telegram
            send_telegram(text, config)
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)
