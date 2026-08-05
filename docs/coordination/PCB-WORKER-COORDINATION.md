# PCB Worker Coordination Protocol

## Problem

Multiple workers (kanban + delegate_task) modifying the same .kicad_pcb file
simultaneously causes silent overwrites, corrupted boards, and wasted work.

## Rule: SINGLE WORKER PER FILE

At any given time, exactly ONE worker owns a board file:

```
v_c3_flight_final.kicad_pcb → deleg_4978657e (delegate_task, K2.7)
```

No kanban task or other delegate may touch this file until the owner completes.

## Enforcement

### Manager (me) responsibilities:
1. Before dispatching ANY board task, check:
   - Is a delegate_task already modifying this file? (check background tasks)
   - Is a kanban task assigned to worker-layout? (hermes kanban list)
   - If YES to either: WAIT. Do not dispatch.

2. After a delegate_task completes:
   - Verify quality gate PASSED
   - If pass: dispatch next phase as NEW delegate_task
   - If fail: re-dispatch same phase with error context

3. After a kanban task completes:
   - Review output before allowing next task
   - Block stale tasks immediately when superseded

### Quality Gates (enforced between EVERY phase):

```
Gate 0 (PRE): Model available? curl test before dispatch
Gate 1: Schematic loads in kicad-cli (exit 0)
Gate 2: ERC < 10 violations
Gate 2.5 (PLACEMENT): All footprints inside board outline, 0 courtyard overlaps,
     0 shorting_items BEFORE any routing. Run kicad-cli pcb drc and verify
     shorting_items=0 before routing phase begins. If placement fails this gate,
     DO NOT ROUTE — fix placement first.
Gate 3: PCB has > 10 footprints (NOT EMPTY)
Gate 4: DRC < 20 violations, 0 shorting_items
Gate 5: F_Cu.gtl > 1KB, B_Cu.gbl > 1KB
Gate 6: Board thickness = 0.6mm
Gate 7: All footprints within board outline (max X < board_width, max Y < board_height)
```

### Gate 2.5 — Placement Overlap Check (CRITICAL)

This gate is enforced AFTER placement, BEFORE routing. The board must pass
this gate with ZERO routing (no tracks). If the placement itself creates
shorts, no amount of routing will fix it.

Check command:
```python
# After placement, before routing:
# 1. Verify no footprint extends beyond board outline
# 2. Run kicad-cli pcb drc — shorting_items must be 0
# 3. courtyards_overlap must be 0
```

LESSON LEARNED (2026-08-05):
- U1 (ESP32-C3, 28.6mm wide) and U2 (LR2021) physically overlapped
- ANT1 extended 4.5mm past board edge
- Multiple components outside 45x35mm outline
- Routing cannot fix placement problems — shorts come from overlapping pads

### Dispatch mechanism selection:
- **delegate_task (background)**: When I need the result to continue
  - Sequential phases where each depends on previous
  - I control the quality gate check between phases
  - Result returns to me for review

- **kanban**: For autonomous work I don't need to gate
  - Firmware builds, test runs, documentation
  - Worker picks up, completes, commits
  - I check later via git log

### NEVER mix both on the same file
- If I dispatch delegate_task for a board file → block all kanban tasks for worker-layout
- If I schedule a kanban task → don't dispatch delegate_task for same file

## File Ownership Registry

| File | Owner | Status |
|------|-------|--------|
| v_c3_flight_final.kicad_pcb | deleg_4978657e (K2.7 DRC fix) | RUNNING |
| v_c3_flight.kicad_sch | none (broken, bypassed) | ABANDONED |

## Cleanup (done 2026-08-05)
- Blocked: t_9d4a6f09 (was running, collided)
- Archived: t_b99e92a9, t_cd67fdda, t_57e93855, t_19e2c805 (stale)
