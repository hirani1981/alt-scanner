# Alt Strength Digest - 2026-09-12

**Regime [ALT_LED]:** BTC mixed vs trend, 60% of alts beating it - neutral; be selective.
_Default view sorts by ACCUM intensity, not Early or divergence (config v2). Regime is context only._
Breadth: 42/136 above W, 93 above M, 103 above Q, 30 above Y.  BTC -1.5% vs monthly open.

## New ACCUM flags (quiet accumulation, newly flagged)
  HOLOUSDT       vol_trend=5.06  10d range=17.5%  days flagged=1
  RUNEUSDT       vol_trend=1.56  10d range=15.5%  days flagged=1
  ALGOUSDT       vol_trend=1.51  10d range=16.6%  days flagged=1
  NVDABUSDT      vol_trend=1.81  10d range=7.9%  days flagged=1
  SEIUSDT        vol_trend=1.69  10d range=18.3%  days flagged=1

## New IGNITE / RS-divergence flags
  ETHFIUSDT      IGNITE         RS_7d=+35.3%  vol_z=1.8
  MTLUSDT        IGNITE         RS_7d=+37.3%  vol_z=10.0
  PUNDIXUSDT     IGNITE         RS_7d=+12.1%  vol_z=8.1
  PENDLEUSDT     RS-divergence  RS_7d=+12.0%  vol_z=-0.5
  MUBARAKUSDT    RS-divergence  RS_7d=+1.1%  vol_z=-0.1

## New entrants to the Early top-20
  #1   PENDLEUSDT     early=0.667  stage=RUN
  #2   DOGSUSDT       early=0.591  stage=RUN
  #4   KAVAUSDT       early=0.569  stage=RUN
  #5   HOLOUSDT       early=0.538  stage=ACCUM
  #6   RUNEUSDT       early=0.534  stage=ACCUM
  #7   THETAUSDT      early=0.511  stage=-
  #8   ETHFIUSDT      early=0.506  stage=IGNITE
  #9   ALGOUSDT       early=0.504  stage=ACCUM
  #10  ETHUSDT        early=0.487  stage=-
  #12  SEIUSDT        early=0.456  stage=ACCUM
  #13  KATUSDT        early=0.448  stage=RUN
  #14  MTLUSDT        early=0.448  stage=IGNITE
  #15  SOMIUSDT       early=0.425  stage=RUN
  #16  NEWTUSDT       early=0.421  stage=-
  #18  CFGUSDT        early=0.413  stage=-
  #19  PUNDIXUSDT     early=0.407  stage=IGNITE
  #20  JSTUSDT        early=0.402  stage=-

## Volume surge alerts (vol_z >= 3.0)
  MTLUSDT        vol_z=10.0  rank=#14  stage=IGNITE
  REZUSDT        vol_z=10.0  rank=#21  stage=RUN
  LSKUSDT        vol_z=10.0  rank=#71  stage=EXT
  PUNDIXUSDT     vol_z=8.1  rank=#19  stage=IGNITE
  THEUSDT        vol_z=6.6  rank=#46  stage=-
  CHZUSDT        vol_z=3.5  rank=#49  stage=RUN

## Top 10 by Early score
#    Symbol         Stage    Early  Strgth  RS 24h   RS 7d  RS 30d  VolZ  VolTr
------------------------------------------------------------------------------------
1    PENDLEUSDT     RUN      0.667   0.797   +8.6%  +12.0%  +33.3%  -0.5   1.31
2    DOGSUSDT       RUN      0.591   0.803   +0.4%  +19.8%  +20.6%  -0.1   2.70
3    QQQBUSDT       ACCUM    0.571   0.186   -0.2%   +2.5%  -19.9%  -1.8   1.69
4    KAVAUSDT       RUN      0.569   0.887   +6.4%  +42.3%  +42.9%   0.5   1.98
5    HOLOUSDT       ACCUM    0.538   0.426   +1.7%   -2.0%  -27.2%  -0.1   5.06
6    RUNEUSDT       ACCUM    0.534   0.589   -0.8%   +8.2%   -1.6%  -0.6   1.56
7    THETAUSDT      -        0.511   0.792   +1.4%  +11.1%  +18.3%   0.5   2.23
8    ETHFIUSDT      IGNITE   0.506   0.947  +11.2%  +35.3%  +39.4%   1.8   1.66
9    ALGOUSDT       ACCUM    0.504   0.406   -0.1%   +2.1%   -2.5%  -1.0   1.51
10   ETHUSDT        -        0.487   0.521   +0.5%   +5.4%  +10.2%  -1.1   1.17

---
_config v2 (frozen 2026-06-11) — see HYPOTHESIS.md. Stored rank & validation cohorts remain Early-based._