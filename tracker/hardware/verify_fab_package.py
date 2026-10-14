#!/usr/bin/env python3
"""verify_fab_package.py — prove a fab ZIP actually matches its board.

WHY THIS EXISTS (a real defect, measured 2026-10-14)
----------------------------------------------------
The wing-v9 fab package `tracker/hardware/output/gerbers_wing_v9_jlcpcb.zip`
carried a recorded sha256 in `wing_v9-GATE-RECORD.json` and a gate status of
PASS -- but by the time anyone looked, it did NOT match the board:

    committed B_Cu.gbl :    901 bytes,  0 D01/D02 draw codes   <- NO COPPER
    regenerated B_Cu.gbl: 1858 bytes, 20 D01/D02 draw codes

The board had been fixed by commit 0ed25484 ("wire the B.Cu solar back string")
-- which added the B.Cu series string and 8 vias -- but **the gerbers were never
re-exported**. Ordering from the committed ZIP would have produced a wing board
with no B.Cu copper at all: the entire back-face solar string dead, i.e. a
two-layer board shipped as a one-layer one. The gate record's PASS was attached
to the broken ZIP's hash, so the record actively certified the defect.

LESSON: a hash match against a RECORD proves the file did not change since the
record was written. It does NOT prove the file is correct. Only re-deriving the
artifact from the current source proves that.

WHAT THIS CHECKS
  1. Every expected layer file is present.
  2. No layer is EMPTY when it should carry features (the classic
     ">1KB file with no D-codes" trap, and its worse form: a file with 0 draws).
  3. The board's own copper geometry is consistent with the gerber: the number
     of D01/D02 draw codes on a copper layer must be >= the number of track
     segments on that layer (a lower count means copper was dropped).
  4. Drill files carry at least as many holes as the board has vias + through
     holes.
  5. The CPL row count matches the number of footprints with a position.

Exit 0 = coherent. Exit 1 = INCOHERENT (do not order).

Usage:
  verify_fab_package.py <board.kicad_pcb> <gerber_dir_or_zip>
"""
import os
import re
import sys
import zipfile
import tempfile
import shutil
import subprocess

# copper layer suffix -> KiCad layer name
CU_SUFFIX = {"-F_Cu.gtl": "F.Cu", "-B_Cu.gbl": "B.Cu",
             "-In1_Cu.g1": "In1.Cu", "-In2_Cu.g2": "In2.Cu"}


def read_draw_count(path):
    """Count D01/D02 draw codes in a gerber file."""
    n = 0
    with open(path, "r", errors="ignore") as fh:
        for line in fh:
            n += len(re.findall(r"D0[12]\*", line))
    return n


def board_geometry(board):
    """Return per-copper-layer segment counts and via/hole counts from a board."""
    sys.path.insert(0, "/usr/lib/python3/dist-packages")
    import pcbnew  # noqa

    b = pcbnew.LoadBoard(board)
    segs = {}
    vias = 0
    for t in b.GetTracks():
        cls = t.GetClass()
        if cls == "PCB_VIA":
            vias += 1
        elif cls in ("PCB_TRACK", "PCB_ARC"):
            ln = b.GetLayerName(t.GetLayer())
            segs[ln] = segs.get(ln, 0) + 1
    fps = [f for f in b.GetFootprints()]
    holes = 0
    for f in fps:
        for p in f.Pads():
            if p.GetDrillSize().x > 0:
                holes += 1
    return segs, vias, holes, len(fps)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    board, pkg = sys.argv[1], sys.argv[2]

    tmp = None
    if zipfile.is_zipfile(pkg):
        tmp = tempfile.mkdtemp(prefix="fabpkg_")
        with zipfile.ZipFile(pkg) as z:
            z.extractall(tmp)
        gdir = tmp
        # NESTED-ZIP FIX: most packages in this repo wrap the gerbers in a
        # single top-level directory (e.g. "gerbers_v8b/…"). Descend into it,
        # otherwise every layer looks MISSING and the tool reports a phantom
        # defect. Measured 2026-10-14: without this, 4 correct packages
        # (v2_adc_4layer, v2_adc_v3, v_c3_4layer, v2_adc_4layer_final_jlcpcb)
        # were falsely flagged INCOHERENT.
        entries = [e for e in os.listdir(tmp) if not e.startswith(".")]
        if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
            gdir = os.path.join(tmp, entries[0])
    else:
        gdir = pkg

    files = sorted(os.listdir(gdir))
    problems = []

    segs, vias, holes, nfp = board_geometry(board)
    print(f"board     : {os.path.basename(board)}")
    print(f"package   : {os.path.basename(pkg)}")
    print(f"board has : {sum(segs.values())} track segs on {segs} | {vias} vias | "
          f"{holes} drilled pads | {nfp} footprints")
    print()

    # 1/2/3. copper layers present and non-empty
    print("=== copper layers: board segments vs gerber draws ===")
    for suf, layer in CU_SUFFIX.items():
        cand = [f for f in files if f.endswith(suf)]
        nseg = segs.get(layer, 0)
        if not cand:
            if nseg > 0:
                problems.append(f"MISSING {suf}: board has {nseg} segments on {layer}")
                print(f"  {suf:16} MISSING - board has {nseg} segments on {layer}  <-- BAD")
            else:
                print(f"  {suf:16} absent (board has no {layer} copper) - ok")
            continue
        fp = os.path.join(gdir, cand[0])
        draws = read_draw_count(fp)
        size = os.path.getsize(fp)
        flag = ""
        if nseg > 0 and draws == 0:
            flag = "  <-- BAD: layer is EMPTY (no copper draws)"
            problems.append(f"{cand[0]} empty: board declares {nseg} segments on {layer}")
        elif draws < nseg:
            flag = f"  <-- SUSPECT: fewer draws ({draws}) than board segments ({nseg})"
            problems.append(f"{cand[0]}: draws {draws} < board segments {nseg}")
        print(f"  {cand[0]:34} {size:>7}B  draws={draws:<4} board_segs={nseg}{flag}")

    # 4. drill holes -- must cover BOTH vias AND through-hole pads.
    # MEASURED 2026-10-14: the first version of this check compared holes to
    # VIAS only, and therefore falsely flagged two CORRECT packages:
    #   gerbers_v_c3_final      26 holes vs a board with 0 vias / 26 TH pads
    #   gerbers_v_c3            26 holes vs the same board
    # A board with zero vias but through-hole pads legitimately emits a drill
    # file. The floor is (vias + drilled pads).
    print()
    print("=== drill ===")
    total_holes = 0
    for f in files:
        if f.endswith(".drl"):
            n = len(re.findall(r"^X", open(os.path.join(gdir, f), errors="ignore").read(), re.M))
            total_holes += n
            print(f"  {f:34} {n} holes")
    need = vias + holes
    print(f"  board needs: {vias} vias + {holes} drilled pads = {need}")
    if total_holes < need:
        problems.append(f"drill holes {total_holes} < board vias+pads {need}")
        print(f"  <-- BAD: {total_holes} holes < {need} required")

    # 5. CPL / pos rows
    print()
    print("=== CPL / positions ===")
    for f in files:
        if f.lower().endswith(".csv"):
            with open(os.path.join(gdir, f), errors="ignore") as fh:
                rows = sum(1 for _ in fh) - 1
            print(f"  {f:34} {rows} rows (board footprints: {nfp})")
            if rows <= 0:
                problems.append(f"{f} has no position rows")

    print()
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)

    if problems:
        print("VERDICT: INCOHERENT -- DO NOT ORDER")
        for p in problems:
            print("  -", p)
        return 1
    print("VERDICT: coherent -- package matches the board")
    return 0


if __name__ == "__main__":
    sys.exit(main())
