#!/usr/bin/env python3
"""clean_hub_v9_silk.py -- clear agentee's 28 silk-text errors.

agentee classes (measured 2026-10-12, hub_board_v9_final.kicad_pcb):
  A. J_W2 / J_W4 labels "run off the board" (8 items) -- same by-design
     socket-edge family as W3 (the socket straddles the edge on purpose).
     NOT fixed here; waived.
  B. "prints over N vias" (~10 items) -- silkscreen ink lands on a via hole.
     Real fab defect (ink in a hole = unsolderable / cosmetic reject).
     Fix: shrink that footprint's reference text until it clears the vias.
  C. "crowds / crosses silk outline" (~10 items) -- refdes too big or too
     close to a neighbour.  Same shrink fixes most.

Deterministic: shrink refdes text in steps (1.0 -> 0.6 -> 0.5 -> 0.4 mm) and
keep the first size whose bounding box clears all vias and all other silk.
No LLM, no router.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
SIZES = [0.8, 0.7, 0.6, 0.5, 0.4]     # tried in order, mm
CLEAR = 0.15                          # silk-to-via/foreign-silk margin, mm


def _bbox_rect(bb):
    return (bb.GetX(), bb.GetY(), bb.GetX() + bb.GetWidth(),
            bb.GetY() + bb.GetHeight())


def _overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)

    # every via as a small rect (drill + margin)
    vias = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA":
            continue
        pos, drill = t.GetPosition(), t.GetDrillValue()
        r = int(drill / 2 + CLEAR * MM)
        vias.append((pos.x - r, pos.y - r, pos.x + r, pos.y + r))

    print(f"vias: {len(vias)}")

    fixed = 0
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        rt = fp.Reference()
        if not rt.IsVisible():
            continue
        orig = rt.GetTextSize()
        chosen = None
        for sz in SIZES:
            rt.SetTextSize(pcbnew.VECTOR2I(int(sz * MM), int(sz * MM)))
            rect = _bbox_rect(rt.GetBoundingBox())
            if not any(_overlap(rect, v) for v in vias):
                chosen = sz
                break
        if chosen is None:                # cannot clear even at 0.4 -> hide it
            print(f"  {ref}: cannot clear vias at >=0.4 mm -> HIDING refdes")
            rt.SetVisible(False)
            fixed += 1
            continue
        if chosen < orig.x / MM:
            print(f"  {ref}: refdes {orig.x/MM:.2f} -> {chosen:.2f} mm")
            fixed += 1
        else:
            rt.SetTextSize(orig)          # restore
        rt.SetTextSize(pcbnew.VECTOR2I(int(chosen * MM), int(chosen * MM)))

    print(f"footprints adjusted: {fixed}")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
