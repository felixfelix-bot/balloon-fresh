# BASE-STATION: ZONE REFILL RESOLVED THE DRC PICTURE — and my floorplan edits FAILED

**Date:** 2026-10-14 · Two results: **one decisive success, one honest failure.**

## SUCCESS: the 699 "violations" were phantom. Refill, then grade.

Following the procedure the previous note owed, I drove `pcbnew`'s `ZONE_FILLER` headless and re-ran
`kicad-cli pcb drc` on the refilled board.

| board | violations | unconnected |
|---|---:|---:|
| `bs_v1_routed_strict` (stale-zone grading) | **770** | 18 |
| **`bs_v1_routed_strict_filled` (refilled)** | **88** | **19** |

**699 clearance/hole entries → ZERO.**

| pair type | stale | refilled |
|---|---:|---:|
| track + zone | 311 | **0** |
| via + zone | 189 | **0** |
| via + zone hole clearance | 199 | **0** |
| **pad + pad** | **0** | **0** |

**And the 88 that remain are benign:**

| count | type | electrical? |
|---:|---|---|
| 48 | `silk_overlap` | no — silkscreen |
| 17 | `silk_over_copper` | no — silkscreen |
| 5 | `silk_edge_clearance` | no — silkscreen |
| 14 | `via_dangling` | minor |
| 3 | `starved_thermal` | assembly, minor |
| 1 | `lib_footprint_issues` | metadata |

**70 of 88 are silkscreen. There are NO clearance violations, NO shorts, NO crossings.** The copper
is electrically sound, and the earlier `solder_mask_bridge 41` / `shorting_items 12` counts were
**my own reverted hand routes** — this board does not have them.

**This is the third time in this campaign that grading a board before the step that makes the grade
meaningful produced a false verdict.** Now recorded as procedure: **refill, then grade.**

## FAILURE: my two floorplan attempts both made the board worse. Neither is shipped.

The motive was real and measured: `U_MCU` at x ≈ 2.6–7.4 mm, `U_FLASH` at x = 61.74, `U_VGA` at
x = 52.99 — so `QSPI_SS` (56.85 mm) and `VGA_GAIN1/2` (45.6/45.2 mm) are long **because the parts are
at opposite ends**.

**Attempt 1 — guessed coordinates** (`U_FLASH` → (22,6), `U_VGA` → (30,24)): **introduced 4 new
bounding-box overlaps.** Guess-and-hope, the pattern this campaign keeps punishing.

**Attempt 2 — rasterised free-space search** (1 mm occupancy grid over the board, pick the free site
nearest `U_MCU` that fits the part's extent): **288 overlaps and parts OUTSIDE the outline.**

**Why attempt 2 is unsound, not merely unlucky:** the occupancy grid is built from KiCad
**bounding boxes**, which include **courtyard, silkscreen and reference text** — not the copper
extent. So the "free" cells it finds are free only in a bbox sense, and a 43.2 mm-wide part like
`U_VGA` cannot be seated by centre-point placement on a grid whose resolution is coarser than the
gaps between real pads. **Grid-snapping a part whose neighbours are 0402s is the wrong method.**

**Both files are retained as evidence, neither is promoted.**

## What this tells me about the right method

The packer (`place_base_station.py`) **already does this correctly** — it cleared 44/44 with zero
gate-rectangle overlaps and everything inside the outline. **The correct move is therefore to change
the PACKER's inputs — the net-aware ordering/seed — and let it re-place, not to post-hoc shuffle two
parts in a placed board.** Post-hoc shuffling has no knowledge of the packer's own overlap model, so
it fights it.

**And the deeper point, worth stating plainly: the "long nets" problem may not need a floorplan change
at all.** 58.5 % of the board is free *as gate rectangles*, but the router's failure on those three
nets is about **corridors and layer changes**, not only distance. `U_MCU`→`U_FLASH` QSPI is 4 signal
lines that a router can take around the periphery; **45 mm of length is a signal-integrity question
at QSPI clock rates, not an impossibility.** So the honest next step is to **re-route with the packer
ordering unchanged and see whether the 19 opens persist**, before spending more on placement churn.

## Honest state

- **`bs_v1_routed_strict_filled.kicad_pcb`** — the best artifact: clean copper at the frozen floor
  (min track 0.200, via 0.600, drill 0.300), **zero clearance violations after refill**, 88 benign
  entries, **19 opens**.
- **Route is NOT complete.** 19 unconnected items remain, and the two floorplan attempts to fix them
  **failed and were reverted**.
- **No board has passed DRC, so nothing advances to a review gate.** Per the operator's gate, the
  review step comes **after** DRC passes.
