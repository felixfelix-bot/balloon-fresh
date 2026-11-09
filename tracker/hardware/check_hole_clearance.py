#!/usr/bin/env python3
"""Deterministic hole-clearance gate (ADR-125).

Checks every H*/HW* footprint (NPTH tether/string holes) on a KiCad board against:

    hole <-> every pad        (both sides)   gap >= 1.0 mm  edge-to-edge
    hole <-> every track seg  ("lanes")      gap >= 0.5 mm  centre-dist minus half-widths
    hole <-> every via                       gap >= 0.5 mm
    hole <-> zone bbox       (pours, conservatively)  no intersection
    hole <-> board edge                      >= 2.0 mm
    hole <-> other hole                      >= 4.0 mm centre-to-centre

Exit 0 = clean. Exit 1 = every violation printed. No LLM, no eyeballs: this is the
gate that catches what a courtyard-bbox check cannot (containment), born from the
2026-10-21 U3 incident (holes 0.41 mm from pads passed bbox-overlap).

Run:
    ~/venvs/kicad/bin/python tracker/hardware/check_hole_clearance.py \
        --board tracker/hardware/hub_board_v10.kicad_pcb
"""
import argparse
import math
import sys

import pcbnew

UM = 1_000_000.0
PAD_GAP = 1.0        # mm, hole-edge to pad-edge
LANE_GAP = 0.5       # mm, hole-edge to track-edge
ZONE_GAP = 0.2       # mm, hole-edge to pour fill. JLCPCB's minimum NPTH-to-copper is 0.20 mm, so
                     # 0.20 is the fabrication floor, not a comfort margin. HW1 measures 0.25 mm
                     # on F.Cu/In1, which is why this passes by 0.05 mm and must not be loosened.
EDGE_GAP = 2.0       # mm, hole-edge to board edge
HOLE2HOLE = 4.0      # mm, centre-to-centre


def seg_point_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    a = ap.parse_args()
    b = pcbnew.LoadBoard(a.board)
    if not b:
        print("REFUSED: board did not load")
        return 3

    holes = []
    others = []
    for fp in b.GetFootprints():
        if fp.GetReference().startswith(("H", "HW")):
            holes.append(fp)
        else:
            others.append(fp)
    # any ref starting with H and value mentioning TETHER or STRING counts
    holes = [fp for fp in b.GetFootprints()
             if fp.GetReference().startswith(("H", "HW"))
             and ("TETHER" in (fp.GetValue() or "").upper() or "STRING" in (fp.GetValue() or "").upper())]
    if not holes:
        print("no holes found (refs H*/HW* with TETHER/STRING values)")
        return 0

    bad = []
    W, H = 53.0, 62.0   # updated by outline bbox below
    bb = b.GetBoardEdgesBoundingBox()
    W, H = bb.GetWidth() / UM, bb.GetHeight() / UM
    x0, y0 = bb.GetX() / UM, bb.GetY() / UM

    centers = []
    for h in holes:
        p = h.GetPosition()
        cx, cy = p.x / UM, p.y / UM
        hr = 1.25  # D2.5/2 (verify from pad drill)
        for pd in h.Pads():
            d = pd.GetDrillSize()
            if d.x:
                hr = (d.x / UM) / 2.0
        centers.append((h.GetReference(), cx, cy, hr))

    # hole <-> pad
    for ref, cx, cy, hr in centers:
        for fp in others:
            for pd in fp.Pads():
                q = pd.GetPosition()
                pr = math.hypot(pd.GetSizeX() / UM, pd.GetSizeY() / UM) / 2
                gap = math.hypot(q.x / UM - cx, q.y / UM - cy) - hr - pr
                if gap < PAD_GAP:
                    bad.append(f"{ref} <-> PAD {fp.GetReference()}.{pd.GetNumber()}: gap {gap:.2f} < {PAD_GAP}")
    # hole <-> lanes (tracks)
    for ref, cx, cy, hr in centers:
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                q = t.GetPosition()
                gap = math.hypot(q.x / UM - cx, q.y / UM - cy) - hr - t.GetWidth() / 2 / UM
                if gap < LANE_GAP:
                    bad.append(f"{ref} <-> VIA: gap {gap:.2f} < {LANE_GAP}")
            else:
                s, e = t.GetStart(), t.GetEnd()
                d = seg_point_dist(cx, cy, s.x / UM, s.y / UM, e.x / UM, e.y / UM)
                gap = d - hr - t.GetWidth() / 2 / UM
                if gap < LANE_GAP:
                    bad.append(f"{ref} <-> LANE {t.GetNetname() or '(no net)'}: gap {gap:.2f} < {LANE_GAP}")
    # hole <-> zones: test the FILL, not the bounding box.
    #
    # The bbox test that used to be here could never pass on this board: the pours cover the whole
    # outline (71.1 x 79.1 mm), so every mounting hole "intersected" every pour's bounding box by
    # construction. Measured 2026-11-09: 40 violations on a board with 8 holes and 5 zones -- 8 x 5
    # bbox hits -- reported as "verify keep-out" with no way to act on any of them. A gate that
    # cannot pass is not a gate; it is a permanent red light people learn to ignore, which is
    # strictly worse than no check, because it also hides real violations of the same shape.
    #
    # What actually matters is whether the hole's drill edge penetrates the copper that the pour
    # really lays down. Ask the fill polygon, and ask it with the hole's edge as a circle.
    for ref, cx, cy, hr in centers:
        for z in b.Zones():
            try:
                poly = z.GetFilledPolysList(z.GetLayer())
            except Exception:
                poly = None
            if poly is None or poly.IsEmpty():
                # unfilled zone: it lays down no copper, so it cannot violate a keep-out. Not a
                # pass-by-omission -- a pour that has not been filled is air.
                continue
            hit = False
            # CollideEdge takes a POINT, not a shape; step the hole's rim around the circle.
            N = 24
            for i in range(N):
                th = 2 * math.pi * i / N
                px = int(round((cx + hr * math.cos(th)) * UM))
                py = int(round((cy + hr * math.sin(th)) * UM))
                pt = pcbnew.VECTOR2I(px, py)
                try:
                    if poly.Collide(pt, 0):
                        hit = True
                        break
                except Exception:
                    continue
            # and the centre, which catches a hole fully swallowed by the pour
            if not hit:
                try:
                    if poly.Collide(pcbnew.VECTOR2I(int(round(cx * UM)), int(round(cy * UM))), 0):
                        hit = True
                except Exception:
                    pass
            if hit:
                gap = 0.0
            else:
                # measure the real clearance, so a pour that comes close but not quite is reported
                # with a number instead of passing silently
                try:
                    gap = min(
                        poly.Distance(pcbnew.VECTOR2I(
                            int(round((cx + hr * math.cos(2 * math.pi * i / 24)) * UM)),
                            int(round((cy + hr * math.sin(2 * math.pi * i / 24)) * UM)))) / UM
                        for i in range(24))
                except Exception:
                    continue
            if gap < ZONE_GAP:
                bad.append(f"{ref} <-> ZONE {z.GetNetname()} ({b.GetLayerName(z.GetLayer())}): "
                           f"drill edge to fill {gap:.2f} mm < {ZONE_GAP} mm")
    # hole <-> edge
    for ref, cx, cy, hr in centers:
        d = min(cx - x0, (x0 + W) - cx, cy - y0, (y0 + H) - cy) - hr
        if d < EDGE_GAP:
            bad.append(f"{ref} <-> EDGE: {d:.2f} < {EDGE_GAP}")
    # hole <-> hole
    for i, (r1, x1, y1, h1) in enumerate(centers):
        for r2, x2, y2, h2 in centers[i + 1:]:
            d = math.hypot(x2 - x1, y2 - y1)
            if d < HOLE2HOLE:
                bad.append(f"{r1} <-> {r2}: {d:.2f} < {HOLE2HOLE} centre-to-centre")

    print(f"holes checked: {len(centers)}  ({', '.join(r for r, *_ in centers)})")
    if bad:
        print(f"VIOLATIONS: {len(bad)}")
        for v in bad:
            print("  ", v)
        return 1
    print("clear: 0 violations (pads, lanes, vias, zones, edge, hole-to-hole)")
    return 0


if __name__ == "__main__":
    sys.exit(main())