# ADR-067 — Hub board: continuous GND return on the 4-layer stack

**Status:** Accepted (2026-10-11)

## Context

`tracker/hardware/build_hub_board_v9.py` produced a **placement-only** board:
39 footprints, **0 tracks, 0 vias, and 0 copper zones**. The stack declares
`LAYER_COUNT = 4` with `In1.Cu` / `In2.Cu` (ADR-029), but those inner layers
were **declared and empty**, and the outer faces were bare. The 0.6 mm 4-layer
panel therefore provided **no continuous return path** — every GND return had to
share the signal layers, and `In1.Cu` (the dedicated ground layer of this
stackup) carried no copper at all.

Measured on the committed board with `kicad-cli pcb drc` (KiCad 9.0.8,
`--severity-all`): **157 unconnected items**, of which **66 were GND**.

## Decision

Pour GND zones on **In1.Cu + F.Cu + B.Cu**, clipped 0.5 mm inside the
board-level Edge.Cuts outline. `In2.Cu` and the signal routing stay clear.

Three constraints shaped the implementation:

1. **The plane must reach the GND pads.** An inner-layer-only pour moved the
   unconnected count by **one** (157 → 156) because the 79 GND pads are almost
   all SMD lands on **F.Cu** — an inner plane cannot reach them without a via
   per pad. So `F.Cu` is poured too. *A ground plane that changes nothing
   measurable is not a fix.*
2. **The outline is board-level Edge.Cuts only.** `J_W1..J_W4` are wing-tab
   footprints whose **footprint-level** Edge.Cuts graphics stick ~6 mm past the
   panel and inflated the naive bbox to **103.15 × 115.05 mm**. Filtering to
   board-level edges gives the correct **103.15 × 103.15 mm** outline and the
   fill clips to 0.5–102.5 mm with no leak.
3. **Small QFN lands connect SOLID, not thermally.** A 0.80 × 0.25 mm land
   (U4's SX1280 QFN24 perimeter GND pads) cannot host **two** 0.3 mm spokes
   across its short axis, so a thermal connection DRC-fails as
   `starved_thermal`. Narrowing the spoke from 0.5 → 0.3 mm did **not** fix it —
   the limit is geometry, not width. Any GND pad too small to take two spokes is
   therefore overridden to `ZONE_CONNECTION_FULL`. The QFN is reflow-only, so a
   solid tie is also the lower-impedance, correct answer there. Hand-solderable
   parts keep their thermal reliefs.

The fix is applied to the **frozen artifact** through a new no-re-place mode
(`--add-planes BOARD`) because the committed board was generated from an earlier
`EDGE_SEATS` offset than the current generator (5 edge-seated refs drift by
exactly 1.000 mm). Re-running the generator wholesale would apply an
unrequested 1 mm layout change.

## Evidence

`kicad-cli pcb drc`, same board, before vs after (KiCad 9.0.8):

| class | before | after |
|---|---|---|
| `unconnected_items` | **157** | **101** |
| `copper_edge_clearance` | 16 | 16 |
| `silk_over_copper` | 16 | 16 |
| `drill_out_of_range` | 12 | 12 |
| `silk_overlap` | 12 | 12 |
| `lib_footprint_issues` | 7 | 7 |
| `silk_edge_clearance` | 6 | 6 |
| `starved_thermal` | 0 | **0** |
| **total** | **226** | **170** |

The 56-item reduction is **entirely GND (66 → 10)**; every other net is
byte-identical. The pour introduces **zero** new violation classes.

Placement is preserved: **0 of 39 footprints moved** (verified ref-by-ref,
position and layer, against the pristine committed board).

## Residual (tracked, not silently absorbed)

10 GND items remain unconnected and are a **separate** defect:

- `J_W1..J_W4` pads 2/4 — the 4 hub-side wing connectors sit inside the
  breakaway-tab region, where the pour is **correctly** clipped away (copper on a
  breakaway tab is a fracture risk). Their F.Cu and B.Cu halves are also
  unconnected **to each other**, so they need explicit stitching.
- `U4` pad 19 and `ANT4` pad 2.

Also still open in the BOM: `R_NTC1` and `TH_NTC1` = `TODO(unverified)`, and
`D_CLAMP` = "TVS clamp (set point TODO(unverified))".

## Consequences

- The 4-layer stack now has a real ground reference on In1.Cu, with redundant
  F.Cu/B.Cu pours for shielding and return.
- The 16 `copper_edge_clearance` and 12 `drill_out_of_range` violations are
  **pre-existing** in the baseline (`J_W1..J_W4` geometry straddles Edge.Cuts;
  0.2 mm PTH holes against a 0.3 mm rule). This ADR does not address them.
- Hub connectors' GND stitching is deferred to a follow-up card.
- Generator scratch (`output/.hub_v9_libcache/`, `output/.hub_v9_scaffold.kicad_pcb`)
  is now git-ignored — it is regenerated on every run.
