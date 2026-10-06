#!/usr/bin/env python3
"""Authoritative parts extraction from the v8i flight board.

  * PCB  : parse footprints (Reference / Value) from v8i_krt_gnss.kicad_pcb
  * SCH  : parse the sibling netlist v_c3_flight.net
Print both, and diff them so we know whether the schematic matches the board.
"""
import re, json, collections
from pathlib import Path

HW = Path("~/worktrees/fab-record-v8i/tracker/hardware").expanduser()
PCB = HW / "output" / "v8i_krt_gnss.kicad_pcb"
NETS = [HW / "schematics/flight_board/v_c3_flight.net",
        HW / "schematics/v_c3_flight.net"]

s = PCB.read_text(errors="replace")

# --- PCB: walk footprint blocks, pull Reference + Value properties -----------
parts = {}
blocks = re.split(r'\n  \(footprint ', s)[1:]
for b in blocks:
    block = "(footprint " + b
    ref = re.search(r'\(property "Reference" "([^"]+)"', block)
    val = re.search(r'\(property "Value" "([^"]+)"', block)
    if not ref:
        ref = re.search(r'\(fp_text reference "([^"]+)"', block)
    if not val:
        val = re.search(r'\(fp_text value "([^"]+)"', block)
    if ref:
        parts[ref.group(1)] = val.group(1) if val else "?"

print(f"=== PCB footprints: {len(parts)} ===")
def key(r):
    m = re.match(r'([A-Za-z]+)(\d+)', r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)
for r in sorted(parts, key=key):
    print(f"  {r:6s} {parts[r]}")

print()
for net in NETS:
    if not net.exists():
        continue
    t = net.read_text(errors="replace")
    comps = dict(re.findall(r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\)', t))
    if not comps:
        comps = dict(re.findall(r'\(ref "([^"]+)"\).*?\(value "([^"]*)"\)', t, re.S))
    print(f"=== NETLIST {net.name}: {len(comps)} components ===")
    for r in sorted(comps, key=key):
        print(f"  {r:6s} {comps[r]}")
    only_pcb = set(parts) - set(comps)
    only_net = set(comps) - set(parts)
    print(f"  in PCB not netlist: {sorted(only_pcb, key=key)}")
    print(f"  in netlist not PCB: {sorted(only_net, key=key)}")
    print()
