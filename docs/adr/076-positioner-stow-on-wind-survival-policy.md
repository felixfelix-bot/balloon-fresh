# ADR-076 — Positioner survival policy: stow on wind, anemometer cutoff, mechanical latch

- **Status:** **Proposed** — an agent-derived engineering policy (the operator's locked goal is a
  cheap, 3D-printed positioner, not a specific survival policy). It orders nothing.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator) — the cost/printability goal
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-071 (design basis — one positioner), ADR-077 (print the
  structure, buy the gearing), ADR-078 (right-sizing and the class cliff), ADR-082 (rate
  adaptation).
- **Evidence:** `docs/analysis/positioner-lowcost-3dprinted.md` +
  `docs/analysis/positioner_lowcost_model.py` + `docs/analysis/figures/positioner-rightsizing.png`
  (source branch `design/positioner-lowcost`, whose file `docs/adr/067-positioner-architecture.md`
  is **superseded by this record** / ADR-077 / ADR-078); the wind/moment model in
  `docs/analysis/gain-per-dollar-cliff.md` (source branch `design/gain-per-dollar-cliff`).
  Reproduce: `python3 docs/analysis/positioner_lowcost_model.py`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(see **ADR-071 §Numbering and collision note** for the full table) and are **not reused**.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. This record takes the fresh
number below (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

Swept area and wind torque scale **steeply** with aperture: **1.2 m → 0.6 m is 4.00× less area
and 4.00× less wind force at the same wind speed** (0.6 m → 83.1 N, 1.2 m → 332.5 N at 20 m/s,
solid); wind **moment** scales as **D³**. That is why a small dish/antenna is the cheap
positioner's precondition (ADR-078) — but it does **not** remove the storm case, and the storm
case is what sets the positioner's cost class.

Two findings from the committed analysis and an independent consultant round fix the policy:

1. **The survival case should be the STOW case, not the storm-torque case.** Stowing the aperture
   **aperture-up** presents **11.8 %** of the broadside wind area → **≈8.5× torque reduction**
   (geometry-specific, not a universal number). Sizing the structure for a 10–15 m/s operating
   wind and **parking for the storm** is what keeps the positioner cheap; sizing it to survive
   storm broadside loads would step it a class (or two) up.
2. **Stow cannot be held by motor torque or by worm self-locking.** The consultant's load-bearing
   finding — *"you cannot hold stow with motor torque"* — stands. Holding stow on worm
   self-locking is **not accepted as a safety property** (the vendor does not warrant the
   self-locking for holding loads; it is ratio- and friction-dependent).

## Decision

**D1 — Size the positioner for a 10–15 m/s OPERATING wind, and handle the storm by STOWING.** The
structure is rated for operating wind, not storm broadside load.

**D2 — Stow is triggered by an ANEMOMETER CUTOFF with a fail-safe stow direction.** Loss of
control (power, MCU, watchdog) drives the station to STOW, asserted at **MCU level**, not PC level.

**D3 — Stow is held by a POSITIVE MECHANICAL LATCH or brake, not by motor torque and not by worm
self-locking.** A spring-applied brake or a mechanical stow latch is **required** wherever loss of
hold is unacceptable.

**D4 — Two hard endstops per axis**, plus a fail-safe stow direction, are part of the mechanical
specification.

**D5 — Elevation-axis geometry through the dish's/antenna's centre of pressure (balanced-axis
placement) is the lever that reduces wind torque (~4×).** A **counterweight** is accepted for
**motor sizing and power-loss stability only**, and this record states plainly that a
counterweight **does not reduce wind torque**.

## Invariants

- **INV-1.** The survival case is the **stow** case: the structure is rated for operating wind and
  a positive mechanical hold covers the storm case.
- **INV-2.** The fail-safe direction is **STOW**, asserted by an MCU-level cutout.
- **INV-3.** **No** holding of stow on motor torque or worm self-locking alone; a latch/brake is
  required with them.
- **INV-4.** Any quoted wind-torque-reduction figure derived from stow geometry must carry its
  **silhouette assumption** (the 11.8 % figure is geometry-specific).

## Consequences

### Positive
- The positioner stays in the **cheap printed class**: one structural class down, driven by stow
  rather than by steel.
- A stated, testable failure mode (loss of power → stow) instead of an implicit one.

### Costs / risks
- **An unattended station must be able to stow on short notice**, which means the anemometer,
  the latch/brake and the MCU cutout are **not optional** items in the cost roll-up.
- A stow latch adds a mechanical part that must be bench-tested (release and hold both).
- The 10–15 m/s operating window is a **service limit**: above it the station parks.

## Open items (not assumed)

- **`TODO(unverified)`** a measured stow-latch hold torque and release reliability.
- **`TODO(unverified)`** the exact 11.8 % silhouette for the finally chosen antenna geometry.
- **`TODO(unverified)`** the anemometer part and its cutoff calibration.

## Relation to other ADRs

- **Supersedes** the off-branch `067-positioner-architecture`
  (`design/positioner-lowcost`) for the **survival policy**; its print/buy finding lands in
  ADR-077 and its right-sizing/class findings in ADR-078.
- **Consumes** the `design/gain-per-dollar-cliff` wind/moment model and its consultant finding on
  the latch (that branch's own file is superseded by ADR-078 / ADR-081).
- **ADR-077** owns the drive/gearing that this policy assumes is self-locking but never relied on
  for hold.

## For future sessions

- **One-line rule:** *stow, don't steel* — size for 10–15 m/s, park for the storm on an
  anemometer cutoff, and hold the parked state with a **mechanical latch/brake**, never with
  motor torque or worm self-locking.
- **Reproduce:** `python3 docs/analysis/positioner_lowcost_model.py`.
