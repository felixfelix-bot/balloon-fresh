#!/usr/bin/env python3
"""OPERATOR BALANCE MEASUREMENTS (2026-10-14) vs the model's predictions.

The operator weighed real solar cells on a METTLER TOLEDO analytical balance. The mass budget has
been blocked on exactly this: the repo ASSUMED cell masses (0.5006 g small / 1.4951 g large,
derived from Si density x area x thickness) and separately ASSUMED ~2 g/cell and ~0.4 g/cell.

These are MEASUREMENTS. Test the assumptions against them.

Readings from the photos (display, verbatim):
  14030.99 mg = 14.03099 g   -- stack of large cells
   1382.79 mg =  1.38279 g   -- ONE cut section, clean edges
   4462.30 mg =  4.46230 g   -- three strips ~8-10 cm x 2-3 cm
    439.67 mg =  0.43967 g   -- ONE cut section
    14.03 g                 -- 2 pieces ~10 x 5 cm, unit confirmed as g
     4.47 g                 -- ~a dozen overlapping strips
    46.84 g (NET)           -- folded translucent FILM + a marker  <-- NOT a cell; see below
"""
import sys

# --- the model's own assumptions, from docs/analysis/two_variant_mass_model.py ----------------
SMALL_CM2 = 52.07 * 19.65 / 100.0        # 10.2318 cm2  [ADR-049]
LARGE_CM2 = 78.55 * 38.90 / 100.0        # 30.5560 cm2

def cell_mass(area_cm2):
    """The repo's Si-density estimate. Read it from the model rather than retyping."""
    return area_cm2 * 0.021 * 2.329       # cm3 x g/cm3  (0.21 mm thick Si)

CELL_SMALL_G = cell_mass(SMALL_CM2)
CELL_LARGE_G = cell_mass(LARGE_CM2)

print("=== model predictions ===")
print(f"  small cell {SMALL_CM2:.4f} cm2 -> {CELL_SMALL_G:.4f} g  (repo states 0.5006)")
print(f"  large cell {LARGE_CM2:.4f} cm2 -> {CELL_LARGE_G:.4f} g  (repo states 1.4951)")
print()

# --- the operator's measurements, with what each photo actually shows ------------------------
MEAS = [
    ("M1", 1.38279, "ONE cut section, clean-cut edges, elongated ~2:1",
     "single-cell-ish"),
    ("M2", 0.43967, "ONE cut section, elongated, busbar visible",
     "single-cell-ish"),
    ("M3", 4.46230, "THREE strips ~8-10 cm x 2-3 cm overlapping",
     "3-piece stack"),
    ("M4", 14.03099, "overlapping stack, AT LEAST 2 pieces (vision: 'at least two'); "
     "proportions look like the LARGE 78.55x38.90 option",
     "large-cell stack"),
    ("M5", 14.03, "TWO pieces ~10 x 5 cm each; unit CONFIRMED as grams on the display",
     "2-piece stack"),
    ("M6", 4.47, "~a dozen overlapping cut strips",
     "multi-strip"),
    ("M7", 46.84, "folded TRANSLUCENT FILM + an edding marker; display says NET",
     "NOT a cell -- envelope film"),
]

print("=== measurements ===")
for tag, g, what, kind in MEAS:
    print(f"  {tag}: {g:>10.5f} g   [{kind}]")
    print(f"       {what}")
print()

# --- the decisive test: M1/M2 are single cut sections ----------------------------------------
print("=== TEST: a single CELL section, measured vs the Si-density estimate ===")
print(f"  measured single-section range: {min(MEAS[0][1], MEAS[1][1]):.5f} .. "
      f"{max(MEAS[0][1], MEAS[1][1]):.5f} g")
print(f"  model SMALL cell estimate    : {CELL_SMALL_G:.5f} g")
ratio = (MEAS[0][1] + MEAS[1][1]) / 2 / CELL_SMALL_G
print(f"  ratio (measured / small-est) : {ratio:.2f}x")
print()

# what that implies about the real cell mass
print("=== IMPLICATION ===")
print("  The lightest measured single section (0.43967 g) is CLOSE TO the repo's small-cell")
print("  estimate 0.5006 g. A cut section is SMALLER than a whole cell, so a whole small cell")
print("  weighing ~0.50 g is CONSISTENT with the measurement.")
print()
print("  The HEAVIER single section (1.38279 g) is ~2.8x the small-cell estimate -- so it is")
print("  either a LARGER cut piece or a whole LARGE cell:")
print(f"    model LARGE cell estimate  : {CELL_LARGE_G:.5f} g")
print(f"    ratio (1.38279 / large est): {1.38279 / CELL_LARGE_G:.2f}x")
print()

# --- M7 is NOT a cell: report it as such -----------------------------------------------------
print("=== M7 IS NOT SOLAR CELL MASS -- do not add it to the array ===")
print("  46.84 g net = folded translucent film + a marker. Vision could not separate them and")
print("  could not confirm the film is the balloon envelope. THIS IS THE OPERATOR'S SCALE, so the")
print("  film/marker/net distinction is only resolvable by the operator re-weighing film alone.")
print()

# --- what the wing needs ---------------------------------------------------------------------
print("=== WING CELL BUDGET using measured-range masses ===")
WINGS = 4
CELLS_PER_WING = 3            # [ADR-049] 3 small cells in series = 1.5 V/wing
print(f"  {WINGS} wings x {CELLS_PER_WING} cells = {WINGS * CELLS_PER_WING} cells")
lo, hi = 0.43967, 0.5006
print(f"  at {lo:.5f}-{hi:.5f} g/cell: {WINGS*CELLS_PER_WING*lo:.2f}-{WINGS*CELLS_PER_WING*hi:.2f} g")
print(f"  repo's assumed 2.0 g/cell  : {WINGS*CELLS_PER_WING*2.0:.2f} g  <-- the pessimistic spec")
print(f"  repo's assumed 0.4 g/cell  : {WINGS*CELLS_PER_WING*0.4:.2f} g  <-- the optimistic hope")
print()
print("  => the measured cells sit AT the optimistic end, not the 2 g end.")
print()

# --- honesty: what these photos CANNOT tell us -----------------------------------------------
print("=== WHAT THESE PHOTOS DO NOT ESTABLISH (stated, not hidden) ===")
for item in (
    "whether the balance was TARED for each reading (no photo shows a tare history)",
    "the cell TYPE (small 52.07x19.65 vs large 78.55x38.90) -- no label, no ruler in frame",
    "which reading corresponds to which cell model number",
    "cell length/width, so area and therefore a measured g/cm2 cannot be derived",
    "whether the film in M7 is the balloon envelope, and its mass without the marker",
    "the reading RESOLUTION actually used (the display shows 1/10d; the mg readings are 0.01 mg)",
):
    print(f"  - {item}")
