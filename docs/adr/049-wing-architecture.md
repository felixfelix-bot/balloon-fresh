# ADR-049 — Wing architecture: cell class, structure, orientation and protection

- Status: **Proposed** — the *text* has **NOT** been accepted by a human. The
  recommendation below is put to the operator; until a human accepts it, no
  schematic/placement/routing may treat it as frozen (ADR-first rule, ADR-029 §Context).
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: manager (Hermes agent), consolidating four independent consultant analyses.
- Supersedes in part: the wing geometry assumptions of `docs/hardware-design.md` and the
  un-rebuilt `tracker/hardware/wing_board/wing_board_v9.kicad_pcb`.
- Amends: ADR-046 §2.3 (bypass diode placement and rating), §3.4/§0.3 (cell land size,
  which contradicts itself), and the hub-slot width (0.9 mm — below the fab minimum).
- Inputs (all on main, all committed): `docs/analysis/wing-mass-shape.md`,
  `docs/analysis/wing-electrical.md`, `docs/analysis/wing-fab-cost.md`,
  `docs/analysis/wing-insolation-geometry.md` plus the two reproducible scripts.

## Context

The vehicle is one hub board plus four solar wing boards at 90°. The wings were designed
on paper before the actual cells were in hand. The operator has now measured the cells and
asked four questions: (1) should one wing board carry both cell sizes; (2) is there an
optimal shape to maximise energy per gram; (3) what happens if a size class is omitted;
(4) winter geometry — tilt, V-shape, inverted-V, half-shape. Four consultants answered
independently (mass/shape, electrical, fab/cost, insolation geometry).

## Measured inputs (not assumed)

| Item | Small cell | Large cell |
|---|---|---|
| Outline | 52.07 × 19.65 × 0.20–0.21 mm | 78.55 × 38.90 × 0.21 mm |
| Area | 10.23 cm² | 30.6 cm² |
| Terminations | **one pad on the FRONT face, one on the BACK face** | not yet confirmed |
| Nominal | ~0.5 V, ~0.4 A | ~0.5 V, ~1.2 A |
| Quantity in hand | ~100 | "more than enough" — **exact count not yet stated** |

## Decision (single recommendation)

> **Build each wing as three LARGE cells in series, in a VERTICAL plane, on a spine-and-ribs
> frame, with a ≥2 A / 40 V bypass Schottky per wing and a rated shunt clamp at the raw
> supercap node. Do not mix cell sizes. Do not build a universal wing. Do not use a leaned,
> V, inverted-V or half shape. Do not use a full-area FR4 carrier.**

Array result: 12 cells, **6.0 V nominal / 1.2 A ≈ 7.2 W** peak — which is the first
arrangement that **exceeds** the radio's 6.15 W maximum draw (ADR-047) from solar alone.

**This recommendation is CONDITIONAL on two unverified facts.** If either fails, the
fallback is stated with it:

1. **The operator must confirm ≥12 intact large panels.** If fewer, fall back to
   **9 small cells per wing (3 parallel × 3 series)** — same 7.2 W, same 6.0 V/1.2 A, but
   **108 hand-soldered joints per aircraft instead of 36** and 36 cells instead of 12.
   If he prefers 3 smalls per wing instead, the array becomes 6.0 V / 0.4 A ≈ 2.4 W,
   which is **below** the radio's maximum draw — that is a deliberate downgrade, not an
   equivalent, and must be recorded as such.
2. **The pad geometry of both cell sizes must be measured** (front pad and back pad: size,
   and distance from the cell end and long edges). Until then the cell land is unverified
   and **no wing may be ordered** — this is the only irreversible step in the whole wing
   programme.

## Why each rejected option was rejected (with the number)

| Option | Verdict | Number |
|---|---|---|
| **Mix sizes in one series string** | REJECT | string runs at min(0.4 A, 1.2 A) = 0.4 A; each large cell adds 1.50 g and 30.6 cm² for **zero extra amps**; one large in series with one small throws away **66.7%** of the large cell's 0.60 W |
| **One universal wing board** | REJECT | rejected on all three lenses (electrical, mass, assembly) independently |
| **Full-area FR4 carrier** | REJECT | 0.6 mm FR4 = **127.6 mg/cm²** vs 48.9 mg/cm² per cell area — the board is **2.61× heavier per unit area than the silicon it carries**; current 176 × 25 mm wing spends 5.71 g of FR4 on 1.50 g of cells (array 29.20 g vs 12.85 g for spine+ribs = **16.35 g saved**) |
| **Double-sided carrier** | REJECT | the dark face of an opaque panel produces nothing; array mass 35.57 g, strictly worse |
| **Flat horizontal cross** | REJECT | 0.1863 vs 0.2559 daily — **vertical is +37%** |
| **Leaned vertical (~15°, β≈75°)** | REJECT | only **+3.3%** over plain vertical and needs a new tab/slot feature |
| **V / inverted-V (two half-panels per arm)** | REJECT | **−4.3% / −7.4%** versus one properly tilted panel |
| **Half-shape (one panel per arm)** | REJECT | a 6-cell string is 3.0 V and **cannot charge the 5.4 V bank at all** — fails on topology, not merely on efficiency |
| **Cells only, flex harness, no PCB** | REJECT (for now) | lightest at 8.35 g but **no load path**; revisit only if the spine proves too heavy |

## Consequences that change existing records

1. **ADR-046's bypass diode is already undersized.** BAT54 family = 200 mA / 30 V against
   the accepted 0.4 A array — undersized **before** any change. Re-rate to **≥2 A / 40 V**
   (SS24 or PMEG4020ER class). Add per-cell bypass once any series position is paralleled.
2. **The vertical-wing gain is CONDITIONAL on those diodes** (insolation analysis): with
   uncontrolled azimuth the 3.36× sun-facing advantage collapses to 1.07× at noon and
   1.67× over the day, and the series topology makes a flat cross **13.7% better at noon**
   while losing 37% daily. Vertical without bypass diodes is a regression.
3. **The rail clamp is no longer "cheap insurance" — it is a required, rated part.** The
   array's −60 °C open-circuit voltage is ≈ **9.3 V** against a 5.4 V bank and a 5.5 V
   radio ceiling, and **no series count satisfies both**. The clamp must sink up to
   **1.2 A at 5.5 V**. This upgrades the clamp in ADR-044/ADR-047 from optional to mandatory.
4. **ADR-046's 0.9 mm hub slot is below JLCPCB's minimum non-plated slot (1.0 mm)**, and its
   worst-case clearance against a 0.6 mm tab is **0.00 mm**. Fix: slot ≥ 1.0 mm, or drop the
   slot in favour of plain solder pads. **Hub-side blocker.**
5. **ADR-046 contradicts itself**: cell land stated as 1.6 × 14.0 mm (§0.3) and 1.6 × 4.0 mm
   (§3.4); bypass Schottky placed on the hub (§2.3) but specified per-wing in the build
   brief. Both must be resolved in ADR-046 or by an amendment here.
6. **Wing plane orientation is VERTICAL.** The repo does not state this (`ADR-048 OPEN-23`
   records the contradiction); it is resolved by arithmetic — a 0.9 mm slot admits a 0.6 mm
   tab plus a 0.30 mm gap, and a 9 mm tab cannot fit a 6 mm in-plane slot. Recorded as a
   **derived inference**, not a cited fact.
7. **Tab lands 4.0 × 1.2 mm are adequate** (~2.7 A at 1 oz copper / 10 °C rise), so the
   4-pin wing interface from ADR-046/ADR-048 stands, subject to clause 4.

## Recommended outline (per arm, both classes)

- **Large cells (preferred):** 167.1 × 86.8 mm short-and-wide arm carrying 3 cells.
  The 247.65 mm single-row arm is rejected.
- **Small cells (fallback, 9 per wing):** 168.2 × 25.65 mm; span 358.4 mm.
- All four arms must be **identical boards** (one order line; equal series sources; no mass
  imbalance). Asymmetry, if wanted, belongs in the soldered assembly, not the design.

## Open items carried, not silently dropped

- `TODO(unverified)`: exact intact large-panel count.
- `TODO(unverified)`: pad size and position on both cell sizes, both faces — **the order blocker**.
- `TODO(unverified)`: whether spine-and-ribs leaves unsupported silicon spans that crack;
  the frame's rib pitch is set by that answer, and it is why the frame is a recommendation
  and not yet a layout.
- `TODO(unverified)`: the array's −60 °C open-circuit voltage (the 9.3 V figure is a
  calculation, not a measurement).
- `TODO(unverified)`: whether the wing should be jettisonable (under study; see the release
  mechanism analysis once it lands).
- `TODO(unverified)`: whether a cylindrical array outperforms four blades. Preliminary
  derivation recorded in the session: for the same **installed cell area** a cylinder and a
  4-blade cross harvest identically ((1/π)·cos e ≈ 0.305 each); a cylinder needs about π×
  more cells to achieve the same projected area. To be confirmed by the geometry consultant.

## Rollout

1. Operator confirms the large-panel count and the cell class, and measures the pads.
2. This ADR is amended (or accepted) with those numbers.
3. ADR-046 is corrected for clauses 4, 5 and the diode rating.
4. The wing board is **redrawn** for the chosen class, vertical, spine-and-ribs.
5. Placement is rejected unless it passes ADR-045 (antenna solder access) **and** ADR-046/048
   (wing tab geometry and keep-out).
6. Then route → order gate → gerbers/CPL for both designs → BOM freeze → one JLCPCB quote.
