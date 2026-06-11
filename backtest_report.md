# Backtest Report — Alt Strength Scanner

## 1. Read this first (honesty block)
- Date range: **2023-11-22 to 2026-05-26** (917 evaluable dates, 404 candidate symbols).
- **Survivorship bias:** the universe is reconstructed per-date, but only from coins listed TODAY. Delisted and dead coins are absent, so results are flattered — real-time performance will be worse than shown here.
- This report describes the CURRENT config (C:\Users\hiten\Dropbox\1 - Claude_code\Crypto_Scanner\config.yaml); no parameters were tuned against these results.
- The backtest is a hypothesis generator; the LIVE validation table remains the verdict.

## 1b. Regime timeline
Of 917 evaluable dates: **ALT_LED 292** (alt share >= 55%), **NEUTRAL 103**, **BTC_LED 522** (alt share <= 45%).

## 2. Per-stage outcomes (long side; success = positive forward RS)
| Stage | Horizon | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|---|
| ACCUM | 3d | 3463 | 44% | -0.8% | +0.3% |
| ACCUM | 7d | 3463 | 41% | -2.0% | -0.4% |
| ACCUM | 14d | 3463 | 41% | -3.1% | -1.0% |
| IGNITE | 3d | 1265 | 38% | -2.9% | -2.6% |
| IGNITE | 7d | 1265 | 31% | -6.7% | -6.1% |
| IGNITE | 14d | 1265 | 27% | -10.3% | -9.4% |
| RUN | 3d | 9757 | 37% | -2.2% | -1.4% |
| RUN | 7d | 9757 | 34% | -4.0% | -2.9% |
| RUN | 14d | 9757 | 32% | -6.5% | -5.4% |
| EXT | 3d | 11921 | 38% | -2.7% | -2.2% |
| EXT | 7d | 11921 | 33% | -5.4% | -4.6% |
| EXT | 14d | 11921 | 30% | -9.5% | -8.3% |
| COOL | 3d | 16054 | 40% | -1.4% | -0.7% |
| COOL | 7d | 16054 | 38% | -2.5% | -1.2% |
| COOL | 14d | 16054 | 34% | -4.6% | -3.4% |
| - | 3d | 95090 | 41% | -1.2% | -0.6% |
| - | 7d | 95090 | 38% | -2.6% | -1.6% |
| - | 14d | 95090 | 35% | -4.6% | -3.6% |
| universe | 3d | 137550 | 41% | -1.3% | -0.8% |
| universe | 7d | 137550 | 37% | -2.8% | -1.9% |
| universe | 14d | 137550 | 34% | -5.0% | -4.0% |

## 3. Early-score decile spread (median 7d forward RS)
| Cohort | n | median 7d fwd RS |
|---|---|---|
| Early top decile | 13773 | -3.5% |
| Early bottom decile | 13769 | -3.8% |
| Universe | 137550 | -2.8% |

### 3b. Stability by calendar quarter (anti-overfitting check)
Early top-decile-vs-universe spread, 7d fwd RS, per quarter. A signal that only worked in one quarter is noise.
| Quarter | dates | top decile median | universe median | spread |
|---|---|---|---|---|
| 2023Q4 | 40 | -2.4% | -1.1% | -1.30% |
| 2024Q1 | 91 | -2.8% | -2.9% | +0.07% |
| 2024Q2 | 91 | -4.3% | -3.6% | -0.62% |
| 2024Q3 | 92 | -2.8% | -1.5% | -1.23% |
| 2024Q4 | 92 | -3.6% | -2.3% | -1.28% |
| 2025Q1 | 90 | -7.9% | -6.2% | -1.68% |
| 2025Q2 | 91 | -3.8% | -3.3% | -0.50% |
| 2025Q3 | 92 | -1.8% | -1.5% | -0.37% |
| 2025Q4 | 92 | -4.2% | -3.5% | -0.70% |
| 2026Q1 | 90 | -3.4% | -2.7% | -0.67% |
| 2026Q2 | 56 | -2.2% | -1.9% | -0.38% |

## 4. RS-divergence resolution
Flags: 1081
| Horizon | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|
| 7d | 1081 | 35% | -4.4% | -2.9% |
| 14d | 1081 | 33% | -6.3% | -4.9% |

## 5. ACCUM outcomes
Flags: 3504
| Horizon | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|
| 3d | 3504 | 44% | -0.8% | +0.2% |
| 7d | 3504 | 41% | -2.0% | -0.5% |
| 14d | 3504 | 40% | -3.2% | -1.1% |

ACCUM runs: 1248; median days in ACCUM: 2.0
Resolution destinations (stage after leaving ACCUM):
- -: 947
- RUN: 128
- COOL: 86
- IGNITE: 44
- left universe / end of data: 39
- EXT: 4

## 6. Short-side cohorts (success = NEGATIVE forward RS)
Computed for Part B review; UI remains OFF (shorts.enabled: false). DIST here is v2 (requires down-volume dominance + RS below its 10d MA).
| Stage | Horizon | n | % negative fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|---|
| DIST | 3d | 47 | 60% | -0.4% | +0.0% |
| DIST | 7d | 47 | 49% | +0.2% | +2.7% |
| DIST | 14d | 47 | 45% | +0.7% | +2.4% |
| BREAK | 3d | 437 | 53% | -0.4% | +0.7% |
| BREAK | 7d | 437 | 59% | -1.8% | -0.0% |
| BREAK | 14d | 437 | 52% | -1.1% | +2.4% |
| universe | 3d | 137550 | 59% | -1.3% | -0.8% |
| universe | 7d | 137550 | 63% | -2.8% | -1.9% |
| universe | 14d | 137550 | 66% | -5.0% | -4.0% |
| weak_top_decile | 3d | 13778 | 59% | -1.4% | -1.0% |
| weak_top_decile | 7d | 13778 | 64% | -3.2% | -2.4% |
| weak_top_decile | 14d | 13778 | 67% | -5.7% | -5.0% |

## 6b. Coil cohort (measured, NOT scored; hypothesized bullish continuation — success = POSITIVE forward RS)
Flags: 434. Joins no stage and no score in hypothesis v2; earns a place in v3 only if this evidence holds.
| Horizon | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|
| 3d | 434 | 44% | -1.0% | -0.7% |
| 7d | 434 | 39% | -3.0% | -2.1% |
| 14d | 434 | 38% | -3.8% | -0.7% |

## 7. Regime split
Alt-led days (>50% of universe beating BTC over 7d): 328; BTC-led days: 589.

### 7.1 Alt-led tape (328 dates)

**Per-stage outcomes (7d):**
| Stage | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|
| ACCUM | 1453 | 40% | -2.8% | -0.0% |
| IGNITE | 782 | 27% | -7.9% | -7.6% |
| RUN | 5456 | 32% | -4.7% | -4.0% |
| EXT | 4264 | 31% | -6.2% | -5.5% |
| COOL | 3179 | 32% | -3.8% | -2.5% |
| - | 34066 | 35% | -3.1% | -2.4% |
| universe | 49200 | 34% | -3.5% | -2.8% |

**Early decile spread (7d):** top -4.2% (n=4927) vs bottom -4.4% (n=4930) vs universe -3.5%.
**Divergence (7d):** n=470, 29% positive, median -5.6%.
**DIST (7d, short):** n=1 (insufficient sample), 100% negative, median -0.7%.
**BREAK (7d, short):** n=60, 43% negative, median +0.7%.
**weak_top_decile (7d, short):** n=4927, 66% negative, median -4.5%.

### 7.2 BTC-led tape (589 dates)

**Per-stage outcomes (7d):**
| Stage | n | % positive fwd RS | median fwd RS | median fwd USD |
|---|---|---|---|---|
| ACCUM | 2010 | 42% | -1.4% | -0.7% |
| IGNITE | 483 | 38% | -4.8% | -3.6% |
| RUN | 4301 | 37% | -3.2% | -1.7% |
| EXT | 7657 | 34% | -4.9% | -4.1% |
| COOL | 12875 | 40% | -2.2% | -1.0% |
| - | 61024 | 39% | -2.2% | -1.2% |
| universe | 88350 | 39% | -2.4% | -1.4% |

**Early decile spread (7d):** top -3.2% (n=8846) vs bottom -3.5% (n=8839) vs universe -2.4%.
**Divergence (7d):** n=611, 41% positive, median -3.0%.
**DIST (7d, short):** n=46, 48% negative, median +0.4%.
**BREAK (7d, short):** n=377, 62% negative, median -2.1%.
**weak_top_decile (7d, short):** n=8851, 62% negative, median -2.6%.
