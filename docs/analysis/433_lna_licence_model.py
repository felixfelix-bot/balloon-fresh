#!/usr/bin/env python3
"""Reproducible model for the 433 MHz LNA substitution + German amateur-licence study.

    python3 docs/analysis/433_lna_licence_model.py

Every number printed here is quoted verbatim in
`docs/analysis/433-lna-substitution-and-amateur-licence.md`. stdlib only (math).

Provenance tags used in the comments:
  [CITED <url|repo path>]  a figure read from a source this session
  [COMPUTED]               derived here, formula shown in the print
  [ESTIMATE <basis>]       labelled estimate, basis named
  [TODO(unverified)]       could not be sourced
"""

import math

# ─────────────────────────────────────────────────────────────────────────────
# Constant bank
# ─────────────────────────────────────────────────────────────────────────────

# 433 MHz ISM downlink design point (repo band split, ADR-034/ADR-073)
F_MHZ = 433.92                      # [CITED repo docs/adr/034-radio-band-split-433-tx-2g4-rx.md]
F_UP_MHZ = 2450.0                   # ground->balloon uplink, [CITED repo ADR-034]

# Receive-chain (masthead-LNA) model — same frame as the sibling study
# [CITED design/amplifier-hypothesis-check @148578c, docs/analysis/ground-station-amplifier-hypothesis-check.md §1.2]
COAX_LOSS_DB = 1.14                 # 15 m Airborne 10 @433 MHz [CITED ground-station-bom-candidates.md §F3]
CONN_LOSS_DB = 0.5                  # connectors [CITED same]
FEED_LOSS_DB = COAX_LOSS_DB + CONN_LOSS_DB
T_ANT_WIDE = 200.0                  # K, wide-beam ground antenna [ESTIMATE, sibling §1.2 bracket 150-290 K]
NF_RX_DB = 8.0                      # LR2021 receiver NF, bracketed 6/8/10 in sibling [TODO(unverified)]

# Sensitivities, LR2021 datasheet Table 3-12/3-13 [CITED repo docs/analysis/ground-station-flrc-max-throughput.md]
FLRC = [
    # label,        kbps, BW DSB MHz, sens dBm
    ("FLRC 2600 kbps", 2600, 2.666, -99.0),
    ("FLRC 2080 kbps", 2080, 2.222, -100.0),
    ("FLRC 1300 kbps", 1300, 1.333, -101.5),
    ("FLRC 1040 kbps", 1040, 1.333, -102.5),
    ("FLRC  650 kbps",  650, 0.740, -104.0),
    ("FLRC  520 kbps",  520, 0.571, -105.0),
]

# The five LNA / preamp candidates, every number sourced this session
# name, NF_dB, gain_dB, price_EUR, band, source
LNAS = [
    ("SSB Electronic LNA ISM 433", 0.7, 20.0, 257.00, "433-435 MHz",
     "https://www.wimo.com/en/ssb-70cm-ism-lna"),
    ("I0JXX PRE432JXX", 0.45, 23.0, 550.00, "430-435 MHz",
     "https://www.wimo.com/en/i0jxx-vhf-uhf-preamplifiers"),
    ("SSB Electronic LNA series 70cm", None, None, 226.00, "430-440 MHz",
     "https://www.wimo.com/en/ssb-electronic-lna-preamp"),
    ("Kuhne MKU LNA 432 A", 0.4, 20.0, None, "432.2 +/-2 MHz",
     "web.archive.org kuhne_english_preamp.pdf (2007)"),
    ("Mini-Circuits ZX60-P103LN+", 0.5, 20.3, 119.47 * 0.92, "50-3000 MHz",
     "https://www.minicircuits.com/WebStore/dashboard.html?model=ZX60-P103LN%2B"),
]

FX_USD_EUR = 0.92                   # [ESTIMATE, sibling §9]

# German amateur limits — AFuV Anlage 1 (BGBl. 2024 I Nr. 175, S. 1-4)
# [CITED https://www.gesetze-im-internet.de/afuv_2005/AFuV.pdf]
AMATEUR = [
    # band,            status, class A,     class E,   class N
    ("430-440 MHz", "P", "750 W PEP", "75 W PEP", "6.1 W ERP"),
    ("2320-2400 MHz", "S", "75 W PEP", "5 W PEP", "-"),
    ("2400-2450 MHz", "S", "75 W PEP", "5 W PEP", "-"),
]
BW_MAX_70CM_MHZ = 2.0               # AFuV Anlage 1, Band 18, Zusatzbestimmung 7
BW_MAX_13CM_MHZ = 10.0              # AFuV Anlage 1, Band 22/23, Zusatzbestimmung 9

# 2-bay array (operator's upgrade path)
ARRAY_GAIN_DB = 10 * math.log10(2)  # +3.01 dB coherent 2-bay
HARNESS_LOSS_DB = 0.5               # [ESTIMATE: Wilkinson IL ~0.2 dB + jumpers/connectors ~0.3 dB;
                                    #  sibling ledger allows EUR 12 jumper harness]
SPLITTER_430_EUR = 61.40            # WiMo "Power splitters 430 MHz, 2000W" (N-f, 2 or 4 way)
PHASE_LINE_70CM_EUR = 63.00         # WiMo 70 cm phase line for X-Quad
YU1CF_70CM_EUR = 103.00             # WiMo YU1CF 70 cm divider (1/2 or 1/4 lambda, 2-8 out)
YAGI_15EL_EUR = 74.50               # Diamond A-430S15R, 14.8 dBi [CITED funktechnik-bielefeld.de]


def t_e(nf_db):
    """Noise temperature [K] of a device with noise figure nf_db."""
    return 290.0 * (10.0 ** (nf_db / 10.0) - 1.0)


def t_sys(nf_lna_db, gain_lna_db, t_ant=T_ANT_WIDE, nf_rx_db=NF_RX_DB):
    """Friis cascade, masthead LNA ahead of the feedline.

    order: antenna -> LNA -> feedline(+connectors) -> receiver
    """
    t_lna = t_e(nf_lna_db)
    g_lna = 10.0 ** (gain_lna_db / 10.0)
    t_feed = t_e(FEED_LOSS_DB)
    g_feed = 10.0 ** (-FEED_LOSS_DB / 10.0)
    t_rx = t_e(nf_rx_db)
    return t_ant + t_lna + t_feed / g_lna + t_rx / (g_lna * g_feed)


def fspl_db(d_km, f_mhz):
    return 20.0 * math.log10(d_km) + 20.0 * math.log10(f_mhz) + 32.44


def hr(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# ─────────────────────────────────────────────────────────────────────────────
hr("S1  TQP3M9037 vs the 433 MHz downlink  (ADR-079 D5, the disputed band edge)")
# ─────────────────────────────────────────────────────────────────────────────
print("Qorvo TQP3M9037 product page, archived 2023-01-27 (and 2017, and cn.qorvo.com 2026):")
print("  Frequency Min (GHz) = 0.7     Frequency Max (GHz) = 6")
print("  Gain = 20 dB  NF = 0.4 dB  OP1dB = 20 dBm  OIP3 = 35 dBm  5 V / 70 mA  DFN 2x2 mm")
print("  prose: \"The TQP3M9037 covers the 0.7-4 GHz frequency band\"")
print("")
print("Downlink frequency = %.2f MHz = %.4f GHz" % (F_MHZ, F_MHZ / 1000.0))
print("Vendor LF edge     = 0.7 GHz = %.1f MHz" % 700.0)
print("margin      = 700.0 - %.2f = %.2f MHz  --> %.2f MHz BELOW the vendor LF edge"
      % (F_MHZ, 700.0 - F_MHZ, 700.0 - F_MHZ))
print("VERDICT: the owned part's datasheet band (0.7-6 GHz) EXCLUDES the 433 MHz downlink.")
print("         (Operator's module label read 0.1 MHz-6 GHz; the vendor page contradicts it.)")

# ─────────────────────────────────────────────────────────────────────────────
hr("S2  What a 433-specific masthead LNA is worth  (Friis, central T_ant = 200 K)")
# ─────────────────────────────────────────────────────────────────────────────
t_no = t_sys(0.0, 0.0)      # no LNA at all: antenna -> feed -> rx
t_no = T_ANT_WIDE + t_e(FEED_LOSS_DB) + t_e(NF_RX_DB) / (10.0 ** (-FEED_LOSS_DB / 10.0))
print("no LNA:        T_sys = %.1f K" % t_no)
print("formula:       T_sys = T_ant + T_feed + T_rx/G_feed")
print("")
print("%-32s %8s %8s %10s %12s  %s" % ("LNA", "NF dB", "gain dB", "T_sys K", "benefit dB", "price EUR"))
best = None
for name, nf, g, price, band, src in LNAS:
    if nf is None:
        print("%-32s %8s %8s %10s %12s  %8s   (NF not published -> TODO(unverified))"
              % (name, "-", "-", "-", "-", "%.2f" % price))
        continue
    t = t_sys(nf, g)
    b = 10.0 * math.log10(t_no / t)
    pr = "%.2f" % price if price is not None else "n/a (unpriced)"
    print("%-32s %8.2f %8.1f %10.1f %12.2f  %8s" % (name, nf, g, t, b, pr))
    if name.startswith("SSB Electronic LNA ISM"):
        rec = (name, t, b, price)
best = rec
print("")
print("RECOMMENDED = %s" % best[0])
print("  T_sys = %.1f K vs %.1f K no-LNA  ->  +%.2f dB of system noise temperature"
      % (best[1], t_no, best[2]))
print("  price per NEEDED dB (price / benefit) = %.2f / %.2f = %.2f EUR/dB"
      % (best[3], best[2], best[3] / best[2]))
print("  NOTE: this is NOT price/gain (= %.2f EUR/dB) -- an LNA is worth its NF delta, not its gain."
      % (best[3] / 20.0))
print("")
print("Step-up priced: I0JXX PRE432JXX (NF 0.45 dB, 550.00 EUR)")
t_i, b_i = t_sys(0.45, 23.0), 10.0 * math.log10(t_no / t_sys(0.45, 23.0))
print("  T_sys = %.1f K  benefit = %.2f dB" % (t_i, b_i))
print("  marginal over the recommendation: (%.2f - %.2f) / (%.2f - %.2f) = %.0f EUR per extra dB"
      % (550.00, best[3], b_i, best[2], (550.00 - best[3]) / (b_i - best[2])))
print("Cheapest priced wideband: Mini-Circuits ZX60-P103LN+ (NF 0.5 dB headline, 50-3000 MHz)")
t_z = t_sys(0.5, 20.3)
print("  USD 119.47 -> EUR %.2f @ %.2f (ESTIMATE FX) ; benefit = %.2f dB ; %.2f EUR/dB"
      % (119.47 * FX_USD_EUR, FX_USD_EUR, 10.0 * math.log10(t_no / t_z),
         (119.47 * FX_USD_EUR) / (10.0 * math.log10(t_no / t_z))))

# ─────────────────────────────────────────────────────────────────────────────
hr("S3  German amateur limits (AFuV Anlage 1) and the bandwidth that trips them")
# ─────────────────────────────────────────────────────────────────────────────
print("%-16s %7s %10s %10s %10s" % ("band", "status", "Klasse A", "Klasse E", "Klasse N"))
for b, s, a, e, n in AMATEUR:
    print("%-16s %7s %10s %10s %10s" % (b, s, a, e, n))
print("(P = primaerer Funkdienst, S = sekundaerer Funkdienst; AFuV Anlage 1 Fussnote 1)")
print("")
print("Additional operating condition on 430-440 MHz (Anlage 1, Band 18 -> note 7):")
print("  max OCCUPIED bandwidth of an amateur emission = %.1f MHz" % BW_MAX_70CM_MHZ)
print("Additional operating condition on the 13 cm bands (notes 9):")
print("  max occupied bandwidth = %.1f MHz" % BW_MAX_13CM_MHZ)
print("")
print("433 MHz downlink — rate ladder vs the 2 MHz occupied-bandwidth ceiling:")
print("%-16s %10s %14s  %s" % ("mode", "kbps", "BW DSB MHz", "legal on 70 cm (<=2 MHz) ?"))
for label, kbps, bw, sens in FLRC:
    ok = "YES" if bw <= BW_MAX_70CM_MHZ else "NO  -> exceeds AFuV Anlage 1 note 7"
    print("%-16s %10d %14.3f  %s" % (label, kbps, bw, ok))
legal = [r for r in FLRC if r[2] <= BW_MAX_70CM_MHZ]
print("")
print("=> highest German-legal FLRC rate on the 433 downlink: %s (%.3f MHz occupied)"
      % (legal[0][0], legal[0][2]))
print("   2.4 GHz uplink is under note 9 (%.0f MHz) -> every FLRC rate passes there."
      % BW_MAX_13CM_MHZ)

# ─────────────────────────────────────────────────────────────────────────────
hr("S4  What the amateur footing does to the uplink ceiling (the 4-5 km removal)")
# ─────────────────────────────────────────────────────────────────────────────
print("Old (licence-exempt) uplink ceiling: min(20 dBm, 10 dBm/MHz + 10log10 BW)")
for label, kbps, bw, sens in FLRC[:1]:
    ism = min(20.0, 10.0 + 10.0 * math.log10(bw))
    print("  %s: %s -> %.2f dBm EIRP" % (label, "min(20, 10+10log10(%.3f))" % bw, ism))
print("")
print("Now: amateur 2400-2450 MHz, Klasse E = 5 W PEP = +36.99 dBm, Klasse A = 75 W PEP = +48.75 dBm")
print("Ground antenna gain (recommended Sirio SLP-17) = 11.1 dBi; balloon RX gain ~ 0 dBi.")
print("FLRC is constant-envelope (GMSK+FEC), so PEP ~ average power.")
print("")
print("required_EIRP(d) = S + FSPL(d) - G_balloon ;  d_max at EIRP = P_leg + G_ground")
print("%-16s %8s %14s %12s %12s" % ("mode", "S dBm", "req@1km dBm", "d_max Kl.E", "d_max Kl.A"))
for label, kbps, bw, sens in FLRC:
    req1 = sens + fspl_db(1.0, F_UP_MHZ)          # EIRP needed at 1 km, G_balloon = 0
    eirp_e = 10.0 * math.log10(5.0 * 1000.0) + 11.1
    eirp_a = 10.0 * math.log10(75.0 * 1000.0) + 11.1
    d_e = 10.0 ** ((eirp_e - req1) / 20.0)
    d_a = 10.0 ** ((eirp_a - req1) / 20.0)
    print("%-16s %8.1f %14.1f %10.0f km %10.0f km" % (label, sens, req1, d_e, d_a))
print("")
print("=> the ~4-5 km uplink ceiling was an ISM PSD artefact. On the amateur footing the")
print("   same chain reaches hundreds of km on Klasse E and >1000 km on Klasse A.")
print("   (G_balloon = 0 dBi, no fade margin, no implementation loss -- an upper bound.)")

# ─────────────────────────────────────────────────────────────────────────────
hr("S5  The 2-bay combiner: Wilkinson dimensions and cost")
# ─────────────────────────────────────────────────────────────────────────────
lam_m = 300.0 / F_MHZ
print("lambda0 = 300 / %.2f MHz = %.4f m" % (F_MHZ, lam_m))
print("lambda/4 (n=1 free-space) = %.4f m = %.2f cm" % (lam_m / 4.0, lam_m / 4.0 * 100.0))
print("")
print("%-28s %8s %12s" % ("coax", "VF", "lambda/4 cm"))
for nm, vf in [("RG-213 / URM-67", 0.66), ("RG-58", 0.66), ("Airborne 10 / LMR-400", 0.85),
               ("Ecoflex 10", 0.84), ("RG-11 (75 ohm)", 0.66)]:
    print("%-28s %8.2f %12.2f" % (nm, vf, lam_m / 4.0 * vf * 100.0))
print("")
print("Wilkinson: two lambda/4 sections of Z = sqrt(2)*50 = %.1f ohm  (RG-11 is 75 ohm: ~6 %% match error)"
      % (50.0 * math.sqrt(2.0)))
print("           isolation resistor across the two outputs = 2*50 = 100 ohm")
print("")
print("2-bay array gain (coherent)         = 10*log10(2) = +%.2f dB" % ARRAY_GAIN_DB)
print("harness/phasing loss (ESTIMATE)     = -%.2f dB" % HARNESS_LOSS_DB)
print("net                                 = %+.2f dB" % (ARRAY_GAIN_DB - HARNESS_LOSS_DB))
print("")
print("Commercial 2-way 430 MHz splitter (WiMo)      EUR %.2f  (N-f, 2 or 4 way, 2000 W)" % SPLITTER_430_EUR)
print("YU1CF 70 cm divider 1/2 or 1/4 lambda (WiMo)  EUR %.2f  (2-8 outputs)" % YU1CF_70CM_EUR)
print("70 cm phase line for X-Quad (WiMo)            EUR %.2f" % PHASE_LINE_70CM_EUR)
print("2nd Diamond A-430S15R bay                     EUR %.2f" % YAGI_15EL_EUR)
print("")
print("marginal cost of the 2nd bay (antenna + commercial splitter + 0.5 dB harness jumpers EUR 12):")
marg = YAGI_15EL_EUR + SPLITTER_430_EUR + 12.0
print("  %.2f + %.2f + 12.00 = EUR %.2f for %+.2f dB  ->  %.2f EUR/dB"
      % (YAGI_15EL_EUR, SPLITTER_430_EUR, marg, ARRAY_GAIN_DB - HARNESS_LOSS_DB,
         marg / (ARRAY_GAIN_DB - HARNESS_LOSS_DB)))
print("owned XR-613 resistive divider: -6 dB per port -> cancels the +3.01 dB array gain EXACTLY")
print("  (ADR-080).  Do NOT use it as a combiner.")
print("2-bay narrows the stacked-plane beam by 10 % (14 dBi element) to 32 % (3-el element)")
print("  [CITED design/amplifier-hypothesis-check @148578c, S0.1 Q2 row]")

print("\n[done]")
