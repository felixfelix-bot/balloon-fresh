#!/usr/bin/env python3
"""Dump v8j DRC violations with involved item descriptions + layers."""
import json, subprocess, sys, tempfile, os
from collections import Counter

board = sys.argv[1]
with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '-o', out, board], capture_output=True, timeout=900)
    drc = json.load(open(out))

viol = drc.get('violations', [])
print(f"violations={len(viol)} unconnected={len(drc.get('unconnected_items',[]))}")
keys = sorted({k for v in viol for k in v})
print("violation keys:", keys)
print()
# item type pairs for clearance
pair = Counter()
lay = Counter()
for v in viol:
    if v['type'] != 'clearance':
        continue
    its = v.get('items', [])
    d = ' + '.join(i.get('description', '?')[:44] for i in its)
    pair[d] += 1
    for i in its:
        lay[(i.get('description', '?')[:20], tuple(i.get('layer', []) or []))] += 1
print("=== clearance item-pair histogram ===")
for d, n in pair.most_common(25):
    print(f"  {n:4d}  {d}")
print()
print("=== clearance item kinds ===  (desc, layers) -> count")
for (d, l), n in lay.most_common(25):
    print(f"  {n:4d}  {d!r} layers={l}")
print()
print("=== all non-clearance violations (detail) ===")
for v in viol:
    if v['type'] == 'clearance':
        continue
    its = ' | '.join(f"{i.get('description','?')[:70]}" for i in v.get('items', []))
    print(f"  [{v['type']}] {v['description'][:80]} :: {its}")
