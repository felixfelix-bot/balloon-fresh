#!/usr/bin/env python3
"""GATE 2.5 placement probe for ONE board -- pad overlaps, out-of-outline, unconnected-to-nothing.

This is the base-station-specific form of the fleet `scripts/placement_overlap_check.py`
(which is hardcoded to the hub). It answers the question that must be answered BEFORE any
routing and before any placement is adopted:

  * do any two pads of DIFFERENT nets overlap (a short that no amount of routing can fix)?
  * do any two courtyards on the SAME side overlap?
  * does any courtyard leave the outline?
  * are there pads with no net (metal that belongs to nothing)?

Exit: 0 = clean, 1 = defects (listed), 2 = could not run.

Usage: placement_gate.py BOARD.kicad_pcb [--clearance 0.2]
"""
import argparse
import sys

import pcbnew

MM = 1e6


def rect_of_pad(pad):
    b = pad.GetBoundingBox()
    return b.GetLeft() / MM, b.GetTop() / MM, b.GetRight() / MM, b.GetBottom() / MM


def overlap(a, b, margin=0.0):
    return not (a[2] + margin <= b[0] or b[2] + margin <= a[0]
                or a[3] + margin <= b[1] or b[3] + margin <= a[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--clearance", type=float, default=0.2)
    ap.add_argument("--json")
    a = ap.parse_args()

    b = pcbnew.LoadBoard(a.board)
    if b is None:
        print(f"REFUSED: cannot load {a.board}")
        return 2

    tracks = list(b.GetTracks())
    fps = list(b.GetFootprints())
    bb = b.GetBoardEdgesBoundingBox()
    bx0, by0 = bb.GetLeft() / MM, bb.GetTop() / MM
    bx1, by1 = bb.GetRight() / MM, bb.GetBottom() / MM

    pads = []
    nonet = []
    for f in fps:
        for p in f.Pads():
            pads.append((f.GetReference(), p))
            if not p.GetNetname():
                nonet.append((f.GetReference(), p.GetNumber(), p.GetPosition().x / MM,
                              p.GetPosition().y / MM))

    shorts = []
    for i in range(len(pads)):
        ri, pi = pads[i]
        ai = rect_of_pad(pi)
        for j in range(i + 1, len(pads)):
            rj, pj = pads[j]
            if ri == rj:
                continue
            if pi.GetNetname() == pj.GetNetname() and pi.GetNetname():
                continue  # same net touching itself is legal
            aj = rect_of_pad(pj)
            if overlap(ai, aj):
                if not (pi.IsOnLayer(pj.GetLayer()) or pj.IsOnLayer(pi.GetLayer())):
                    continue  # opposite faces, no shared copper
                shorts.append(f"{ri}.{pi.GetNumber()} [{pi.GetNetname()}] <-> "
                              f"{rj}.{pj.GetNumber()} [{pj.GetNetname()}]")

    courts = []
    for f in fps:
        lay = f.GetLayer()
        c = f.GetCourtyard(lay)
        if c.OutlineCount() == 0:
            continue
        cbb = c.BBox()
        courts.append((f.GetReference(), lay,
                       cbb.GetLeft() / MM, cbb.GetTop() / MM,
                       cbb.GetRight() / MM, cbb.GetBottom() / MM))

    coverlaps = []
    for i in range(len(courts)):
        for j in range(i + 1, len(courts)):
            if courts[i][1] != courts[j][1]:
                continue
            if overlap(courts[i][2:], courts[j][2:]):
                coverlaps.append(f"{courts[i][0]} <-> {courts[j][0]} on "
                                 f"{'F.Cu' if courts[i][1] == pcbnew.F_Cu else 'B.Cu'}")

    outside = [f"{r} ({x0:.2f},{y0:.2f}..{x1:.2f},{y1:.2f})"
               for r, _l, x0, y0, x1, y1 in courts
               if x0 < bx0 - 1e-6 or y0 < by0 - 1e-6 or x1 > bx1 + 1e-6 or y1 > by1 + 1e-6]

    print(f"board          : {a.board}")
    print(f"outline        : {bx1 - bx0:.2f} x {by1 - by0:.2f} mm")
    print(f"footprints     : {len(fps)}")
    print(f"tracks/vias    : {len(tracks)}")
    print(f"pads           : {len(pads)}  ({len(nonet)} with no net)")
    print(f"courtyards     : {len(courts)}")
    print()
    print(f"pad overlaps (different nets, shared copper layer) : {len(shorts)}")
    for s in shorts[:40]:
        print(f"   {s}")
    print(f"courtyard overlaps (same side)                     : {len(coverlaps)}")
    for s in coverlaps[:40]:
        print(f"   {s}")
    print(f"courtyards outside the outline                     : {len(outside)}")
    for s in outside[:40]:
        print(f"   {s}")
    print(f"pads with no net                                   : {len(nonet)}")
    for s in nonet[:40]:
        print(f"   {s[0]}.{s[1]} at ({s[2]:.2f},{s[3]:.2f})")

    ok = not (shorts or coverlaps or outside)
    print()
    print(f"placement_gate: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
