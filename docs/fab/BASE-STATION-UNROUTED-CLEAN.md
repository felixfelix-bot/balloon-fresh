# BASE STATION — from 143 violations to an electrically clean, UN-ROUTED board

**Date:** 2026-11-11 · **Worktree:** `~/worktrees/pr-base-clean` · **Base:** `origin/master ace09314`
**Artifact of record for this commit:** `tracker/hardware/base_station/base_station_v1_unrouted.kicad_pcb`

## Result

| | before (`_placed_v2`) | after (`_unrouted`) |
|---|---:|---:|
| footprints | **44** | **53** |
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

## Density (AGENTS.md §1b) — measured, and a decision left to the operator

| outline | area | courtyard occupancy | largest empty rect |
|---|---:|---:|---:|
| 55 × 40 | 2214.3 mm² | 36.93 % | 732.1 mm² |
| 60 × 45 | 2715.8 mm² | 30.11 % | 1220.1 mm² |
| 70 × 50 (shipped) | 3518.0 mm² | **23.22 %** | **1984.6 mm²** |
| two-sided | **0 mm² saved** | — | — |

**55 × 40 also seats all 53 parts and also grades 0 errors — 37.1 % smaller.** It is not adopted
here because the choice trades area/cost against routing headroom, and that is the operator's
call, not a measurement. 70 × 50 is kept because it is what the existing artifact and every
consumer reference.

**Two-sided buys nothing measurable on this board**, and that is a measured statement, not a
dismissal: at 23 % single-sided occupancy the binding constraint is the packer's row layout, not
part area, so a second side can only shrink the outline by splitting the ADR-084 RF chain
(LNA → BPF → VGA → detector) or the U_MCU decoupler ring across faces — both forbidden by §1b
without proof. `two_sided_measure.py` computes and prints this rather than asserting it.

## What is NOT claimed

- **Not routed.** 0 tracks, 82 opens. This is the legal pre-routing state, not a working board.
- **No gerbers, no render, no fab package.** AGENTS §4 wants a rendered image with a board claim;
  none is attached to this commit.
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
    --outline 70x50 -o base_station_v1_unrouted.kicad_pcb
```

Instruments (each prints its numbers; none is a gate that can pass silently):
`classify_violations.py`, `measure_zone_clearance.py`, `placement_gate.py`, `density_gate.py`,
`two_sided_measure.py`, `refill_zones.py`, `silk_repair.py`.
