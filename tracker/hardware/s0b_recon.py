#!/usr/bin/env python3
"""S0b recon helper: independent artefact checks for the netlist audit.

Prints:
  1. official KiCad symbol pins for the SOT-23-5 LDO families used in this repo
     (independent of TI's datasheet and of this repo's custom symbol), and
  2. the U2/U3/U4 symbol + footprint facts the audit cites.

Usage: python3 s0b_recon.py
"""
import re
from pathlib import Path

KICAD_SYMS = Path("/usr/share/kicad/symbols")
BOARD = Path(__file__).resolve().parent / "output" / "v_c3_flight_4layer_placed.kicad_pcb"


def symbol_pins(libname: str, symname: str):
    t = (KICAD_SYMS / libname).read_text(encoding="utf-8", errors="replace")
    needle = f'(symbol "{symname}"'
    if needle not in t:
        return None
    i = t.index(needle)
    d, j = 0, i
    while j < len(t):
        if t[j] == "(":
            d += 1
        elif t[j] == ")":
            d -= 1
            if d == 0:
                break
        j += 1
    blk = t[i:j + 1]
    flat = " ".join(blk.split())
    pins = []
    for m in re.finditer(r'\(pin\s+(\S+)\s+\w+\s+\(at[^)]*\)\s*\(length [\d.]+\)\s*'
                         r'\(name "([^"]*)"[^)]*\)\s*\(number "([^"]*)"', flat):
        pins.append((m.group(3), m.group(2), m.group(1)))
    return pins


def main():
    for lib, sym in (("Regulator_Linear.kicad_sym", "TPS7A0508PDBV"),
                     ("Regulator_Linear.kicad_sym", "TPS7A0233PDBVR")):
        pins = symbol_pins(lib, sym)
        print(f"official KiCad {lib}::{sym} -> {sorted(pins) if pins else 'NOT IN LIBRARY'}")

    txt = BOARD.read_text(encoding="utf-8", errors="replace")
    for ref in ("U2", "U3", "U4"):
        m = re.search(r'\(property "Reference" "' + ref + r'"', txt)
        if not m:
            print(f"{ref}: not found")
            continue
        start = txt.rfind("(footprint", 0, m.start())
        blk = txt[start:m.start() + 4000]
        fp = re.search(r'\(footprint "([^"]+)"', blk)
        val = re.search(r'\(property "Value" "([^"]*)"', blk)
        descr = re.search(r'\(descr "([^"]*)"', blk)
        pads = re.findall(r'\(pad "([^"]*)"', blk)
        print(f"{ref}: footprint={fp.group(1) if fp else '?'} value={val.group(1) if val else '?'}")
        if descr:
            print(f"    descr={descr.group(1)}")
        print(f"    pads exposed: {len(pads)} -> {','.join(pads)}")


if __name__ == "__main__":
    main()
