#!/usr/bin/env python3
"""Stitch the routed hub v9's fragmented GND zones to the In1.Cu plane.

WHY -- measured 2026-10-12 on hub_board_v9_routed.kicad_pcb (post-refill DRC):
  unconnected_items: 44
    10  F-B castellated pad pairs (Wing_Tab_4P, by design, excluded here)
    17  zone-vs-zone GND fragment pairs
    10  pad-vs-zone GND pairs
     3  pad-pad (U4<->U1 DIO2/MISO duplex nets)
     3  pad-track (solar N)
     1  other
The router cut the F.Cu GND zone into 24 fragments. Fragments do not overlap,
so no single via can join a pair directly -- each fragment gets its OWN via
down to In1.Cu, which is one solid plane (1 filled_polygon) and thus the GND
backbone. B.Cu (2 fragments) gets the same treatment; a through via touches
all copper layers and GND is on F/In1/B.

RULES a stitch via must satisfy (from the board's own DRC values):
  via size 0.6 / drill 0.3 (same as the router's 94 vias)
  >= 0.5 mm from every track centre (0.3 radius + 0.2 clearance)
  >= 0.5 mm from every pad/pad-centre bbox edge  (conservative: pad centre
      distance checked against pad size + 0.5 mm)
  >= 0.8 mm from the board edge (0.3 radius + 0.5 copper-edge clearance)
  >= 1.0 mm from every other via centre (0.3+0.3 radius + 0.2 clearance
      plus slack for the annular ring)
  inside the fragment polygon it stitches (shapely contains)

OUTPUT: a NEW board file (--out); the input board is never modified.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402


def _shapely():
    try:
        from shapely.geometry import Point, Polygon  # noqa: F401
        return True
    except ImportError:
        return False


def fragment_polygons(zone) -> list:
    """Return shapely polygons for each filled fragment of a zone."""
    from shapely.geometry import Polygon
    sps = zone.GetFilledPolysList(zone.GetFirstLayer())
    polys = []
    for i in range(sps.OutlineCount()):
        outl = sps.Outline(i)
        pts = [(p.x / 1e6, p.y / 1e6) for p in outl.CPoints()]
        if len(pts) >= 3:
            polys.append(Polygon(pts))
    return polys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("board", help="routed .kicad_pcb (NOT modified)")
    ap.add_argument("--out", required=True, help="stitched output .kicad_pcb")
    args = ap.parse_args(argv)

    board = pcbnew.LoadBoard(args.board)
    mm = 1_000_000  # nm per mm

    # find GND net by name (v9 API: GetNetClassByName is not a thing; use the
    # netcode map)
    gnd_code = None
    for code, net in board.GetNetsByNetcode().items():
        if net.GetNetname() == "GND":
            gnd_code = code
            break
    if gnd_code is None:
        raise SystemExit("no GND net found")

    # geometry for clearance checks
    tracks = []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK":
            s, e = t.GetStart(), t.GetEnd()
            w = t.GetWidth()
            tracks.append((s.x / mm, s.y / mm, e.x / mm, e.y / mm, w / mm))
    vias = [(v.GetPosition().x / mm, v.GetPosition().y / mm)
            for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
    pads = []  # (x, y, clearance_radius_mm) for every pad on any layer
    for fp in board.GetFootprints():
        for p in fp.Pads():
            c = p.GetCenter()
            size = max(p.GetSizeX(), p.GetSizeY()) / 2 / mm
            pads.append((c.x / mm, c.y / mm, size))
    edge = board.GetBoardEdgesBoundingBox()
    ex0, ey0 = edge.GetX() / mm, edge.GetY() / mm
    ex1, ey1 = (edge.GetX() + edge.GetWidth()) / mm, (edge.GetY() + edge.GetHeight()) / mm

    def seg_dist(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
        return ((px - x1 - t * dx) ** 2 + (py - y1 - t * dy) ** 2) ** 0.5

    def clear(px, py):
        if not (ex0 + 0.8 <= px <= ex1 - 0.8 and ey0 + 0.8 <= py <= ey1 - 0.8):
            return False
        for (x1, y1, x2, y2, w) in tracks:
            if seg_dist(px, py, x1, y1, x2, y2) < 0.5 + w / 2:
                return False
        for (vx, vy) in vias:
            if (px - vx) ** 2 + (py - vy) ** 2 < 1.0 ** 2:
                return False
        for (px2, py2, r) in pads:
            if ((px - px2) ** 2 + (py - py2) ** 2) ** 0.5 < r + 0.5:
                return False
        return True

    # candidate grid per fragment
    placed, failed = [], []
    n_vias_before = len(vias)
    for zone in board.Zones():
        if zone.GetNetCode() != gnd_code:
            continue
        layer = zone.GetLayerName()
        if layer == "In1.Cu":
            continue  # the backbone plane itself
        polys = fragment_polygons(zone)
        if not polys:
            continue
        for poly in polys:
            if poly.area < 0.25:  # mm^2 -- slivers can't host a via
                continue
            x0, y0, x1, y1 = poly.bounds
            done = False
            # 0.5mm raster, interior-first (sample the centroid first)
            cx, cy = poly.centroid.x, poly.centroid.y
            cands = [(cx, cy)]
            yy = y0 + 0.6
            while yy < y1 and not done:
                xx = x0 + 0.6
                while xx < x1:
                    cands.append((xx, yy))
                    xx += 0.5
                yy += 0.5
            for (px, py) in cands:
                if poly.contains(pcbnew_point := __import__("shapely.geometry", fromlist=["Point"]).Point(px, py)) \
                        and not done and poly.contains(__import__("shapely.geometry", fromlist=["Point"]).Point(px, py)) \
                        and clear(px, py):
                    v = pcbnew.PCB_VIA(board)
                    v.SetPosition(pcbnew.VECTOR2I(int(px * mm), int(py * mm)))
                    v.SetTopLayer(pcbnew.F_Cu)
                    v.SetBottomLayer(pcbnew.B_Cu)
                    v.SetWidth(int(0.6 * mm))
                    v.SetDrill(int(0.3 * mm))
                    v.SetNetCode(gnd_code)
                    board.Add(v)
                    placed.append((layer, round(px, 2), round(py, 2)))
                    vias.append((px, py))  # later fragments must clear it too
                    done = True
            if not done:
                failed.append((layer, round(poly.area, 2)))

    if not placed and not failed:
        print("no GND fragments needed stitching")
    for (l, x, y) in placed:
        print(f"  stitch via: {l} fragment @ ({x}, {y})")
    if failed:
        print(f"  WARNING: {len(failed)} fragment(s) too small/congested: {failed}")

    pcbnew.SaveBoard(args.out, board)
    print(f"saved: {args.out} (+{len(placed)} vias, {n_vias_before} -> {len(vias)})")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())