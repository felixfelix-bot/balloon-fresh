# BASE STATION — from 143 violations to an electrically clean, UN-ROUTED board

**Date:** 2026-11-11 · **Worktree:** `~/worktrees/pr-base-clean` · **Base:** `origin/master ace09314`
**Artifact of record for this commit:** `tracker/hardware/base_station/base_station_v1_unrouted.kicad_pcb`

## Result

| | before (`_placed_v2`) | after (`_unrouted`) |
|---|---:|---:|
| footprints | **44** | **53** |
| outline | 55 × 40 (declared) | **55 × 40** (was 70 × 50 in the first cut) |
| tracks / vias | 0 | 0 |
| **ERROR-severity DRC** | **74** | **0** |
| warnings | 69 | 12 (`lib_footprint_mismatch`) |
| silkscreen violations | 84 | **0** |
| unconnected records | 63 | 82 (= the ratnest exactly) |
| placement gate | PASS | PASS |
| netlist ↔ board parity | **FAIL** (53 vs 44) | **PASS** |

`unconnected == ratnest` is the completeness proof: on an unrouted board every open record must
equal `sum(pads-1)` over non-GND multi-pad nets. Here it does, exactly (32 nets, 82 opens). So
every open is an unrouted connection and **none** is lost connectivity.

## Root cause 1 — 74 of the 143 were a pour that was never computed

All 37 `clearance` **and** all 37 `solder_mask_bridge` items were **pad-vs-zone** on **two
footprints only** (U_FLASH 14, U_VGA 60). Every one reported `actual 0.0000 mm` — a value that
cannot change, because the stale `filled_polygon` was one unbroken rectangle *containing* the pads.

Measured gap from each pad's own copper polygon to the zone's **filled** polygon:

| pour state | measured gap | zone rule | verdict |
|---|---:|---:|---|
| as committed | **0.0000 mm** | 0.200 mm | artifact |
| after one refill | **0.2005 mm** | 0.200 mm | passes |

Same pads, same rules, same parts — only the pour was recomputed. 143 → 69, and the remaining 69
were 100 % silk warnings.

**This is not a rule relaxation.** `(connect_pads (clearance 0.2))` is untouched in the board and
was read back after the fill. It is the difference between grading against copper that exists and
copper that was never generated.

Reproduce: `tracker/hardware/base_station/classify_violations.py BOARD --refilled REFILLED`.

## Root cause 2 — the shipped board was built from a superseded netlist

`base_station_v1.net` (ERC-gated, parity-checked against the native schematic) declares **53**
parts. Both shipped boards carry **44**:

```
missing (12): C_FLASH, C_MCU_P10/P22/P23/P33/P42/P43/P48/P49/P50, C_VREG_OUT, R_PG
extra    (3): R_EN, R_FB1, R_FB2     ← removed by the startup-circularity fix (94025096)
```

`tracker/hardware/tests/test_netlist_integrity.py` **already failed on master** for this reason
("netlist declares 53, board carries 44"). Refilling the 44-part board would have produced a
board that *looked* clean while missing twelve parts including the whole U_MCU decoupling ring —
which is why the artifact is regenerated rather than patched.

## Pipeline (all deterministic, verified)

```
place_base_station.py   footprints from the ERC-gated netlist       (placement only)
refill_zones.py         recompute every pour                        (makes DRC meaningful)
silk_repair.py          silkscreen legible BEFORE routing            (hard gate, no allow-list)
grade                   DRC + placement + density + ratnest arithmetic
```

`build_unrouted_board.py` runs the four in order and refuses to call the result clean unless every
one passes. Determinism: builder 3× identical md5 (`a6f67baf…`); silk repair byte-identical across
runs. `kicad-cli` DRC report order is **not** stable, so every silk decision is made from a sorted
report.

## Two bugs in my own tools, found by measuring rather than asserting

1. **bbox overlap in the silk step.** Moving any silk graphic whose *bounding box* crossed a pad
   bbox moved the TP_GND/TP_5V test-point markers — a bbox containing its own pad — destroying the
   markers and adding 2 self-inflicted `lib_footprint_mismatch` warnings. Replaced with
   **DRC-uuid keying**: the report names the exact item, and an unmatched uuid is reported rather
   than guessed.
2. **A 26 mm search cap** stranded connector designators while 1220 mm² of board sat free
   ("NO SITE … within 26 mm"). The search now runs to the board diagonal. Silk went 84 → 0 in one
   round afterwards.

## Density (AGENTS.md §1b) — 55 × 40 mm adopted

`docs/fab/BASE-STATION-PLACEMENT.md` names **55 × 40** as the tight candidate and **60 × 45** as the
routing-room fallback; 70 × 50 appears there only as a utilisation comparison point (26.1 %). The
doc explicitly declines to commit — *"neither is a geometric commitment yet"* — so the outline was a
decision to make, and §1b says to take the smaller one when it is materially smaller.

| outline | area | occupancy | largest empty rect | grade |
|---|---:|---:|---:|---|
| 48 × 33 | 1584 mm² | — | — | **FAIL** — 10 `silk_edge_clearance` |
| 50 × 36 | 1800 mm² | — | — | **FAIL** — designators on the edge |
| 52 × 38 | 1976 mm² | — | — | **FAIL** — 3 silk |
| **55 × 40** | **2200 mm²** | **36.93 %** | **732.1 mm²** | **CLEAN** |
| 60 × 45 | 2700 mm² | 30.11 % | 1220.1 mm² | clean |
| 70 × 50 (rejected) | 3500 mm² | 23.22 % | 1984.6 mm² | clean |

55 × 40 is **36.8 % smaller than 70 × 50** and 18.5 % smaller than 60 × 45, and it still seats all
53 parts with 0 errors. Adoption criteria were explicit and all met: seats all 53, `SKIP 0`,
`OVERFLOW 0`, 0 ERROR-severity violations, silk 0, placement and density gates rc=0, ratnest
identity exact, pad_audit 0 findings, parity PASS.

**The floor is the SILKSCREEN, not the parts.** 52 × 38 and 48 × 33 seat all 53 perfectly
(`OVERFLOW 0`) but leave designators on `Edge.Cuts`, because §26 fixes designator text at
**0.80 mm / 0.15 mm** — the JLCPCB minimum — so it needs a certain empty margin that the packing
test does not model. Below 55 × 40 you must either shrink text under the fab minimum or accept
edge-clipped labels. That is the real binding constraint, and it was found by running the whole
gate, not the packer alone.

**Two-sided: measured, 0 mm² claimed.** `two_sided_measure.py` now *reads the movable set from the
board each run* and prints it — 3 of 53 parts (`R_PG`, `R_RUN`, `R_LNA_ILIM`) are series/pull parts
that §1b permits moving; the other 50 are pinned (U_MCU decoupler ring, ADR-084 RF chain,
connectors, test points). Three resistors cannot free a lattice row, so the claimable saving is
zero. An earlier version of that tool *printed* a hardcoded "23.22 %" verdict — 70 × 50's number —
without measuring; that is a verdict asserted in prose, exactly what §1b exists to stop, and it is
fixed.

## What is NOT claimed

- **Not routed.** 0 tracks, 82 opens. This is the legal pre-routing state, not a working board.
- **No gerbers, no fab package.** A 3D render is generated and reviewed locally (`kicad-cli pcb
  render`, 24.4 s / 629 KB — bodies present, not a flat placeholder) but is not committed.
- **12 `lib_footprint_mismatch` warnings remain.** They vary between runs (2 at one point, 12 at
  another) which suggests library resolution in the scratch workdir rather than board damage, but
  that is **not proven** and is therefore not written off.
- **The schematic's 7 declared open items are unchanged** (`RF_TEE_MAST`, `RF_LNA_OUT`,
  `RF_COAX_RX`, `RF_2450_TX`, `VGA_RF_OUT`, `USB_DM`, `USB_DP`). ERC and parity both pass against
  that baseline; neither is a zero.

## Reproduce

```
cd tracker/hardware/base_station
PYTHONPATH=/usr/lib/python3/dist-packages /usr/bin/python3 build_unrouted_board.py \
    --outline 55x40 -o base_station_v1_unrouted.kicad_pcb
```

Instruments (each prints its numbers; none is a gate that can pass silently):
`classify_violations.py`, `measure_zone_clearance.py`, `placement_gate.py`, `density_gate.py`,
`two_sided_measure.py`, `refill_zones.py`, `silk_repair.py`.
