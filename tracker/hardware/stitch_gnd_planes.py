#!/usr/bin/env python3
"""Stitch v3 -- OFFSET stitching vias with a stub, for pads with no room at centre.

WHY v3 EXISTS (measured 2026-10-14)
-----------------------------------
v2 asked "does a 0.60 mm via fit AT THE PAD CENTRE?" and correctly REJECTED 63 pads
where it does not. That was the right safety call, but it left 4 pads unconnected --
pads on C_MON, J_W1, J_W3 and C_HF that the router had already given a short GND
stub track, and which the v2 check would not stitch.

The correct fix is not to shrink the via (a sub-0.60 mm via would violate the frozen
rule set) and not to accept the open. It is to put the SAME 0.60 mm via SOMEWHERE
THAT FITS and join it to the pad with a short GND track. A GND stub plus an offset
via is a normal, manufacturable plane tap.

WHAT v3 DOES
  For every GND pad not already stitched:
    1. search outward on a 0.25 mm ring (r = 0.6 .. 4.0 mm) around the pad centre for
       a via position that clears every FOREIGN net by (via_d/2 + clearance)
    2. if found, drop the via there AND add a GND track from the pad to the via
    3. if no position on any ring qualifies, report the pad as UNRESOLVABLE rather
       than silently leaving it (so the remaining count is honest)

  It never moves a part, never deletes, and never shrinks the via. It is idempotent:
  a pad within 1.0 mm of an existing GND via is left alone.

Run:
  python3 stitch_gnd_planes.py <in.kicad_pcb> <out.kicad_pcb>            # v2 behaviour
  python3 stitch_gnd_planes.py <in.kicad_pcb> <out.kicad_pcb> --offset   # v3
"""
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

VIA_D = 0.6
VIA_DRILL = 0.3
CLEARANCE = 0.2
TRACK_W = 0.2
RING_STEP = 0.25
R_MAX = 4.0


def mm(v):
    return pcbnew.ToMM(v)


def bbox_of(item):
    bb = item.GetBoundingBox()
    return (mm(bb.GetX()), mm(bb.GetY()),
            mm(bb.GetX() + bb.GetWidth()), mm(bb.GetY() + bb.GetHeight()))


def main():
    argv = sys.argv[1:]
    offset_mode = "--offset" in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    src, dst = args

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

    foreign = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gcode:
                foreign.append(bbox_of(pad))
    for t in board.GetTracks():
        if t.GetNetCode() != gcode:
            foreign.append(bbox_of(t))

    r_test = VIA_D / 2.0 + CLEARANCE

    def free(cx, cy):
        for (x0, y0, x1, y1) in foreign:
            nx = min(max(cx, x0), x1)
            ny = min(max(cy, y0), y1)
            if (cx - nx) ** 2 + (cy - ny) ** 2 < r_test ** 2:
                return False
        return True

    def near_gnd_via(cx, cy):
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gcode:
                p = t.GetPosition()
                if (cx - mm(p.x)) ** 2 + (cy - mm(p.y)) ** 2 < 1.0 ** 2:
                    return True
        return False

    added_here = added_offset = already = unresolvable = 0
    bad = []

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gcode:
                continue
            ls = pad.GetLayerSet()
            if not (ls.Contains(pcbnew.F_Cu) or ls.Contains(pcbnew.B_Cu)):
                continue
            p = pad.GetPosition()
            cx, cy = mm(p.x), mm(p.y)
            if near_gnd_via(cx, cy):
                already += 1
                continue

            if free(cx, cy):
                site, off = (cx, cy), False
            elif offset_mode:
                site = None
                ring = VIA_D / 2.0 + CLEARANCE
                while ring <= R_MAX and site is None:
                    n = max(8, int(2 * math.pi * ring / 0.2))
                    for k in range(n):
                        a = 2 * math.pi * k / n
                        tx, ty = cx + ring * math.cos(a), cy + ring * math.sin(a)
                        if free(tx, ty):
                            site = (tx, ty)
                            break
                    ring += RING_STEP
                off = True if site else False
                if site is None:
                    unresolvable += 1
                    bad.append(f"{fp.GetReference()}.{pad.GetNumber()}")
                    continue
            else:
                unresolvable += 1
                bad.append(f"{fp.GetReference()}.{pad.GetNumber()}")
                continue

            sx, sy = site
            # stub track from the pad to the via, when offset
            if off:
                tr = pcbnew.PCB_TRACK(board)
                tr.SetStart(pcbnew.VECTOR2I(int(round(cx * 1e6)), int(round(cy * 1e6))))
                tr.SetEnd(pcbnew.VECTOR2I(int(round(sx * 1e6)), int(round(sy * 1e6))))
                tr.SetWidth(int(TRACK_W * 1e6))
                tr.SetLayer(pcbnew.F_Cu)
                tr.SetNetCode(gcode)
                board.Add(tr)

            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(int(round(sx * 1e6)), int(round(sy * 1e6))))
            v.SetWidth(int(VIA_D * 1e6))
            v.SetDrill(int(VIA_DRILL * 1e6))
            v.SetNetCode(gcode)
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            board.Add(v)

            if off:
                added_offset += 1
            else:
                added_here += 1

    pcbnew.SaveBoard(dst, board)
    print(f"vias at pad centre      : {added_here}")
    print(f"vias OFFSET + GND stub  : {added_offset}")
    print(f"pads already stitched   : {already}")
    print(f"UNRESOLVABLE            : {unresolvable}")
    if bad:
        print("  unresolved pads:", ", ".join(bad[:20]))
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
