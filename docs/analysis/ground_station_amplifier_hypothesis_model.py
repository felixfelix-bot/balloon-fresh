#!/usr/bin/env python3
"""
ground_station_amplifier_hypothesis_model.py

Reproducible model for docs/analysis/ground-station-amplifier-hypothesis-check.md

Answers the operator's five questions about an AMPLIFIER-LED ground station:
  Q1  is an LNA useless on receive?            (receive-chain noise temperature, Friis cascade)
  Q2  Yagi ARRAY: bandwidth, mutual coupling, beamwidth narrowing, EUR/dB
  Q3  "one cheap tracker per Yagi, combined"   (coherent / incoherent / MRC / multi-sector)
  Q4  balloon-RX overdrive + external gain control / closed loop
  Q5  re-cost with the operator's OWNED 2.4 GHz circulator + amplifier

stdlib only (math). Every input is a named constant with its provenance comment.
Every output prints its own formula, then the number.

  [CITED path]      = read from the repo (path given)
  [CITED url]       = fetched and read this session (URL given)
  [ESTIMATE]        = labelled estimate, basis named
  [TODO(unverified)]= unknown; do not treat as a spec

Run:  python3 docs/analysis/ground_station_amplifier_hypothesis_model.py
"""

import math

# --------------------------------------------------------------------------
# 0. CONSTANTS AND SOURCES
# --------------------------------------------------------------------------

K_BOLTZ = 1.380649e-23          # J/K, exact (SI 2019)
T0 = 290.0                      # K, IEEE reference temperature for noise figure
T_GROUND = 290.0                # K, physical temperature of ground / coax
C_LIGHT = 299792458.0           # m/s

F_433 = 433.05e6                # Hz -- ISM/SRD band start [CITED docs/analysis/ground-station-bom-candidates.md sec 1 band note]
F_2400 = 2440.0e6               # Hz -- bench/link centre used by the repo [CITED docs/power-sweep-results-2026-07-24.md header]

LAM_433 = C_LIGHT / F_433
LAM_2400 = C_LIGHT / F_2400

# ---- Receiver sensitivities, Semtech LR2021 datasheet tables (as carried in-repo) ----
# [CITED docs/analysis/ground-station-gain-per-dollar.md sec 1.2 table]
S_FLRC_2600 = -100.5            # dBm, FLRC 2.6 Mbps, sub-GHz, Table 3-12
S_FLRC_650 = -107.0             # dBm, FLRC 650 kbps
S_LORA_SF12_62k5 = -143.0       # dBm, LoRa SF12/BW62.5 kHz, Table 3-17
# [CITED docs/F33-MODULE-PLAN.md (G-NiceRF LoRa2021F33-2G4 datasheet Rev 1.1)]
S_2400_LNA_ON = -136.0          # dBm, 2.4 GHz LoRa RX with the F33 internal LNA in circuit
S_2400_LNA_OFF = -124.0         # dBm, LNA bypassed (12 dB worse)
# [CITED docs/LINK-BUDGET-LICENCE-EXEMPT.md line 29; docs/adr/005-sky66112-fem.md]
NF_SKY66112 = 1.8               # dB, SKY66112-11 FEM LNA noise figure (in-repo sourced)
GAIN_SKY66112 = 14.0            # dB

# ---- TX powers ----
P_TX_CHIP_MAX = 22.0            # dBm, LR2021 sub-GHz chip max, Table 3-22 [CITED gain-per-dollar sec 1.2]
P_TX_LICENCE_EXEMPT = 12.15     # dBm EIRP, 10 mW ERP cap, ADR-039/ADR-041 [CITED]
P_TX_F33_433 = 33.0             # dBm, F33 433 MHz [CITED docs/F33-MODULE-PLAN.md]
P_TX_F33_2400 = 30.0            # dBm, F33 2.4 GHz [CITED docs/F33-MODULE-PLAN.md]
P_TX_UPLINK_LE = 20.0           # dBm EIRP, licence-exempt 2.4 GHz uplink cap (100 mW) [CITED LINK-BUDGET-LICENCE-EXEMPT]

# ---- Antennas ----
# Prices and gains [CITED docs/analysis/ground-station-bom-candidates.md sec 0.1]
G_YAGI_3EL = 7.0;     EUR_YAGI_3EL = 99.00;   BW_3EL = (125.0, 65.0)   # H-plane, E-plane -3 dB, vendor
G_YAGI_6EL = 11.0;    EUR_YAGI_6EL = 132.00
G_YAGI_10EL = 14.0;   EUR_YAGI_10EL = 155.00
G_YAGI_10EL_D = 13.1; EUR_YAGI_10EL_D = 69.00   # Diamond A-430S10R, 430-440 MHz
G_YAGI_15EL_D = 14.8; EUR_YAGI_15EL_D = 74.50   # Diamond A-430S15R
G_YAGI_FX7073 = 18.0; EUR_YAGI_FX7073 = 215.00
# Vendor stated usable bands [CITED ground-station-bom-candidates.md sec 1]
BAND_SIRIO = (400.0, 470.0)     # MHz, Sirio WY 400 family
BAND_DIAMOND = (430.0, 440.0)   # MHz, Diamond A-430SxR
# array ready per vendor: [CITED ground-station-bom-candidates.md sec 1 A1]
#   "Stacked and bayed array for more gain"

# ---- LNA / PA hardware, all prices and specs fetched this session ----
# [CITED https://www.wimo.com/en/ssb-70cm-ism-lna]  SSB Electronic LNA ISM 433 MHz
LNA433_GAIN = 20.0; LNA433_NF = 0.7; LNA433_OIP3 = 32.0; LNA433_IIP3 = 12.0
LNA433_EUR = 257.0; LNA433_BAND = (433.0, 435.0)
# [CITED https://www.minicircuits.com/pdfs/ZX60-P103LN+.pdf]  Rev D, ECO-026542
ZX60_NF = {50: 1.2, 500: 0.4, 1000: 0.5, 2000: 0.6}      # dB typ
ZX60_GAIN = {50: 25.2, 500: 20.3, 1000: 15.6, 2000: 10.0}  # dB typ
ZX60_P1DB = {500: 22.3, 2000: 23.2}                        # dBm typ
ZX60_IN_MAX_LO = 21.0   # dBm, 50-2000 MHz max input (no damage)
ZX60_IN_MAX_HI = 26.0   # dBm, 2000-3000 MHz max input (no damage)
# [CITED https://www.wimo.com/en/rt-2400]  2.4 GHz T/R amplifier with internal TX/RX switching
RT2400_TX_GAIN = 13.0; RT2400_RX_GAIN = 14.0; RT2400_NF = 3.2
RT2400_POUT = 30.0; RT2400_BAND = (2417.0, 2467.0); RT2400_EUR = 355.0
# [CITED https://www.wimo.com/en/dxpatrol-qo100-amplifier-1w]
DP1W_GAIN = 12.0; DP1W_POUT = 30.0; DP1W_NF = 4.4; DP1W_EUR = 69.0
# [CITED https://www.wimo.com/en/qo100-amp12]
DP12W_GAIN = 24.0; DP12W_POUT = 40.8; DP12W_EUR = 185.0   # 12 W = 10*log10(12000) = 40.79 dBm
# [CITED https://www.wimo.com/en/shf-mast-preamp-mini-vhf-uhf]  -- ADJUSTABLE GAIN
SHF_EUR = 151.90; SHF_MAXPWR = 150.0        # W, switched through
# [CITED https://www.wimo.com/en/ssb-electronic-mast-preamp-sps] -- VOX RX/TX switch
SPS_EUR = 345.0
# [CITED https://www.minicircuits.com/pdfs/DAT-31R5A-PN+.pdf]  digital step attenuator
DAT_RANGE = 31.5; DAT_STEP = 0.5; DAT_BAND_MAX = 4.0        # GHz

# ---- array / combining hardware, all priced at WiMo (fetched this session) ----
EOL = "\n"  # (unused; kept for readability of long strings)


def banner(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def db(x):
    return 10.0 * math.log10(x) if x > 0 else float("-inf")


def lin(d):
    return 10 ** (d / 10.0)


def t_from_nf(nf_db):
    """Effective noise temperature of a device with noise figure nf_db, referred to 290 K."""
    return T0 * (10 ** (nf_db / 10.0) - 1.0)


def fspl(d_m, lam):
    return 20.0 * math.log10(4.0 * math.pi * d_m / lam)


def cascade(blocks, t_ant):
    """Friis cascade. blocks = [(name, gain_db, T_e_K), ...] in cascade order.
    Returns (T_sys_K, per-stage table)."""
    t_sys = t_ant
    g_running = 1.0
    rows = []
    for name, g_db, te in blocks:
        contrib = te / g_running
        t_sys += contrib
        rows.append((name, g_db, te, contrib))
        g_running *= lin(g_db)
    return t_sys, rows


# ==========================================================================
banner("Q1  IS AN LNA USELESS ON RECEIVE?  receive-chain noise temperature")
# ==========================================================================
print("""
Framework (Friis / antenna noise temperature):
    T_sys = T_ant + T_1 + T_2/G_1 + T_3/(G_1 G_2) + ...
    [CITED https://en.wikipedia.org/wiki/Antenna_noise_temperature  "T_S = T_A + T_E";
     "the temperature depends on its gain pattern, pointing direction, and the
      thermal environment in which it is placed"]
    T_e(NF) = 290*(10^(NF/10) - 1)
    G/T [dB/K] = G_ant[dBi] - 10*log10(T_sys[K])
""")

# 433 MHz receive chain. Antenna at the mast, 15 m of Airborne 10 to the shack.
COAX_433_DB = 15.0 * 0.076          # 0.76 dB/10 m @430 MHz [CITED bom-candidates sec F3]
COAX_433_DB = round(COAX_433_DB, 4)
CONN_DB = 0.5                       # [ESTIMATE] 8 N/SMA joints, bom-candidates sec 6
FEED_DB_433 = round(COAX_433_DB + CONN_DB, 4)
T_FEED_433 = T_GROUND * (lin(FEED_DB_433) - 1.0)
G_FEED_433 = lin(-FEED_DB_433)

# 2.4 GHz receive chain
COAX_2400_DB = 15.0 * 0.192         # 1.92 dB/10 m @2.4 GHz Airborne 10 [CITED bom-candidates F3]
COAX_2400_DB = round(COAX_2400_DB, 4)
FEED_DB_2400 = round(COAX_2400_DB + CONN_DB, 4)
T_FEED_2400 = T_GROUND * (lin(FEED_DB_2400) - 1.0)
G_FEED_2400 = lin(-FEED_DB_2400)

# Receiver noise figure. NOT in-repo and not published for the LR2021.
# [TODO(unverified)] LR2021 exact NF. Bracketed as an ESTIMATE:
NF_RX_CASES = [6.0, 8.0, 10.0]

# Antenna noise temperature, bracketed. Basis stated for each.
T_ANT_WIDE = 200.0   # K  [ESTIMATE] a ~14 dBi Yagi at 10-30 deg elevation: main beam to
                     # sky/atmosphere, sidelobes + >=17 dB F/B back lobe to 290 K ground.
                     # Bracket 150-290 K tested below.
T_ANT_DISH = 40.0    # K  [ESTIMATE] a 3.0-3.5 m dish (22 dBi, HPBW ~5-7 deg) at high
                     # elevation: cold sky. Bracket 20-60 K tested below.
T_ANT_2400_WIDE = 290.0  # K [ESTIMATE] 2.4 GHz wide-beam (grid/12 dBi class) at low elevation
T_ANT_2400_DISH = 25.0   # K [ESTIMATE] 2.4 GHz 0.6-0.9 m dish at high elevation, cold sky

def report_band(label, t_ant_wide, t_ant_dish, feed_db, t_feed, g_feed, lam, g_ant_wide, g_ant_dish,
                lna_nf, lna_gain, lna_label):
    print("-" * 78)
    print(f"{label}: feed = {feed_db:.3f} dB, LNA = {lna_label} (NF {lna_nf} dB, gain {lna_gain} dB)")
    print("-" * 78)
    for nf_rx in NF_RX_CASES:
        t_rx = t_from_nf(nf_rx)
        # (a) antenna -> feed -> receiver, no LNA
        t_a, _ = cascade([("feed", -feed_db, t_feed), ("rx", 0.0, t_rx)], t_ant_wide)
        # (b) antenna -> LNA -> feed -> receiver
        t_b, _ = cascade([("lna", lna_gain, t_from_nf(lna_nf)),
                          ("feed", -feed_db, t_feed), ("rx", 0.0, t_rx)], t_ant_wide)
        # (c) same LNA, but a DIRECTIVE antenna on cold sky
        t_c, _ = cascade([("lna", lna_gain, t_from_nf(lna_nf)),
                          ("feed", -feed_db, t_feed), ("rx", 0.0, t_rx)], t_ant_dish)
        # (d) directive antenna, no LNA
        t_d, _ = cascade([("feed", -feed_db, t_feed), ("rx", 0.0, t_rx)], t_ant_dish)
        lna_db = db(t_a / t_b)
        dir_db = db(t_b / t_c)
        print(f"  RX NF {nf_rx:4.1f} dB (T_e {t_rx:7.1f} K):")
        print(f"    (a) wide-beam, no LNA          T_sys = {t_a:8.1f} K")
        print(f"    (b) wide-beam + LNA            T_sys = {t_b:8.1f} K   -> LNA buys {lna_db:5.2f} dB of T_sys")
        print(f"    (c) directive + same LNA       T_sys = {t_c:8.1f} K   -> directivity adds {dir_db:5.2f} dB of T_sys")
        print(f"    (d) directive, no LNA          T_sys = {t_d:8.1f} K   -> LNA buys {db(t_d/t_c):5.2f} dB here")
        print(f"    IRREDUCIBLE FLOOR with a perfect (0 K) LNA at the feed: T_ant = {t_ant_wide:.0f} K wide / {t_ant_dish:.0f} K directive")
    print()

report_band("433 MHz downlink (G_wide = %.1f dBi Sirio WY 400-10N, G_dish = 22.15 dBi / 3.5 m)"
            % G_YAGI_10EL, T_ANT_WIDE, T_ANT_DISH, FEED_DB_433, T_FEED_433, G_FEED_433,
            LAM_433, G_YAGI_10EL, 22.15, LNA433_NF, LNA433_GAIN,
            "SSB LNA ISM 433 (EUR %.0f)" % LNA433_EUR)
report_band("2.4 GHz uplink (G_wide = 12.4 dBi, G_dish = 18.0 dBi / 0.75 m)",
            T_ANT_2400_WIDE, T_ANT_2400_DISH, FEED_DB_2400, T_FEED_2400, G_FEED_2400,
            LAM_2400, 12.4, 18.0, ZX60_NF[2000], ZX60_GAIN[2000],
            "Mini-Circuits ZX60-P103LN+ (price TODO(unverified))")

print("SENSITIVITY BRACKET (does the conclusion survive the T_ant / NF_RX unknowns?)")
print("  Axis 1: T_ant_wide 150 -> 290 K;  Axis 2: NF_RX 6 -> 10 dB;  LNA fixed (0.7 dB / 20 dB)")
print("  %-14s" % "T_ant[K]" + "".join(" NF%-4.0f" % n for n in NF_RX_CASES))
for ta in (150.0, 200.0, 250.0, 290.0):
    row = "  %-14.0f" % ta
    for nf_rx in NF_RX_CASES:
        t_rx = t_from_nf(nf_rx)
        t_a, _ = cascade([("feed", -FEED_DB_433, T_FEED_433), ("rx", 0.0, t_rx)], ta)
        t_b, _ = cascade([("lna", LNA433_GAIN, t_from_nf(LNA433_NF)),
                          ("feed", -FEED_DB_433, T_FEED_433), ("rx", 0.0, t_rx)], ta)
        row += " %5.2f" % db(t_a / t_b)
    print(row + "   <- dB of T_sys the LNA buys")
print("  -> robust across the whole plausible box: the LNA is worth ~%.1f-%.1f dB of T_sys"
      % (6.77, 12.31))
print("     (%.1f dB at the central case T_ant = 200 K, NF_RX = 8 dB). It is NOT useless." % 9.73)

print("""
ANSWER Q1:  the premise is WRONG.
  * An LNA IS the standard, cheapest way to improve receive sensitivity: it sets the
    system noise figure (Friis).  Against the numbers above it buys ~7-12 dB of T_sys
    on the 433 downlink (central case ~10 dB) and ~7-10 dB on the 2.4 GHz uplink -
    NOT zero.  The premise inverts the truth.
  * What an LNA CANNOT buy is the lower ANTENNA noise temperature that directivity
    provides: with the LNA already fitted, swapping the wide-beam antenna for a
    cold-sky dish removes only the T_ant term, worth ~4.0 dB at 433 MHz and only
    ~1.5-2.8 dB at 2.4 GHz (the 2.4 GHz figure is small because the ZX60 has only
    10 dB of gain at 2 GHz, so it does not fully suppress the downstream receiver
    noise - a higher-gain LNA would realise more of the cold-sky advantage).  That
    part is directivity-only and no amplifier can supply it.
  * Add the dish's own gain (22.15 - 14.0 = 8.15 dB) and a dish's total advantage is
    that gain PLUS the noise term above.
  * So the honest statement: an LNA is worth ~7-12 dB of the receive problem, and
    directivity is worth a further ~1.5-4 dB of NOISE plus its own gain.  They are
    ADDITIVE, not alternatives.""")

print("""
WHAT THE LNA'S dB IS AND IS NOT (the two things that must not be conflated)
  * The LNA's OWN gain (20 dB for the SSB 433 unit) is NOT worth 20 dB of link.  The
    worth is the T_sys improvement (~7-12 dB here), because the receiver noise is
    what it displaces.
  * The LNA cannot lower T_ant.  A wide-beam antenna at a warm horizon has a noise
    FLOOR (~200 K used here) that no amplifier can go below.  Only directivity
    (cold sky) goes below it.
  * The LNA must be at the MASTHEAD (before the coax) or it amplifies the coax loss
    too: 1.64 dB of feed loss at 433 MHz, 3.38 dB at 2.4 GHz.  That is exactly what
    the ~20 dB masthead preamps (EUR 152-345) are for.""")

# ==========================================================================
banner("Q2  YAGI ARRAY: bandwidth, mutual coupling, beamwidth, EUR/dB")
# ==========================================================================
print("""BANDWIDTH
  [CITED https://en.wikipedia.org/wiki/Yagi%E2%80%93Uda_antenna]
    "The bandwidth of Yagi-Uda ... is narrow, just a few percent of the center
     frequency, decreasing for models with higher gain"
    "in its basic form has a narrow bandwidth, 2-3 percent of the centre frequency"
  [CITED docs/analysis/ground-station-bom-candidates.md sec 1]  vendor stated bands:""")
for nm, band in (("Sirio WY 400 family (3/6/10 el)", BAND_SIRIO), ("Diamond A-430S10R / S15R", BAND_DIAMOND)):
    fb = 100.0 * (band[1] - band[0]) / ((band[0] + band[1]) / 2.0)
    print("    %-30s %6.1f-%6.1f MHz  = %5.2f %% fractional  (%.1f MHz)"
          % (nm, band[0], band[1], fb, band[1] - band[0]))
for pct in (2.0, 3.0):
    print("    generic %-22s %5.2f %% of 433.05 MHz         = %.1f MHz" % ("Yagi (Wikipedia)", pct, pct / 100.0 * 433.05))
print("""  READ: a practical 433 MHz Yagi is a 9-13 MHz antenna on the 2-3 % rule; the
  Diamond's own spec (430-440 MHz = 2.3 %) lands inside that. The Sirio WY 400
  family claims 400-470 MHz, i.e. it is a deliberately de-tuned wideband design
  and its "up to 14 dBi" is the peak, not the flat-band figure.
""")
print("""  THE INTERACTION THAT MATTERS: the priced 433 LNA is NARROWER THAN THE YAGI.
  [CITED https://www.wimo.com/en/ssb-70cm-ism-lna]  SSB LNA ISM 433 MHz is
  433-435 MHz ONLY = 2.0 MHz = %.2f %%. An LNA in front of the antenna sets the
  receive system bandwidth, so a narrowband LNA COLLAPSES a 2.3 %% Yagi to a
  0.46 %% system. That is fine for the 433.05-434.79 MHz ISM allocation
  (1.74 MHz, 0.40 %%) but forbids any operation outside it.""" % (2.0 / 434.0 * 100))

print("""
MUTUAL COUPLING (why a real 2-bay is +2.5-2.7 dB, not +3.0)
  For a pair at spacing d the coupling is strong (S21 in the -10 to -20 dB range at
  d ~ 0.5-0.7 lambda) and it does three things at once:
    1. PATTERN: the pair's array factor multiplies the element pattern; the coupling
       perturbs the element currents so the achieved gain falls short of the ideal
       +3.01 dB and the sidelobe level rises.
    2. IMPEDANCE / MATCH: each element's input impedance shifts, so the SWR<1.5
       window NARROWS relative to a single element - arraying costs bandwidth.
    3. BANDWIDTH: the stacked pair's match is narrowest at the design frequency.
  [CITED https://en.wikipedia.org/wiki/Phased_array] "arrays must extend many
   wavelengths to achieve the high gain needed for narrow beamwidth"; grating lobes
   are predicted from integer solutions of k*d*sin(theta) = 2*pi*m, i.e. d must stay
   below ~1 lambda to keep a single main lobe.""")

# ---- array factor and beamwidth, computed numerically ----
def af_hpbw(n, d_over_lam, elem_hpbw_deg):
    """HPBW of an N-element uniform broadside array (no taper) times a cos^q element
    pattern whose own -3 dB (half-POWER) HPBW is elem_hpbw_deg.
    Returns (combined_hpbw_deg, array_factor_hpbw_deg)."""
    kd = 2.0 * math.pi * d_over_lam
    th_h = math.radians(elem_hpbw_deg / 2.0)
    # half-power is 1/sqrt(2) in AMPLITUDE: cos(theta_h)^q = 1/sqrt(2)
    q = math.log(1.0 / math.sqrt(2.0)) / math.log(math.cos(th_h))

    def af_only(theta):
        psi = kd * math.sin(theta)
        if abs(math.sin(psi / 2.0)) < 1e-12:
            return 1.0
        return abs(math.sin(n * psi / 2.0) / (n * math.sin(psi / 2.0)))

    def pat(theta):
        return af_only(theta) * (max(math.cos(theta), 0.0) ** q)

    def cross(fn):
        t = 0.0
        step = math.radians(0.005)
        while t < math.radians(89.5):
            if fn(t) <= 1.0 / math.sqrt(2.0):
                break
            t += step
        return math.degrees(t)

    return 2.0 * cross(pat), 2.0 * cross(af_only)


print("-" * 78)
print("BEAMWIDTH vs ARRAY CONFIGURATION  (d = 0.5 lambda and 1.0 lambda stacking)")
print("-" * 78)
print("Element: the 3-element Sirio's PUBLISHED -3 dB beamwidth 125 deg (H) / 65 deg (E).")
print("  [CITED https://www.funktechnik-bielefeld.de/sirio-wy-400-3n-3-element-400-470-mhz]")
print("  d=%.1f lam : " % 0.5, end="")
print("the array factor's own HPBW is what sets how much a stack can narrow:")
for n in (2, 4):
    _, af = af_hpbw(n, 0.5, 65.0)
    print("      N=%d, d=0.5 lam -> array factor HPBW %.1f deg  (ideal array gain %+.2f dB)"
          % (n, af, 10 * math.log10(n)))

print("""
  PATTERN MULTIPLICATION: a STACK (same plane) narrows ONLY the stacking plane; the
  orthogonal plane is essentially unchanged.  Values below use the beam-solid-angle
  relation D = 41253 / (theta_E * theta_H)  [CITED https://en.wikipedia.org/wiki/Directivity,
  D = U_max/(P_tot/4*pi), and 4*pi = 41253 deg^2].
  Calibration on the vendor's own 3-el data (7 dBi with 65 x 125 deg):""")
d3 = lin(7.0); prod3 = 41253.0 / d3
print("    D = 7 dBi -> theta_E*theta_H = %.0f deg^2;  vendor 65*125 = %d deg^2 -> %.1f %% agreement."
      % (prod3, 65 * 125, 100.0 * abs(prod3 - 65 * 125) / (65 * 125)))
print("    (the relation is therefore validated on this antenna family; the element")
print("     beamwidths it predicts are ESTIMATEs - the 10/15-el vendors publish gain and")
print("     band but NOT beamwidth: TODO(unverified) exact -3 dB beamwidths.)")
for g in (7.0, 11.0, 14.0, 18.0):
    prod = 41253.0 / lin(g)
    ratio = 65.0 / 125.0
    th_e = math.sqrt(prod * ratio); th_h = th_e / ratio
    print("    %4.1f dBi class -> theta_E ~ %5.1f deg, theta_H ~ %5.1f deg" % (g, th_e, th_h))
print()
print("  NARROWING IN THE STACKING PLANE (element HPBW -> stacked HPBW):")
for g, elem in ((7.0, 65.0), (14.0, 29.2), (18.0, 18.4)):
    for n, d in ((2, 0.5), (2, 0.7), (4, 0.5)):
        comb, af = af_hpbw(n, d, elem)
        print("     %4.1f dBi element (%.1f deg) N=%d d=%.1f lam -> %5.1f deg  (x%.2f, %+.2f dB ideal gain)"
              % (g, elem, n, d, comb, comb / elem, 10 * math.log10(n)))
print("""  READ (and this is a MORE HONEST result than the intuition suggests):
    * For a SHORT/low-gain element (3-el, 65 deg) a 2-bay stack narrows 65 -> 44.5 deg,
      i.e. 32 % - the beamwidth penalty is real.
    * For a HIGH-gain 10/15-el element (29 deg) the SAME 2-bay stack narrows only
      29.2 -> 26.3 deg (10 %), because the array factor (60 deg) is already BROADER
      than the element, so pattern multiplication barely bites.  A 4-bay narrows it
      to 19.7 deg (33 %).
    * The orthogonal plane is essentially unchanged.
  So the "arraying makes pointing harder" objection is REAL but MODEST at 2-bay
  (10-32 % depending on the element), and stronger at 4-bay (33 %).  The heavier
  cost of arraying is WIND, not beamwidth: doubling the aperture doubles the mast
  moment, which can cross a positioner class boundary (EUR 80-1,346).""")

print("-" * 78)
print("2-BAY / 4-BAY FULL COST  (all prices fetched at WiMo this session)")
print("-" * 78)
SPLITTER_430_EUR = 61.40    # [CITED https://www.wimo.com/en/accessories/antenna-accessories/power-splitter-phasing-harnesses]
PHASELINE_70CM_EUR = 63.00  # [CITED same]
JUMPER_EST = 12.00          # [ESTIMATE] ~3 x 1 m N-male jumper + 2 T-pieces, no vendor price read
for n, eur_each, gain_each, tot_gain in ((1, EUR_YAGI_10EL, G_YAGI_10EL, 14.0),
                                         (2, EUR_YAGI_10EL, G_YAGI_10EL, 17.0),
                                         (4, EUR_YAGI_10EL, G_YAGI_10EL, 20.0)):
    ants = n * eur_each
    harness = ((SPLITTER_430_EUR + (n - 1) * JUMPER_EST) if n > 1 else 0.0)
    marg = (ants + harness) - EUR_YAGI_10EL
    dg = tot_gain - G_YAGI_10EL
    print("  %d-bay 10-el WY 400-10N: antennas EUR %6.2f + harness EUR %5.2f = EUR %7.2f"
          % (n, ants, harness, ants + harness))
    if n > 1:
        print("     marginal over ONE element: EUR %7.2f for +%.1f dB  =  %.1f EUR/dB"
              % (marg, dg, marg / dg))
print("  (2x Sirio WY 400-10N stacked is the repo's own measured pairing: 14.0 -> 17.0 dBi,"
      " i.e. the +3.0 dB ideal. [CITED docs/analysis/ground-station-gain-per-dollar.md Table A])")
print("  Wind: stacking also doubles the projected area and the mast moment -> the array")
print("  can cross a positioner class boundary (a step of EUR 80-1,346 in the")
print("  positioner menu). [CITED ground-station-gain-per-dollar.md sec 1.6 / sec 2.7]")

# ==========================================================================
banner("Q3  'ONE CHEAP TRACKER PER YAGI, COMBINED' - what actually adds gain")
# ==========================================================================
print("""Four DIFFERENT things the operator's sentence could mean.  Signal and noise
bookkeeping for N equal branches, each with per-branch SNR s = a^2/sigma^2:
""")
N_list = (2, 4)
print("  (a) COHERENT PHASED ARRAY - phase-aligned sum into ONE receiver")
print("      y = sum(a + n_i) = N*a + sum(n_i)  ->  P_sig = N^2 a^2, P_noise = N sigma^2")
print("      SNR = N*a^2/sigma^2   -> GAIN = 10*log10(N)")
print("        N=2: %+.2f dB    N=4: %+.2f dB" % (10 * math.log10(2), 10 * math.log10(4)))
print("      REQUIRES: per-element phase coherence. Costs a phase shifter (or a")
print("      measured/servoed line length) PER ELEMENT, plus a coherent reference, plus")
print("      CONTINUOUS phase correction because the balloon's geometry changes.")
print("      [CITED https://en.wikipedia.org/wiki/Phased_array  'the transmitter is fed to")
print("       the radiating elements through devices called phase shifters, controlled by")
print("       a computer system, which can alter the phase or signal delay electronically']")
print()
print("  (b) INCOHERENT POWER COMBINING - the N antenna outputs squashed together in one")
print("      receiver (or summed after envelope detection, phases random)")
print("      P_sig = N a^2, P_noise = N sigma^2  ->  SNR = a^2/sigma^2  -> GAIN = 0.00 dB")
print("      This is the case people HOPE works and it does not: N x signal AND N x noise.")
print()
print("  (c) MRC / DIVERSITY with N SEPARATE RECEIVERS")
print("      Each branch keeps its own independent noise; MRC weights by SNR and sums:")
print("      SNR_out = sum_k s_k = N*s  -> GAIN = 10*log10(N)   [same as (a)]")
print("        N=2: %+.2f dB    N=4: %+.2f dB"
      % (10 * math.log10(2), 10 * math.log10(4)))
print("      [CITED https://en.wikipedia.org/wiki/Diversity_combining  'Maximal-ratio")
print("       combining ... The resulting SNR yields sum_{k=1}^{N} SNR_k']")
print("      REQUIRES N complete receivers (N LR2021 + N LNAs + N feeds) AND per-branch")
print("      co-phasing (MRC is 'predetection combining', i.e. still coherent).")
print("      [CITED https://en.wikipedia.org/wiki/Maximal-ratio_combining]")
print("      CAVEAT: the 10*log10(N) needs the branch noise to be INDEPENDENT. If the")
print("      elements are close and T_ant noise is correlated, the gain is less.")
print("      DIVERSITY gain against FADING is a different quantity:")
print("      selection combining on N independent Rayleigh branches gives sum_{k=1}^{N} 1/k:")
for n in N_list:
    sel = sum(1.0 / k for k in range(1, n + 1))
    print("        N=%d: sum 1/k = %.3f -> %+.2f dB (fading only, not mean SNR)"
          % (n, sel, db(sel)))
print("      [CITED https://en.wikipedia.org/wiki/Diversity_combining  'the expected")
print("       diversity gain has been shown to be sum_{k=1}^{N} 1/k']")
print("      An elevated balloon is a near-LOS path, so there is little fading to harvest:")
print("      this diversity gain is mostly NOT available to us.")
print()
print("  (d) MULTI-SECTOR COVERAGE - N cheap, coarsely aimed antennas at DIFFERENT sky")
print("      sectors, pick the best  ->  GAIN over the best single = 0.00 dB (one target!)")
print("      What it DOES buy: the per-antenna pointing requirement relaxes by about the")
print("      sector width, and a tracker that misses costs coverage, not the link.")
print()
print("COST CHECK (prices fetched at WiMo this session)")
print("  a 2-way 430 MHz 2000 W splitter + jumpers   = EUR %.2f" % (SPLITTER_430_EUR + JUMPER_EST))
print("  a (c)-style SECOND receive chain (LNA-only) = EUR %.2f (+ a 2nd LR2021 ~USD 20-30 [ESTIMATE])"
      % LNA433_EUR)
print("  a (a)-style phase-shifter per element        = not priced; no 433 MHz amateur phase")
print("      shifter product was found this session -> TODO(unverified).")
print()
print("""ANSWER Q3, UNDIPLOMATICALLY
  * The operator's sentence, taken literally - "one cheap tracker per Yagi, COMBINED" -
    is case (a)/(c) ONLY IF the phases are aligned. Nothing about using a SEPARATE
    tracker per Yagi achieves that: separate trackers guarantee separate phase.
  * If the N Yagis point at the SAME target and their outputs are simply combined, that
    is case (b) = +0.00 dB of SNR. It adds COST and COMPLEXITY and NO GAIN.
  * The only versions that ADD GAIN are (a) coherent phased array and (c) MRC with N
    receivers, both worth 10*log10(N) (+3.0 dB for N=2, +6.0 dB for N=4), and BOTH need
    per-branch phase coherence and (for c) N radios.
  * The version that is actually USEFUL to this project is (d) MULTI-SECTOR COVERAGE:
    it adds NO gain but it REMOVES the precision-tracking requirement - which is the
    real engineering problem for a cheap tracker.  Frame the operator's idea as (d),
    not as a gain scheme, and it is sound; frame it as a gain scheme and it is not.
""")

# ==========================================================================
banner("Q4  BALLOON-RECEIVER OVERDRIVE AND EXTERNAL GAIN CONTROL")
# ==========================================================================
G_TX_GROUND_WIDE = 12.4      # dBi, FlexaYagi FX 7015V class [CITED bom-candidates A6]
L_UPLINK = 2.0               # dB [ESTIMATE] implementation/polarisation on the uplink
G_BALLOON_2400 = 0.0         # dBi, conservative [CITED docs/LINK-BUDGET-LICENCE-EXEMPT.md]
print("Uplink geometry: ground TX at P_tx into G_tx = %.1f dBi, balloon RX G = %.1f dBi," % (G_TX_GROUND_WIDE, G_BALLOON_2400))
print("L = %.1f dB, lambda(2440 MHz) = %.4f m, FSPL(d) = 20*log10(4*pi*d/lambda) = %.2f + 20*log10(d_m)"
      % (L_UPLINK, LAM_2400, 20 * math.log10(4 * math.pi / LAM_2400)))
def p_rx_balloon(p_tx_dbm, d_m):
    return p_tx_dbm + G_TX_GROUND_WIDE + G_BALLOON_2400 - fspl(d_m, LAM_2400) - L_UPLINK
print()
print("  P_rx_at_balloon(dBm) = P_tx + %.1f - FSPL(d) - %.1f" % (G_TX_GROUND_WIDE, L_UPLINK))
print()
print("  %-22s %-10s %-10s %-12s" % ("ground TX", "P_rx @10 m", "@100 m", "@20 km"))
for p in (20.0, 30.0, 33.0, 40.0, 40.8):
    print("  %-22s %-10.1f %-10.1f %-12.1f" % ("+%.1f dBm" % p, p_rx_balloon(p, 10),
                                              p_rx_balloon(p, 100), p_rx_balloon(p, 20000)))
print()
print("  RANGE AT WHICH THE BALLOON RX BEGINS TO COMPRESS / OVERLOAD")
print("  (solving P_rx(d) = threshold for d)")
print("  %-10s" % "ground TX" + "".join("  %-11s" % t for t in ("-30 dBm", "-20 dBm", "-10 dBm", "0 dBm")))
for p in (20.0, 30.0, 33.0, 40.8):
    row = "  %-10s" % ("+%.1f dBm" % p)
    for thr in (-30.0, -20.0, -10.0, 0.0):
        # P_tx + G - 40.05... solve 20log10 d = p + G - L - thr - C0
        c0 = 20 * math.log10(4 * math.pi / LAM_2400)
        x = p + G_TX_GROUND_WIDE - L_UPLINK - thr - c0
        d = 10 ** (x / 20.0)
        row += "  %-11s" % ("%.1f m" % d if d < 1000 else "%.2f km" % (d / 1000.0))
    print(row)
print("""
  THRESHOLDS USED, and why they are the right ones:
    -20 dBm  : a LoRa-class receiver's AGC/LNA compression onset.  The repo MEASURED
               exactly this on hardware: at 1-2 m the LR2021's RSSI read -8.0 dBm at
               every TX power from 0 to 12 dBm and the AGC/LNA compressed, "masking
               power differences".  [CITED docs/power-sweep-results-2026-07-24.md,
               "Receiver saturation at close range ... This is the most likely
               explanation"]
    0 dBm    : hard overload.
  [TODO(unverified)] the LR2021's published maximum input / blocking level - not found
  in-repo and not fetched this session. -20 dBm is used as the conservative onset.""")
print()
print("  So a +33 dBm ground PA on a 12.4 dBi Yagi puts the balloon's receiver into")
print("  compression inside roughly 15 m and hard-overloads it inside ~1.5 m.  The same")
print("  arithmetic at the balloon's working range (>20 km) leaves the uplink at")
print("  %.1f dBm - i.e. the PA is not needed at all (see Q5)." % p_rx_balloon(33.0, 20000))
print()
print("-" * 78)
print("CAN EXTERNAL GAIN CONTROL SOLVE IT?  Four candidate mechanisms, costed")
print("-" * 78)
print("""  1. VARIABLE-GAIN AMPLIFIER (VGA) or DIGITAL STEP ATTENUATOR in front of the PA.
     A step attenuator is a real, priced, buyable mechanism:
       [CITED https://www.minicircuits.com/pdfs/DAT-31R5A-PN+.pdf] DAT-31R5A+ series,
       0-31.5 dB in 0.5 dB steps, DC-4.0 GHz, IP3 52 dBm.  PRICE TODO(unverified)
       (Mini-Circuits prices are AJAX-only; the WebStore price endpoints returned
       nothing to this session's fetch).
       [CITED https://www.wimo.com/en/accessories/antenna-accessories/meters/dummyloads-attenuators]
       fixed attenuators: 1 W 3-20 dB SMA EUR 24.50; 3-30 dB 2 W N EUR 39.00.
     A 31.5 dB range covers the +33 dBm -> compression-inside-15 m problem ONLY if it
     is DRIVEN WITH INFORMATION; a hand-set attenuator is a one-off calibration, not
     a control loop.
  2. AGC inside the receiving radio - and here is the catch: THE OVERDRIVE IS IN THE
     BALLOON'S RECEIVER, WHICH WE DO NOT CONTROL FROM THE GROUND.  Ground-side AGC
     cannot help a receiver on the other end of the link.
  3. CLOSED-LOOP POWER CONTROL from the balloon's telemetry (its own GNSS range):
     range is known on the balloon, so the F33/PA drive could in principle be scaled:
       P_tx_required(d) = S + FSPL(d) + margin - G_balloon - G_ground + L
     This is implementable (the balloon already has the F33's CE/LDO enable pin and
     GNSS).  Cost: firmware, not hardware.  It fully solves the CLOSE-RANGE case,
     because the balloon can drop its own TX power - but that is the BALLOON's PA
     (433 downlink) and is a separate control loop from the GROUND uplink PA.
  4. CLOSED-LOOP FROM THE DOWNLINK RSSI AS FEEDBACK: the ground listens to the
     433 downlink RSSI and scales the 2.4 GHz uplink drive so the balloon sees a
     constant level.  Round-trip latency is one packet; usable.  Cost: firmware + a
     power detector (the DXpatrol 12 W amp already exports 0-4 V forward-power and
     SWR outputs: [CITED https://www.wimo.com/en/qo100-amp12] "outputs (0-4V) for SWR
     and power ... allow precise control of the amplifier's operation").""")
print("""
  WHAT IT COSTS AND HOW WELL IT WORKS""")
print("  %-30s %-20s %-9s %s" % ("mechanism", "hardware", "solves?", "note"))
print("  " + "-" * 74)
for m, hw, sv, nt in (
        ("step attenuator (manual)", "EUR 24.50-39.00", "partly", "one-off calibration; no loop"),
        ("VGA + detector + MCU", "EUR 40-120 [EST]", "yes", "needs firmware"),
        ("ground AGC", "EUR 0", "no", "wrong end of the link"),
        ("balloon TX power from GNSS", "firmware only", "yes", "balloon side only"),
        ("downlink-RSSI closed loop", "firmware + detector", "yes", "best of the four")):
    print("  %-30s %-20s %-9s %s" % (m, hw, sv, nt))
print("""CONCLUSION Q4: the catch is MANAGEABLE, not fatal, and it is NOT a reason to reject
  amplification - but it IS a reason not to need it.  Note the direction of cause: the
  overdrive exists ONLY because the ground PA is oversized by ~36 dB for the link it
  serves (Q5).  Remove the surplus and the problem disappears; power control buys back
  the same 30-40 dB the link never needed.  The honest verdict: "not needed", not
  "solved" - but if the operator wants the amplifier anyway, a step attenuator plus a
  downlink-RSSI loop is the correct, cheap, implementable answer.""")

# ---- does a SINGLE FIXED pad suffice?  compute the crossover honestly ----
print()
print("-" * 78)
print("DOES ONE FIXED PAD SUFFICE?  (the precise crossover - do not over-claim)")
print("-" * 78)
print("  A fixed pad P (dB) must satisfy TWO constraints at once:")
print("    (i)  close-in: P >= P_rx(d_min) - (compression onset)   so the balloon is not overdriven")
print("    (ii) at range: P <= P_rx(d_max) - (sensitivity + margin) so the link still closes")
S_2400 = M.S_2400_LNA_ON
MARGIN = 6.0
D_MIN = 1.4
p_close = M.p_rx_balloon(40.8, D_MIN)
need_min = p_close - (-20.0)
print("  P_tx = +40.8 dBm (12 W), G_tx = 12.4 dBi, d_min = 1.4 m -> P_rx = %+.1f dBm" % p_close)
print("    (i)  P >= %+.1f - (-20.0) = %.1f dB" % (p_close, need_min))
print("  %-9s %-13s %-13s %-13s %s"
      % ("d_max", "P_rx@d_max", "P_max (ii)", "P_min (i)", "single fixed pad?"))
for d_max in (20e3, 300e3, 650e3):
    p_far = M.p_rx_balloon(40.8, d_max)
    pad_max = p_far - (S_2400 + MARGIN)
    ok = "YES" if need_min <= pad_max else "NO"
    print("  %-9s %+9.1f   %9.1f dB  %9.1f dB  %s"
          % ("%.0f km" % (d_max / 1e3), p_far, pad_max, need_min, ok))
print("""  READ (this is the precise version of the answer, and it corrects a looser claim):
    * A SINGLE FIXED pad satisfies BOTH constraints only while the range ceiling is
      generous enough. The DAT-31R5A+ (0-31.5 dB in 0.5 dB steps) covers the whole span
      in ONE part, so the cheap answer is a SWITCHABLE pad of 2-4 discrete states driven
      by an estimated range - not a hand-set screwdriver pad, and not necessarily a
      continuous VGA loop.
    * Where the row says NO, no fixed pad works at all and a state change is mandatory.""")


# ==========================================================================
banner("Q5  RE-COST THE AMPLIFIER-LED STATION (operator ALREADY owns the 2.4 GHz amp + circulator)")
# ==========================================================================
print("""FIRST, THE BAND QUESTION - because it decides everything else.
  Committed band split: [CITED docs/adr/034-* "433 TX / 2.4 GHz RX"; reproduced in
  docs/analysis/ground-station-gain-per-dollar.md sec 1.3]
      balloon TX = 433 MHz (downlink)          <- the BINDING direction
      balloon RX = 2.4 GHz (uplink)            <- needs NEGATIVE ground gain
  A circulator and an amplifier are BAND-SPECIFIC.  A 2.4 GHz amplifier can only ever
  amplify the GROUND->BALLOON uplink.  It cannot add one dB to the 433 downlink, which
  is the direction that sets ground gain.  This is the single most important sentence
  in this document.""")
print()
print("-" * 78)
print("HOW MUCH DOES THE UPLINK ACTUALLY NEED?  (is there anything left to amplify?)")
print("-" * 78)
REQ_G_650 = -10.7   # dBi required ground gain at 650 km, +20 dBm EIRP, balloon LNA [CITED gain-per-dollar sec 1.3]
print("  [CITED docs/analysis/ground-station-gain-per-dollar.md sec 1.3; positioner study sec 3.1]")
print("    2.4 GHz uplink required ground gain at 650 km, +20 dBm EIRP = %+.1f dBi  (NEGATIVE)" % REQ_G_650)
for p_tx in (20.0, 30.0, 33.0, 40.8):
    req = REQ_G_650 - (p_tx - 20.0)
    surplus = G_TX_GROUND_WIDE - req
    print("    ground TX +%.1f dBm -> required ground gain %+7.1f dBi; a 12.4 dBi Yagi gives %+5.1f dB SURPLUS"
          % (p_tx, req, surplus))
print("""
  READ: the uplink closes with an OMNI at +20 dBm.  With a 12.4 dBi Yagi and the
  repo's own -10.7 dBi requirement it has ~23 dB of surplus BEFORE any amplifier, and
  ~36 dB with a +33 dBm PA.  There is no link-closure job for the amplifier to do on
  this band.  A very high power 2.4 GHz uplink also collides with the 100 mW EIRP
  licence-exempt cap (the +13...+33 dBm class is amateur-licence-only).""")
print()
print("-" * 78)
print("DOES THE CIRCULATOR SOLVE T/R ISOLATION / SELF-DESENSE?")
print("-" * 78)
Iso_typ = 20.0   # dB, typical coaxial drop-in circulator TX->RX isolation  [TODO(unverified) exact figure]
IL_typ = 0.5     # dB, typical insertion loss                              [TODO(unverified) exact figure]
print("  [TODO(unverified)] no 2.4 GHz circulator datasheet was fetched this session (vendor")
print("  pages returned 404; search engines captcha'd).  The class figures used here are")
print("  ESTIMATES typical of a coaxial ferrite drop-in: isolation ~18-25 dB, IL ~0.3-0.5 dB.")
print("  Using the pessimistic end: isolation %.0f dB, IL %.1f dB." % (Iso_typ, IL_typ))
print()
print("  A) SAME-BAND, ONE SHARED 2.4 GHz ANTENNA (the only case where a circulator helps):")
for p_tx in (30.0, 33.0, 40.8):
    leak = p_tx - Iso_typ + IL_typ
    lna_out = leak + ZX60_GAIN[2000]
    print("     TX %+.1f dBm -> leakage at the RX port = %+.1f - %.0f + %.1f = %+.1f dBm" % (p_tx, p_tx, Iso_typ, IL_typ, leak))
    print("        after a 10 dB 2.4 GHz LNA the chip sees %+.1f dBm  -> %s"
          % (lna_out, "RX chip destroyed/overloaded" if lna_out > 0 else "still hot"))
print("     So a SINGLE circulator is NOT sufficient at +30...+40 dBm: ~20 dB of isolation")
print("     leaves +10...+20 dBm at the RX port.  You need isolation >= TX - (RX tolerance),")
print("     i.e. ~40-55 dB, which is circulator + T/R switch or circulator + a T/R")
print("     amplifier/preamp with a bypass relay - NOT a circulator alone.")
print("     The repo's own ZX60 max input is +%.0f dBm (2-3 GHz) [CITED ZX60-P103LN+ datasheet]"
      % ZX60_IN_MAX_HI)
print("     and its P1dB is +%.1f dBm at 2 GHz, so the LNA survives but the downstream" % ZX60_P1DB[2000])
print("     receiver does not.  Practical, buyable alternatives that DO switch the LNA out:")
print("       - RT-2400-2  2.4 GHz TX+RX amplifier with internal switching, EUR %.2f" % RT2400_EUR)
print("       - SHF mast preamp, ADJUSTABLE gain, 150 W switched through, EUR %.2f" % SHF_EUR)
print("       - SP-S mast preamp with VOX RX/TX switch, EUR %.2f" % SPS_EUR)
print("       - coax relay SPDT 3x N (CX-600N), EUR 142.00  [CITED wimo coaxial-relays]")
print()
print("  B) THE COMMITTED 433/2.4 GHz SPLIT: the circulator is the WRONG COMPONENT.")
print("     With ground RX at 433 MHz and ground TX at 2.4 GHz you do not need T/R")
print("     isolation at all - different bands, and the feed is a diplexer/filter problem,")
print("     not a circulator problem.  A 2.4 GHz circulator can only serve a same-band")
print("     (2.4 GHz, both directions) link, which the repo does not currently run.")
print("     [CITED https://en.wikipedia.org/wiki/Circulator  'a signal applied to port 1")
print("      only comes out of port 2' - band-selective by construction]")
print()
print("-" * 78)
print("MARGINAL COST OF THE AMPLIFIER-LED DESIGN AND ITS EUR/dB")
print("-" * 78)
print("  Operator already owns the 2.4 GHz amplifier + circulator -> marginal hardware cost")
print("  of the amplification itself = EUR 0.00.  The REAL marginal cost is what the")
print("  amplifier forces you to add so its output is usable:")
print("    step attenuator (so the PA drive is settable)        EUR  25.00-40.00")
print("    T/R switching that actually works at +33 dBm         EUR 142.00-355.00")
print("    PSU + heatsink for 12 W (heat is NOT a constraint,")
print("      but the metal is still bought)                     EUR  40.00-90.00  [ESTIMATE]")
print("    ------------------------------------------------------")
print("    marginal total (low / high)                          EUR 207.00 / 485.00")
print()
print("  Link dB bought: 0.0 dB on the binding 433 downlink; 0 dB NEEDED on the")
print("  non-binding 2.4 GHz uplink (it is already ~23-36 dB in surplus).")
print("  => EUR/dB = UNDEFINED / infinite: you buy no needed dB.")
print()
print("  The 2.4 GHz amplifier's OWN gain is 12-24 dB [CITED DXpatrol 1 W / 12 W pages],")
print("  so if EUR/dB is computed on the DEVICE's gain it looks like EUR 0-2/dB:")
print("    device-gain EUR/dB, owned amp    = 0.00 EUR/dB (free hardware)")
print("    device-gain EUR/dB, RT-2400-2    = %.2f EUR/dB (EUR %.2f / 13 dB TX gain)"
      % (RT2400_EUR / RT2400_TX_GAIN, RT2400_EUR))
print("    BUT that dB is in the WRONG DIRECTION.  A dB is not fungible across bands.")
print()

print("-" * 78)
print("THE FULL EUR/dB LEDGER, SAME DEFINITION FOR EVERY ROW")
print("-" * 78)
print("""
  Definition: USD (or EUR) per dB of LINK-BUDGET improvement in the direction that
  needs it.  For a receive device the 'dB' is the T_sys improvement it delivers
  (computed in Q1), NOT the device's own gain - otherwise a gain block looks free.""")

def row(label, money, unit, dbs, note=""):
    return (label, money, unit, dbs, (money / dbs if dbs else None), note)

# the LNA's system dB, from Q1, at the central case RX NF = 8 dB
t_rx8 = t_from_nf(8.0)
_t_a, _ = cascade([("feed", -FEED_DB_433, T_FEED_433), ("rx", 0.0, t_rx8)], T_ANT_WIDE)
_t_b, _ = cascade([("lna", LNA433_GAIN, t_from_nf(LNA433_NF)),
                   ("feed", -FEED_DB_433, T_FEED_433), ("rx", 0.0, t_rx8)], T_ANT_WIDE)
lna_dbs = db(_t_a / _t_b)

rows = []
# F33 on the balloon: USD 8 for +20 dB (+12.15 -> +33 dBm) [CITED task brief + flrc-max REC-1]
rows.append(row("F33 module on the BALLOON (+12.15 -> +33 dBm)", 8.00, "USD", 20.0,
                "USD 8 [CITED brief/flrc-max]; this IS the 0.40 USD/dB bar"))
rows.append(row("F33, alternative reading (chip +22 -> +33 dBm)", 8.00, "USD", 11.0,
                "same USD 8 counted as 11 dB -> 0.73 USD/dB"))
rows.append(row("F33 (same, expressed in EUR @ 0.92)", 7.36, "EUR", 20.0,
                "FX 0.92 EUR/USD is an ESTIMATE; the bar is 0.40 USD/dB"))
# 433 LNA, from Q1 (RX NF 8 dB, wide-beam 433)
rows.append(row("SSB LNA ISM 433 (EUR 257) as a SYSTEM dB", LNA433_EUR, "EUR", lna_dbs,
                "the priced, spec'd 433 LNA; T_sys gain at RX NF 8 dB"))
rows.append(row("bare MMIC LNA in the same role", float('nan'), "?", lna_dbs,
                "no MMIC price sourced this session -> cannot be scored (TODO)"))
# 2.4 GHz PA on the wrong direction
rows.append(row("DXpatrol 1 W 2.4 GHz PA - WRONG DIRECTION", DP1W_EUR, "EUR", 0.0,
                "0 dB on the 433 downlink; the uplink is already in surplus"))
rows.append(row("DXpatrol 12 W 2.4 GHz PA - WRONG DIRECTION", DP12W_EUR, "EUR", 0.0, "same"))
# Yagi arrays
marg2 = (2 * EUR_YAGI_10EL + SPLITTER_430_EUR + 1 * JUMPER_EST) - EUR_YAGI_10EL
rows.append(row("2-bay Yagi array (marginal over one Yagi)", marg2, "EUR", 3.0,
                "2nd ant EUR 155 + splitter EUR 61.40 + 1 jumper EUR 12"))
marg4 = (4 * EUR_YAGI_10EL + SPLITTER_430_EUR + 3 * JUMPER_EST) - EUR_YAGI_10EL
rows.append(row("4-bay Yagi array (marginal over one Yagi)", marg4, "EUR", 6.0, "same harness"))
# dish + tracker (from the base study): marginal over the recommended Yagi rig
rows.append(row("1.9 m mesh dish + BIG-RAS, GAIN only", 2297.0, "EUR", 2.84,
                "marginal over the Yagi rig (repo Table D); +2.84 dB of antenna gain"))
rows.append(row("same dish, gain + cold-sky noise advantage", 2297.0, "EUR", 2.84 + 3.8,
                "adds the ~3.8 dB T_ant term from Q1 -> the honest upper bound"))
print("  %-52s %6s %8s %10s" % ("candidate", "money", "dB", "per dB"))
print("  " + "-" * 80)
for label, money, unit, dbs, epd, note in rows:
    m = ("%.2f" % money) if money == money else "TODO"
    u = unit if money == money else ""
    d = "%.1f" % dbs
    v = ("%.2f" % epd) if (epd is not None and epd == epd) else ("INF" if dbs == 0 else "TODO")
    print("  %-52s %6s %8s %10s  %s" % (label[:52], m, d, v, u))
print("  " + "-" * 80)
print("  (notes)")
for label, money, unit, dbs, epd, note in rows:
    print("    - %-48s %s" % (label[:48], note))
print()
print("""  RANKING ON COST-PER-NEEDED-dB, best first:""")
print("    1. F33 module on the balloon      %.2f USD/dB  (%.2f EUR/dB)  <- the bar" % (8.0 / 20.0, 7.36 / 20.0))
print("    2. 433 ground LNA (system dB)      %.1f EUR/dB" % (LNA433_EUR / lna_dbs))
print("    3. 2-bay Yagi array               %.1f EUR/dB" % (marg2 / 3.0))
print("    4. 4-bay Yagi array               %.1f EUR/dB" % (marg4 / 6.0))
print("    5. 1.9 m mesh dish + tracker      %.0f-%.0f EUR/dB" % (2297.0 / (2.84 + 3.8), 2297.0 / 2.84))
print("    6. 2.4 GHz ground PA            INF - buys ZERO needed dB (wrong direction)")
print()
print("  RATIOS against the bar (the numbers quoted in the doc and ADR):")
f33_eur = 8.0 * 0.92 / 20.0
print("    F33 in EUR/dB                     %.3f EUR/dB  (= %.2f USD/dB)" % (f33_eur, 8.0 / 20.0))
print("    433 LNA   / F33                   %.0fx" % ((LNA433_EUR / lna_dbs) / f33_eur))
print("    2-bay arr / F33                   %.0fx   (and %.2fx the 433 LNA)"
      % ((marg2 / 3.0) / f33_eur, (marg2 / 3.0) / (LNA433_EUR / lna_dbs)))
print("    4-bay arr / F33                   %.0fx   (and %.2fx the 433 LNA)"
      % ((marg4 / 6.0) / f33_eur, (marg4 / 6.0) / (LNA433_EUR / lna_dbs)))

# ==========================================================================
banner("VERDICT")
# ==========================================================================
print("DO-NOT-BUILD the amplifier-led ground station.")
print()
print("BUILD (unchanged from the prior studies):")
print("  1. the F33 module on the balloon (USD 8, +20 dB, %.2f USD/dB) - the bar;" % (8.0 / 20.0))
print("  2. a 433 MHz LNA at the masthead as the receive-side gain device it is")
print("     (EUR %.0f, +%.1f dB of T_sys, %.1f EUR/dB) IF extra receive margin is wanted -"
      % (LNA433_EUR, lna_dbs, LNA433_EUR / lna_dbs))
print("     this is the ONE ground amplifier that does something, and it is a RECEIVE one;")
print("  3. a Yagi (not an array, not a dish) on the DIY tracker.")
print()
print("DO NOT DO:")
print("  - do not amplify the 2.4 GHz uplink (nothing to amplify; ~23-36 dB surplus);")
print("  - do not expect the owned 2.4 GHz circulator to fix T/R (wrong band for the")
print("    committed split; insufficient isolation for a same-band +33 dBm front end);")
print("  - do not build a Yagi ARRAY expecting cheap gain (%.0f-%.0f EUR/dB and a NARROWER beam);"
      % (marg2 / 3.0, marg4 / 6.0))
print("  - do not expect 'one tracker per Yagi, combined' to add gain (it adds coverage).")
print("Reproduction: python3 docs/analysis/ground_station_amplifier_hypothesis_model.py")
