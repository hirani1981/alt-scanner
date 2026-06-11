"""Cross-sectional percentile ranking, Strength & Early scores, and stage tags."""
import numpy as np
import pandas as pd


def _pct_rank(series: pd.Series) -> pd.Series:
    """Percentile rank within the universe, 0 (weakest) → 1 (strongest).
    NaN values are filled with the cross-sectional median before ranking
    so a missing signal doesn't propagate to a zero score."""
    numeric = pd.to_numeric(series, errors="coerce")
    filled = numeric.fillna(numeric.median())
    return filled.rank(pct=True, method="average")


def _assign_stage(r: pd.Series, st: dict) -> str:
    """First match wins: EXT → IGNITE → ACCUM → RUN → COOL → '-'."""
    if r["extension_pct"] >= st["ext_rs30_pctile"] / 100.0:
        return "EXT"
    vol_z = r["vol_z"]
    if (r["rs_divergence"] or r["rs_new_high"]) and pd.notna(vol_z) and vol_z >= st["ignite_volz_min"]:
        return "IGNITE"
    if r["accum_flag"]:
        return "ACCUM"
    if r["strength_pct"] >= st["run_strength_pctile"] / 100.0 and r["rs_persistence"] >= st["run_persistence_min"]:
        return "RUN"
    rs7, rs30 = r["rs_7d"], r["rs_30d"]
    if pd.notna(rs7) and pd.notna(rs30) and rs7 < 0 and rs30 > 0:
        return "COOL"
    return "-"


def _assign_short_stage(r: pd.Series, st: dict, oversold_cut: float) -> str:
    """Mirror of the long stages, first match wins:
    OVERSOLD → BREAK → DIST → SLIDE → RELIEF → '-'.
    BREAK reuses the IGNITE vol_z threshold and SLIDE the RUN percentile /
    persistence thresholds — they are deliberate mirrors, not new knobs."""
    if r["extension_pct"] <= oversold_cut:
        return "OVERSOLD"
    vol_z = r["vol_z"]
    if r["rs_breakdown"] and pd.notna(vol_z) and vol_z >= st["ignite_volz_min"]:
        return "BREAK"
    if r["dist_flag"]:
        return "DIST"
    if r["weak_pct"] >= st["run_strength_pctile"] / 100.0 and r["weak_persistence"] >= st["run_persistence_min"]:
        return "SLIDE"
    rs7, rs30 = r["rs_7d"], r["rs_30d"]
    if pd.notna(rs7) and pd.notna(rs30) and rs7 > 0 and rs30 < 0:
        return "RELIEF"
    return "-"


def compute_scores(rows: list[dict], config: dict) -> pd.DataFrame:
    """
    Accept per-coin metric dicts (from compute_coin_metrics), compute
    cross-sectional flags, the Strength and Early scores, stage tags,
    and rank by Early descending (Phase 2 rank semantics).
    """
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    sc = config["scoring"]
    sig = config["signals"]
    st = config["stages"]

    # Normalise flag columns: missing → False / 0
    df["rs_divergence"] = df["rs_divergence"].fillna(False).astype(bool)
    df["rs_new_high"] = df["rs_new_high"].fillna(False).astype(bool)
    df["rs_persistence"] = pd.to_numeric(df["rs_persistence"], errors="coerce").fillna(0).astype(int)
    df["rs_breakdown"] = df["rs_breakdown"].fillna(False).astype(bool)
    df["rs_new_low"] = df["rs_new_low"].fillna(False).astype(bool)
    df["weak_persistence"] = pd.to_numeric(df["weak_persistence"], errors="coerce").fillna(0).astype(int)

    # ------------------------------------------------------------------ #
    # Strength score (the Phase 1 composite — "how strong is it")          #
    # ------------------------------------------------------------------ #
    rs_w = sc["rs_window_weights"]
    rs_blend = pd.Series(0.0, index=df.index)
    for w, weight in rs_w.items():
        pct_col = f"rs{w}_pct"
        df[pct_col] = _pct_rank(df[f"rs_{w}d"])
        rs_blend += weight * df[pct_col]
    df["rs_pct"] = rs_blend

    df["vol_pct"] = _pct_rank(df["vol_z"])
    df["structure_norm"] = df["structure"] / 4.0

    sw = sc["strength_weights"]
    df["strength"] = (
        sw["relative_strength"] * df["rs_pct"]
        + sw["volume_surge"] * df["vol_pct"]
        + sw["structure"] * df["structure_norm"]
    )
    df["strength_pct"] = _pct_rank(df["strength"])

    # ------------------------------------------------------------------ #
    # Cross-sectional quiet-accumulation flags                             #
    # ------------------------------------------------------------------ #
    vol_trend = pd.to_numeric(df["vol_trend"], errors="coerce")
    range_rank = _pct_rank(df["range_pct_10d"])
    df["price_quiet"] = range_rank <= sig["quiet_range_pctile"] / 100.0

    df["extension_pct"] = _pct_rank(df["rs_30d"])
    df["not_extended"] = df["extension_pct"] < sig["extended_pctile"] / 100.0

    df["accum_flag"] = (
        (vol_trend >= sig["vol_trend_min"]).fillna(False)
        & df["price_quiet"]
        & df["not_extended"]
    )

    # ------------------------------------------------------------------ #
    # Early score ("how early does this look")                             #
    # ------------------------------------------------------------------ #
    ew = sc["early_weights"]
    nh_partial = sc["rs_new_high_partial"]
    accum_scale = sc["accum_partial_scale"]

    divergence_comp = np.where(
        df["rs_divergence"], 1.0, np.where(df["rs_new_high"], nh_partial, 0.0)
    )
    vol_trend_pct = _pct_rank(vol_trend)
    accum_comp = np.where(df["accum_flag"], 1.0, accum_scale * vol_trend_pct)
    persistence_pct = _pct_rank(df["rs_persistence"])

    df["early"] = (
        ew["divergence"] * divergence_comp
        + ew["accumulation"] * accum_comp
        + ew["persistence"] * persistence_pct
        + ew["extension_penalty"] * (1 - df["extension_pct"])
    )

    # ------------------------------------------------------------------ #
    # Stage tags (first match wins)                                        #
    # ------------------------------------------------------------------ #
    df["stage"] = df.apply(_assign_stage, axis=1, st=st)

    # Stage-aware penalty: an EXT coin already ran — it cannot look early,
    # even if it fires RS-new-high. Applied before ranking.
    df.loc[df["stage"] == "EXT", "early"] *= sc["early_ext_penalty"]

    # ------------------------------------------------------------------ #
    # Short side (mirror) — computed every run; UI rendering is gated by    #
    # shorts.enabled, computation is not (gated rendering, not computation) #
    # ------------------------------------------------------------------ #
    shorts = config["shorts"]
    ww = shorts["weak_weights"]

    # DIST v2: the v1 footprint (extended + quiet + volume building) described
    # bullish consolidation and backtested as an anti-signal. Distribution now
    # additionally requires EVIDENCE OF SUPPLY: down-day volume dominating the
    # basing window, and the RS line already below its 10d MA (weakness
    # appearing at the highs). Deliberate asymmetry vs accum stands: accum
    # requires NOT-extended, distribution requires extended.
    extended_mask = ~df["not_extended"]
    down_vol = pd.to_numeric(df["down_vol_ratio"], errors="coerce")
    rs_below = df["rs_below_ma"].fillna(False).astype(bool)
    base_footprint = (
        (vol_trend >= sig["vol_trend_min"]).fillna(False)
        & df["price_quiet"]
        & extended_mask
    )
    df["dist_flag"] = (
        base_footprint
        & (down_vol >= sig["dist_down_vol_min"]).fillna(False)
        & rs_below
    )
    # Coil: the same footprint with BUYERS dominating — the bullish
    # continuation pattern the old DIST accidentally captured. Measured in
    # backtest cohorts only; joins NO stage and NO score in hypothesis v2.
    df["coil_flag"] = base_footprint & (down_vol <= sig["coil_up_vol_max"]).fillna(False)

    breakdown_comp = np.where(
        df["rs_breakdown"], 1.0, np.where(df["rs_new_low"], nh_partial, 0.0)
    )
    distribution_comp = np.where(
        df["dist_flag"], 1.0,
        np.where(extended_mask, accum_scale * vol_trend_pct, 0.0),
    )
    weak_persistence_pct = _pct_rank(df["weak_persistence"])
    # Lateness penalty: percentile of collapse depth (most-negative RS_30d
    # ranks highest), inverted — already-collapsed coins are bounce risk.
    collapse_pct = _pct_rank(-pd.to_numeric(df["rs_30d"], errors="coerce"))

    df["weak"] = (
        ww["breakdown"] * breakdown_comp
        + ww["distribution"] * distribution_comp
        + ww["persistence"] * weak_persistence_pct
        + ww["lateness_penalty"] * (1 - collapse_pct)
    )
    df["weak_pct"] = _pct_rank(df["weak"])

    df["short_stage"] = df.apply(
        _assign_short_stage, axis=1, st=st, oversold_cut=shorts["oversold_pctile"] / 100.0
    )

    # Mirror of the EXT penalty: an OVERSOLD coin already collapsed —
    # it is bounce risk, not a short entry.
    df.loc[df["short_stage"] == "OVERSOLD", "weak"] *= shorts["weak_oversold_penalty"]

    # ------------------------------------------------------------------ #
    # Rank by Early descending (Phase 2 semantics)                         #
    # ------------------------------------------------------------------ #
    df = df.sort_values("early", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    df["rank_change"] = None

    return df
