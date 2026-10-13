#!/usr/bin/env python3
"""Prepare a placement input board: rip routing, KEEP the zone planes.

Why this exists (PCB-S0 t_7c65638f)
----------------------------------
The placement stage must run on a copper-free board (a placement move leaves
tracks detached from their pads - the placer refuses a routed input for exactly
that reason).  But it must NOT lose the board's PLANES: the 4-layer flight board
carries an In1.Cu GND pour, an In2.Cu +3V3 pour and a 4-layer keepout, and the
routing stage refills them.  A naive "strip every (zone ...)" loses the stackup.

What it does
------------
  * removes every top-level (segment ...), (via ...) and (arc ...) block;
  * keeps every (zone ...) definition, but drops the stale fill geometry
    ((filled_polygon ...)) inside it - a moved part makes the old pour geometry
    a lie, and DRC then reports it as a clearance/hole_clearance violation with
    `actual 0.0000 mm` (the known stale-fill artefact);
  * touches NOTHING else: footprints, pads, nets and outlines pass through
    byte-identically.  This file computes no coordinates.

usage: python3 prep_placement_input.py <in.kicad_pcb> <out.kicad_pcb>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def blocks(text: str, keyword: str):
    """Yield (start, end, block) for every (keyword ...) block in text."""
    out = []
    i = 0
    tok = "(" + keyword
    while True:
        s = text.find(tok, i)
        if s < 0:
            break
        nxt = text[s + len(tok):s + len(tok) + 1]
        if nxt and (nxt.isalnum() or nxt == "_"):
            i = s + 1
            continue
        depth, j = 0, s
        while j < len(text):
            c = text[j]
            if c == '"':
                j += 1
                while j < len(text) and text[j] != '"':
                    if text[j] == "\\":
                        j += 1
                    j += 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append((s, j + 1, text[s:j + 1]))
        i = j + 1
    return out


def prep(src: str, dst: str) -> dict:
    t = Path(src).read_text(encoding="utf-8")
    edits = []
    stats = {"segments_removed": 0, "vias_removed": 0, "arcs_removed": 0,
             "zones_kept": 0, "stale_fills_removed": 0}
    for kw, key in (("segment", "segments_removed"), ("via", "vias_removed"), ("arc", "arcs_removed")):
        for s, e, blk in blocks(t, kw):
            if not re.match(r"\(" + kw + r"[\s(]", blk):
                continue
            stats[key] += 1
            edits.append((s, e, ""))
    for s, e, blk in blocks(t, "zone"):
        if not re.match(r"\(zone[\s(]", blk):
            continue
        stats["zones_kept"] += 1
        for fs, fe, fblk in blocks(blk, "filled_polygon"):
            if not re.match(r"\(filled_polygon[\s(]", fblk):
                continue
            stats["stale_fills_removed"] += 1
            edits.append((s + fs, s + fe, ""))
    edits.sort()
    out, prev = [], 0
    for s, e, _ in edits:
        out.append(t[prev:s])
        prev = e
    out.append(t[prev:])
    Path(dst).write_text("".join(out), encoding="utf-8")
    return stats


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    stats = prep(sys.argv[1], sys.argv[2])
    print(f"{sys.argv[1]} -> {sys.argv[2]}: {stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
