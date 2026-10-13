#!/usr/bin/env python3.14
"""Experiment: refill all zones on a copy of the routed v8j board and re-DRC.

Zero-inference, deterministic. Writes ONLY to a scratch path in the worktree.
"""
import sys, os, shutil, subprocess, json, tempfile, hashlib
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

HW = 'tracker/hardware/output'
SRC = f'{HW}/v8j_krt_ms5611.kicad_pcb'
DST = f'{HW}/v8j_refill_test.kicad_pcb'

# sibling rule files so kicad-cli DRC resolves the SAME frozen rule set as v8i
shutil.copy(f'{HW}/v8i_krt_gnss.kicad_dru', f'{HW}/v8j_refill_test.kicad_dru')
shutil.copy(f'{HW}/v8i_krt_gnss.kicad_dru', f'{HW}/v8j_krt_ms5611.kicad_dru')
d = json.load(open(f'{HW}/v8i_krt_gnss.kicad_pro'))
d.setdefault('meta', {})['filename'] = 'v8j_krt_ms5611.kicad_pro'
json.dump(d, open(f'{HW}/v8j_krt_ms5611.kicad_pro', 'w'), indent=2)
shutil.copy(f'{HW}/v8j_krt_ms5611.kicad_pro', f'{HW}/v8j_refill_test.kicad_pro')

b = pcbnew.LoadBoard(SRC)
zones = list(b.Zones())
print(f'zones={len(zones)}  filled={sum(1 for z in zones if z.IsFilled())}')
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
print(f'after fill: filled={sum(1 for z in b.Zones() if z.IsFilled())}')
pcbnew.SaveBoard(DST, b)
print('wrote', DST, os.path.getsize(DST))

with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '-o', out, DST], capture_output=True, timeout=900)
    r = json.load(open(out))
from collections import Counter
v = r.get('violations', [])
e = sum(1 for x in v if str(x.get('severity','')).lower()=='error')
w = sum(1 for x in v if str(x.get('severity','')).lower()=='warning')
print(f"AFTER REFILL: violations={len(v)} (err={e} warn={w}) unconnected={len(r.get('unconnected_items',[]))}")
for t, n in Counter(x['type'] for x in v).most_common():
    print(f"   {n:4d} {t}")
unc = r.get('unconnected_items', [])
if unc:
    print("  unconnected:")
    for u in unc:
        print("   -", u['description'][:70])
