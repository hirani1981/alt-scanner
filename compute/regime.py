"""Market regime header — is today worth hunting alts at all?"""
import logging

import pandas as pd

from compute.metrics import get_period_opens

logger = logging.getLogger(__name__)


def compute_regime(btc_df: pd.DataFrame, ranked: pd.DataFrame, config: dict) -> dict:
    """
    Returns a dict for the dashboard header and the digest opening line:
    BTC trend vs its SMAs, % from monthly open, breadth counts, alt share,
    and a plain-English summary line.
    """
    rcfg = config["regime"]
    closes = btc_df["close"]
    btc_now = float(closes.iloc[-1])

    sma_fast = float(closes.rolling(rcfg["btc_sma_fast_days"]).mean().iloc[-1])
    sma_slow = float(closes.rolling(rcfg["btc_sma_slow_days"]).mean().iloc[-1])

    if btc_now > sma_fast and btc_now > sma_slow:
        btc_trend = "above both"
    elif btc_now < sma_fast and btc_now < sma_slow:
        btc_trend = "below both"
    else:
        btc_trend = "mixed"

    month_open = get_period_opens(btc_df, btc_df.index[-1]).get("month")
    btc_pct_m = (btc_now / month_open - 1) * 100 if month_open else None

    n = len(ranked)
    breadth = {
        "week": int((pd.to_numeric(ranked["pct_w"], errors="coerce") > 0).sum()),
        "month": int((pd.to_numeric(ranked["pct_m"], errors="coerce") > 0).sum()),
        "quarter": int((pd.to_numeric(ranked["pct_q"], errors="coerce") > 0).sum()),
        "year": int((pd.to_numeric(ranked["pct_y"], errors="coerce") > 0).sum()),
    }

    rs7 = pd.to_numeric(ranked["rs_7d"], errors="coerce")
    alt_share = float((rs7 > 0).sum()) / n * 100 if n else 0.0

    # Operational regime label (context only — does NOT change scores or the
    # default sort; v2 uses one ordering everywhere).
    if alt_share >= rcfg["alt_led_min"]:
        regime_class = "ALT_LED"
    elif alt_share <= rcfg["btc_led_max"]:
        regime_class = "BTC_LED"
    else:
        regime_class = "NEUTRAL"

    high, low = rcfg["alt_share_high"], rcfg["alt_share_low"]
    share_txt = f"{alt_share:.0f}% of alts beating it"
    if btc_trend == "above both" and alt_share >= high:
        line = f"BTC trending, {share_txt} - risk-on for alts."
    elif btc_trend == "above both" and alt_share <= low:
        line = f"BTC trending but only {share_txt} - BTC-led market; alts lagging."
    elif btc_trend == "below both" and alt_share >= high:
        line = f"BTC below trend yet {share_txt} - alt rotation under a weak BTC; watch closely."
    elif btc_trend == "below both" and alt_share <= low:
        line = f"BTC below trend, {share_txt} - defensive; treat signals with suspicion."
    else:
        line = f"BTC {btc_trend} vs trend, {share_txt} - neutral; be selective."

    return {
        "btc_trend": btc_trend,
        "btc_price": btc_now,
        "btc_pct_month": btc_pct_m,
        "breadth": breadth,
        "universe_size": n,
        "alt_share_rs7": alt_share,
        "regime_class": regime_class,
        "line": line,
    }
