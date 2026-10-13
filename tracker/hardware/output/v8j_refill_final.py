#!/usr/bin/env python3.14
"""Refill every zone on the target board in place (deterministic, no inference).

The 138 `clearance` errors + the 9 `hole_clearance` errors on the salvaged v8j
were STALE inner-layer fills: In1 (GND) / In2 (+3V3) retained fill polygons
computed before the U5 swap, so vias and pads sat 0.2005 mm from plane copper
where the frozen zone clearance is 0.220 mm.  Refilling regenerates the
antipads/thermals against the CURRENT geometry.  Idempotent.
"""
import sys, os, subprocess, json, tempfile
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew  # noqa: E402
from collections import Counter

path = sys.argv[1]
b = pcbnew.LoadBoard(path)
n = len(list(b.Zones()))
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
pcbnew.SaveBoard(path, b)
print(f'refilled {n} zones on {path} ({os.path.getsize(path)} bytes)')

with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '-o', out, path], capture_output=True, timeout=900)
    r = json.load(open(out))
v = r.get('violations', [])
e = sum(1 for x in v if str(x.get('severity', '')).lower() == 'error')
w = sum(1 for x in v if str(x.get('severity', '')).lower() == 'warning')
u = r.get('unconnected_items', [])
print(f'DRC: violations={len(v)} (err={e} warn={w}) unconnected={len(u)}')
print('  by type:', dict(Counter(x["type"] for x in v).most_common()))
for it in u:
    print('   UNCONN:', it['description'][:90])
