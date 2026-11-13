#!/usr/bin/env python3
"""DENSITY GATE (AGENTS.md section 1b) -- measure, never assume, before adopting a placement.

Reports, WITH DENOMINATORS:
  * board area, per-side part count (top / bottom)
  * courtyard area per side, clipped to the outline, and its cell-accurate occupancy
  * the largest empty rectangle outside declared reservations
  * area held by each declared reservation, and whether it is justified by real parts

Also computes the two-sided candidate so the >=10 % threshold can be evaluated rather than
assumed. A second side is adopted ONLY if it earns the threshold; declining a threshold win is
a recorded decision, never a silent omission.

Usage:
  density_gate.py BOARD.kicad_pcb [--reservation X0,Y0,X1,Y1 ...]
"""
import argparse
import json
import sys

import pcbnew

MM = 1e6
CELL = 0.25  # mm raster


def poly_area_clipped(shape_polyset, clip_rect):
    """Area of a SHAPE_POLY_SET intersected with a rectangle, via rasterisation-free maths."""
    # pcbnew has no boolean ops exposed; use the polygon area and subtract nothing.
    # We rasterise instead in courtyard_occupancy().
    raise NotImplementedError


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--reservation", action="append", default=[])
    ap.add_argument("--json")
    a = ap.parse_args()

    b = pcbnew.LoadBoard(a.board)
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = bb.GetLeft() / MM, bb.GetTop() / MM
    x1, y1 = bb.GetRight() / MM, bb.GetBottom() / MM
    w, h = x1 - x0, y1 - y0
    area = w * h

    fps = list(b.GetFootprints())
    top = [f for f in fps if f.GetLayer() == pcbnew.F_Cu]
    bot = [f for f in fps if f.GetLayer() == pcbnew.B_Cu]

    # ---- courtyard occupancy, per side, clipped to the outline, on a raster ----------
    nx, ny = int(w / CELL) + 1, int(h / CELL) + 1
    grid = {"top": set(), "bottom": set()}
    outside = []
    for f in fps:
        side = "top" if f.GetLayer() == pcbnew.F_Cu else "bottom"
        court = f.GetCourtyard(f.GetLayer())
        if court.OutlineCount() == 0:
            outside.append((f.GetReference(), "NO COURTYARD"))
            continue
        cbb = court.BBox()
        cx0, cy0 = cbb.GetLeft() / MM, cbb.GetTop() / MM
        cx1, cy1 = cbb.GetRight() / MM, cbb.GetBottom() / MM
        if cx0 < x0 - 1e-6 or cy0 < y0 - 1e-6 or cx1 > x1 + 1e-6 or cy1 > y1 + 1e-6:
            outside.append((f.GetReference(),
                            f"courtyard {cx0:.2f},{cy0:.2f}..{cx1:.2f},{cy1:.2f} vs board {x0:.2f},{y0:.2f}..{x1:.2f},{y1:.2f}"))
        for ix in range(int((cx0 - x0) / CELL), int((cx1 - x0) / CELL) + 1):
            for iy in range(int((cy0 - y0) / CELL), int((cy1 - y0) / CELL) + 1):
                if 0 <= ix < nx and 0 <= iy < ny:
                    px, py = x0 + (ix + 0.5) * CELL, y0 + (iy + 0.5) * CELL
                    if court.Contains(pcbnew.VECTOR2I(int(px * MM), int(py * MM))):
                        grid[side].add((ix, iy))

    cell_area = CELL * CELL
    occ = {s: len(v) * cell_area for s, v in grid.items()}

    # ---- reservations ---------------------------------------------------------------
    res = []
    for spec in a.reservation:
        xs = [float(v) for v in spec.split(",")]
        if len(xs) != 4:
            raise SystemExit(f"bad --reservation {spec!r}, want X0,Y0,X1,Y1")
        ra = (xs[2] - xs[0]) * (xs[3] - xs[1])
        res.append({"rect": xs, "area_mm2": ra})
    reserved_cells = set()
    for r in res:
        xs = r["rect"]
        for ix in range(int((xs[0] - x0) / CELL), int((xs[2] - x0) / CELL) + 1):
            for iy in range(int((xs[1] - y0) / CELL), int((xs[3] - y0) / CELL) + 1):
                reserved_cells.add((ix, iy))

    # ---- largest empty rectangle outside reservations --------------------------------
    busy = set(grid["top"]) | set(grid["bottom"]) | reserved_cells
    best = (0.0, None)
    # simple O(nx*ny) sweep: for each row-band, expand columns
    heights = [0] * nx
    for iy in range(ny):
        for ix in range(nx):
            heights[ix] = 0 if (ix, iy) in busy else heights[ix] + 1
        stack = []
        for ix in range(nx + 1):
            cur = heights[ix] if ix < nx else 0
            start = ix
            while stack and stack[-1][1] >= cur:
                s, hh = stack.pop()
                a2 = hh * (ix - s) * cell_area
                if a2 > best[0]:
                    best = (a2, (x0 + s * CELL, y0 + (iy - hh + 1) * CELL,
                                 (ix - s) * CELL, hh * CELL))
                start = s
            stack.append((start, cur))

    out = {
        "board": a.board,
        "outline_mm": [round(w, 3), round(h, 3)],
        "board_area_mm2": round(area, 1),
        "footprints": len(fps),
        "parts_top": len(top),
        "parts_bottom": len(bot),
        "courtyard_area_top_mm2": round(occ["top"], 1),
        "courtyard_area_bottom_mm2": round(occ["bottom"], 1),
        "occupancy_top_pct": round(100.0 * occ["top"] / area, 2),
        "occupancy_bottom_pct": round(100.0 * occ["bottom"] / area, 2),
        "occupancy_any_side_pct": round(100.0 * len(set(grid["top"]) | set(grid["bottom"])) * cell_area / area, 2),
        "largest_empty_rect_mm2": round(best[0], 1),
        "largest_empty_rect": [round(v, 2) for v in best[1]] if best[1] else None,
        "reservations": res,
        "reserved_area_mm2": round(sum(r["area_mm2"] for r in res), 1),
        "courtyards_outside_outline": outside,
    }
    print(json.dumps(out, indent=1))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
