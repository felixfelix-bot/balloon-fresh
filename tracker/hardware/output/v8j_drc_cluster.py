#!/usr/bin/env python3
"""Parse kicad-cli DRC json, cluster violations by position + type."""
import json, subprocess, sys, tempfile, os
from collections import Counter, defaultdict

board = sys.argv[1]
with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '-o', out, board], capture_output=True, timeout=600)
    drc = json.load(open(out))

viol = drc.get('violations', [])
unc = drc.get('unconnected_items', [])
print(f"violations={len(viol)} unconnected={len(unc)}")
print("\n=== by type ===")
for t, n in Counter(v['type'] for v in viol).most_common():
    print(f"  {n:4d}  {t}")

def pos_of(v):
    for it in v.get('items', []):
        p = it.get('pos')
        if p:
            return (round(p['x'], 1), round(p['y'], 1))
    return None

print("\n=== violation items by description (dedup) ===")
desc = Counter()
for v in viol:
    key = (v['type'], v['description'][:110])
    desc[key] += 1
for (t, d), n in desc.most_common(40):
    print(f"  {n:4d}  [{t}] {d}")

print("\n=== position clusters (rounded to 1mm) ===")
cl = Counter()
for v in viol:
    p = pos_of(v)
    if p:
        cl[(t_round := (round(p[0]), round(p[1])), v['type'])] += 1
    else:
        cl[(('?', '?'), v['type'])] += 1
for (p, t), n in cl.most_common(40):
    print(f"  {n:4d}  {t:24s} @ {p}")

print("\n=== unconnected detail ===")
for u in unc:
    items = u.get('items', [])
    ds = ' | '.join(f"{i.get('description','?')[:60]} @{i.get('pos',{}).get('x','?'):.1f},{i.get('pos',{}).get('y','?'):.1f}" for i in items if i.get('pos'))
    print(f"  {u['description'][:50]}: {ds}")
