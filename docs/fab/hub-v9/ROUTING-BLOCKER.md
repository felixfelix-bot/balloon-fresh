# HUB v9 — routing blocker: evidence and root cause

**Date:** 2026-10-14 · **Status:** BLOCKED — v9 is NOT fab-ready, and the cause is
structural, not a router tuning problem.

## What was measured (not assumed)

`tracker/hardware/hub_board_v9.kicad_pcb` is **placed-only**:

| Property | Value |
|---|---:|
| footprints | 39 |
| pads | 251 |
| board | 103.15 × 115.05 mm, 4-layer |
| track segments | **0** |
| vias | **0** |
| nets | 51 |
| nets with any copper | **0** |
| committed DRC (2026-10-07) | 69 violations, 157 unconnected |

## Two independent routing attempts, same verdict

Both runs used the deterministic KRT A* router (`py_router/route.py`) and were
then **re-graded by `kicad-cli pcb drc` against the FROZEN rule set**
(`tracker/hardware/jlcpcb-s1-frozen.kicad_dru`, clearance 0.20 mm / via 0.60 mm /
drill 0.30 mm).

| Run | Input | Nets routed | DRC violations | Unconnected | Verdict |
|---|---|---:|---:|---:|---|
| r1 | `hub_board_v9.kicad_pcb` | 43/49 | 816 | 18 | NOT fab-ready |
| r2 | `output/hub_board_v9_seed.kicad_pcb` (canonical seed, sha256 verified) | 43/49 | 822 | 18 | NOT fab-ready |

Run r2 is the important one: the seed's sha256 matches the recorded
`reproducible_input_sha256` (`06ac5c92…32abf`), so **the same 6 nets fail from the
repo's own canonical, reproducible starting point**. The failures are not noise
from a stale board.

## The 6 nets that will not route (identical in both runs)

| Net | Failure mode | Reading |
|---|---|---|
| `/W1_SOLAR_N` | 3/4 pairs connected | wing solar return |
| `/W2_SOLAR_N` | 3/4 pairs connected | wing solar return |
| `/W3_SOLAR_N` | 3/4 pairs connected | wing solar return |
| `GND` | 71/77 pairs, `boxed_in_static` after 5001 iterations | plane tap unreachable |
| `/CUT_SENSE_W2` | 0/1 | cut-sense stub, pad outside the board |
| `/CUT_SENSE_W4` | 0/1 | cut-sense stub, pad outside the board |

**Decisive detail:** the `GND` failure is reported as `boxed_in_static` — the
router exhausted 5001 iterations and concluded the pad is geometrically
enclosed, not that it ran out of time. And `/CUT_SENSE_W2` / `/CUT_SENSE_W4`
reference pads at **y = 106.0 and y = −3.0** while the board is 115.05 mm tall
with the wing sockets seated on the edge centre lines — i.e. those pads sit
**outside the board outline**.

## Root cause: over-subscribed area, not router tuning

From `build_hub_board_v9.py`'s own header, measured:

> the 39 footprinted components demand **2582 mm²** of courtyard against the
> board's **2475 mm²**, and a best-effort pack left **28 of 39 parts unseated**.

That is a **104% > 100%** area oversubscription at the 103 × 103 mm outline. A
board cannot route cleanly when placement does not fit: the router is asked to
thread 0.20 mm-clearance copper through gaps that do not exist, which is exactly
what 504 clearance + 200 hole-clearance violations look like.

## A self-grading hazard, caught

The router **rewrites the output `.kicad_pro` to relax the fab floors** so its
own copper "reads clean":

```
rules.min_hole_clearance:        0.2  -> 0.175 mm
rules.min_via_diameter:          0.5  -> 0.25  mm
rules.min_through_hole_diameter: 0.3  -> 0.15  mm
net_class[Default].clearance:    0.2  -> 0.175 mm
```

Every one of the numbers in this document was taken **after restoring the frozen
project and DRC rule file**, so they are measured against the real rules, not the
relaxed ones. Any future run must do the same.

## 7 footprints are unplaceable — a real gap, not a bug

The generator names them explicitly:

```
unplaceable  PVA1       SolarCell_78x39mm
unplaceable  PVA2       SolarCell_78x39mm
unplaceable  U_CUT1     latched cut driver + cut-sense (part TODO(unverified))
unplaceable  U_CUT2     latched cut driver + cut-sense (part TODO(unverified))
unplaceable  U_CUT3     latched cut driver + cut-sense (part TODO(unverified))
unplaceable  U_CUT4     latched cut driver + cut-sense (part TODO(unverified))
unplaceable  U_HUB_CVT  HUB_PV input (part TODO(unverified))
```

So the netlist has **46 components but only 39 are placed**. Five of the seven
(`U_CUT1..4`, `U_HUB_CVT`) have **no part selected at all** — they are
`TODO(unverified)`. The two solar cells are 78 × 39 mm each, i.e. **6084 mm² of
solar alone** against a 10609 mm² board — they overhang by design (ADR-063), which
is a separate mechanical question.

## What this means for the order

**v9 cannot be ordered.** The PRE-ORDER-CHECKLIST's 6 blockers are real, and this
adds a seventh, harder one: *the board does not route*. No quantity of post-hoc
DRC-fixing changes that, because the cause is that placement does not fit.

## Recommended next step

Do **not** re-run the router. Either:

1. **Enlarge or re-plan the outline** so that 39 placed footprints + 5 unselected
   parts fit with routing channel to spare, then re-run the canonical chain
   (`build_hub_board_v9.py --publish` → KRT route → frozen-rules DRC); or
2. **Cut scope on v9**: the D8 nested dual LoRa2021 footprint (U2 *and* U3 both
   populated) doubles RF area for a variant that may not fly on the first
   article. Removing it frees real estate and removes the selectable-rail
   complexity; and
3. **Select the 5 `TODO(unverified)` parts** (`U_CUT1..4`, `U_HUB_CVT`) or
   explicitly DNP them — as it stands the netlist references parts that do not
   exist, so the BOM cannot be completed either.

Both (1) and (2) are geometric decisions that the operator's goal says must be
"locked in early" — which is why this is surfaced now rather than after an order.
