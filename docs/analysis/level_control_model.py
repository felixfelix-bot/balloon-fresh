#!/usr/bin/env python3
"""
Level-control design model for the balloon ground station.
Reproduces EVERY numeric table in
  docs/analysis/ground-station-level-control-design.md
Run:  python3 docs/analysis/level_control_model.py

Sources for every constant are inline. Anything not sourced is marked TODO(unverified).
No external fetches; pure arithmetic so the doc is reproducible offline.
"""
import math

# ---------------------------------------------------------------- constants
# 433 MHz RX chain (ADR-079 / ADR-072)
F_MHZ_433 = 433.0
F_MHZ_24 = 2450.0
LNA_GAIN_DB = 20.0          # TQP3M9037 gain, qorvo.com/products/p/TQP3M9037 (via Wayback)
LNA_NF_DB = 0.4             # TQP3M9037 NF (same source)
# VGA noise figures, Analog Devices datasheets (analog.com/media/.../*.pdf, fetched 2026-10-08)
ADL5240_NF_450 = 2.8        # ADL5240 AMP noise figure @450 MHz, datasheet Table
ADL5330_NF_450 = 8.0        # ADL5330 NF @450 MHz, VGAIN=1.4 V, datasheet Table
# PSD / EIRP ceiling used by design/rf-shopping-list (EN 300 328 10 dBm/MHz)
PSD_DBM_PER_MHZ = 10.0
BW_2666_MHZ = 2.666
# 433 downlink sensitivities, LR2021 datasheet Table 3-13 (2.4 GHz FLRC rows used as the
# band-agnostic proxy -- the 433-specific row is TODO(unverified), see ADR-082 open item)
SENS = {2600: -99.0, 2080: -100.0, 1300: -101.5, 1040: -102.5, 650: -104.0, 520: -105.0}
F33_TX_433_DBM = 33.0       # ADR-075 high-power flight variant
G_BALLOON_433_DBI = 2.0     # TODO(unverified) stub/half-wave balloon 433 antenna
G_GROUND_433_DBI = 14.8     # Diamond A-430S15R, funktechnik-bielefeld.de (CONFIRMED)
G_GROUND_24_DBI = 11.1      # Sirio SLP-17, funktechnik-bielefeld.de (CONFIRMED)
G_BALLOON_24_DBI = 0.0      # TODO(unverified) bare 2.4 GHz stub
LR2021_HF_PA_DBM = 12.0     # 2.4 GHz HF PA (docs/2G4-LINK-BUDGET-ANALYSIS.md §1)
# demodulator usable window at the top rate: sensitivity -> onset of compression.
# An ASSUMPTION (the LR2021 max-input figure is TODO(unverified)); 35 dB is the
# conservative end of the 30-40 dB class quoted for GMSK/FLRC-class demodulators.
W_TOP_DB = 35.0
FADE_DB = 15.0              # slow fade/pointing allowance (design choice, labelled)


def fspl(f_mhz, d_km):
    return 20 * math.log10(d_km) + 20 * math.log10(f_mhz) + 32.44


def prx_433(d_km):
    """Received power at the ground 433 antenna port, dBm."""
    return F33_TX_433_DBM + G_BALLOON_433_DBI + G_GROUND_433_DBI - fspl(F_MHZ_433, d_km)


def prx_24_at_balloon(d_km, p_tx_dbm):
    """Received power at the balloon 2.4 GHz receiver, dBm."""
    return p_tx_dbm + G_GROUND_24_DBI + G_BALLOON_24_DBI - fspl(F_MHZ_24, d_km)


def nf_cascade(nfs_db, gains_db):
    """Friis noise figure (dB) of a cascade."""
    f = 10 ** (nfs_db[0] / 10.0)
    g = 10 ** (gains_db[0] / 10.0)
    for i in range(1, len(nfs_db)):
        f = f + (10 ** (nfs_db[i] / 10.0) - 1.0) / g
        g = g * 10 ** (gains_db[i] / 10.0)
    return 10 * math.log10(f)


def hr(t):
    print("\n" + "=" * 74 + "\n" + t + "\n" + "=" * 74)


hr("1. FRIIS: WHY THE VGA GOES *SECOND* (after the LNA)")
for label, vga_nf in (("ADL5240 (amp NF 2.8 dB @450 MHz)", ADL5240_NF_450),
                      ("ADL5330 (NF 8.0 dB @450 MHz)", ADL5330_NF_450)):
    after = nf_cascade([LNA_NF_DB, vga_nf], [LNA_GAIN_DB, 0.0])
    # VGA first, set to unity gain (no attenuation), then LNA
    before = nf_cascade([vga_nf, LNA_NF_DB], [0.0, LNA_GAIN_DB])
    print(f"VGA = {label}")
    print(f"  LNA -> VGA : system NF = {after:.3f} dB   (VGA adds {after - LNA_NF_DB:+.3f} dB)")
    print(f"  VGA -> LNA : system NF = {before:.3f} dB   (VGA adds {before - LNA_NF_DB:+.3f} dB)")
print("\n(Friis: F = F1 + (F2-1)/G1 ; the VGA's excess noise is divided by the LNA's 20 dB gain)")

hr("2. 433 MHz RECEIVED LEVEL vs RANGE (F33 +33 dBm balloon TX, 14.8 dBi ground)")
print(f"{'range km':>10} {'FSPL dB':>9} {'P_rx dBm':>10}  {'vs 650 km':>10}")
for d in (0.01, 0.05, 0.1, 1, 10, 100, 650):
    print(f"{d:>10.3g} {fspl(F_MHZ_433, d):>9.1f} {prx_433(d):>10.1f}  {prx_433(d) - prx_433(650):>+10.1f}")
var = fspl(F_MHZ_433, 650) - fspl(F_MHZ_433, 1)
print(f"\n1 km -> 650 km path-loss swing = {var:.2f} dB  (the brief's ~56 dB)")
print(f"+ {FADE_DB:.0f} dB fade allowance = mission span {var + FADE_DB:.2f} dB")

hr("3. DYNAMIC-RANGE BUDGET: WHAT A FIXED GAIN CAN AND CANNOT DO")
mission = var + FADE_DB
for name, R in (("no level control (fixed gain)", 0.0),
                ("DSA 0-31.75 dB (ADL5240 / PE43711)", 31.5),
                ("VGA -35..+22 dB (ADL5330, 57 dB)", 57.0)):
    span = W_TOP_DB + R
    dist_ratio = 10 ** (span / 20.0)
    frac_db = min(1.0, span / mission)
    print(f"{name:38s} acceptance span {span:5.1f} dB  "
          f"= {dist_ratio:8.1f}x in distance  ({frac_db*100:5.1f}% of mission dB-span)")
print(f"\nAssumed demod usable window at the TOP rate W_top = {W_TOP_DB:.0f} dB "
      f"({SENS[2600]:.0f} dBm .. {SENS[2600] + W_TOP_DB:.0f} dBm)  [TODO(unverified) input range]")

hr("4. WHAT THE TOP RATE (2.6 Mbps) COSTS / BUYS")
for k, s in SENS.items():
    print(f"  {k:>5} kbps  sens {s:>7.1f} dBm   rate ratio vs 650 kbps = {k/650:.2f}x")
print("\nThe top rate has the WORST sensitivity -> it is the FIRST casualty of a mis-set level.")

hr("5. TRANSMIT LEVEL: RANGE -> ATTENUATION LUT (constant level at the balloon RX)")
P_TARGET = -40.0   # balloon RX level to hold: max linear input minus margin. TODO(unverified)
print(f"Target level at the balloon 2.4 GHz receiver: {P_TARGET:.0f} dBm")
for p_tx in (LR2021_HF_PA_DBM, 30.0, 33.0):
    print(f"\n Ground TX available at antenna port = {p_tx:.0f} dBm "
          f"({'LR2021 HF PA' if p_tx == LR2021_HF_PA_DBM else 'with a PA'})")
    print(f"  {'range km':>10} {'P_rx@balloon dBm':>18} {'DSA atten dB':>13}")
    for d in (0.01, 0.05, 0.1, 0.5, 1, 5, 50, 650):
        lvl = prx_24_at_balloon(d, p_tx)
        att = max(0.0, min(31.75, lvl - P_TARGET))
        print(f"  {d:>10.3g} {lvl:>18.1f} {att:>13.2f}")

hr("6. ISM EIRP CEILING (context; the operator set compliance aside for this task)")
ceiling = min(20.0, PSD_DBM_PER_MHZ + 10 * math.log10(BW_2666_MHZ))
print(f"EN 300 328 PSD ceiling @ {BW_2666_MHZ} MHz = {ceiling:.2f} dBm EIRP")
print(f"  -> conducted at an {G_GROUND_24_DBI:.1f} dBi antenna = {ceiling - G_GROUND_24_DBI:+.1f} dBm")
print(f"  -> LR2021 HF PA ({LR2021_HF_PA_DBM:.0f} dBm) must be turned DOWN "
      f"{LR2021_HF_PA_DBM - (ceiling - G_GROUND_24_DBI):.1f} dB")

hr("7. LOOP DYNAMICS: AGC TIME CONSTANT vs FRAME / FADE / GEOMETRY")
# frame air-times from docs/FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md (511 B, fw CR 3/4)
air = {2600: 2.140, 1300: 1.07, 650: 2.14, 260: 5.35}
GAPS_MS = (0.5, 5.0, 40.0)
for gap in GAPS_MS:
    f = 1000.0 / (2.140 + gap)
    print(f"  FLRC-2600, 511 B (2.140 ms air) + {gap:>4.1f} ms GAP -> {f:6.1f} frames/s "
          f"(frame period {1000/f:.2f} ms)")
print("\n  Fastest physical fade (multipath, 2v/lambda, v=25 m/s @433 MHz) = "
      f"{2*25/0.692:.0f} Hz  [lambda = {0.692:.3f} m]")
print("  Slow geometry / range-change rate                                ~ 0.01-1 Hz")
print("  -> correct AGC bandwidth: BELOW the fade rate (do not chase fading),")
print("     ABOVE the geometry rate (must track the slow path-loss change)")

hr("8. CONSULT-READY SUMMARY")
print(f"LNA->VGA system NF (ADL5240 VGA)  = {nf_cascade([LNA_NF_DB, ADL5240_NF_450], [LNA_GAIN_DB, 0.0]):.3f} dB")
print(f"VGA->LNA system NF (ADL5240 VGA)  = {nf_cascade([ADL5240_NF_450, LNA_NF_DB], [0.0, LNA_GAIN_DB]):.3f} dB")
print(f"435 MHz mission span              = {mission:.1f} dB")
print(f"Fixed-gain acceptance             = {W_TOP_DB:.0f} dB  ({W_TOP_DB/mission*100:.0f}% of mission)")
print(f"With 31.5 dB DSA                  = {W_TOP_DB+31.5:.1f} dB ({min(100,(W_TOP_DB+31.5)/mission*100):.0f}%)")
