# The wing-interface fix is REAL but NOT on the board that goes to fab

**Measured 2026-10-17. Branch `pr/wing-slot-rule` (commit `05f963c16`).**

## The fix, independently verified

The worker derived the `J_W*` seat rotations from the footprint's datum convention instead of compensating
with an offset, and the result is correct. I re-ran its detector myself, without a pipe (so the exit code is
the script's, not `tail`'s):

```
detector on the CANONICAL board  (tracker/hardware/hub_board_v9.kicad_pcb)        EXIT=1
detector on the REGENERATED seed (tracker/hardware/output/hub_board_v9_seed.kicad_pcb)  EXIT=0
```

**Slot geometry, relative to each footprint's origin** — before, and after:

| tab | edge | rotation | BEFORE (defective) | AFTER (fixed) |
|---|---|---|---|---|
| `J_W1` | west | 0 → 0 | `(-0.03, -0.48, 6.02, 0.48)` | `(-0.03, -0.48, **6.03**, 0.48)` |
| `J_W2` | north | 270 → **90** | `(-0.48, **-0.02**, 0.48, 6.03)` | `(-0.48, **-6.02**, 0.48, 0.03)` |
| `J_W3` | east | 180 → 180 | `(-6.02, -0.48, 0.03, 0.48)` | unchanged |
| `J_W4` | south | **90 → 270** | `(-0.48, **-6.03**, 0.48, 0.02)` | `(-0.48, **-0.03**, 0.48, 6.03)` |

**The four slots are now congruent under the same 90° rotations as the pads** — `J_W1` and `J_W3` already
agreed, and `J_W2`/`J_W4` now match them instead of mirroring them. **The 180° inconsistency between the
{west,east} pair and the {north,south} pair is gone.** Inboard offset **5.20 mm → 0.00 mm**, derived as
`max(0, 0.20 − 1.00)` from the measured pad geometry rather than typed.

**Detector: `EXIT=1` before → `EXIT=0` after.** That is the fix the whole exercise was for, and it is real.

## The problem: the fix landed on a board that is not the fab input

```
fixed:     tracker/hardware/output/hub_board_v9_seed.kicad_pcb   (detector EXIT=0)
fab input: tracker/hardware/hub_board_v9.kicad_pcb               (detector EXIT=1)  <-- still defective
```

**The canonical board still carries the defect.** Measured on it directly: `J_W1`/`J_W3` slots wholly inside
**5.25 mm**; `J_W2`/`J_W4` crossing their edges by **0.75 mm**.

**And `regen_fab_package.py` reads the canonical board**, not the seed:

```
DEFAULT_BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"
  1. reads the CANONICAL board (tracker/hardware/hub_board_v9.kicad_pcb)
```

So **the fab package, the gerbers and the review artefacts are all built from the board that still has the
defect**, while the fix sits in an intermediate build product.

## Why this happened — a documented builder trap

The worker reported it, and it is the same class as the earlier H1 regression:

> *"the builder's `--publish` path writes a placed-only board to the canonical path — i.e. it cannot legally
> produce the canonical board, and running it destroys the routing until the fab guard refuses the commit."*

**`build_hub_board_v9.py` generates a PLACEMENT. The canonical board is a PLACEMENT + ROUTING artifact** that
was promoted to the canonical path by hand after the routing was done. So the builder **cannot** regenerate
the canonical board — and the fix, being a placement change, lands in the seed. **Promoting the seed to
canonical would destroy the 834 tracks and 286 vias**, which is exactly what the fab guard exists to catch.

## The cost of applying it — measured, not guessed

```
board: tracker/hardware/hub_board_v9.kicad_pcb
  footprints: 59      tracks: 834      vias: 286
  J_W* footprints: 4  J_W* pads: 16

  J_W* pads with a TRACK endpoint on them: 7
  J_W* pads with a VIA on them:            6
  J_W* footprints electrically touched:    ['J_W1', 'J_W2', 'J_W3', 'J_W4']
```

**All four wing sockets are electrically connected on the routed board** — 7 pads carry a track endpoint and
6 carry a via. **Moving the footprints moves those 13 connection points, so 13 pad connections need
re-routing** (not the whole board: only the escapes from the moved pads).

`tracker/hardware/measure_wing_routing_cost.py` produces this, so the number is reproducible.

## What has to happen (a decision, not a mechanical step)

**Option A — apply the fix to the canonical board.** Re-run placement, then re-route the 13 affected pad
connections. The board is **57/59 routed with 2 nets already waiting on hand-routing**, so this adds to work
the operator is already doing in the GUI. **This is the only option that makes the fab package correct.**

**Option B — leave the canonical board as-is and document.** The wings cannot seat symmetrically, which
changes the array geometry and **the solder-joint load case the peel coupon exists to measure** — so the
peel coupon's specimen geometry would be measuring a configuration the board does not implement.

**Option A is the one that makes the artefact honest**, and it should be sequenced with the two unrouted
nets the operator is already going to hand-route, so it is one GUI session rather than two.

## Also verified in the same pass

- **the canonical board was NOT touched** by the fix — sha256 still `e55a294628fd38a7`, tree clean
- the worker's detector is now a real gate (`EXIT=1` on a bad board, `EXIT=0` on a good one), so **the four
  interfaces cannot silently diverge again**
- `ADR-085` was written for the slot-placement rule, and **`ADR-048 §2.1`'s stale 22 × 22 mm outline was
  corrected with the change recorded** rather than silently rewritten

## The pattern, once more

**The fix is correct, the detector is correct, and the artefact that reaches the fabricator still has the
defect.** This is the same shape as the earlier finding that the fab package matched a board that no longer
existed: **a correct change applied to the wrong artefact looks like progress and ships the defect.**
