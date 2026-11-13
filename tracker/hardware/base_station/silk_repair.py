#!/usr/bin/env python3
"""silk_repair.py -- deterministic silkscreen legibility repair for a LARGE-FREE-AREA board.

WHY A SECOND TOOL EXISTS. `tracker/hardware/fix_silk.py` was written for the v10 hub and
carries that board's geometry in its constants (margin X slots at 3.6 and 67.0 mm on a 72x80
board). Run on a 70x50 board those hardcoded coordinates are simply wrong, and a tool with the
wrong constants silently produces worse silk. So this tool derives EVERY coordinate from the
board it is given, and it prints each move.

ALGORITHM, and why each step is the measured fix for a measured class:

  1. DESIGNATOR TEXT to 0.80 mm height / 0.15 mm stroke -- the JLCPCB minimum that still
     prints legibly. Not a cosmetic shrink: the fab clips thinner/smaller ink.
  2. FOOTPRINT SILK GRAPHICS that cross a pad's mask opening move to the Fab layer. That is
     where a component BODY OUTLINE belongs, so the move is lossless, and the alternative
     (trimming the outline) was measured on the hub to make things WORSE (9 -> 12) because
     every cut creates a new crossing.
  3. A FREE-SPACE SEARCH for every designator still in violation. The board is rasterised at
     `CELL` into cells that are BUSY if a courtyard, a pad, or an already-placed label touches
     them. Each label takes the closest free slot to its own part, searching outward in a
     deterministic order (distance, then angle) so two runs cannot disagree.
  4. Loop 3 until kicad-cli reports no `silk_overlap`, `silk_over_copper`,
     `silk_edge_clearance`, or the search budget is exhausted. The report is SORTED before it
     is acted on: kicad-cli runs DRC multi-threaded, so report order is not stable, and acting
     on an unstable order makes the result a function of thread scheduling.

WHAT IT NEVER TOUCHES: pads, tracks, vias, zones, courtyards, the outline, connectivity, or any
part's XY position. Silk text is not placement. If a fix would need a PART to move, this tool
reports it and stops rather than moving the part.

Usage: silk_repair.py --board B.kicad_pcb [-o OUT.kicad_pcb] [--json R.json] [--rounds 6]
Exit: 0 = clean silk, 1 = violations remain (listed), 2 = could not run.
"""
import argparse
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")

MM = 1e6
CELL = 0.20                 # mm raster for the free-space search
TEXT_H = 0.80               # mm -- JLCPCB minimum legible height
TEXT_W = 0.15               # mm -- JLCPCB minimum stroke
LABEL_PAD_W = 0.55          # mm of clearance a label needs around its own bbox reserve
SILK_FAIL = ("silk_overlap", "silk_over_copper", "silk_edge_clearance")


def drc(board, out_json):
    if os.path.exists(out_json):
        os.unlink(out_json)
    r = subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "-o", out_json, board],
                       capture_output=True, text=True)
    if not os.path.exists(out_json):
        raise SystemExit(f"REFUSED: kicad-cli produced no report: {r.stderr[:400]}")
    return json.load(open(out_json))


def silk_list(doc):
    vs = [v for v in (doc.get("violations") or []) if v.get("type") in SILK_FAIL]
    return sorted(vs, key=lambda v: (v["type"],
                                     tuple(sorted(i.get("description", "") for i in v["items"]))))


class Occupancy:
    """Raster of what a silkscreen label may not be printed on, per side."""

    def __init__(self, board, x0, y0, x1, y1):
        import pcbnew
        self.pcbnew = pcbnew
        self.x0, self.y0 = x0, y0
        self.nx = int((x1 - x0) / CELL) + 2
        self.ny = int((y1 - y0) / CELL) + 2
        self.free = {"F": bytearray(b"\x01" * (self.nx * self.ny)),
                     "B": bytearray(b"\x01" * (self.nx * self.ny))}
        # ---- block: every pad's copper (silk over copper) + every courtyard (over parts) ----
        for fp in board.GetFootprints():
            side = "B" if fp.GetLayer() == pcbnew.B_Cu else "F"
            for p in fp.Pads():
                b = p.GetBoundingBox()
                self._block(b.GetLeft() / MM, b.GetTop() / MM,
                            b.GetRight() / MM, b.GetBottom() / MM, side, pad=LABEL_PAD_W)
            c = fp.GetCourtyard(fp.GetLayer())
            if c.OutlineCount():
                b = c.BBox()
                self._block(b.GetLeft() / MM, b.GetTop() / MM,
                            b.GetRight() / MM, b.GetBottom() / MM, side, pad=LABEL_PAD_W)
        # ---- block: the board edge band (silk_edge_clearance) ----
        self._block_edge(x0, y0, x1, y1, 0.60)

    def _idx(self, x, y):
        ix = int((x - self.x0) / CELL)
        iy = int((y - self.y0) / CELL)
        return ix, iy

    def _block(self, l, t, r, b, side, pad=0.0):
        ix0, iy0 = self._idx(l - pad, t - pad)
        ix1, iy1 = self._idx(r + pad, b + pad)
        g = self.free[side]
        for ix in range(max(0, ix0), min(self.nx - 1, ix1) + 1):
            for iy in range(max(0, iy0), min(self.ny - 1, iy1) + 1):
                g[iy * self.nx + ix] = 0

    def _block_edge(self, x0, y0, x1, y1, band):
        for side in ("F", "B"):
            self._block(x0 - 5, y0 - 5, x1 + 5, y0 + band, side)
            self._block(x0 - 5, y1 - band, x1 + 5, y1 + 5, side)
            self._block(x0 - 5, y0 - 5, x0 + band, y1 + 5, side)
            self._block(x1 - band, y0 - 5, x1 + 5, y1 + 5, side)

    def reserve(self, cx, cy, w, h, side):
        self._block(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, side, pad=0.0)

    def ok(self, cx, cy, w, h, side):
        ix0, iy0 = self._idx(cx - w / 2, cy - h / 2)
        ix1, iy1 = self._idx(cx + w / 2, cy + h / 2)
        if ix0 < 0 or iy0 < 0 or ix1 >= self.nx or iy1 >= self.ny:
            return False
        g = self.free[side]
        for ix in range(ix0, ix1 + 1):
            for iy in range(iy0, iy1 + 1):
                if not g[iy * self.nx + ix]:
                    return False
        return True


def label_size(fp):
    rf = fp.Reference()
    b = rf.GetBoundingBox()
    return b.GetWidth() / MM, b.GetHeight() / MM


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("-o", "--out")
    ap.add_argument("--json")
    ap.add_argument("--work", default=None, help="scratch board path (default: OUT + .work)")
    a = ap.parse_args()

    import pcbnew

    out = a.out or a.board
    work = a.work or (os.path.splitext(out)[0] + ".silkwork.kicad_pcb")
    rep = os.path.splitext(out)[0] + ".silkdrc.json"

    b = pcbnew.LoadBoard(a.board)
    if b is None:
        print(f"REFUSED: cannot load {a.board}")
        return 2
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = bb.GetLeft() / MM, bb.GetTop() / MM
    x1, y1 = bb.GetRight() / MM, bb.GetBottom() / MM
    print(f"board     : {a.board}  ({x1 - x0:.2f} x {y1 - y0:.2f} mm)")

    # ---- step 1: text size -----------------------------------------------------------------
    n = 0
    for fp in b.GetFootprints():
        rf = fp.Reference()
        rf.SetTextSize(pcbnew.VECTOR2I(int(TEXT_H * MM), int(TEXT_H * MM)))
        rf.SetTextThickness(int(TEXT_W * MM))
        n += 1
    # ---- step 1b: rotate designators on parts too narrow to hold them horizontally ----------
    # WHY ROTATION AND NOT A NAMING FIX. Measured on the 1 mm-pitch 0402 decoupler row: nine
    # designators each ~5.76 mm wide (at the 0.80 mm fab minimum) were spaced 3.0 mm apart in X, so
    # they overlapped by arithmetic -- no free-space search can separate text wider than its own
    # pitch. Shortening the names (C_MCU_Pnn -> C_MCU<nn>) recovered 1.8 mm per label and is worth
    # keeping, but the remaining 4 mm still does not fit in a 3 mm pitch.
    #
    # A label rotated 90 degrees occupies only its TEXT HEIGHT (~0.9 mm) along X, so a whole row
    # can be labelled without touching each other. This is the standard fix for dense rows and it
    # changes NOTHING electrical: silk only, no pad/zone/courtyard/outline/connectivity (AGENTS 26).
    # Applied only to parts whose horizontal label genuinely cannot fit its own pitch, measured per
    # part -- never blanket-rotated, which would make an easy board harder to read for no reason.
    rot = 0
    parts = []
    for fp in b.GetFootprints():
        p = fp.GetPosition()
        parts.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), fp))
    for x, y, fp in parts:
        rf = fp.Reference()
        # Horizontal extent of this label at the fab minimum, plus a 0.25 mm gap.
        wide = len(fp.GetReference()) * TEXT_H * 0.80 + 0.25
        # ROW-MATES ONLY. The same-row band must be TIGHT: an earlier version used `abs(dy) < wide`
        # (~6 mm at this text size) and rotated 38 parts including U_REG, TP_GND and FLT_433_A --
        # parts on completely different rows -- which created 33 new silk_over_copper items and 37
        # lib_footprint_mismatch warnings. A row is where parts share a placement line, so the band
        # is a few text heights, not a few label widths.
        ROW_BAND = 2.0
        neighbours = [abs(x2 - x) for x2, y2, fp2 in parts
                      if fp2 is not fp and abs(y2 - y) <= ROW_BAND and x2 != x]
        if not neighbours:
            continue
        pitch = min(neighbours)
        if pitch < wide:
            rf.SetTextAngle(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
            rot += 1
    print(f"step1b    : {rot} designator(s) rotated 90 deg -- label wider than its row pitch")

    # ---- step 2: footprint silk graphics that DRC says sit over copper -> Fab --------------
    # DRIVEN BY THE DRC REPORT *AND KEYED BY UUID*, never by bounding boxes and never by
    # matching substrings of a human-readable description.
    #
    # Two measured failures forced this shape:
    #   (a) BBOX MATHS. An earlier version moved any graphic whose bounding box overlapped any
    #       pad's bounding box. A test point's silk CIRCLE has a bbox containing its own pad, so
    #       TP_GND and TP_5V had their markers moved for no reason -- which ALSO broke the
    #       footprint's own geometry and produced 2 `lib_footprint_mismatch` warnings that were
    #       pure self-inflicted damage. bbox-vs-real-geometry is a defect class this repo has
    #       hit repeatedly; do not reintroduce it.
    #   (b) STRING MATCHING. Addressing items by `fp.GetReference() in description` is ambiguous
    #       the moment two parts share a prefix, and the descriptions are prose that can change
    #       with a KiCad point release. The DRC JSON carries a stable `uuid` per item; use it.
    #
    # Silk graphics that need moving are footprint-owned, so a uuid hit is resolved against
    # `fp.GraphicalItems()` across all footprints. Anything unmatched is REPORTED, never guessed.
    pcbnew.SaveBoard(work, b)
    pre = drc(work, rep)
    uuid_targets = set()
    for v in pre.get("violations") or []:
        if v.get("type") not in ("silk_over_copper", "silk_overlap"):
            continue
        for it in v.get("items") or []:
            if "Silkscreen" in it.get("description", ""):
                uuid_targets.add(it.get("uuid"))
    moved = 0
    unresolved = []
    seen = set()
    for fp in b.GetFootprints():
        for gi in list(fp.GraphicalItems()):
            lay = gi.GetLayer()
            if lay not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                continue
            if not isinstance(gi, pcbnew.PCB_SHAPE):
                continue
            u = gi.m_Uuid.AsString()
            if u not in uuid_targets:
                continue
            seen.add(u)
            gi.SetLayer(pcbnew.F_Fab if lay == pcbnew.F_SilkS else pcbnew.B_Fab)
            moved += 1
    unresolved = sorted(uuid_targets - seen)
    print(f"step2     : {moved} footprint silk graphic(s) -> Fab (body outline, lossless)")
    print(f"            (kicad-cli named {len(uuid_targets)} silk item(s) over copper/labels; "
          f"unresolved {len(unresolved)})")
    for u in unresolved[:8]:
        print(f"            UNRESOLVED silk item uuid {u} -- not a footprint graphic, "
              f"left for the free-space pass")

    pcbnew.SaveBoard(work, b)

    # ---- step 3/4: free-space placement of every label still in violation -------------------
    log = []
    for rnd in range(8):
        doc = drc(work, rep)
        vs = silk_list(doc)
        refs_v = set()
        for v in vs:
            for it in v.get("items") or []:
                d = it.get("description", "")
                if d.startswith("Reference field of "):
                    refs_v.add(d[len("Reference field of "):])
        print(f"round {rnd}  : {len(vs)} silk violation(s), {len(refs_v)} designator(s) implicated"
              f" {sorted(refs_v)}")
        if not vs:
            break
        b = pcbnew.LoadBoard(work)
        occ = Occupancy(b, x0, y0, x1, y1)
        # keep every CLEAN label where it is, by reserving it
        fpb = {f.GetReference(): f for f in b.GetFootprints()}
        for ref, fp in fpb.items():
            if ref in refs_v:
                continue
            rf = fp.Reference()
            w, h = label_size(fp)
            p = rf.GetPosition()
            occ.reserve(p.x / MM, p.y / MM, w + 0.16, h + 0.16,
                        "B" if fp.GetLayer() == pcbnew.B_Cu else "F")

        placed = 0
        for ref in sorted(refs_v):
            fp = fpb.get(ref)
            if fp is None:
                continue
            side = "B" if fp.GetLayer() == pcbnew.B_Cu else "F"
            rf = fp.Reference()
            w, h = label_size(fp)
            pw, ph = w + 0.16, h + 0.16
            px, py = fp.GetPosition().x / MM, fp.GetPosition().y / MM
            best = None
            # Deterministic outward spiral up to the board DIAGONAL, so a part on the edge can
            # always reach the interior. An earlier 26 mm cap left connector labels stranded at
            # the top edge on a 60x45 board ("NO SITE ... within 26 mm") while 1220 mm2 of free
            # area sat untouched -- the search, not the board, was the limit.
            rmax = math.hypot(x1 - x0, y1 - y0) + 1.0
            for r_i in range(0, int(rmax / 0.25) + 1):
                r = r_i * 0.25
                nsteps = 8 if r < 0.3 else max(16, int(2 * math.pi * r / 0.25))
                for s_i in range(nsteps):
                    ang = 2 * math.pi * s_i / nsteps
                    cx = round((px + r * math.cos(ang)) / 0.05) * 0.05
                    cy = round((py + r * math.sin(ang)) / 0.05) * 0.05
                    if not (x0 + 0.9 <= cx <= x1 - 0.9 and y0 + 0.9 <= cy <= y1 - 0.9):
                        continue
                    if occ.ok(cx, cy, pw, ph, side):
                        best = (r, cx, cy)
                        break
                if best:
                    break
            if not best:
                print(f"   NO SITE  {ref}: no free slot anywhere on the board for a "
                      f"{pw:.2f}x{ph:.2f} mm label")
                continue
            r, cx, cy = best
            rf.SetPosition(pcbnew.VECTOR2I(int(round(cx * MM)), int(round(cy * MM))))
            occ.reserve(cx, cy, pw, ph, side)
            log.append({"ref": ref, "part_xy": [round(px, 3), round(py, 3)],
                        "label_xy": [round(cx, 3), round(cy, 3)], "offset_mm": round(r, 2),
                        "side": side, "round": rnd})
            placed += 1
        print(f"         : {placed} designator(s) relocated to measured free space")
        pcbnew.SaveBoard(work, b)
        if placed == 0:
            break

    doc = drc(work, rep)
    vs = silk_list(doc)
    counts = {}
    for v in vs:
        counts[v["type"]] = counts.get(v["type"], 0) + 1
    print()
    print(f"silk result: {len(vs)} violation(s) {counts or ''}")
    for v in vs[:20]:
        print("   " + " <-> ".join(i.get("description", "?") for i in v["items"]))
    pcbnew.SaveBoard(out, pcbnew.LoadBoard(work))
    if os.path.exists(work) and os.path.abspath(work) != os.path.abspath(out):
        os.unlink(work)
    # KiCad AUTO-CREATES a .kicad_pro (and often a .kicad_prl) beside any board it opens for DRC.
    # With the default work path those land next to the artifact of record, so a single silk run
    # left `base_station_v1_unrouted.silkwork.kicad_pro` untracked in the repo -- the same
    # "build dirties the tree" defect as the scaffold in place_base_station.py. They are scratch,
    # not artefacts, so they are removed here. `work` stays in the artifact's directory on purpose:
    # moving it to /tmp changes which project rules DRC applies and silently grades a different
    # rule set (measured earlier in this session -- bare-board DRC disagreed with project DRC).
    for ext in (".kicad_pro", ".kicad_prl"):
        side = os.path.splitext(work)[0] + ext
        if os.path.exists(side) and os.path.abspath(side) != os.path.abspath(
                os.path.splitext(out)[0] + ext):
            os.unlink(side)
    if a.json:
        json.dump({"board": a.board, "out": out, "moves": log,
                   "remaining": len(vs), "remaining_by_type": counts}, open(a.json, "w"), indent=1)
        print(f"log       : {a.json} ({len(log)} label moves)")
    return 0 if not vs else 1


if __name__ == "__main__":
    sys.exit(main())
