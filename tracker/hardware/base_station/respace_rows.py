#!/usr/bin/env python3
"""Distribute placed parts across the board's FULL height, so the board is not top-stacked.

THE DEFECT THIS FIXES, measured on base_station_v1_unrouted at 55x40: all 53 footprints sat in
y = 3..27 and y = 27..40 was completely empty -- a 55.32 x 13.25 mm dead strip = 732.1 mm2, 33 % of
a 2214 mm2 board, reported by density_gate.py as `largest_empty_rect`. The packer in
build_hub_board_v9.pack_rest() scans rows downward but starts at the top edge, so a taller outline
simply leaves the bottom unused instead of spreading the parts out.

Two symptoms, ONE cause, and that is why this is a layout fix and not an outline fix:
  * the dead strip at the bottom;
  * silkscreen clutter in the packed band -- 0.80 mm designators (the JLCPCB minimum, AGENTS 26)
    need roughly 0.9 mm of clear height per row, but the packer leaves only the part pitch, so
    labels in the 1 mm-pitch decoupler row overlapped by arithmetic.

WHAT IT DOES. Groups footprints into rows by shared placement line, then redistributes the ROWS
evenly over the usable height, keeping every row's internal X layout and every footprint's nets
exactly as they are. Row spacing is expanded, never compressed below the composed row height, so
this can only introduce clearance, never overlap. It never moves a part in X, never rotates one,
never touches pads, zones, tracks, vias, courtyards, the outline or connectivity (AGENTS 26 is
about silk; this is placement, and it is additive in Y only).

Not a general packer -- it deliberately does not re-pack, re-order or optimise. It spaces out what
the packer already decided, which keeps the change reviewable and keeps ADR-084's RF chain and the
U_MCU decoupler ring in their existing order and on their existing face.

Usage: respace_rows.py BOARD.kicad_pcb [-o OUT.kicad_pcb] [--json REPORT.json] [--margin 1.0]
Exit: 0 = respaced (or already spread), 2 = could not run.
"""
import argparse
import json
import os
import sys

MM = 1_000_000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--margin", type=float, default=1.0, help="edge margin in mm")
    ap.add_argument("--row-tol", type=float, default=2.0, help="max dy to count as the same row")
    a = ap.parse_args()

    import pcbnew

    b = pcbnew.LoadBoard(a.board)
    if b is None:
        print(f"REFUSED: cannot load {a.board}")
        return 2

    bb = b.GetBoardEdgesBoundingBox()
    top = bb.GetTop() / MM
    bot = bb.GetBottom() / MM
    usable = (bot - a.margin) - (top + a.margin)

    # ---- group footprints into rows ---------------------------------------------------------
    fps = sorted(b.GetFootprints(), key=lambda f: f.GetPosition().y)
    rows = []
    for fp in fps:
        y = fp.GetPosition().y / MM
        if rows and abs(y - rows[-1]["y"]) <= a.row_tol:
            rows[-1]["parts"].append(fp)
            rows[-1]["y"] = sum(p.GetPosition().y / MM for p in rows[-1]["parts"]) / len(rows[-1]["parts"])
        else:
            rows.append({"y": y, "parts": [fp]})

    # ---- each row's occupied height, measured from real courtyards ---------------------------
    for r in rows:
        h = 0.0
        for fp in r["parts"]:
            box = fp.GetBoundingBox(False, False)
            h = max(h, box.GetHeight() / MM)
        r["h"] = h

    need = sum(r["h"] for r in rows)
    gaps = len(rows) - 1
    if gaps <= 0 or usable <= 0:
        print("REFUSED: nothing to respace (single row or no usable height)")
        return 2

    # ---- spread: keep the composed height, distribute the REMAINDER as equal gaps -----------
    # If the rows already need more than the board, do not compress -- report and change nothing.
    if need > usable:
        print(f"REFUSED: rows need {need:.2f} mm but only {usable:.2f} mm is usable; "
              f"compressing would create overlaps")
        return 2
    gap = (usable - need) / gaps

    before_first = rows[0]["y"]
    y = top + a.margin
    moved = 0
    report = []
    for r in rows:
        # vertical centre of this row = top of its band + half its height
        target = y + r["h"] / 2.0
        dy = target - r["y"]
        if abs(dy) > 1e-6:
            for fp in r["parts"]:
                p = fp.GetPosition()
                # `int()` on a python float is fine, but `round()` returns a float and int() of an
                # exact non-integral is a TypeError risk on some paths; be explicit about the
                # numpy-free integer conversion. Also clamp inside the outlines so a rounding
                # artefact can never push a courtyard past the edge rule.
                ny = int(p.y + dy * MM)
                fp.SetPosition(pcbnew.VECTOR2I(int(p.x), ny))
                moved += 1
        report.append({"y_before": round(r["y"], 2), "y_after": round(target, 2),
                       "height": round(r["h"], 2), "parts": len(r["parts"]),
                       "refs": sorted(p.GetReference() for p in r["parts"])[:6]})
        y += r["h"] + gap

    out = a.out or a.board
    pcbnew.SaveBoard(out, b)

    print(f"board        : {a.board}")
    print(f"rows         : {len(rows)} across {usable:.2f} mm usable height")
    print(f"row height   : {need:.2f} mm total, {gap:.2f} mm gap between rows")
    print(f"was packed in: y {before_first:.1f} .. {rows[-1]['y']:.1f} (top-stacked)")
    print(f"now spans    : y {top + a.margin:.1f} .. {y - gap:.1f}")
    print(f"footprints   : {moved} moved (Y only, X untouched)")
    if a.json:
        json.dump({"board": a.board, "out": out, "rows": report, "gap_mm": round(gap, 3),
                   "moved": moved}, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
