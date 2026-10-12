#!/usr/bin/env python3
"""reassign_hub_v9_power_to_plane.py -- move the +3V3 rail onto the In2.Cu plane.

WHY (measured 2026-10-12 on hub_board_v9_routed_stitched_routed.kicad_pcb):
  +3V3 = 14 SMD pads, 82 F.Cu track segments, only 4 vias.
  SMD pads cannot reach an inner-layer plane directly, so the 82 F.Cu segments
  ARE the rail -- and they crowd the top board edge (DRC copper_edge_clearance
  at y=0.38 mm).  Re-running FreeRouting with an In2 plane present changes
  nothing: FreeRouting routes UNROUTED nets and never restructures existing
  tracks (measured: 16 min wedge vs 77 s, no improvement).

  The mechanical fix: delete the +3V3 F.Cu segments, put a via at every +3V3
  SMD pad, and let the In2.Cu +3V3 plane (added by add_hub_v9_power_plane.py)
  carry the rail.  This is deterministic -- no LLM, no router.

PRECONDITION: the board must already carry the In2.Cu +3V3 zone.  This script
refuses to run otherwise, because deleting the F.Cu rail without a plane would
simply disconnect the rail.
"""
import argparse
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--net", default="+3V3")
    ap.add_argument("--via-mm", type=float, default=0.6)
    ap.add_argument("--drill-mm", type=float, default=0.3)
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.inp)

    # --- precondition: the net's plane must exist on an inner layer ----------
    planes = [(board.GetLayerName(z.GetLayer()), z.GetNetname())
              for z in board.Zones()]
    want = [(lay, net) for (lay, net) in planes if net == args.net]
    if not want:
        print(f"REFUSED: no {args.net} zone on this board -- run "
              f"add_hub_v9_power_plane.py first", file=sys.stderr)
        return 2
    print(f"plane(s) carrying {args.net}: {want}")

    # --- collect +3V3 SMD pads ----------------------------------------------
    netcode = board.FindNet(args.net).GetNetCode() if board.FindNet(args.net) else None
    if netcode is None:
        print(f"REFUSED: net {args.net} not found", file=sys.stderr)
        return 2

    pads = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == netcode and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                pads.append((fp.GetReference(), p))
    print(f"{args.net} SMD pads: {len(pads)}")

    # --- rip up the net's existing F.Cu segments -----------------------------
    # KiCad 9 pitfall: calling board.Remove() while a SWIG reference to the
    # TRACKS container is live SEGFAULTS.  Collect first, drop the container
    # reference, THEN remove.
    doomed = [t for t in board.GetTracks()
              if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == netcode]
    removed = 0
    for t in doomed:
        board.Remove(t)
        removed += 1
    print(f"{args.net} track segments removed: {removed}")

    # --- drop a via at every pad (SMD -> plane) ------------------------------
    # Use a BLIND via F.Cu -> the plane's inner layer.  A THROUGH via would
    # punch B.Cu, where /SCAP_MID, /SCAP_ADC, /SX1280_* signal tracks run --
    # measured 2026-10-12: 3 shorting_items + 4 clearance from exactly that.
    # A blind via stops at the plane and never touches B.Cu.
    plane_layer = None
    for z in board.Zones():
        if z.GetNetname() == args.net:
            plane_layer = z.GetLayer()
            break
    vias = 0
    for ref, p in pads:
        pos = p.GetPosition()
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pos)
        v.SetWidth(int(args.via_mm * MM))
        v.SetDrill(int(args.drill_mm * MM))
        v.SetNetCode(netcode)
        if plane_layer is not None and plane_layer != pcbnew.B_Cu:
            v.SetViaType(pcbnew.VIATYPE_BLIND_BURIED)
            v.SetLayerPair(pcbnew.F_Cu, plane_layer)
        else:
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        board.Add(v)
        vias += 1
    kind = "blind F.Cu->%s" % board.GetLayerName(plane_layer) \
        if plane_layer is not None else "through"
    print(f"vias added at {args.net} SMD pads: {vias} ({kind})")

    board.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
