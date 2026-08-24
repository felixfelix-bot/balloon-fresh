# PCB Auto-Route Execution Plan — Consultant Review

**Date:** 2026-08-05
**Reviewer:** Consultant Profile (critical review)
**Document reviewed:** `PCB-AUTO-ROUTE-EXECUTION-PLAN.md` (1,358 lines)
**Cross-referenced:** `LLM-AUTO-ROUTING-PIPELINE.md`, `AUTO-ROUTING-FEASIBILITY.md`

---

## Summary

The plan is well-structured and self-contained. It clearly documents the V1 failure modes, the environment constraints, and the architecture decision. However, it has several serious problems that will cause worker confusion, quality gate bypasses, and at least one architectural contradiction that makes the core pipeline non-functional as written. These must be fixed before scheduling on kanban.

---

## Findings

### 1. [BLOCKER] Pipeline Code Uses LoadBoard() Which Fails Headless — Plan Contradicts Itself

**Severity: BLOCKER**

The execution plan states in its "Verified Environment Facts" table (line 21) that `pcbnew.LoadBoard()` **❌ NEEDS wxApp** and **fails headless**. The plan's Appendix E (line 1347) also says: "USE `NewBoard()` — NEVER `LoadBoard()` (fails headless without wxApp)."

However, the actual pipeline code in `LLM-AUTO-ROUTING-PIPELINE.md` (lines 826, 872) — which Phase 1 Task 1.1 instructs workers to copy verbatim — uses `pcbnew.LoadBoard()` in two places:

```python
# Line 826:
board = pcbnew.LoadBoard(args.board)

# Line 872:
board = pcbnew.LoadBoard(args.board)
```

The plan acknowledges this at line 500 ("NOTE: The pipeline code uses `pcbnew.LoadBoard()` which fails headless") and says Phase 1 and Phase 3 "may need to be combined." But this is phrased as a suggestion, not a hard requirement. A worker following Task 1.1 literally will copy broken code.

**Required fix:** Task 1.1 must NOT instruct workers to copy the pipeline code as-is. The plan must either:
1. Provide corrected code that uses `NewBoard()` throughout, OR
2. Explicitly state that the copied code WILL NOT RUN and must be modified before execution, with the specific modifications listed as mandatory sub-tasks.

The current "may need to be combined" language is insufficient. This is a guaranteed failure.

---

### 2. [BLOCKER] No Independent DRC Review — worker-balloon Does Both Routing AND DRC Verification

**Severity: BLOCKER**

The quality gate requirements (from kanban-worker-management skill) state: "Review pipeline: implementer writes code, DIFFERENT worker reviews." The DRC verification is the most critical quality gate in the entire plan — it's what prevents another V1 disaster (437 violations shipped to JLCPCB).

The plan assigns Phase 4 (DRC Iteration Loop) to **worker-balloon** — the same worker who wrote the pipeline code, created the board, and ran the auto-router. There is no independent verification. worker-balloon has every incentive to declare "DRC passes" and move to gerber export.

**Required fix:** Phase 4's final DRC verification (Task 4.4) must be executed or reviewed by **worker-inspector** — a different worker with a different model. The DRC 0/0 result must be confirmed by worker-inspector before Phase 5 (gerber export) can proceed. This is a hard separation-of-concerns requirement.

Additionally, the DRC verification should not just check the count — it should verify the board file actually contains the expected number of nets, tracks, and footprints (detecting empty-board false-passes).

---

### 3. [BLOCKER] Quality Gates Are in Tables, Not Task Bodies — Race Condition Risk

**Severity: BLOCKER**

The kanban-worker-management skill requires: "Quality gates go in TASK BODY, not comments (race condition prevention)." Every phase's quality gate is currently presented as a markdown table at the end of the phase section. When this gets transcribed to kanban cards, the quality gate checks will likely end up in card comments or descriptions rather than in the executable task body.

The plan must explicitly instruct: "When creating kanban cards from this plan, quality gate checks must be embedded in the task body as executable commands, not added as comments."

**Required fix:** Add a section at the top of the plan stating that all quality gate tables are mandatory task body content, not metadata. Each quality gate should have a concrete shell command that returns exit 0/1.

---

### 4. [BLOCKER] No Circuit Breaker in Any Iterative Task

**Severity: BLOCKER**

The quality gate requirements state: "Circuit breaker: 3 consecutive failures on same error = BLOCKED." Phase 4 (DRC Iteration Loop) is the most critical iterative task — it runs up to 10 iterations. There is no circuit breaker specified. If the A* router produces the same short circuit 3 iterations in a row, the plan says to keep iterating (wasting time) rather than blocking and escalating.

Similarly, Phase 1 Task 1.4 (smoke test) has no circuit breaker. If the pipeline crashes 3 times with the same error, the worker should block, not keep retrying.

**Required fix:** Add circuit breaker language to every iterative task:
- Phase 1 Task 1.4: "If pipeline crashes 3 times with same error → BLOCKED, escalate to orchestrator"
- Phase 3 Task 3.1: "If A* fails to route same net 3 times → BLOCKED"
- Phase 4 Task 4.2: "If same DRC violation persists 3 consecutive iterations → BLOCKED, escalate"

---

### 5. [BLOCKER] No Git Commit + Push in Any Task Body

**Severity: BLOCKER**

The quality gate requirements state: "Git commit + push required in EVERY task body." The plan's Appendix E (line 1354) says "COMMIT AND PUSH — Uncommitted work is invisible to the orchestrator. Commit after each phase." But this is a reminder in an appendix, not an explicit step in any task body.

None of the 8 phases have an explicit git commit + push step in their task sequence. A worker could complete Phase 1, skip the commit, and start Phase 2 — losing all work if the session crashes.

**Required fix:** Every phase must end with an explicit task: "Git commit all changes with message 'Phase N: <description>' and push to remote." This must be in the task body, not an appendix reminder.

---

### 6. [MAJOR] "No Copper Pours" Not Enforced in Every Task Body

**Severity: MAJOR**

The plan mentions "no copper pours" in the environment facts, the V1 failure table, the layer strategy, and Appendix E. But it's not in every task body. Specifically:
- Phase 3 Task 3.3 verification checks for zones (`content.count('(zone')`) — good.
- Phase 4 Quality Gate checks "0 zones in board file" — good.
- But Phase 1 Task 1.2 (create board script) does NOT explicitly say "do not add zones."
- Phase 2 Task 2.1 (board outline) does NOT mention it.

A worker creating `create_board_v2.py` in Phase 1 might add a `pcbnew.ZONE()` call thinking it's a ground plane, not realizing it's forbidden.

**Required fix:** Add "DO NOT create any `pcbnew.ZONE()` calls — no copper pours" to every task that involves board creation or modification.

---

### 7. [MAJOR] python3.14 Not Explicit in Every Task Command

**Severity: MAJOR**

The plan correctly states to use `/usr/bin/python3.14` in most places, but several tasks use bare `python3`:
- Phase 7 Task 7.2: `idf.py set-target esp32s3` — this uses the IDF venv python3.11, which is correct for IDF but could confuse workers
- Phase 7 Task 7.4: `python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py` — uses bare `python3`
- Phase 8 Task 8.1: `python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py` — uses bare `python3`

The board lock and IDF tools may work fine with python3.11, but the plan doesn't distinguish which tasks need python3.14 (pcbnew) vs which can use python3 (general scripts). A worker might try `python3.14` for the IDF build and fail, or try `python3` for pcbnew and segfault.

**Required fix:** Add a note: "Use `/usr/bin/python3.14` ONLY for scripts that import `pcbnew`. Use `python3` (ESP-IDF venv) for IDF and board-lock scripts."

---

### 8. [MAJOR] GPIO18/GPIO19 Fallback Plan Is Not Concrete — FEM_TX Fallback to GPIO8 Conflicts with ADC

**Severity: MAJOR**

The GPIO fallback table (line 94-98) shows:
- FEM_TX fallback 1: GPIO8 (drop ADC)
- FEM_TX fallback 2: GPIO3 (share with RST via mux)

GPIO8 is already assigned to ADC (voltage divider). Using it for FEM_TX means dropping ADC — but ADC is listed as "Required" in the pin table. The plan doesn't resolve this conflict. It also doesn't explain what "share with RST via mux" means — there's no mux component in the BOM.

Furthermore, the plan says (line 99): "Worker action: Before finalizing the netlist, verify the ESP32-C3 module pinout." But this verification step is not assigned to any phase or any worker. It's a floating action item.

**Required fix:**
1. Resolve the GPIO8 conflict explicitly — if FEM_TX falls back to GPIO8, state that ADC is dropped and update the net list.
2. Remove or explain the "mux" fallback — if there's no mux in the BOM, it's not a real option.
3. Assign the GPIO verification to a specific task in Phase 1 or Phase 2.

---

### 9. [MAJOR] Boot Strap Pin Documentation Incomplete — GPIO2 Pull-Down Not in BOM

**Severity: MAJOR**

Appendix D (line 1338) correctly identifies that GPIO2 must be LOW at boot and recommends "Add a 10kΩ pull-down on GPIO2 if needed." However:
1. This pull-down resistor is NOT in the component list (line 133-149) — only 15 components are listed, no pull-down.
2. The net list doesn't include a net for the pull-down.
3. No task in any phase adds this resistor.

If the LR2021 MISO line has a pull-up (which many SPI devices do), the ESP32-C3 won't boot. This is a known hardware design issue that the plan identifies but doesn't fix.

**Required fix:** Either:
1. Add R_PD (10kΩ pull-down) to the BOM and net list, OR
2. Add a task in Phase 2 to verify the LR2021 MISO idle state and add the pull-down if needed.

---

### 10. [MAJOR] Rollback Plans Rely on KiCad GUI — System Has No GUI Access

**Severity: MAJOR**

Multiple rollback plans reference "KiCad GUI":
- Phase 1 rollback (line 369): "fall back to manual KiCad GUI routing"
- Phase 2 rollback (line 479): "fall back to KiCad GUI"
- Phase 3 rollback (line 575): "use KiCad GUI"
- Phase 4 rollback (line 675): "Manually route stubborn nets in KiCad GUI"
- Nuclear rollback (line 1184): "Use KiCad GUI to manually design the board"

The feasibility document explicitly states: "Felix doesn't need to touch KiCad GUI." The system is headless. While the plan mentions "use VNC or local screen" (line 415), there's no evidence that VNC is set up or that a display is available.

If the programmatic pipeline fails, the rollback is "use a tool that doesn't work in this environment." This is not a real rollback plan.

**Required fix:**
1. Verify whether VNC/display is actually available. If not, remove all GUI rollback references.
2. Replace GUI rollbacks with actionable alternatives:
   - "Edit the .kicad_pcb S-expression text directly" (the file is text-based)
   - "Adjust A* grid parameters and re-run"
   - "Simplify the design: drop nets to reduce complexity"
   - "Escalate to Felix for manual board creation on a machine with a display"

---

### 11. [MAJOR] worker-fips Assigned SPI Timing — But worker-fips Is FIPS/Mesh Specialist, Not Firmware

**Severity: MAJOR**

Phase 7 (SPI Timing Characterization) is assigned to worker-fips. The worker profiles say worker-fips is a "FIPS/mesh specialist, glm-5.2 model." SPI timing characterization requires:
- Wiring LR2021 to an S3 test board (hardware work)
- Flashing tracker firmware (firmware work)
- Testing at different SPI frequencies (firmware + hardware work)
- Adjusting SPI clock in firmware (firmware development)

This is firmware work, not FIPS/mesh work. The plan even says Phase 7 depends on Phase 5 completion (needs boards), but the timeline (line 1128) says it happens "Day 1-2" of the JLCPCB wait — before boards arrive. It uses the S3 test board as a proxy, but the S3 is not a C3.

**Required fix:** Reassign Phase 7 to **worker-balloon** (PCB/firmware specialist) or explicitly justify why worker-fips is appropriate. The SPI timing test is firmware validation, not FIPS work.

---

### 12. [MAJOR] Phase 6 (CI Updates) Assigned to worker-fips — Should Be worker-admin

**Severity: MAJOR**

Phase 6 (CI Updates) is assigned to worker-fips. The worker profiles say worker-fips is a "FIPS/mesh specialist." CI workflow updates are not FIPS work — they're DevOps/infrastructure work. worker-admin is described as "docs/scripts, glm-5.2 model" and is the correct assignment for CI workflow changes.

The plan's worker assignment table (line 168) also assigns Phase 6 to worker-fips. This is wrong.

**Required fix:** Reassign Phase 6 to **worker-admin**.

---

### 13. [MAJOR] DRC Loop Max 10 Iterations but No Success Criteria for Partial Convergence

**Severity: MAJOR**

Phase 4 allows 10 iterations. If after 10 iterations there are 0 violations but 1 unconnected net, the plan says to escalate. But what if after 5 iterations there are 2 violations (both clearance, no shorts)? The plan doesn't say whether to continue or escalate early.

The DRC loop specification (line 972-1029) only has two exit conditions: 0/0 (success) or max iterations reached (failure). There's no intermediate escalation.

**Required fix:** Add intermediate escalation criteria:
- If after 3 iterations the violation count is not decreasing → escalate (circuit breaker)
- If after 5 iterations there are still shorts → escalate (shorts are harder to fix than clearance)
- If only unconnected items remain (0 violations) → try manual routing of those specific nets

---

### 14. [MAJOR] Phase 5 (Gerber Export) Includes Manual JLCPCB Web Upload — Not Worker-Automatable

**Severity: MAJOR**

Task 5.5 (line 755) instructs:
1. Go to jlcpcb.com
2. Upload `gerbers_v2_jlcpcb.zip`
3. Verify preview matches 50×40mm board
4. Select options from the table above
5. Add to cart, checkout

This requires a human to interact with a web browser. No worker agent can do this. The plan says "Orchestrator approval required before placing order" but the upload itself is a manual step.

**Required fix:** Clarify that Task 5.5 is a **Felix action item** (human required), not a worker task. The worker's Phase 5 deliverable is the zip file + the order checklist. Felix does the actual JLCPCB upload.

---

### 15. [MAJOR] Missing Dependency: Phase 7 Depends on Phase 5, But Timeline Shows Phase 7 on Day 1-2

**Severity: MAJOR**

The dependency graph (line 184) says: "Phase 7 (SPI Timing) ── depends on Phase 5 completion (needs boards)."

But the timeline (line 1128) says: "Day 1-2: SPI timing characterization on S3 test board | worker-fips | 4h"

Phase 5 (gerber export + JLCPCB order) happens before the 2-week wait. The timeline starts Day 1 of the wait. But Phase 7 says it depends on Phase 5 — which includes receiving boards. Boards arrive on Day 14. So SPI timing on the actual boards can't happen until Day 14+.

The plan resolves this by using the S3 test board as a proxy (line 822-824), but the dependency graph still says "depends on Phase 5 completion (needs boards)." This is contradictory — it doesn't need the V2 boards, it needs the S3 test board which already exists.

**Required fix:** Update the dependency: "Phase 7 depends on Phase 5 gerber export (not board arrival). SPI timing uses S3 test board as proxy. Actual V2 board testing happens post-arrival."

---

### 16. [MINOR] Net List Says ~12 Nets in Header But Table Lists 17

**Severity: MINOR**

Line 105 says "Net List Definition (Single-MCU, ~12 nets)" but the table lists 17 nets (numbered 1-17). Line 129 says "Total: ~17 nets." Line 151 says "Total: ~15 components, ~17 nets." The header is wrong.

**Required fix:** Change header to "~17 nets."

---

### 17. [MINOR] Component Count Says ~15 But Table Lists 15 Components — Consistent But Fragile

**Severity: MINOR**

The component table (line 133-149) lists exactly 15 components. The text says "~15 components." This is fine, but if the pull-down resistor (Finding 9) is added, the count changes. All references should use exact counts, not ~15.

**Required fix:** Use exact counts ("15 components" not "~15") and update if the BOM changes.

---

### 18. [MINOR] RF Trace Impedance Not Addressed — 50Ω on 2-Layer 1.6mm Is Not 0.25mm Width

**Severity: MINOR**

The net list shows RF traces (RF_SUB_868, RF_2G4_2400) with 0.25mm track width and a note "50Ω approx." On a standard 2-layer 1.6mm FR4 board, 50Ω microstrip requires approximately 0.76mm trace width (depending on dielectric). A 0.25mm trace is closer to 75-80Ω, not 50Ω.

For a prototype balloon board, this impedance mismatch is likely acceptable (the LR2021 module has its own matching network), but the plan should acknowledge this rather than labeling it "50Ω approx."

**Required fix:** Add a note: "0.25mm RF traces are NOT 50Ω on 1.6mm FR4. This is acceptable for prototype — LR2021 module has onboard matching. For production, use JLCPCB impedance-controlled stackup or adjust trace width."

---

### 19. [MINOR] Phase 8 Test Scripts Don't Include trap for Lock Release on Error

**Severity: MINOR**

The quality gate for Phase 8 (line 965) says "All scripts release locks on exit (trap)." But the example script (Task 8.1, line 919-945) does NOT include a `trap` command. It manually releases locks at the end. If the script fails midway (e.g., flash fails), the locks are never released.

**Required fix:** Add `trap` to the example script:
```bash
trap 'python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release board-a; \
      python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release board-b' EXIT
```

---

### 20. [MINOR] Board Files Use /tmp — Lost on Reboot

**Severity: MINOR**

All intermediate board files are written to `/tmp/`:
- `/tmp/balloon_v2_single_mcu.kicad_pcb`
- `/tmp/balloon_v2_routed.kicad_pcb`
- `/tmp/drc_v2.json`

If the system reboots (or a worker session restarts), all work in /tmp is lost. The plan has no checkpoint mechanism. A worker could complete Phases 1-4, lose the files on reboot, and have no way to recover.

**Required fix:** Write board files to the repo directory (e.g., `tracker/hardware/output/`) instead of `/tmp/`. At minimum, copy final outputs to the repo and git-commit them.

---

### 21. [PRAISE] V1 Failure Documentation Is Excellent

**Severity: PRAISE**

The "What Went Wrong on V1" table (line 37-43) is exactly right. It clearly maps each V1 failure to its root cause and the plan's fix. The "NO COPPER POURS" rule is prominent and repeated. The architecture decision (single-MCU, no RP2040) is clearly stated as final. This is the strongest part of the plan.

---

### 22. [PRAISE] Self-Contained Document Design

**Severity: PRAISE**

The plan's "READ THIS FIRST" section (line 10-12) correctly identifies that kanban workers won't have conversation context. The document provides all environment facts, API references, and appendices. This is the right approach for kanban scheduling.

---

### 23. [PRAISE] A* Over LLM Coordinates

**Severity: PRAISE**

The decision to use A* pathfinding instead of LLM-generated coordinates (documented in the pipeline doc, Q3) is the correct architectural choice. The feasibility analysis is sound — 15 nets on a 50×40mm grid is trivial for A*.

---

### 24. [PRAISE] DRC Hard Gate Language Is Correct

**Severity: PRAISE**

Phase 4 Quality Gate (line 659-668) correctly labels DRC 0/0 as "HARD GATE — no exceptions" and "No copper pours" as HARD GATE. The "CRITICAL" warning (line 677) about not ordering boards with DRC failures is appropriately emphatic.

---

## Overarching Goal Alignment

The project's goal is "pico balloon, tollgate & FIPS version of starlink." This plan advances that goal by:
- Getting JLCPCB-orderable gerbers for the balloon tracker board (critical path)
- Using the 2-week JLCPCB wait productively (SPI timing, CI, test scripts)
- Keeping firmware unchanged (single-MCU architecture is already tested)

**Lowest hanging fruit:** Phase 8 (integration test scripts) and Phase 6 (CI updates) can start immediately, don't depend on PCB work, and deliver value during the JLCPCB wait. These should be scheduled first.

**Immediately actionable:** Phase 1 (pipeline code) can start right now — all tools are verified. The LoadBoard→NewBoard fix (Finding 1) is the only blocker.

**During 2-week wait:** SPI timing characterization is the highest-value activity — it de-risks the hardware design before boards arrive. But it should be assigned to worker-balloon, not worker-fips (Finding 11).

---

## Required Changes Before Scheduling

The following must be fixed before this plan goes on kanban:

1. **[BLOCKER]** Fix the LoadBoard→NewBoard contradiction in the pipeline code (Finding 1)
2. **[BLOCKER]** Assign DRC final verification to worker-inspector, not worker-balloon (Finding 2)
3. **[BLOCKER]** Add explicit instruction that quality gates go in task bodies, not comments (Finding 3)
4. **[BLOCKER]** Add circuit breaker (3 consecutive failures = BLOCKED) to all iterative tasks (Finding 4)
5. **[BLOCKER]** Add explicit git commit + push step to every phase's task body (Finding 5)
6. **[MAJOR]** Reassign Phase 6 (CI) from worker-fips to worker-admin (Finding 12)
7. **[MAJOR]** Reassign Phase 7 (SPI timing) from worker-fips to worker-balloon (Finding 11)
8. **[MAJOR]** Resolve GPIO8 conflict in FEM_TX fallback (Finding 8)
9. **[MAJOR]** Add GPIO2 pull-down to BOM or create verification task (Finding 9)
10. **[MAJOR]** Replace GUI-based rollback plans with headless alternatives (Finding 10)
11. **[MAJOR]** Clarify that JLCPCB upload is a Felix action, not a worker task (Finding 14)

---

## CONSULTANT VERDICT: NEEDS REVISION

The plan is structurally sound and well-documented, but has 5 blockers that will cause worker failures if scheduled as-is. The LoadBoard contradiction (Finding 1) alone will stop Phase 1 dead. The missing circuit breakers and git requirements violate kanban-worker-management skill mandates. The worker assignments for Phases 6 and 7 are wrong.

Fix the 5 blockers and 6 major items listed above, then this plan is ready for kanban scheduling. The remaining minor items can be fixed during execution.

---

*End of consultant review.*