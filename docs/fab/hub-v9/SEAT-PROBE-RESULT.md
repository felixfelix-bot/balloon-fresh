# SEAT PROBE RESULT — 70 × 70 is the component floor; the hub now routes completely

**Date:** 2026-10-14 · **Status:** MEASURED. Revises ADR-068's figure (not its principle).
**Reproduce:** `python3 tracker/hardware/seat_probe.py`

---

## 1. Why a probe was needed

ADR-068 chose **60 × 60 mm** from the **aggregate courtyard floor**: 2582 mm² at
72 % packing = 59.9 mm. That arithmetic is correct. **It is also incomplete.**

The packer must place one **39.65 × 22.30 mm rectilinear body** — `U2`, the
`LoRa2021F33-2G4`, the largest part on the board. A single long body wastes more
area than its own footprint implies, because the space that fits beside a 39.65 mm
side is not usable by it. **Aggregate courtyard arithmetic cannot see that.** So the
outline was probed instead of derived.

## 2. Seating vs outline (measured, real generator, 39 parts at every outline)

| Outline | Overflow | U2 on board? |
|---|---|---|
| **60 mm** | `U2` | **NO** — parked off-board |
| **65 mm** | `U5` | YES, but **U5 overflows instead** |
| **70 mm** | *(none)* | **YES** |
| 75 mm | (none) | YES |
| 80 mm | (none) | YES |
| 102 mm | (none) | YES |

**Two findings that matter:**

1. **60 × 60 does not seat the design.** The packer cannot fit `U2` alongside the
   other 38 parts.
2. **65 × 65 is a trap.** It seats `U2` only by overflowing **`U5`** instead — it
   **moves the problem rather than solving it.** A probe that only asked "does U2
   fit?" would have wrongly blessed 65 mm.

**70 × 70 is the smallest outline that seats all 39 parts with no overflow.**

## 3. Routing result — the hub routes completely at 70 × 70

| Outline | Routed | Multipoint pads | Open nets |
|---|---:|---:|---|
| 60 mm | 43/44 | 69/69 | `GND` |
| **70 mm** | **48/48** | **148/148** | **NONE** |

**48 of 48 nets routed, 148 of 148 pads connected, zero unrouted nets.** This is the
first time the v9 hub has been fully routed in this project.

## 4. Frozen-rules DRC (project + `.kicad_dru` restored before grading)

The router rewrites the project floors on every run (min track width **0.0889 mm**,
below JLCPCB's 0.10 mm), so the frozen project and rule file are restored first.

| | 60 × 60 (after seat fix) | **70 × 70** |
|---|---:|---:|
| **Unconnected items** | 16 | **5** |
| Clearance | 505 | 505 |
| Hole clearance | 200 | 202 |
| Track width | 199 | 199 |
| Via diameter | 132 | 173 |
| Silk overlap | 22 | 103 |
| Copper-edge clearance | 76 | 65 |
| **Total violations** | 1195 | **1317** |

**The violation total is HIGHER at 70 × 70 — and that is the right direction.** At
60 × 60 the router had given up on `GND`; at 70 × 70 it routes *everything*, so
**more copper exists and therefore more copper is graded.** Silk overlap rising
22 → 103 is exactly that: silkscreen that previously sat over empty space now
overlaps real copper.

**The character of the remaining work changed:** from *"the router cannot route this
board"* to *"clean up a routed board."* That is a much smaller, different problem.

## 5. Still not a pass — stated plainly

- **5 unconnected items remain.**
- The router still delivers **sub-fab geometry** in places (0.0889 mm track).
- Silk/copper-edge items need cleanup (103 + 65).

Nothing is orderable yet. But this is the first state where the board is
**electrically complete as a route** and the remaining work is refinement.

## 6. Effect on ADR-068

**Principle unchanged; figure revised.** The board is still sized by **components**,
not by the array, and the array still rides the separate overhanging carrier
(ADR-063). What changes is the **number**:

| | Was | Now |
|---|---|---|
| Outline | 60 × 60 mm | **70 × 70 mm** |
| Area | 36.0 cm² | 49.0 cm² |
| 0.6 mm mass | 4.60 g | **6.26 g** |
| JLCPCB tier | cheap (≤102 mm) | **still cheap** |

**The mass cost is +1.66 g; the benefit is a board that actually routes.** And the
cheap-tier and decoupling arguments that justified ADR-068 are **unaffected** — 70 mm
is still far inside the 102 mm cliff.

**Honest note on the earlier claim:** ADR-068 recorded that "103 × 103 and 60 × 60
route the SAME net count (43/49), so the shrink is routing-neutral." That was true
*as measured*, but it was measured with **`U2` parked at the board origin** (the
unplaceable-part defect fixed later in `de8e05d1`). Once that defect was fixed, the
comparison changed completely: **60 × 60 caps out at 43/44; 70 × 70 reaches 48/48.**
The earlier conclusion was drawn from a board state that was itself defective.
