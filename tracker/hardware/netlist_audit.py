#!/usr/bin/env python3
"""Netlist audit for the S0-frozen flight board: classify the pads that carry no net.

Every pad on output/v_c3_flight_4layer_placed.kicad_pcb whose (net ...) is absent
is listed and classified as INTENTIONAL or GAP, with the evidence for the call.

The classification table below is KNOWLEDGE (device pin functions), not geometry:
it contains no coordinates.  The pad list itself is read off the board, so this
file cannot drift from the artefact it audits.

Sources for the pin functions (all in-repo or in the KiCad libraries on this host):
  * U1  ESP32-C3-WROOM-02 : /usr/share/kicad/footprints/RF_Module.pretty/
                            ESP32-C3-WROOM-02.kicad_mod has exactly 9 UNNAMED pads
                            (an unnamed pad cannot carry a net - library fact).
  * U2  LR2021F33         : tracker/hardware/full_pipeline.py:191-213
                            ("NiceRF LR2021F33 module. 18 pads") - pads 12 and 15
                            are the module's only NC pins.
  * U3  MAX-M10S          : /usr/share/kicad/symbols/RF_GPS.kicad_sym symbol
                            MAX-M10S pin names (1 GND, 2 TXD, 3 RXD, 4 TIMEPULSE,
                            5 EXTINT, 6 V_BCKP, 7 VCC_IO, 8 VCC, 9 ~RESET, 10 GND,
                            11 RF_IN, 12 GND, 13 LNA_EN, 14 VCC_RF, 15 VIO_SEL,
                            16 SDA, 17 SCL, 18 ~SAFEBOOT).
  * U4  TPS7A02 (DBV)     : schematics/v_c3_rp2040/balloon_symbols.kicad_sym
                            TPS7A0233PDBVR pins (1 IN, 2 GND, 3 EN, 4 OUT, 5 NC)
                            vs tracker/hardware/full_pipeline.py:279 ("(IN, GND,
                            EN, OUT, NC)") - the two disagree about pins 4/5.
  * J1                     : Connector_Generic 1x06; 5 of 6 pins carry nets.

usage: python3 netlist_audit.py [board] [--json out.json] [--md out.md]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (ref, pad) -> (classification, pin_function, basis, action)
KNOWN = {
    # ---- U1: the ESP32-C3 module's 9 unnamed pads are library MECHANICAL pads ----
    # handled generically below (empty pad number)

    ("J1", "6"): ("INTENTIONAL",
                  "spare pin on a 1x06 programming header (5 signals used)",
                  "J1 carries GND/+3V3/EN/UART0_TX/UART0_RX on pads 1-5; pad 6 is the "
                  "unused end pin of the header",
                  "mark it no-connect in the schematic so ERC stops reporting it"),

    ("U2", "7"): ("GAP (probable unused I/O)",
                  "left-side pad between LR_RST (6) and GND (8)",
                  "the module's only NC pins are 12 and 15 (full_pipeline.py:191-213); "
                  "pad 7 is not one of them",
                  "confirm against the NiceRF LR2021F33 drawing; if it is DIO2, tie it or "
                  "declare it no-connect - it is unmodelled today"),
    ("U2", "11"): ("GAP (probable GROUND tab left floating)",
                   "right-side pad between GND (10) and LR_BUSY (12)",
                   "on the RFM9xW 16-pad reference pinout pads 10/11/16 are GND, and this "
                   "board already nets GND on pads 1/8/10 - pad 11 is the same class of tab",
                   "verify and connect to GND if confirmed; a floating RF module ground tab "
                   "is a grounding/EMC defect"),
    ("U2", "15"): ("GAP (probable unused I/O)",
                   "right-side pad between LR_DIO0 (14) and the netless 16",
                   "not one of the module's declared NC pins (12, 15 in the 18-pad map do "
                   "not line up with this 16-pad footprint)",
                   "confirm and no-connect explicitly"),
    ("U2", "16"): ("GAP (probable GROUND tab left floating)",
                   "right-side end pad, next to netless 15",
                   "same evidence as U2 pad 11 (RFM9xW reference GND tab)",
                   "verify and connect to GND if confirmed"),

    ("U3", "4"): ("INTENTIONAL", "TIMEPULSE (output)",
                  "optional 1PPS output, unused in this design",
                  "no-connect in schematic"),
    ("U3", "5"): ("INTENTIONAL", "EXTINT (input)",
                  "optional external-interrupt input, unused",
                  "no-connect in schematic"),
    ("U3", "6"): ("GAP (power pin unconnected)", "V_BCKP (backup supply)",
                  "V_BCKP is a power_in pin; nothing on the board drives it, so RTC/hot-start "
                  "backup is undefined",
                  "tie to +3V3 (or to the supercap rail) or declare the trade-off explicitly"),
    ("U3", "9"): ("GAP (input floating)", "~RESET (active-low reset input)",
                  "active-low reset is not tied and not driven - a floating reset input is "
                  "undefined at power-up",
                  "tie to +3V3 through the design's pull-up or drive it"),
    ("U3", "11"): ("GAP (FUNCTIONAL-CRITICAL)", "RF_IN (GPS antenna input)",
                   "nothing on this board connects to RF_IN: the 20-footprint board carries no "
                   "GPS antenna part or feed net (only ANT1/U.FL for 2.4GHz), so the MAX-M10S "
                   "receiver input is open",
                   "add the antenna feed (patch / U.FL + matching) or the GPS cannot receive"),
    ("U3", "13"): ("INTENTIONAL", "LNA_EN (output)",
                   "only used to bias an external LNA; none fitted",
                   "no-connect in schematic"),
    ("U3", "14"): ("INTENTIONAL", "VCC_RF (power output for an ACTIVE antenna)",
                   "no active antenna in this design",
                   "no-connect in schematic; revisit if an active antenna is ever fitted"),
    ("U3", "15"): ("GAP (input floating)", "VIO_SEL (IO voltage select)",
                   "a floating select input leaves the IO reference undefined",
                   "tie per the u-blox datasheet (to GND or VCC_IO)"),
    ("U3", "16"): ("INTENTIONAL", "SDA (DDC/I2C data)",
                   "the module is used over UART (GPS_RX/GPS_TX on pads 2/3)",
                   "no-connect in schematic"),
    ("U3", "17"): ("INTENTIONAL", "SCL (DDC/I2C clock)",
                   "as pad 16",
                   "no-connect in schematic"),
    ("U3", "18"): ("GAP (input floating)", "~SAFEBOOT (input)",
                   "safe-boot input is not tied or driven",
                   "tie to the level the datasheet requires or no-connect explicitly"),

    ("U4", "3"): ("GAP (enable floating)", "EN (active-high enable)",
                  "every in-repo source agrees pin 3 is EN, and EN carries no net - the rail is "
                  "never explicitly enabled",
                  "tie EN to IN/VCAP (always-on) or to a GPIO"),
    ("U4", "4"): ("GAP (OUT/NC contradiction)", "OUT or NC - the two in-repo sources disagree",
                  "balloon_symbols.kicad_sym says pin 4 = OUT and pin 5 = NC; "
                  "full_pipeline.py:279 says the pads are (IN, GND, EN, OUT, NC). The board "
                  "carries +3V3 on pad 5 and nothing on pad 4, which matches the TI DBV "
                  "arrangement (5 = OUT, 4 = NC) and contradicts the custom symbol",
                  "arbitrate against the TI datasheet before fab, then fix whichever artefact "
                  "is wrong (symbol or board) - today they cannot both be right"),
}


def pads_without_net(board: Path):
    text = board.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in re.finditer(r"\(footprint\s+\"([^\"]*)\"\s+\(layer", text):
        i = m.start()
        d, j = 0, i
        while j < len(text):
            c = text[j]
            if c == '"':
                j += 1
                while j < len(text) and text[j] != '"':
                    if text[j] == "\\":
                        j += 1
                    j += 1
            elif c == "(":
                d += 1
            elif c == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        blk = text[i:j + 1]
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
        libid = m.group(1)
        if not ref:
            continue
        for padded in re.finditer(r"\(pad\s+\"([^\"]*)\"\s+(\w+)\s+(\w+)([\s\S]*?)\n\s*\)", blk):
            num, ptype, shape, body = padded.groups()
            if re.search(r"\(net \d+", body):
                continue
            size = re.search(r"\(size ([\d.]+) ([\d.]+)\)", body)
            drill = re.search(r"\(drill ([\d.]+)", body)
            at = re.search(r"\(at ([-\d.]+) ([-\d.]+)", body)
            out.append({
                "ref": ref.group(1), "pad": num, "footprint": libid,
                "type": ptype, "shape": shape,
                "size_mm": [float(size.group(1)), float(size.group(2))] if size else None,
                "drill_mm": float(drill.group(1)) if drill else 0.0,
                "local_at": [float(at.group(1)), float(at.group(2))] if at else None,
            })
    return out


def classify(rows):
    # confidence = how well the call is documented by something in this repo/host
    #   HIGH   = proven from an artefact (library footprint, symbol, board census)
    #   MEDIUM = inferred from the datasheet-level pin map; needs the module drawing
    #   LOW    = the sources contradict each other; a human/datasheet must arbitrate
    conf = {
        ("U2", "7"): "MEDIUM", ("U2", "11"): "MEDIUM",
        ("U2", "15"): "MEDIUM", ("U2", "16"): "MEDIUM",
        ("U3", "6"): "HIGH", ("U3", "9"): "MEDIUM", ("U3", "11"): "HIGH",
        ("U3", "15"): "HIGH", ("U3", "18"): "MEDIUM",
        ("U4", "3"): "HIGH", ("U4", "4"): "LOW",
    }
    for r in rows:
        key = (r["ref"], r["pad"])
        if key in KNOWN:
            c, fn, basis, action = KNOWN[key]
            r.update(classification=c, confidence=conf.get(key, "MEDIUM"),
                     pin_function=fn, basis=basis, action=action)
        elif r["ref"] == "U1" and r["pad"] == "":
            r.update(classification="INTENTIONAL", confidence="HIGH",
                     pin_function="library mechanical pad (no pad number)",
                     basis="the KiCad library footprint "
                           "RF_Module.pretty/ESP32-C3-WROOM-02.kicad_mod contains exactly 9 "
                           "unnamed pads; an unnamed pad cannot be netted by construction",
                     action="none - mechanical only")
        else:
            r.update(classification="UNCLASSIFIED", confidence="LOW",
                     pin_function="unknown",
                     basis="no evidence found for this pad",
                     action="classify by hand")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("board", nargs="?", default=str(HERE / "output" / "v_c3_flight_4layer_placed.kicad_pcb"))
    ap.add_argument("--json")
    ap.add_argument("--md")
    a = ap.parse_args()
    board = Path(a.board)
    rows = classify(pads_without_net(board))
    counts = Counter(r["classification"].split(" (")[0] for r in rows)
    conf = Counter(r["confidence"] for r in rows if r["classification"].startswith("GAP"))
    doc = {
        "board": str(board),
        "pads_total_without_net": len(rows),
        "classification_counts": dict(counts),
        "gap_confidence_counts": dict(conf),
        "by_ref": dict(Counter(r["ref"] for r in rows)),
        "pads": rows,
        "note": "GAP = a pin whose device function expects a connection that no net provides. "
                "INTENTIONAL = unused/optional pin, or a library mechanical pad. "
                "The 4-layer routed board carried the SAME 27 netless pads, so no net was lost "
                "by the S0 placement change - this audit characterises a pre-existing netlist, "
                "it does not introduce one.",
    }
    s = json.dumps(doc, indent=2)
    print(json.dumps({k: doc[k] for k in
                      ("board", "pads_total_without_net", "classification_counts",
                       "gap_confidence_counts", "by_ref")},
                     indent=2))
    if a.json:
        Path(a.json).write_text(s)
    if a.md:
        lines = [f"# Netlist audit - {board.name}", "",
                 f"{len(rows)} pads carry no net: **{counts.get('GAP', 0)} classified GAP** "
                 f"({', '.join(f'{v} {k}' for k, v in sorted(conf.items()))}) and "
                 f"{counts.get('INTENTIONAL', 0)} intentional.", "",
                 "Confidence: HIGH = proven from an artefact in this repo/host; "
                 "MEDIUM = inferred from the datasheet-level pin map; "
                 "LOW = the in-repo sources contradict each other.", "",
                 "| ref | pad | classification | conf | pin function | evidence | action |",
                 "|---|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda x: (x["ref"], x["pad"])):
            lines.append(f"| {r['ref']} | {r['pad'] or '(unnamed)'} | {r['classification']} | "
                         f"{r['confidence']} | {r['pin_function']} | {r['basis']} | {r['action']} |")
        lines += ["", doc["note"], ""]
        Path(a.md).write_text("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
