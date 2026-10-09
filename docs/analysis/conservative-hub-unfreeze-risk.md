# Conservative hub unfreeze — risk register

> **STATUS: RISK DOCUMENT — NOT A DECISION RECORD.** This document records the risk accepted to resume design work. The governing interim decision is ADR-066.

## Decision boundary

The operator chose a conservative baseline rather than further optimization: proceed with a robust continuous/near-continuous carrier and component-driven PCB work, while deferring unsupported-span optimization until measurements exist. This removes the `S_crack` result as a blocker to board implementation; it does not remove the physical risk.

## Ranked risks and controls

| Risk | Evidence / uncertainty | Conservative control | Residual status |
|---|---|---|---|
| Silicon cracks across an unsupported span | No flexural strength or modulus of rupture is in-repo; ADR-063 calibrates 0.504 MPa at 1 g over 78.55 mm (model result, simply-supported beam) | Continuous/near-continuous carrier; no pitch credit; inspect before/after handling | **Open until coupon** |
| Local support/contact stress, carrier flatness, adhesive peel/shear at ribs/posts/hard points | Not modeled by the gravity-bending plot; consultant challenge 2026-10-09 item 7 | Separate local-support analysis or test before design freeze; no span-credit claim covers these modes | **Open — new requirement** |
| Pendulum or acceleration rotates gravity transverse to a vertical panel | No measured swing angle or acceleration vector; 90° returns the full 0.504 MPa 1 g transverse demand | Do not claim an orientation factor; obtain an instrumented envelope and qualify | **Open** |
| Thermal restraint at cold soak | −55 °C repeat is specified; 27–35 MPa is only a fully restrained estimate | Characterize restraint and cold-soak real cells; do not treat estimate as allowable | **Open** |
| Vibration/buffet fatigue | No spectrum or PSD was found | Define a spectrum and inspect joints/cells after test | **Open** |
| Array group failure | Series topology can make a local failure system-level without bypass | Preserve hub-side per-group bypass protection and electrical rating gate | **Controlled, verify in schematic/BOM** |
| PCB geometry regression | Existing 103 mm placement is provisional under ADR-063; new outline has not passed placement | Re-place deterministically and rerun ADR-030/S0/DRC gates | **Open implementation gate** |
| Conservative carrier mass / charge-path mismatch | Continuous support costs mass; larger array may exceed the named harvester input limit | Freeze no array-area increase; quantify mass and charge-path headroom before order | **Open** |

## Explicitly accepted trade

We accept extra carrier mass and deferred energy-per-gram optimization in exchange for avoiding an unsupported, unmeasured mechanical assumption. The optimization is **deferred**, not declared safe. A later design may reduce support only after real-cell, cold-soak, acceleration/vibration and thermal-restraint evidence.

## Required evidence to close the risk

1. Real-cell end-only `S_crack` coupon at ambient and approximately −55 °C.
2. Instrumented pendulum/acceleration vector or an approved conservative qualification envelope.
3. Thermal restraint measurement or a compliant flexible load path.
4. Local support/contact stress analysis or test covering ribs/posts/hard points, carrier flatness, adhesive stiffness/peel/shear, and cell/carrier thermal mismatch; modal response plus vibration/shock qualification input and post-test inspection.
5. Replaced hub placement passing the deterministic placement and DRC gates.
6. Schematic proof of per-group bypass paths and BOM rating/thermal checks.

## Verification

The vertical load analysis is reproducible with:

```text
python3 docs/analysis/vertical_hub_load_cases.py
```

Its conclusion is a demand statement, not a strength claim: vertical mounting conditionally reduces transverse gravity demand, but orientation alone cannot justify a larger unsupported pitch. The visual consultant challenge completed on 2026-10-09 at attempt 6 via `gpt-6-astra` (HTTP 200) and returned `CHANGES_REQUESTED`; the verbatim answer is in `docs/analysis/assets/adr066-consult-answer.md` and machine output in `docs/analysis/assets/adr066-consult.json`. The requested qualification changes are incorporated in the analysis and this risk register; no consultant approval is claimed.
