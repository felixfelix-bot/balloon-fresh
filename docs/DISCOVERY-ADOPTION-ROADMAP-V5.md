# Discovery Adoption: ROADMAP v5 + Phase Progress (2026-08-07)

Adopted independently from balloon-hermes commits (4754c73, 4c1befe, 440a975, 1e47714, 7e0e18b, 6e5d29f, f459f5d, 1e497fd, ffb67e2).

## ROADMAP v5 Two-Stage Architecture (adopted)
- Stage A: Placement (A1-A4) with BLOCKING quality gates
- Stage B: Routing (B1-B5) — CANNOT START until Stage A passes
- Per-phase versioning: snapshot .kicad_pcb per task, git commit per gate

## Critical Technical Lessons (adopted)
1. **Through-vias short through inner-plane zones** — on 4-layer with GND on In1.Cu, 3V3 on In2.Cu, any through-via passes through both planes and shorts to them. Signals MUST route without through-vias. Use layer alternation per net (entire net on F.Cu OR B.Cu).
2. **Zone creation via .kicad_pcb text edit** — python3.14 pcbnew API segfaults on ZONE operations. Edit .kicad_pcb file directly.
3. **SaveBoard(path, board) NOT board.Save(path)** — b.Save drops tracks.
4. **python3.14 mandatory** — python3 segfaults with pcbnew.
5. **300s timeout too short** — KiCad scripting routinely exceeds 300s. Use 1800s.
6. **Zone keepout flags** — KiCad API SetDoNotAllow* not persisted by SaveBoard. Requires .kicad_pcb text edit.
7. **Manhattan router needs per-segment collision detection** — check each L-route segment independently against ALL existing copper.

## RF Routing (adopted from Phase 1A)
- RF_OUT as 50Ω microstrip on F.Cu (0.2mm over GND plane)
- GND stitching vias flanking antenna feed + RF pad
- Solid GND on In1.Cu beneath entire RF path (no cuts, no slots)
- 2.4GHz: consider coplanar waveguide geometry

## Current Progress (balloon-hermes track)
- Phase 0: PASS (placement verified, caps near ICs)
- Phase 1A: PASS (RF 50Ω + power + thermal vias + GND stitching)
- Next: Phase 1B (signal autorouting)

## Impact on V0.1 Plan
- V0.1 Hub Board plan is OBSOLETE — balloon-hermes has a more mature PCB pipeline
- ROADMAP v5 is the authoritative design document
- My FLIGHT-BOARD-PLAN.md should be updated to reference ROADMAP v5

## Open Question (Escalated to Orchestrator)
The C3 flight PCB being developed in balloon-hermes appears to be the same design
as my V0.1 Hub Board (ESP32-C3 + LoRa + GPS, 4-layer, 50x40mm). Need confirmation:
- Is balloon-hermes doing the PCB design that my track was planning?
- If so, what is my track's remaining scope? Schematic capture? BOM? Solar carrier?
