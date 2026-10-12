#!/usr/bin/env python3
"""add_hub_v9_fab_marks.py -- add the 3 fiducials + 3 tooling holes JLCPCB wants.

MEASURED 2026-10-12 (agentee):
  fiducials     -- "no fiducials: JLCPCB puts them on the rails of an assembly
                    panel, place three on the board for a line that assembles"
  tooling-holes -- "no non-plated tooling holes of 1.5 mm or more: JLCPCB wants
                    three for high precision routing"

Both are PURE ADDITIONS placed in corners, so they cannot collide with anything
if the corner cells are checked first.  Deterministic placement, no search.

Fiducial: 1.0 mm copper dot, mask-opened, on F.Cu, no net (**net 0**).
Tooling hole: 1.5 mm NPTH (non-plated) pad with no copper.

Placement: inset 5 mm from each of 3 board corners (the 4th stays free for the
J_W2 socket which pokes out at y=103..109).
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
FID_DIA = 1.0          # fiducial copper diameter, mm
FID_MASK = 2.0         # mask opening, mm
TOOL_DIA = 1.5         # NPTH diameter, mm
INSET = 5.0            # corner inset, mm


def _place_fiducial(b, i, cx, cy):
    """A single round F.Cu pad with a 2 mm mask opening, no net.

    The footprint must be NAMED like `Fiducial` -- agentee's `fiducials` rule
    matches the footprint library name (`LIB_ID`), not the reference: measured
    from `strings agentee` -> "no footprint named like `Fiducial` on the board".
    Setting only the reference left the rule firing with 3 pads placed.
    """
    fp = pcbnew.FOOTPRINT(b)
    fp.SetFPID(pcbnew.LIB_ID("Fiducial", "Fiducial_1mm_Mask2mm"))
    fp.SetReference(f"FID{i}")
    fp.SetValue("Fiducial")
    fp.SetPosition(pcbnew.VECTOR2I(int(cx * MM), int(cy * MM)))
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES |
                     pcbnew.FP_EXCLUDE_FROM_BOM)
    pad = pcbnew.PAD(fp)
    pad.SetNumber("1")
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    pad.SetSize(pcbnew.VECTOR2I(int(FID_DIA * MM), int(FID_DIA * MM)))
    pad.SetPosition(pcbnew.VECTOR2I(int(cx * MM), int(cy * MM)))
    ls = pcbnew.LSET()
    ls.AddLayer(b.GetLayerID("F.Cu"))
    ls.AddLayer(b.GetLayerID("F.Mask"))
    pad.SetLayerSet(ls)
    pad.SetLocalSolderMaskMargin(int((FID_MASK - FID_DIA) / 2 * MM))
    fp.Add(pad)
    b.Add(fp)


def _place_tooling(b, i, cx, cy):
    """A 1.5 mm non-plated through hole, named like `MountingHole`."""
    tfp = pcbnew.FOOTPRINT(b)
    tfp.SetFPID(pcbnew.LIB_ID("MountingHole", "MountingHole_1.5mm"))
    tfp.SetReference(f"TH{i}")
    tfp.SetValue("MountingHole")
    tfp.SetPosition(pcbnew.VECTOR2I(int(cx * MM), int(cy * MM)))
    tfp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES |
                      pcbnew.FP_EXCLUDE_FROM_BOM)
    tpad = pcbnew.PAD(tfp)
    tpad.SetNumber("1")
    tpad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    tpad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    tpad.SetSize(pcbnew.VECTOR2I(int(TOOL_DIA * MM), int(TOOL_DIA * MM)))
    tpad.SetDrillSize(pcbnew.VECTOR2I(int(TOOL_DIA * MM), int(TOOL_DIA * MM)))
    tpad.SetPosition(pcbnew.VECTOR2I(int(cx * MM), int(cy * MM)))
    tls = pcbnew.LSET()
    for ln in ("F.Cu", "B.Cu", "F.Mask", "B.Mask"):
        tls.AddLayer(b.GetLayerID(ln))
    tpad.SetLayerSet(tls)
    tfp.Add(tpad)
    b.Add(tfp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)

    # true board outline, excluding the by-design J_W2/J_W4 off-board slots:
    # use the In1.Cu GND zone outline, which is the proven 0.425..102.575 range.
    x0, y0, x1, y1 = 0.425, 0.425, 102.575, 102.575
    print(f"board cell: ({x0},{y0})..({x1},{y1})")

    corners = [
        (x0 + INSET, y0 + INSET),
        (x1 - INSET, y0 + INSET),
        (x0 + INSET, y1 - INSET),
    ]
    # --- check each corner cell is clear of copper ---------------------------
    def cell_clear(cx, cy, rad):
        r = (rad + 0.5) * MM
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                pos = t.GetPosition()
                if math.hypot(pos.x - cx * MM, pos.y - cy * MM) < r:
                    return False
            else:
                for p in (t.GetStart(), t.GetEnd()):
                    if math.hypot(p.x - cx * MM, p.y - cy * MM) < r:
                        return False
        for f in b.GetFootprints():
            fp = f.GetPosition()
            if math.hypot(fp.x - cx * MM, fp.y - cy * MM) < r:
                return False
            for p in f.Pads():
                # test the pad EXTENT, not its centre -- a 4.0 x 1.2 mm J_W3 pad
                # centred at (100.0,52.4) reaches x=98.0, and testing only the
                # centre let a fiducial land inside it and short J_W3.2.
                bb = p.GetBoundingBox()
                if (bb.GetX() / MM - 0.5 <= cx <= (bb.GetX() + bb.GetWidth()) / MM + 0.5
                        and bb.GetY() / MM - 0.5 <= cy <=
                        (bb.GetY() + bb.GetHeight()) / MM + 0.5):
                    return False
        return True

    added_fid = added_tool = 0
    fid_pts = []
    for i, (cx, cy) in enumerate(corners, 1):
        if not cell_clear(cx, cy, FID_MASK / 2):
            print(f"  corner {i} ({cx},{cy}): NOT clear -- skipped")
            continue
        fid_pts.append((cx, cy))
        _place_fiducial(b, i, cx, cy)
        added_fid += 1
        print(f"  FID{i} @ ({cx},{cy})  {FID_DIA} mm copper, {FID_MASK} mm mask")

    # JLCPCB wants THREE fiducials, widely separated and non-collinear, for a
    # usable datum.  If a corner was blocked, scan the 2 mm grid for the cell
    # farthest from the ones we have (measured: 1869 clear cells on this board).
    #
    # The scan MUST reject the by-design J_W socket slots (Edge.Cuts) as well as
    # copper: the first fallback picked (98.425,52.425) and shorted J_W3.2.
    # Only NARROW slot segments count -- the board outline is itself an Edge.Cuts
    # segment spanning the whole board, so a naive bbox test rejects every cell
    # (measured: fallback found 0 candidates and only 2 fiducials got placed).
    def slot_clear(cx, cy):
        for d in b.GetDrawings():
            if d.GetLayer() != b.GetLayerID("Edge.Cuts"):
                continue
            s, e = d.GetStart(), d.GetEnd()
            w = abs(s.x - e.x) / MM
            h = abs(s.y - e.y) / MM
            if min(w, h) > 0.5:          # board outline / long edge, not a slot
                continue
            if min(s.x, e.x) / MM - 1.0 <= cx <= max(s.x, e.x) / MM + 1.0 and \
               min(s.y, e.y) / MM - 1.0 <= cy <= max(s.y, e.y) / MM + 1.0:
                return False
        return True

    n = max(i for i, _ in enumerate(fid_pts, 1)) + 1
    while len(fid_pts) < 3:
        best = None
        step = 2.0
        gx = x0
        while gx <= x1:
            gy = y0
            while gy <= y1:
                if 4.0 <= gx <= 99.0 and 4.0 <= gy <= 99.0 and \
                        slot_clear(gx, gy) and cell_clear(gx, gy, FID_MASK / 2):
                    d = min(math.hypot(gx - a, gy - b_) for (a, b_) in fid_pts)
                    if best is None or d > best[0]:
                        best = (d, gx, gy)
                gy += step
            gx += step
        if best is None:
            break
        _, cx, cy = best
        fid_pts.append((cx, cy))
        _place_fiducial(b, n, cx, cy)
        added_fid += 1
        print(f"  FID{n} @ ({cx},{cy})  [fallback, "
              f"{best[0]:.1f} mm from nearest]")
        n += 1

    # tooling holes: one near each of the first 3 fiducials, offset inward
    for i, (cx, cy) in enumerate(fid_pts[:3], 1):
        tcx = cx + 4.0 if cx < 50 else cx - 4.0
        tcy = cy + 4.0 if cy < 50 else cy - 4.0
        if not cell_clear(tcx, tcy, TOOL_DIA / 2):
            print(f"    tooling hole @ ({tcx},{tcy}): NOT clear -- skipped")
            continue
        _place_tooling(b, i, tcx, tcy)
        added_tool += 1
        print(f"  TH{i} @ ({tcx},{tcy})  {TOOL_DIA} mm NPTH")

    print(f"fiducials added: {added_fid}   tooling holes added: {added_tool}")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
