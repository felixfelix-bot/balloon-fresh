#!/usr/bin/env python3.14
"""Diagnose: which neighbour blocks a 0.60 mm via at each under-size site."""
import sys, os, json, shutil, subprocess, tempfile, math
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
MM = 1e6
HW = 'tracker/hardware/output'
SRC = f'{HW}/v8j_krt_ms5611.kicad_pcb'
PROBE = f'{HW}/v8j_probe.kicad_pcb'
shutil.copy(SRC, PROBE)
for ext in ('.kicad_dru', '.kicad_pro'):
    shutil.copy(f'{HW}/v8j_krt_ms5611{ext}', f'{HW}/v8j_probe{ext}')

bd = pcbnew.LoadBoard(PROBE)
targets = [v for v in bd.GetTracks() if v.Type() == pcbnew.PCB_VIA_T
           and round(v.GetWidth(v.TopLayer()) / MM, 3) < 0.599]
print('under-size vias:', len(targets))
for v in targets:
    p = v.GetPosition(); v.SetWidth(int(0.6 * MM)); v.SetDrill(int(0.3 * MM))
pcbnew.SaveBoard(PROBE, bd)

with tempfile.TemporaryDirectory() as td:
    o = os.path.join(td, 'd.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '-o', o, PROBE], capture_output=True, timeout=900)
    r = json.load(open(o))
errs = [x for x in r.get('violations', []) if str(x.get('severity', '')).lower() == 'error']
print('error violations after 0.60 resize:', len(errs))
# group: find which via each clearance error belongs to
for x in errs:
    if x['type'] != 'clearance':
        print(f"  [{x['type']}] {x['description'][:80]}")
        continue
    items = x.get('items', [])
    vias = [it for it in items if 'Via' in (it.get('description') or '')]
    others = [it for it in items if 'Via' not in (it.get('description') or '')]
    vp = vias[0].get('pos', {}) if vias else {}
    for it in others:
        p = it.get('pos', {})
        print(f"  VIA {vias[0].get('description','?')[:34] if vias else '?'} "
              f"@({vp.get('x')},{vp.get('y')})  <-> {it.get('description','?')[:44]} @({p.get('x')},{p.get('y')})")
