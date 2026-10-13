# ADR-051: Canonical Board-Production Order of Operations

**Date:** 2026-10-13
**Status:** Accepted
**Decision Maker:** Felix (operator), directive 2026-10-13 ("lock these decisions in as ADRs")
**Related:** ADR-015 (Three-Board Hardware Strategy), ADR-046 (hub socket), ADR-049 (wing-fixed connector), ADR-107 (three-variant PCB design)

## Context

The hub-v9 effort measured the cost of order violations directly:

- Two nets (`/SX1280_DIO2`, `/SX1280_MISO`) were unroutable **after** layout freeze.
  FreeRouting (53 s, "cannot make further progress") and agentee ("no path
  within the rules") refused independently — a **capacity wall**, not tuning.
- A 0.1 mm-resolution escape scan then proved U4.9/U4.11 have **zero** legal
  F.Cu escapes within 3 mm (fanout-blocked), while U1 pads have 141–328 clear
  spots: the failure was a **placement property**, detectable before routing.
- Recovering required a stackup change (D1-corrected, ADR-052) + via-in-pad
  routing — a re-layout class of work that a placement-time gate would have
  caught at a fraction of the cost.

Two required boards (base-station, bench-rig) do not yet exist; they inherit
this order from day one.

## Decision

The board-production pipeline is a **strict sequential gate chain**. No stage
begins until the previous stage's gate passes. The gates are BLOCKING.

1. **Logical definition** — netlist in code (SKiDL or equivalent Python);
   zero coordinates. Output: components + connections as data.
2. **Form factor** — board outline, mounting/castellated pad positions, RF
   keep-outs, connector positions (locked RF geometry per ADR-046/049).
   Output: hard boundary constraints.
3. **Deterministic placement** — fixed connectors + power parts FIRST, then
   decoupling caps adjacent to their ICs, then the remainder. Placement is
   computed, not guessed; overlaps are rejected programmatically.
4. **Placement gate (BLOCKING)** — render 3D + layer views; **Felix review
   in Signal** + **Astra spatial review** must BOTH pass before routing.
   U4-wall-class failures (no escape, blocked fanout) are caught HERE, where
   moving a part is cheap.
5. **Routing** — deterministic engines (FreeRouting / agentee / verified
   scripts). Component coordinates are now immovable anchors.
6. **DRC gate (BLOCKING)** — kicad-cli DRC is the authoritative checker;
   unconnected must equal the pre-route baseline; no new violation families.
   Then Astra re-review (kanban Done gate), STEP + drill regen, Gerbers, fab
   preflight.

Rule of change flow: **schematic → layout, never layout-only edits** (a
layout edit without a netlist update reads as a short at the next check).

## Consequences

- Base-station and bench-rig boards start with this order enforced in their
  kanban cards (gate fields per stage).
- Placement-review renders are produced at stage 4 for EVERY board.
- Retrofit cost for the hub board is accepted (already paid); the ADR
  prevents recurrence, not retroactivity.

## Verification hooks

- `scripts/gen_adr_index.py` picks the number (068); index regenerated.
- Gate evidence per board: stage-4 render path + Astra verdict file +
  DRC json committed alongside the board file.
