#!/usr/bin/env python3
"""Regulatory duty-cycle / airtime model for the v9 balloon radio links.

Companion to docs/analysis/radio-legal-power-limits.md. This script computes
NOTHING that is not already printed in that document; it exists so every
number in the document's tables can be reproduced.

LoRa air-time formula: Semtech AN1200.13 (SX127x modem; also valid for
SX1280 / LR2021 LoRa). Same formula and same constants as the in-repo
docs/airtime_calc.py -- deliberately duplicated rather than imported so that
this analysis does not depend on a bench-sweep script.

    T_sym           = 2^SF / BW
    PayloadSymbNb   = 8 + ceil( max(8*PL - 4*SF + 28 + 16*CRC, 0)
                               / (4*(SF - 2*DE)) ) * CR_denom
    T_packet        = (preamble + 4.25 + PayloadSymbNb) * T_sym

    CRC = 1 (hardware CRC on), preamble = 8 symbols, CR_denom = 5 for CR 4/5,
    DE  = 1 when T_sym > 16 ms (low-data-rate-optimise)

Sub-GHz LoRa bandwidths on the LR2021 (see docs/bw-code-table.md):
    BW_62 = 62.5 kHz (code 0x03), BW_125 = 125 kHz (0x04),
    BW_250 = 250 kHz (0x05).  The narrow codes BW_7 (7.8125 kHz, 0x00),
    BW_10 (10.417 kHz, 0x08), BW_15 (15.625 kHz, 0x01), BW_20 (20.833 kHz,
    0x09) also exist and are the ones that matter for Vfg. 91/2025 entry 45c
    (Bandbreite <= 25 kHz).

Duty cycle: Vfg. 91/2025 defines "Arbeitszyklus" as sum(T_on)/T_obs with
T_obs a continuous one hour unless the tables say otherwise.  The CEPT
equivalent (ERC/REC 70-03 "Duty cycle categories") is the same definition
against a one hour period.  Both are quoted in the analysis document.

Usage:  python3 docs/analysis/radio_power_limits_model.py
"""

import math

# ---------------------------------------------------------------- air time ---


def lora_airtime_ms(pl, sf, bw_hz, cr_param=1, preamble=8, crc=True):
    """LoRa on-air time in ms. Formula: Semtech AN1200.13."""
    t_sym = (2 ** sf) / bw_hz                      # seconds
    de = 1 if t_sym > 0.016 else 0                 # low data rate optimise
    crc_val = 1 if crc else 0
    cr_denom = cr_param + 4                        # CR 4/5 -> 5
    numerator = 8 * pl - 4 * sf + 28 + 16 * crc_val
    if numerator < 0:
        numerator = 0
    payload_symb = 8 + math.ceil(numerator / (4 * (sf - 2 * de))) * cr_denom
    t_packet = (preamble + 4.25 + payload_symb) * t_sym
    return t_packet * 1000.0, de


SF_RANGE = (7, 8, 9, 10, 11, 12)
BW_KHZ = (62, 125, 250)          # driver Hz constants 62 500 / 125 000 / 250 000
PAYLOADS = (32, 64, 255)

# The design's own baseline 433 MHz downlink parameters (ADR-041 quotes
# tools/link_budget.py --freq 433 --sf 12 --bw 125).
BASELINE = dict(sf=12, bw_khz=125, pl=255)

# Duty-cycle ceiling of Vfg. 91/2025 entry 44b / CEPT ERC/REC 70-03 Annex 1
# entry f (both "< 10 %").
DUTY_CAP_PCT = 10.0
# Default observation period: one continuous hour (Vfg. 91/2025 Arbeitszyklus
# definition; ERC/REC 70-03 "Duty cycle categories").
T_OBS_S = 3600.0

LINK_BUDGET = [
    # (label, TX dBm, balloon/ground antenna dBi, FSPL dB, sensitivity dBm)
    ("433 downlink, 10 mW ERP, ground 12 dBi Yagi, tool sens",
     10.0, 12.0, 134.7, -137.0),
    ("433 downlink, 10 mW ERP, ground 12 dBi Yagi, module -143",
     10.0, 12.0, 134.7, -143.0),
    ("433 downlink, 10 mW ERP, ground 15 dBi Yagi, tool sens",
     10.0, 15.0, 134.7, -137.0),
    ("2.4G uplink, 100 mW EIRP, balloon 10 dBi, F33 LNA (-136)",
     20.0, 10.0, 149.6, -136.0),
    ("2.4G uplink, 100 mW EIRP, balloon 10 dBi, no LNA (-124)",
     20.0, 10.0, 149.6, -124.0),
    ("2.4G uplink, 100 mW EIRP, balloon  6 dBi, F33 LNA (-136)",
     20.0, 6.0, 149.6, -136.0),
    ("2.4G uplink, 100 mW EIRP, balloon  6 dBi, no LNA (-124)",
     20.0, 6.0, 149.6, -124.0),
]


def hdr(text):
    print()
    print("=" * 78)
    print(text)
    print("=" * 78)


def main():
    hdr("1. Sub-GHz LoRa air time (CR 4/5, 8-symbol preamble, CRC on)")
    print(f"{'SF/BW':<12}{'32 B':>10}{'64 B':>10}{'255 B':>10}{'LDRO':>7}")
    airtime = {}
    for sf in SF_RANGE:
        for khz in BW_KHZ:
            row = []
            de = 0
            for pl in PAYLOADS:
                t, de = lora_airtime_ms(pl, sf, khz * 1000)
                row.append(t)
            airtime[(sf, khz)] = row
            print(f"SF{sf}/BW{khz:<7}{row[0]:>9.0f}ms{row[1]:>9.0f}ms"
                  f"{row[2]:>9.0f}ms{'yes' if de else 'no':>7}")

    hdr("2. Duty cycle vs beacon interval, 255 B packet, T_obs = 1 h, cap 10 %")
    print("   (interval = time from the START of one packet to the START of the next)")
    print(f"{'SF/BW':<12}{'T_air':>9}{'min interval':>14}{'30s':>9}{'60s':>9}"
          f"{'90s':>9}{'120s':>9}{'300s':>9}")
    for sf in SF_RANGE:
        for khz in BW_KHZ:
            t = airtime[(sf, khz)][2] / 1000.0                  # seconds
            min_int = t / (DUTY_CAP_PCT / 100.0)                # seconds
            duty = lambda iv: t / iv * 100.0
            cells = "".join(
                f"{duty(iv):>8.2f}%" + (" " if duty(iv) <= DUTY_CAP_PCT else "!")
                for iv in (30, 60, 90, 120, 300))
            print(f"SF{sf}/BW{khz:<7}{t:>8.2f}s{min_int:>12.1f}s  {cells}")

    hdr("3. The design's own baseline 433 config (ADR-041: SF12 / BW125 / 255 B)")
    t, de = lora_airtime_ms(BASELINE["pl"], BASELINE["sf"], BASELINE["bw_khz"] * 1000)
    print(f"  LoRa SF12 / BW125 kHz / CR 4/5 / 255 B -> T_air = {t/1000.0:.2f} s "
          f"(LDRO {'on' if de else 'off'})")
    print(f"  Minimum interval that satisfies <= 10 % : {t/1000.0/0.10:.1f} s")
    for iv in (60, 90, 120, 300, 600):
        d = t / 1000.0 / iv * 100.0
        print(f"    1 packet / {iv:>3} s -> duty {d:5.2f} %  "
              f"{'OK' if d <= DUTY_CAP_PCT else 'OVER 10 % -> NOT entry 44b'}")
    print("  Packets per hour at the 10 % ceiling: "
          f"{int(T_OBS_S / (t/1000.0/0.10))}")

    hdr("4. Entry 45c arithmetic (Bandbreite <= 25 kHz, Arbeitszyklus <= 100 %)")
    print("  LR2021 LoRa bandwidth codes at or below 25 kHz "
          "(docs/bw-code-table.md):")
    for name, hz in (("BW_7", 7812), ("BW_10", 10417),
                     ("BW_15", 15625), ("BW_20", 20833)):
        print(f"    {name:<6} {hz/1000.0:8.4f} kHz  -> {'<= 25 kHz: OK' if hz <= 25000 else 'no'}")
    print("  Airtime at SF12/BW20.833 kHz, 255 B (for the throughput trade):")
    t20, _ = lora_airtime_ms(255, 12, 20833)
    print(f"    T_air = {t20/1000.0:.1f} s  (vs {t/1000.0:.1f} s at 125 kHz, "
          f"x{t20/t:.1f} airtime)")

    hdr("5. Link-budget delta for the fallback power (10 dB cut on each link)")
    print(f"{'scenario':<62}{'RX dBm':>9}{'margin':>9}{'+fallback':>11}")
    for label, tx_dbm, ant_dbi, fspl, sens in LINK_BUDGET:
        rx = tx_dbm + ant_dbi - fspl
        print(f"{label:<62}{rx:>9.1f}{rx - sens:>9.1f}"
              f"{(rx - 10.0) - sens:>11.1f}")
    print()
    print("  Range penalty of a 10 dB cut (free space, loss ~ 20*log10(d)):")
    print(f"    distance factor = 10^(-10/20) = {10 ** (-10 / 20):.3f}  "
          f"-> 300 km becomes {300 * 10 ** (-10 / 20):.0f} km at equal margin")
    print("  Rate penalty of a 10 dB cut (tool LoRa table, ~2.5-3 dB per SF step):")
    print("    SF12(-137) -> SF9(-129) = 8x airtime = ~8x lower rate at equal range")


if __name__ == "__main__":
    main()
