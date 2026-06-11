"""Per-coin signal computation — opens, relative strength, volume z-score, structure."""
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Period opens
# ---------------------------------------------------------------------------

def _period_open_dates(snapshot_date: pd.Timestamp) -> dict[str, pd.Timestamp]:
    """Return the UTC-midnight timestamps for each period's opening candle."""
    d = snapshot_date

    # Most recent Monday on or before snapshot_date
    monday = d - pd.Timedelta(days=d.dayofweek)  # dayofweek: Mon=0

    # 1st of current month
    month_start = d.replace(day=1)

    # 1st of current quarter
    quarter_month = ((d.month - 1) // 3) * 3 + 1
    quarter_start = d.replace(month=quarter_month, day=1)

    # Jan 1 of current year
    year_start = d.replace(month=1, day=1)

    return {
        "week": monday,
        "month": month_start,
        "quarter": quarter_start,
        "year": year_start,
    }


def get_period_opens(df: pd.DataFrame, snapshot_date: pd.Timestamp) -> dict[str, Optional[float]]:
    """
    Look up the candle open for each period boundary in df.
    Returns None for any period where no candle exists (coin too new).
    """
    dates = _period_open_dates(snapshot_date)
    opens: dict[str, Optional[float]] = {}
    for key, target in dates.items():
        # Normalise to midnight UTC to match DataFrame index
        ts = pd.Timestamp(target.year, target.month, target.day, tz="UTC")
        if ts in df.index:
            opens[key] = float(df.loc[ts, "open"])
        else:
            opens[key] = None
            logger.debug("No candle for %s open (%s) in %s", key, ts.date(), df.index[-1].date())
    return opens


# ---------------------------------------------------------------------------
# Relative strength vs BTC
# ---------------------------------------------------------------------------

def compute_relative_strength(
    coin_df: pd.DataFrame,
    btc_df: pd.DataFrame,
    windows: list[int],
) -> dict[int, Optional[float]]:
    """
    True BTC-denominated return: rs_w = (1 + alt_ret_w) / (1 + btc_ret_w) - 1.
    This is the alt's return priced in BTC, computed from existing USD data.
    Crypto trades every day, so positional look-back is safe.
    Returns None for any window where there is insufficient history.
    """
    result: dict[int, Optional[float]] = {}
    last_coin = float(coin_df["close"].iloc[-1])
    last_btc = float(btc_df["close"].iloc[-1])

    for w in windows:
        required = w + 1  # need today + w prior candles
        if len(coin_df) < required or len(btc_df) < required:
            result[w] = None
            continue
        coin_w = float(coin_df["close"].iloc[-(w + 1)])
        btc_w = float(btc_df["close"].iloc[-(w + 1)])

        coin_ret = last_coin / coin_w - 1
        btc_ret = last_btc / btc_w - 1
        result[w] = (1 + coin_ret) / (1 + btc_ret) - 1

    return result


# ---------------------------------------------------------------------------
# Volume z-score
# ---------------------------------------------------------------------------

def compute_volume_zscore(
    df: pd.DataFrame,
    baseline_days: int,
    clamp: float,
) -> Optional[float]:
    """
    vol_z = (today_vol - mean(baseline)) / std(baseline)
    baseline = the `baseline_days` candles immediately before today's candle.
    Clamped to ±clamp.
    """
    required = baseline_days + 1
    if len(df) < required:
        return None

    today_vol = float(df["quote_volume"].iloc[-1])
    baseline = df["quote_volume"].iloc[-(baseline_days + 1):-1]

    std = baseline.std(ddof=1)
    if std == 0 or pd.isna(std):
        return 0.0

    z = (today_vol - baseline.mean()) / std
    return max(-clamp, min(clamp, z))


# ---------------------------------------------------------------------------
# RS line (alt priced in BTC) and its leading signals
# ---------------------------------------------------------------------------

def compute_rs_line(coin_df: pd.DataFrame, btc_df: pd.DataFrame) -> pd.Series:
    """
    RS line = alt_close / btc_close for every shared date.
    Computed from klines at run time — never from accumulated snapshots,
    so all RS-line signals work from the first run.
    """
    coin, btc = coin_df["close"].align(btc_df["close"], join="inner")
    return coin / btc


def _streak(flags, cap: int) -> int:
    """Length of the trailing run of True values, capped."""
    n = 0
    for flag in flags[::-1]:
        if not flag:
            break
        n += 1
        if n >= cap:
            break
    return n


def compute_rs_line_signals(
    rs_line: pd.Series,
    closes: pd.Series,
    lookback: int,
    ma_days: int,
    persistence_cap: int,
) -> dict:
    """
    Long side:
      rs_new_high:    RS line today is the highest of the last `lookback` days.
      price_new_high: USD close today is the highest of the same lookback.
      rs_divergence:  rs_new_high AND NOT price_new_high — relative strength
                      breaking out before price does (the leading flag).
      rs_persistence: consecutive days the RS line closed above its
                      `ma_days`-day SMA, capped at `persistence_cap`.
    Short side (bearish mirrors):
      rs_new_low / price_new_low: same lookback, lows instead of highs.
      rs_breakdown:   rs_new_low AND NOT price_new_low — relative weakness
                      leading price; distribution before the chart breaks.
      weak_persistence: consecutive days the RS line closed BELOW the SMA.
    """
    rs_window = rs_line.iloc[-lookback:]
    price_window = closes.iloc[-lookback:]

    rs_now = float(rs_line.iloc[-1])
    price_now = float(closes.iloc[-1])

    rs_new_high = bool(rs_now >= float(rs_window.max()))
    price_new_high = bool(price_now >= float(price_window.max()))
    rs_divergence = rs_new_high and not price_new_high

    rs_new_low = bool(rs_now <= float(rs_window.min()))
    price_new_low = bool(price_now <= float(price_window.min()))
    rs_breakdown = rs_new_low and not price_new_low

    ma = rs_line.rolling(ma_days).mean()
    above = (rs_line > ma).to_numpy()
    below = (rs_line < ma).to_numpy()

    return {
        "rs_new_high": rs_new_high,
        "price_new_high": price_new_high,
        "rs_divergence": rs_divergence,
        "rs_persistence": _streak(above, persistence_cap),
        "rs_new_low": rs_new_low,
        "price_new_low": price_new_low,
        "rs_breakdown": rs_breakdown,
        "weak_persistence": _streak(below, persistence_cap),
        # DIST v2 ingredient: weakness appearing at the highs today
        "rs_below_ma": bool(below[-1]) if len(below) else False,
    }


# ---------------------------------------------------------------------------
# Quiet accumulation inputs (cross-sectional flags are set in scoring)
# ---------------------------------------------------------------------------

def compute_vol_trend(df: pd.DataFrame, fast_days: int, slow_days: int) -> Optional[float]:
    """mean(quote_volume, fast) / mean(quote_volume, slow) — building attention."""
    if len(df) < slow_days:
        return None
    fast_mean = float(df["quote_volume"].iloc[-fast_days:].mean())
    slow_mean = float(df["quote_volume"].iloc[-slow_days:].mean())
    if slow_mean == 0:
        return None
    return fast_mean / slow_mean


def compute_range_pct(df: pd.DataFrame, days: int) -> Optional[float]:
    """N-day price range as a fraction of current price — small = basing."""
    if len(df) < days:
        return None
    hi = float(df["high"].iloc[-days:].max())
    lo = float(df["low"].iloc[-days:].min())
    close = float(df["close"].iloc[-1])
    if close == 0:
        return None
    return (hi - lo) / close


def compute_down_vol_ratio(df: pd.DataFrame, days: int) -> Optional[float]:
    """
    Share of quote volume that traded on down-close days over the last `days`
    completed candles (DIST v2's supply evidence). A down-close day is one
    whose close is below the previous day's close. Needs days+1 candles.
    """
    if len(df) < days + 1:
        return None
    window = df.iloc[-(days + 1):]
    closes = window["close"].to_numpy()
    vols = window["quote_volume"].to_numpy()[1:]
    down = closes[1:] < closes[:-1]
    total = vols.sum()
    if total <= 0:
        return None
    return float(vols[down].sum() / total)


def compute_rs_spark(rs_line: pd.Series, days: int) -> Optional[list[float]]:
    """Last `days` RS-line values normalised to the first point (shape only)."""
    window = rs_line.iloc[-days:]
    if window.empty:
        return None
    base = float(window.iloc[0])
    if base == 0:
        return None
    return [round(float(v) / base, 4) for v in window]


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def compute_structure(price: float, opens: dict[str, Optional[float]]) -> int:
    """Count how many of the four period opens the price is currently above (0–4)."""
    return sum(
        1 for key in ("week", "month", "quarter", "year")
        if opens.get(key) is not None and price > opens[key]
    )


# ---------------------------------------------------------------------------
# Distance from open (display only, not used in scoring)
# ---------------------------------------------------------------------------

def compute_pct_from_open(price: float, open_price: Optional[float]) -> Optional[float]:
    if open_price is None or open_price == 0:
        return None
    return (price / open_price - 1) * 100


# ---------------------------------------------------------------------------
# Full per-coin metric bundle
# ---------------------------------------------------------------------------

def compute_coin_metrics(
    symbol: str,
    coin_df: pd.DataFrame,
    btc_df: pd.DataFrame,
    config: dict,
    as_of: Optional[pd.Timestamp] = None,
) -> Optional[dict]:
    """
    Compute all signals for a single coin.
    Returns None (with a warning) if the coin doesn't have enough data.
    snapshot_date is taken from the last row of coin_df.

    as_of: optional cutoff for backtest replay — candles after as_of are
    ignored, so signals at a historical date D use data <= D only. The live
    run omits it ("now"). This is the single-code-path mechanism: replay and
    live runs flow through exactly the same logic below.
    """
    if as_of is not None:
        coin_df = coin_df.loc[:as_of]
        btc_df = btc_df.loc[:as_of]
        if coin_df.empty:
            return None

    # Intraday runs include today's live partial candle as the final row.
    # It may be used for current price / volume-so-far, but NEVER as a
    # completed candle in lookback aggregates (no look-ahead).
    today_utc = pd.Timestamp.now(tz="UTC").normalize()
    has_live = len(coin_df) > 0 and coin_df.index[-1] == today_utc
    hist = coin_df.iloc[:-1] if has_live else coin_df

    min_listing = config["universe"]["min_listing_days"]
    if len(hist) < min_listing:
        logger.warning("%s: only %d completed candles, need %d — skipping", symbol, len(hist), min_listing)
        return None

    snapshot_date = coin_df.index[-1]
    price = float(coin_df["close"].iloc[-1])
    sig = config["signals"]

    opens = get_period_opens(coin_df, snapshot_date)
    rs = compute_relative_strength(coin_df, btc_df, sig["returns_windows_days"])
    vol_z = compute_volume_zscore(
        coin_df, sig["volume_baseline_days"], sig["volume_z_clamp"]
    )
    structure = compute_structure(price, opens)

    # RS line and its leading signals
    rs_line = compute_rs_line(coin_df, btc_df)
    rs_sig = compute_rs_line_signals(
        rs_line,
        coin_df["close"],
        sig["rs_high_lookback_days"],
        sig["rs_persistence_ma_days"],
        sig["rs_persistence_cap"],
    )

    # Quiet-accumulation raw inputs (flags need the universe; set in scoring).
    # vol_trend averages whole completed days, so the partial candle's
    # incomplete volume must not count as a day — use hist.
    vol_trend = compute_vol_trend(
        hist, sig["vol_trend_fast_days"], sig["vol_trend_slow_days"]
    )
    range_pct_10d = compute_range_pct(coin_df, sig["quiet_range_days"])
    # Down-volume share is a completed-day volume aggregate — use hist
    down_vol_ratio = compute_down_vol_ratio(hist, sig["quiet_range_days"])
    rs_spark = compute_rs_spark(rs_line, sig["rs_spark_days"])

    # Raw alt returns for display (not BTC-adjusted)
    closes = coin_df["close"]
    ret_1d  = float(closes.iloc[-1] / closes.iloc[-2]  - 1) if len(closes) >= 2  else None
    ret_7d  = float(closes.iloc[-1] / closes.iloc[-8]  - 1) if len(closes) >= 8  else None
    ret_30d = float(closes.iloc[-1] / closes.iloc[-31] - 1) if len(closes) >= 31 else None

    return {
        "symbol": symbol,
        "date": snapshot_date.strftime("%Y-%m-%d"),
        "price": price,
        "pct_w": compute_pct_from_open(price, opens.get("week")),
        "pct_m": compute_pct_from_open(price, opens.get("month")),
        "pct_q": compute_pct_from_open(price, opens.get("quarter")),
        "pct_y": compute_pct_from_open(price, opens.get("year")),
        "ret_1d": ret_1d,
        "ret_7d": ret_7d,
        "ret_30d": ret_30d,
        "rs_1d": rs.get(1),
        "rs_7d": rs.get(7),
        "rs_30d": rs.get(30),
        "vol_z": vol_z,
        "structure": structure,
        "rs_new_high": rs_sig["rs_new_high"],
        "price_new_high": rs_sig["price_new_high"],
        "rs_divergence": rs_sig["rs_divergence"],
        "rs_persistence": rs_sig["rs_persistence"],
        "rs_new_low": rs_sig["rs_new_low"],
        "price_new_low": rs_sig["price_new_low"],
        "rs_breakdown": rs_sig["rs_breakdown"],
        "weak_persistence": rs_sig["weak_persistence"],
        "rs_below_ma": rs_sig["rs_below_ma"],
        "vol_trend": vol_trend,
        "range_pct_10d": range_pct_10d,
        "down_vol_ratio": down_vol_ratio,
        "rs_spark": rs_spark,
    }
