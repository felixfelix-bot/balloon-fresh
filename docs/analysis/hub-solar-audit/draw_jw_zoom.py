#!/usr/bin/env python3
"""Render an annotated ZOOM of the J_W2 wing-seat area so the audit's claim can be SEEN.

Draws, in board coordinates clipped to a crop window:
  * every F.Cu track (thin), every B.Cu track (dashed cyan)
  * every pad outline on either outer layer, with its reference.pad label
  * the 0.20 mm pad-edge keep-out around the blocker object
  * J_W2.1 highlighted (the pad the audit says cannot escape) and D_BP2.1 (its partner)
  * a scale bar and the measured numbers printed on the image

Refuses to write if the repo's svg_layout_guard rejects the layout (visual-consultant pitfall 16).
Usage: draw_jw_zoom.py <board> <out.svg> [--cx 33.3 --cy 76.0 --w 18 --h 14]
"""
import argparse
import sys

sys.path.insert(0, "/home/c08r4d0r/worktrees/flight-readiness-20261102/tracker/hardware")
import svg_layout_guard as G  # noqa: E402
import pcbnew  # noqa: E402

UM = 1_000_000.0
PX = 40.0          # svg px per mm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("out")
    ap.add_argument("--cx", type=float, default=33.3)
    ap.add_argument("--cy", type=float, default=76.0)
    ap.add_argument("--w", type=float, default=18.0)
    ap.add_argument("--h", type=float, default=15.0)
    a = ap.parse_args()
    b = pcbnew.LoadBoard(a.board)

    W, H = int(a.w * PX) + 340, int(a.h * PX) + 130
    c = G.Canvas(W, H, strict_shapes=False)
    c.raw(f'<rect width="{W}" height="{H}" fill="#0d1520"/>')
    pad_px = int(a.h * PX)

    def X(x_mm):
        return (x_mm - (a.cx - a.w / 2)) * PX

    def Y(y_mm):
        return (y_mm - (a.cy - a.h / 2)) * PX

    def vis(x0, y0, x1, y1):
        return not (x1 < a.cx - a.w / 2 or x0 > a.cx + a.w / 2
                    or y1 < a.cy - a.h / 2 or y0 > a.cy + a.h / 2)

    # board area background
    c.raw(f'<rect x="0" y="0" width="{W}" height="{pad_px}" fill="#12311f" opacity="0.55"/>')

    # tracks
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            if not vis(p.x / UM, p.y / UM, p.x / UM, p.y / UM):
                continue
            c.raw(f'<circle cx="{X(p.x / UM):.1f}" cy="{Y(p.y / UM):.1f}" '
                  f'r="{t.GetWidth(pcbnew.F_Cu) / UM / 2 * PX:.1f}" fill="#ffffff"/>')
            continue
        x1, y1 = t.GetStart().x / UM, t.GetStart().y / UM
        x2, y2 = t.GetEnd().x / UM, t.GetEnd().y / UM
        if not vis(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)):
            continue
        col = "#c8611e" if t.GetLayer() == pcbnew.F_Cu else "#39c6d6"
        dash = '' if t.GetLayer() == pcbnew.F_Cu else ' stroke-dasharray="6 4"'
        wd = max(1.5, t.GetWidth() / UM * PX)
        c.raw(f'<line x1="{X(x1):.1f}" y1="{Y(y1):.1f}" x2="{X(x2):.1f}" y2="{Y(y2):.1f}" '
              f'stroke="{col}" stroke-width="{wd:.1f}" opacity="0.85"{dash}/>')

    # pads
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            x0, y0 = bb.GetLeft() / UM, bb.GetTop() / UM
            x1, y1 = bb.GetRight() / UM, bb.GetBottom() / UM
            if not vis(x0, y0, x1, y1):
                continue
            ref = fp.GetReference()
            tag = f"{ref}.{p.GetNumber()}"
            hi = tag in ("J_W2.1", "D_BP2.1")
            stroke = "#ffd166" if hi else "#8fb3c9"
            c.raw(f'<rect x="{X(x0):.1f}" y="{Y(y0):.1f}" width="{(x1 - x0) * PX:.1f}" '
                  f'height="{(y1 - y0) * PX:.1f}" fill="{"#ffd166" if hi else "none"}" '
                  f'fill-opacity="0.28" stroke="{stroke}" stroke-width="{2.5 if hi else 1.2}"/>')
            if hi:
                c.raw(f'<text x="{X((x0 + x1) / 2):.1f}" y="{Y(y0) - 6:.1f}" font-size="15" '
                      f'font-weight="bold" fill="#ffd166" text-anchor="middle">{tag}</text>')

    # the blocker the audit names: object at (35.10, 77.00) r=2.000, keep-out 2.300
    c.raw(f'<circle cx="{X(35.10):.1f}" cy="{Y(77.00):.1f}" r="{2.0 * PX:.1f}" '
          f'fill="none" stroke="#e2574c" stroke-width="2"/>')
    c.raw(f'<circle cx="{X(35.10):.1f}" cy="{Y(77.00):.1f}" r="{2.30 * PX:.1f}" '
          f'fill="none" stroke="#e2574c" stroke-width="1.2" stroke-dasharray="5 5" opacity="0.8"/>')
    # distance line 1.651 mm from pad centre
    c.raw(f'<line x1="{X(33.30):.1f}" y1="{Y(77.00):.1f}" x2="{X(35.10):.1f}" '
          f'y2="{Y(77.00):.1f}" stroke="#e2574c" stroke-width="1.4" stroke-dasharray="3 3"/>')

    # scale bar: 2 mm
    sb = 2.0 * PX
    c.raw(f'<line x1="20" y1="{pad_px - 18}" x2="{20 + sb:.0f}" y2="{pad_px - 18}" '
          f'stroke="#e8eef5" stroke-width="3"/>')
    c.raw(f'<text x="20" y="{pad_px - 26}" font-size="14" fill="#e8eef5">2 mm</text>')

    # caption strip
    lines = [
        f"J_W2 wing seat (crop {a.w:.0f} x {a.h:.0f} mm)  ·  F.Cu solid orange, B.Cu dashed cyan",
        "J_W2.1 = 4.00 x 1.20 mm SMD, F.Cu only  ·  legal first moves from its centre: 0 of 4",
        "blocker: keep-out object at (35.10,77.00) r=2.000 mm, needs 2.300 mm, actual 1.651 mm",
        "measured: bounded 2-layer A* with one via -> no path. D_BP2.1's own B.Cu is clear (2.75 mm).",
    ]
    y = pad_px + 26
    for ln in lines:
        c.text(18, y, ln, size=15, fill="#e8eef5")
        y += 24
    try:
        probs = c.write(a.out)
    except G.OverlapError as e:
        print("LAYOUT GUARD REFUSED:", e)
        return 2
    print(f"wrote {a.out} ({W}x{H}) guard problems={len(probs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
