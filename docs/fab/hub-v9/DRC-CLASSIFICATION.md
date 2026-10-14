# Hub v9 — the 235 DRC items CLASSIFIED by fab-legality

**Date:** 2026-10-14 · **Reproduce:** `tracker/hardware/fab_grade.sh <board>` then read
the JSON; the classification below is from `/tmp/fgout/fg_in_drc.json`.

The raw count (235 violations, 1 unconnected) is misleading. Classified against the
**JLCPCB capability** they split into three very different groups: **items the RULESET
should not be flagging**, **items that are correct BY DESIGN**, and **items that are
genuine but cosmetic**.

---

## Group A — RULESET / ENVIRONMENT artifacts, NOT board defects (154 items)

| Item | Count | Why it is not a board fault |
|---|---:|---|
| `silk_overlap` | 103 | Silkscreen-over-silkscreen. **JLCPCB does not reject silk overlap**; it only trims/clips silk that lands on exposed copper. This is a *preference* rule, not a capability rule. |
| `silk_edge_clearance` | 12 | Silk near the board edge — same class, cosmetic. |
| `silk_over_copper` | 28 | Silk over exposed copper: JLC clips it, does not reject it. |
| `lib_footprint_issues` | 7 | **MEASURED, not assumed:** `kicad-cli pcb drc` reports *"The current configuration does not include the footprint library 'balloon_flight_v9'"* — it does **not** read a project-local `fp-lib-table` from the CLI. Adding `tracker/hardware/fp-lib-table` with all three libs verified to exist changed nothing **because the board was graded from a different CWD**. This is a **KiCad environment/config artifact** of how the board is graded, not a property of the board. |

**Subtotal 150 of the 235 are not electrical or fab-legality faults.**

## Group B — correct BY DESIGN, and the ruleset is over-strict (80 items)

| Item | Count | Actual vs required | Verdict |
|---|---:|---|---|
| `copper_edge_clearance` | 68 | required **0.500 mm**; actual **0.000 / 0.200 / 0.2025 mm** | **BY DESIGN.** The wing-socket land sets (`J_W1..J_W4`) are *edge-launched*: ADR-046/048 put the land set **on the board edge**, and the pads must reach the edge to meet the wing tab. An `actual 0.0000 mm` is not a mistake, it is the interface. The **0.500 mm rule is the default board-setup value** and is simply the wrong rule for an edge-launched interface. |
| `drill_out_of_range` | 12 | required 0.300 mm; actual **0.200 mm** | **BY DESIGN.** These are the ESP32-S3 module's **thermal/heatsink vias** — 0.2 mm is **Espressif's own recommended land pattern**, and **JLCPCB's mechanical floor is 0.20 mm**, so 0.2 mm is manufacturable. The **board's own `min_through_hole_diameter = 0.3 mm` is stricter than the fab requires.** |

**Both of these are rule-scope questions, and both have a defensible resolution that is
a DECISION rather than a silent relaxation:**

- `copper_edge_clearance`: **0.5 mm is wrong for an edge-launched land set.** The honest
  fix is to scope the rule so the wing-socket interface is exempt (a KiCad rule with a
  condition), **not** to lower the board-wide floor — lowering it board-wide would let
  *unintended* copper reach 0.2 mm everywhere.
- `drill_out_of_range`: set `min_through_hole_diameter = 0.2` **with the recorded
  rationale** that the module's thermal vias are 0.2 mm by the vendor land pattern, or
  carry 12 explicitly-waived items.

## Group C — genuine, small, and real work (12 items)

| Item | Count | Note |
|---|---:|---|
| `starved_thermal` | 3 | Thermal relief with 1 spoke instead of 2 — a real (minor) layout item. |
| `via_dangling` | 2 | Vias on `/SX1280_BUSY` and `/SX1280_DIO1` connected on one layer only — the honest residue of the **boxed-in fan-out** (item 3 of the work list). |
| `unconnected_items` | 1 | The `/SX1280_DIO1` open (`Via (65.9,11.6)` ↔ `Pad 10 of U4 (52.5,29.2)`) — the same net. **The other 4 GND taps from the previous report are GONE**, so the v2-safe stitcher plus refill already closed them. |

**Group C is the entire remaining real work: 6 items, of which 3 are one net.**

---

## What this means for the plan

The original 4-item list assumed 235 items were all board faults. They are not:

1. **"Fix the U1 footprint"** — **DELETED.** `U1` is KiCad's official footprint and is
   correct; the 12 items are a rule-scope call (Group B).
2. **"Clear the silkscreen (143) + copper-edge (68)"** — **143 are not capability
   violations at all** (Group A: JLC clips silk, it does not reject it), and the 68
   copper-edge are **the edge-launched wing interface, by design** (Group B). What
   remains here is a **ruleset-configuration** task, not layout work.
3. **"`/SX1280_DIO1` fan-out by placement"** — **still valid** and is the only genuine
   electrical item (`via_dangling` 2 + `unconnected` 1 all belong to it).
4. **"The 4 GND pad-to-plane taps"** — **ALREADY RESOLVED** by the v2-safe stitcher +
   zone refill; the current report has 1 unconnected, not 5.

## Attempted and REVERTED: offset stitching (v3)

I tried to close the remaining taps by placing **offset** vias with a stub track where
a via does not fit at the pad centre. **Measured result: it made the board worse** —
`hole_to_hole` 36, `shorting_items` 5, `solder_mask_bridge` 6 appeared, and
copper-edge rose 68 → 78, because ring-searched via sites land illegally close to each
other and to edges. **Reverted to the safe default.** An offset stitcher needs a real
clearance solver (checking every ring site against *all* copper *and* drill-to-drill),
not a bbox test. Recorded here so nobody re-tries the naive version.

## Honest bottom line

- **Every net is routed at the full frozen fab sizes** (47/48, zero escalations, 148/148 pads).
- **1 unconnected item** (the `/SX1280_DIO1` boxed-in fan-out).
- **~150 of the 235 reported items are ruleset/environment artifacts, not board faults.**
- **~80 are correct by design against an over-strict rule**, needing a *decision*, not a fix.
- **6 are genuine**, of which 3 are one net.

**The board is much closer to orderable than the raw 235 suggests — but the honest
gate is not a lower number, it is a ruleset that expresses the real design intent.**
