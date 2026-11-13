#!/usr/bin/env python3
"""v11_diode_sites_v2.py -- find top-face sites for D_BP1..4 using REAL copper geometry.

WHY A SECOND VERSION. The first one (v11_diode_sites.py) produced 387/584/194/6154 "valid
sites", which were applied and generated 13 shorting_items in DRC. Then a quick patch made it
report ZERO sites everywhere. BOTH answers were artifacts of the same two geometric errors,
in opposite directions:

  1. TRACKS WERE REDUCED TO THEIR ENDPOINTS. A 20 mm track passing through a candidate site has
     no endpoint near it, so it was invisible. This UNDER-counted obstruction -- which is how
     sites that sit directly on copper got reported as free.

  2. CLEARANCE WAS MEASURED FROM THE FOOTPRINT CENTRE. A D_SMA has its two pads 4.00 mm apart,
     so each pad sits 2.00 mm off centre. A 2.5 mm centre clearance demands 4.5 mm from the
     pad -- far stricter than needed. This OVER-counted obstruction, which is how the "zero
     sites" answer appeared.

Neither error is visible without checking the geometry the checker claims to check, which is
why this version works in terms of the two PADS and the actual SEGMENTS.

METHOD. For each candidate centre and rotation:
  - compute both pad positions from the real footprint pad offsets
  - pad A must be within MAX_REACH of its own net's copper
  - pad B must be within MAX_REACH of its own net's copper
  - BOTH pads must clear every foreign-net track segment, via, and pad by >= CLEAR

Segment distance, not point distance: point-to-segment projection.
"""
import math
import os
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hub_board_v10.kicad_pcb")
MAX_REACH = 6.0     # pad-to-own-net copper
CLEAR = 0.35        # pad edge to foreign copper: DRC clearance is 0.2, add margin
EDGE_KEEP = 3.0
# D_SMA is 4.30 mm long and 2.60 mm wide; two diodes must not share space. Centre-to-centre
# minimum that guarantees no body overlap at any rotation is the diagonal, 5.0 mm.
DIODE_SPACING = 5.0

# Real D_SMA pad offsets, measured from the footprint rather than assumed.
def sma_pads():
    """Pad geometry is read from a PLACED footprint, never from my own transform.

    The first two attempts computed pad positions by rotating the local offsets by hand. That
    is wrong: a KiCad footprint's local +Y points DOWN while board +Y points UP, so the
    placement transform is a reflection for 90/270 rotations, not a pure rotation. Both
    versions therefore reported pads in mirrored positions -- which is why every "valid" site
    shorted Pad 2 onto /CUT_SENSE_W* tracks. Rather than patch the transform a third time,
    this asks KiCad itself: place the footprint and read pad.GetPosition().
    """
    lib = "/usr/share/kicad/footprints/Diode_SMD.pretty"
    fp = pcbnew.FootprintLoad(lib, "D_SMA")
    if fp is None:
        raise SystemExit("cannot load D_SMA to read pad offsets")
    out = []
    for p in fp.Pads():
        pos = p.GetPosition()
        out.append((pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y),
                    pcbnew.ToMM(p.GetSize().x), pcbnew.ToMM(p.GetSize().y)))
    return out


def seg_dist(px, py, x1, y1, x2, y2):
    """Distance from a point to a line SEGMENT (not to its endpoints, not to its line)."""
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0.0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def read_placed_pads(probe, x, y, rot):
    """Position the single probe footprint and read where its pads land.

    The probe is loaded ONCE and mutated. Loading a footprint per candidate crashed SWIG
    (FootprintLoad returning a null plug after repeated calls, then a core dump), and adding/
    removing a footprint per candidate was both slow and leak-prone.
    """
    probe.SetPosition(pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
    probe.SetOrientation(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
    out = []
    for p in probe.Pads():
        pos = p.GetPosition()
        sz = p.GetSize()
        out.append((pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y),
                    max(pcbnew.ToMM(sz.x), pcbnew.ToMM(sz.y)) / 2.0))
    return out


def main():
    b = pcbnew.LoadBoard(BOARD)
    if b is None:
        raise SystemExit(f"cannot load {BOARD}")
    bb = b.GetBoardEdgesBoundingBox()
    W, H = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())

    pads = sma_pads()
    print(f"board {W:.1f} x {H:.1f} mm")
    print(f"D_SMA pads (real offsets): "
          f"{[(round(x,2), round(y,2), round(sx,2), round(sy,2)) for x, y, sx, sy in pads]}")

    # ---- copper of each net, as SEGMENTS (tracks+vias) and PADS ----------------------
    segs = {}     # net -> [(x1,y1,x2,y2, halfwidth)]
    padpts = {}   # net -> [(cx, cy, halfwidth)]  (square pads approximated by half-diag)
    for t in b.GetTracks():
        net = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            w = pcbnew.ToMM(t.GetWidth()) / 2.0
            segs.setdefault(net, []).append(
                (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), w))
            continue
        lay = t.GetLayer()
        w = pcbnew.ToMM(t.GetWidth()) / 2.0
        for layer in (pcbnew.F_Cu, pcbnew.In1_Cu):
            if lay == layer:
                s, e = t.GetStart(), t.GetEnd()
                segs.setdefault(net, []).append(
                    (pcbnew.ToMM(s.x), pcbnew.ToMM(s.y),
                     pcbnew.ToMM(e.x), pcbnew.ToMM(e.y), w))
    for f in b.GetFootprints():
        if f.GetReference().startswith("D_BP"):
            continue
        for p in f.Pads():
            if p.GetLayer() not in (pcbnew.F_Cu, pcbnew.In1_Cu):
                continue
            pos = p.GetPosition()
            sz = p.GetSize()
            half = max(pcbnew.ToMM(sz.x), pcbnew.ToMM(sz.y)) / 2.0
            padpts.setdefault(p.GetNetname(), []).append(
                (pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y), half))

    def dist_to_net(net, px, py):
        """Nearest copper EDGE of `net` to a point, considering segments and pads alike."""
        best = 1e9
        for x1, y1, x2, y2, w in segs.get(net, ()):
            best = min(best, seg_dist(px, py, x1, y1, x2, y2) - w)
        for cx, cy, half in padpts.get(net, ()):
            best = min(best, math.hypot(px - cx, py - cy) - half)
        return best

    def foreign_clear(px, py, own_nets):
        best = 1e9
        for net in set(list(segs.keys()) + list(padpts.keys())):
            if net in own_nets or net == "":
                continue
            best = min(best, dist_to_net(net, px, py))
            if best <= CLEAR:
                return best
        return best

    pairs = [
        ("D_BP1", "/W1_SOLAR_P", "/W1_SOLAR_N"),
        ("D_BP2", "/W1_SOLAR_N", "/W2_SOLAR_N"),
        ("D_BP3", "/W2_SOLAR_N", "/W3_SOLAR_N"),
        ("D_BP4", "/W3_SOLAR_N", "GND"),
    ]

    probe = pcbnew.FootprintLoad("/usr/share/kicad/footprints/Diode_SMD.pretty", "D_SMA")
    if probe is None:
        raise SystemExit("cannot load D_SMA probe")

    print(f"\nreach limit {MAX_REACH} mm, foreign clearance {CLEAR} mm "
          f"(measured to pad EDGES and track EDGES)")
    print()
    results = {}
    taken = []   # (x, y, rot) already assigned to an earlier diode -- diodes are 4.3 mm long
    # and must not be stacked on each other. Without this, the per-diode searches
    # independently return sites 1.2 mm apart (D_BP3 at 66.8,40.0 and D_BP4 at 67.2,39.0),
    # which would collide on the board.
    for ref, n1, n2 in pairs:
        found = []
        xi = int(EDGE_KEEP * 10)
        while xi <= int((W - EDGE_KEEP) * 10):
            yi = int(EDGE_KEEP * 10)
            while yi <= int((H - EDGE_KEEP) * 10):
                x, y = xi / 10.0, yi / 10.0
                for rot in (0, 90, 180, 270):
                    ok = True
                    worst_own, worst_for = -1e9, 1e9
                    placed = read_placed_pads(probe, x, y, rot)
                    for k, (px, py, phalf) in enumerate(placed):
                        own = n1 if k == 0 else n2
                        d_own = dist_to_net(own, px, py)
                        if d_own > MAX_REACH:
                            ok = False
                            break
                        worst_own = max(worst_own, d_own)
                        # Subtract the pad's OWN extent. Skipping this was the bug that produced
                        # 15 shorting_items: a 2.5 mm pad measured centre-to-copper needs
                        # phalf adding back, so a "0.35 mm clear" pad was actually overlapping
                        # foreign copper by ~1.25 mm. dist_to_net() returns EDGE distance to the
                        # other net; the pad contributes its own half-extent.
                        # Exclude ONLY this pad's own net. Excluding both diode nets let
                        # D_BP2's /W2_SOLAR_N pad sit on J_W2's /W1_SOLAR_N pad without the
                        # check noticing -- which was the last remaining short.
                        d_for = foreign_clear(px, py, (own,)) - phalf
                        worst_for = min(worst_for, d_for)
                        if d_for < CLEAR:
                            ok = False
                            break
                    if ok:
                        # mutual exclusion against already-assigned diodes
                        for tx, ty, _tr in taken:
                            if math.hypot(x - tx, y - ty) < DIODE_SPACING:
                                ok = False
                                break
                    if ok:
                        found.append((worst_own, worst_for, x, y, rot))
                yi += 2
            xi += 2
        found.sort(key=lambda r: (r[0], -r[1]))
        if found:
            _own, _for, bx, by, br = found[0]
            taken.append((bx, by, br))
        results[ref] = found
        print(f"{ref}  ({n1} / {n2})   {len(found)} site(s)")
        for own, for_, x, y, rot in found[:3]:
            print(f"    ({x:5.1f}, {y:5.1f}) rot {rot:3d}   "
                  f"own-net reach {own:4.2f} mm   foreign clearance {for_:4.2f} mm")
        if not found:
            print("    NONE within the reach limit")
        print()

    return 0 if all(v for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
