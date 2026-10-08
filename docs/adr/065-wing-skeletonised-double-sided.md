# ADR-065 — Wing board: skeletonised frame carrier + double-sided cells

**Status:** Accepted (operator decision, 2026-10-08)

## Context

The wing board is the least mass-efficient element on the vehicle: a 176 × 25 mm
full-carrier wing spent **5.71 g of FR4 carrying 1.50 g of cells** — a **3.8:1**
board-to-silicon ratio. Two operator decisions, made together, flip this:

1. **Skeletonise the wing carrier** — replace the solid FR4 board with a
   spine-and-ribs frame, keeping FR4 only where load or copper requires it.
   This respects ADR-052's "end-only, no bond" constraint: cells bridge open
   gaps between ribs, unbonded, carried at their ends — same as the hub
   carrier recommendation in ADR-063.

2. **Double-side the wing** — put cells on both faces. For a vertical plane,
   front gets `max(0, n·s)`, back gets `max(0, −n·s)`, sum = `|n·s|` →
   **2× the single-sided rotationally-averaged harvest**.

## Decision

**Adopt both: a skeletonised spine-and-ribs wing frame carrying cells on both
faces.**

## Measured mass impact

| configuration | carrier FR4 | cells | total | ratio |
|---|---|---|---|---|
| current (single-sided, full carrier) | 5.71 g | 1.50 g | 7.21 g | 3.8:1 board-heavy |
| skeletonised + double-sided (target) | ~1.6 g (28.4% of 5.71) | 3.00 g | ~4.6 g | ~0.5:1 cells-heavy |

- Carrier mass drops from 5.71 g toward ~1.6 g (the measured 28.4% board/cell
  area ratio from `wing-mass-shape.md` §1.4).
- Cell mass doubles: 1.50 g → 3.00 g.
- **The ratio flips from 3.8:1 board-heavy to ~0.5:1 cells-heavy.**
- Net wing mass: ~7.21 g → ~4.6 g per wing (**~2.6 g saved per wing, ~10.4 g
  across four wings**).

## Energy impact

Double-siding doubles the rotationally-averaged harvest per wing. The
instantaneous peak is unchanged (at normal incidence the back face is fully
shadowed by the board), so this is an **energy** gain, not a peak gain:

- Energy per rotation: **2×**
- Good windows per rotation: **2×** (peaks twice instead of once)
- Instantaneous peak: **unchanged**

This benefits a duty-cycled transmitter that sends whenever there's sun. It
does not help if the mission needs a burst at one specific moment.

## Costs (real, not footnotes)

1. **Joint count doubles: ~36 → ~72 hand-soldered joints across four wings.**
   Joints are the primary hand-build risk metric. Joints-per-watt improves
   because the same frame carries twice the power.
2. **Thermal gradient across the blade: front face radiates to deep sky, back
   face faces the sun.** On a 0.6 mm blade this ΔT drives both faces' end-only
   joints from opposite sides. More acute than on the hub. The coupon test
   should probe this.
3. **Cutting a wing now sheds twice the cells** — fine (that's the intent), but
   doubles the value at risk per cut.

## Gating dependency

**The rib pitch is gated by the coupon test** (ADR-063 §6): one real cell,
end-supported over a growing gap, loaded to ½ g at −55 °C → `S_crack` →
rib pitch ≤ `S_crack`. **No flexural strength for 0.21 mm silicon exists in
the repo or the datasheet. This ADR does not invent one.**

Until that test exists, the frame is designed to a **conservative default rib
pitch** (every cell end supported + one mid-span rib), and lighter rib spacings
are deferred.

## Supersedes

- The full-carrier wing board in ADR-046 (5.71 g carrier) is superseded for
  mass purposes. The wing *outline* and *interface* (4-pin tab, 90° spacing)
  are unchanged.
- The single-sided cell count (3 per wing) is superseded: **6 per wing** (3
  front + 3 back).

## For future sessions

- The wing board respin (to match the plain-pad socket from ADR-063 + this
  skeletonised double-sided frame) is the **next mechanical deliverable**.
- The hub board outline move (~60 × 60 mm) and the wing respin should be
  done together — both change the interface geometry.
- Do NOT re-place the hub board until the new outline is frozen (ADR-063).
- The coupon test gates every "make the ribs lighter" follow-up.