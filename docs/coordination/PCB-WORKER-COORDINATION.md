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
Gate 3: PCB has > 10 footprints (NOT EMPTY)
Gate 4: DRC < 20 violations, 0 shorting_items
Gate 5: F_Cu.gtl > 1KB, B_Cu.gbl > 1KB
Gate 6: Board thickness = 0.6mm
```

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
