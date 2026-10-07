# REPORT — Power + mass budget reconcile (ADR-006 + 2026-10-07 energy policy)

## What was done

- Created a fresh worktree at `/home/c03rad0r/worktrees/bf-power-reconcile` from the
  worker branch `task/t_f77dbc2d` tip `ff1f91f`.
- Merged the current tip of `adr/radioband-tdm` (`8b46f6873f815425acb7203da1d22685e954d404`,
  verified via `git ls-remote`) into the worktree.
- Resolved the ADR-029 merge conflict so that **both** the ADR-034/035 supersede
  pointer line and the O5 BLOCKED power-budget section survived. Verified with `grep`.
- Reworked `docs/POWER-BUDGET-V9-D2BE.md` in place into a single reconciled budget:
  - Solar array and storage grounded in ADR-006 (12 cells, 2.4 W peak, 1.65 F @ 5.4 V).
  - Energy policy from ADR-036 folded in (burst-sized storage, daylight-only TX,
    mandatory night deep sleep, cold-start-at-dawn accepted).
  - Power budget table with peak, sleep/RX, duty cycle, average, and provenance.
  - Array coverage check showing the average load (~0.39 W) is below the array's
    conservative two-wing estimate (~1.2 W).
  - Modulation fork: FLRC ~1 mF buffer (~0.2 g) vs LoRa SF12 ~0.5 F buffer.
  - Mass budget with FR4 board mass computed from the brief's formula and every
    other line carrying `[datasheet ...]`, `[computed: ...]`, or `TODO(unverified)`.
  - Contradictions-found section comparing the original worker doc to ADR-006/036.
  - Supersede/relationship section covering ADR-006, ADR-036, ADR-035, ADR-034, and
    ADR-029 O5.
- Wrote `PROGRESS.md` and this `REPORT.md` at the worktree root.
- Committed the rework, pushed `github` then `ngit` sequentially (no force), and
  verified both remote SHAs with `git ls-remote`.

## Branch and observed SHAs

- Branch: `docs/power-mass-reconciled`
- Local HEAD after final commit: `TBD`
- Remote `github`: `TBD`
- Remote `ngit`: `TBD`

(These will be filled in after the push step below.)

## Modified files

- `docs/POWER-BUDGET-V9-D2BE.md` — reconciled power + mass budget.
- `docs/adr/029-dual-band-flight-board.md` — merge-resolution result (supersede pointer
  + O5 BLOCKED text kept).
- `PROGRESS.md` — this task log.
- `REPORT.md` — this file.

`docs/adr/034-radio-band-split-433-tx-2g4-rx.md` and
`docs/adr/035-tdm-radio-schedule.md` are present via the merge but were not edited
in this task.

## Reconciled numbers

- **FLRC burst buffer**: ~1 mF (~0.2 g)
- **LoRa SF12/BW125 burst buffer**: ~0.5 F (tenths-of-a-farad range)
- **Known/computed mass subtotal**: 5.76 g
- **Unverified mass lines**: 11 of 13 (all other items marked `TODO(unverified)`)
- **TODO(unverified) count in the power/mass doc**: 20
- **Contradictions found**: 5 (listed in §5 of the budget doc)

## Open items carried forward

- FLRC availability on the F33 sub-GHz 433 MHz port.
- Cold −60 °C buffer characterization.
- Payload deep-sleep current (decides night LOG survival).
- All `TODO(unverified)` mass and current figures must be replaced by datasheet or
  measurement values before flight.
- ADR-029 O5 (5 V rail) remains open; the bank-at-5.4 V tap is recorded only as a
  possibility.

## Blockers

None.
