#!/usr/bin/env python3
"""hub_array_overhang_model.py — arithmetic behind
docs/analysis/hub-array-overhang-and-support.md and the ADR-055 amendment (2026-10-08).

Every constant is CITED to an in-repo source (named inline) or COMPUTED here.
NO material strength, allowable or modulus is invented: the one property used
(Si elastic modulus 170 GPa) is the value already carried as "standard" in
docs/analysis/hub-thickness-deflection.md §3. The cell's flexural STRENGTH is
NOT in the repo and is NOT assumed — the script prints the DEMAND as a function
of span and says so.

Run:  python3 docs/analysis/hub_array_overhang_model.py
"""
from __future__ import annotations

import itertools

# ---------------------------------------------------------------- constants
G = 9.80665            # m/s^2
RHO_SI = 2330.0        # kg/m^3   crystalline Si (physical constant)
E_SI = 170e9           # Pa       Si modulus — docs/analysis/hub-thickness-deflection.md §3 ("standard")
T_CELL = 0.21e-3       # m        cell thickness — operator caliper (0.20-0.21 mm)

# LARGE cell — ADR-049 Measured inputs; ADR-051 §1.4
LW, LH = 78.55e-3, 38.90e-3
L_AREA = LW * LH                       # m^2
L_MASS = L_AREA * T_CELL * RHO_SI      # kg

# SMALL cell — docs/analysis/wing-mass-shape.md §1.2
SW, SH = 52.07e-3, 19.65e-3
S_AREA = SW * SH
S_MASS = S_AREA * T_CELL * RHO_SI

# FR4 areal masses — docs/analysis/wing-mass-shape.md §2.1 (CITED)
FR4_06 = 127.65e-3     # g/cm^2
FR4_04 = 85.10e-3      # g/cm^2
CELL_AREAL = 48.93e-3  # g/cm^2  0.21 mm bare Si (2.33 g/cm^3 * 0.021 cm)

# Measured structural masses — docs/analysis/wing-mass-shape.md §1.4 (per wing; array = x4)
WING_FULL, WING_SPINE, WING_HARNESS = 7.300, 3.212, 2.088   # g
ARR_FULL, ARR_SPINE, ARR_HARNESS = 29.201, 12.846, 8.352    # g
WING_FULL_BOARD, WING_SPINE_BOARD = 5.709, 1.620            # g  (PCB only)
WING_FULL_AREA, WING_SPINE_AREA = 4472.0, 1269.1            # mm^2 (PCB area)
RIBS_FRACTION = WING_SPINE_AREA / WING_FULL_AREA            # 0.284 measured

# v9 hub placement measurement — tracker/hardware/PLACEMENT-S0-FREEZE-v9-hub.md §3
COMPONENT_COURTYARD_MM2 = 2582.0    # measured courtyard demand of the 39 placed components
BOARD_55x45_MM2 = 55.0 * 45.0       # 2475
USABLE_55x45_MM2 = 2279.0           # interior after edge-seated interfaces

# ADR-055 / ADR-051 targets
ARR_TARGET_CM2 = 106.1              # horizontal day-mean requirement, 0.388 W (ADR-051 §1.4)
BOARD_103_CM2 = (103.0 ** 2) / 100.0  # 106.09

# JLCPCB cheap-tier boundary — docs/analysis/jlcpcb-size-tier-quote.md §3 (measured)
CHEAP_MAX_SIDE_MM = 102.0


def f(x: float, n: int = 3) -> str:
    return f"{x:,.{n}f}"


# ------------------------------------------------------- 1. cell tiling search
def max_cells(container_w: float, container_h: float, w: float, h: float) -> int:
    """Exact max count of identical axis-aligned rectangles (either orientation)
    packable in the container. Bottom-left candidate-position recursion; area-pruned."""
    eps = 1e-9
    orients = [(w, h)] if abs(w - h) < eps else [(w, h), (h, w)]

    def overlap(a, b):
        return not (a[0] + a[2] <= b[0] + eps or b[0] + b[2] <= a[0] + eps or
                    a[1] + a[3] <= b[1] + eps or b[1] + b[3] <= a[1] + eps)

    best = 0

    def rec(placed):
        nonlocal best
        if len(placed) > best:
            best = len(placed)
        area_used = len(placed) * w * h
        if (container_w * container_h - area_used) < w * h - eps:
            return
        xs = {0.0}
        ys = {0.0}
        for (px, py, pw, ph) in placed:
            xs.add(px + pw)
            ys.add(py + ph)
        for x in sorted(xs):
            for y in sorted(ys):
                for (rw, rh) in orients:
                    if x + rw > container_w + eps or y + rh > container_h + eps:
                        continue
                    cand = (x, y, rw, rh)
                    if any(overlap(cand, p) for p in placed):
                        continue
                    rec(placed + [cand])
        return

    rec([])
    return best


# --------------------------------------------- 2. cell self-weight bending demand
def ss_stress(span_m, t=T_CELL, rho=RHO_SI, g=G):
    """Max surface bending stress, simply-supported beam under its own weight.
    sigma = 3*rho*g*L^2 / (4*t)   (derived; mass = rho*b*t*L, Z = b*t^2/6)."""
    return 3.0 * rho * g * span_m ** 2 / (4.0 * t)


def ss_deflection(span_m, t=T_CELL, rho=RHO_SI, E=E_SI, g=G):
    """Max mid-span deflection, simply-supported under its own weight.
    delta = 5*rho*g*L^4 / (32*E*t^2)   (derived)."""
    return 5.0 * rho * g * span_m ** 4 / (32.0 * E * t ** 2)


def main() -> None:
    print("=" * 78)
    print("BLOCK 1 — cell tiling in a 103 x 103 mm square (ADR-055 D5's board)")
    print("=" * 78)
    for name, (w, h) in {"LARGE 78.55x38.90": (LW * 1e3, LH * 1e3),
                         "SMALL 52.07x19.65": (SW * 1e3, SH * 1e3)}.items():
        n = max_cells(103.0, 103.0, w, h)
        area_cm2 = n * (w * h) / 100.0
        print(f"  {name}: max cells in 103x103 = {n}  -> {area_cm2:.2f} cm^2 "
              f"of {ARR_TARGET_CM2} cm^2 target ({100*area_cm2/ARR_TARGET_CM2:.0f}%)")
    need_large = ARR_TARGET_CM2 / (L_AREA * 1e4)
    need_small = ARR_TARGET_CM2 / (S_AREA * 1e4)
    print(f"  area minimum for 106.1 cm^2: {need_large:.2f} LARGE -> {int(-(-need_large//1))}"
          f" cells ({int(-(-need_large//1))*(L_AREA*1e4):.1f} cm^2)"
          f" ; {need_small:.2f} SMALL -> {int(-(-need_small//1))} cells "
          f"({int(-(-need_small//1))*(S_AREA*1e4):.1f} cm^2)")

    print()
    print("=" * 78)
    print("BLOCK 2 — unsupported-span DEMAND for 0.21 mm bare silicon")
    print("        (no allowable exists in-repo: this is DEMAND, not a verdict)")
    print("=" * 78)
    print(f"  Si modulus used (in-repo, standard): {E_SI/1e9:.0f} GPa ; t = {T_CELL*1e3:.2f} mm")
    print("  simply-supported beam under own weight (the end-only mount is exactly this):")
    print("    span_mm   sigma@1g_MPa  sigma@2g_MPa  delta@1g_um")
    for span in (19.65, 38.90, 52.07, 78.55, 100.0, 103.0):
        s = span * 1e-3
        print(f"    {span:7.2f}   {ss_stress(s)/1e6:8.3f}   {2*ss_stress(s)/1e6:8.3f}"
              f"   {ss_deflection(s)*1e6:8.1f}")
    print("  cantilever (ONE end unsupported = a cell overhanging with no far-end carry):")
    print("    sigma_cant = 4 x sigma_ss ; delta_cant = 9.6 x delta_ss  (derived)")
    s = LW
    print(f"    LARGE cell 78.55 mm: sigma@1g = {4*ss_stress(s)/1e6:.2f} MPa,"
          f" delta@1g = {9.6*ss_deflection(s)*1e6:.0f} um")
    print("  ALLOWABLE: TODO(unverified) — no flexural strength / modulus of rupture for")
    print("  the operator's cell is in the repo or in any datasheet supplied. Per the repo")
    print("  honesty rule this is NOT assumed; the coupon bend test (§13 of")
    print("  hub-thickness-deflection.md, re-named for the span case) supplies kappa_damage.")

    print()
    print("=" * 78)
    print("BLOCK 3 — array area achievable with overhang (board area decoupled)")
    print("=" * 78)
    b = 60.0  # candidate component-driven board side (mm) — see BLOCK 5
    print(f"  array footprint side = board side + 2*overhang ; board = {b:.0f} mm")
    print("    overhang/side_mm  footprint_mm  footprint_cm2  duty-vs-106.1cm2")
    for ov in (0, 8.9, 15, 21.5, 25, 48.6, 50):
        side = b + 2 * ov
        a = side ** 2 / 100.0
        print(f"    {ov:14.1f}  {side:12.1f}  {a:13.1f}  {100*a/ARR_TARGET_CM2:14.0f}%")
    for n in (2, 3, 4, 6):
        print(f"  {n} LARGE cells = {n*L_AREA*1e4:.1f} cm^2 "
              f"= {100*n*L_AREA*1e4/ARR_TARGET_CM2:.0f}% of full duty")

    print()
    print("=" * 78)
    print("BLOCK 4 — mass per candidate arrangement (hub array, 4 LARGE = 122.4 cm^2)")
    print("=" * 78)
    cells_cm2 = 4 * L_AREA * 1e4
    cells_g = 4 * L_MASS * 1e3
    print(f"  cells: {cells_cm2:.1f} cm^2 of 0.21 mm Si = {cells_g:.3f} g")
    print()
    # (a) full carrier: board = array footprint
    for label, areal in (("0.6 mm", FR4_06), ("0.4 mm", FR4_04)):
        board_g = BOARD_103_CM2 * areal
        print(f"  (a) FULL CARRIER, board = array footprint {BOARD_103_CM2:.2f} cm^2,"
              f" {label}: board {board_g:.3f} g + cells {cells_g:.3f} g"
              f" = {board_g+cells_g:.3f} g")
    # (b) skeletonised: windows cut; use the measured wing rib fraction as the
    #     board fraction (the only in-repo number for "board reduced to a frame")
    print(f"  (b) SKELETONISED CARRIER (windows), board = {100*RIBS_FRACTION:.1f}% of footprint"
          f" (measured wing spine/full ratio, wing-mass-shape §1.4)")
    for label, areal in (("0.6 mm", FR4_06), ("0.4 mm", FR4_04)):
        board_g = cells_cm2 * RIBS_FRACTION * areal
        print(f"      {label}: board {board_g:.3f} g + cells {cells_g:.3f} g"
              f" = {board_g+cells_g:.3f} g   (board {cells_cm2*RIBS_FRACTION:.2f} cm^2)")
    # (c) spine + ribs: same measured fraction, quoted as the MEASURED wing array
    print(f"  (c) SPINE + RIBS  — MEASURED for the wing: {ARR_SPINE:.3f} g per 4-arm array")
    print(f"      board {4*WING_SPINE_BOARD:.3f} g ({RIBS_FRACTION*100:.1f}%) + cells"
          f" {4*L_MASS*1e3:.3f} g = {4*WING_SPINE_BOARD + 4*L_MASS*1e3:.3f} g")
    # (d) cells only + harness, separate electronics board
    print(f"  (d) CELLS + RIBBON HARNESS — MEASURED for the wing: {ARR_HARNESS:.3f} g per array")
    el_board_04 = (COMPONENT_COURTYARD_MM2 / 100.0 / 0.72) * FR4_04  # 72% packing
    print(f"      harness {4*WING_HARNESS - 4*WING_SPINE_BOARD:.3f} g (flex+tab)"
          f" + cells {4*L_MASS*1e3:.3f} g + separate electronics board {el_board_04:.3f} g"
          f" = {4*(WING_HARNESS-WING_SPINE_BOARD) + 4*L_MASS*1e3 + el_board_04:.3f} g")

    print()
    print("=" * 78)
    print("BLOCK 5 — component-driven board floor and outline")
    print("=" * 78)
    print(f"  measured component courtyard demand : {COMPONENT_COURTYARD_MM2:.0f} mm^2"
          f" = {COMPONENT_COURTYARD_MM2/100:.2f} cm^2")
    print(f"  the 55x45 mm board (rejected)       : {BOARD_55x45_MM2:.0f} mm^2"
          f" = {BOARD_55x45_MM2/100:.2f} cm^2")
    print(f"  usable interior of the 55x45 board  : {USABLE_55x45_MM2:.0f} mm^2"
          f"  -> required interior packing"
          f" {100*2203.0/USABLE_55x45_MM2:.1f}%  (fails; ADR-055/placement)")
    for p in (0.72, 0.75, 0.80):
        need = COMPONENT_COURTYARD_MM2 / p
        side = need ** 0.5
        print(f"  at {p*100:.0f}% packing: board >= {need:.0f} mm^2"
              f" = {need/100:.2f} cm^2 -> square {side:.1f} mm")
    print("  add the four socket land rows: 4 interfaces x 8 lands x 4.0 x 1.2 mm"
          f" = {4*8*4.0*1.2:.0f} mm^2, plus the 1.0-5.0 mm inboard keep-out band")
    for side in (60.0, 65.0, 70.0):
        a = side ** 2 / 100.0
        print(f"  candidate {side:.0f} x {side:.0f} mm = {a:.2f} cm^2"
              f" ; 0.4 mm board = {a*FR4_04:.3f} g ; 0.6 mm = {a*FR4_06:.3f} g"
              f" ; longest side {side:.0f} mm {'<= ' if side <= CHEAP_MAX_SIDE_MM else '> '}"
              f"{CHEAP_MAX_SIDE_MM:.0f} mm cheap-tier")

    print()
    print("=" * 78)
    print("BLOCK 6 — thickness lever re-quantified at the shrunken outline")
    print("=" * 78)
    for side, label in ((103.0, "103 x 103 (ADR-055 D5)"), (60.0, "60 x 60 (component floor)")):
        a = side ** 2 / 100.0
        prize = a * (FR4_06 - FR4_04)
        print(f"  {label}: {a:.2f} cm^2 -> 0.6->0.4 mm saves {prize:.3f} g"
              f"  ({a*FR4_06:.3f} -> {a*FR4_04:.3f} g)")

    print()
    print("=" * 78)
    print("BLOCK 7 — price-tier consequence")
    print("=" * 78)
    print(f"  measured cheap-tier boundary: largest side <= {CHEAP_MAX_SIDE_MM:.0f} mm"
          f" (JLCPCB '$8 Special Offer' vs '$31.50+' with engineering fee)")
    print("  103 mm 4L 1.6 mm measured $31.60 ; 102 mm $8.00 ; 89 mm $8.00 ; 89 mm 2L $4.00")
    print("  a 60-70 mm outline is far inside the cheap class; 103 mm is over the cliff")


if __name__ == "__main__":
    main()
