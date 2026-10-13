# Visual consult evidence — vertical hub load cases

**Served model:** `gpt-6-astra`  **HTTP:** 200  **Structured verdict field:** `PARTIAL`
**Figure:** `docs/analysis/vertical-hub-load-cases.png`
**Command:** `visual_consult.py docs/analysis/vertical-hub-load-cases.png --timeout 900 --emit-evidence --json --ask '...Challenge the conclusion...'`

## Model's own final verdict line (verbatim)

> "Vertical mounting relocates or changes the governing crack boundary; it does
> not remove it, and the proposed larger rib pitch is not justified by this
> figure alone."

## Challenges the model raised (its own words, condensed)

1. The "vertical static" curve is identically zero BECAUSE the model sets k=0
   ("self-weight bending zeroed"). That is an imposed boundary condition, not a
   calculation — the figure cannot demonstrate vertical is safe, only that the
   model was told to assume it.
2. A 90-degree pendulum case should coincide exactly with the horizontal 1 g
   case (same bending model, k=1). If they differ in the plot, that is an
   internal inconsistency in load factors or geometry.
3. Plot scaling is unusable for the question: mechanical curves span 0-2 MPa
   while thermal lines sit at 27 and ~35 MPa, so intersections cannot be read.
4. Pendulum dynamics absent: dynamic amplification, angular acceleration,
   damping, load duration, impact at the stop. A pendulum release is not
   equivalent to a static k*g load.
5. Vertical mounting leaves other load paths: axial compression, joint loads,
   torsion, lateral acceleration, misalignment, vibration-induced bending.
   k=0 is a special case, not proof the governing mode is gone.
6. Thermal stress is not interchangeable with transverse bending stress
   (different failure mode). 27 MPa may be a large overestimate if not fully
   restrained, or an underestimate with local gradients / CTE mismatch.
   Thermal lines above mechanical curves does not prove dominance.
7. No larger rib pitch is justified: bending grows ~quadratically with span,
   S_crack is unmeasured, and no allowable stress, fracture toughness, flaw
   size, fatigue life or safety factor appears. Rib-root stress concentrations
   and attachment details are missing.

## Consequence (recorded 2026-10-09)

- Hypothesis "vertical mounting removes S_crack" -> **REFUTED** (it relocates).
- Thermal-dominance framing -> **over-stated**; the figure cannot settle it.
- Disposition at the time: S_crack card must still run.
- Superseded by operator decision (2026-10-09): go conservative + add panel
  redundancy, document the risk, unfreeze the design, revisit after test
  flights. See the risk doc on this branch.
