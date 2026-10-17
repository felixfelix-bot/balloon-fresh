# Wing-interface seat rule: regenerated placement + why the CANONICAL board is untouched

**Date:** 2026-10-17
**Rule changed:** `tracker/hardware/build_hub_board_v9.py` — `EDGE_SEATS` rotations are now
DERIVED from the footprint datum convention (`seat_rotation_deg`), and
`wing_socket_inboard_offset()` is re-derived from the corrected rotations.
**Detector:** `tracker/hardware/verify_wing_interfaces.py` (edge-reach assertion now drives the exit code).
**Rule record:** `docs/adr/072-wing-slot-placement-rule.md`.

## Before / after, measured

Offset before **5.20 mm** (uniform, from the 2026-10-14 repair) → after **0.00 mm** (derived).

```
tab    edge   rot before -> after   slot union BEFORE (absolute mm)        verdict
J_W1   west    0   ->   0           x  5.17..11.22   y 34.52..35.48        WHOLLY INSIDE, 5.25 mm
J_W2   north 270   ->  90           x 34.52..35.48   y 64.78..70.83        crosses bottom, +0.75 mm
J_W3   east  180   -> 180           x 58.77..64.83   y 34.52..35.48        WHOLLY INSIDE, 5.25 mm
J_W4   south  90   -> 270           x 34.52..35.48   y -0.82.. 5.22        crosses top,    +0.75 mm

tab    edge   rot   slot union AFTER (absolute mm)                          verdict
J_W1   west    0    x  -0.03.. 6.03  y 34.52..35.48                         reaches LEFT   edge
J_W2   north  90    x  34.52..35.48  y 63.98..70.03                         reaches BOTTOM edge
J_W3   east  180    x  63.98..70.03  y 34.52..35.48                         reaches RIGHT  edge
J_W4   south 270    x  34.52..35.48  y -0.03.. 6.03                         reaches TOP    edge
```

Outline `Edge.Cuts` bbox `x -0.07..70.08  y -0.07..70.08` (70.15 x 70.15 mm). Every slot now crosses
its own edge by **0.03 mm** (the footprint's own slot local `x` starts at `-0.03`), i.e. within the
detector's stated **0.30 mm** tolerance. Every land (local `x = +3.0`, i.e. `x0 = +1.0`) is 1.0 mm
inboard, so the pads stay on the board.

**Detector exit code:** **1 before** (J_W1, J_W3 wholly inside) → **0 after**.

## Regenerated artifact

```
KRT_DIR=/data/repos/KiCadRoutingTools ~/venvs/kicad/bin/python \
    tracker/hardware/build_hub_board_v9.py \
    --out tracker/hardware/output/hub_board_v9_seed.kicad_pcb --publish
```

* seed `tracker/hardware/output/hub_board_v9_seed.kicad_pcb` sha256 `7eb1b7dce0fe38fa…`
  → `verify_wing_interfaces.py` **EXIT 0**
* KRT lap output sha256 `d8b23136d88e2e51…` → `verify_wing_interfaces.py` **EXIT 0**

The builder's KRT side effect on `hub_board_v9.kicad_pro` / `.kicad_prl` was REVERTED by the builder's
own guard; both files are byte-identical to their committed state (verified by sha256).

## Why the CANONICAL board is NOT overwritten

`tracker/hardware/hub_board_v9.kicad_pcb` is the **routed** board (834 tracks, 286 vias, 57/59 nets —
promoted to canonical by commit `ff87f4953`, Astra item H1). The builder is a **placement** writer: its
output carries **0 tracks / 0 vias**, and the routing is applied by a separate step
(`tracker/hardware/fab_grade.sh` → KRT `py_router/route.py`).

Regenerating the canonical path therefore DROPS the routing, and the repo's own gate refuses it:

```
$ python3 tracker/hardware/fab_readiness_guard.py --check tracker/hardware/hub_board_v9.kicad_pcb
fab-guard: ... -> tracks 0, vias 0, nets 0/59
  *** FAB GUARD: REFUSING THIS COMMIT ***
      tracks 0 < recorded 834
      nets_routed 0 < recorded 57
```

The routing reduction here is a **side effect**, not an intentional reduction, so `FAB_GUARD_ACK` is not
appropriate and `--no-verify` is forbidden. The canonical board is therefore left as the routed board.

**FINDING (same defect class as H1):** the builder's `--publish` path writes a PLACED-ONLY board to the
canonical path — i.e. the builder cannot legally produce the canonical board, and running it silently
destroys the routing until the fab guard refuses the commit. That is worth its own record.

## Remaining step to land the fix on the canonical board

1. Re-run the routing on the regenerated placement:
   `bash tracker/hardware/fab_grade.sh tracker/hardware/hub_board_v9_seed.kicad_pcb <outdir>`
   — this MOVES 18 parts (the KRT lap) and re-routes; it is deliberately NOT done here
   (the task forbids re-routing).
2. Grade + promote the routed result to `tracker/hardware/hub_board_v9.kicad_pcb`.
3. Re-record `FAB-READINESS.json` for the promoted board.
4. Expect the 30 `copper_edge_clearance` items on `J_W1..J_W4` to CHANGE: the west/east slots now add
   edge-located copper that was previously 5.25 mm inboard (the intentional ADR-046/048 interface).
