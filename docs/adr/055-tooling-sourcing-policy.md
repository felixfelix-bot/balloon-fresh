# ADR-055: Tooling Sourcing Policy for Board Production

**Date:** 2026-10-13
**Status:** Accepted
**Decision Maker:** Felix (operator), directive 2026-10-13 (adopt/skip list from external AI-tooling survey, vetted)
**Related:** ADR-051, ADR-053, ADR-054

## Context

A 2026-10-13 external survey of "AI PCB + 3D tooling" (Flux AI, Quilter AI,
ProtoFlow, Cadence Allegro X AI, Altium AI, Zoo dev, Meshy AI, Tripo AI,
Kaedim, SKiDL, CadQuery/build123d, OpenSCAD, Trimesh) was vetted against the
project's constraints: RF geometry locked (ADR-046/049), boards must be
JLCPCB-orderable, fleet runs offline-capable deterministic tooling, and the
value loop this session was LLM-intent + deterministic-geometry, not
cloud-autorouting.

## Decision

**Adopted** (all local/deterministic, already in or joining the stack):
- KiCad `kicad-cli` (DRC, SVG/STEP export) — authoritative checks and renders
- FreeRouting + agentee — routing engines (agentee as gate, not SoT)
- SKiDL — netlist authoring for new boards (ADR-054)
- CadQuery/build123d + OpenSCAD — parametric enclosures (existing skills:
  `openscad-3d-enclosure`, `embedded-enclosure-design`)
- Trimesh — deterministic mesh checks if enclosure mesh QA is needed

**Rejected**:
- **Flux AI, Quilter AI, ProtoFlow** — cloud EDA, vendor lock-in, and
  auto-placement/routing that ignores our LOCKED RF geometry; the U4-wall
  incident shows autorouters don't solve placement-quality problems, they
  refuse them. No value at our stackup/size class.
- **Meshy AI, Tripo, Kaedim** — generative MESH output is not fab-grade
  (survey itself concedes "structural modifications required for physical
  fabrication"). We need STEP/parametric, not textured meshes.
- **Cadence Allegro X AI / Altium AI** — enterprise accelerators for
  high-speed BGA/microvia density classes we don't have; cost and lock-in
  for zero fit.

## Consequences

- No cloud-AI dependency enters the board pipeline; every stage runs
  locally and reproducibly (fleet IaC doctrine).
- Re-evaluation trigger: if a future board needs 6+ layer HDI or BGA fanout
  density beyond KiCad+FreeRouting capability, revisit enterprise tooling in
  a new ADR (do not silently adopt).
