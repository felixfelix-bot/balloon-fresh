#!/usr/bin/env python3
"""stub_hub_v9_moved_vias.py -- reconnect via/pad pairs our edits separated.

WHY (measured 2026-10-12): when fix_hub_v9_thermals.py moved the two +3V3 vias
near U4 clear of its GND pad 3, one stopped touching its own pad, so DRC reports
`Blind/Buried Via [+3V3] <> Pad 2 [+3V3] of U4`.  Add a short F.Cu stub from the
via to the pad centre on the SAME net.  Only ever connects same-net items.

Deterministic; refuses to touch a foreign net.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)

    # every +3V3 pad with its XY
    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != "+3V3":
                continue
            pads.append((fp.GetReference(), p.GetNumber(), p.GetPosition(),
                         p.GetNetCode(), p.GetSize()))
    vias = [t for t in b.GetTracks()
            if t.GetClass() == "PCB_VIA" and t.GetNetname() == "+3V3"]
    print(f"+3V3 pads: {len(pads)}  vias: {len(vias)}")

    added = 0
    for (ref, num, ppos, pnet, psize) in pads:
        # nearest via on the same net
        best = None
        for v in vias:
            vp = v.GetPosition()
            d = math.hypot(vp.x - ppos.x, vp.y - ppos.y)
            if best is None or d < best[0]:
                best = (d, v)
        if best is None:
            continue
        d, v = best
        # a via landing inside the pad is already connected
        half = max(psize.x, psize.y) / 2
        if d <= half:
            continue
        # already joined by an existing track?
        joined = False
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetNetCode() != pnet:
                continue
            for a, c in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
                if (abs(a.x - ppos.x) < 1000 and abs(a.y - ppos.y) < 1000):
                    joined = True
                    break
            if joined:
                break
        if joined:
            continue

        tr = pcbnew.PCB_TRACK(b)
        tr.SetStart(ppos)
        tr.SetEnd(v.GetPosition())
        tr.SetWidth(int(0.2 * MM))
        tr.SetLayer(pcbnew.F_Cu)
        tr.SetNetCode(pnet)
        b.Add(tr)
        added += 1
        print(f"  stub {ref}.{num} ({ppos.x/MM:.3f},{ppos.y/MM:.3f}) -> "
              f"via ({v.GetPosition().x/MM:.3f},{v.GetPosition().y/MM:.3f}) "
              f"d={d/MM:.3f} mm")

    print(f"stub traces added: {added}")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
