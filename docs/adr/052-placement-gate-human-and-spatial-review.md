# ADR-052: Placement Gate with Human + Spatial-LLM Review Before Routing

**Date:** 2026-10-13
**Status:** Accepted
**Decision Maker:** Felix (operator) — "getting user feedback on a 3d model of the parts once they are placed... before routing them" + standing goal clause "reviewed by an LLM with good spatial reasoning (like Astra)"
**Related:** ADR-051 (order of operations), docs/BENCH-CONSOLE-SPEC.md

## Context

Routing is the most expensive stage (engine hours + iteration loops). The
hub-v9 session measured nine refuted blind geometric nudges before a measured
0.1 mm-resolution scan produced the first true answer — every nudge thrashed
a violation family or silently did nothing. Placement quality determines
routability (U4 zero-escape vs U1 141–328 spots, same board, same rules).

Felix is a visual thinker (stated profile) and reviews geometry well from
images. Until 2026-10-13 the spatial-LLM lane was unusable — the consultant
sent `image/svg+xml` which the Codex vision backend rejects outright
(90-byte SVG → 503; 27 KB PNG → 200 with real vision). Fixed by rasterizing
SVG→PNG in `visual_consult.py` (hermes-orchestration master `197ccc06`);
the consultant then returned a full verdict on the real board on first try.

## Decision

**No board advances from placement to routing without BOTH reviews:**

1. **Felix review**: the pipeline renders the placed board (3D STEP render +
   per-layer SVGs rasterized to PNG) and sends it in Signal for operator
   approval. Visual, ergonomic, and RF-sanity judgement lives here.
2. **Astra spatial review**: the same renders go to `visual_consult.py`
   (gpt-6-astra lane) with a board-specific question set. The verdict file
   (APPROVED / CHANGES_REQUESTED / PARTIAL) is committed as the artifact of
   record (D-128 §20 pattern: `docs/CONSULT-<topic>-<date>.txt`).

Both must pass. A CHANGES_REQUESTED from either reviewer sends the board back
to stage 3 (deterministic re-placement), not to routing.

For the Done gate on the kanban board, the **post-route** Astra review
additionally reviews the routed result (standing goal requirement).

## Consequences

- Every board gains two render-and-review checkpoints (pre-route, pre-done).
- Renders must be PNG (or rasterized) — never raw SVG payloads.
- The consultant lane's per-request flakiness is absorbed by retry (~6×),
  already the documented practice.

## Verification hooks

- `kicad-cli pcb export step` + `pcb export svg` → `convert` rasterize.
- Verdict regex: `VERDICT: APPROVED|CHANGES_REQUESTED|PARTIAL` (as parsed by
  `visual_consult.py`).
