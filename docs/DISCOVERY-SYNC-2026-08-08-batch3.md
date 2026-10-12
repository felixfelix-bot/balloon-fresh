# Discovery Sync — 2026-08-08 Batch 3

## Finding: feat(router): diagonal 45° routing capability for PCB v7
- **Source:** balloon-circuit-design, commit `cbdd656`
- **Tags:** HARDWARE, PROTOCOL
- **Files:** tracker/hardware/route_diagonal.py

## FIPS Relevance: HIGH

### Current FIPS PCB State
- Board: hub_board_f33.kicad_pcb
- DRC: 177 violations (15 shorting, 32 unconnected)
- Router: tracker/hardware/router.py — Manhattan-only, 403 lines
- Router type: text-based (no pcbnew dependency, standalone)

### What the Discovery Provides
8 diagonal 45° routing patterns:
1. Single 45° diagonal (both slopes)
2. Diagonal + orthogonal (45° then H/V, or H/V then 45°)
3. Z-shaped: diagonal 45°, horizontal, diagonal -45° (and mirror + vertical-middle variants)
4. 2-segment diagonal: two 45° segments meeting at computed midpoint
5. Mixed-layer: diagonal on F.Cu, via, diagonal on B.Cu, via back

Applied to v7 board: 9/16 → 13/16 signal nets routed (44% improvement in completion).

### Assessment for FIPS Adoption
- **Transferable:** YES. FIPS router.py has the same geometry functions (point_to_seg_dist,
  seg_to_seg_dist, _segments_intersect) needed for diagonal collision detection.
- **Approach:** Add diagonal patterns to router.py's `_try_detour()` method. The text-based
  router emits KiCad segments directly — diagonal segments are just (x1,y1)-(x2,y2) pairs
  with non-orthogonal coordinates. No architectural change needed.
- **Expected impact:** Could close some of the 32 unconnected nets on f33 board.
  The 15 shorts may need manual track removal first (separate issue).
- **Priority:** MEDIUM — FIPS board f33 needs routing work. Diagonal capability would
  improve routing density. But shorts (15) must be fixed first before adding complexity.

### Action Plan
1. Fix existing 15 shorts on f33 board first (track removal / layer reassignment)
2. Port diagonal patterns from route_diagonal.py into router.py's _try_detour()
3. Re-run router on cleaned f33 board with diagonal patterns enabled
4. DRC verify

### No Code Changes This Sync
This is an assessment-only sync. No FIPS code modified. Will adopt diagonal routing
when routing work resumes on f33 board.

## Other Discoveries This Batch
- balloon-hermes dcb3778: "9/16 signal nets routed, FreeROUTING hung — need diagonal router"
  → Informational. This is the same gap that cbdd656 addresses. Confirms FreeROUTING
  is unreliable for balloon PCBs; diagonal router is the solution.

- balloon-pre-stretching 773f824: "FreeROUTING hung, no weight impact, informational"
  → No FIPS impact. Weight estimates are pre-stretching track concern.