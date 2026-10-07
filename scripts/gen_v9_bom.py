#!/usr/bin/env python3
"""Generate docs/v9-BOM.md for the v9 balloon flight board FROM the netlist.

Reproducible: every machine-readable column (Reference, Value, Footprint,
Library id, DNP, net membership) is read out of the KiCad netlist.  Nothing is
hand-typed except the FUNCTION column (prose) and the 'Parts and their key
ratings' section, both of which cite an in-repo source for every number and use
`TODO(unverified)` where no source exists.

Usage:
    python3 scripts/gen_v9_bom.py                       # default : v9 variant
    python3 scripts/gen_v9_bom.py --net <path.net> --out <path.md>
    python3 scripts/gen_v9_bom.py --check               # exit 1 if docs/v9-BOM.md is stale

Regenerate the netlist first if the schematic moved:
    python3 tracker/hardware/schematics/flight_board/build_flight_sch.py v9
    kicad-cli sch export netlist --output <...>/v9_flight.net <...>/v9_flight.kicad_sch
"""
import argparse
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_NET = os.path.join(
    REPO, "tracker", "hardware", "schematics", "flight_board", "v9_flight.net")
DEFAULT_OUT = os.path.join(REPO, "docs", "v9-BOM.md")

# ---------------------------------------------------------------- FUNCTION prose
# One line per reference designator.  Written by hand; the script fails loudly if
# the netlist grows a reference that has no entry here, so the table can never
# silently fall out of sync with the schematic.
FUNCTION = {
    # --- connectors / antennas
    "ANT1": "433 MHz DOWNLINK U.FL coaxial tap for the F33 sub-GHz port; hub wire dipole (ADR-009, ADR-034).",
    "ANT2": "2.4 GHz U.FL coaxial tap for the F33's second 50 ohm port (TX/RX); hub wire dipole.",
    "ANT3": "2.4 GHz UPLINK-RX U.FL coaxial tap for the bare LoRa2021 receiver; hub wire dipole.",
    "ANT4": "GNSS L1 U.FL coaxial tap for the MAX-M10S; hub wire dipole with ground plane.",
    # --- decoupling / bulk
    "C4": "GNSS rail decoupling on GNSS_VCC, after the R_F1 series element.",
    "C_BULK": "100 uF bulk reservoir on F33_VCC so the 1100 mA PA burst does not sag the rail.",
    "C_HF": "100 nF HF decoupling on F33_VCC at the module pin.",
    "C_CAP1": "Supercapacitor bank cell 1 (top of the series pair) - the only energy store; no battery.",
    "C_CAP2": "Supercapacitor bank cell 2 (bottom of the series pair, cold end at GND).",
    "C_MON": "Filter/storage cap on the F33_VSENSE divider tap feeding the ESP32 ADC.",
    # --- diodes
    "D1": "BAT54 series-blocking Schottky at the wing-string output (ADR-006); defines VSCAP, the pre-LDO node.",
    "D_BP1": "Per-interface bypass Schottky across J_W1 SOLAR_P..SOLAR_N; a cracked/shaded wing costs one wing, not the string (ADR-053).",
    "D_BP2": "Per-interface bypass Schottky across J_W2 SOLAR_P..SOLAR_N (ADR-053).",
    "D_BP3": "Per-interface bypass Schottky across J_W3 SOLAR_P..SOLAR_N (ADR-053).",
    "D_BP4": "Per-interface bypass Schottky across J_W4 SOLAR_P..SOLAR_N; its cathode side sits on the GND-referenced end of the string (ADR-053).",
    "D_CLAMP": "TVS shunt clamp on the raw supercap node; set point TODO(unverified) (must conduct above the 5.4 V bank top, ADR-047).",
    "D_HUB1": "Bypass Schottky for the hub array's upper cell (PVA1) - hub string is INDEPENDENT of the wing string (ADR-051).",
    "D_HUB2": "Bypass Schottky for the hub array's lower cell (PVA2) - hub string is INDEPENDENT of the wing string (ADR-051).",
    # --- jumper / sockets / cells
    "J_VCC": "3-way solder jumper selecting the F33 rail: pin 1 = VSCAP (raw ~5.4 V, PRE-REGULATOR), pin 2 = F33_VCC, pin 3 = +3V3 (ADR-047).",
    "J_W1": "Wing 1 jettisonable socket, 4-pin: 1 SOLAR_P, 2 GND, 3 RF_FEED (reused as CUT_SENSE_W1), 4 SOLAR_N (ADR-046/048).",
    "J_W2": "Wing 2 jettisonable socket, 4-pin (pin 1 ties to the W1 SOLAR_N hub link: the wings are ONE series string).",
    "J_W3": "Wing 3 jettisonable socket, 4-pin (pin 1 ties to the W2 SOLAR_N hub link).",
    "J_W4": "Wing 4 jettisonable socket, 4-pin (pin 4 SOLAR_N is the string's GND end).",
    "PVA1": "Hub solar array cell 1 of 2 (SolarCell_78x39mm): a separate, independent series string (ADR-051).",
    "PVA2": "Hub solar array cell 2 of 2 (SolarCell_78x39mm); series with PVA1 via HUB_PV_MID1.",
    # --- resistors
    "R_BAL1": "Balancing/pull resistor from VSCAP to the SCAP_MID tap (bank midpoint monitoring and leakage balance).",
    "R_BAL2": "Balancing/pull resistor from SCAP_MID to GND (completes the bank midpoint divider).",
    "R_DIV1": "Upper leg of the supercap voltage divider to SCAP_ADC (1 M/1 M avoided: 1 M/1 M costs 14.6 uW, ADR-047).",
    "R_DIV2": "Lower leg of the supercap voltage divider to SCAP_ADC and GND.",
    "R_F1": "100R series filter/limiter between the 3V3 rail and GNSS_VCC.",
    "R_MON1": "Upper leg of the F33_VSENSE divider on the F33 rail (4.7 M, chosen so bias stays at the 100 uW night-anchor scale, ADR-047).",
    "R_MON2": "Lower leg of the F33_VSENSE divider to GND (4.7 M/4.7 M = 9.4 M total, 5.4 V/9.4 M = 0.574 uA = 3.1 uW).",
    "R_NTC1": "NTC bias/series resistor from the bare LoRa2021 VTCXO pad; **DNP** - the pads have NO path back to the chip on the owned module (ADR-059).",
    "TH_NTC1": "NTC thermistor on NTC_SENSE for the on-chip temperature-compensation provision; **DNP** (ADR-059).",
    # --- ICs / modules
    "U1": "ESP32-S3-WROOM-1U-N8R8 MCU: 8 MB flash + 8 MB PSRAM on-module; flash is the persistent log, PSRAM may only stage (ADR-061).",
    "U2": "LoRa2021F33-2G4 - 433 MHz DOWNLINK TX, internal 0.5 ppm TCXO, +33 dBm / ~1100 mA at 5 V; MUST be fed pre-regulator (ADR-034/047).",
    "U3": "LoRa2021 (bare, castellated) - 2.4 GHz UPLINK RX, crystal only (no TCXO), 1.8-3.6 V (ADR-034).",
    "U4": "SX1280 - 2.4 GHz RANGING only: not a link carrier and not the timing authority (ADR-060).",
    "U5": "MAX-M10S GNSS receiver; its 1PPS on TIMEPULSE is the zero-gram clock-discipline source (ADR-056 D3).",
    "U6": "MS5611-01BA barometer on I2C. NOTE: ADR-108 names MS5607-02BA03 - see discrepancy note below.",
    "U7": "TPS7A0233 LDO producing the 3V3 rail from VSCAP; rated ~200 mA (KiCad lib) / 300 mA (ADR-006) and CANNOT feed the F33.",
    "U_CUT1": "Latched cut driver for wing 1 (nichrome), powered from the post-BAT54/pre-LDO VSCAP node so a cut still works with the converter dead.",
    "U_CUT2": "Latched cut driver for wing 2 (nichrome); VSCAP-powered.",
    "U_CUT3": "Latched cut driver for wing 3 (nichrome); VSCAP-powered.",
    "U_CUT4": "Latched cut driver for wing 4 (nichrome); VSCAP-powered.",
    "U_HUB_CVT": "HUB_CONVERTER - TPS63060-class buck-boost on the hub array input (HUB_PV_P/HUB_PV_N). Output net is TODO(unverified) in this netlist.",
}

# Ratings section: (label, figure, source).  Source is an in-repo path; nothing here
# is a datasheet figure pulled from memory.
RATINGS = [
    ("F33 (U2) RF output", "+33 dBm (2 W) on the sub-GHz port; 5 V for full power",
     "`docs/adr/047-v9-power-provisioning.md:67` (5.0 V / 33.0 dBm / 1100 mA)"),
    ("F33 (U2) TX supply current", "1100 mA at 5 V (datasheet round bound <1200 mA)",
     "`docs/adr/047-v9-power-provisioning.md:67,104`"),
    ("F33 (U2) reference", "internal TCXO, 0.5 ppm",
     "`docs/V9-RADIO-SITE-MATRIX.md` \u00a72 variant census"),
    ("F33 (U2) rail feed", "**PRE-REGULATOR from the raw storage node (VSCAP)**, selected by `J_VCC` pin 1",
     "`docs/adr/047-v9-power-provisioning.md:125-153` (`pin 1 = VSCAP (raw cap rail, ~5.4 V) \u2190 F33 position`)"),
    ("Why not the LDO", "TPS7A02 recorded rating **\u2264300 mA** (ADR-006) / **200 mA** (KiCad lib symbol). "
                        "1118 mA \u00f7 200 mA = **5.59\u00d7 over** - a pre-regulator-class LDO CANNOT feed the F33",
     "`docs/adr/047-v9-power-provisioning.md:167-172`"),
    ("Bare LoRa2021 (U3) rail", "1.8-3.6 V (3.3 V); crystal only, **no TCXO, no NTC**",
     "`docs/V9-RADIO-SITE-MATRIX.md` \u00a72; `docs/adr/034-radio-band-split-433-tx-2g4-rx.md`"),
    ("Bypass Schottky D_BP1..D_BP4 (SS24)", "**2 A / 40 V**, populated, hub-side",
     "`docs/adr/049-wing-architecture.md:76-78` (\u22652 A / 40 V, SS24 or PMEG4020ER class); `docs/adr/053-per-cell-bypass-diodes.md`"),
    ("Bypass Schottky D_HUB1/D_HUB2 (SS24)", "**2 A / 40 V**, populated, hub array",
     "same rating class as ADR-049:76-78; hub string per `docs/adr/051-hub-array-and-cut-topology.md:213`"),
    ("Supercapacitor bank C_CAP1/C_CAP2", "2 \u00d7 AVX SCC **3.3 F 2.7 V** series = **1.65 F @ \u22645.4 V** (24.06 J full); "
                                          "doubled bank **3.3 F** = **33.264 J usable** (5.4 \u2192 3.0 V). "
                                          "**No battery.** `docs/adr/006-supercapacitor-power.md`, `docs/adr/047-v9-power-provisioning.md:218-228`",
     "`docs/POWER-BUDGET-V9-D2BE.md:41,44`; `docs/adr/047-v9-power-provisioning.md:218-221,526-527`"),
    ("Wing solar array", "4 wings \u00d7 3 LARGE cells = **12 cells in ONE series string**, "
                         "**6.0 V nominal @ 1.2 A \u2248 7.2 W peak**",
     "`docs/adr/051-hub-array-and-cut-topology.md:75`; `docs/adr/049-wing-architecture.md:43-44`"),
    ("Wing string cold Voc", "\u2248**9.58 V at \u221260 \u00b0C** (items the bypass diodes' 40 V rating)",
     "`docs/adr/051-hub-array-and-cut-topology.md:512`"),
    ("Hub array", "INDEPENDENT series string (PVA1/PVA2), own converter input `HUB_CONVERTER` (TPS63060-class). "
                  "Cutting a wing cannot kill the hub array",
     "`docs/adr/051-hub-array-and-cut-topology.md:213`"),
    ("Energy budget", "average load **0.388 W** (day); night anchor **100 uW** (10 h = 3.6 J)",
     "`docs/POWER-BUDGET-V9-D2BE.md:85,98,112`; `docs/adr/047-v9-power-provisioning.md:415-417`"),
    ("Rail monitor bias R_MON1/R_MON2", "5.4 V \u00f7 9.4 M\u03a9 = **0.574 uA = 3.1 uW**",
     "`docs/adr/047-v9-power-provisioning.md:411,540`"),
    ("ESP32-S3-WROOM-1U-N8R8 (U1)", "**8 MB flash + 8 MB PSRAM** on-module; **no external storage part**",
     "`docs/adr/061-onboard-storage.md`; commit `e4d0569` corrects previously wrong 16 MB claims"),
    ("MAX-M10S (U5)", "1PPS on TIMEPULSE \u2192 ESP32 **GPIO21**; zero-gram/zero-watt clock discipline",
     "`docs/adr/056-thermal-and-frequency-drift.md:126-141`; `docs/adr/108-f33-sx1280-pin-plan.md:38`"),
    ("Barometer (U6)", "schematic says **MS5611-01BA**; ADR-108 names **MS5607-02BA03**. "
                       "Schematic wins on the drawing, discrepancy flagged",
     "`tracker/hardware/schematics/flight_board/v9_flight.net` vs `docs/adr/108-f33-sx1280-pin-plan.md`"),
    ("Wing socket pinout", "`1 SOLAR_P / 2 GND / 3 RF_FEED / 4 SOLAR_N`; the wing string order runs "
                           "W1\u2192W2\u2192W3\u2192W4 with only W4_SOLAR_N on GND",
     "`docs/adr/048-v9-hub-wing-interfaces.md:83,99-128`"),
    ("Cut drivers U_CUT1..U_CUT4", "powered from `VSCAP` = post-`D1`(BAT54) / pre-LDO node",
     "netlist net `/VSCAP` = {`C_CAP1.1`, `D1.1`, `J_VCC.1`, `R_BAL1.1`, `R_DIV1.1`, `U7.1`, `U7.3`, `U_CUT1..4.1`}"),
    ("DNP parts", "`R_NTC1`, `TH_NTC1` - pads have **NO path back to the chip** on the owned module",
     "`docs/adr/059-ntc-temp-compensation-provision.md:333,371-375`; netlist `(property (name \"dnp\"))`"),
]


# ---------------------------------------------------------------- netlist parsing
def parse_net(path):
    text = open(path, encoding="utf-8").read()
    title = re.search(r'\(title "([^"]*)"\)', text)
    rev = re.search(r'\(rev "([^"]*)"\)', text)
    comps = []
    for b in re.split(r"\n    \(comp ", text)[1:]:
        ref = re.search(r'\(ref "([^"]+)"\)', b).group(1)
        val = re.search(r'\(value "([^"]*)"\)', b)
        fp = re.search(r'\(footprint "([^"]*)"\)', b)
        lib = re.search(r'\(libsource \(lib "([^"]*)"\) \(part "([^"]+)"\)', b)
        desc = re.search(r'\(libsource .*?\(description "(.*?)"\)', b, re.S)
        comps.append(dict(
            ref=ref,
            value=val.group(1) if val else "",
            footprint=fp.group(1) if fp else "",
            lib=(lib.group(1) + ":" + lib.group(2)) if lib else "",
            description=(desc.group(1) if desc else "").replace("\\n", " "),
            dnp='(property (name "dnp"))' in b,
        ))
    nets = []
    for b in re.split(r"\n    \(net ", text)[1:]:
        name = re.search(r'\(name "([^"]*)"\)', b).group(1)
        nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', b)
        nets.append((name, nodes))
    return dict(title=title.group(1) if title else "", rev=rev.group(1) if rev else "",
                comps=comps, nets=nets)


def per_ref_nets(nets):
    out = {}
    for name, nodes in nets:
        for ref, pin in nodes:
            out.setdefault(ref, []).append((name, pin))
    return out


def md_escape(s):
    return s.replace("|", "\\|").strip() or "\u2014"


def render(data, net_path, sch_path):
    comps = data["comps"]
    nets = data["nets"]
    joined = per_ref_nets(nets)
    refs = sorted(comps, key=lambda c: (re.sub(r"\d+$", "", c["ref"]), int(re.findall(r"\d+$", c["ref"])[0]) if re.findall(r"\d+$", c["ref"]) else 0))
    missing = [c["ref"] for c in comps if c["ref"] not in FUNCTION]
    if missing:
        sys.exit("FUNCTION prose missing for: %s" % missing)

    L = []
    L.append("# v9 balloon flight board - Bill of Materials")
    L.append("")
    L.append("**Source of truth:** `%s` (exported from `%s`)." % (
        os.path.relpath(net_path, REPO), os.path.relpath(sch_path, REPO)))
    L.append("")
    L.append("**GENERATED FILE - do not hand-edit.** Regenerate with:")
    L.append("")
    L.append("```sh")
    L.append("python3 scripts/gen_v9_bom.py")
    L.append("```")
    L.append("")
    L.append("Every column except FUNCTION is read out of the netlist. The FUNCTION column")
    L.append("and the ratings section are prose authored against in-repo sources; anything with")
    L.append("no source carries `TODO(unverified)`.")
    L.append("")
    L.append("**Total component count: %d** (single hub+4-wing variant; netlist exports %d nets). "
             "Count the rows below against `grep -c '(comp (ref ' %s` if you want to check this "
             "table against the schematic itself." % (
                 len(comps), len(nets), os.path.relpath(net_path, REPO)))
    L.append("")
    L.append("Title block on the schematic: *%s*, rev *%s*." % (data["title"], data["rev"]))
    L.append("")
    L.append("> **Configurations.** This is the **A** variant population (hub + 4 wings). "
             "**Variant B** is hub-only - no wings, no cut, target <20 g payload - in which "
             "`J_W1..J_W4`, `D_BP1..D_BP4`, `U_CUT1..U_CUT4` go unpopulated but stay on the "
             "board. The netlist carries the superset; it does not distinguish the two.")
    L.append("")

    # ---- table
    L.append("## Bill of materials")
    L.append("")
    L.append("| # | Reference | Value | Footprint / library id | DNP | Function |")
    L.append("|---:|---|---|---|---|---|")
    for i, c in enumerate(refs, 1):
        fp = (c["footprint"] or "\u2014").replace(":", " : ")
        L.append("| %d | `%s` | `%s` | `%s` / `%s` | %s | %s |" % (
            i, c["ref"], md_escape(c["value"]), fp, c["lib"] or "\u2014",
            "**DNP**" if c["dnp"] else "populated", FUNCTION[c["ref"]]))
    L.append("")

    # ---- DNP summary
    dnp = [c["ref"] for c in refs if c["dnp"]]
    L.append("### Do-not-populate parts")
    L.append("")
    L.append("%d of %d parts are marked DNP in the schematic: %s." % (
        len(dnp), len(comps), ", ".join("`%s`" % d for d in dnp)))
    L.append("")
    L.append("**Why - `R_NTC1` / `TH_NTC1` (ADR-059):** the provision is the LR2021's on-chip NTC")
    L.append("temperature compensation, biased from the bare module's `VTCXO` pad (net `/VTCXO_VNTC`).")
    L.append("ADR-059 records that **the sense node has no path back to the chip on the owned bare")
    L.append("module** - the module's 18 castellations expose no `NTC` pad, so the loop cannot be")
    L.append("closed. The pads stay on the board (the `NTC_SENSE` net exists: `R_NTC1.2` /")
    L.append("`TH_NTC1.1`) so the provision can be populated if the module break-out is ever")
    L.append("confirmed. Source: `docs/adr/059-ntc-temp-compensation-provision.md:333,371-375`.")
    L.append("")

    # ---- ratings
    L.append("---")
    L.append("")
    L.append("## Parts and their key ratings")
    L.append("")
    L.append("The numbers that matter when ordering. Each row cites its in-repo source.")
    L.append("")
    L.append("| Item | Rating / figure | Source |")
    L.append("|---|---|---|")
    for label, fig, src in RATINGS:
        L.append("| %s | %s | %s |" % (label, fig, src))
    L.append("")

    # ---- discrepancies
    L.append("---")
    L.append("")
    L.append("## Discrepancies found while extracting this BOM (flagged, not resolved)")
    L.append("")
    L.append("1. **Barometer part number.** The schematic/netlist says `U6 = MS5611-01BA`")
    L.append("   (footprint `Package_LGA:LGA-8_3x5mm_P1.25mm`). `docs/adr/108-f33-sx1280-pin-plan.md`")
    L.append("   names **MS5607-02BA03**. This BOM and the system diagram draw **MS5611-01BA**")
    L.append("   because that is what the schematic says. Operator to reconcile.")
    L.append("2. **Bypass diode part family, rating and DNP state.** ADR-048 \u00a72.3 specifies")
    L.append("   \"BAT54 family, SOD-323, **DNP for the first prototype**\". ADR-049:76-78 re-rates")
    L.append("   the requirement to **\u22652 A / 40 V (SS24 or PMEG4020ER class)** because BAT54's")
    L.append("   200 mA / 30 V is undersized against the 1.2 A LARGE-cell string. The schematic")
    L.append("   follows ADR-049: `D_BP1..D_BP4` are **SS24 in `Diode_SMD:D_SMA`, populated**, and")
    L.append("   the netlist marks **no** DNP flag on them. ADR-048's text is therefore stale.")
    L.append("3. **Wing pin 3 `RF_FEED`.** ADR-048 \u00a72.3 states pin 3 \"carries NO net on v9\". The")
    L.append("   netlist wires it: `/CUT_SENSE_W<n>` = {`J_W<n>.3`, `U_CUT<n>.3`}. The cut-continuity")
    L.append("   sense therefore **does** reuse the RF_FEED line on this design, as the design intent")
    L.append("   requires - but the ERC still reports the four `J_W<n>` pin-3 pads, so read the")
    L.append("   ERC count as \"expected baseline\", not as a defect.")
    L.append("4. **`U_HUB_CVT` has no output net.** The netlist gives `HUB_CONVERTER` only")
    L.append("   `HUB_PV_P` (pin 1), `GND` (pin 2) and `HUB_PV_N` (pin 3). No rail on the output")
    L.append("   side is assigned: **TODO(unverified)** - which rail the hub converter feeds, and")
    L.append("   whether it parallels the wing string into `VSCAP` or drives `+3V3`, is not in the")
    L.append("   netlist. Verify against `docs/adr/051-hub-array-and-cut-topology.md` before layout.")
    L.append("5. **ERC.** `v9_flight-erc.rpt` (2026-10-07T16:35:38) reports **23 errors, 0 warnings**,")
    L.append("   all of them `pin_not_connected` (deliberate provision/`TODO(unverified)` pins such")
    L.append("   as `U3` pads 16/17, `U4` VDD_IN/VDD_IO/RFIO, `U6` PS/SDO/CSB). No short or drive")
    L.append("   conflict is reported.")
    L.append("")
    L.append("Per-reference nets (for auditing any row above against the schematic):")
    L.append("")
    L.append("| Reference | Nets |")
    L.append("|---|---|")
    for c in refs:
        ns = joined.get(c["ref"], [])
        L.append("| `%s` | %s |" % (c["ref"], ", ".join("`%s`" % n for n, _ in ns) or "\u2014 (no net, deliberate provision)"))
    L.append("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", default=DEFAULT_NET)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if --out differs from what would be generated")
    a = ap.parse_args()
    sch = a.net.replace(".net", ".kicad_sch")
    data = parse_net(a.net)
    body = render(data, a.net, sch)
    if a.check:
        old = open(a.out).read() if os.path.exists(a.out) else ""
        if old != body:
            print("STALE: %s differs from generator output" % a.out)
            return 1
        print("OK: %s is current (%d components)" % (a.out, len(data["comps"])))
        return 0
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(body)
    print("wrote %s (%d components, %d nets)" % (a.out, len(data["comps"]), len(data["nets"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
