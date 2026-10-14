#!/usr/bin/env python3
"""Stitch GND pads to the GND plane with SAFE, verified stitching vias.

WHY THIS EXISTS (measured 2026-10-14)
-------------------------------------
The KRT router routes nets with A* tracks, but GND on this board is a PLANE on
In1.Cu/F.Cu/B.Cu. A plane net is not "routed" by tracks -- it is connected by the
plane plus the vias that pull pads down to it. The router gets most of it via the
plane and leaves a few pad-to-plane taps open, which kicad-cli DRC reports as
unconnected GND items.

FIRST VERSION WAS UNSAFE -- MEASURED, NOT GUESSED
-------------------------------------------------
v1 dropped a 0.60 mm via at the CENTRE of every unstitched GND pad. That is fine
for a large pad and WRONG for a small one: on a 0402 (pad ~0.5 x 0.6 mm) a 0.60 mm
via overhangs the pad and reaches the neighbouring pad. Isolated by grading the
same board with and without stitching:

    strict route, NO stitching : 937 violations,  0 shorting_items
    strict route, WITH v1 stitch: 980 violations, 26 shorting_items
                                                  14 holes_co_located
                                                  12 drill_out_of_range
So v1 CREATED the shorts. A "fix" that introduces a short is worse than the open
it repairs.

WHAT v2 DOES DIFFERENTLY
  For each candidate GND pad it first asks whether a via of the required size can
  physically sit there WITHOUT violating clearance to any FOREIGN net:
    - candidate centre = pad centre
    - the via occupies a disc of radius (via_d/2 + clearance) for the purpose of
      the test
    - any pad, track segment, or via belonging to a DIFFERENT net whose bounding
      box comes within that disc => REJECT this pad (leave it as it was)
  Only pads that pass are stitched. Nothing is ever moved or deleted.

  It reports rejects explicitly instead of silently shrinking the via, because the
  frozen rule set REQUIRES via >= 0.60 mm -- a "smaller via" would be a fab-floor
  violation, not a fix.

Run:
  python3 stitch_gnd_planes.py <in.kicad_pcb> <out.kicad_pcb> [--via 0.6] [--drill 0.3]
"""
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

VIA_D = 0.6
VIA_DRILL = 0.3
CLEARANCE = 0.2


def mm(v):
    return pcbnew.ToMM(v)


def bbox_of(item):
    bb = item.GetBoundingBox()
    return (mm(bb.GetX()), mm(bb.GetY()),
            mm(bb.GetX() + bb.GetWidth()), mm(bb.GetY() + bb.GetHeight()))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    src, dst = args[0], args[1]
    via_d, drill = VIA_D, VIA_DRILL
    for i, a in enumerate(sys.argv):
        if a == "--via":
            via_d = float(sys.argv[i + 1])
        if a == "--drill":
            drill = float(sys.argv[i + 1])
    r_test = via_d / 2.0 + CLEARANCE

    board = pcbnew.LoadBoard(src)
    if board is None:
        print(f"cannot load {src}")
        return 2

    gcode = None
    for code, net in board.GetNetInfo().NetsByNetcode().items():
        if net.GetNetname() == "GND":
            gcode = code
    if gcode is None:
        print("no GND net")
        return 2

    # --- index every FOREIGN-net item once -------------------------------------
    foreign = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gcode:
                foreign.append(bbox_of(pad))
    for t in board.GetTracks():
        if t.GetNetCode() != gcode:
            foreign.append(bbox_of(t))

    def circle_hits_foreign(cx, cy):
        for (x0, y0, x1, y1) in foreign:
            # closest point of the bbox to the circle centre
            nx = min(max(cx, x0), x1)
            ny = min(max(cy, y0), y1)
            if (cx - nx) ** 2 + (cy - ny) ** 2 < r_test ** 2:
                return True
        return False

    def has_gnd_via_near(cx, cy):
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gcode:
                p = t.GetPosition()
                if (cx - mm(p.x)) ** 2 + (cy - mm(p.y)) ** 2 < 1.0 ** 2:
                    return True
        return False

    added = rejected = already = 0
    rejects = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gcode:
                continue
            ls = pad.GetLayerSet()
            if not (ls.Contains(pcbnew.F_Cu) or ls.Contains(pcbnew.B_Cu)):
                continue
            p = pad.GetPosition()
            cx, cy = mm(p.x), mm(p.y)
            if has_gnd_via_near(cx, cy):
                already += 1
                continue
            if circle_hits_foreign(cx, cy):
                rejected += 1
                rejects.append(f"{fp.GetReference()}.{pad.GetNumber()}")
                continue
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(p)
            v.SetWidth(int(via_d * 1e6))
            v.SetDrill(int(drill * 1e6))
            v.SetNetCode(gcode)
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            board.Add(v)
            added += 1

    pcbnew.SaveBoard(dst, board)
    print(f"stitching vias added     : {added}")
    print(f"pads already stitched    : {already}")
    print(f"pads REJECTED (no room)  : {rejected}")
    if rejects:
        print("  rejected pads:", ", ".join(rejects[:20]),
              ("..." if len(rejects) > 20 else ""))
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
