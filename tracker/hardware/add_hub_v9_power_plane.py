#!/usr/bin/env python3
"""add_hub_v9_power_plane.py -- add the missing +3V3 plane on In2.Cu.

WHY (measured 2026-10-12): the hub v9 board enables 4 copper layers but In2.Cu
is EMPTY -- no zone, no tracks. In1.Cu carries a solid GND plane. The result is
that every one of 553 signal segments crowds onto F.Cu, including 50 `+3V3`
and 35 `F33_VCC` power segments; +3V3 is forced to run along the top board edge
at y = 0.38 mm, which is exactly the DRC `copper_edge_clearance` family.

The standard 4-layer JLCPCB stackup is signal / GND / POWER / signal. This
script writes the missing POWER plane, so the rails have an inner layer instead
of fighting the signals for F.Cu area.

Usage:
    add_hub_v9_power_plane.py <board.kicad_pcb> <out.kicad_pcb> [--net +3V3]
"""
import argparse
import sys

import pcbnew


def add_plane(board_path: str, out_path: str, net: str = "+3V3",
              layer: str = "In2.Cu", inset_mm: float = 0.5) -> None:
    board = pcbnew.LoadBoard(board_path)
    mm = 1e6
    lay = board.GetLayerID(layer)
    if lay < 0:
        raise SystemExit(f"layer {layer} not present on {board_path}")

    if any(board.GetLayerName(z.GetLayer()) == layer and z.GetNetname() == net
           for z in board.Zones()):
        print(f"  {layer} already carries a {net} zone -- nothing to do")
        return

    nets = board.GetNetsByName()
    if net not in nets:
        raise SystemExit(f"net {net} not found; available: {sorted(nets.keys())[:12]}")
    netcode = nets[net].GetNetCode()

    # Outline: copy the In1.Cu GND zone's outline. NEVER GetBoardEdgesBounding
    # Box() -- it includes the off-board J_W* slot graphics, so the zone
    # polygon spans kICAD y -5.5..108.5 on a 0..103.15 board. KiCad clips the
    # FILL to the outline (DRC stays clean) but the DSN exporter emits the raw
    # ZONE OUTLINE, and FreeRouting wedges on a plane outside the boundary
    # (measured: 1800 s, no SES; the same board routes in 77 s without it).
    src = None
    for z in board.Zones():
        if board.GetLayerName(z.GetLayer()) == "In1.Cu" and z.GetNetname() == "GND":
            src = z
            break
    if src is None:
        raise SystemExit("no In1.Cu GND zone to copy the proven outline from")

    zone = pcbnew.ZONE(board)
    zone.SetLayer(lay)
    zone.SetNetCode(netcode)
    zone.SetAssignedPriority(0)
    zone.SetIsFilled(False)

    outline = zone.Outline()
    # KiCad 9 pitfall: Outline().Append(x,y) SEGFAULTS while the poly set is
    # empty. NewOutline() first, then append via Outline(idx).
    outline.NewOutline()
    idx = outline.OutlineCount() - 1
    o = outline.Outline(idx)
    src_outline = src.Outline().Outline(0)
    for i in range(src_outline.PointCount()):
        pt = src_outline.CPoint(i)
        o.Append(pt.x, pt.y)
    outline.NormalizeAreaOutlines()
    zone.HatchBorder()

    board.Add(zone)

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())

    ok = pcbnew.SaveBoard(out_path, board)
    if not ok:
        raise SystemExit(f"SaveBoard failed for {out_path}")
    filled = zone.GetFilledArea() / 1e12
    print(f"  added {net} plane on {layer}: {filled:.0f} mm^2 filled -> {out_path}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("board")
    ap.add_argument("out")
    ap.add_argument("--net", default="+3V3")
    ap.add_argument("--layer", default="In2.Cu")
    args = ap.parse_args(argv)
    add_plane(args.board, args.out, net=args.net, layer=args.layer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
