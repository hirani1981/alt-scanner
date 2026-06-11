# Backtest Report — Alt Strength Scanner

## 1. Read this first (honesty block)
- Date range: **2025-07-15 to 2026-05-26** (316 evaluable dates, 394 candidate symbols).
- **Survivorship bias:** the universe is reconstructed per-date, but only from coins listed TODAY. Delisted and dead coins are absent, so results are flattered — real-time performance will be worse than shown here.
- This report describes the CURRENT config (C:\Users\hiten\Dropbox\1 - Claude_code\Crypto_Scanner\config.yaml); no parameters were tuned against these results.
- The backtest is a hypothesis generator; the LIVE validation table remains the verdict.

## 2. Per-stage outcomes (long side; success = positive forward RS)
| Stage | Horizon | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|---|
| ACCUM | 3d | 1117 | 45% | -0.5% | -0.9% |
| ACCUM | 7d | 1117 | 36% | -2.5% | -3.6% |
| ACCUM | 14d | 1117 | 35% | -3.8% | -5.1% |
| IGNITE | 3d | 434 | 36% | -3.9% | -3.9% |
| IGNITE | 7d | 434 | 31% | -5.7% | -7.6% |
| IGNITE | 14d | 434 | 29% | -8.4% | -11.3% |
| RUN | 3d | 3730 | 36% | -2.1% | -2.0% |
| RUN | 7d | 3730 | 34% | -3.6% | -3.5% |
| RUN | 14d | 3730 | 31% | -6.5% | -7.8% |
| EXT | 3d | 4108 | 37% | -3.1% | -3.2% |
| EXT | 7d | 4108 | 32% | -5.8% | -6.4% |
| EXT | 14d | 4108 | 30% | -9.5% | -11.1% |
| COOL | 3d | 6283 | 40% | -1.3% | -1.2% |
| COOL | 7d | 6283 | 37% | -2.5% | -2.7% |
| COOL | 14d | 6283 | 35% | -3.7% | -4.7% |
| - | 3d | 31728 | 40% | -1.2% | -1.1% |
| - | 7d | 31728 | 36% | -2.5% | -2.5% |
| - | 14d | 31728 | 35% | -4.1% | -5.7% |
| universe | 3d | 47400 | 40% | -1.3% | -1.4% |
| universe | 7d | 47400 | 36% | -2.8% | -2.9% |
| universe | 14d | 47400 | 34% | -4.5% | -6.1% |

## 3. Early-score decile spread (median 7d forward RS)
| Cohort | n | median 7d fwd RS |
|---|---|---|
| Early top decile | 4748 | -3.4% |
| Early bottom decile | 4743 | -3.7% |
| Universe | 47400 | -2.8% |

## 4. RS-divergence resolution
Flags: 603
| Horizon | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|
| 7d | 603 | 41% | -2.7% | -2.6% |
| 14d | 603 | 39% | -4.3% | -4.8% |

## 5. ACCUM outcomes
Flags: 1136
| Horizon | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|
| 3d | 1136 | 45% | -0.6% | -1.0% |
| 7d | 1136 | 36% | -2.6% | -3.6% |
| 14d | 1136 | 35% | -3.8% | -5.2% |

ACCUM runs: 402; median days in ACCUM: 2.0
Resolution destinations (stage after leaving ACCUM):
- -: 263
- RUN: 68
- COOL: 40
- IGNITE: 18
- left universe / end of data: 13

## 6. Short-side cohorts (success = NEGATIVE forward RS)
Computed for Part B review; UI remains OFF (shorts.enabled: false).
| Stage | Horizon | n | % negative fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|---|
| DIST | 3d | 296 | 47% | +0.4% | -0.1% |
| DIST | 7d | 296 | 50% | +0.2% | -0.1% |
| DIST | 14d | 296 | 47% | +0.9% | +0.0% |
| BREAK | 3d | 56 | 61% | -0.8% | -0.5% |
| BREAK | 7d | 56 | 59% | -1.0% | -0.2% |
| BREAK | 14d | 56 | 70% | -3.8% | -1.1% |
| universe | 3d | 47400 | 60% | -1.3% | -1.4% |
| universe | 7d | 47400 | 64% | -2.8% | -2.9% |
| universe | 14d | 47400 | 66% | -4.5% | -6.1% |
| weak_top_decile | 3d | 4745 | 60% | -1.3% | -1.7% |
| weak_top_decile | 7d | 4745 | 65% | -3.4% | -3.6% |
| weak_top_decile | 14d | 4745 | 67% | -5.5% | -7.2% |

## 7. Regime split
Alt-led days (>50% of universe beating BTC over 7d): 106; BTC-led days: 210.

### 7.1 Alt-led tape (106 dates)

**Per-stage outcomes (7d):**
| Stage | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|
| ACCUM | 445 | 39% | -2.8% | -2.7% |
| IGNITE | 232 | 28% | -6.7% | -9.3% |
| RUN | 1749 | 29% | -4.4% | -5.2% |
| EXT | 1378 | 30% | -6.3% | -7.1% |
| COOL | 1229 | 35% | -3.1% | -3.5% |
| - | 10867 | 34% | -2.8% | -3.6% |
| universe | 15900 | 34% | -3.2% | -4.0% |

**Early decile spread (7d):** top -3.7% (n=1591) vs bottom -4.0% (n=1592) vs universe -3.2%.
**Divergence (7d):** n=209, 35% positive, median -3.7%.
**DIST (7d, short):** n=30, 57% negative, median -0.7%.
**BREAK (7d, short):** n=8 (insufficient sample), 25% negative, median +1.7%.
**weak_top_decile (7d, short):** n=1592, 66% negative, median -4.8%.

### 7.2 BTC-led tape (210 dates)

**Per-stage outcomes (7d):**
| Stage | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|
| ACCUM | 672 | 35% | -2.4% | -4.1% |
| IGNITE | 202 | 34% | -5.3% | -6.0% |
| RUN | 1981 | 39% | -2.6% | -2.1% |
| EXT | 2730 | 33% | -5.3% | -6.1% |
| COOL | 5054 | 38% | -2.4% | -2.3% |
| - | 20861 | 37% | -2.3% | -2.0% |
| universe | 31500 | 37% | -2.5% | -2.4% |

**Early decile spread (7d):** top -3.1% (n=3157) vs bottom -3.5% (n=3151) vs universe -2.5%.
**Divergence (7d):** n=394, 45% positive, median -1.7%.
**DIST (7d, short):** n=266, 49% negative, median +0.5%.
**BREAK (7d, short):** n=48, 65% negative, median -1.6%.
**weak_top_decile (7d, short):** n=3153, 64% negative, median -2.9%.
