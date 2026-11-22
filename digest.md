# Alt Strength Digest - 2026-11-22

**Regime [BTC_LED]:** BTC below trend, 39% of alts beating it - defensive; treat signals with suspicion.
_Default view sorts by ACCUM intensity, not Early or divergence (config v2). Regime is context only._
Breadth: 24/115 above W, 15 above M, 13 above Q, 15 above Y.  BTC -21.7% vs monthly open.

## New ACCUM flags (quiet accumulation, newly flagged)
  ORCAUSDT       vol_trend=2.03  10d range=24.2%  days flagged=1
  EWYBUSDT       vol_trend=1.61  10d range=20.6%  days flagged=1

## New IGNITE / RS-divergence flags
  LISTAUSDT      IGNITE         RS_7d=+13.7%  vol_z=10.0
  ERAUSDT        RS-divergence  RS_7d=+14.6%  vol_z=-0.8
  NIGHTUSDT      RS-divergence  RS_7d=+5.1%  vol_z=0.6

## New entrants to the Early top-20
  #1   LISTAUSDT      early=0.681  stage=IGNITE
  #3   ORCAUSDT       early=0.566  stage=ACCUM
  #4   HUMAUSDT       early=0.445  stage=-
  #5   ENSOUSDT       early=0.398  stage=RUN
  #6   EWYBUSDT       early=0.396  stage=ACCUM
  #7   SENTUSDT       early=0.377  stage=RUN
  #8   INTCBUSDT      early=0.375  stage=-
  #9   YBUSDT         early=0.373  stage=RUN
  #10  LUNCUSDT       early=0.371  stage=RUN
  #11  SOXLBUSDT      early=0.370  stage=-
  #12  KERNELUSDT     early=0.361  stage=RUN
  #13  RWUSDUSDT      early=0.356  stage=RUN
  #14  AIGENSYNUSDT   early=0.353  stage=RUN
  #15  SKYUSDT        early=0.351  stage=-
  #16  KAVAUSDT       early=0.348  stage=-
  #17  SOLUSDT        early=0.342  stage=-
  #18  KORUBUSDT      early=0.341  stage=-
  #19  COOKIEUSDT     early=0.337  stage=RUN
  #20  ETHUSDT        early=0.337  stage=-

## Volume surge alerts (vol_z >= 3.0)
  LISTAUSDT      vol_z=10.0  rank=#1  stage=IGNITE
  XVGUSDT        vol_z=10.0  rank=#26  stage=-
  ACEUSDT        vol_z=10.0  rank=#72  stage=-
  ALLOUSDT       vol_z=4.3  rank=#27  stage=-
  AIGENSYNUSDT   vol_z=3.8  rank=#14  stage=RUN
  COOKIEUSDT     vol_z=3.2  rank=#19  stage=RUN

## Top 10 by Early score
#    Symbol         Stage    Early  Strgth  RS 24h   RS 7d  RS 30d  VolZ  VolTr
------------------------------------------------------------------------------------
1    LISTAUSDT      IGNITE   0.681   0.831   +5.3%  +13.7%  +21.0%  10.0   1.21
2    ERAUSDT        RUN      0.568   0.699   +1.7%  +14.6%  +32.8%  -0.8   0.35
3    ORCAUSDT       ACCUM    0.566   0.629   -2.7%   +4.4%  -10.1%   2.4   2.03
4    HUMAUSDT       -        0.445   0.464   -2.2%  +41.9%  -56.0%  -0.8   1.54
5    ENSOUSDT       RUN      0.398   0.696   -3.7%  +31.5%   -4.3%   2.1   3.54
6    EWYBUSDT       ACCUM    0.396   0.576   +0.7%   -3.5%  +13.7%   0.0   1.61
7    SENTUSDT       RUN      0.377   0.724   -3.4%  +26.2%  +18.4%  -0.1   3.30
8    INTCBUSDT      -        0.375   0.448   +0.1%   -1.9%  -16.9%  -0.6   0.96
9    YBUSDT         RUN      0.373   0.690   -2.9%  +30.3%  +11.5%  -0.0   4.14
10   LUNCUSDT       RUN      0.371   0.661   -3.6%  +17.8%  +14.7%  -0.4   3.29

---
_config v2 (frozen 2026-06-11) — see HYPOTHESIS.md. Stored rank & validation cohorts remain Early-based._