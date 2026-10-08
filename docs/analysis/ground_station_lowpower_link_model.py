#!/usr/bin/env python3
"""ground_station_lowpower_link_model.py

Reproducible model for the LOW-POWER LR2021 433 MHz ground-station analysis.

Question answered:
  required_G_ground = S_dBm + FSPL_dB - P_tx_dBm - G_balloon_dBi

Run:  python3 docs/analysis/ground_station_lowpower_link_model.py

Every sensitivity is a DATASHEET value; every constant is either a datasheet
value or a stated, cited physical formula. Nothing here is a guess.
"""
import math

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
C_M_S = 299_792_458.0            # speed of light, m/s (CODATA)


def fspl_db(freq_hz: float, dist_m: float) -> float:
    """Free-space path loss, dB."""
    return 20.0 * math.log10(4.0 * math.pi * dist_m * freq_hz / C_M_S)


# ----------------------------------------------------------------------------
# Datasheet sensitivities  (Semtech LR2021/LR2022/LR2012 Final Datasheet)
#   sub-GHz LoRa : Table 3-17  "LoRa Sub-GHz 64B Payload (LR20xx)", 1% PER
#   sub-GHz FLRC : Table 3-12  "FLRC Sub-GHz 1% PER (LR2021)",     1% PER
#   TX power     : Table 3-22  "Transmit Mode Specification"  (TXOPLF typ 22 dBm)
# Local citable copy: docs/lr2021-research/semtech-official/
#                     LR2021_LR2022_LR2012_Datasheet_v2.2.pdf
# (Values are identical in Rev 2.1, docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf.)
# ----------------------------------------------------------------------------
SENS = {
    # Sub-GHz LoRa (LR20xx), 64-byte payload, 1% PER
    "LoRa SF12/BW125 kHz": -141.5,   # Table 3-17, LORA_SUB_125_SF12
    "LoRa SF12/BW62.5 kHz": -143.0,  # Table 3-17, LORA_SUB_62_SF12  <- repo's -143 dBm
    "LoRa SF12/BW31.25 kHz": -147.0, # Table 3-17, LORA_SUB_31_SF12
    # Sub-GHz FLRC (LR2021), 1% PER @ 915 MHz
    "FLRC 2.6 Mbps (BRF 2600k)": -100.5,  # Table 3-12, FLRC_2600_CR05_915_S
    "FLRC 1.04 Mbps (BRF 1040k)": -105.0, # Table 3-12, FLRC_1040_CR05_915_S
    "FLRC 650 kbps (BRF 650k)": -107.0,   # Table 3-12, FLRC_650_CR05_915_S
    "FLRC 520 kbps (BRF 520k)": -108.5,   # Table 3-12, FLRC_520_CR05_915_S
    "FLRC 325 kbps (BRF 325k)": -110.0,   # Table 3-12, FLRC_325_CR05_915_S
}

FREQ_433 = 433.05e6
DIST_650KM = 650_000.0

FSPL_433_650 = fspl_db(FREQ_433, DIST_650KM)

# Ground-gain reference points (from docs/LINK-BUDGET-LICENCE-EXEMPT.md)
G_OMNI = 0.0
G_YAGI_LO, G_YAGI_HI = 12.0, 15.0     # 433 Yagi, licence-exempt budget band
G_DISH_12M = 12.5                     # 1.2 m dish @ 433 MHz, eta=0.60
G_DISH_27M = 20.0                     # ~2.7-3.0 m dish @ 433 MHz


def required_g_ground(sens_dbm, p_tx_dbm, g_balloon=0.0):
    return sens_dbm + FSPL_433_650 - p_tx_dbm - g_balloon


def main():
    print("=" * 78)
    print("FSPL @ 433.05 MHz, 650 km = %.1f dB" % FSPL_433_650)
    print("  (repo committed 300 km figure is 134.7 dB; 650 km adds %.1f dB)"
          % (FSPL_433_650 - fspl_db(FREQ_433, 300_000)))
    print("=" * 78)

    # P_tx cases. +13..+22 dBm = LR2021 sub-GHz PA (TXOPLF typ 22 dBm, 63 x 0.5 dB
    # steps down). +12.15 dBm EIRP = the committed licence-exempt design point
    # (10 mW ERP integral antenna -> EIRP = ERP + 2.15 dB).
    tx_cases = [("+22 dBm (chip max, TXOPLF)", 22.0),
                ("+19 dBm (chip min-max, TXOPLF)", 19.0),
                ("+13 dBm (low-power op)", 13.0),
                ("+12.15 dBm EIRP (10 mW ERP cap)", 12.15)]

    for label, ptx in tx_cases:
        print("\n### P_tx = %s, G_balloon = 0 dBi" % label)
        print("%-30s %10s %14s %18s" % ("modulation", "S (dBm)",
                                        "req G_gnd (dBi)", "margin @12dBi Yagi"))
        for name, s in SENS.items():
            g = required_g_ground(s, ptx)
            margin = G_YAGI_LO - g
            print("%-30s %10.1f %14.1f %18.1f" % (name, s, g, margin))
        print("  -> omni (0 dBi) verdict:  %s"
              % ("CLOSES" if required_g_ground(min(SENS.values()), ptx) <= 0
                 else "FAILS (needs gain)"))
    print()
    print("=" * 78)
    print("Dish gain @ 433 MHz  G = 10 log10(eta (pi D / lambda)^2), eta=0.60")
    lam = C_M_S / FREQ_433
    for D in (1.2, 1.5, 2.7, 3.0):
        g = 10 * math.log10(0.60 * (math.pi * D / lam) ** 2)
        print("  D = %.1f m -> %.1f dBi" % (D, g))
    print()
    print("Feed illumination half-angle  theta = 2 atan(1/(4 f/D))")
    for fd in (0.25, 0.35, 0.4, 0.5, 0.6, 0.7):
        print("  f/D = %.2f -> theta = %.1f deg"
              % (fd, 2 * math.degrees(math.atan(1.0 / (4.0 * fd)))))
    print()
    print("lambda/4 defocus-as-1dB-tolerance (lambda @ band):")
    for f, nm in ((433.05e6, "433 MHz"), (2.4e9, "2.4 GHz")):
        print("  %s: lambda = %.1f mm, lambda/4 = %.1f mm"
              % (nm, C_M_S / f * 1e3, C_M_S / f * 1e3 / 4))
    print()
    print("Mesh/grid hole rule  lambda/10 (largest hole ~ lambda/10):")
    for f, nm in ((433.05e6, "433 MHz"), (2.4e9, "2.4 GHz")):
        print("  %s: lambda/10 = %.1f mm" % (nm, C_M_S / f * 1e3 / 10))


if __name__ == "__main__":
    main()
