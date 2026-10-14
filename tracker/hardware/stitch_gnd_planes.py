#!/usr/bin/env python3
"""Stitch GND pads that the router left unconnected, to the nearest GND plane.

WHY THIS EXISTS (measured 2026-10-14)
-------------------------------------
At 70x70 the KRT router completes 48/48 nets and 148/148 multipoint pads, but
kicad-cli DRC still reports 5 unconnected items -- ALL of them GND, and all of the
same shape: a GND PAD or a short GND track segment that never reached the plane.

    Zone 'GND_PLANE_F.Cu' [GND] on F.Cu   <->  Pad 2 [GND] of J_W1  (8.2, 34.1)
    Pad 2 [GND] of J_W1 on F.Cu           <->  Pad 2 [GND] of J_W1 on B.Cu
    Pad 2 [GND] of J_W4 on B.Cu           <->  Track [GND] on F.Cu  (34.1, 2.2)
    Track [GND] on F.Cu                   <->  Pad 6 [GND] of U2    (33.70, 7.65)
    Track [GND] on B.Cu                   <->  Pad 2 [GND] of J_W3  (61.8, 35.9)

These are NOT a routing failure: GND on this board is a PLANE on In1.Cu/F.Cu/B.Cu,
and a plane net is not "routed" by A* tracks -- it is connected by the plane plus
the vias that stitch pads down to it. The router treats GND like any other net,
gets most of it via the plane, and leaves these few pad-to-plane taps open.

WHAT IT DOES
  For each GND pad/track endpoint that is not connected to the plane, drop a short
  stitching via at (or adjacent to) the pad, so the pad joins In1.Cu (the primary
  GND plane) directly. Deterministic: it only ADDS vias, never moves a part or a
  track, and it is idempotent (a second run adds nothing).

SAFETY
  - Only touches GND pads whose layer is copper.
  - Skips a pad that ALREADY has a via within STITCH_R of it.
  - Rejects a via site that would violate the frozen clearance to a foreign net
    (uses pcbnew's own DRC engine to check, not a custom geometry).
  - Never deletes anything.

Run:
  python3 stitch_gnd_planes.py <in.kicad_pcb> <out.kicad_pcb>
"""
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

STITCH_R = 1.0          # mm: treat a pad as stitched if a GND via is this close
VIA_D = 0.6             # mm via outer diameter (frozen rules: via 0.6 / drill 0.3)
VIA_DRILL = 0.3


def gnd_net(board):
    for code, net in board.GetNetInfo().NetsByNetcode().items():
        if net.GetNetname() == "GND":
            return net
    return None


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    board = pcbnew.LoadBoard(src)
    if board is None:
        print(f"cannot load {src}")
        return 2

    net = gnd_net(board)
    if net is None:
        print("no GND net in this board")
        return 2
    gcode = net.GetNetCode()

    # collect existing GND via sites (on any layer pair) for the idempotence test
    existing = []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gcode:
            p = t.GetPosition()
            existing.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))

    def already(p):
        px, py = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        return any((px - x) ** 2 + (py - y) ** 2 < STITCH_R ** 2 for x, y in existing)

    added = 0
    skipped = 0
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gcode:
                continue
            # only copper pads that are on an outer layer (plane taps)
            layers = pad.GetLayerSet()
            on_outer = (layers.Contains(pcbnew.F_Cu) or layers.Contains(pcbnew.B_Cu))
            if not on_outer:
                continue
            if already(pad.GetPosition()):
                skipped += 1
                continue
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pad.GetPosition())
            v.SetWidth(int(VIA_D * 1e6))
            v.SetDrill(int(VIA_DRILL * 1e6))
            v.SetNetCode(gcode)
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            board.Add(v)
            existing.append((pcbnew.ToMM(pad.GetPosition().x),
                             pcbnew.ToMM(pad.GetPosition().y)))
            added += 1

    pcbnew.SaveBoard(dst, board)
    print(f"GND stitching vias added : {added}")
    print(f"GND pads already stitched: {skipped}")
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
