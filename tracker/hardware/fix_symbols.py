#!/usr/bin/env python3
"""SYMBOL SURGERY: give CUT_CHANNEL and HUB_CONVERTER their real pin counts and real parts.

OPERATOR AUTHORISED THIS ("change U_CUT's symbol to the latched form, apply U_HUB_CVT") and asked me
to pick the parts on price and fit. Picks, with the live-verified evidence in
docs/fab/CUT-DRIVER-SELECTION.md:

    CUT_CHANNEL  -> SN74LVC1G373DBVR   LCSC C128413   stock 34892   $0.2779   SOT-23-6
    HUB_CONVERTER-> BQ25504RGTR        LCSC C2876746  stock 21      $4.5857   VQFN-16 (RGR)

MEASURED DEFECT BEING FIXED: the schematic INSTANCES carried `(property "Footprint" "")` -- empty --
which is exactly why the generator reported these parts "unplaceable" and 7 parts were missing from
the board. A working instance (U2) carries the footprint; these did not.

THE PIN CHANGE IS ADDITIVE ON PURPOSE. Pins 1/2/3 keep their EXACT positions and names, because KiCad
connects by coordinate: moving a pin would silently detach the wires already drawn to it. The new pins
go on free coordinates and the body rectangle grows to hold them.

    CUT_CHANNEL      1 VSCAP  2 GND  3 CUT_W  (unchanged)  + 4 ARM  5 CTRL  6 SENSE
    HUB_CONVERTER    1 PV_P   2 GND  3 PV_N   (unchanged)  + 4 VOUT

`VOUT` is the pin whose ABSENCE made the old 3-pin HUB_CONVERTER unusable as a harvester: a 3-pin part
with no output cannot have a power path to the rail.

Usage:  python3 fix_symbols.py --check | --write
"""
import argparse
import os
import re
import shutil
import uuid

FL = "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/schematics/flight_board"
SCH = os.path.join(FL, "v9_flight.kicad_sch")
LIB = os.path.join(FL, "v9_lib/balloon_flight_v9.kicad_sym")

PARTS = {
    "CUT_CHANNEL": {
        "value": "SN74LVC1G373DBVR",
        "footprint": "Package_TO_SOT_SMD:SOT-23-6",
        "lcsc": "C128413",
        "new_pins": [("ARM", "4"), ("CTRL", "5"), ("SENSE", "6")],
        "old_value": "latched cut driver + cut-sense (part TODO(unverified))",
    },
    "HUB_CONVERTER": {
        "value": "BQ25504RGTR",
        "footprint": "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.1x1.1mm",
        "lcsc": "C2876746",
        "new_pins": [("VOUT", "4")],
        "old_value": "HUB_PV input (part TODO(unverified))",
    },
}

# Where each new pin sits. Chosen on FREE coordinates so no existing connection moves.
# Body is grown from y -3.81..3.81 to -5.08..5.08 to hold them.
PIN_AT = {
    ("CUT_CHANNEL", "ARM"): ("15.24", "-1.27", "180"),
    ("CUT_CHANNEL", "CTRL"): ("-15.24", "3.81", "0"),
    ("CUT_CHANNEL", "SENSE"): ("15.24", "3.81", "180"),
    ("HUB_CONVERTER", "VOUT"): ("15.24", "-1.27", "180"),
}

PIN_TMPL = """\t\t\t(pin passive line
\t\t\t\t(at {x} {y} {rot})
\t\t\t\t(length 2.54)
\t\t\t\t(name "{name}"
\t\t\t\t\t(effects
\t\t\t\t\t\t(font
\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(number "{num}"
\t\t\t\t\t(effects
\t\t\t\t\t\t(font
\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
"""


def block_span(s, needle):
    i = s.find(needle)
    if i < 0:
        return None
    d = 0
    j = i
    while j < len(s):
        if s[j] == "(":
            d += 1
        elif s[j] == ")":
            d -= 1
            if d == 0:
                break
        j += 1
    return i, j + 1


def add_pins_to_libsymbol(blk, sym, new_pins):
    """Append pin blocks to the last sub-symbol that holds pins."""
    subs = list(re.finditer(r'\(symbol "' + sym + r'_\d+_\d+"', blk))
    if not subs:
        return blk, False
    last = subs[-1]
    # span of that sub-symbol
    d = 0
    j = last.start()
    while j < len(blk):
        if blk[j] == "(":
            d += 1
        elif blk[j] == ")":
            d -= 1
            if d == 0:
                break
        j += 1
    end = j + 1
    add = ""
    for name, num in new_pins:
        x, y, rot = PIN_AT[(sym, name)]
        add += PIN_TMPL.format(x=x, y=y, rot=rot, name=name, num=num)
    # insert before the closing paren of the sub-symbol
    inner = blk[last.start():end]
    close = inner.rfind(")")
    new_sub = inner[:close] + add + inner[close:]
    return blk[:last.start()] + new_sub + blk[end:], True


def grow_body(blk):
    return blk.replace("(start -12.7 3.81)", "(start -12.7 5.08)") \
              .replace("(end 12.7 -3.81)", "(end 12.7 -5.08)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    sch = open(SCH, encoding="utf-8").read()
    lib = open(LIB, encoding="utf-8").read()
    changed = []

    # ---------- 1. library file: add pins + grow body ----------
    for sym, spec in PARTS.items():
        span = block_span(lib, '(symbol "' + sym + '"')
        if not span:
            print(f"  LIB {sym}: NOT FOUND")
            continue
        blk = lib[span[0]:span[1]]
        blk2 = grow_body(blk)
        blk2, ok = add_pins_to_libsymbol(blk2, sym, spec["new_pins"])
        if ok:
            lib = lib[:span[0]] + blk2 + lib[span[1]:]
            changed.append(f"lib:{sym}+{len(spec['new_pins'])}pins")

    # ---------- 2. schematic: embedded lib_symbol, same edit ----------
    for sym, spec in PARTS.items():
        span = block_span(sch, '(symbol "balloon_flight_v9:' + sym + '"')
        if not span:
            print(f"  SCH lib_symbol {sym}: NOT FOUND")
            continue
        blk = sch[span[0]:span[1]]
        blk2 = grow_body(blk)
        blk2, ok = add_pins_to_libsymbol(blk2, sym, spec["new_pins"])
        if ok:
            sch = sch[:span[0]] + blk2 + sch[span[1]:]
            changed.append(f"sch_libsym:{sym}")

    # ---------- 3. instances: add (pin N) entries, set Footprint + Value ----------
    for sym, spec in PARTS.items():
        # every instance of this symbol
        idx = 0
        while True:
            m = re.search(r'\(lib_id "balloon_flight_v9:' + sym + r'"\)', sch[idx:])
            if not m:
                break
            start = sch.rfind("(symbol", 0, idx + m.start())
            span = block_span(sch[start:], "(symbol")
            start, end = start, start + span[1]
            blk = sch[start:end]
            ref_m = re.search(r'\(property "Reference" "([^"]+)"', blk)
            ref = ref_m.group(1) if ref_m else "?"
            nb = blk
            # footprint property
            nb = re.sub(r'(\(property "Footprint" )"[^"]*"',
                        r'\1"' + spec["footprint"] + '"', nb, count=1)
            # value
            nb = nb.replace('(property "Value" "' + spec["old_value"] + '"',
                            '(property "Value" "' + spec["value"] + '"')
            # LCSC field: insert a property after the Footprint property block if absent
            if '"LCSC"' not in nb:
                fp_i = nb.find('(property "Footprint"')
                # find end of that property block
                d = 0
                j = fp_i
                while j < len(nb):
                    if nb[j] == "(":
                        d += 1
                    elif nb[j] == ")":
                        d -= 1
                        if d == 0:
                            break
                    j += 1
                lcsc = ('\n\t\t(property "LCSC" "' + spec["lcsc"] + '"\n'
                        '\t\t\t(at 0 0 0)\n\t\t\t(effects\n\t\t\t\t(font\n'
                        '\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)')
                nb = nb[:j + 1] + lcsc + nb[j + 1:]
            # new pin uuids
            for name, num in spec["new_pins"]:
                if f'(pin "{num}"' not in nb:
                    last_pin = None
                    for pm in re.finditer(r'\(pin "\d+"\n\t\t\t\(uuid "[^"]+"\)\n\t\t\)', nb):
                        last_pin = pm
                    if last_pin:
                        ins = last_pin.end()
                        nb = (nb[:ins] + f'\n\t\t(pin "{num}"\n\t\t\t(uuid "{uuid.uuid4()}")\n\t\t)'
                              + nb[ins:])
            if nb != blk:
                sch = sch[:start] + nb + sch[end:]
                changed.append(f"inst:{ref}")
                idx = start + len(nb)
            else:
                idx = end

    print("changes: " + (", ".join(changed) if changed else "NONE"))

    if a.check or not a.write:
        print("\n(check mode -- nothing written)")
        return 0

    shutil.copy2(SCH, SCH + ".bak2")
    shutil.copy2(LIB, LIB + ".bak2")
    open(SCH, "w", encoding="utf-8").write(sch)
    open(LIB, "w", encoding="utf-8").write(lib)
    print("\nwrote schematic + library (backups *.bak2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
