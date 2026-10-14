# FIX THE SCHEMATIC FIRST — plan, blockers, and the integrity gate

**Date:** 2026-10-14 · **Status:** ⚠ **3 of the 7 fixes are NOT mechanically derivable.**
Operator ruled **Option B** (fix the schematic, accept board invalidation). This records exactly
what the fix requires, what is blocked, and the deterministic gate now in place.

Supersedes my **Option A** recommendation.

## What must change (the 7 parts, measured)

| ref | declared value | netlist footprint | fix needed |
|---|---|---|---|
| `PVA1`, `PVA2` | `SolarCell_78x39mm` | **empty** | **BLOCKED — see §1** |
| `U_CUT1…U_CUT4` | *latched cut driver + cut-sense* | **empty** | **BLOCKED — see §2** |
| `U_HUB_CVT` | *HUB_PV input (harvester)* | **empty** | **BLOCKED — see §3** |

**Root cause (measured, confirmed):** the schematic's `CUT_CHANNEL` symbol is **3 pins** —
`(1 VSCAP) (2 GND) (3 CUT_W)`. **That is the defect the operator named**: a 3-pin block has **no
GPIO, no arm line, nothing to latch from**, so no real latched part can be assigned to it.
`HUB_CONVERTER` is likewise **3 pins** (`PV_P / GND / PV_N`) — **a 3-pin part with no output pin**,
so it cannot be a harvester with a power path to the rail.

## §1 `PVA1`/`PVA2` — the cells cannot be on this board

`SolarCell_78x39mm` is **78 × 39 mm**. Two in series via `D_HUB1`/`D_HUB2` =
**78 × 78 mm of cell area**. The hub board is **70 × 70 mm**.

**The cells physically cannot be placed on the hub**, and allowing them would blow the agreed
envelope. **This is not a footprint-assignment task — it is a topology decision:**

- **Option 1 — designated off-board connector** (no board invalidation for these two). The hub PV
  pair then terminates at a connector, exactly as the wing solar already does at `J_W1…J_W4`
  (pins 1/4 per wing). `docs/analysis/PANEL-MOUNTING-OFF-BOARD.md` already argues panels are
  **off-board**, so this is consistent with existing analysis, and it makes `PVA1`/`PVA2`
  *mechanical drawings*, not PCBA parts — they then leave the **order** BOM entirely.
- **Option 2 — delete `PVA1`/`PVA2`** and let the PV pair enter through the existing connector.

**Option 1 is my recommendation**: it preserves the string topology the netlist already encodes
(`HUB_PV_P → D_HUB1 → HUB_PV_MID1 → D_HUB2 → HUB_PV_N`), keeps the bypass diodes
(`D_HUB1`, `D_HUB2`) on the PCBA where they belong, and removes no order line.

## §2 `U_CUT1…4` — blocked on the pin contract

Required, measured: a **latched** driver with **drive**, **arm**, **GPIO**, **GND**, **VSCAP**, and
**cut-sense** — because the cut must latch **independently of MCU state** (`ARM_RAW`), and the
`CUT_SENSE_W*` nets exist to confirm the cut happened.

**Current symbol supplies 3 pins. A real part needs ~6.** Assigning a footprint to a 3-pin symbol
would produce a land pattern whose pads cannot be netted — **a board that routes but is
electrically wrong.** So this **must** be a symbol change:
*3-pin `CUT_CHANNEL` → latched form with drive/arm/GPIO/sense*, then a real part, then re-place.

**Part candidates (not selected — selection is not mine to guess):** the class is a latched load
switch / nano-power latch, e.g. a **TI `LTC2954`-class pushbutton on/off controller** (latch +
enable, has the independent-control property the design wants) against a simple
**MOSFET latch** (2 transistors, no IC). **I am not picking one** — the choice sets GPIO count,
quiescent draw and VSCAP load-bearing, all of which the power budget already constrains.

## §3 `U_HUB_CVT` — part IS named; symbol is wrong

`ORDER-PACKAGE-AUDIT-4` records a **recommendation that was never applied: `BQ25504RGTR`
(`C2876746`)** — and I verified that part **LIVE, in stock 21 @ $4.5857** during the F33 check,
so it is real and orderable.

**But the `HUB_CONVERTER` symbol is 3 pins with no output.** `BQ25504` has `VIN_DC`, `VSTOR`,
`VOUT` pins at minimum. **So this too is a symbol change, not a footprint assignment.**

## §4 What is NOT blocked

- **`U_CUT`'s symbol → latched form**: mechanical once the pin contract is chosen.
- **`U_HUB_CVT` symbol → apply `BQ25504RGTR`**: the part is confirmed in stock.
- **Re-place, re-route, re-DRC, re-export**: the whole chain is proven (the base station now
  places 44/44 and the strict route is clean at the frozen floor).

## §5 The regression gate (delivered, deterministic)

`tracker/hardware/tests/test_netlist_integrity.py` — **10 pass, 4 FAIL**, and all four failures are
the real defects. It encodes six classes, each a failure that actually occurred:

| | class | what it catches |
|---|---|---|
| **A** | empty footprint field | the 7 comps → **the order blocker** |
| **B** | footprint does not resolve | a named footprint no library provides |
| **C** | **declared ≠ placed** | **the check that would have caught A** |
| **D** | duplicate designators | two parts on one ref |
| **E** | `TODO` as a part value | unverified parts (discovered, not hardcoded — **8 in v9**, not 5) |
| **F** | DRC floor relaxation | a router grading against floors it rewrote |

**Class C is the important one.** It compares the netlist's declared set against the board's
footprint count, so **it fails on the exact defect that reached the order package.** It reads the
board with `pcbnew` and the netlist with regex, so it cannot be satisfied by editing one side.

**Run it before any order.** Every A/B/C/D failure is an order blocker.

## §6 Order impact

**The hub board cannot be ordered while `C` fails** — the delivered hardware would lack the wing-cut
drivers and the power harvester, so those functions could not work regardless of firmware.

**The base station is unaffected** (44 declared, 44 placed, footprints all resolve).

**Still required before the order** (unchanged from the previous list): the LCSC BOM build, the
loose MAX-M10S line, the 0.8 mm re-price, the per-placement fee, and the schematic annotation
cleanup (`kicad-cli` warns the schematic is not clean, which undermines every schematic-derived
export — including the netlist this defect lives in).
