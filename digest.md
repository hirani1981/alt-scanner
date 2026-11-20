# Alt Strength Digest - 2026-11-20

**Regime [BTC_LED]:** BTC below trend, 36% of alts beating it - defensive; treat signals with suspicion.
_Default view sorts by ACCUM intensity, not Early or divergence (config v2). Regime is context only._
Breadth: 23/149 above W, 15 above M, 15 above Q, 15 above Y.  BTC -24.8% vs monthly open.

## New ACCUM flags (quiet accumulation, newly flagged)
  ENSOUSDT       vol_trend=1.72  10d range=30.5%  days flagged=1
  SAPIENUSDT     vol_trend=2.53  10d range=25.5%  days flagged=1

## New IGNITE / RS-divergence flags
  SPYBUSDT       IGNITE         RS_7d=+8.0%  vol_z=7.2
  HMSTRUSDT      IGNITE         RS_7d=+16.4%  vol_z=4.4
  KERNELUSDT     IGNITE         RS_7d=+23.2%  vol_z=10.0
  SENTUSDT       RS-divergence  RS_7d=+39.7%  vol_z=0.7
  GOOGLBUSDT     RS-divergence  RS_7d=+6.1%  vol_z=0.5
  WLFIUSDT       RS-divergence  RS_7d=+9.4%  vol_z=0.6
  XUSDUSDT       RS-divergence  RS_7d=+17.1%  vol_z=0.5
  TRXUSDT        RS-divergence  RS_7d=+13.0%  vol_z=-0.2
  AAPLBUSDT      RS-divergence  RS_7d=+13.0%  vol_z=0.1
  KITEUSDT       RS-divergence  RS_7d=+24.0%  vol_z=-0.2
  JSTUSDT        RS-divergence  RS_7d=+16.4%  vol_z=0.8
  MMTUSDT        RS-divergence  RS_7d=+157.4%  vol_z=1.2
  BFUSDUSDT      RS-divergence  RS_7d=+17.0%  vol_z=0.1
  DODOUSDT       RS-divergence  RS_7d=+33.2%  vol_z=0.1
  UUSDT          RS-divergence  RS_7d=+17.1%  vol_z=0.7
  ERAUSDT        RS-divergence  RS_7d=+18.0%  vol_z=-0.5

## New entrants to the Early top-20
  #1   SENTUSDT       early=0.712  stage=RUN
  #2   SPYBUSDT       early=0.695  stage=IGNITE
  #3   GOOGLBUSDT     early=0.679  stage=RUN
  #4   WLFIUSDT       early=0.673  stage=RUN
  #5   HMSTRUSDT      early=0.650  stage=IGNITE
  #7   TRXUSDT        early=0.611  stage=RUN
  #8   AAPLBUSDT      early=0.565  stage=RUN
  #9   ENSOUSDT       early=0.529  stage=ACCUM
  #10  KERNELUSDT     early=0.503  stage=IGNITE
  #11  SAPIENUSDT     early=0.488  stage=ACCUM
  #12  HUMAUSDT       early=0.435  stage=-
  #13  INTCBUSDT      early=0.394  stage=-
  #14  XAIUSDT        early=0.393  stage=RUN
  #15  TLMUSDT        early=0.390  stage=-
  #16  ZILUSDT        early=0.375  stage=-
  #17  ZKCUSDT        early=0.374  stage=-
  #18  KAVAUSDT       early=0.368  stage=-
  #19  YBUSDT         early=0.362  stage=RUN
  #20  SOXLBUSDT      early=0.357  stage=-

## Volume surge alerts (vol_z >= 3.0)
  KERNELUSDT     vol_z=10.0  rank=#10  stage=IGNITE
  SQQQBUSDT      vol_z=8.4  rank=#74  stage=EXT
  SPYBUSDT       vol_z=7.2  rank=#2  stage=IGNITE
  SAPIENUSDT     vol_z=6.0  rank=#11  stage=ACCUM
  HMSTRUSDT      vol_z=4.4  rank=#5  stage=IGNITE
  ENSOUSDT       vol_z=4.3  rank=#9  stage=ACCUM
  ORCLBUSDT      vol_z=3.6  rank=#145  stage=COOL
  SOXLBUSDT      vol_z=3.3  rank=#20  stage=-
  PROMUSDT       vol_z=3.1  rank=#115  stage=RUN

## Top 10 by Early score
#    Symbol         Stage    Early  Strgth  RS 24h   RS 7d  RS 30d  VolZ  VolTr
------------------------------------------------------------------------------------
1    SENTUSDT       RUN      0.712   0.766   +0.2%  +39.7%  +26.6%   0.7   3.15
2    SPYBUSDT       IGNITE   0.695   0.752   +2.7%   +8.0%  +29.5%   7.2   1.19
3    GOOGLBUSDT     RUN      0.679   0.605   +3.3%   +6.1%  +15.3%   0.5   0.88
4    WLFIUSDT       RUN      0.673   0.629   +0.7%   +9.4%  +12.2%   0.6   0.90
5    HMSTRUSDT      IGNITE   0.650   0.862   +8.7%  +16.4%  +38.2%   4.4   0.92
6    XUSDUSDT       RUN      0.611   0.824   +6.3%  +17.1%  +44.0%   0.5   0.70
7    TRXUSDT        RUN      0.611   0.547   +3.1%  +13.0%  +31.3%  -0.2   0.66
8    AAPLBUSDT      RUN      0.565   0.613   +3.7%  +13.0%  +43.8%   0.1   0.37
9    ENSOUSDT       ACCUM    0.529   0.742   +8.0%  +15.7%  -14.1%   4.3   1.72
10   KERNELUSDT     IGNITE   0.503   0.851  +20.9%  +23.2%  +39.8%  10.0   0.36

---
_config v2 (frozen 2026-06-11) — see HYPOTHESIS.md. Stored rank & validation cohorts remain Early-based._