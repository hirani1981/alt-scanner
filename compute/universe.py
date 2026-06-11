"""Universe construction — filter Binance USDT pairs down to the scored alt list."""
import logging

logger = logging.getLogger(__name__)


def get_candidate_pairs(config: dict) -> list[str]:
    """
    All USDT spot pairs passing the STATIC exclusion filters (stablecoins,
    wrapped, fiat, leveraged tokens, non-ASCII, benchmark). No volume floor
    or cap — this is the candidate pool. The live run narrows it by current
    24h volume (build_universe); the backtest narrows it per-date by trailing
    volume as of each replay date, using this same exclusion logic.
    """
    from data.binance import get_usdt_pairs

    uni = config["universe"]
    benchmark = config["benchmark"]

    exclude_contains = [s.upper() for s in uni.get("exclude_symbol_contains", [])]
    exclude_bases = {
        s.upper()
        for s in (
            list(uni.get("exclude_stablecoins", []))
            + list(uni.get("exclude_wrapped", []))
            + list(uni.get("exclude_fiat", []))
            + list(uni.get("exclude_commodity", []))
        )
    }

    pairs = get_usdt_pairs()
    out: list[str] = []
    for pair in pairs:
        symbol = pair["symbol"]
        base = pair["baseAsset"].upper()

        # Skip symbols with non-ASCII characters (e.g. Chinese-character tokens)
        if not symbol.isascii():
            continue
        if symbol == benchmark:
            continue
        if base in exclude_bases:
            continue
        if any(exc in symbol for exc in exclude_contains):
            continue
        out.append(symbol)
    return out


def build_universe(config: dict) -> list[str]:
    """
    Return the top max_universe USDT spot pairs by 24h quote volume, after
    applying exclude lists and the sanity volume floor.
    The benchmark symbol (BTCUSDT) is always excluded from the output.
    """
    from data.binance import get_24h_tickers

    uni = config["universe"]
    min_volume = uni["min_24h_quote_volume_usd"]
    max_size = uni["max_universe"]

    logger.info("Fetching exchange info and 24h tickers…")
    candidates = get_candidate_pairs(config)
    tickers = get_24h_tickers()

    scored: list[tuple[str, float]] = []
    for symbol in candidates:
        if symbol not in tickers:
            continue
        quote_vol = float(tickers[symbol].get("quoteVolume", 0))
        if quote_vol < min_volume:
            continue
        scored.append((symbol, quote_vol))

    scored.sort(key=lambda x: x[1], reverse=True)
    symbols = [s for s, _ in scored[:max_size]]
    logger.info("Universe: %d symbols after filters (cap=%d)", len(symbols), max_size)
    return symbols
