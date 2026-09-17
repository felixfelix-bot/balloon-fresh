# archive/hardware-placement-legacy — placement nudge scripts (RETIRED 2026-09-17)

These files were hand-typed placement/patch scripts for the balloon flight
board.  They were retired on 2026-09-17 as part of PCB-S0 (kanban t_7c65638f)
because placement coordinates are GEOMETRY and must be COMPUTED, never
hand-typed.

They are kept in git history (this file is a marker; the scripts were moved
here with `git mv`, never deleted).  Do not resurrect them.  Fixes to placement
go through the dedicated tool:

    tracker/hardware/publish_placed_board.py      (the single writer of the
                                                   frozen placed board)
    KiCadRoutingTools py_placer/place_optimize.py (the placer)
    tracker/hardware/gate25_check.py              (the referee)

Why, in one line: the same two pad-overlap pairs (U2/C4 and D1/U1) survived on
the 55x45mm 4-layer board AND on the much bigger 80x60mm 2-layer board,
because every route/patch step inherited coordinates from these tables -
nobody owned the geometry, and every "nudge" created a new near-miss.

The measurement that forced the decision: `fix_placement_v2.py`'s literal
`placements` dict matches the shipped board's positions within 0.1mm for 16 of
20 footprints (commit 93427ca).  See
`tracker/hardware/placement-source-of-truth.json` for the full registry.
