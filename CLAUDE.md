# Alt Strength Scanner — working rules

## Stack
- Python 3.11+. Keep dependencies minimal: httpx (or requests), pandas, PyYAML, stdlib sqlite3.
- No paid APIs in Phase 1. Binance public endpoints only; no API key required.
- Market-data host: default https://data-api.binance.vision (api.binance.com returns HTTP 451 to cloud IPs e.g. GitHub Actions). Hosts are a fallback list; a 451 advances to the next. Override with the BINANCE_API_BASE env var (comma-separated). If every Binance host 451s from the runner, add a cross-exchange fallback (Bybit/OKX) — mind the differing symbol/quote-volume semantics.

## Data conventions
- All timestamps and period boundaries are UTC.
- Derive weekly/monthly/quarterly/yearly opens from daily candles (see brief §5). Weekly open = most recent Monday 00:00 UTC.
- Quote volume (USDT) is the volume measure, not base volume.

## Correctness
- NO LOOK-AHEAD: every signal for a given snapshot date uses only data up to that date. Never use a future or partial-today candle in a completed signal.
- The snapshot store is append-only. Never overwrite or delete historical rows.
- Cross-sectional percentile ranking is computed within a single day's universe.

## Robustness
- Fail-soft: one coin failing to fetch or compute must log a warning and continue; it must not abort the run.
- Respect Binance rate limits: batch requests, add backoff on HTTP 429.
- Provide a --dry-run mode (fetch + compute, no writes, no alerts).

## Config & secrets
- All thresholds, weights, windows come from config.yaml. No magic numbers in code.
- Secrets (e.g. Telegram token, chat id) come from environment variables / GitHub Actions secrets. Never commit them.

## Style
- Small, testable functions. A clear module boundary between data fetch, compute, store, and output.

## Phase 2 rules
- RS line = alt_close / btc_close, computed from klines history at run time; never from snapshots.
- Intraday runs may use the live partial candle for current price/volume only; completed-candle lookbacks must exclude it.
- The 00:30 UTC run is the canonical EOD snapshot (is_eod=1); ΔRank, digest diffs, and validation use EOD snapshots only.
- Rank/ΔRank are computed on the Early score from Phase 2 onward (Phase 1 ranks were strength-based; do not compare across).
- The validation table is append-only, like snapshots.

## Backtest rules (Phase 2.5)
- The backtest reuses the exact live compute path via the as_of cutoff. Never reimplement signal logic in replay code — a backtest of different code is a backtest of nothing.
- The backtest is a hypothesis generator; the LIVE validation table remains the verdict.
- No automated parameter optimisation against backtest results. Comparing a handful of candidate configs by hand (--config alt.yaml) is the ceiling — never a search loop.
- The survivorship caveat must appear in every report header: the universe is reconstructed per-date but only from coins listed today, so results are flattered.
- store/backtest.db is derived data and rebuilt each run; the live snapshot store stays append-only.

## Short side (Phase 2.5)
- Short signals are computed every run; UI/digest rendering is gated by shorts.enabled (gated rendering, not gated computation).
- Shorting is not symmetric with buying: uncapped losses, funding decay, squeeze risk. The flags locate weakness only.
- Funding/open-interest crowdedness data is deliberately deferred to Phase 3; until then BREAK flags on heavily-shorted coins can be squeeze bait.

## Hypothesis v2 (Phase 2.6)
- dist_flag (v2) requires supply evidence: down_vol_ratio >= threshold AND RS line below its 10d MA, in addition to the v1 conditions.
- coil_flag is computed and reported in backtest cohorts but joins no score and no stage in v2.
- Klines history is paginated (config-driven depth, not API-bound); the disk cache merges missing older/newer ranges and never re-downloads cached candles.
- Default DISPLAY sort is one ordering everywhere: ACCUM flag desc -> vol_trend desc -> Strength desc. Early is NOT in the sort key (backtest shows it is a stable anti-signal); it stays a column only. There is no regime-conditional sorting — the regime header/digest line are context only; all scores are computed identically in every regime.
- Stored rank/rank_change and validation cohorts remain defined on the Early score regardless of display sort (continuity of the live validation table). Display order and stored rank are decoupled.
- RS-divergence is measured-only in v2 (badge/tooltip only): its v1 edge did not survive the long backtest, so it drives no new score or sort. It still appears inside the (demoted) Early score and as an IGNITE input — those are frozen v2 definitions, not new uses.
- IGNITE is dimmed in the UI in all regimes (worst long stage in both backtests).
- CONFIG FREEZE (hypothesis v2, see HYPOTHESIS.md): no signal/weight/threshold changes for >= 8 weeks of live EOD data except semantics-free bug fixes; subsequent changes must cite the live validation table and increment the hypothesis version. The backtest may be re-run for information but is no longer grounds for tuning.
