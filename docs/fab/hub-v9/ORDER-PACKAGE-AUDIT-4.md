# ORDER PACKAGE AUDIT — 4: the shipped board is MISSING 7 parts the scheme declares

**Date:** 2026-10-14 · **Status:** ⚠ **ORDER-BLOCKING — OPERATOR DECISION REQUIRED.**
**Found during:** the attempt to regenerate the stale 103×115 repo board file.

---

## The finding

The v9 schematic netlist declares **46 components**. The shipped board carries **39**.

**Missing from the board:**

| ref | netlist value | footprint |
|---|---|---|
| `U_CUT1…U_CUT4` | *latched cut driver + cut-sense* | **NONE ASSIGNED** |
| `U_HUB_CVT` | *HUB_PV input (harvester)* | **NONE ASSIGNED** |
| `PVA1`, `PVA2` | `SolarCell_78x39mm` | **NONE ASSIGNED** |

**Root cause, measured:** these seven components carry an **empty `Footprint` field** in the
netlist. The builder consumes the netlist and loads each footprint from a library; with no
footprint named, they cannot be placed, so the generator reports them as *unplaceable* and
**parks them off-board** (the correct behaviour — added on 2026-10-14 after the park bug).

So this is **not** a generator bug. **The schematic declares parts the board cannot carry.**

## What IS on the board

The board **does** carry the cut **interface**: `CUT_W` / `CUT_SENSE` / `ARM_RAW` appear in the
board's nets. What is absent is the **driver silicon** (`U_CUT1-4`) and the **harvester**
(`U_HUB_CVT`).

## This is half-documented, and the undocumented half is the order blocker

`docs/fab/hub-v9/PART-DECISIONS.md` documents the **upstream** cause for `U_CUT`: the committed
`CUT_CHANNEL` symbol is **3-pin** (VSCAP / GND / CUT_W), so *"a 3-pin block has no GPIO, no arm
line, nothing to latch from"* — the part choice **requires a schematic symbol change** (+4
nets, ~4–8 pads/channel). `U_HUB_CVT` likewise has a recommendation (BQ25504RGTR, `C2876746`)
that was never applied to the schematic.

**What was NOT recorded, and is the actual risk:** the **consequence** — that the board we are
about to order **physically lacks** the wing-cut drivers and the power harvester, so those
functions cannot work on the delivered hardware regardless of firmware.

## Why this matters for the order

We priced `U_CUT` (~$1.11/board) and `U_HUB_CVT` (~$3.47–4.09) with consultants **for this
board** — but **neither is on it**, so **neither can be assembled**, and the PCBA BOM correctly
does not contain them.

**Nothing about the delivered PCB prevents adding them later by hand** — but the *footprints*
must exist on the board for that, and they do not.

## The decision (operator)

| option | consequence |
|---|---|
| **A. Order as-is** | 39-part board: RF, MCU, power, sensing all present and verified. **No wing-cut drivers, no harvester, no hub solar string.** Those functions are deferred to a **revision**. |
| **B. Fix the schematic first** | Assign footprints + set the real part numbers, changing `U_CUT`'s symbol to the latched form (a schematic change, per PART-DECISIONS §0) and applying `U_HUB_CVT`. Then **re-place, re-route, re-DRC, re-export** — i.e. invalidate the 48/48 routed board and redo the fab chain. |
| **C. Order as-is + a small separate cut/harvest board** | Keeps the main board verified; adds a second design to build. |

**I recommend A for a first flight article**: the missing parts are a *capability deferral*,
not a defect in what is present — and B costs a full re-route of a board that currently routes
48/48 at JLC-legal geometry. But **this must be a decision, not a silent omission**, because
the pre-order checklist did not list it and the goal is a board that flies.

## Also corrected — my own claim

I said `tracker/hardware/hub_board_v9.kicad_pcb` at 103×115 mm was a "stale tracked repo
source file". **Corrected:** that file is **not** produced by the generator and **not** the
ordered artifact — the ordered board is `docs/fab/hub-v9/gerbers/hub_v9.kicad_pcb`, generated
by `build_hub_board_v9.py` into `output/hub_board_v9_seed.kicad_pcb` and measured at
**70.2 × 71.7 mm** with the seal confirmed by the plotted `hub_v9-Edge_Cuts.gm1` (70.0 ×
71.6 mm). Running the generator **does not overwrite** the stale file. **The shipped board
remains the 70×70 ADR-068 board** — that part of audit-3 stands; the "source file" framing was
wrong.

## Reproduce

```
python3 ~/audit_netlist_components.py     # netlist 46 vs board 39
cd tracker/hardware && ~/venvs/kicad/bin/python build_hub_board_v9.py | grep unplaceable
#   -> unplaceable U_CUT1..4, U_HUB_CVT, PVA1, PVA2
```
