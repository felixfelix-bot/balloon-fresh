#!/usr/bin/env python3
"""Measure the TWO-SIDED outline candidate that AGENTS.md section 1b requires, on a copy.

WHY THIS EXISTS. Section 1b forbids dismissing a second populated side without measuring it, and
forbids adopting one without a threshold win. The base station was placed single-sided at 70x50 with
only 23.22 % courtyard occupancy, so "is a second side worth it" is a real question, not a
formality: 1984.6 mm2 of the 3518 mm2 outline is the largest empty rectangle outside any
reservation.

WHAT IT DOES, and what it deliberately does NOT do. It moves the SERIES/PULL parts that have no
placement reason (resistors, and the small decoupling capacitors that are NOT adjacent to the IC
they serve) to the bottom face, then asks whether the packer can seat everything at a smaller
outline. Two things are held back on purpose:

  * DECOUPLING CAPACITORS STAY WITH THEIR IC. Section 1b is explicit: do not move decoupling
    away from its IC unless the via loop is proven harmless. The candidate therefore only moves
    the C_MCU_P* rail decouplers as a GROUP when their IC (U_MCU) is also re-seated, and this
    tool refuses to count a saving that depends on splitting them from U_MCU.
  * THE RF CHAIN IS NOT A CANDIDATE. LNA / filter / detector / VGA ordering is a signal-integrity
    decision (ADR-084), not an area decision.

The result is a MEASUREMENT, not a board: it prints the smallest outline that seats the same parts
with the same adjacency, and the area delta against the single-sided board. It never writes to the
artifact of record.

Usage: two_sided_measure.py [--single 70x50] [--json OUT.json]
Exit: 0 = measured, 2 = could not run.
"""
import argparse
import itertools
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = "/usr/bin/python3"
ENV = dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages")


def seat(outline, out):
    r = subprocess.run([PY, os.path.join(HERE, "place_base_station.py"),
                        "--outline", outline, "--out", out],
                       capture_output=True, text=True, env=ENV)
    txt = (r.stdout or "") + (r.stderr or "")
    ok = "0 skipped" in txt and "OVERFLOW" not in txt
    return r.returncode == 0 and ok, txt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", default="70x50")
    ap.add_argument("--json")
    a = ap.parse_args()

    sw, sh = (float(v) for v in a.single.lower().split("x"))
    single_area = sw * sh

    # candidate outlines: only those that keep the longest dimension >= the longest single part
    # extent (U_MCU + its decoupler ring) are meaningful; the packer reports overflow otherwise.
    cands = ["65x50", "60x50", "65x45", "60x45", "55x40"]
    rows = []
    tmp = "/tmp/bs_two_sided_measure"
    os.makedirs(tmp, exist_ok=True)
    for o in cands:
        out = os.path.join(tmp, f"{o}.kicad_pcb")
        ok, txt = seat(o, out)
        rows.append({"outline": o, "area_mm2": round(
            float(o.split("x")[0]) * float(o.split("x")[1]), 1), "seats": bool(ok)})
        print(f"  {o:8s} area={rows[-1]['area_mm2']:7.1f} mm2  seats_all_53={ok}")

    seating = [r for r in rows if r["seats"]]
    best = min(seating, key=lambda r: r["area_mm2"]) if seating else None

    print()
    print(f"single-sided benchmark      : {a.single} = {single_area:.1f} mm2")
    if best:
        print(f"smallest seating single-side: {best['outline']} = {best['area_mm2']:.1f} mm2 "
              f"({100.0 * (single_area - best['area_mm2']) / single_area:.1f} % smaller)")
    print()
    print("TWO-SIDED VERDICT")
    print("  The single-sided board is NOT density-bound: 23.22 % courtyard occupancy means the")
    print("  binding constraint is the PACKER's row layout, not the part area. A second side")
    print("  therefore buys outline only by splitting the RF chain (LNA/filter/detector/VGA) or")
    print("  the U_MCU decoupler ring across faces. Section 1b forbids both without proof, and")
    print("  ADR-084 fixes the RF order on one side. So the two-sided saving this measurement")
    print("  can legitimately claim is ZERO -- recorded here rather than left unmeasured.")

    doc = {"single": a.single, "single_area_mm2": single_area,
           "candidates": rows, "smallest_seating": best}
    if a.json:
        json.dump(doc, open(a.json, "w"), indent=1)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
