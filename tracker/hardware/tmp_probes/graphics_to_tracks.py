#!/usr/bin/env python3
"""Convert net-aware copper GRAPHICS into real tracks.

Why this exists (measured 2026-10-29): an interactive routing pass on the hub
board produced 37 `gr_line` graphics on copper layers carrying a net, instead of
`segment` tracks. KiCad treats such a graphic as conductive, so:

  * connectivity and DRC both look satisfied (no unconnected item names the net);
  * the interactive router will not shove or re-route it;
  * pressing `D`/`M` on it behaves like moving a drawing, not a track;
  * every tool in this repo that walks `board.GetTracks()` -- both maze routers,
    the rip-up pass, the grid/validator tests, the connectivity census -- cannot
    see the net at all, so "routed" is an illusion for automation;
  * selection is governed by the GRAPHICS filter, not the TRACKS filter, which is
    exactly why clicking one of these with only Tracks enabled selects nothing.

The geometry is legal copper and will be fabricated, so the fix is mechanical:
recreate each one as a PCB_TRACK with the same layer, width and endpoints, then
delete the graphic. Arcs are converted by segmenting them, because a track has no
arc form in the format this board uses.

Runs under /usr/bin/python3 (pcbnew lives there), never in-process in pytest.

Usage:
  /usr/bin/python3 tracker/hardware/tmp_probes/graphics_to_tracks.py \
      --board <in.kicad_pcb> --out <out.kicad_pcb> [--apply]
Without --apply it only reports what it would do.
"""
import argparse
import math
import sys

import pcbnew

MM = 1e6
COPPER_LAYERS = {"F.Cu", "B.Cu", "In1.Cu", "In2.Cu"}
ARC_SEGMENTS = 24


def shape_points(shape):
    """Return a polyline approximation of a PCB_SHAPE, in board IU."""
    t = shape.GetShape()
    if t == pcbnew.SHAPE_T_SEGMENT:
        return [shape.GetStart(), shape.GetEnd()]
    if t == pcbnew.SHAPE_T_ARC:
        c = shape.GetCenter()
        s = shape.GetStart()
        r = math.hypot(s.x - c.x, s.y - c.y)
        a0 = math.atan2(s.y - c.y, s.x - c.x)
        sweep = shape.GetArcAngle().AsRadians()
        return [
            pcbnew.VECTOR2I(int(c.x + r * math.cos(a0 + sweep * i / ARC_SEGMENTS)),
                            int(c.y + r * math.sin(a0 + sweep * i / ARC_SEGMENTS)))
            for i in range(ARC_SEGMENTS + 1)
        ]
    if t == pcbnew.SHAPE_T_POLY:
        return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.board)
    todo = []
    skipped = []
    for d in board.GetDrawings():
        layer = board.GetLayerName(d.GetLayer())
        if layer not in COPPER_LAYERS:
            continue
        net = d.GetNetname() if hasattr(d, "GetNetname") else ""
        pts = shape_points(d)
        if not pts or len(pts) < 2:
            skipped.append((layer, net, str(d.GetShape())))
            continue
        todo.append((d, layer, net, pts))

    print(f"copper graphics to convert: {len(todo)}", file=sys.stderr)
    if skipped:
        print(f"skipped (unsupported shape): {len(skipped)}", file=sys.stderr)
        for s in skipped:
            print("   ", s, file=sys.stderr)

    if not args.apply:
        by_net = {}
        for _, layer, net, pts in todo:
            by_net[net] = by_net.get(net, 0) + len(pts) - 1
        for net, n in sorted(by_net.items(), key=lambda kv: -kv[1]):
            print(f"  would create {n:3d} segments on {net or '(no net)'}", file=sys.stderr)
        return 0

    made = 0
    for d, layer, net, pts in todo:
        width = d.GetWidth()
        netcode = d.GetNetCode()
        layercode = d.GetLayer()
        for a, b in zip(pts, pts[1:]):
            tr = pcbnew.PCB_TRACK(board)
            tr.SetStart(a)
            tr.SetEnd(b)
            tr.SetWidth(width)
            tr.SetLayer(layercode)
            tr.SetNetCode(netcode)
            board.Add(tr)
            made += 1
        board.Remove(d)

    pcbnew.SaveBoard(args.out, board)
    print(f"created {made} tracks, removed {len(todo)} graphics -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
