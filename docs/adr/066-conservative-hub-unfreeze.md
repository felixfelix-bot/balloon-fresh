# ADR-066 — Conservative hub baseline: unfreeze board work without claiming an unmeasured cell allowable

- **Status:** Proposed — operator direction recorded 2026-10-09; this record is the interim design basis and is not an order authorization.
- **Decision owner:** Felix (operator).
- **Author:** Hermes subagent, branch `pr/conservative-hub-unfreeze`.
- **Amends:** ADR-063 §D4/D5 for the interim baseline only. ADR-063 remains the long-term optimization record.
- **Evidence:** `docs/analysis/vertical-hub-load-cases.md`, `docs/analysis/conservative-hub-unfreeze-risk.md`.
- **Reproduction:** `python3 docs/analysis/vertical_hub_load_cases.py`.

## 0. Operator decision

Stop optimizing the hub support structure for now. Use a conservative, easily testable baseline and let measured flight/bench evidence earn later mass reduction. The board design is **unfrozen for implementation work**: schematic cleanup, component-driven placement, routing, DRC and fabrication preparation may proceed. This does **not** mean that the silicon support is qualified, that the board is fab-ready, or that an order is authorized.

The conservative baseline deliberately gives up the mass benefit of an aggressively skeletonised carrier. The design may be optimized after the `S_crack` coupon, cold-soak, vibration/acceleration evidence and thermal-restraint characterization exist.

## 1. Decisions

### D1 — Component-driven hub board proceeds

Retain ADR-063's component-driven hub concept. The retired 103 × 103 mm array-sized outline is not reinstated. Re-run placement from the measured component courtyard on a practical component-driven outline (nominally ≈60 × 60 mm, subject to the placement gate), then re-freeze the placement hash. Do not treat the existing 103 mm placement as the design of record.

### D2 — Conservative array support: continuous carrier, not an optimized open-rib pitch

For the interim build, each bare 0.21 mm cell is supported over its relevant span by a **continuous or near-continuous carrier**. No unsupported-span value, rib pitch, maximum overhang, or mass-optimized skeleton is frozen from an assumed silicon strength. The carrier's thickness and material are selected for practical handling and stiffness, with the default interim bias toward the more robust existing carrier construction rather than the minimum-mass construction.

This is intentionally conservative **only for the idealized global transverse beam-bending calculation**: it avoids unsupported-span credit without claiming a demonstrated conservative bound for the supported assembly. Local support/contact stress, carrier flatness error, adhesive peel/shear, thermal mismatch, residual stress, shock and vibration remain separate risks and are not bounded by this ADR's beam model. It does not prove immunity to drops, vibration, thermal cycling, or bad handling.

### D3 — Panel redundancy remains mandatory

Keep the independent panel/interface topology and the hub-side per-group bypass protection required by ADR-053/054. A cracked or disconnected group must not be allowed to make the entire remaining array electrically unusable. Bypass parts remain rated for the array current and voltage; their exact part and thermal margin remain an electrical/BOM gate, not an assumption in this ADR.

### D4 — Conservative electrical and mechanical riders

The following remain explicit gates under the conservative baseline:

1. **Cell integrity:** inspect every cell and end-only joint before and after assembly, cold soak and handling.
2. **Thermal:** characterize whether the mounting path restrains contraction. The analysis estimates 27–35 MPa only for the fully restrained uniaxial idealization; equal-biaxial plane-stress restraint can be approximately 37.6 MPa for E=130 GPa and ν=0.28. These are estimates, not material allowables, and must not be used as one.
3. **Acceleration/drop:** obtain a bounded acceleration/vector history or apply a separately approved qualification envelope. The repository's unmeasured 10 g assumption is not silently promoted to a requirement.
4. **Vibration/buffet and supported-assembly response:** define and test a spectrum before claiming flight qualification; separately analyze or test local support/contact stress at ribs/posts/hard points, carrier flatness, adhesive stiffness/peel/shear, cell/carrier thermal mismatch, and modal response. The 2 g transverse curve is illustrative only, not a validated environmental envelope or qualification requirement.
5. **`S_crack` coupon:** still required before any later skeletonisation, larger unsupported pitch, or mass optimization. The coupon is no longer a blocker to beginning the conservative board implementation.
6. **Placement and fabrication:** the re-placed board must pass ADR-030's deterministic placement gate, then schematic/ERC, DRC, routing, BOM and order gates independently.

## 2. Why this is conservative

- Vertical orientation can reduce static transverse self-weight bending, but the documented model gives **0.504 MPa at 1 g** over 78.55 mm and the vertical-panel demand returns to that value at a 90° effective-gravity rotation.
- The maximum swing angle and acceleration history are not measured.
- Thermal stress is orientation-independent and can dominate if contraction is restrained.
- Silicon flexural strength/modulus of rupture is absent from the repository; no safe unsupported span can honestly be calculated.
- Continuous support costs mass and may cost array area, but it removes the need to pretend that an invented pitch is qualified.

## 3. What this record does not authorize

This ADR does not authorize a PCB order, a solar-cell order, a flight, a claim of `S_crack` margin, or a replacement of the required qualification tests. It authorizes only the **design workflow** to proceed on the conservative baseline. Any later reduction in carrier support must be a new measured decision.

## 4. Optimization deliberately deferred

Deferred, not rejected:

- rib pitch and open-area fraction;
- maximum cell overhang;
- carrier thickness reduction;
- array-area increase beyond the charge-path limit;
- thermal-compliance details that trade mass against restraint;
- flight-envelope-derived orientation credit.

The condition for revisiting them is evidence: real-cell coupon results, cold-soak results, inspection records, acceleration/vibration data, and a charge-path check.

## 5. Rollout

1. Re-place the hub board from the component-driven floorplan; do not edit the old frozen placement in place.
2. Route and run the normal schematic, placement, DRC and fabrication gates.
3. Lay out the first carrier as continuous/near-continuous support with no unsupported-span credit.
4. Keep all qualification riders attached to the design record.
5. After test evidence lands, amend ADR-063 or supersede this interim basis with a measured optimization.

**Bottom line:** board implementation is unblocked; unsupported-span optimization is not. Conservative support is the price of moving without manufacturing certainty.
