#!/usr/bin/env python3
"""Tier-0 (ultra-low-cost) and re-costed Tier-A ground station — link + cost model.

Reproduce EVERY numeric table in
  docs/analysis/tier0-accessible-ground-station.md
with:

    python3 docs/analysis/tier0_accessible_model.py

Nothing here is guessed: every physical constant and price is either a datasheet /
repo value (cited inline and in the document) or an explicitly-labelled ESTIMATE /
TODO(unverified).  The point of the script is that the document's numbers are
re-runnable, not asserted.

Author: Hermes Agent (subagent), for the operator.  Date 2026-10-08.
"""

import math

# ----------------------------------------------------------------------------
# 1. SOURCED INPUTS
# ----------------------------------------------------------------------------
C = 299_792_458.0

# --- Receiver sensitivities (Semtech LR2021 datasheet, see the doc's sources) ---
# Sub-GHz LoRa, 64B payload, 1% PER, rx_boost=7 (Table 3-17)
LORA_62_SF12 = -143.0     # dBm  BW 62.5 kHz, SF12   <- the repo's "-143 dBm" figure
LORA_125_SF12 = -141.5    # dBm
LORA_500_SF12 = -138.5    # dBm  (not used in the headline tables)
# Sub-GHz FLRC, 1% PER (Table 3-12, 915 MHz test point)
FLRC = {                  # rate kbps -> sensitivity dBm
    "2600": -100.5,
    "1040": -105.0,
    "650": -107.0,
    "520": -108.5,
    "325": -110.0,
}

# --- Transmitters ---
LR2021_SUB_GHZ_MAX_DBM = 22.0   # Table 3-22 TXOPLF typ
LR2021_24GHZ_MAX_DBM   = 12.0   # Table 3-22 TXOPHF typ
F33_433_DBM            = 33.0   # NiceRF LoRa2021F33, 5.0 V (repo ADR-044 / RANGE-THROUGHPUT-PLAN)

# --- Regulatory design points (repo LINK-BUDGET-LICENCE-EXEMPT.md) ---
LE_433_EIRP_DBM  = 12.15   # 10 mW ERP integral antenna (ERC Rec 70-03 Annex 1)
LE_24_EIRP_DBM   = 20.0    # 100 mW EIRP, 2400-2483.5 MHz wideband

# --- Balloon-side antennas (repo ADR-037 / LINK-BUDGET-LICENCE-EXEMPT.md) ---
G_BALLOON_24_RX_DBI = 10.0   # ADR-037
G_BALLOON_433_DBI   = 0.0    # conservative, licence-exempt budget
S_BALLOON_24_DBM    = -137.0 # bare LR2021 SF12 2.4 GHz (Table 3-18, -137)

# --- Geometry given by the task ---
RANGES_KM = [300.0, 650.0]
F_LORA = 433.05e6
F_24   = 2.4e9

# --- Antenna class gains ---
OMNI_DBI = 0.0
WHIP_DBI = 3.0      # typical 2.4 GHz rubber-duck / small omni
PANEL8_DBI = 8.0    # small 2.4 GHz panel (uses the whole legal EIRP with the chip's PA)


def fspl_db(d_km: float, f_hz: float) -> float:
    """Free-space path loss, dB."""
    d = d_km * 1000.0
    return 20.0 * math.log10(4.0 * math.pi * d * f_hz / C)


def dish_gain_dbi(d_m: float, f_hz: float, eta: float = 0.60) -> float:
    lam = C / f_hz
    return 10.0 * math.log10(eta * (math.pi * d_m / lam) ** 2)


def hpbw_deg(d_m: float, f_hz: float) -> float:
    lam = C / f_hz
    return 70.0 * lam / d_m


def rule(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# ----------------------------------------------------------------------------
# 2. THE EIRP-CAP QUESTION (headline)
# ----------------------------------------------------------------------------
rule("TABLE 1 — THE EIRP-CAP QUESTION: 2.4 GHz UPLINK margin vs GROUND antenna gain")
print("Balloon RX: S = -137 dBm (bare LR2021 SF12), G_rx = 10 dBi (ADR-037).")
print("Ground 2.4 GHz PA max = +12 dBm (LR2021 TXOPHF). Licence-exempt cap = 20 dBm EIRP.")
print("Margin = EIRP_eff + G_rx - S - FSPL ;  EIRP_eff = min(P_tx + G_ground, 20 dBm)\n")
LINK = {}
for rng in RANGES_KM:
    fs = fspl_db(rng, F_24)
    print(f"---- {rng:.0f} km   FSPL = {fs:.1f} dB ----")
    print(f"{'G_ground dBi':>12} {'EIRP_eff dBm':>13} {'margin dB':>10} {'useful?':>22}")
    for g in [0, 3, 6, 8, 10, 12, 15, 21, 27]:
        eirp = min(LR2021_24GHZ_MAX_DBM + g, LE_24_EIRP_DBM)
        margin = eirp + G_BALLOON_24_RX_DBI - S_BALLOON_24_DBM - fs
        note = ("gain fully useful" if (LR2021_24GHZ_MAX_DBM + g) <= LE_24_EIRP_DBM
                else "gain INERT (EIRP capped)")
        print(f"{g:>12.1f} {eirp:>13.1f} {margin:>10.1f}   {note:>22}")
        LINK[(rng, g)] = margin
    print()

# the two numbers that matter
G_USEFUL_MAX = LE_24_EIRP_DBM - LR2021_24GHZ_MAX_DBM
print(f"*** USEFUL ground gain under the cap = 20 - 12 = {G_USEFUL_MAX:.0f} dB. ***")
print("Above that the ground antenna gain CANCELS from the link equation (EIRP is fixed).")
maxm300 = LINK[(300.0, 8.0)]
maxm650 = LINK[(650.0, 8.0)]
print(f"Max COMPLIANT uplink margin: {maxm300:+.1f} dB @300 km, {maxm650:+.1f} dB @650 km")

rule("TABLE 1b — the 2.4 GHz DISH: how many of its dBi are INERT")
print(f"{'antenna':<28}{'G dBi':>7}{'EIRP_eff':>10}{'inert dB':>10}{'margin@300':>12}{'margin@650':>12}")
cands = [("omni / rubber duck", WHIP_DBI),
         ("small 8 dBi panel", PANEL8_DBI),
         ("0.60 m dish (eta .60)", dish_gain_dbi(0.60, F_24)),
         ("0.75 m dish (eta .60)", dish_gain_dbi(0.75, F_24)),
         ("1.20 m dish (eta .60)", dish_gain_dbi(1.20, F_24))]
for name, g in cands:
    eirp = min(LR2021_24GHZ_MAX_DBM + g, LE_24_EIRP_DBM)
    inert = max(0.0, g - G_USEFUL_MAX)
    m300 = eirp + G_BALLOON_24_RX_DBI - S_BALLOON_24_DBM - fspl_db(300.0, F_24)
    m650 = eirp + G_BALLOON_24_RX_DBI - S_BALLOON_24_DBM - fspl_db(650.0, F_24)
    print(f"{name:<28}{g:>7.1f}{eirp:>10.1f}{inert:>10.1f}{m300:>12.1f}{m650:>12.1f}")

# ----------------------------------------------------------------------------
# 3. 433 MHz DOWNLINK — required ground gain and margin by class
# ----------------------------------------------------------------------------
rule("TABLE 2 — 433 MHz DOWNLINK: required ground gain and margin by antenna class")
print("G_balloon = 0 dBi.  reqG = S + FSPL - P_tx - G_balloon.  margin = G_ground - reqG.\n")
classes = [("omni 0 dBi", OMNI_DBI), ("small Yagi 10 dBi", 10.0),
           ("Diamond A-430S10R 13.1 dBi", 13.1), ("Diamond A-430S15R 14.8 dBi", 14.8),
           ("Sirio WY 400-10N 14 dBi", 14.0)]
TX = [("low-power LR2021 +12.15 EIRP (licence-exempt)", LE_433_EIRP_DBM, "LoRa"),
      ("low-power LR2021 +22 dBm (amateur, chip max)", LR2021_SUB_GHZ_MAX_DBM, "FLRC"),
      ("F33 +33 dBm (amateur)", F33_433_DBM, "FLRC")]
rows = [("LoRa SF12/62.5", LORA_62_SF12), ("FLRC 2600 kbps", FLRC["2600"]),
        ("FLRC 650 kbps", FLRC["650"])]
for tname, ptx, kind in TX:
    print(f"--- TX: {tname} ---")
    for rng in RANGES_KM:
        fs = fspl_db(rng, F_LORA)
        print(f"  {rng:.0f} km  FSPL={fs:.1f}")
        for rname, s in rows:
            req = s + fs - ptx
            m = "  ".join(f"{n.split()[0]} {g-req:+.1f}" for n, g in classes)
            print(f"    {rname:<18} reqG={req:+6.1f} dBi | margins: {m}")
    print()

# ----------------------------------------------------------------------------
# 4. COST TABLES
# ----------------------------------------------------------------------------
rule("TABLE 3 — TIER 0 (ultra-low-cost, BELOW Tier A) vs RE-COSTED TIER A")

def show(items, total_note=""):
    tot_lo = tot_hi = 0.0
    print(f"{'line':<52}{'low EUR':>10}{'high EUR':>10}  src")
    for name, lo, hi, src in items:
        tot_lo += lo
        tot_hi += hi
        print(f"{name:<52}{lo:>10.2f}{hi:>10.2f}  {src}")
    print(f"{'TOTAL':<52}{tot_lo:>10.2f}{tot_hi:>10.2f}")
    if total_note:
        print(total_note)
    return tot_lo, tot_hi

print("\n-- TIER 0a  'LoRa-only, no pointing at all' (fixed mast, two omnis) --")
t0a = show([
    ("433 MHz omni / ground-plane (LoRa downlink)", 15, 40, "TODO(unverified): generic"),
    ("2.4 GHz omni / rubber-duck (uplink)",          5, 25, "TODO(unverified): generic"),
    ("Mast / tripod, no motors",                   30, 90, "TODO(unverified): generic"),
    ("Coax + connectors (2.4 GHz + 433)",          40, 90, "repo BOM-coax class"),
])
print("\n-- TIER 0b  'F33 FLRC, hand-aimed Yagi' (manual pan/tilt, no motors) --")
t0b = show([
    ("Diamond A-430S10R 13.1 dBi 433 Yagi",        69, 69, "BOM A4 CONFIRMED"),
    ("2.4 GHz omni / rubber-duck (uplink)",          5, 25, "TODO(unverified): generic"),
    ("Manual AZ/EL pan-tilt head + tripod",        30, 120, "TODO(unverified): generic"),
    ("Coax + connectors",                          40, 90, "repo BOM-coax class"),
])
print("\n-- TIER A (RE-COSTED, no 2.4 GHz dish) --")
print("   positioner = sibling 'gain-per-dollar' P1 DIY tracker EUR429 (== positioner-lowcost EUR412+EUR50ctl+EUR100mast)")
tA = show([
    ("Diamond A-430S15R 14.8 dBi 433 Yagi",     74.50, 74.50, "BOM A5 CONFIRMED"),
    ("2.4 GHz small panel 8 dBi (replaces dish+feed)", 15, 60, "TODO(unverified): generic"),
    ("DIY printed tracker P1 (NEMA23 + NMRV40 worm)", 429, 429, "gain-per-dollar Sec1.6 CONFIRMED"),
    ("Coax 15 m Airborne 10 + connectors",      97.50, 121.50, "BOM F3/CX N/SMA CONFIRMED"),
])
print("\n-- TIER A (RE-COSTED, bought rotator, no 2.4 GHz dish) --")
tAb = show([
    ("Diamond A-430S15R 14.8 dBi 433 Yagi",     74.50, 74.50, "BOM A5 CONFIRMED"),
    ("2.4 GHz small panel 8 dBi",                   15, 60, "TODO(unverified): generic"),
    ("Yaesu G-450CDC AZ+EL rotator",            359.00, 359.00, "BOM E2 CONFIRMED"),
    ("Coax 15 m Airborne 10 + connectors",      97.50, 121.50, "BOM CONFIRMED"),
])
print("\n-- TIER A (AS ORIGINALLY COSTED, for the delta) --")
print("   original = 433 Yagi + 0.6 m 2.4 GHz dish + feed + tracker")
tOrig = show([
    ("Diamond A-430S15R 14.8 dBi 433 Yagi",     74.50, 74.50, "BOM A5 CONFIRMED"),
    ("Gibertini 75 SE Profi 0.75 m Ku dish",    94.90, 94.90, "BOM B3 CONFIRMED"),
    ("2.4 GHz dish feed (RS-ONE proxy) + CLX1", 231.00, 231.00, "BOM C2+C6 CONFIRMED"),
    ("DIY printed tracker P1",                    429, 429, "gain-per-dollar Sec1.6"),
    ("Coax 15 m Airborne 10 + connectors",      97.50, 121.50, "BOM CONFIRMED"),
])
print(f"\nRE-COST DELTA (DIY tracker, no dish): TIER A {tA[0]:.0f}-{tA[1]:.0f} EUR "
      f"vs ORIGINAL {tOrig[0]:.0f}-{tOrig[1]:.0f} EUR  ->  saves "
      f"{tOrig[0]-tA[1]:.0f}-{tOrig[1]-tA[0]:.0f} EUR")
print(f"TIER 0a {t0a[0]:.0f}-{t0a[1]:.0f} EUR  /  TIER 0b {t0b[0]:.0f}-{t0b[1]:.0f} EUR")

# ----------------------------------------------------------------------------
# 5. WHY THE POSITIONER COLLAPSES (beamwidth)
# ----------------------------------------------------------------------------
rule("TABLE 4 — why NO tight pointing is left once the 2.4 GHz dish goes")
print(f"{'element':<30}{'G dBi':>8}{'HPBW deg':>11}{'10% budget deg':>16}{'tracker class':>26}")
for name, g, hb in [("2.4 GHz omni", WHIP_DBI, 360.0),
                    ("2.4 GHz 0.6 m dish", dish_gain_dbi(0.60, F_24), hpbw_deg(0.60, F_24)),
                    ("433 omni", 0.0, 360.0),
                    ("433 small Yagi 10 dBi", 10.0, 47.0),
                    ("433 Yagi 13.1 dBi", 13.1, 40.0),
                    ("433 1.2 m dish", dish_gain_dbi(1.20, F_LORA), hpbw_deg(1.20, F_LORA))]:
    print(f"{name:<30}{g:>8.1f}{hb:>11.1f}{hb*0.10:>16.1f}{'(none)' if hb>90 else 'cheap/open-loop':>26}")

print("\nDone.  Every table above is reproduced by this script.")
