#!/usr/bin/env python3
"""Reproducible model for the balloon ground-station internet gateway RF front end.

Prints every numeric table quoted in
docs/analysis/rf-shopping-list-and-duplex-architecture.md.

stdlib only (math).  Every input carries its source inline.  Run:
    python3 docs/analysis/rf_shopping_list_model.py
"""

import math

# ----------------------------------------------------------------------------
# Constants / inputs (each with its source)
# ----------------------------------------------------------------------------

# --- bands -------------------------------------------------------------------
F_RX_HZ = 433.92e6      # balloon->ground downlink (ground RECEIVE)  [ADR-034 band split]
F_TX_HZ = 2450e6        # ground->balloon uplink   (ground TRANSMIT)
C = 299792458.0

# --- LR2021 2.4 GHz HF transmit path ----------------------------------------
P_TX_HF_DBM = 12.0      # LR2021 TXOPHF max +12 dBm  [datasheet Table 3-22; 2G4-LINK-BUDGET-ANALYSIS.md]

# --- FLRC 2.4 GHz receiver sensitivity, 1% PER, 31B packet -------------------
# [LR2021 datasheet Rev 2.1, Table 3-13 "FLRC 2.4GHz 1% PER"]
# (rate_kbps, dsb_bw_MHz, effective_kbps, sensitivity_dBm)
FLRC_2G4 = [
    (2600, 2.666, 1.95e3,  -99.0),
    (2080, 2.222, 1.56e3, -100.0),
    (1300, 1.333,  975.0, -101.5),
    (1040, 1.333,  780.0, -102.5),
    ( 650, 0.740,  487.0, -104.0),
    ( 520, 0.571,  390.0, -105.0),
]

# --- 2.4 GHz licence-exempt EIRP ceiling ------------------------------------
# EN 300 328 V2.2.2 / Vfg. 91-2025 57c: 20 dBm EIRP AND 10 dBm/MHz EIRP PSD.
PSD_DBM_PER_MHZ = 10.0
EIRP_ABS_CAP_DBM = 20.0

# --- receiver at the balloon (uplink) ---------------------------------------
G_BALLOON_RX_DBI = 0.0     # ASSUMPTION: bare 2.4 GHz stub on the balloon, TODO(unverified)

# --- LNA (owned) -------------------------------------------------------------
LNA = "TQP3M9037"
LNA_GAIN_DB = 20.0         # 20 dB @1.9 GHz        [Qorvo product page, via Wayback]
LNA_NF_DB = 0.4            # 0.4 dB NF @1.9 GHz
LNA_OP1DB_DBM = 20.0       # OP1dB 20 dBm
LNA_MAX_IN_DBM = 22.0      # "High input power ruggedness, 22 dBm CW"
LNA_BAND_GHZ = (0.7, 6.0)  # Qorvo: "0.7 - 6 GHz operational bandwidth"
# NOTE the operator's brief said 0.1 MHz-6 GHz; the vendor page says 0.7-6 GHz.
LNA_BRIEF_LOW_MHZ = 0.1

# --- isolation budget for the recommended two-antenna duplexer ---------------
# Components of the ground's own 2.4 GHz TX -> own 433 MHz RX leak:
ISO_SPACING_DB = 20.0      # ASSUMPTION: physical separation + pattern + polarisation
ISO_ANTMISMATCH_DB = 3.0   # ASSUMPTION: 433 antenna feed mismatch loss at 2.4 GHz
ISO_RX_BPF_DB = 45.0       # ASSUMPTION: 2-cavity / SAW 433 MHz BPF rejection at 2.4 GHz

# --- circulator reference figures (if one were bought) -----------------------
CIRC_ISO_DB = 20.0         # typical 2.4 GHz coaxial circulator isolation, ~18-22 dB
CIRC_IL_DB = 0.4           # typical insertion loss


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def fspl_db(d_m, f_hz):
    """Free-space path loss: 20*log10(4*pi*d*f/c)."""
    return 20.0 * math.log10(4.0 * math.pi * d_m * f_hz / C)


def eirp_ceiling_dbm(bw_mhz):
    """min(20 dBm, 10 dBm/MHz + 10*log10(BW))."""
    return min(EIRP_ABS_CAP_DBM, PSD_DBM_PER_MHZ + 10.0 * math.log10(bw_mhz))


def rule(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def msg(fmt, *a):
    print(fmt % a)


# ----------------------------------------------------------------------------
# 0. TASK 0 - duplex isolation options
# ----------------------------------------------------------------------------
rule("TASK 0  Duplex architecture: achievable TX->RX isolation per option")
msg("RX band (ground receive) = 433.92 MHz ; TX band (ground transmit) = 2450 MHz")
msg("Band ratio = %.2f  (%.2f octaves)", F_TX_HZ / F_RX_HZ, math.log2(F_TX_HZ / F_RX_HZ))

msg("\n(a) TWO SEPARATE BAND ANTENNAS (recommended)")
msg("    iso = spacing/pattern/polarisation + own-antenna mismatch + RX BPF rejection")
msg("        = %.0f dB + %.0f dB + %.0f dB", ISO_SPACING_DB, ISO_ANTMISMATCH_DB, ISO_RX_BPF_DB)
iso_two_ant = ISO_SPACING_DB + ISO_ANTMISMATCH_DB + ISO_RX_BPF_DB
msg("    total = %.0f dB", iso_two_ant)

msg("\n(b) BAND DIPLEXER (single dual-band feedline)")
iso_diplex = ISO_RX_BPF_DB + 15.0
msg("    iso = RX-BPF rejection (%.0f dB) + diplexer port isolation (~15 dB) = %.0f dB",
    ISO_RX_BPF_DB, iso_diplex)
msg("    (only worth building if ONE antenna must serve both bands)")

msg("\n(c) SINGLE-BAND CIRCULATOR (not applicable - bands differ)")
msg("    iso = %.0f dB  (typical 2.4 GHz coaxial circulator)", CIRC_ISO_DB)
msg("    A ferrite circulator is narrowband (~10-20%%); a 2.4 GHz unit has no")
msg("    433 MHz path, so it cannot route two DIFFERENT bands at all.")

msg("\nVERDICT: two separate band antennas -> %.0f dB isolation, no switching,", iso_two_ant)
msg("         no circulator. Cheaper AND better than (c).")

# ----------------------------------------------------------------------------
# 0b. ground's own 2.4 GHz TX leaking into its own 433 MHz RX front end
# ----------------------------------------------------------------------------
rule("TASK 0b  Ground TX leakage into the ground's own 433 MHz RX (two-antenna case)")
for label, iso in (("nominal", iso_two_ant), ("pessimistic (-20 dB)", iso_two_ant - 20.0)):
    leak = P_TX_HF_DBM - iso
    msg("%-22s iso=%.0f dB -> LNA-input leakage = %+.1f dBm", label, iso, leak)
    msg("   margin to LNA max input  (+%.0f dBm CW) = %.1f dB", LNA_MAX_IN_DBM, LNA_MAX_IN_DBM - leak)
    msg("   margin to LNA P1dB       (+%.0f dBm)    = %.1f dB", LNA_OP1DB_DBM, LNA_OP1DB_DBM - leak)

msg("\nWith a +30 dBm external PA instead of +12 dBm, add 18 dB:")
for label, iso in (("nominal", iso_two_ant),):
    leak30 = 30.0 - iso
    msg("  +30 dBm PA, %s iso=%.0f dB -> leakage %+.1f dBm (still %.1f dB below P1dB)",
        label, iso, leak30, LNA_OP1DB_DBM - leak30)

# ----------------------------------------------------------------------------
# 1. TASK 1 - uplink link budget and PA / attenuator sizing
# ----------------------------------------------------------------------------
rule("TASK 1  Uplink (ground->balloon, 2.4 GHz FLRC) required EIRP vs legal ceiling")
msg("required_EIRP = S + FSPL(d) - G_balloon   [FSPL = 20log10(d_km)+20log10(f_MHz)+32.4478]")
msg("G_balloon = %.0f dBi (assumption)", G_BALLOON_RX_DBI)

ranges_km = [1, 2, 5, 10, 20, 50]
print("\nFSPL 2.4 GHz [dB]:")
for d in ranges_km:
    msg("  %5d km : %.1f dB", d, fspl_db(d * 1e3, F_TX_HZ))

msg("\nRequired EIRP [dBm] per FLRC mode  (legal ceiling in the last column):")
hdr = "  rate  BW      sens   " + "".join("%9s" % ("%dkm" % d) for d in ranges_km)
msg(hdr)
for rate, bw, eff, sens in FLRC_2G4:
    row = "  %4d %5.3f  %6.1f  " % (rate, bw, sens)
    for d in ranges_km:
        req = sens + fspl_db(d * 1e3, F_TX_HZ) - G_BALLOON_RX_DBI
        row += "%9.1f" % req
    msg(row)
    msg("       legal EIRP ceiling at BW=%.3f MHz : %.2f dBm", bw, eirp_ceiling_dbm(bw))

msg("\nMax throughput mode = BR 2600 (BW 2.666 MHz), ceiling %.2f dBm EIRP",
    eirp_ceiling_dbm(2.666))
msg("=> the 2.4 GHz uplink at max FLRC is RANGE-LIMITED by the EIRP cap, not by a PA.")

print("\nMax range [km] at each FLRC mode, G_balloon=%.0f dBi (ceiling == required):" % G_BALLOON_RX_DBI)
for rate, bw, eff, sens in FLRC_2G4:
    ceil = eirp_ceiling_dbm(bw)
    # sens + 20log10(d_km) + 20log10(f_MHz) + 32.4478 - G = ceil
    logd = (ceil + G_BALLOON_RX_DBI - sens - 32.4478 - 20 * math.log10(F_TX_HZ / 1e6)) / 20.0
    d_km = 10 ** logd
    msg("  %4d kbps (eff %7.0f kbps): ceiling %5.2f dBm -> %8.2f km", rate, eff, ceil, d_km)

# --- conducted PA power needed for a given antenna gain ---------------------
rule("TASK 1b  Conducted power at the antenna port to reach the legal EIRP ceiling")
for g_ant in (2.0, 8.0, 11.1, 18.0, 24.0):
    need = eirp_ceiling_dbm(2.666) - g_ant
    msg("  G_ground = %5.1f dBi -> conducted %+6.2f dBm  (LR2021 HF PA gives %+.0f dBm)",
        g_ant, need, P_TX_HF_DBM)
    msg("      => %s by %.1f dB", "ATTENUATE" if need < P_TX_HF_DBM else "AMPLIFY",
        abs(P_TX_HF_DBM - need))

# --- closed-loop gain-control range ----------------------------------------
rule("TASK 1c  Gain-control (dynamic range) the closed loop must cover")
d_near_km, d_far_km = 0.5, 50.0
msg("ratio far/near = %.0f/%.1f km -> %.1f dB of path-loss swing",
    d_far_km, d_near_km, 20 * math.log10(d_far_km / d_near_km))
msg("plus the fixed trim to sit on the legal EIRP ceiling with the chosen antenna")
msg("=> total closed-loop range ~= %.0f-%.0f dB", 20 * math.log10(d_far_km / d_near_km), 45.0)
msg("   (a 0-31.75 dB / 0.25 dB-step DSA plus the radio's own 0.5 dB-step TX power")
msg("    control covers this comfortably)")

# ----------------------------------------------------------------------------
# 2. TASK 2 - circulator isolation-vs-protection arithmetic
# ----------------------------------------------------------------------------
rule("TASK 2  If a circulator IS used: required isolation vs PA power")
msg("Rule: isolation_dB > P_TX_conducted - LNA_max_input")
msg("Compare against BOTH this rugged LNA and a typical low-NF LNA (P1dB ~ -10 dBm):")
LNA_TYPICAL_P1DB = -10.0
for p_tx in (12.0, 20.0, 30.0, 33.0):
    resid = p_tx - CIRC_ISO_DB
    msg("  P_TX=%+5.1f dBm - %.0f dB circulator = %+.1f dBm at the LNA",
        p_tx, CIRC_ISO_DB, resid)
    msg("      TQP3M9037 (P1dB %+.0f dBm): %s   |  typical LNA (P1dB %+.0f dBm): %s",
        LNA_OP1DB_DBM, "OK" if resid < LNA_OP1DB_DBM else "COMPRESSED",
        LNA_TYPICAL_P1DB, "OK" if resid < LNA_TYPICAL_P1DB else "COMPRESSED / at risk")

# ----------------------------------------------------------------------------
# 2b. rate-vs-range neutrality under the EIRP (PSD) cap
# ----------------------------------------------------------------------------
rule("TASK 2b  Why the EIRP PSD cap makes rate adaptation range-neutral here")
msg("The ceiling falls 10*log10(BW) as the rate (and bandwidth) rises, while the")
msg("receiver sensitivity improves only ~1-2 dB per rate step - so max range is")
msg("nearly constant:")
for rate, bw, eff, sens in FLRC_2G4:
    ceil = eirp_ceiling_dbm(bw)
    logd = (ceil + G_BALLOON_RX_DBI - sens - 32.4478 - 20 * math.log10(F_TX_HZ / 1e6)) / 20.0
    msg("  %4d kbps: ceiling %5.2f dBm, sens %6.1f dBm -> %5.2f km", rate, ceil, sens, 10 ** logd)
msg("=> ~4-5 km at ANY FLRC rate.  Raising the balloon's own RX antenna gain")
msg("   (e.g. +5 dBi patch) extends this by 10^(5/20) = %.2fx", 10 ** (5.0 / 20.0))

# ----------------------------------------------------------------------------
# 3. TASK 3 - Red Pitaya reach
# ----------------------------------------------------------------------------
rule("TASK 3  Red Pitaya (STEMlab 125-14) reach vs the bands of interest")
RP_FS_MSPS = 125.0
RP_BW_MHZ = 60.0
msg("ADC/DAC 125 MS/s, 14-bit; analog BW DC-%.0f MHz; Nyquist %.1f MHz",
    RP_BW_MHZ, RP_FS_MSPS / 2.0)
for name, f in (("433.92 MHz downlink", 433.92), ("2450 MHz uplink", 2450.0),
                ("XR-613 upper spec edge", 5000.0)):
    msg("  direct reach of %-24s : %s", name,
        "YES" if f <= RP_BW_MHZ else "NO (%.1fx above DC-%.0f MHz)" % (f / RP_BW_MHZ, RP_BW_MHZ))

rule("Model complete")


if __name__ == "__main__":
    pass
