# THE SCOPED EDGE-CLEARANCE RULE IS INERT — measured, with controls

**Date:** 2026-10-14 · **This overturns my own earlier recommendation.** I recommended "an item-type
scope that stops the copper rule applying to `Edge.Cuts` graphics". **I have now measured that the
scoped exemption the operator approved cannot be expressed in KiCad's DRC condition language.**

## What was claimed vs what is true

The frozen ruleset `tracker/hardware/jlcpcb-s1-frozen.kicad_dru` carries an **operator-approved
(2026-10-14)** scoped exemption for the edge-launched wing land sets:

```
(rule "edge_clearance_wing_socket_lands_44"
  (constraint edge_clearance (min 0.0mm))
  (condition "A.Reference == 'J_W1' || A.Reference == 'J_W2' || A.Reference == 'J_W3' || A.Reference == 'J_W4'"))
```

The board still reports **28 `copper_edge_clearance` ERRORS**. The file's own honesty note guessed why
("their Edge.Cuts SEGMENTS cannot be reached by a copper condition"). **I tested it.**

## Measurement, with controls

Control first, because a rule form that never works proves nothing:

| probe | edge errors | verdict |
|---|---:|---|
| baseline (frozen as-is) | **28** | — |
| **blanket** `edge_clearance min 0.0` (no condition) | **16** | ✅ **rules DO fire** |
| **blanket** `edge_clearance min 0.1` (no condition) | **16** | ✅ same |

**So the rule mechanism works.** Now the condition forms:

| condition | edge errors | fires? |
|---|---:|---|
| `A.Reference == 'J_W1'` | 28 | ❌ **inert** |
| `A.Reference == 'J_W3'` | 28 | ❌ inert |
| `B.Reference == 'J_W3'` | 28 | ❌ inert |
| `A.Reference == 'J_W1' \|\| … \|\| B.Reference == 'J_W4'` (all eight) | 28 | ❌ **inert** |
| `A.Layer == 'Edge.Cuts'` | **16** | ✅ fires |
| `B.Layer == 'Edge.Cuts'` | **16** | ✅ fires |
| `A.Type == 'Pad'` | **20** | ✅ fires |
| `A.Type == 'Track'` | 26 | ✅ fires |
| `A.Type == 'Via'` | 26 | ✅ fires |
| `A.Layer == 'Edge.Cuts' && A.Type == 'Pad'` | 28 | ❌ **inert** (the `&&` form fails) |

## Conclusions, each measured

1. **`A.Reference` / `B.Reference` cannot be matched for an edge-clearance pair.** All eight
   reference-based forms are inert. **The operator-approved scoped exemption does nothing.** It has
   been in the ruleset since 2026-10-14 and has never suppressed a single item — which is why the 28
   keep appearing and kept being re-reported as if newly found.

2. **`Layer` and `Type` DO match**, but they are **not scoped to the wing sockets**:
   - `A.Layer == 'Edge.Cuts'` removes 12 → but it would exempt **any** copper near **any** edge.
   - `A.Type == 'Pad'` removes 8 → but it would exempt **every pad on the board**, not just `J_W1..J_W4`.

   **Both are far broader than the approved scope.** Applying either would silently stop the
   board-wide 0.5 mm edge floor from doing its job — exactly what the ruleset's own note refused when
   it declined to lower the board default.

3. **Combining conditions with `&&` is inert** (`Edge.Cuts && Pad` → 28), so there is no way to
   narrow `Layer`/`Type` down to the wing sockets either.

## What this means, stated plainly

**The operator's intent is sound and the physical justification stands**: `J_W1..J_W4` are
**edge-launched by design** (ADR-046/048) — the land set sits ON the board edge so the pads meet the
wing tab, and `actual 0.0000 mm` **is** the interface, not a defect.

**But the intent cannot be expressed in the rules file.** The remaining options are:

| option | honest assessment |
|---|---|
| **Accept as a documented DELTA** | ✅ **my recommendation.** The 28 items are named, their physical justification is recorded, and the count is reported as a delta — **never as a pass**. This is what the operator's other question already anticipated ("or accept as a documented delta"). |
| Lower the board-wide edge floor | ❌ **refused** — the ruleset's own note already rejected it: it would let any trace reach 0.2 mm everywhere. |
| A board-wide `A.Type == 'Pad'` exemption | ❌ **refused** — broader than approved; exempts every pad on the board. |
| Move the wing sockets inboard | ❌ **breaks the design** — the edge launch IS the interface (ADR-046/048). |

## Correcting my own earlier recommendation

I told the operator: *"an item-type scope that stops the copper rule applying to `Edge.Cuts`
graphics — not a delta, not a waiver."* **That was wrong, and I can now show why:**

- the item-type scope **cannot be narrowed** to the wing sockets (`&&` is inert, `Reference` is inert);
- applied broadly it **weakens a rule the operator deliberately kept strict**.

**A documented delta is therefore the correct answer, not the scope I recommended.** The delta must
be **explicit and counted**, so it can never be mistaken for a clean board.

## The other two error classes (both resolved or named)

| class | count | status |
|---|---:|---|
| `drill_out_of_range` | **12 → 0** | ✅ **RESOLVED.** The operator's `min_through_hole_diameter` 0.3 → 0.2 decision (already applied to the base station) had never been applied to the **hub's** project. Applied. The 12 items are `U1` (ESP32-S3-WROOM-1U) **PTH pad 41**, and `U1`'s only drill size is **0.2 mm** — Espressif's own land pattern, equal to JLCPCB's mechanical drill floor. |
| `starved_thermal` | **3** | ⚠ **REAL, unresolved.** `Pad 2 [GND]` of `U_CUT3`, `U7`, and one more connect to the F.Cu GND plane with **1 thermal spoke where the rule requires 2**. This is a **new, genuine** finding — the newly-placed `U_CUT3` is one of the parts added by the symbol surgery. |
| `copper_edge_clearance` | **28** | ⚠ **documented delta** (above). |

## Result on the 44-part hub board

| | before | after |
|---|---:|---:|
| errors | 43 | **31** |
| `drill_out_of_range` | 12 | **0** |
| `starved_thermal` | 3 | 3 |
| `copper_edge_clearance` | 28 | 28 |
| unconnected | 5 | 5 |
| routed | 49/50 single-ended, 85/85 multipoint | same |

**The board is NOT orderable yet**: 31 errors and 5 unconnected remain. **What changed is that every
remaining item is now NAMED, COUNTED, and either resolved or explicitly recorded as a delta — instead
of being re-discovered each pass.**
