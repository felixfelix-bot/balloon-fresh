# Bounded C10 routing attempt — REJECTED / no route found

No legal joint routing candidate was found within this bounded search. The preserved candidate directory is a full matching project copy, refilled and scored, **with no new copper added**, not a completed routing solution. Both required C10 connections still fail.

## Scope and method

Exact source: `/home/c08r4d0r/reports/pr468-verification-853f648c/connectivity/refilled-after/board.kicad_pcb` (SHA256 a732114acc2e0cf5950b750d2b64ad6f42890b7687cad178bba2942e3c892ce9, verified unchanged).

`route.py` imports the frozen graph_kernel.py at the supplied verification path, consuming actual geometry nodes including net-bearing copper graphics. Hard obstacles include foreign pads/tracks/vias/graphics, netless copper and board/footprint edges. Foreign filled zones may retreat during refill. No handpicked track coordinates; deterministic 0.1 mm eight-neighbor Dijkstra search within +/-4 mm of each source pad. Track width 0.2 mm, through via 0.6/0.3 mm; clearance buffers add 1 um safety. All pads, including same-net pads, exclude via annuli. Conservative 0.5 mm edge clearance retained without modifying project rules. Existing drill exclusion is conservative.

Power search: F.Cu escape from U1.2 to an off-pad through-via site overlapping existing C10.1-connected In1.Cu copper. Ground search: F.Cu escape from C10.2 to an off-pad via site overlapping U7.2-connected B.Cu copper. Search explored 165 and 218 reachable grid points respectively, around 15 seconds per target including geometry preparation. Neither found a legal site. No alternate board candidates generated.

This restricted topology/grid failure is **not proof of routing impossibility**: it does not search additional In1 routing segments, multiple transitions, alternative ground landing layers, or sub-grid escapes. The preserved board is unchanged routing, rather than fabricated partial success.

## Native result after refill

KiCad/pcbnew 9.0.9; `ZONE_FILLER.Fill` then SaveBoard. Matching .kicad_pro/.kicad_dru and libraries copied intact.

| Metric | Baseline | Attempt |
|---|---:|---:|
| Unconnected native records | 41 | 41 |
| Non-connectivity warnings | 24 | 24 |
| Non-connectivity errors | 0 | 0 |

Full violation multiset comparison (type, severity, description, sorted item UUIDs): zero added, zero removed. Frozen graph check: C10.1→U1.2 false; C10.2→U7.2 false.

## Artifacts

- `candidate/`: complete matching project copy, refilled.
- `before-refill.kicad_pcb`: saved pre-refill board evidence (project context remains in candidate/).
- `route.py`: bounded search and copy/refill script; refuses existing candidate directory.
- `search.json`: search outcomes and budgets.
- `native-candidate.json`: full native DRC.
- `check.py`, `comparison.json`: graph target tests and full native multiset comparison.

Canonical/manual-handoff untouched. No component motion, rule modification or removed geometry. Evidence prepared on separate feature branch for manager publication.

## Independent completion checks

Baseline and candidate SHA256 are identical: `a732114acc2e0cf5950b750d2b64ad6f42890b7687cad178bba2942e3c892ce9`. Independently repeated full graph verification includes 228 pads, 983 tracks, 107 vias, 11 conductive graphics and 76 filled islands. MISO PASS; both C10 targets FAIL; zero broken or newly joined common pad pairs. See `connectivity/{baseline,candidate}.json` and `connectivity/partition-baseline-candidate.json`.

Annotated physical-width hard-copper images are in `visuals/local-F.Cu-before-after.png` and the other three layer views; no zone fills are drawn. Both sides intentionally show identical geometry and SHA. XML parsing and annotation-presence checks passed.

Search limitations: 0.1 mm source-relative grid and conservative keepouts can miss valid narrow corridors. No refusal/open-corridor calibration was performed. Consequently the search failure is only nonconvergence of this bounded attempt, NOT a finding that the board is unroutable. Further work needs a finer-grid calibrated search and inner-layer continuation rather than repeating this restricted landing-only search.
