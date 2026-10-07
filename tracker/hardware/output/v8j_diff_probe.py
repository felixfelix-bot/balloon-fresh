#!/usr/bin/env python3
"""Diagnose v8j vs v8i: what did the MS5611 swap actually change?"""
import subprocess, json, sys, re
from collections import Counter

sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

V8I = 'tracker/hardware/output/v8i_krt_gnss.kicad_pcb'
V8J = 'tracker/hardware/output/v8j_krt_ms5611.kicad_pcb'

def survey(path):
    b = pcbnew.LoadBoard(path)
    fps = list(b.GetFootprints())
    info = {}
    for fp in fps:
        info[fp.GetReference()] = {
            'value': fp.GetValue(),
            'fpid': str(fp.GetFPID()),
            'pos': (fp.GetPosition().x/1e6, fp.GetPosition().y/1e6),
            'orient': fp.GetOrientation()/10.0,
            'npads': len(list(fp.Pads())),
            'pads': {p.GetNumber(): ((p.GetPosition().x)/1e6, (p.GetPosition().y)/1e6,
                      p.GetNet().GetNetname() if p.GetNet() else '?') for p in fp.Pads()},
        }
    segs = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
    vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    zones = list(b.Zones())
    return {'fps': info, 'nseg': len(segs), 'nvia': len(vias), 'nzone': len(zones),
            'board': b}

a = survey(V8I)
c = survey(V8J)

print("=== COUNTS ===")
print(f"v8i: fp={len(a['fps'])} seg={a['nseg']} via={a['nvia']} zone={a['nzone']}")
print(f"v8j: fp={len(c['fps'])} seg={c['nseg']} via={c['nvia']} zone={c['nzone']}")

print("\n=== FOOTPRINT DELTA (only refs that differ) ===")
for ref in sorted(set(a['fps']) | set(c['fps'])):
    fa, fc = a['fps'].get(ref), c['fps'].get(ref)
    if fa is None:
        print(f"  {ref}: ONLY in v8j: {fc['value']} {fc['fpid']} @ {fc['pos']}")
        continue
    if fc is None:
        print(f"  {ref}: ONLY in v8i: {fa['value']} {fa['fpid']} @ {fa['pos']}")
        continue
    diffs = []
    if fa['value'] != fc['value']: diffs.append(f"value {fa['value']!r}->{fc['value']!r}")
    if fa['fpid'] != fc['fpid']: diffs.append(f"fpid {fa['fpid']!r}->{fc['fpid']!r}")
    if fa['pos'] != fc['pos']: diffs.append(f"pos {fa['pos']}->{fc['pos']}")
    if fa['orient'] != fc['orient']: diffs.append(f"orient {fa['orient']}->{fc['orient']}")
    if fa['npads'] != fc['npads']: diffs.append(f"npads {fa['npads']}->{fc['npads']}")
    # pad net deltas
    netdelta = []
    for pn in sorted(set(fa['pads']) | set(fc['pads'])):
        pa, pc = fa['pads'].get(pn), fc['pads'].get(pn)
        if pa is None or pc is None:
            netdelta.append(f"pad{pn}: {'MISSING-v8i' if pa is None else 'MISSING-v8j'}")
        elif pa[2] != pc[2]:
            netdelta.append(f"pad{pn}: {pa[2]}->{pc[2]}")
    if netdelta: diffs.append("nets[" + "; ".join(netdelta) + "]")
    if diffs:
        print(f"  {ref}: " + " | ".join(diffs))

print("\n=== U5 detail v8j ===")
u5 = c['fps'].get('U5')
if u5:
    for pn, (x, y, net) in sorted(u5['pads'].items()):
        print(f"  pad {pn}: abs=({x:.3f},{y:.3f}) net={net}")
print("=== U5 detail v8i ===")
u5a = a['fps'].get('U5')
if u5a:
    for pn, (x, y, net) in sorted(u5a['pads'].items()):
        print(f"  pad {pn}: abs=({x:.3f},{y:.3f}) net={net}")
