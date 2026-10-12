#!/usr/bin/env python3
"""Extract, per footprint of a .kicad_pcb, its F.Fab and F.CrtYd bounding boxes.

Read-only reconnaissance for the 3D-model generators: a footprint's own F.Fab
outline is an in-repo, machine-readable source for the part's X/Y envelope, so a
model can be authored with a cited dimension instead of a guessed one.
"""
from __future__ import annotations

import re
import sys


def blocks(text: str):
    i = 0
    while True:
        s = text.find("(footprint ", i)
        if s < 0:
            return
        d, pos = 0, s
        while pos < len(text):
            if text[pos] == "(":
                d += 1
            elif text[pos] == ")":
                d -= 1
                if d == 0:
                    pos += 1
                    break
            pos += 1
        yield text[s:pos]
        i = pos


def bbox_for_layer(block: str, layer: str):
    """Union of (start,end) of every fp_line/fp_rect/fp_poly on `layer`."""
    xs: list[float] = []
    ys: list[float] = []
    # fp_line / fp_rect carry (start x y) and (end x y); scan each graphic statement.
    for m in re.finditer(r"\((fp_line|fp_rect)\s", block):
        start = m.start()
        # take the balanced statement
        d, pos = 0, start
        while pos < len(block):
            if block[pos] == "(":
                d += 1
            elif block[pos] == ")":
                d -= 1
                if d == 0:
                    pos += 1
                    break
            pos += 1
        stmt = block[start:pos]
        if f'(layer "{layer}")' not in stmt:
            continue
        sm = re.search(r"\(start ([-\d.]+) ([-\d.]+)\)", stmt)
        em = re.search(r"\(end ([-\d.]+) ([-\d.]+)\)", stmt)
        if sm and em:
            xs += [float(sm.group(1)), float(em.group(1))]
            ys += [float(sm.group(2)), float(em.group(2))]
    if not xs:
        return None
    return (round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3),
            round(min(xs), 3), round(max(xs), 3), round(min(ys), 3), round(max(ys), 3))


def main(path: str) -> int:
    text = open(path).read()
    print(f"{'ref':8} {'value':26} {'fp':34} {'F.Fab wxh':>16} {'F.CrtYd wxh':>16}  model")
    for b in blocks(text):
        ref = re.search(r'\(property "Reference" "([^"]+)"', b)
        val = re.search(r'\(property "Value" "([^"]+)"', b)
        fp = re.search(r'\(footprint "([^"]+)"', b)
        fab = bbox_for_layer(b, "F.Fab")
        crt = bbox_for_layer(b, "F.CrtYd")
        models = re.findall(r'\(model "([^"]+)"', b)
        r = ref.group(1) if ref else "?"
        v = (val.group(1) if val else "")[:26]
        f = (fp.group(1) if fp else "")[:34]
        fs = f"{fab[0]} x {fab[1]}" if fab else "-"
        cs = f"{crt[0]} x {crt[1]}" if crt else "-"
        ms = "|".join(m.split("/")[-1] for m in models) if models else "(none)"
        print(f"{r:8} {v:26} {f:34} {fs:>16} {cs:>16}  {ms}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"))
