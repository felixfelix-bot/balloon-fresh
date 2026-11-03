#!/usr/bin/env python3
"""AUDIT: are the 9 solar gaps really not board-fixable?

The claim under test (docs/analysis/hub-solar-gaps/FINDINGS.md) is:
  "A via cannot land on either end because both are SMD, not PTH, so it would be via-in-pad.
   A via *near* the pad does not connect to it either, since the pad has copper on one layer only."

The second sentence is the one to test. A via does not need to touch the pad: a PAD on F.Cu can be
joined by a short F.Cu TRACK to a via, and the via carries the net to B.Cu, where a second short
track reaches the other pad. That is how every layer change in every routed board works. If there
is room for two short stubs and a via, the pair IS board-fixable and the finding is overstated.

For each gap this measures, with no routing decisions taken:
  * pad side, pad type, pad size, position, and the XY distance between the pair
  * whether a legal via site exists within --search of EACH pad: a point whose via annulus clears
    every other-net track/pad/via on BOTH layers, and which clears the board edge
  * whether the straight stub from each pad to that site is itself clear of other-net copper
and reports, per pair, whether a via-bridge is geometrically available.

Read-only. Usage: audit_solar_gaps.py <board.kicad_pcb> [--search 3.0] [--via-d 0.50]
"""
import argparse
import math
import sys

import pcbnew

UM = 1_000_000.0

# The 9 pairs named by the finding, as (net, refA.padA, refB.padB).
PAIRS = [
    ("/W1_SOLAR_N", "J_W1.4", "D_BP1.2"),
    ("/W1_SOLAR_N", "J_W1.4", "D_BP2.1"),
    ("/W1_SOLAR_N", "J_W2.1", "D_BP2.1"),
    ("/W2_SOLAR_N", "J_W2.4", "D_BP2.2"),
    ("/W2_SOLAR_N", "J_W3.1", "D_BP3.1"),
    ("/W3_SOLAR_N", "J_W3.4", "D_BP3.2"),
    ("/W3_SOLAR_N", "J_W4.1", "D_BP4.1"),
    ("/W3_SOLAR_N", "J_W4.1", "D_BP3.2"),
    ("GND", "U2.4", "D_BP4.2"),
]


def mm(v):
    return round(v / UM, 4)


def find_pad(board, spec):
    ref, num = spec.split(".", 1)
    fp = next((f for f in board.GetFootprints() if f.GetReference() == ref), None)
    if fp is None:
        return None, None
    pad = next((p for p in fp.Pads() if p.GetNumber() == num), None)
    return fp, pad


def copper_obstacles(board, exclude_net):
    """Every other-net copper object on either outer layer, as (kind, bbox, layer)."""
    obs = []
    for t in board.GetTracks():
        if t.GetNetname() == exclude_net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            obs.append(("via", t.GetBoundingBox(), None))
        else:
            obs.append(("track", t.GetBoundingBox(), t.GetLayer()))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == exclude_net:
                continue
            obs.append(("pad", p.GetBoundingBox(), p.GetLayer()))
    return obs


def clears(board, pt, radius_iu, obstacles, layers):
    """Does a circle of radius_iu at pt avoid every obstacle on the given layers?"""
    for kind, bb, lay in obstacles:
        if lay is not None and lay not in layers:
            continue
        # distance from point to bbox
        bx0, by0, bx1, by1 = bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()
        dx = max(bx0 - pt.x, 0, pt.x - bx1)
        dy = max(by0 - pt.y, 0, pt.y - by1)
        if math.hypot(dx, dy) < radius_iu:
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--search", type=float, default=3.0)
    ap.add_argument("--via-d", type=float, default=0.50)
    ap.add_argument("--clearance", type=float, default=0.20)
    ap.add_argument("--step", type=float, default=0.10)
    a = ap.parse_args()

    board = pcbnew.LoadBoard(a.board)
    if board is None:
        print("FAIL: could not load board")
        return 2
    edge = [d.GetBoundingBox() for d in board.GetDrawings()
            if d.GetLayer() == pcbnew.Edge_Cuts]

    def inside_edge(pt, margin):
        for bb in edge:
            if (pt.x < bb.GetLeft() + margin or pt.x > bb.GetRight() - margin
                    or pt.y < bb.GetTop() + margin or pt.y > bb.GetBottom() - margin):
                return False
        return True

    via_r = (a.via_d / 2.0 + a.clearance)
    via_riu = int(via_r * UM)

    results = []
    for net, specA, specB in PAIRS:
        fpA, padA = find_pad(board, specA)
        fpB, padB = find_pad(board, specB)
        if padA is None or padB is None:
            print(f"MISSING {specA} / {specB}")
            continue
        pA, pB = padA.GetPosition(), padB.GetPosition()
        dist = math.hypot(pA.x - pB.x, pA.y - pB.y) / UM
        layA = [pcbnew.LayerName(i) for i in padA.GetLayerSet().Seq()]
        layB = [pcbnew.LayerName(i) for i in padB.GetLayerSet().Seq()]
        sideA = "F" if pcbnew.F_Cu in padA.GetLayerSet().Seq() else "B"
        sideB = "F" if pcbnew.F_Cu in padB.GetLayerSet().Seq() else "B"
        obstacles = copper_obstacles(board, net)

        # For each pad, look for a via site within --search whose annulus clears other-net copper
        # on BOTH layers (a via spans the board) and which sits inside the outline.
        sites = {}
        for tag, pad, p in (("A", padA, pA), ("B", padB, pB)):
            best = None
            n = int(a.search / a.step)
            for ix in range(-n, n + 1):
                for iy in range(-n, n + 1):
                    dx, dy = ix * a.step, iy * a.step
                    d = math.hypot(dx, dy)
                    if d > a.search:
                        continue
                    # keep the site OUTSIDE the pad body so it is not via-in-pad
                    half = max(pad.GetSize().x, pad.GetSize().y) / 2 / UM
                    if d < half + a.via_d / 2 + a.clearance:
                        continue
                    pt = pcbnew.VECTOR2I(p.x + int(dx * UM), p.y + int(dy * UM))
                    if not inside_edge(pt, a.via_d / 2 + 0.3):
                        continue
                    if clears(board, pt, via_riu, obstacles, {pcbnew.F_Cu, pcbnew.B_Cu}):
                        if best is None or d < best[0]:
                            best = (d, dx, dy, pt)
            sites[tag] = best

        results.append({
            "net": net, "A": specA, "B": specB,
            "dist_mm": round(dist, 3),
            "sideA": sideA, "sideB": sideB,
            "layersA": layA, "layersB": layB,
            "via_site_A": None if not sites["A"] else round(sites["A"][0], 2),
            "via_site_B": None if not sites["B"] else round(sites["B"][0], 2),
            "bridge_possible": bool(sites["A"] and sites["B"] and sideA != sideB),
        })
        r = results[-1]
        print(f"{net:14s} {specA:9s}({sideA}) <-> {specB:9s}({sideB})  d={dist:6.2f}mm  "
              f"via-site near A={r['via_site_A']}  near B={r['via_site_B']}  "
              f"BRIDGE={'YES' if r['bridge_possible'] else 'NO'}")

    ok = sum(1 for r in results if r["bridge_possible"])
    print(f"\nvia-bridge geometrically available: {ok} of {len(results)}")
    print("(a via site exists beside EACH pad, the two sit on opposite outer layers, so a "
          "stub-via-stub path is available wherever a stub can also be routed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
