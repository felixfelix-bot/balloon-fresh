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
| W1 | `unconnected_items` F-B pad pairs | 12 | J_W1–J_W4 (`Wing_Tab_4P`) | Edge-card socket: the inserted wing tab bridges the F.Cu and B.Cu halves of each land mechanically (ADR-046 §socket). Board copper MUST NOT bridge them — a copper bridge would short the tab insertion. | Spec-mandated. **Verified 2026-10-12:** each J_W* pad is TWO stacked 4.0 x 1.2 mm SMD pads at identical XY (F.Cu+In1.Cu, and In2.Cu+B.Cu), no drill. `WING-TO-HUB-SOCKET-SPEC §2` line 62-64: "Both options reproduce the same 4 lands on BOTH faces of the hub edge (top and bottom), so the wing tab can be soldered from both sides." The **solder fillet** is the connection, not copper. Adding a via here would be a defect. |
| W2 | `pad-off-board` / lands outside outline | 3+ | J_W1–J_W3 | Milled 0.9 mm slots at the board edge: lands flank the slot and half of each land lies outside the final routed outline — that half is the castellated tab contact area. | Spec-mandated (WING-TO-HUB-SOCKET-SPEC §5). |
| W3 | `copper_edge_clearance` on slot Edge.Cuts geometry **and the socket pads** | 32 | J_W1–J_W4 | Same slots as W2. The Edge.Cuts rectangles/segments of the socket are, by definition, at the copper edge — **and so are the connector's own lands**: `Pad 2 [GND]` and `Pad 3 [/CUT_SENSE_W*]` of each J_W* sit inside the milled slot. They are the edge-card interface; they cannot be moved inward without moving the socket (ADR-046). Their unavoidable stub tracks and the F→B via are part of the same family. | Spec-mandated. |
| W4 | `drill` on J_W* lands | 0 (fixed) | J_W1–J_W4 | Was 12 × 0.2 mm; fixed to SMD no-drill lands per spec §5. Fix landed in commit 5706536. | Resolved. |

| W6 | `silk-text` on J_W1–J_W4 labels | 10 | J_W2, J_W4 | The socket part-number labels (`1`,`4`,`W`,`90`) sit on the socket body at the board edge — same W3 family. Labels are correct and readable; they persist into the fab drawing but the silk over the edge is clipped by the fab. Cosmetic. |
| W7 | `silk-text` over-via / crowd (accepted) | 12 | U4, U6, D_BP1-3, D_CLAMP, R_NTC1, R_DIV1, R_F1 | **Proven unfixable at the current layout (2026-10-12):** these parts sit on via fields, so silk ink lands on via holes. Three independent attempts to move the labels all failed — (1) shrink to 0.80 mm cleared 10 of 28 but left 8 needing the *parts* moved; (2) `agentee silk --dry-run` (its own auto-fixer, which iterates to a fixed point) offers a clear spot for **0 of 20** labels; (3) our own spiral search moved 13 labels and made it WORSE (22 -> 29) by trading via-collisions for text/outline collisions. The board is silk-congested: **no free spot exists at the current text size.** The real fix is a layout revision (larger board or a smaller default refdes size), not a script. Accepted as a cosmetic fab flag; refdes stay VISIBLE (an unlabeled board cannot be debugged). |

## What is NOT waived

- **The socket slot pokes 6 mm off-board — and that is INTENTIONAL.** Measured
  2026-10-12: the board outline is 103 x 103 mm with 1 outline / 0 holes; each
  J_W* footprint draws its own 0.95 x 6.0 mm Edge.Cuts slot. J_W1 (x 0..6) and
  J_W3 (x 97..103) are edge notches; J_W2 (y 103..109) and J_W4 (y -6..0) span
  the edge. **Attempting to pull J_W2/J_W4 inward was REFUTED by measurement:**
  DRC went 40 -> 110 violations (11 shorts, 27 mask bridges, 3 courtyard
  overlaps) because dragging the connector moved its pads onto foreign nets. The
  socket position is fixed by the WING geometry (ADR-049) — the connector must sit
  on the board edge to meet the inserted wing tab. So this family stays waived.
  Reproducible: `tracker/hardware/fix_hub_v9_socket_slots.py` (dry-run by
  default) + `cut_hub_v9_socket_slots.py` (exact slot bboxes).
- Copper-to-board-edge on real tracks/vias: **RESOLVED** for the +3V3 family by
  the In2.Cu plane (38 -> 4; commit f02f36b). The remaining 4 are the J_W*
  socket pads + their unavoidable stubs.
- The 6 genuinely unrouted nets (DIO2, MISO, W1-W3_SOLAR_N, GND island):
  routing work, not waivers.
- Starved thermals (4) and clearance (3): manual fixes.
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