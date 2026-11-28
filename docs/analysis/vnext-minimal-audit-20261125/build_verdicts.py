#!/usr/bin/env python3
"""G4 keep/optional/remove verdict table for the vnext MINIMAL variant (ADR-089).

Every verdict cites its evidence (ADR, netlist, measurement). Coverage rule from the
plan (Phase 3 exit criteria): every reference in the FULL-variant netlist (101 refs)
gets a verdict; anything without a verdict is a defect, not an omission. The script
FAILS if a netlist ref has no verdict and if a verdict names no existing ref.

This is a DOC tool: it reads the committed netlist, applies the verdict map below,
emits verdicts.json + a markdown table. No board is touched.
"""
import json
import re
import sys

REPO = "/home/c08r4d0r/worktrees/vnext-minimal-docs"
NET = f"{REPO}/tracker/hardware/schematics/flight_board/v11_flight.net"

# ref -> (verdict, reason). Verdicts: KEEP / OPTIONAL / REMOVE / REPLACE.
# REPLACE = removed as such, superseded by a named new feature (pogo pads).
V = {
    # -- radios per ADR-089 S1 ------------------------------------------------
    "U2": ("KEEP", "F33 TX, the transmitter (ADR-089 S1). Part identity NOT settled: NiceRF page "
                  "names LoRa2021F33-2G4; LCSC C53243927 reads LoRa1121F33-2G4-433MHz -- competing "
                  "evidence recorded, pin verification pending (gate G2)."),
    "U3": ("KEEP", "the ONE low-power LR2021 RX (ADR-089 S1). Footprint pin-verification pending "
                  "(gate G2); shopping list records the operator's small module does NOT fit U3 "
                  "or U_C as a drop-in (handfit shopping list row 14)."),
    "U_C": ("REMOVE", "redundant second LR2021 RX removed on MINIMAL (ADR-089 S1; ADR-145 MOOT on "
                     "MINIMAL). Its 4 control nets have no MCU endpoint (ADR-145). Site stays "
                     "valid on non-MINIMAL variants."),
    "U_LORA1280": ("REMOVE", "ranging site D removed on MINIMAL (ADR-089 S1); ADR-138/139 gates "
                            "bind only where site D exists. Netlist-vs-board divergence "
                            "(U_LORA1280 vs U_E28) mooted by removal for THIS variant."),
    # -- programming interface ------------------------------------------------
    "J_PROG": ("REPLACE", "2.54 mm 6-pin header removed on MINIMAL; replaced by functional pogo "
                         "pads exposing the SAME six signals + EN RC (ADR-089 S1, ADR-121 amended "
                         "in part; pogo header is the CANDIDATE implementation, its part "
                         "selection pending gate G2 Phase 1.3)."),
    # -- release safety (retained until evidence permits removal, ADR-089 S1) --
    "U_CUT1": ("KEEP", "cut-driver latch, channel 1 (release safety, ADR-129; netlist value "
                      "SN74LVC1G373DBVR; stage-1 board carries a placeholder footprint part "
                      "TODO(unverified))"),
    "U_CUT2": ("KEEP", "cut-driver latch, channel 2 (as U_CUT1)"),
    "U_CUT3": ("KEEP", "cut-driver latch, channel 3 (as U_CUT1)"),
    "U_CUT4": ("KEEP", "cut-driver latch, channel 4 (as U_CUT1)"),
    "Q_CUT1": ("KEEP", "cut FET AO3400A, channel 1 (release safety, V11-CUT-CHANNELS.md)"),
    "Q_CUT2": ("KEEP", "cut FET, channel 2 (as Q_CUT1)"),
    "Q_CUT3": ("KEEP", "cut FET, channel 3 (as Q_CUT1)"),
    "Q_CUT4": ("KEEP", "cut FET, channel 4 (as Q_CUT1)"),
    "R_G1": ("KEEP", "cut FET gate resistor, ch 1 (V11-CUT-CHANNELS.md gate chain)"),
    "R_G2": ("KEEP", "cut FET gate resistor, ch 2"),
    "R_G3": ("KEEP", "cut FET gate resistor, ch 3"),
    "R_G4": ("KEEP", "cut FET gate resistor, ch 4"),
    "R_SH1": ("KEEP", "0.1 ohm 2512 Kelvin shunt, ch 1 (V11-CUT-CHANNELS.md; sense error budget)"),
    "R_SH2": ("KEEP", "Kelvin shunt, ch 2 (as R_SH1)"),
    "R_SH3": ("KEEP", "Kelvin shunt, ch 3 (as R_SH1)"),
    "R_SH4": ("KEEP", "Kelvin shunt, ch 4 (as R_SH1)"),
    "R_SNS1": ("KEEP", "shunt sense tap, ch 1 (V11-CUT-CHANNELS.md ADC chain)"),
    "R_SNS2": ("KEEP", "shunt sense tap, ch 2"),
    "R_SNS3": ("KEEP", "shunt sense tap, ch 3"),
    "R_SNS4": ("KEEP", "shunt sense tap, ch 4"),
    "R_SNSA1": ("KEEP", "sense divider 300k, ch 1 (1/4 divider per V11-CUT-CHANNELS.md)"),
    "R_SNSA2": ("KEEP", "sense divider 300k, ch 2"),
    "R_SNSA3": ("KEEP", "sense divider 300k, ch 3"),
    "R_SNSA4": ("KEEP", "sense divider 300k, ch 4"),
    "R_SNSB1": ("KEEP", "sense divider 100k, ch 1"),
    "R_SNSB2": ("KEEP", "sense divider 100k, ch 2"),
    "R_SNSB3": ("KEEP", "sense divider 100k, ch 3"),
    "R_SNSB4": ("KEEP", "sense divider 100k, ch 4"),
    "C_SNS1": ("KEEP", "sense filter cap, ch 1"),
    "C_SNS2": ("KEEP", "sense filter cap, ch 2"),
    "C_SNS3": ("KEEP", "sense filter cap, ch 3"),
    "C_SNS4": ("KEEP", "sense filter cap, ch 4"),
    "R_FPD": ("KEEP", "100k pulldown holding all four cut-FET gates low via /CUT_FIRE "
                     "(measured from netlist: R_FPD.1 on /CUT_FIRE with R_GPD1-4, .2 on GND) -- "
                     "release-safety default-off"),
    "R_GPD1": ("KEEP", "gate pulldown, ch 1 (netlist: .2 on GND with R_FPD)"),
    "R_GPD2": ("KEEP", "gate pulldown, ch 2"),
    "R_GPD3": ("KEEP", "gate pulldown, ch 3"),
    "R_GPD4": ("KEEP", "gate pulldown, ch 4"),
    "R_PROT1": ("KEEP", "cut-loop protection resistor, ch 1 (netlist cut channel chain)"),
    "R_PROT2": ("KEEP", "cut-loop protection resistor, ch 2"),
    "R_PROT3": ("KEEP", "cut-loop protection resistor, ch 3"),
    "R_PROT4": ("KEEP", "cut-loop protection resistor, ch 4"),
    "J_HT1": ("KEEP", "cut loop 1 header (two-conductor /VSCAP-heater-drain loop, "
                     "V11-CUT-CHANNELS.md)"),
    "J_HT2": ("KEEP", "cut loop 2 header (as J_HT1)"),
    "J_HT3": ("KEEP", "cut loop 3 header (as J_HT1)"),
    "J_HT4": ("KEEP", "cut loop 4 header (as J_HT1)"),
    "U_DEC": ("KEEP", "SN74LVC1G139 one-hot decoder serialising the four latch /OE lines -- "
                     "hardware guarantee no two FETs conduct (V11-CUT-CHANNELS.md; release "
                     "safety)"),
    "R_A0PD": ("KEEP", "decoder address pulldown A0 (netlist: on /CUT_FIRE + GND; keeps decoder "
                      "address defined at reset)"),
    "R_A1PD": ("KEEP", "decoder address pulldown A1 (as R_A0PD)"),
    # -- cut sense via I2C ADC (ADR-148) ----------------------------------------
    "U_ADC1": ("KEEP", "ADS1115 #1: /SCAP_ADC + cut sense (plan Phase 0.2: both ADS1115 stay; "
                      "ADR-148)"),
    "U_ADC2": ("KEEP", "ADS1115 #2: solar dividers + cut sense (as U_ADC1)"),
    "C_ADC1": ("KEEP", "ADS1115 decoupling/filter"),
    "C_ADC2": ("KEEP", "ADS1115 decoupling/filter"),
    # -- GPS / tracking (retained until evidence permits removal) ----------------
    "U5": ("KEEP", "MAX-M10S GNSS retained on MINIMAL (ADR-089 S1); actual installed part on the "
                  "operator's board is an unidentified 4-pin breakout -- needs identification "
                  "(handfit list row 16; not established as the bare MAX-M10S footprint)"),
    "R_PU1": ("KEEP", "4k7 I2C SCL pullup (netlist: R_PU1.2 on /I2C_SCL with U1/U6/U_ADC1/2)"),
    "R_PU2": ("KEEP", "4k7 I2C SDA pullup (netlist: R_PU2.2 on /I2C_SDA)"),
    "U6": ("OPTIONAL", "MS5611 barometer: DNP by decision on v10 (order sheet DNP table); "
                      "retained on MINIMAL as an optional site pending cold-qualification "
                      "evidence (ADR-089 retains GPS/tracking; NTC chain measures the cold "
                      "today)"),
    # -- power -------------------------------------------------------------------
    "U7": ("KEEP", "TPS7A02 3V3 LDO -- required power (ADR-089 S1 'ESP32 + required power')"),
    "C_BULK": ("KEEP", "100uF 10V bulk cap (DC-bias corrected part, order sheet)"),
    "C_HF": ("KEEP", "100nF HF decoupling"),
    "C10": ("KEEP", "10uF decoupling"),
    "C4": ("KEEP", "10uF decoupling"),
    "C_MON": ("KEEP", "10nF monitor filter"),
    "R_F1": ("KEEP", "100R F33 CE feed/filter (netlist: R_F1.1 on +3V3 with U2.5 CE)"),
    "R_BAL1": ("KEEP", "10k cell-balance tap (v10 assembly; battery management)"),
    "R_BAL2": ("KEEP", "10k cell-balance tap (as R_BAL1)"),
    "R_DIV1": ("KEEP", "solar/SCAP divider 2.2M (netlist v11 values; v10 had 1M pair) -- SCAP "
                      "monitoring chain"),
    "R_DIV2": ("KEEP", "solar/SCAP divider 620k (as R_DIV1)"),
    "R_MON1": ("KEEP", "4.7M monitor divider leg 1 (with C_MON)"),
    "R_MON2": ("KEEP", "4.7M monitor divider leg 2"),
    "C_DIV1": ("KEEP", "10nF divider filter cap"),
    "C_CAP1": ("OPTIONAL", "3.3F 2.7V supercap site 1: DNP on v10 (order sheet); burst storage "
                          "RETAINED on MINIMAL as an optional site per ADR-089 S1 (ADR-006/036), "
                          "population decision pending qualification"),
    "C_CAP2": ("OPTIONAL", "3.3F 2.7V supercap site 2 (as C_CAP1)"),
    "D1": ("KEEP", "BAT54 gate-protection/power diode (v10 assembly)"),
    "D_HUB1": ("KEEP", "SS24 hub-PV panel diode 1 (solar input protection)"),
    "D_HUB2": ("KEEP", "SS24 hub-PV panel diode 2"),
    "D_BP1": ("KEEP", "SS24 bypass-panel diode 1 (wing solar bypass; top-side per ADR-146)"),
    "D_BP2": ("KEEP", "SS24 bypass-panel diode 2 (top-side per ADR-146; stage-1 board moved it)"),
    "D_BP3": ("KEEP", "SS24 bypass-panel diode 3 (top-side per ADR-146)"),
    "D_BP4": ("KEEP", "SS24 bypass-panel diode 4 (top-side per ADR-146)"),
    "J_HUB_PV": ("KEEP", "hub PV panel 5-pin header (solar input)"),
    "J_VCC": ("OPTIONAL", "F33_VCC_SEL solder jumper (VSCAP/+3V3): leave open until supply "
                          "selection verified (handfit list row 22); site retained, strap "
                          "decision pending"),
    # -- wing interface --------------------------------------------------------
    "J_W1": ("KEEP", "wing socket 1 (board feature; support/wing interface -- its retention is "
                    "tied to the support/wing interface decision, gate G5, and hardware must be "
                    "weighed)"),
    "J_W2": ("KEEP", "wing socket 2 (as J_W1)"),
    "J_W3": ("KEEP", "wing socket 3 (as J_W1)"),
    "J_W4": ("KEEP", "wing socket 4 (as J_W1)"),
    # -- MCU ---------------------------------------------------------------------
    "U1": ("KEEP", "ESP32-S3-WROOM-1U-N8R8 -- the MCU (ADR-089 S1)"),
    # -- unbuildable-on-MINIMAL sites ---------------------------------------------
    "U_HUB_CVT": ("OPTIONAL", "hub PV converter site: part TODO(unverified), output net absent "
                             "on v10 (order sheet DNP). Site kept as OPTIONAL pending a real "
                             "converter part + netlist; NOT part of the MINIMAL radio set."),
    # -- solar divider chain (v11 additions) ----------------------------------------
    "R_SOL1": ("KEEP", "solar divider 220k (wing solar monitoring, netlist chain with R_SOL2)"),
    "R_SOL2": ("KEEP", "solar divider 62k (as R_SOL1)"),
    "R_SOL3": ("KEEP", "solar divider 220k (as R_SOL1)"),
    "R_SOL4": ("KEEP", "solar divider 62k (as R_SOL1)"),
    "R_SOL5": ("KEEP", "solar divider 220k (as R_SOL1)"),
    "R_SOL6": ("KEEP", "solar divider 62k (as R_SOL1)"),
    "C_SOL1": ("KEEP", "solar divider filter cap (as R_SOL1 chain)"),
    "C_SOL2": ("KEEP", "solar divider filter cap"),
    "C_SOL3": ("KEEP", "solar divider filter cap"),
}


def main():
    net = open(NET).read()
    refs = sorted(set(re.findall(r'\(comp \(ref "([A-Za-z_0-9]+)"\)', net)))
    missing = [r for r in refs if r not in V]
    extra = [r for r in V if r not in refs]
    if missing or extra:
        print("VERDICT-COVERAGE FAIL")
        for r in missing:
            print("  netlist ref WITHOUT verdict:", r)
        for r in extra:
            print("  verdict for NON-EXISTING ref:", r)
        sys.exit(1)

    values = {}
    for ref in refs:
        m = re.search(rf'\(comp \(ref "{ref}"\)\s*\n\s*\(value "([^"]*)"\)', net)
        values[ref] = m.group(1) if m else "?"

    out = {
        "_meta": {
            "netlist": "tracker/hardware/schematics/flight_board/v11_flight.net",
            "coverage": f"{len(V)} verdicts for {len(refs)} netlist refs -- 100% of the FULL "
                        "v11 variant reference set (plan Phase 3 exit criterion)",
            "verdict_scale": "KEEP = on the MINIMAL board as-is; OPTIONAL = site retained, "
                             "population/DNP decided by qualification (supercaps, barometer, "
                             "jumper, converter site); REMOVE = dropped from MINIMAL only "
                             "(ADR-089 S1); REPLACE = superseded by a named new feature "
                             "(J_PROG -> pogo pads)",
        },
        "verdicts": {ref: {"verdict": V[ref][0], "value": values[ref], "reason": V[ref][1]}
                     for ref in refs},
        "tally": {},
    }
    for ref in refs:
        k = V[ref][0]
        out["tally"][k] = out["tally"].get(k, 0) + 1

    with open(sys.argv[1], "w") as f:
        json.dump(out, f, indent=1)
    print("WROTE", sys.argv[1])
    print("tally", out["tally"])
    print("coverage: all", len(refs), "netlist refs have verdicts")


if __name__ == "__main__":
    main()
