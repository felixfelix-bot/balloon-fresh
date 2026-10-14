#!/usr/bin/env python3
"""Are the edge tracks in the SEED (generator) or introduced by the ROUTER?

That decides the fix: seed -> fix build_hub_board_v9.py; router -> pass
--board-edge-clearance explicitly.
"""
import sys
import pcbnew

SEED = sys.argv[1] if len(sys.argv) > 1 else "seed"
ROUTED = sys.argv[2] if len(sys.argv) > 2 else "fg_in_filled.kicad_pcb"


def scan(path, label):
    b = pcbnew.LoadBoard(path)
    bds = b.GetBoardEdgesBoundingBox()
    x0, y0 = bds.GetX() / 1e6, bds.GetY() / 1e6
    x1 = x0 + bds.GetWidth() / 1e6
    y1 = y0 + bds.GetHeight() / 1e6
    hits = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK":
            continue
        for pt, other in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
            x, y = pt.x / 1e6, pt.y / 1e6
            d = min(x - x0, x1 - x, y - y0, y1 - y)
            if d < 0.60:
                hits.append((t.GetNetname(), b.GetLayerName(t.GetLayer()), d))
                break
    print(f"{label}: {len(hits)} tracks whose endpoints are within 0.60mm of the bbox edge")
    for n, l, d in hits[:14]:
        print(f"    {n:16s} {l:8s} {d:.3f} mm")
    return len(hits)


n1 = scan(SEED, "SEED")
print()
n2 = scan(ROUTED, "ROUTED")
print()
print(f"=> {'SEED carries them: fix the generator' if n1 else 'the ROUTER introduced them: pass --board-edge-clearance'}")
