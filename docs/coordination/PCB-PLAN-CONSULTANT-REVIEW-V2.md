# PCB Auto-Route Execution Plan V2 — Consultant Re-Review

**Date:** 2026-08-05
**Reviewer:** Consultant Profile (verification re-review)
**Document reviewed:** `PCB-AUTO-ROUTE-EXECUTION-PLAN-V2.md` (1,573 lines)
**Original review:** `PCB-PLAN-CONSULTANT-REVIEW.md` (5 blockers, 11 major issues, 6 minor issues)
**Purpose:** Verify all 5 blockers and 11 major issues from the first review are fixed. Check for new issues introduced by the revision.

---

## Executive Summary

The V2 plan is a thorough, well-executed revision. All 5 blockers are fixed. All 11 major issues are fixed. The plan is self-contained, correctly assigns workers by domain expertise, uses executable quality gates, and includes circuit breakers and git push in every phase. Two minor residual issues were found (non-blocking) and two observations for future attention. The plan is ready for kanban scheduling.

---

## BLOCKER VERIFICATION (5/5 FIXED)

### BLOCKER 1: LoadBoard() → NewBoard() — ✅ FIXED

**Original issue:** Pipeline code copied from `LLM-AUTO-ROUTING-PIPELINE.md` used `LoadBoard()` in two places, which fails headless. The V1 plan acknowledged this but only suggested "may need to be combined" — not a hard requirement.

**V2 fix verification:**
- Line 33: Environment facts table explicitly marks `LoadBoard()` as `❌ NEVER USE`
- Line 44: Dedicated section "CRITICAL: LoadBoard() is BANNED" with full explanation
- Line 46: Explicit instruction — "If you find yourself writing `LoadBoard()`, STOP — you are introducing a guaranteed failure"
- Line 321: Phase 1 objective states code "MUST be adapted to use `NewBoard()` throughout"
- Line 323: Task 1.1 title includes "(uses NewBoard, NOT LoadBoard)"
- Lines 329-345: Mandatory modification block listing both LoadBoard locations (lines 826, 872) and the 9-step replacement procedure
- Line 370: Code comment: "MODIFIED: all LoadBoard() calls replaced with NewBoard()"
- Line 374: `create_board_v1_fast()` uses `pcbnew.NewBoard(output_path)` ✅
- Line 383: `create_board_v2_adc()` uses `pcbnew.NewBoard(output_path)` ✅
- Line 451: Quality Gate 2 — `grep -c 'LoadBoard'` must return 0 (enforcement gate)
- Line 1172: DRC loop spec: `board = pcbnew.NewBoard(output_path)` with comment "ALWAYS NewBoard, NEVER LoadBoard"
- Line 1412: Appendix B API reference: "ALWAYS use NewBoard, NEVER LoadBoard"
- Line 1518: Appendix E reminder #2: "USE `NewBoard()` — NEVER `LoadBoard()`"

**All LoadBoard() references in V2 are either "DO NOT USE" warnings or grep-based enforcement gates. No code example uses LoadBoard() as a functional call.** ✅ VERIFIED FIXED

---

### BLOCKER 2: DRC Verification Reassigned to worker-inspector — ✅ FIXED

**Original issue:** Phase 4 DRC verification was assigned to worker-balloon — the same worker who wrote the pipeline and ran the router. No independent review.

**V2 fix verification:**
- Line 78: Worker profiles table — `worker-inspector` assigned "Independent DRC verification + code review" with "different model"
- Line 87: Reassignment note — "Phase 4 DRC final verification moved from worker-balloon → worker-inspector (independent review)"
- Phase 4 split into 4A (worker-balloon, iterative fixing) and 4B (worker-inspector, independent verification)
- Line 638: Phase 4A objective explicitly states "Phase 4B (worker-inspector) does the final independent verification"
- Line 740: Phase 4B header — "Independent DRC Verification (worker-inspector, 30 min)"
- Line 744-746: Separation of concerns rationale — "worker-balloon has incentive to declare 'DRC passes'... worker-inspector has no such bias"
- Line 751: "worker-inspector runs DRC from scratch — does NOT trust worker-balloon's results"
- Lines 756-783: Inspector verifies both DRC counts AND board content (footprints, nets, tracks, zones) — false-pass detection implemented
- Lines 788-817: Same verification for V2-ADC board
- Line 829: Circuit breaker for inspector discrepancy detection
- Line 1520: Appendix E #4: "Confirmed by worker-inspector (independent), not worker-balloon"

**Independent DRC verification by a different worker using a different model, with false-pass detection.** ✅ VERIFIED FIXED

---

### BLOCKER 3: Quality Gates in Task Body Text — ✅ FIXED

**Original issue:** Quality gates were in markdown tables at the end of each phase, not explicitly marked as task body content. Race condition risk when transcribed to kanban cards.

**V2 fix verification:**
- Line 48-50: Dedicated section "CRITICAL: Quality Gates Go in Task Body Text" — "ALL quality gate checks MUST be embedded in the task body (`--body` parameter at card creation time), NOT added as comments"
- All 9 quality gate sections across 8 phases use the header: `QUALITY GATES (MANDATORY — embed in task body, not comments):` (lines 449, 559, 621, 717, 820, 936, 985, 1073, 1144)
- Quality gates are checkbox lists `[ ]` with executable shell commands, not table rows
- Line 1528: Appendix E #12: "QUALITY GATES IN TASK BODY — All quality gates are mandatory task body content, not comments or metadata. Embed them in `--body` at kanban card creation."

**Quality gates are explicitly marked as task body content with instructions for kanban card creation.** ✅ VERIFIED FIXED

---

### BLOCKER 4: Circuit Breaker in Every Iterative Task — ✅ FIXED

**Original issue:** No circuit breaker (3 strikes) specified in any iterative task. Workers could spin indefinitely on the same error.

**V2 fix verification — 9 circuit breakers found:**
1. **Phase 1 (line 458):** "If the pipeline crashes 3 times consecutively with the same error, STOP. Write a failure summary... Return BLOCKED status."
2. **Phase 2 (line 570):** "If board creation fails 3 times consecutively with the same error... STOP. Write failure summary... Return BLOCKED status."
3. **Phase 3 (line 630):** "If the A* router fails to route the same net 3 times consecutively, STOP... Return BLOCKED status. Do NOT retry — escalate to orchestrator."
4. **Phase 4A (line 727):** "If the same DRC violation persists for 3 consecutive iterations, STOP... Return BLOCKED status."
5. **Phase 4B (line 829):** "If the same DRC discrepancy is found 3 times (e.g., worker-balloon says 0/0 but worker-inspector finds violations), STOP... Return BLOCKED status."
6. **Phase 5 (line 946):** "If gerber export fails 3 times consecutively with the same error, STOP... Return BLOCKED status."
7. **Phase 6 (line 991):** "If CI fails 3 times consecutively with the same error, STOP... Return BLOCKED status."
8. **Phase 7 (line 1081):** "If SPI communication fails 3 times consecutively at the same frequency with the same error, STOP... Return BLOCKED status."
9. **Phase 8 (line 1152):** "If a test script fails to run 3 times consecutively with the same error, STOP... Return BLOCKED status."

Additionally, Phase 4A has intermediate escalation criteria (lines 683-686):
- After 3 iterations with no violation count decrease → escalate
- After 5 iterations with shorts still present → escalate
- If only unconnected items remain → try manual S-expression editing

Line 1527: Appendix E #11 reiterates the circuit breaker rule.

**Every phase has a 3-strike circuit breaker with BLOCKED status and escalation.** ✅ VERIFIED FIXED

---

### BLOCKER 5: Git Commit + Push in Every Task Body — ✅ FIXED

**Original issue:** No explicit git commit + push step in any phase's task sequence. Only an appendix reminder.

**V2 fix verification — 9 git commit+push gates found (one per phase):**
1. **Phase 1 (line 456):** `git commit -m "Phase 1: Pipeline code with NewBoard, no LoadBoard, V1-FAST smoke test" && git push github autonomous/mesh-baseline`
2. **Phase 2 (line 568):** `git commit -m "Phase 2: V1-FAST + V2-ADC boards created, footprints placed, nets assigned, no routing" && git push github autonomous/mesh-baseline`
3. **Phase 3 (line 628):** `git commit -m "Phase 3: A* auto-routing complete for V1-FAST and V2-ADC boards" && git push github autonomous/mesh-baseline`
4. **Phase 4A (line 725):** `git commit -m "Phase 4A: DRC iteration complete — V1-FAST and V2-ADC both at 0 violations / 0 unconnected" && git push github autonomous/mesh-baseline`
5. **Phase 4B (line 827):** `git commit -m "Phase 4B: Independent DRC verification PASSED..." && git push github autonomous/mesh-baseline`
6. **Phase 5 (line 944):** `git commit -m "Phase 5: Gerbers exported for V1-FAST and V2-ADC, old V1 gerbers deleted..." && git push github autonomous/mesh-baseline`
7. **Phase 6 (line 989):** `git commit -m "Phase 6: CI updates — relay pipeline + nostr_dump test suites added" && git push github autonomous/mesh-baseline`
8. **Phase 7 (line 1079):** `git commit -m "Phase 7: SPI timing characterization complete..." && git push github autonomous/mesh-baseline`
9. **Phase 8 (line 1150):** `git commit -m "Phase 8: Integration test scripts written..." && git push github autonomous/mesh-baseline`

All use the same branch (`autonomous/mesh-baseline`) and remote (`github`). Each is a quality gate checkbox with the exact command.

Line 1525: Appendix E #9 reiterates: "COMMIT AND PUSH — Uncommitted work is invisible to the orchestrator."

**Every phase has an explicit, executable git commit + push quality gate.** ✅ VERIFIED FIXED

---

## MAJOR ISSUE VERIFICATION (11/11 FIXED)

### MAJOR 1: worker-fips CI tasks → worker-admin — ✅ FIXED

- Line 79: Worker table — `worker-admin` assigned "CI updates + integration scripts + documentation" for Phases 6, 8
- Line 85: "Phase 6 (CI Updates) moved from worker-fips → worker-admin (CI is DevOps work, not FIPS)"
- Line 956: Phase 6 header — "Phase 6: CI Updates (worker-admin, 30 min)"
- Line 80: worker-fips explicitly marked "(not assigned to PCB plan phases)"

### MAJOR 2: worker-fips SPI timing → worker-balloon — ✅ FIXED

- Line 77: Worker table — `worker-balloon` assigned Phase 7
- Line 86: "Phase 7 (SPI Timing) moved from worker-fips → worker-balloon (SPI timing is firmware work)"
- Line 997: Phase 7 header — "Phase 7: SPI Timing Characterization (worker-balloon — during 2-week JLCPCB wait)"
- Timeline (line 1325): "SPI timing characterization on S3 test board | worker-balloon | 4h"

### MAJOR 3: GPIO8 Conflict Resolved — ✅ FIXED

- Lines 160-166: Dedicated "GPIO8 Fallback Conflict Resolution (FIXED)" section
- V1-FAST: ADC disabled, GPIO8 free for FEM_TX fallback (no conflict)
- V2-ADC: FEM_TX redirected to GPIO0, GPIO8 dedicated to ADC (no conflict)
- If GPIO0 unavailable on V2-ADC: FEM_TX falls back to GPIO19 (original), GPIO8 stays on ADC
- Line 166: "The 'mux' fallback from the V1 plan is removed — there is no mux component in the BOM"
- No mux component appears anywhere in the BOM or net lists

### MAJOR 4: GPIO2 Pull-Down in BOM — ✅ FIXED

- Line 228: Component table — `R_PD | 10kΩ 0402 | 0402 | (10, 14) | GPIO2 pull-down (boot strapping)`
- Line 177: Net list includes R_PD:1 on GND net
- Line 256: R_PD:2 connects to SPI_MISO net (GPIO2)
- Lines 249-257: Dedicated "GPIO2 Pull-Down Resistor (ADDED per consultant review)" section
- Line 253: "R_PD (10kΩ pull-down) is added to the BOM for BOTH board variants"
- Line 194: V1-FAST total includes R_PD in component count
- Line 203: V2-ADC total includes R_PD in component count
- Line 1495: Appendix D GPIO reference confirms pull-down requirement
- Line 1509: Boot strapping section confirms R_PD in BOM for both variants

### MAJOR 5: KiCad GUI Rollback References Removed — ✅ FIXED

- Line 1336: Rollback summary header — "ROLLBACK PLANS SUMMARY (HEADLESS ONLY — NO KiCad GUI)"
- All 8 rollback entries use headless alternatives:
  - Edit .kicad_pcb S-expression text directly
  - Adjust A* grid parameters
  - Simplify design (drop non-essential nets)
  - Escalate to Felix for manual creation on his personal machine
- Line 1357: "Felix — he may manually design the board on a machine with a display (this is the only GUI-allowed path, and it requires Felix's personal machine, not the headless server)"
- Line 1360: "ALL rollback plans are headless-compatible. No rollback requires KiCad GUI on this server."
- Line 1530: Appendix E #14: "NO KICAD GUI — This server is headless."
- Remaining "GUI" references are all in the context of "no GUI" or "Felix's personal machine as last resort" — acceptable.

### MAJOR 6: JLCPCB Upload Marked as Manual Human Step — ✅ FIXED

- Line 82: Worker table — `Felix (HUMAN)` assigned "JLCPCB web upload + order approval" for "Phase 5 Task 5.5 (manual)"
- Line 907: Task 5.5 header — "JLCPCB Order — MANUAL HUMAN STEP (Felix)"
- Line 909: "⚠️ This is a FELIX ACTION ITEM. No worker agent can do this."
- Lines 911-918: Step-by-step instructions for Felix (human actions: go to website, upload, verify preview, checkout)
- Line 1531: Appendix E #15: "JLCPCB UPLOAD IS HUMAN — Task 5.5 is a Felix action item. Workers produce the zip files; Felix does the upload."
- Worker's Phase 5 deliverable is gerber zips + order checklist (Tasks 5.1-5.4)

### MAJOR 7: Phase 7 Dependency Fixed — ✅ FIXED

- Line 309: Dependency graph — "Phase 7 (SPI Timing, worker-balloon) ── depends on Phase 5 gerber export (NOT board arrival)"
- Line 313: "Phase 7 depends on Phase 5 gerber export completion (not board arrival). SPI timing characterization uses the existing S3 test board as a proxy. Actual V2 board testing happens post-arrival (Day 14+)."
- Line 1003: Phase 7 objective reiterates: "Phase 7 depends on Phase 5 gerber export completion for scheduling priority only. It does NOT depend on board arrival."
- Timeline (line 1325): SPI timing on Day 1-2 of JLCPCB wait — consistent with dependency on Phase 5 gerber export (which happens before the wait begins), not board arrival

### MAJOR 8: RF Trace Impedance Corrected — ✅ FIXED

- Lines 191-192: Net list — RF_SUB_868 and RF_2G4_2400 both at **0.76mm** track width (was 0.25mm)
- Lines 205-211: Dedicated "RF Trace Impedance Note (FIXED from consultant review)" section
- Line 207: "0.25mm trace is closer to 75-80Ω" — correct physics
- Line 209: Prototype acceptance rationale — "LR2021 module has its own onboard matching network and the antenna traces are short (<10mm)"
- Line 211: Production guidance — "Use JLCPCB impedance-controlled stackup or calculate exact width based on the actual stackup parameters"
- Line 1179: DRC loop spec — RF width = 0.76mm
- Lines 1304-1305: Routing priority order — RF traces at 0.76mm width

### MAJOR 9: V2 Board Section with ADC Pin — ✅ FIXED

- Lines 113-137: Full V2-ADC pin assignment table with GPIO8 marked as "**Required**" for ADC
- Line 115: Redesign rationale — "FEM_TX moves from GPIO19 to GPIO0 (dropping GPS TX)"
- Lines 196-203: V2-ADC net list — 18 nets, 18 components, includes VDIV_MID net
- Lines 238-247: V2-ADC component list with R_DIV1 and R_DIV2
- Line 199: VDIV_MID net connects C3:GPIO8, R_DIV1:2, R_DIV2:1
- Lines 509-531: Task 2.3 creates V2-ADC board programmatically
- Lines 589-602: Task 3.2 routes V2-ADC board
- Lines 689-705: Task 4A.3 runs DRC on V2-ADC
- Lines 786-817: Task 4B.2 inspector verifies V2-ADC
- Lines 860-879: Task 5.2 exports V2-ADC gerbers

### MAJOR 10: Both Boards in Same JLCPCB Order — ✅ FIXED

- Line 18: "Felix has decided to build TWO board variants in the same JLCPCB order"
- Line 22: "Both boards ordered in the same JLCPCB batch"
- Lines 911-917: Task 5.5 instructs Felix to upload both zips as separate designs, add both to cart, checkout in same order
- Lines 920-934: JLCPCB order checklist table covers BOTH boards side by side
- Line 932: "Both in same shipment"
- Line 1529: Appendix E #13: "Both in same JLCPCB order. Both must pass DRC independently."

### MAJOR 11: Board Files Moved from /tmp to Persistent Location — ✅ FIXED

- Line 1398: "Working Directory (NOT /tmp — files persist across reboots)"
- Line 1400: "All board files are stored in the repository under `tracker/hardware/output/` instead of `/tmp/`"
- All output paths in tasks use `~/repos/balloon-fresh/tracker/hardware/output/`:
  - `v1_fast_unrouted.kicad_pcb` (line 493)
  - `v1_fast_routed.kicad_pcb` (line 433)
  - `v2_adc_unrouted.kicad_pcb` (line 517)
  - `v2_adc_routed.kicad_pcb` (line 600)
  - DRC JSON files (lines 644, 695, 753, 790)
- Gerber directories use `~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fast/` and `gerbers_v2_adc/` (lines 842, 863)
- **Note:** Two `/tmp` references remain in quality gate verification commands (lines 454, 566) — these are temporary DRC output files for one-off checks, not board files. Acceptable since they're throwaway verification artifacts, not pipeline outputs. Also line 970 references `/tmp/test_relay` for CI test binary — also acceptable.

---

## ADDITIONAL CHECKS

### Worker Assignment Correctness — ✅ PASS

| Phase | Worker | Domain Match | Verdict |
|-------|--------|-------------|---------|
| 1 (Pipeline Code) | worker-balloon | PCB pipeline + board creation | ✅ Correct |
| 2 (Board Creation) | worker-balloon | PCB pipeline + board creation | ✅ Correct |
| 3 (Auto-Route) | worker-balloon | PCB pipeline + board creation | ✅ Correct |
| 4A (DRC Iteration) | worker-balloon | Same worker fixes own routing | ✅ Correct (fixer role) |
| 4B (DRC Verification) | worker-inspector | Independent review, different model | ✅ Correct (checker role) |
| 5 (Gerber Export) | worker-balloon + Felix | PCB worker + human for upload | ✅ Correct |
| 6 (CI Updates) | worker-admin | DevOps/infrastructure | ✅ Correct |
| 7 (SPI Timing) | worker-balloon | Firmware/hardware validation | ✅ Correct |
| 8 (Integration Scripts) | worker-admin | Scripts/documentation | ✅ Correct |

worker-fips is explicitly excluded from PCB plan phases (line 80). worker-tollgate is also excluded (line 81).

### Quality Gate Checkbox Executability — ✅ PASS

All quality gates use concrete, executable shell commands or Python one-liners:
- `grep -c 'LoadBoard' ... returns 0` — executable, binary pass/fail
- `grep -c '(zone' ... returns 0` — executable, binary pass/fail
- `kicad-cli pcb drc --format json --output ... exits 0` — executable, exit code check
- Python JSON parsing scripts with explicit count comparisons — executable
- `git add -A && git commit -m "..." && git push ...` — executable
- File existence checks — executable

No vague gates like "verify DRC passes" or "ensure quality." All are machine-verifiable.

### Self-Containedness — ✅ PASS

The plan provides:
- Full environment facts table (lines 28-42) with verified API status
- Complete GPIO pin assignments for both board variants (lines 95-131)
- Full net lists for both boards (lines 172-203)
- Complete component lists with positions (lines 217-247)
- LR2021 pinout reference (lines 259-281)
- Python API call reference (Appendix B, lines 1404-1459)
- DRC command reference (Appendix C, lines 1463-1483)
- ESP32-C3 GPIO reference (Appendix D, lines 1487-1512)
- Critical reminders (Appendix E, lines 1515-1531)
- File paths reference (Appendix A, lines 1364-1400)

A worker with zero conversation context can execute this plan from the document alone.

### New Issues Introduced by Revision — ⚠️ TWO MINOR OBSERVATIONS

**Observation 1 (MINOR): Net count discrepancy in V1-FAST header vs table**

Line 172 header says "V1-FAST Net List (15 nets, 15 components)" but the table lists 17 nets (numbered 1-17) and line 194 says "V1-FAST total: 17 nets, 16 components." The header count (15/15) is stale from an earlier draft. The table and summary line are correct (17/16). This is a cosmetic inconsistency — a worker will use the table, not the header count. **Non-blocking.**

**Observation 2 (MINOR): Phase 2 Task 2.1 GPIO verification is descriptive, not prescriptive**

Lines 469-483 (Task 2.1) instruct the worker to verify the ESP32-C3 module pinout but the "verification" is a series of bash comments (`# Check if using...`) rather than executable commands. There's no quality gate that verifies this step was actually performed. A worker could skip it. The task should have at minimum a gate like: `[ ] Gate: Module type recorded as comment in full_pipeline.py — grep 'Module type:' full_pipeline.py returns ≥1`. **Non-blocking but should be tightened.**

No other new issues were introduced. The revision is clean.

---

## MINOR ISSUES FROM ORIGINAL REVIEW (Status Check)

| # | Original Minor Issue | V2 Status |
|---|---------------------|-----------|
| 1 | Net list header said ~12 nets | ✅ Fixed — headers now say exact counts (15→17 in table, though header line 172 still shows stale "15") |
| 2 | Component count approximate | ✅ Fixed — exact counts used (16, 18) |
| 3 | Phase 8 test scripts missing trap | ✅ Fixed — `trap '...' EXIT` added to Task 8.1 template (line 1105) |
| 4 | Board files in /tmp | ✅ Fixed — moved to `tracker/hardware/output/` |

---

## PRAISE (Carried Forward + New)

1. **V1 Failure Documentation** — Still excellent. The "What Went Wrong" table (lines 63-69) maps each failure to root cause and fix.
2. **Self-Contained Design** — Improved with appendices A-F. A worker truly needs nothing else.
3. **A* Over LLM Coordinates** — Correct architectural choice preserved.
4. **DRC Hard Gate Language** — Preserved and strengthened with independent verification.
5. **NEW: Revision Summary (Appendix F)** — The V2 plan includes a complete change log mapping each blocker and major issue to its fix. This is excellent practice for traceability.
6. **NEW: Dual-Board Design** — The V1-FAST / V2-ADC split is well-reasoned. Ship-fast strategy with ADC variant as backup is the right call for a balloon project with a 2-week lead time.
7. **NEW: False-Pass Detection** — Phase 4B doesn't just check DRC 0/0; it verifies board content (footprints ≥14, nets ≥15, tracks ≥15, zones = 0). This catches the edge case where an empty board passes DRC because there's nothing to violate.

---

## FINAL ASSESSMENT

| Category | Count | Status |
|----------|-------|--------|
| Blockers (original) | 5 | 5/5 FIXED ✅ |
| Major issues (original) | 11 | 11/11 FIXED ✅ |
| Minor issues (original) | 4 | 4/4 FIXED ✅ |
| New issues introduced | 2 minor observations | Non-blocking |
| Worker assignments | 8 phases | All correct ✅ |
| Quality gate executability | 9 phases | All executable ✅ |
| Circuit breakers | 9 phases | All present ✅ |
| Git commit + push | 9 phases | All present ✅ |
| Self-containedness | Full document | Complete ✅ |

The two minor observations (stale header count on line 172, soft GPIO verification in Task 2.1) are cosmetic/soft issues that can be fixed in-flight during execution. They do not block scheduling.

---

## CONSULTANT VERDICT: APPROVED

All 5 blockers and 11 major issues from the original review are fixed. The V2 plan is self-contained, correctly assigns workers by domain expertise, uses executable quality gates with circuit breakers and git push in every phase, and introduces no new blocking issues. The plan is ready for kanban scheduling.

Two minor cosmetic observations are noted above for in-flight correction. Neither blocks execution.

---

*End of consultant re-review.*