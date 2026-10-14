# HUB v9 at the component-floor outline — measured result

**Date:** 2026-10-14 · **Status:** MEASURED. Decision-grade. No freeze.
**Supersedes** the assumption in `ROUTING-BLOCKER.md` that the outline size is what
blocks routing. It is not. The measurements below say so.

## What was run

The generator takes `--outline WxH` (`tracker/hardware/build_hub_board_v9.py`), so the
resize proposed by ADR-063 (board sized by COMPONENTS, array on a separate overhanging
carrier) is a parameter, not a rework. Three outlines were generated and the 60×60 case
was carried all the way through the canonical chain:

```
python3 build_hub_board_v9.py --outline 60x60 --out seed     # 4-layer, 0.6 mm
KRT py_router/route.py seed routed.kicad_pcb                 # deterministic A*
kicad-cli pcb drc   (frozen rules re-applied first)
```

## Result 1 — the small board SEATS and generates

All three outlines seat cleanly, with the same eight parts on the edges:

`edge-seated: J_W1, J_W2, J_W3, J_W4, ANT1, ANT2, ANT3, ANT4` — the four wing tabs and
the four U.FL antenna pads. So the interface geometry (ADR-046 wing tab, ADR-045 antenna
solder access) survives at the small outline. 46 components on the netlist, **39 placed**,
7 unplaceable (the 2 solar cells + the 5 parts with no part chosen).

## Result 2 — **the outline size is NOT what blocks the routing**

| Outline | Single-ended | Multipoint pads | Vias |
|---|---:|---:|---:|
| 103 × 103 mm (array-sized) | **43/49** | — | — |
| **60 × 60 mm (component floor)** | **43/49** | **51/51 connected** | 148 |

**Identical net count at 1.7× less area.** The same 6 nets fail either way:

`/W1_SOLAR_N`, `/W2_SOLAR_N`, `/W3_SOLAR_N` (3 of 4 pairs), `/CUT_SENSE_W2`,
`/CUT_SENSE_W4`, and `GND`.

That is the finding: **the 2582 mm² oversubscription was real but it was not the binding
constraint on the router.** Shrinking the board does not fix these six nets, and enlarging
it would not either — the original 103 × 103 board failed the same six.

## Result 3 — the six failures have a common signature, and it is not density

Every one of them is a **seat-interface net**, and the router's own diagnostics name the
mechanism:

- **`GND`** — `boxed_in_static` after **5001 iterations**. Per the router's own semantics,
  `static` means *geometrically enclosed*, not *timed out*. `pad_pairs_open: GND 72/77`.
- **`/CUT_SENSE_W2`, `/CUT_SENSE_W4`** — `boxed_in_static` after **2 iterations**. Two
  iterations is not a search failure; the pad is **unreachable from the start**.
- **`/W*_SOLAR_N`** — `failed_multipoint` with the failing pad reported at
  **`J_W2 @ (32.7, 63.0)`** and **`J_W4 @ (29.1…32.7, −3.0)`**.

**Look at those coordinates.** On **every** outline the wing-tab pads land **outside the
board edge**: `y = 63.0` against a 60 mm board, `y = −3.0` against a 60 mm board. The
wing-tab pads sit at a **negative coordinate** and at **y past the top edge**. The router
cannot route to a pad that is not on the board.

## Result 4 — re-graded under the FROZEN rules (not the router's relaxed floors)

The router rewrites the output `.kicad_pro` to relax the floors again (`min_track_width`
written as **0.0889 mm**, via diameter **0.25 mm**, clearance **0.1 mm**). These numbers are
measured **after** restoring `hub_board_v9.kicad_pro` + `jlcpcb-s1-frozen.kicad_dru`:

| | 103 × 103 | **60 × 60** |
|---|---:|---:|
| Clearance | 504 | **502** |
| Hole clearance | 201 | **201** |
| Track width | 34 | **199** |
| Via diameter | 18 | **151** |
| Copper-edge clearance | — | **48** |
| **Total violations** | 816 | **1189** |
| Unconnected | 18 | **16** |

**The small board is worse, not better** — because the same 39 components are packed into
1.7× less area, so the router leans harder on sub-fab geometry to fit (track width
34→199, via diameter 18→151). Its own JSON discloses **155 `fab_tier_escalations`** and a
minimum delivered track width of **0.0889 mm**, which is **below JLCPCB's 0.10 mm floor**.

## What this means

1. **The resize is still correct as a decision** — ADR-063's decoupling is sound, it saves
   ~2.9× board mass, moves the board inside the 102 mm cheap tier, and it does not harm
   routing. But it is **not** the thing that unblocks fabrication, and it should not be
   sold as such.
2. **The real blocker is the wing-tab/GND interface**, not area: wing-tab pads at negative
   coordinates and past the top edge, plus `boxed_in_static` GND with 5 of 77 pad pairs
   unreachable. This is consistent with the earlier note that `TH1 (9.425, 9.425)` /
   `TH2 (9.425, 93.575)` are both at **x = 9.425** — i.e. the tab geometry is not being
   placed relative to the shrunk outline, and on the small board it falls off it.
3. **`/CUT_SENSE_W2` and `/CUT_SENSE_W4` fail in 2 iterations on both outlines** — their
   pads are unreachable from the start, which points at the netlist/footprint placement for
   the five `TODO(unverified)` parts, not at the router.
4. **Nothing here is orderable.** Both outlines produce a board whose copper is below the
   fab floor in places, with 16–18 unconnected nets.

## Next concrete step (not a re-run of the router)

The interface must be made outline-relative before any outline is adopted:

1. **Fix the wing-tab seat** so `J_W1..J_W4` land **on** the board for the chosen outline,
   then confirm `W*_SOLAR_N` and `CUT_SENSE_W*` route.
2. **Select or explicitly DNP** `U_CUT1–4` and `U_HUB_CVT` — five parts with no part
   chosen, which is also why the BOM cannot complete.
3. **Only then** re-run generator → route → frozen DRC, and require the router to deliver
   **≥ 0.10 mm** track/via (the fab floor) rather than relaxing to 0.0889 mm.

## Reproduce

```
cd tracker/hardware
python3 build_hub_board_v9.py --outline 60x60 --out seed
cd /data/repos/KiCadRoutingTools
.venv/bin/python py_router/route.py <seed> <out.kicad_pcb>
# then restore the FROZEN project + rules and grade:
cp hub_board_v9.kicad_pro <out>.kicad_pro ; cp jlcpcb-s1-frozen.kicad_dru <out>.kicad_dru
kicad-cli pcb drc --format json --severity-all --output drc.json <out>.kicad_pcb
```
