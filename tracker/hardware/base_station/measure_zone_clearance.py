"""Measure the TRUE gap between a non-GND pad and the actual GND pour fill.

The DRC report says `actual 0.0000 mm` for all 37 `clearance` items on the base-station
board, and every one of them is a pad against a ZONE. A stale/never-refilled zone reports
pad-vs-zone clearance at the zone OUTLINE, which geometrically contains the pad, so the
reported gap is always exactly 0.0000 regardless of the real pour. This script measures
the real number: distance from each pad's own copper polygon to the zone's FILLED polygon
(with holes), in mm.

Usage:  /usr/bin/python3 measure_zone_clearance.py BOARD.kicad_pcb [drc.json]
"""
import json
import sys

import pcbnew
from shapely.geometry import Polygon
from shapely.ops import unary_union

MM = 1e6


def poly_of(sps):
    """SHAPE_POLY_SET -> shapely MultiPolygon (outer rings minus holes)."""
    out = []
    for i in range(sps.OutlineCount()):
        outer = sps.COutline(i)
        pts = [(outer.CPoint(k).x / MM, outer.CPoint(k).y / MM) for k in range(outer.PointCount())]
        if len(pts) < 3:
            continue
        holes = []
        for h in range(sps.HoleCount(i)):
            hc = sps.CHole(i, h)
            hp = [(hc.CPoint(k).x / MM, hc.CPoint(k).y / MM) for k in range(hc.PointCount())]
            if len(hp) >= 3:
                holes.append(hp)
        try:
            out.append(Polygon(pts, holes))
        except Exception:
            pass
    return unary_union(out) if out else Polygon()


def pad_poly(pad):
    sps = pcbnew.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(
        sps, pad.GetLayer(), 0, pcbnew.FromMM(0.001), pcbnew.ERROR_INSIDE
    )
    return poly_of(sps)


def main():
    board_path = sys.argv[1]
    drc_path = sys.argv[2] if len(sys.argv) > 2 else None
    b = pcbnew.LoadBoard(board_path)

    pads = {}
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            pads[pad.m_Uuid.AsString()] = (fp.GetReference(), pad)

    zones = {}
    for z in b.Zones():
        if not z.IsFilled():
            continue
        zones[z.m_Uuid.AsString()] = z

    targets = []
    if drc_path:
        drc = json.load(open(drc_path))
        for v in drc["violations"]:
            if v["type"] != "clearance":
                continue
            pad_item = zone_item = None
            for it in v["items"]:
                if it["description"].startswith("Pad "):
                    pad_item = it
                elif it["description"].startswith("Zone "):
                    zone_item = it
            if pad_item and zone_item:
                targets.append((pad_item["uuid"], zone_item["uuid"], pad_item["description"]))
    else:
        # all non-GND pads vs every GND zone
        for uuid, (ref, pad) in pads.items():
            if pad.GetNetname() in ("", "GND"):
                continue
            for zu in zones:
                targets.append((uuid, zu, f"Pad {pad.GetNumber()} [{pad.GetNetname()}] of {ref}"))

    print(f"board            {board_path}")
    print(f"filled zones     {len(zones)}")
    print(f"targets          {len(targets)}")
    print()
    hdr = f"{'pad':46s} {'net':14s} {'layer':9s} {'gap_mm':>8s} {'verdict':>10s}"
    print(hdr)
    print("-" * len(hdr))
    worst = []
    for pad_uuid, zone_uuid, desc in targets:
        if pad_uuid not in pads or zone_uuid not in zones:
            print(f"MISSING OBJECT for {desc}")
            continue
        ref, pad = pads[pad_uuid]
        z = zones[zone_uuid]
        zshape = poly_of(z.GetFilledPolysList(z.GetLayer()))
        pshape = pad_poly(pad)
        gap = pshape.distance(zshape) if not zshape.is_empty else float("nan")
        clear = z.GetOwnClearance(z.GetLayer()) / MM
        ok = gap >= clear - 1e-6
        worst.append((gap, ref, pad.GetNumber(), pad.GetNetname(), clear, ok))
        print(
            f"Pad {pad.GetNumber():>3s} of {ref:<28s} {pad.GetNetname():14s} "
            f"{pcbnew.LayerName(pad.GetLayer()):9s} {gap:8.3f} {'PASS' if ok else 'FAIL':>10s}"
        )
    print()
    if worst:
        worst.sort()
        g = worst[0]
        print(
            f"tightest real gap: {g[0]:.3f} mm at {g[1]} pad {g[2]} [{g[3]}], "
            f"zone clearance {g[4]:.3f} mm -> {'PASS' if g[5] else 'FAIL'}"
        )
        print(f"all {len(worst)} measured gaps >= zone clearance: {all(w[5] for w in worst)}")


if __name__ == "__main__":
    main()
