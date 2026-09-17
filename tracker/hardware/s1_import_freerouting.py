#!/usr/bin/python3.14
"""Attempt-B importer: Specctra SES -> .kicad_pcb, deterministically.

WHY IT EXISTS
-------------
The S1 campaign needs the Freerouting attempt to land on a board whose
PLACEMENT is byte-identical to the frozen S0 placement.  pcbnew's own
``ImportSpecctraSES`` is the canonical, coordinate-correct importer (it handles
the um/10 -> nm transform and the DSN Y-inversion itself); the older in-repo
hand-rolled parsers only knew F.Cu/B.Cu and dumped inner-layer copper onto
F.Cu, which shorts a 4-layer board.  So: use KiCad's importer, then PROVE the
placement did not move.

No coordinate literals live here - the SES is the geometry source (a tool
output, not LLM-typed numbers).  This script writes only the path given on
argv, so it owns no board basename (placement_guard R1).

usage: s1_import_freerouting.py <frozen_input.kicad_pcb> <in.ses> <out.kicad_pcb>
exit 0 = imported and placement verified unmoved
"""
from __future__ import annotations

import sys

sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew  # noqa: E402

TOL_NM = 0  # placement must be bit-identical


def placement_map(board) -> dict:
    out = {}
    for fp in board.GetFootprints():
        p = fp.GetPosition()
        out[fp.GetReference()] = (p.x, p.y, fp.GetOrientationDegrees(),
                                  fp.GetLayer())
    return out


def main() -> int:
    src, ses, dst = sys.argv[1], sys.argv[2], sys.argv[3]

    frozen = pcbnew.LoadBoard(src)
    before = placement_map(frozen)

    ok = pcbnew.ImportSpecctraSES(frozen, ses)
    if not ok:
        print("FAIL: pcbnew.ImportSpecctraSES returned False")
        return 1

    after = placement_map(frozen)

    moved = []
    for ref, b in before.items():
        a = after.get(ref)
        if a is None:
            moved.append((ref, "MISSING", b, a))
            continue
        if (abs(a[0] - b[0]) > TOL_NM or abs(a[1] - b[1]) > TOL_NM
                or abs(a[2] - b[2]) > 1e-6 or a[3] != b[3]):
            moved.append((ref, "MOVED", b, a))

    traces = [t for t in frozen.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
    vias = [t for t in frozen.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    layers = {}
    for t in traces:
        layers[frozen.GetLayerName(t.GetLayer())] = \
            layers.get(frozen.GetLayerName(t.GetLayer()), 0) + 1
    via_sizes = {}
    for v in vias:
        key = (round(pcbnew.ToMM(v.GetFrontWidth()), 3),
               round(pcbnew.ToMM(v.GetDrill()), 3))
        via_sizes[key] = via_sizes.get(key, 0) + 1

    print("imported segments=%d vias=%d layers=%s" % (len(traces), len(vias), layers))
    print("via (dia,drill) histogram: %s" % via_sizes)
    print("footprints: before=%d after=%d" % (len(before), len(after)))
    if moved:
        print("PLACEMENT CHECK: FAIL - %d footprint(s) moved:" % len(moved))
        for ref, why, b, a in moved:
            print("   %s %s before=%s after=%s" % (ref, why, b, a))
        return 2
    print("PLACEMENT CHECK: PASS - all %d footprints at frozen position/orientation"
          % len(before))

    pcbnew.SaveBoard(dst, frozen)
    print("wrote %s" % dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
