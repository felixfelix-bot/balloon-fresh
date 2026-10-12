#!/usr/bin/env python3
"""move_hub_v9_refdes_off_vias.py -- move refdes labels off via fields.

Measured 2026-10-12 (hub_board_v9_final.kicad_pcb): 6 parts have a reference
designator whose text box sits on top of via holes, which agentee reports as
`silk-text ... prints over N vias` (a real fab defect: ink in a hole).

  D_BP1 (2), D_BP2 (2), R_NTC1 (1), R_DIV1 (2), R_DIV2 (1), R_F1 (1)

The PARTS do not move -- only the label.  For each offender, search a spiral of
candidate offsets around the current label position and keep the first offset
whose text box clears (a) every via and (b) the board edge.  Deterministic, no
LLM.  Never hides a label: an unlabeled part cannot be debugged.
"""
import argparse
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
STEP = 0.25                     # search step, mm
RINGS = 8                       # 8 * 0.25 = 2.0 mm search radius
MARGIN = 0.20                   # text-to-via clearance, mm
EDGE = 0.30                     # text-to-board-edge, mm


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)

    vias = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA":
            continue
        pos = t.GetPosition()
        r = t.GetDrillValue() / 2 + int(MARGIN * MM)
        vias.append((pos.x - r, pos.y - r, pos.x + r, pos.y + r))

    bb = b.GetBoardEdgesBoundingBox()
    ex0, ey0 = bb.GetX() + int(EDGE * MM), bb.GetY() + int(EDGE * MM)
    ex1, ey1 = (bb.GetX() + bb.GetWidth() - int(EDGE * MM),
                bb.GetY() + bb.GetHeight() - int(EDGE * MM))

    def rect_of(rt):
        r = rt.GetBoundingBox()
        return (r.GetX(), r.GetY(), r.GetX() + r.GetWidth(),
                r.GetY() + r.GetHeight())

    def bad(rect):
        if rect[0] < ex0 or rect[1] < ey0 or rect[2] > ex1 or rect[3] > ey1:
            return True
        for v in vias:
            if not (rect[2] <= v[0] or v[2] <= rect[0] or
                    rect[3] <= v[1] or v[3] <= rect[1]):
                return True
        return False

    moved = 0
    for fp in b.GetFootprints():
        rt = fp.Reference()
        if not rt.IsVisible():
            continue
        if not bad(rect_of(rt)):
            continue
        ref = fp.GetReference()
        home = rt.GetPosition()
        best = None
        for ring in range(1, RINGS + 1):
            rad = int(ring * STEP * MM)
            for dx, dy in ((0, -rad), (0, rad), (rad, 0), (-rad, 0),
                           (rad, -rad), (-rad, -rad), (rad, rad), (-rad, rad)):
                rt.SetPosition(pcbnew.VECTOR2I(home.x + dx, home.y + dy))
                if not bad(rect_of(rt)):
                    best = (home.x + dx, home.y + dy)
                    break
            if best:
                break
        if best:
            print(f"  {ref}: refdes ({home.x/MM:.2f},{home.y/MM:.2f}) -> "
                  f"({best[0]/MM:.2f},{best[1]/MM:.2f})")
            moved += 1
        else:
            rt.SetPosition(home)
            print(f"  {ref}: NO free spot within {RINGS*STEP:.1f} mm -- left as is")

    print(f"refdes moved: {moved}")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
