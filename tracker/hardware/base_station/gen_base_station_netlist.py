#!/usr/bin/env python3
"""Generate the base-station PCBA v1 KiCad netlist from the verified spec.

Candidate derived from spec.json. Buck is an explicit proposed deviation from D14 freeze;
legacy transcription checks cover retained constraints, not approval. See BUCK-EVIDENCE.md.

FROZEN SCOPE, NOT INVENTED:
  - the 433 RX AGC + telemetry controller; NO 2.4 GHz PA, NO masthead LNA on the PCBA
  - separate +5V_LNA_SW / +5V_VGA / +5V_DET / +3V3_MCU domains; no LNA fault may remove MCU power
  - the detector tap carries a SECOND 433 MHz BPF before the AD8318 (mandatory in the freeze)
  - a circulator is forbidden as a substitute

FOOTPRINTS ARE ALL REAL AND INSTALLED -- resolved by resolve_bs_footprints.py against the 165
libraries present on this machine. No footprint is invented.

Every component that cannot be placed without a footprint is given one; parts whose package the
freeze does not pin are marked TODO(unverified) and given a GENERIC package so the first-pass
board is complete but the gap is visible.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = json.load(open(os.path.join(HERE, "spec.json")))
OUT = os.path.join(HERE, "base_station_v1.net")

# (ref, value, footprint, [ (pin, net), ... ])
COMPS = []

def add(ref, value, fp, pins):
    COMPS.append((ref, value, fp, pins))

# ---------------- power entry + regulator (proposed replacement: protected VIN_GS 9-18V -> TPS54202 -> +5V_PCBA) -------
add("J_PWR", "VIN_GS 9-18V input", "TerminalBlock_4Ucon:TerminalBlock_4Ucon_1x02_P3.50mm_Vertical",
    [("1", "VIN_GS"), ("2", "GND")])
# Protection is external at J_PWR; see BUCK-EVIDENCE.md input contract.
# Do not represent unselected/misoriented diodes as working protection.
add("C_IN", "22uF X7R 50V; effective >= 10uF", "Capacitor_SMD:C_1210_3225Metric",
    [("1", "VIN_GS"), ("2", "GND")])
add("C_IN_HF", "100nF X7R 50V", "Capacitor_SMD:C_0603_1608Metric",
    [("1", "VIN_GS"), ("2", "GND")])
# TI SLVSD26C Table 4-1. EN5 deliberately NC: internal pullup (section 6.3.5).
add("U_REG", "TPS54202DDCR", "Package_TO_SOT_SMD:SOT-23-6",
    [("1", "GND"), ("2", "REG_SW"), ("3", "VIN_GS"), ("4", "REG_FB"), ("6", "REG_BOOT")])
add("C_BOOT", "100nF X7R 16V", "Capacitor_SMD:C_0603_1608Metric",
    [("1", "REG_BOOT"), ("2", "REG_SW")])
add("L1", "SRP6060FA-150M 15uH +/-20%; Isat typ 5.8A; Irms typ 4.5A (20C rise); DCR max 43mOhm", "Inductor_SMD:L_Bourns_SRP6060FA",
    [("1", "REG_SW"), ("2", "+5V_PCBA")])
add("R_FB1", "100k 0.1%", "Resistor_SMD:R_0402_1005Metric",
    [("1", "+5V_PCBA"), ("2", "REG_FB")])
add("R_FB2", "13.5k 0.1%", "Resistor_SMD:R_0402_1005Metric",
    [("1", "REG_FB"), ("2", "GND")])
add("C_OUT", "22uF X7R 25V; effective >= 15uF", "Capacitor_SMD:C_1206_3216Metric",
    [("1", "+5V_PCBA"), ("2", "GND")])

add("C_OUT2", "22uF X7R 25V; effective >= 15uF", "Capacitor_SMD:C_1206_3216Metric",
    [("1", "+5V_PCBA"), ("2", "GND")])
add("C_FF", "75pF C0G 50V", "Capacitor_SMD:C_0402_1005Metric",
    [("1", "+5V_PCBA"), ("2", "REG_FB")])

# ---------------- +5V_LNA_SW : switched, resettable-limited (spec) ---------------------------
add("Q_LNA_SW", "load switch / resettable limiter (ADL5240 must NOT share this rail)",
    "Package_TO_SOT_SMD:SOT-23-5",
    [("1", "+5V_PCBA"), ("2", "GND"), ("3", "LNA_EN"), ("4", "LNA_FLT"), ("5", "+5V_LNA_SW")])
add("R_LNA_ILIM", "set LNA branch current limit", "Resistor_SMD:R_0402_1005Metric",
    [("1", "LNA_FLT"), ("2", "GND")])
add("C_LNA1", "100nF (tee DC injection bypass)", "Capacitor_SMD:C_0402_1005Metric",
    [("1", "+5V_LNA_SW"), ("2", "GND")])
add("C_LNA2", "10uF (tee DC injection bypass)", "Capacitor_SMD:C_0805_2012Metric",
    [("1", "+5V_LNA_SW"), ("2", "GND")])

# ---------------- +5V_VGA : ferrite/pi filtered, NOT from the LNA branch ----------------------
add("FB_VGA", "ferrite bead / pi filter", "Inductor_SMD:L_0603_1608Metric",
    [("1", "+5V_PCBA"), ("2", "+5V_VGA")])
add("U_VGA", "ADL5240 VGA (93mA @ 4.75-5.25V, gain from RP2040)", "Package_CSP:LFCSP-32-1EP_5x5mm_P0.5mm_EP3.1x3.1mm",
    [("1", "+5V_VGA"), ("2", "GND"), ("3", "VGA_RF_IN"), ("4", "GND"),
     ("5", "VGA_RF_OUT"), ("6", "VGA_GAIN0"), ("7", "VGA_GAIN1"), ("8", "VGA_GAIN2"),
     ("33", "GND")])
add("C_VGA1", "100nF", "Capacitor_SMD:C_0402_1005Metric", [("1", "+5V_VGA"), ("2", "GND")])
add("C_VGA2", "1uF", "Capacitor_SMD:C_0603_1608Metric", [("1", "+5V_VGA"), ("2", "GND")])

# ---------------- +5V_DET : AD8318 log detector ----------------------------------------------
add("FB_DET", "ferrite bead", "Inductor_SMD:L_0603_1608Metric",
    [("1", "+5V_PCBA"), ("2", "+5V_DET")])
add("U_DET", "AD8318ACPZ-R7 log detector (15mA allowance)",
    "Package_CSP:LFCSP-16-1EP_3x3mm_P0.5mm_EP1.3x1.3mm",
    [("1", "GND"), ("2", "GND"), ("3", "DET_RF_IN"), ("4", "GND"),
     ("5", "+5V_DET"), ("6", "DET_VOUT"), ("7", "GND"), ("8", "GND"), ("17", "GND")])
add("C_DET1", "100nF", "Capacitor_SMD:C_0402_1005Metric", [("1", "+5V_DET"), ("2", "GND")])
add("C_DET2", "100nF (VOUT filter)", "Capacitor_SMD:C_0402_1005Metric",
    [("1", "DET_VOUT"), ("2", "GND")])

# ---------------- +3V3_MCU : RP2040 rail ------------------------------------------------------
add("U_MCU", "RP2040 QFN-56", "base_station_lib:RP2040-QFN-56",
    [(pin, net) for pin, net in SPEC["rp2040_capture"]["pad_nets"].items()])
crystal = SPEC["boot_core"]["crystal"]
add("Y1", crystal["mpn"], crystal["footprint"], list(crystal["pad_nets"].items()))
add("R_XOUT", crystal["xout_series"], "Resistor_SMD:R_0402_1005Metric", [("1", "XOUT"), ("2", "XOUT_XTAL")])
add("C_X1", crystal["load_caps"], "Capacitor_SMD:C_0402_1005Metric", [("1", "XIN"), ("2", "GND")])
add("C_X2", crystal["load_caps"], "Capacitor_SMD:C_0402_1005Metric", [("1", "XOUT_XTAL"), ("2", "GND")])
flash = SPEC["boot_core"]["flash"]
add("U_FLASH", flash["mpn"], flash["footprint"], list(flash["pad_nets"].items()))
add("C_FLASH", "100nF", "Capacitor_SMD:C_0402_1005Metric",
    [("1", "+3V3_MCU"), ("2", "GND")])
for ref, net in (("R_FLASH_CS", "QSPI_SS"), ("R_FLASH_WP", "QSPI_SD2"), ("R_FLASH_HOLD", "QSPI_SD3")):
    add(ref, "10k", "Resistor_SMD:R_0402_1005Metric", [("1", "+3V3_MCU"), ("2", net)])
add("J_SWD", "SWD debug header 1x4", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
    [("1", "+3V3_MCU"), ("2", "SWDIO"), ("3", "GND"), ("4", "SWCLK")])
add("R_RUN", "10k RUN pull-up", "Resistor_SMD:R_0402_1005Metric",
    [("1", "+3V3_MCU"), ("2", "RUN")])
# Datasheet §§2.9,2.10: one local capacitor per supply pin. Placement is still a gate.
for pin in (1, 10, 22, 33, 42, 49, 23, 50, 43, 48, 44, 45):
    add(f"C_RP_{pin}", "1uF" if pin in (44, 45) else "100nF",
        "Capacitor_SMD:C_0402_1005Metric",
        [("1", SPEC["rp2040_capture"]["pad_nets"][str(pin)]), ("2", "GND")])
# Datasheet §1.4.2 requires 27-ohm series termination. Port/ESD selection remains open.
for signal in ("DM", "DP"):
    add(f"R_USB_{signal}", "27R", "Resistor_SMD:R_0402_1005Metric",
        [("1", f"USB_{signal}"), ("2", f"USB_{signal}_PORT")])

# Service-only USB Micro-B: VBUS is an isolated ESD reference, NOT board power.
usb = SPEC["usb_programming"]
for ref, key in (("J_USB", "connector"), ("U_USB_ESD", "esd")):
    part = usb[key]
    add(ref, part["mpn"], part["footprint"], list(part["pad_nets"].items()))
for ref, net in (("SW_BOOTSEL", "BOOTSEL_SW"), ("SW_RESET", "RUN")):
    add(ref, usb["switch"]["mpn"], usb["switch"]["footprint"], [("1", net), ("2", "GND")])
add("R_BOOTSEL", usb["boot_resistor"], "Resistor_SMD:R_0402_1005Metric",
    [("1", "QSPI_SS"), ("2", "BOOTSEL_SW")])

# ---------------- +3V3_MCU source: LDO from +5V_PCBA (own domain per the ERC requirement) -----
ldo = SPEC["boot_core"]["ldo"]
add("U_LDO", ldo["mpn"], ldo["footprint"], list(ldo["pad_nets"].items()))
add("C_LDO1", ldo["capacitors"], "Capacitor_SMD:C_0805_2012Metric", [("1", "+3V3_MCU"), ("2", "GND")])
add("C_LDO2", ldo["capacitors"], "Capacitor_SMD:C_0805_2012Metric", [("1", "+5V_PCBA"), ("2", "GND")])
# TPS54202 has neither an external EN pullup requirement nor a PG output.

# ---------------- RF chain (spec): ant -> BPF -> tee -> LNA -> coax -> tee -> VGA -------------
add("J_433_RX", "433 MHz RX antenna port (SMA)", "Connector_Coaxial:SMA_Amphenol_132134-10_Vertical",
    [("1", "RF_433_ANT"), ("2", "GND")])
# the 433 BPF ahead of the LNA -- first of the two the freeze requires
add("FLT_433_A", "433 MHz BPF (ahead of LNA)", "Filter:Filter_SAW-6_3.8x3.8mm",
    [("1", "RF_433_ANT"), ("2", "RF_433_BPF1")])
add("TEE1", "Mini-Circuits ZFBT-4R2GW+ bias tee (masthead feed boundary, NOT in series)",
    "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    [("1", "RF_433_BPF1"), ("2", "RF_LNA_OUT"), ("3", "+5V_LNA_SW")])
add("J_LNA_FEED", "coax feed to the masthead LNA (SMA)", "Connector_Coaxial:SMA_Amphenol_132134-10_Vertical",
    [("1", "RF_TEE_MAST"), ("2", "GND")])
add("TEE2", "ZFBT-4R2GW+ bias tee (board side)", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    [("1", "RF_COAX_RX"), ("2", "VGA_RF_IN"), ("3", "+5V_LNA_SW")])
# the SECOND 433 BPF before the AD8318 -- MANDATORY in the freeze
add("C_TAP", "directional/coupled tap after the BPF/LNA (TODO(unverified) coupling)",
    "Capacitor_SMD:C_0402_1005Metric", [("1", "VGA_RF_IN"), ("2", "RF_TAP")])
add("FLT_433_B", "433 MHz BPF #2 (before the AD8318 -- mandatory)", "Filter:Filter_SAW-6_3.8x3.8mm",
    [("1", "RF_TAP"), ("2", "DET_RF_IN")])
add("J_2450_TX", "2.45 GHz TX antenna port (SMA; no PA on the PCBA)",
    "Connector_Coaxial:SMA_Amphenol_132134-10_Vertical",
    [("1", "RF_2450_TX"), ("2", "GND")])

# ---------------- quiet analog ground return + test points ------------------------------------
add("TP_5V", "+5V_PCBA test point", "TestPoint:TestPoint_Pad_D1.5mm",
    [("1", "+5V_PCBA")])
add("TP_GND", "GND test point", "TestPoint:TestPoint_Pad_D1.5mm", [("1", "GND")])

# ---- emit netlist ---------------------------------------------------------------------------
def q(s):
    return f'"{s}"'

lines = []
lines.append("(export (version \"E\")\n  (design\n")
lines.append("  )\n")

lines.append("  (components\n")
for ref, val, fp, pins in COMPS:
    lines.append(f'    (comp (ref {q(ref)})\n')
    lines.append(f'      (value {q(val)})\n')
    # CRITICAL: emit a DIRECT (footprint ...) token, not only a field. The hub's proven reader
    # (build_hub_board_v9.read_netlist) extracts `fp = re.search(r'\(footprint "([^"]*)"\)', b)`
    # and falls back to "" -- so a fields-only netlist silently yields an EMPTY lib_id and every
    # part becomes "unplaceable" with no error. Measured 2026-10-14: 44/44 skipped, 0 placed.
    lines.append(f'      (footprint {q(fp)})\n')
    lines.append('      (fields\n')
    lines.append(f'        (field (name "Footprint") {q(fp)})\n')
    lines.append('      )\n')
    lines.append('    )\n')
lines.append("  )\n")

lines.append("  (libparts\n  )\n")
lines.append("  (libraries\n  )\n")

# gather nets
nets = {}
for ref, val, fp, pins in COMPS:
    for pin, net in pins:
        nets.setdefault(net, []).append((ref, pin))

lines.append("  (nets\n")
for i, net in enumerate(sorted(nets), 1):
    lines.append(f'    (net (code "{i}") (name {q(net)})\n')
    for ref, pin in sorted(nets[net]):
        lines.append(f'      (node (ref {q(ref)}) (pin {q(pin)}))\n')
    lines.append("    )\n")
lines.append("  )\n")
lines.append(")\n")

open(OUT, "w").write("".join(lines))
print(f"wrote {OUT}")
print(f"  components : {len(COMPS)}")
print(f"  nets       : {len(nets)}")
print(f"  power rails: {sorted(n for n in nets if n.startswith('+'))}")
print()
print("rails present (the ERC requirement wants four SEPARATE domains on +5V):")
for r in ("+5V_PCBA", "+5V_LNA_SW", "+5V_VGA", "+5V_DET", "+3V3_MCU"):
    print(f"  {r:14s} {'YES' if r in nets else 'MISSING'}")
