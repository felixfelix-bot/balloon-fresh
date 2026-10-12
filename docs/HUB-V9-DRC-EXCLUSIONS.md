# HUB v9 — By-Design DRC Exclusions (waiver ledger)

**Board:** hub_board_v9_routed_stitched.kicad_pcb
**Date:** 2026-10-12 · **Status:** Proposed · **Refs:** ADR-046, ADR-048, WING-TO-HUB-SOCKET-SPEC.md

Every DRC family below is **intentional geometry**, not a defect. This ledger is
the machine-readable record so every checker (KiCad DRC, agentee drc, JLCPCB
preflight, human review) can map violation → waiver → justification instead of
re-litigating design intent on every run.

## Waiver table

| # | DRC family | Count | Footprints | Mechanism | Justification |
|---|-----------|-------|------------|-----------|---------------|
| W1 | `unconnected_items` F-B pad pairs | 10 | J_W1–J_W4 (`Wing_Tab_4P`) | Edge-card socket: the inserted wing tab bridges the F.Cu and B.Cu halves of each land mechanically (ADR-046 §socket). Board copper MUST NOT bridge them — a copper bridge would short the tab insertion. | Spec-mandated. |
| W2 | `pad-off-board` / lands outside outline | 3+ | J_W1–J_W3 | Milled 0.9 mm slots at the board edge: lands flank the slot and half of each land lies outside the final routed outline — that half is the castellated tab contact area. | Spec-mandated (WING-TO-HUB-SOCKET-SPEC §5). |
| W3 | `copper_edge_clearance` on slot Edge.Cuts geometry | 38 | J_W1–J_W4 | Same slots as W2 — the Edge.Cuts rectangles/segments of the socket are, by definition, at the copper edge. | Spec-mandated. |
| W4 | `drill` on J_W* lands | 0 (fixed) | J_W1–J_W4 | Was 12 × 0.2 mm; fixed to SMD no-drill lands per spec §5. Fix landed in commit 5706536. | Resolved. |

## What is NOT waived

- Copper-to-board-edge on real tracks/vias (13 items, 0.38–1.65 mm): must be
  pulled inward to ≥ 0.5 mm.
- The 6 genuinely unrouted nets (DIO2, MISO, W1–W3_SOLAR_N, GND island):
  routing work, not waivers.
- Starved thermals (4) and clearance (2): manual fixes.
- U1-41@1..12 castellation pads: real thermal pads, distinct XY, all in GND —
  they are NOT pad-halves and their drills are now 0.3 mm (JLCPCB floor).

## Machine-readable form

KiCad-side: set `exclude_from_drc` on the J_W1–J_W4 footprint pads (KiCad
attribute, survives .kicad_pcb round-trip; agentee's TOML importer preserves
the description string so the waiver provenance survives import too).
agentee-side: blocked until upstream waiver support exists — tracked in
v0l/agentee TODO.md + draft PR #15.

## History

- 2026-10-12 run-5 stall root cause: FreeRouting + agentee both burned passes
  on the 16 unjoinable F-B pairs; fixed at DSN level by merging @N back-halves
  (commit 3df2582, tests test_route_dsn_padhalf_merge.py).