# DRC Verification Report — Independent Inspector (worker-inspector)

**Task:** t_04b2ba3a — PCB-V2 Phase 4B: Independent DRC verification — both boards
**Date:** 2026-08-05
**Inspector:** worker-inspector (cold review — did NOT trust implementer DRC files)
**Verdict:** 🚫 **BOTH BOARDS FAIL — BLOCKED (CIRCUIT BREAKER TRIPPED)**

> This verification re-ran `kicad-cli pcb drc` from scratch on the actual `.kicad_pcb`
> files in `tracker/hardware/output/`. DRC results were parsed directly from the JSON
> produced by the inspector's own `kicad-cli` runs — not from any implementer-supplied
> DRC file. Board structure (tracks/vias/zones/nets) was confirmed by direct text
> inspection of the `.kicad_pcb` files.

---

## Summary table

| Gate | Check | V1-FAST | V2-ADC | Required |
|------|-------|---------|--------|----------|
| 1 | Independent DRC: 0 violations | ❌ **52 violations** (all errors) | ❌ **115 violations** (113 error + 2 warn) | 0 |
| 1 | Independent DRC: 0 unconnected | ❌ **19 unconnected** | ❌ **12 unconnected** | 0 |
| 2 | (covered by Gate 1 per board) | — | — | — |
| 3 | No zones (copper pours) | ✅ 0 zones | ✅ 0 zones | 0 |
| 4 | Verification report written | ✅ this file | ✅ this file | yes |
| 5 | Git commit "both boards pass" + push | ⛔ NOT performed — precondition false | ⛔ NOT performed — precondition false | n/a |

**Net result: Gate 1 FAILED, Gate 2 FAILED, Gate 3 PASSED, Gate 4 DONE, Gate 5 NOT APPLICABLE (boards do not pass).**

---

## Violation breakdown (inspector-run DRC, current snapshot)

### V1-FAST — `output/v1_fast_routed.kicad_pcb`

Structure on disk: **40 track segments, 0 vias, 0 zones**, 15 footprints.

```
violations:        52   (all severity = error)
unconnected_items: 19
by type:
   solder_mask_bridge : 27
   shorting_items     : 12   ← NET SHORTS (electrical shorts between distinct nets)
   tracks_crossing    : 11
   clearance          : 2
```

**The 12 net shorts (CRITICAL — these are real electrical short circuits):**
- `GND` ↔ `3V3`   (×multiple — the EXACT V1 failure mode the plan was written to prevent)
- `3V3` ↔ `RF_SUB_868`
- `GND` ↔ `SPI_MOSI`
- `RF_SUB_868` ↔ `GND`
- `RF_2G4_2400` ↔ `GND`
- `LED_ANODE` ↔ `GND`
- `GND` ↔ `SPI_SCK`
- (others)

> The V1 plan's root-cause table (PCB-AUTO-ROUTE-EXECUTION-PLAN-V2.md line 65) lists
> "18× 3V3↔GND shorts" as the primary V1 failure. **Those shorts are present again in
> V1-FAST.** The router is producing overlapping/colliding tracks on different nets.

### V2-ADC — `output/v2_adc_routed.kicad_pcb`

Structure on disk: **165 track segments, 10 vias, 0 zones**, 17 footprints.

```
violations:        115   (113 error + 2 warning)
unconnected_items: 12
by type:
   solder_mask_bridge : 38
   tracks_crossing    : 31
   shorting_items     : 36   ← NET SHORTS (mostly 3V3↔GND)
   clearance          : 8
   track_dangling     : 2    (warnings)
```

**The 36 net shorts are overwhelmingly `3V3` ↔ `GND`** — a hard power-rail-to-ground
short that would prevent the board from powering on at all (and likely damage the LDO /
supercap on first power-up).

---

## How this was verified (independence evidence)

1. **Structure audit** — `grep -c '(segment'`, `(via'`, `(zone'` run directly on each
   `.kicad_pcb`. Confirmed track/via counts and zero copper pours independently of any
   DRC tool.
2. **Fresh DRC** — `kicad-cli pcb drc --format json --output <board>_verify.json <board>.kicad_pcb`
   run by the inspector. Output JSON parsed for `violations[]` and `unconnected_items[]`.
3. **Type/severity tally** — each violation's `type`, `severity`, and `description`
   extracted and counted; net-short descriptions enumerated verbatim.
4. **Cross-check against implementer files** — implementer's own
   `v1_fast_routed_drc.json` also reported violations + unconnected items, i.e. the
   boards were never DRC-clean even by the implementer's own measurements.

## Concurrent-modification hazard (procedural finding)

During verification the board files in the working tree were observed **changing between
read operations** (V1-FAST went 0 → 40 segments; V2-ADC went 121 → 165 segments; mtimes
advanced to 19:54:29 mid-inspection). The committed `HEAD`/index blobs differ from the
working-tree files. This indicates another process (worker-balloon routing iteration) was
rewriting these files concurrently with this verification.

**Recommendation:** independent DRC verification cannot be reliable on a file that is
being written concurrently. Before any re-verification, the boards must be frozen
(committed, no active writers) and the inspector re-run against a stable, committed SHA.

## What must happen before this gate can pass

1. Freeze the board files (commit a stable revision, kill any active routing process).
2. Re-run the routing so that DRC yields **0 violations AND 0 unconnected** for BOTH
   boards. The current routers are emitting **net shorts** — the collision grid / net
   separation in the A* router and/or the FreeROUTING import is not enforcing net-to-net
   clearance. The 3V3↔GND shorts are the highest-priority blocker.
3. Inspector re-runs DRC from scratch against the frozen SHA.

## Artifacts produced by this run

- `tracker/hardware/DRC_VERIFICATION_REPORT.md` (this file)
- `tracker/hardware/output/v1_fast_verify.json` (inspector-run DRC, V1-FAST)
- `tracker/hardware/output/v2_adc_verify.json`  (inspector-run DRC, V2-ADC)

## CIRCUIT BREAKER

Per the task's circuit-breaker clause: DRC shows violations (52 + 115, including 48 net
shorts across both boards) that the implementer's commits claimed were addressed
("feat: V1-FAST board A* routed — all nets traced", "feat: V2-ADC board A* routed — all
18 nets traced"). **Reporting BLOCKED with evidence.** Gate 5 (commit "both boards pass"
+ push) is intentionally NOT executed because its precondition is false.
