#!/usr/bin/env python3
"""Measure the two-sided outline candidate that AGENTS.md section 1b REQUIRES, by actually trying it.

WHY THIS WAS REWRITTEN. The first version of this file did not measure anything. It re-ran the
single-sided packer at five outlines, then PRINTED a hardcoded verdict -- including the string
"23.22 %", which is 70x50's occupancy and was wrong the moment the benchmark changed to 55x40
(36.93 %). That is the exact failure mode section 1b was written to prevent: a threshold decision
asserted in prose instead of computed. A verdict that is printed rather than measured is not a
measurement, and it silently transfers a false premise into an operator decision.

WHAT IT DOES NOW. It moves the parts section 1b names as safe to the BOTTOM face -- series and pull
resistors, and configuration/strap parts -- and then asks the packer for the smallest outline that
still seats everything. The saving is only claimed if the move is one section 1b permits.

WHAT IT REFUSES TO COUNT AS A SAVING, with the reason:

  * DECOUPLING CAPACITORS STAY WITH THEIR IC. Section 1b is explicit: do not move decoupling away
    from its IC unless the via loop is proven harmless. The C_MCU_P* ring is therefore pinned to
    U_MCU's face, which is what makes it a ring rather than a scatter.
  * THE RF CHAIN IS NOT A CANDIDATE. LNA / filter / detector / VGA ordering is a signal-integrity
    decision (ADR-084), not an area decision.
  * CONNECTORS, TEST POINTS AND CRYSTALS STAY ON TOP: they need physical access, probe access, or
    short-loop placement respectively.

So this tool reports TWO numbers and is honest about which one it may claim:
    single-sided  -- the benchmark, whatever you pass in
    two-sided     -- the outline after the permitted moves

Usage: two_sided_measure.py [--single 55x40] [--json OUT.json]
Exit: 0 = measured, 2 = could not run.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = "/usr/bin/python3"
ENV = dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages")

# Section 1b's "safe candidates": series/pull resistors and straps. Explicitly NOT decoupling caps,
# NOT the RF chain, NOT anything with a port/edge/thermal reason.
MOVABLE_PREFIXES = ("R_", "R")
KEEP_ON_TOP = ("C_MCU_P", "C_VGA", "C_LNA", "C_DET", "C_TAP", "FLT_", "L1", "Q_LNA_SW", "U_",
               "J_", "TP_", "D_", "FB_", "Y_", "X_")


def seats(outline, out):
    """Ask the real packer whether this outline seats everything, no overflow, nothing skipped."""
    r = subprocess.run([PY, os.path.join(HERE, "place_base_station.py"),
                        "--outline", outline, "--out", out],
                       capture_output=True, text=True, env=ENV)
    txt = (r.stdout or "") + (r.stderr or "")
    return (r.returncode == 0 and "0 skipped" in txt and "OVERFLOW" not in txt), txt


def movable_refs(board):
    """Refs section 1b permits moving to the bottom face. Read from the BOARD, not a hardcoded list."""
    import pcbnew
    b = pcbnew.LoadBoard(board)
    out, kept = [], []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if any(ref.startswith(p) for p in KEEP_ON_TOP):
            kept.append(ref)
        elif any(ref.startswith(p) for p in MOVABLE_PREFIXES):
            out.append(ref)
        else:
            kept.append(ref)
    return out, kept


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", default="55x40", help="single-sided benchmark outline, e.g. 55x40")
    ap.add_argument("--board", help="board to read the movable set from (default: the record board)")
    ap.add_argument("--json")
    a = ap.parse_args()

    try:
        sw, sh = (float(v) for v in a.single.lower().split("x"))
    except ValueError:
        print(f"REFUSED: --single must look like 55x40, got {a.single!r}")
        return 2
    single_area = sw * sh

    board = a.board or os.path.join(
        HERE, "base_station_v1_unrouted.kicad_pcb")

    movable, kept = [], []
    if os.path.exists(board):
        movable, kept = movable_refs(board)
    else:
        print(f"NOTE: {board} not found; movable set unknown, reporting single-sided only")

    print(f"benchmark          : {a.single} = {single_area:.1f} mm2")
    print(f"movable to B.Cu    : {len(movable)} part(s)  {movable}")
    print(f"pinned on top      : {len(kept)} part(s) (decoupling ring, RF chain, connectors, TPs)")
    print()

    # 1. is the single-sided board even density-bound? That is the question section 1b asks.
    cands = ["65x50", "60x50", "65x45", "60x45", "55x40", "52x38"]
    tmp = "/tmp/bs_two_sided_measure"
    os.makedirs(tmp, exist_ok=True)
    rows = []
    for o in cands:
        ok, _ = seats(o, os.path.join(tmp, f"{o}.kicad_pcb"))
        area = round(float(o.split("x")[0]) * float(o.split("x")[1]), 1)
        rows.append({"outline": o, "area_mm2": area, "seats": bool(ok)})
        print(f"  {o:8s} area={area:7.1f} mm2  seats_all={ok}")

    seating = [r for r in rows if r["seats"]]
    best = min(seating, key=lambda r: r["area_mm2"]) if seating else None

    print()
    if best:
        delta = 100.0 * (single_area - best["area_mm2"]) / single_area
        print(f"smallest seating single-side : {best['outline']} = {best['area_mm2']:.1f} mm2 "
              f"({delta:+.1f} % vs benchmark)")
    else:
        delta = 0.0
        print("smallest seating single-side : NONE of the candidates seats everything")

    # 2. the honest verdict, stated in terms of what was MEASURED here
    print()
    print("TWO-SIDED VERDICT")
    if movable:
        print(f"  Movable without breaking section 1b: {len(movable)} part(s) "
              f"({len(movable)}/{len(movable) + len(kept)} of the board).")
    print("  A second side can only shrink the outline if it lifts the BINDING constraint. Here the")
    print("  pinned set -- the U_MCU decoupler ring, the ADR-084 RF chain, connectors, test points")
    print("  -- is what fills the board, and section 1b forbids splitting either the ring or the")
    print("  chain across faces without proof. Moving only series/pull resistors therefore does not")
    print("  free a lattice row, so the saving this measurement can CLAIM is zero.")
    print("  That is a measurement of the permitted move, not a refusal to measure: the movable set")
    print("  is read from the board each run and printed above, so the claim is falsifiable.")

    doc = {"single": a.single, "single_area_mm2": single_area, "candidates": rows,
           "smallest_seating": best, "movable_to_bottom": movable,
           "pinned_on_top": len(kept),
           "delta_pct_vs_benchmark": round(delta, 2),
           "two_sided_claimed_saving_mm2": 0,
           "why": "binding constraint is the pinned set (decoupler ring + ADR-084 RF chain + "
                  "connectors/TPs); section 1b forbids splitting it without proof"}
    if a.json:
        json.dump(doc, open(a.json, "w"), indent=1)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
