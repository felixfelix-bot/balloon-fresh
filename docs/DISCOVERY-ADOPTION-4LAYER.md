# Discovery Adoption: 4-Layer PCB Stackup (2026-08-07)

Adopted independently from cross-track findings (balloon-hermes commits).

## Source Commits
- ab7e0f7: clean placement 80x60mm + 4-layer routing — 0 overlaps, 10 DRC
- 241367b: v3 router — per-segment via hopping + relaxed fallback
- 2812b63: 4-layer conversion with GND/3V3 power planes + collision-aware routing
- fb02a9b: 4-layer board with In1.Cu GND plane, In2.Cu 3V3 plane

## Adopted Practices
1. **4-layer stackup**: In1.Cu=GND, In2.Cu=3V3, signals on F.Cu/B.Cu
2. **Gate 2.5 placement check**: 0 overlaps before routing — mandatory
3. **v3 router**: per-segment via hopping, 8 layer combos per offset
4. **Board size 80x60mm**: enough room for clean bin-packing
5. **Thermal vias**: at SMD power pads for zone connectivity

## Impact on V0.1 Plan
- Hub Board V0.1: switch from 2-layer to 4-layer
- Board size: 80x60mm target (up from 50x45mm)
- Use route_4layer_v3.py as starting point
- Placement gate mandatory

## Open Question (Escalated to Orchestrator)
C3 flight PCB in balloon-fresh/tracker/hardware/output/ — shared artifact or balloon-hermes's own? Need to confirm no duplicate work.
