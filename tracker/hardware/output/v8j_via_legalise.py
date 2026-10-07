#!/usr/bin/env python3.14
"""v8j: legalise any under-size vias on the finished board.

KRT's fab escalation may deliver a via at 0.55/0.30 when a 0.60/0.30 does not
fit under the frozen 0.20 mm clearance.  The frozen rule (.kicad_dru + the
.kicad_pro board setup carried over from the PASSING v8i) requires
via_diameter >= 0.60 mm, so those are gate errors.

Precedent: tracker/hardware/v8g_escape_fix.py + v8g2_via_legalise.py — resize in
place; if the wider via then violates clearance, shift the via along the
away-from-worst-neighbour direction and re-attach every track that terminated on
the old centre (geometry only, no hand-typed coordinates).

Usage: v8j_via_legalise.py <board.kicad_pcb>          # resize in place
       v8j_via_legalise.py <board.kicad_pcb> --shift dx dy   # shift under-size
"""
import sys, subprocess, json, tempfile, os
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew  # noqa: E402

MM = 1_000_000
NEW_W, NEW_D = 0.60, 0.30

path = sys.argv[1]
shift = None
if '--shift' in sys.argv:
    i = sys.argv.index('--shift')
    shift = (float(sys.argv[i + 1]), float(sys.argv[i + 2]))

b = pcbnew.LoadBoard(path)
under = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T
         and round(t.GetWidth(t.TopLayer()) / MM, 3) < NEW_W - 1e-9]
print(f'{len(under)} under-size via(s):')
for v in under:
    p = v.GetPosition()
    print(f'   {v.GetNetname():<10} {v.GetWidth(v.TopLayer())/MM:.3f}/{v.GetDrill()/MM:.3f} '
          f'@({p.x/MM:.3f},{p.y/MM:.3f})')
if not under:
    print('nothing to do'); sys.exit(0)

for v in under:
    if shift:
        old = v.GetPosition()
        new = pcbnew.VECTOR2I(old.x + int(round(shift[0] * MM)),
                              old.y + int(round(shift[1] * MM)))
        for t in b.GetTracks():
            if t.Type() != pcbnew.PCB_TRACE_T:
                continue
            for getter, setter in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                if getter() == old:
                    setter(new)
        v.SetPosition(new)
    v.SetWidth(int(round(NEW_W * MM)))
    v.SetDrill(int(round(NEW_D * MM)))
pcbnew.SaveBoard(path, b)
print(f'legalised -> {NEW_W:.2f}/{NEW_D:.2f}', os.path.getsize(path), 'bytes')

with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'd.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '-o', out, path], capture_output=True, timeout=900)
    r = json.load(open(out))
v = r.get('violations', [])
e = [x for x in v if str(x.get('severity', '')).lower() == 'error']
print(f'DRC: err={len(e)} warn={len(v)-len(e)} unconnected={len(r.get("unconnected_items", []))}')
for x in e:
    print(f'   ERR [{x["type"]}] {x["description"][:90]}')
