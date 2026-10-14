#!/usr/bin/env python3
"""MEASURED SOLAR-CELL AND BALLOON MASSES -- operator scale readings, 2026-10-14.

SOURCE: operator statement + 8 balance photographs. Two balances were used:
  - a GRAM balance (0.01 g readability, METTLER TOLEDO XS4002S DeltaRange) for the 10-piece piles
  - a MILLIGRAM balance (0.01 mg readability) for single panels
This is stated explicitly because a 10-piece reading on a 0.01 g balance and a single-panel reading
on a 0.01 mg balance have DIFFERENT resolutions -- the cross-check below depends on knowing which.

OPERATOR-STATED VALUES (authoritative, replace every prior estimate):
  10 LARGE panels : 14.04   g      -> 1.40400 g/panel
   1 large panel  :  1.382 g      -> 1.38200 g
   1 small panel  :  0.440 g      -> 0.44000 g
  10 SMALL panels :  4.462 g      -> 0.44620 g
   balloon (Yokohama) : 46.84 g   <- the M7 photo was THE BALLOON, not "film + marker"

The two panels sizes are the repo's:
  small 52.07 x 19.65 x 0.21 mm  = 10.2318 cm2
  large 78.55 x 38.90 x 0.21 mm  = 30.5559 cm2
"""

# --- measured ---------------------------------------------------------------------------------
M_10_LARGE = 14.04
M_1_LARGE  = 1.382
M_1_SMALL  = 0.440
M_10_SMALL = 4.462
M_BALLOON  = 46.84

per_large_from_10 = M_10_LARGE / 10
per_small_from_10 = M_10_SMALL / 10

# --- the repo's previous estimates (to be retired) --------------------------------------------
def si_mass(area_cm2, t_mm=0.21, rho=2.329):
    return area_cm2 * (t_mm * 0.1) * rho

SMALL_CM2 = 52.07 * 19.65 / 100.0
LARGE_CM2 = 78.55 * 38.90 / 100.0
EST_SMALL = si_mass(SMALL_CM2)
EST_LARGE = si_mass(LARGE_CM2)

print("=" * 78)
print("MEASURED vs ESTIMATED cell mass")
print("=" * 78)
print(f"{'panel':<8} {'single (g)':>12} {'10-piece (g)':>13} {'per-panel (g)':>14} {'Si est (g)':>11} {'meas/est':>9}")
print(f"{'small':<8} {M_1_SMALL:>12.4f} {M_10_SMALL:>13.4f} {per_small_from_10:>14.5f} {EST_SMALL:>11.4f} {M_1_SMALL/EST_SMALL:>9.2f}x")
print(f"{'large':<8} {M_1_LARGE:>12.4f} {M_10_LARGE:>13.4f} {per_large_from_10:>14.5f} {EST_LARGE:>11.4f} {M_1_LARGE/EST_LARGE:>9.2f}x")
print()

# --- internal consistency: do the single and 10-piece readings agree? -------------------------
print("=" * 78)
print("INTERNAL CONSISTENCY -- single reading vs the 10-piece average")
print("=" * 78)
print("This is a REAL test: each size was weighed two independent ways, on two balances.")
print()
d_small = M_1_SMALL - per_small_from_10
d_large = M_1_LARGE - per_large_from_10
print(f"  small: 1-panel {M_1_SMALL:.4f} vs 10-panel avg {per_small_from_10:.5f}")
print(f"         delta {d_small:+.5f} g  ({abs(d_small)/M_1_SMALL*100:.2f} % of the single reading)")
print(f"         NOTE the 10-piece reading is on the GRAM balance (0.01 g), so its per-panel")
print(f"         resolution is 0.001 g -- tighter than the sum's own readability.")
print()
print(f"  large: 1-panel {M_1_LARGE:.4f} vs 10-panel avg {per_large_from_10:.5f}")
print(f"         delta {d_large:+.5f} g  ({abs(d_large)/M_1_LARGE*100:.2f} % of the single reading)")
print()
agree_small = abs(d_small) / M_1_SMALL < 0.02
agree_large = abs(d_large) / M_1_LARGE < 0.02
print(f"  => small panels AGREE within 2 %: {'YES' if agree_small else 'NO'}")
print(f"  => large panels AGREE within 2 %: {'YES' if agree_large else 'NO'}")
print()

# --- retired assumptions ----------------------------------------------------------------------
print("=" * 78)
print("RETIRE THESE (superseded by measurement)")
print("=" * 78)
print(f"  '~2 g per cell'   -> measured is {M_1_LARGE:.3f} g (large) / {M_1_SMALL:.3f} g (small)")
print(f"     for 12 small cells: 2.0 g/cell = {12*2.0:.2f} g vs MEASURED {12*M_1_SMALL:.2f} g"
      f"  -> the spec was {12*2.0/(12*M_1_SMALL):.1f}x too heavy")
print(f"  '~0.4 g/cell thin-film hope' -> measured small is {M_1_SMALL:.3f} g, so the HOPE was")
print(f"     actually CLOSE: {M_1_SMALL/0.4:.2f}x. The cells are already near the thin-film figure.")
print()

# --- the array and the payload ----------------------------------------------------------------
print("=" * 78)
print("WHAT THIS DOES TO THE ARRAY AND THE PAYLOAD")
print("=" * 78)
WINGS = 4
CELLS_PER_WING_SMALL = 3       # [ADR-049] 3 small cells in series = 1.5 V/wing
n_small = WINGS * CELLS_PER_WING_SMALL
array_small = n_small * M_1_SMALL
print(f"  v9 baseline: {WINGS} wings x {CELLS_PER_WING_SMALL} SMALL cells = {n_small} cells")
print(f"    measured array mass = {n_small} x {M_1_SMALL:.3f} = {array_small:.3f} g")
print(f"    (previous model used 0.5006 g/cell -> {n_small*0.5006:.3f} g;"
      f" delta {array_small - n_small*0.5006:+.3f} g)")
print()
print(f"  BALLOON: {M_BALLOON:.2f} g (Yokohama).")
print("    This CLOSES the mass chain's last unknown: the envelope mass is now MEASURED.")
print()

# what the array costs if large cells were used instead
array_large = WINGS * 3 * M_1_LARGE
print(f"  if LARGE cells were used: {WINGS}x3 = 12 x {M_1_LARGE:.3f} = {array_large:.3f} g"
      f"  (+{array_large-array_small:.2f} g vs small)")
print()

# --- the 14 g doc ------------------------------------------------------------------------------
print("=" * 78)
print("GAP 1 -- the '<14 g' doc vs reality")
print("=" * 78)
HUB_PCB = 20.2
HUB_PARTS = 5.3
WING_ARRAY = array_small
payload = HUB_PCB + HUB_PARTS + WING_ARRAY
print(f"  hub PCB (0.8mm, 70x70)      {HUB_PCB:>7.2f} g")
print(f"  hub parts                   {HUB_PARTS:>7.2f} g")
print(f"  wing array (MEASURED cells) {WING_ARRAY:>7.2f} g")
print(f"  -------------------------------------")
print(f"  flight hardware             {payload:>7.2f} g")
print(f"  balloon (MEASURED)          {M_BALLOON:>7.2f} g")
print(f"  -------------------------------------")
print(f"  TOTAL floating mass         {payload + M_BALLOON:>7.2f} g")
print()
print(f"  the '<14 g' doc target is {14.0:.1f} g. The MEASURED total is"
      f" {payload + M_BALLOON:.1f} g,")
print(f"  i.e. {((payload+M_BALLOON)/14.0 - 1)*100:.0f} % over. GAP 1 can now be CLOSED as a")
print("  measurement: the doc's target was never achievable with this envelope.")
