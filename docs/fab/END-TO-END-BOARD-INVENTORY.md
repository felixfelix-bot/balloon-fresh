# END-TO-END BOARD INVENTORY — what the goal requires vs what exists

**Date:** 2026-10-14 · **Purpose:** the goal names *"3d models, schematics, board designs and
routed PCBs of **all the boards** that are required for the end-to-end system, with balloons as
a bent pipe connecting base stations via FLRC."* This is the honest gap list.

---

## The required set

The system is **flight end** (hub + 4 wings) + **ground end** (base stations at both ends of the
bent pipe). Status of each:

| board | schematic | placement | routed | DRC classified | gerbers | 3D model |
|---|---|---|---|---|---|---|
| **FLIGHT HUB v9** | ✅ netlist (46 comps) | ✅ 39 placed | ✅ **48/48 nets, 0 unconnected** | ✅ artifact/design/genuine split | ✅ 14 files + zip | ⚠ **per-part `.wrl` only — no assembled model / STEP** |
| **FLIGHT WING v9** | ✅ | ✅ 15 fp | ✅ 0 unconnected | ✅ 35/37 artifact | ✅ zip, sha256 recorded | ⚠ `.wrl` cells + tab lands, no assembled model |
| **BASE STATION** | ⛔ **DOES NOT EXIST** | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| **BASE STATION enclosure** | n/a | ✅ `hardware/ground-station/dish/dish.scad` (dish only) | n/a | n/a | n/a | ✅ `.scad` |
| Flight hub enclosure | n/a | ✅ STL/SCAD set | n/a | n/a | n/a | ✅ |

## Gap 1 — the base-station board is DESIGNED BUT NEVER LAID OUT (largest gap)

`docs/BASE-STATION-PCBA-D14-FREEZE.md` freezes the **parts and the network** for *"schematic
capture"* — and says in its own status line:

> **"STATUS: DESIGN FREEZE NOTE — not a KiCad layout and not an operator purchasing
> authorization."**

**Measured:** there is **no `.kicad_pcb`, no `.kicad_sch`, no netlist, no gerbers and no 3D
model** for the base station anywhere in the repo. The only related artifacts are
`hardware/ground-station/dish/dish.scad` (a dish, i.e. mechanical) and ~10 analysis documents.

**So the ground end — half of the "bent pipe" — has no board at all.** The frozen content is
substantial and lays out cleanly (row 7 AD8318 log detector, row 8 RP2040, row 14 bias tee +
TPS62162 + load switches, row 11/18 DNP), so a layout is **tractable**, but nothing exists yet.

## Gap 2 — no assembled 3D model of either flight board

The repo has **per-component `.wrl` envelopes** (`u1_esp32s3_wroom1u_envelope.wrl`,
`u4_sx1280_qfn24_envelope.wrl`, …) and **enclosure STL/SCAD**, but **no STEP or assembled 3D
model of a populated board**. The goal explicitly lists *"3d models"*. Two ways to close it:
1. **KiCad-native:** `kicad-cli pcb export step` produces a STEP of the board with its 3D models
   — needs 3D models assigned to footprints (partly done, via the `.wrl` envelopes).
2. **STL/STEP from the board** for mechanical fit checks against the enclosure.

## Gap 3 — superseded v1/v2/F33 boards are mixed in with the current set

`tracker/hardware/` holds `hub_board_v1*` (7 variants), `v2_*`, `v1_fast_*`, and
`hub_board_f33.kicad_pcb`. These are **historic**, not part of the order. They are not
misleading in themselves, but the goal's "all the boards" needs a **current-vs-superseded
register** so nobody re-exports the wrong one (the failure class this campaign keeps hitting).

## What closing the gaps requires

| gap | action | effort |
|---|---|---|
| **Base-station board** | schematic capture from the D14 freeze → placement → route → DRC → gerbers. It has **no fine-pitch RF escape problem** (the 433 chain is connector/coupler-level, the MCU is an RP2040 QFN-56), so it is materially easier than the hub. | **new design**, the real remaining work |
| **3D models** | `kicad-cli pcb export step` on both v9 boards; assign any missing footprint 3D models first | **hours**, mechanical |
| **Register** | one current-vs-superseded table for `tracker/hardware/` | minutes |
| **Base-station source** | `VIN_GS` 9–18 V input; the D14 freeze notes the **TPS62162 is 3–17 V rated** so the 18 V upper bound must be enforced upstream — a live constraint for the schematic | design input |

## Honest headline

**The flight end is essentially done** (both boards routed, electrically complete, packaged,
audited). **The ground end does not exist as a board.** The goal cannot be described as complete
while half the bent pipe has no PCB — and that board is **new design work**, not a gap fix.

## Reproduce

```
# no BASE-STATION board anywhere -- every .kicad_pcb in tracker/hardware/output is a
# hub/flight variant (v1..v9, f33, v_c3) or an interposer:
find . -name '*.kicad_pcb' | wc -l                       # 100+ files, all flight-end
find . -name '*.kicad_pcb' | grep -icE 'station|basetation|ground'   # -> 0
grep -n 'not a KiCad layout' docs/BASE-STATION-PCBA-D14-FREEZE.md      # the freeze's own words
# no assembled STEP for any board:
find . \( -name '*.step' -o -name '*.stp' \) | grep -v '\.git'         # -> (nothing)
# per-part .wrl envelopes DO exist (8 in tracker/hardware/3dmodels/hub/) but they are
# component envelopes, not an assembled board model:
ls tracker/hardware/3dmodels/hub/
```
