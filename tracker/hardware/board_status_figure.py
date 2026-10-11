#!/usr/bin/env python3
"""board_status_figure.py — render a machine-checkable PCB status figure.

Reads the JSON from `board_status_census.py` and writes an SVG.  Nothing is
hand-typed: every bar, badge and number comes from the census.

The figure is SELF-DESCRIBING so it can be verified without a vision model:
every drawn element carries `data-*` attributes holding the census value it
represents (data-board, data-layer, data-segments, data-zones, data-pad-side,
data-value, data-verdict).  `board_status_figure_check.py` re-reads the SVG and
asserts the encoded values equal the census, that bar lengths match the declared
scale, and that no label was dropped.

Usage:
  /usr/bin/python3.14 board_status_census.py a.kicad_pcb b.kicad_pcb > census.json
  python3 board_status_figure.py census.json status.svg
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---- palette (dark theme) -------------------------------------------------
BG = "#0d1117"
FG = "#e6edf3"
MUTED = "#8b949e"
GRID = "#21262d"
LAYER_COLOR = {
    "F.Cu": "#e5484d",
    "In1.Cu": "#12a594",
    "In2.Cu": "#ffb224",
    "B.Cu": "#3e63dd",
}
SIDE_COLOR = {"front": "#e5484d", "back": "#3e63dd", "through": "#8b8d98"}
VERDICT_COLOR = {
    "routed": "#3fb950",
    "partial": "#d29922",
    "plane_only": "#ffb224",
    "placed_only": "#e5484d",
}

# ---- geometry ------------------------------------------------------------
W = 1360
MARGIN = 28
ROW_H = 176
HEADER_H = 104
LAYER_COLS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
LEFT_X = MARGIN
LEFT_W = 252          # hard width budget for the left column (name + details)
STACK_X = 300
STACK_W = 330         # width of the 4-column copper stack area
BAR_MAX_H = 78        # px for the tallest layer bar
PAD_X = 690
PADBAR_W = 210
CHAR_W = 0.62         # crude advance-width factor shared with the checker


def wrap(text: str, maxchars: int) -> list[str]:
    """Greedy word wrap so no left-column line can overrun its budget."""
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) <= maxchars:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def budget(maxchars: int, font: float) -> int:
    """How many characters fit in LEFT_W at `font` pt."""
    return max(8, int(LEFT_W / (CHAR_W * font)))



def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def render(boards: list[dict]) -> str:
    # Layout invariant, checked before anything is drawn: the left column's hard
    # budget must not reach the copper stack, or wrapped text would collide with
    # the layer labels (this is the defect the checker caught the first time).
    assert LEFT_X + LEFT_W < STACK_X, "left column would overrun the copper stack"
    assert STACK_X + STACK_W < PAD_X, "copper stack would overrun the pad bars"
    n = len(boards)
    height = HEADER_H + n * ROW_H + MARGIN
    max_seg = max((b["totals"]["segments"] for b in boards), default=1) or 1
    max_len = max((max(v["length_mm"] for v in b["layers"].values())
                   for b in boards), default=1.0) or 1.0

    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'viewBox="0 0 {W} {height}" font-family="DejaVu Sans, Helvetica, sans-serif">'
    )
    out.append(f'<rect width="{W}" height="{height}" fill="{BG}"/>')

    # title + scale legend (states the mapping, so a reader can check a bar)
    out.append(
        f'<text x="{MARGIN}" y="34" fill="{FG}" font-size="21" font-weight="bold">'
        f'PCB routing status — balloon-fresh v9 (machine-censused, pcbnew + kicad-cli DRC)</text>'
    )
    out.append(
        f'<text x="{MARGIN}" y="58" fill="{MUTED}" font-size="12">'
        f'Layer bar height: segments ÷ {max_seg} × {BAR_MAX_H}px  ·  '
        f'track length scale: {max_len:.0f}mm full width  ·  '
        f'hatched = filled copper zone  ·  verdict from DRC unconnected count'
        f'</text>'
    )
    out.append(
        f'<text x="{MARGIN}" y="80" fill="{MUTED}" font-size="12">'
        f'routed = copper present &amp; DRC unconnected 0  ·  partial = copper present, DRC unconnected &gt; 0  ·  '
        f'plane_only = zone(s), no tracks/vias  ·  placed_only = no copper at all'
        f'</text>'
    )
    out.append(
        f'<line x1="{MARGIN}" y1="{HEADER_H - 8}" x2="{W - MARGIN}" y2="{HEADER_H - 8}" '
        f'stroke="{GRID}" stroke-width="1"/>'
    )

    for i, b in enumerate(boards):
        y0 = HEADER_H + i * ROW_H
        cy = y0 + ROW_H / 2

        # board name + verdict badge + details, all inside the LEFT_W budget
        out.append(
            f'<g data-board="{esc(b["name"])}" data-verdict="{b["verdict"]}" '
            f'data-unconnected="{b["drc_unconnected"]}" data-copper-layers="{b["copper_layers"]}">'
        )
        ytxt = y0 + 22
        for line in wrap(b["name"], budget(LEFT_W, 14))[:2]:
            out.append(
                f'<text x="{LEFT_X}" y="{ytxt}" fill="{FG}" font-size="14" '
                f'font-weight="bold">{esc(line)}</text>'
            )
            ytxt += 17
        vc = VERDICT_COLOR.get(b["verdict"], MUTED)
        by = ytxt + 2
        out.append(
            f'<rect x="{LEFT_X}" y="{by}" width="{len(b["verdict"]) * 7.4 + 18}" '
            f'height="20" rx="10" fill="{vc}" fill-opacity="0.18" '
            f'stroke="{vc}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{LEFT_X + 9}" y="{by + 14}" fill="{vc}" font-size="12" '
            f'font-weight="bold">{esc(b["verdict"])}</text>'
        )
        detail = (
            f'{b["copper_layers"]}-layer · {b["footprints"]} footprints · '
            f'{b["totals"]["segments"]} segments · {b["totals"]["vias"]} vias · '
            f'{b["totals"]["zones"]} zones ({b["totals"]["zones_filled"]} filled) · '
            f'DRC unconnected {b["drc_unconnected"]}'
        )
        dytxt = by + 34
        for line in wrap(detail, budget(LEFT_W, 10.5)):
            out.append(
                f'<text x="{LEFT_X}" y="{dytxt}" fill="{MUTED}" font-size="10.5">'
                f'{esc(line)}</text>'
            )
            dytxt += 14
            if dytxt > y0 + ROW_H - 12:
                break

        # ---- copper stack: one column per possible layer -------------------
        sx = 300
        col_w = STACK_W / len(LAYER_COLS)
        base_y = y0 + ROW_H - 34
        out.append(
            f'<text x="{sx}" y="{y0 + 22}" fill="{MUTED}" font-size="11" '
            f'font-weight="bold">COPPER PER LAYER (segments)</text>'
        )
        for j, lname in enumerate(LAYER_COLS):
            lv = b["layers"].get(lname)
            enabled = lv is not None and (
                lv["segments"] or lv["vias"] or lv["zones"]
            )
            # layers that exist on the stack but carry nothing
            on_stack = (j == 0 or j == len(LAYER_COLS) - 1
                        or b["copper_layers"] > 2)
            cx = sx + j * col_w
            bw = col_w - 16
            col = LAYER_COLOR[lname]
            if not on_stack:
                col, op = "#30363d", 0.35
            else:
                op = 1.0
            seg = lv["segments"] if lv else 0
            zones = lv["zones"] if lv else 0
            length = lv["length_mm"] if lv else 0.0
            h = (BAR_MAX_H * seg / max_seg) if seg else 0
            out.append(
                f'<g data-layer="{lname}" data-segments="{seg}" data-zones="{zones}" '
                f'data-length-mm="{length:.2f}" data-enabled="{str(bool(enabled)).lower()}" '
                f'data-on-stack="{str(bool(on_stack)).lower()}">'
            )
            out.append(
                f'<rect x="{cx}" y="{base_y - BAR_MAX_H}" width="{bw}" height="{BAR_MAX_H}" '
                f'fill="{GRID}" fill-opacity="0.45"/>'
            )
            if h > 0:
                out.append(
                    f'<rect x="{cx}" y="{base_y - h}" width="{bw}" height="{h:.2f}" '
                    f'fill="{col}" fill-opacity="{op}" data-role="segments-bar"/>'
                )
            if zones:
                # hatched overlay: a filled zone is present on this layer
                out.append(
                    f'<rect x="{cx}" y="{base_y - BAR_MAX_H}" width="{bw}" '
                    f'height="{BAR_MAX_H}" fill="url(#hatch)" fill-opacity="0.9" '
                    f'data-role="zone-overlay"/>'
                )
            out.append(
                f'<text x="{cx + bw / 2:.1f}" y="{base_y + 16}" fill="{FG}" '
                f'font-size="11" text-anchor="middle">{lname}</text>'
            )
            out.append(
                f'<text x="{cx + bw / 2:.1f}" y="{base_y - BAR_MAX_H - 6}" fill="{col}" '
                f'font-size="11" text-anchor="middle" font-weight="bold">{seg}'
                + (f'⬚' if zones else '') + '</text>'
            )
            out.append('</g>')

        # ---- pads per mounting side ---------------------------------------
        px = 690
        out.append(
            f'<text x="{px}" y="{y0 + 22}" fill="{MUTED}" font-size="11" '
            f'font-weight="bold">PADS PER SIDE</text>'
        )
        pads = b["pads"]
        order = ("front", "back", "through")
        ptot = sum(pads.get(k, 0) for k in order) or 1
        bar_y = y0 + 44
        cursor = px
        for side in order:
            val = pads.get(side, 0)
            w = PADBAR_W * val / ptot
            col = SIDE_COLOR[side]
            out.append(
                f'<g data-pad-side="{side}" data-value="{val}">'
            )
            if w > 0:
                out.append(
                    f'<rect x="{cursor:.2f}" y="{bar_y}" width="{w:.2f}" height="26" '
                    f'fill="{col}" data-role="pad-bar"/>'
                )
            out.append('</g>')
            cursor += w
        cursor = px
        for side in order:
            val = pads.get(side, 0)
            w = PADBAR_W * val / ptot
            if w > 0:
                out.append(
                    f'<text x="{cursor + w / 2:.1f}" y="{bar_y + 18}" fill="#0d1117" '
                    f'font-size="12" text-anchor="middle" font-weight="bold">{val}</text>'
                )
            cursor += w
        ly = bar_y + 44
        for side in order:
            col = SIDE_COLOR[side]
            out.append(
                f'<rect x="{px + order.index(side) * 74}" y="{ly}" width="10" height="10" '
                f'fill="{col}"/>'
            )
            out.append(
                f'<text x="{px + order.index(side) * 74 + 14}" y="{ly + 9}" fill="{MUTED}" '
                f'font-size="11">{side} {pads.get(side, 0)}</text>'
            )

        out.append('</g>')

    # hatch pattern defs
    out.append(
        f'<defs><pattern id="hatch" width="7" height="7" patternTransform="rotate(45)" '
        f'patternUnits="userSpaceOnUse">'
        f'<line x1="0" y1="0" x2="0" y2="7" stroke="{FG}" stroke-opacity="0.55" stroke-width="2"/>'
        f'</pattern></defs>'
    )
    out.append('</svg>')
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    boards = json.loads(Path(argv[0]).read_text())
    svg = render(boards)
    Path(argv[1]).write_text(svg)
    print(f"wrote {argv[1]} ({len(svg)} bytes, {len(boards)} boards)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
