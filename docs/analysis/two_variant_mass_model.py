#!/usr/bin/env python3
"""two_variant_mass_model.py — reproducible arithmetic for
docs/analysis/two-variant-mass-budget.md (branch analysis/two-variant-mass-budget).

Stdlib only. Every constant carries its provenance as a comment; every figure the
document quotes is printed here. Nothing is measured; every number is arithmetic on
a cited constant, an in-repo computed figure, or an explicitly labelled ESTIMATE /
TODO(unverified).

Run:  python3 docs/analysis/two_variant_mass_model.py
"""

# --------------------------------------------------------------------------- #
# Provenance legend used in the printout
#   [REPO]  = an in-repo figure (file named)
#   [COMP]  = computed here from cited constants (formula shown inline)
#   [EST]   = labelled estimate by analogy; NOT a datasheet number
#   [TODO]  = unverified; no in-repo source carries it
# --------------------------------------------------------------------------- #

# --- material constants ---------------------------------------------------- #
FR4_DENSITY = 1.85        # g/cm3  [REPO] docs/PAYLOAD-WEIGHT-ESTIMATES.md line 20
FINISH_UPLIFT = 1.15      # +15% for copper/mask/silk [REPO] same line
SI_DENSITY = 2.33         # g/cm3  physical constant (crystalline Si 2.329)
CELL_THICK = 0.021        # cm     [REPO] operator caliper 0.20-0.21 mm

FR4_06 = 0.060 * FR4_DENSITY * FINISH_UPLIFT   # g/cm2
FR4_04 = 0.040 * FR4_DENSITY * FINISH_UPLIFT
FR4_08 = 0.080 * FR4_DENSITY * FINISH_UPLIFT
SI_021 = CELL_THICK * SI_DENSITY               # g/cm2

# --- board areas ----------------------------------------------------------- #
WING_FULL_MM2 = 4472.0    # [REPO] wing-mass-shape.md §1.4 (176x25 + 8x9 tab)
WING_SPINE_MM2 = 1269.1   # [REPO] wing-mass-shape.md §2.3 (spine+ribs)
HUB_BIG_MM2 = 55.15 * 45.15   # [REPO] POWER-BUDGET-V9-D2BE.md §4 (ADR-029)
HUB_SMALL_MM2 = 22.0 * 22.0   # [REPO] hardware-design.md line 13

# --- cells ----------------------------------------------------------------- #
def cell_mass(area_cm2):
    """Bare-silicon mass by area*thickness*density [COMP]."""
    return area_cm2 * CELL_THICK * SI_DENSITY

SMALL_CM2 = 52.07 * 19.65 / 100.0   # 10.2318 cm2 [REPO] ADR-049
LARGE_CM2 = 78.55 * 38.90 / 100.0   # 30.5559 cm2 [REPO] ADR-049
CELL_SMALL_G = cell_mass(SMALL_CM2)
CELL_LARGE_G = cell_mass(LARGE_CM2)

# --- solar / power --------------------------------------------------------- #
ARRAY_PEAK_W = 7.2        # [REPO] ADR-049: 6.0 V x 1.2 A (12 large cells)
ARRAY_CM2 = 366.7         # [REPO] wing-insolation-geometry.md §6 (12 large)
PEAK_DENSITY_MW_CM2 = ARRAY_PEAK_W * 1000.0 / ARRAY_CM2   # 19.63 [COMP]
ROT_FACTOR = 0.305107     # [REPO] wing-insolation-geometry.md §2 (cos h / pi)
AVG_DENSITY_MW_CM2 = PEAK_DENSITY_MW_CM2 * ROT_FACTOR     # 5.99 [COMP]

A_AVG_W = 0.388           # [REPO] POWER-BUDGET-V9-D2BE.md §2 (daylight avg)
B_AVG_W = 0.164 * 1.20    # [COMP] 3.3 V rail only x1.20 allowance (F33 removed)

# --- supercaps ------------------------------------------------------------- #
def cap_energy(C, vhi, vlo):
    return 0.5 * C * (vhi ** 2 - vlo ** 2)


def main():
    print("=" * 74)
    print("CONSTANTS")
    print("=" * 74)
    print(f"0.6 mm FR4  {FR4_06*1000:8.2f} mg/cm2   (repo: 127.6)")
    print(f"0.4 mm FR4  {FR4_04*1000:8.2f} mg/cm2   (repo: 85.1)")
    print(f"0.8 mm FR4  {FR4_08*1000:8.2f} mg/cm2")
    print(f"0.21 mm Si  {SI_021*1000:8.2f} mg/cm2   (repo: 48.9)")
    print(f"ratio FR4(0.6)/Si = {FR4_06/SI_021:.3f}  (repo: 2.61)")

    print()
    print("=" * 74)
    print("PCB PANELS")
    print("=" * 74)
    for name, mm2 in (("wing full carrier", WING_FULL_MM2),
                      ("wing spine+ribs", WING_SPINE_MM2),
                      ("hub 55.15x45.15", HUB_BIG_MM2),
                      ("hub 22x22", HUB_SMALL_MM2)):
        cm2 = mm2 / 100.0
        print(f"{name:20s} {cm2:7.2f} cm2  "
              f"0.6mm {cm2*FR4_06:6.3f} g | 0.4mm {cm2*FR4_04:6.3f} g | "
              f"0.8mm {cm2*FR4_08:6.3f} g")

    print()
    print("=" * 74)
    print("SOLAR DENSITY / AREA")
    print("=" * 74)
    print(f"peak power density  = {ARRAY_PEAK_W} W / {ARRAY_CM2} cm2 "
          f"= {PEAK_DENSITY_MW_CM2:.2f} mW/cm2")
    print(f"rotation factor     = {ROT_FACTOR:.6f}")
    print(f"average density     = {AVG_DENSITY_MW_CM2:.3f} mW/cm2")
    print(f"A hub array area    = 0.388 W / {AVG_DENSITY_MW_CM2/1000:.5f} W/cm2 "
          f"= {A_AVG_W*1000/AVG_DENSITY_MW_CM2:.1f} cm2   (task: ~65)")
    print(f"B hub array area    = {B_AVG_W:.3f} W / {AVG_DENSITY_MW_CM2/1000:.5f} W/cm2 "
          f"= {B_AVG_W*1000/AVG_DENSITY_MW_CM2:.1f} cm2")
    print(f"B/A average power   = {B_AVG_W/A_AVG_W:.3f}  (F33 removed)")

    print()
    print("=" * 74)
    print("CELLS")
    print("=" * 74)
    print(f"small cell {SMALL_CM2:.4f} cm2  {CELL_SMALL_G:.4f} g (repo 0.5006)")
    print(f"large cell {LARGE_CM2:.4f} cm2  {CELL_LARGE_G:.4f} g (repo 1.4951)")
    print(f"12 large cells        = {12*CELL_LARGE_G:6.2f} g (repo: 18.0)")
    print(f"12 small cells        = {12*CELL_SMALL_G:6.2f} g (repo:  6.0)")
    for area in (A_AVG_W * 1000 / AVG_DENSITY_MW_CM2, B_AVG_W * 1000 / AVG_DENSITY_MW_CM2):
        print(f"hub array {area:5.1f} cm2: bare-Si {area*SI_021:5.2f} g | "
              f"@2g/52x19mm cell {area/SMALL_CM2*2.0:5.2f} g | "
              f"cells {area/SMALL_CM2:.2f}")

    print()
    print("=" * 74)
    print("SUPERCAP STORE")
    print("=" * 74)
    for label, C in (("0.47 F single", 0.47), ("1.65 F (2x3.3F series)", 1.65),
                     ("3.3 F (doubled)", 3.3)):
        ef = 0.5 * C * 5.4 ** 2
        e35 = cap_energy(C, 5.4, 3.5)
        e30 = cap_energy(C, 5.4, 3.0)
        print(f"{label:26s} full {ef:6.2f} J | to3.5V {e35:6.2f} J | to3.0V {e30:6.2f} J")
    print()
    print("B2 cap-only runtime at B average (%.3f W):" % B_AVG_W)
    for label, C in (("0.47 F", 0.47), ("1.65 F bank", 1.65)):
        print(f"  {label:12s} to2.5V-drop->3.5V {cap_energy(C,5.4,3.5)/B_AVG_W:6.1f} s | "
              f"to 3.0V {cap_energy(C,5.4,3.0)/B_AVG_W:6.1f} s")
    print(f"  (1.65F @ 1 mW beacon duty = {cap_energy(1.65,5.4,3.5)/0.001/3600:.1f} h)")

    print()
    print("=" * 74)
    print("30 AWG SUSPENSION LINE (0.23 g / 500 mm, [REPO] wing-mass-shape.md §2.4)")
    print("=" * 74)
    mg_per_mm = 0.23 / 500.0
    print(f"  0.23 g/500 mm = {mg_per_mm*1000:.3f} mg/mm")
    print(f"  1.0 m balloon suspension line = {mg_per_mm*1000:.3f} g")


if __name__ == "__main__":
    main()
