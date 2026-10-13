# ADR-053: DRC-to-Blockers Feedback Script as a Standard Board Tool

**Date:** 2026-10-13
**Status:** Accepted
**Decision Maker:** Felix (operator), directive 2026-10-13 ("codify the error-feedback cycle as one script")
**Related:** ADR-051 (order gates), ADR-052 (review gates)

## Context

The hub-v9 session repeatedly built the same diagnostic by hand: take a DRC
JSON (kicad-cli or agentee), find for each violation **which foreign item
blocks it and by how many mm**, and print a terse report that either a human
or the fix script can act on. Instances: the 4-clearance-graze analysis, the
U4/U1 escape scans (`blockers.py`/`escape2.py`), the via-piercing diagnosis
(`/F33_SCK` d=0.102 mm, `/I2C_SCL` d=0.054 mm), the fiducial cell scans.

The pattern works: after nine refuted blind nudges, the first measured
blocker report ended the thrash loop. But it was ad-hoc each time — tokens
were burned re-deriving geometry queries that are pure computation.

## Decision

One reusable tool: **`tracker/hardware/drc_blockers.py`** — input: a DRC
JSON + the board file; output: a terse per-violation blockers report
(`violation → nearest foreign item(s) → gap in mm → suggested fix family`),
covering:

- track/via/pad clearance (point, segment, endpoint-on-line cases)
- via-vs-track piercing (all layers)
- escape-space scans (free via spots + connecting-segment clearance, any pad)
- unconnected-item counts vs the board's baseline

Rules baked in (paid-for lessons):
1. **kicad-cli DRC is authoritative**; agentee is a supplementary gate, never
   the Source of Truth.
2. **Never `b.Remove()` while iterating `b.GetTracks()`** (use-after-free,
   RC=139) — collect-then-remove only.
3. Segment checks must include the **endpoint-on-line** case (a track ending
   ON another's path is a crossing, measured miss in fix-v1).
4. Obstacle scans must be **per-layer AND cross-layer** (through-via barrels
   occupy every layer).
5. Output is data (JSON-lines) so fix scripts consume it without re-parsing
   prose.

## Consequences

- Every board's DRC loop becomes: run DRC → `drc_blockers.py` → apply a fix
  from a proven family → re-DRC. No LLM arithmetic on coordinates.
- The nine refutation lessons become executable checks, not lore.
