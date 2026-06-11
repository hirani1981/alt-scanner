# Hypothesis Log — Alt Strength Scanner

This file records what each scoring hypothesis claims, what evidence it was
judged on, and the freeze rule that governs changes. The LIVE validation table
is the verdict; the backtest is a hypothesis generator only.

---

## v2 — "Early, demoted; ACCUM, promoted" (frozen 2026-06-11)

### The four changes from v1
1. **History extended to 1000 daily candles** (paginated fetch; disk cache
   head-merges missing ranges, never re-downloads). The replay now spans
   2023-11-22 → 2026-05-26 (917 evaluable dates: 522 BTC_LED / 103 NEUTRAL /
   292 ALT_LED) instead of ~10 months of mostly-BTC-led tape.
2. **DIST v2 requires evidence of supply.** The v1 definition (extended +
   quiet + volume building) described bullish consolidation and backtested as
   an anti-signal. DIST now additionally requires `down_vol_ratio >= 0.60`
   (down-day volume dominating the basing window) AND the RS line below its
   10d MA. The mirror flag **coil** (same footprint with buyers dominating,
   `down_vol_ratio <= 0.40`) is computed and reported but joins no score and
   no stage.
3. **One default display sort, every regime:** ACCUM flag desc → vol_trend
   (accumulation intensity) desc → Strength desc. Regime-conditional "lenses"
   were not built — ACCUM's edge holds in both regimes and IGNITE is worst in
   both, so a single ordering is correct and simpler. The regime header and
   digest regime line are context only.
4. **Early demoted.** Early is no longer in the default sort key (it is a
   stable anti-signal — see below). It remains a stored column. **Stored
   `rank`/`rank_change` and the validation cohorts remain defined on the Early
   score** so the live validation table stays continuous; display order and
   stored rank are decoupled.

### What the long-window backtest (v2) found
Survivorship caveat applies throughout: the universe is reconstructed per-date
but only from coins listed today, so results are flattered.

- **ACCUM is the one robust long edge.** Best long stage at every horizon in
  both regimes (7d: 41% positive vs 37% universe; BTC-led 42% vs 39%; alt-led
  40% vs 34%). This is what the default sort now leads with.
- **IGNITE is reliably the worst long stage** (27% positive at 14d), worst in
  *both* regimes. Dimmed in the UI everywhere; de-emphasised in the digest.
- **Early is a stable anti-signal.** Top-decile-vs-universe 7d-fwd-RS spread is
  negative in 10 of 11 calendar quarters (−0.4% to −1.7%; one quarter +0.07%).
  Consistent enough that it is **logged as a v3 candidate — a possible
  inverse/fade signal — but NOT acted on in v2.** It positively orders nothing.

### Demoted to measured-only (badge/tooltip stays, scored & sorted nowhere new)
- **RS-divergence.** Its v1 "relative-survivor" edge did not survive the long
  window: 35% positive at 7d vs 37% universe (median −4.4% vs −2.8%); the
  BTC-led edge shrank to +2pts with a worse median; alt-led was outright bad.
  Same status as coil: measured and shown, drives no new score or sort. (It
  remains a component of the demoted Early score and an IGNITE input — those
  are pre-existing frozen v2 definitions, not new uses.)
- **coil.** Hypothesised bullish-continuation pattern; only a modest hit-rate
  edge in the backtest. Measured and reported; earns a score in a future
  version only if the evidence strengthens.

### Short side (still `shorts.enabled: false`)
- **BREAK's v1 promise evaporated** on the larger sample: 59% negative at 7d
  vs 63% universe baseline at n=437 — i.e. it *underperformed* shorting at
  random. It is no longer the leading v3 short candidate; it keeps
  accumulating evidence in backtest cohorts and (once live) validation.
- **DIST v2** is appropriately rare (n=47) and shows no short edge yet;
  flagged coins drifted up over the forward windows.
- **weak_top_decile** modestly beats the short baseline but thinly.

### Freeze rule
No signal/weight/threshold changes for a minimum of **8 weeks of live EOD
data**, except bug fixes that change no semantics. Changes after that must cite
the LIVE validation table and become hypothesis **v3** with a new entry here.
The backtest may be re-run for information but is no longer grounds for tuning.

### v3 candidates (do not act until the freeze lifts AND live data supports)
- Early as an inverse/fade signal (stable negative spread across 11 quarters).
- coil as a scored long signal (if its hit-rate edge holds live).
- BREAK as a scored short signal (only if its sample grows and the edge returns).
