#!/usr/bin/env python3
"""Visual: where the 3 unrouted solar-return nets must travel on B.Cu.

Draws, on a B.Cu render:
  - the J_W wing lands involved (green squares)
  - the bypass diodes D_BP1..D_BP4 (blue squares)
  - a straight reference line per net pair (red dashed) purely to show the span
Nothing here is a proposed route; it shows the problem's geometry.
"""
import json
import pathlib
import re
import shutil
import subprocess

import pcbnew as k
from PIL import Image, ImageDraw

SRC = pathlib.Path('/home/c08r4d0r/worktrees/hub-repair-candidate/docs/analysis/'
                   'hub-repair-20261102/output/after')
OUT = pathlib.Path('/home/c08r4d0r/reports/hub-current-visuals/solar')
STEM = 'hub_board_v10_lora1280_7of9'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in SRC.glob(STEM + '.kicad_*'):
        shutil.copy(f, OUT / f.name)
    pcb = OUT / (STEM + '.kicad_pcb')
    b = k.LoadBoard(str(pcb))

    def pads_of(ref, num=None):
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            return []
        return [p for p in fp.Pads() if num is None or p.GetNumber() == num]

    # reference span lines from the audited pairs
    pairs = [
        ('/W1_SOLAR_N', 'D_BP1', '2', 'J_W1', '4'),
        ('/W1_SOLAR_N', 'D_BP2', '1', 'J_W2', '1'),
        ('/W2_SOLAR_N', 'D_BP2', '2', 'J_W2', '4'),
        ('/W2_SOLAR_N', 'D_BP3', '1', 'J_W3', '1'),
        ('/W3_SOLAR_N', 'D_BP3', '2', 'J_W3', '4'),
        ('/W3_SOLAR_N', 'D_BP4', '1', 'J_W4', '1'),
    ]

    def xy(p):
        return (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)

    # render B.Cu + Edge.Cuts, calibrate from the Edge.Cuts-only render
    def export(layers, name):
        svg = OUT / f'{name}.svg'
        subprocess.run(['kicad-cli', 'pcb', 'export', 'svg', '--layers', layers,
                        '--page-size-mode', '2', '--exclude-drawing-sheet',
                        '-o', str(svg), str(pcb)], capture_output=True, text=True)
        png = OUT / f'{name}.png'
        subprocess.run(['rsvg-convert', '-w', '1800', '-b', 'white',
                        '-o', str(png), str(svg)], capture_output=True, text=True)
        return svg, png

    def bbox(png):
        im = Image.open(png).convert('RGB')
        W, H = im.size
        px = im.load()
        mnx, mny, mxx, mxy = W, H, -1, -1
        for y in range(0, H, 2):
            for x in range(0, W, 2):
                r, g, bl = px[x, y]
                if not (r > 245 and g > 245 and bl > 245):
                    mnx, mny = min(mnx, x), min(mny, y)
                    mxx, mxy = max(mxx, x), max(mxy, y)
        return mnx, mny, mxx, mxy

    esvg, epng = export('Edge.Cuts', 'edge_only')
    vb = re.search(r'viewBox="([^"]*)"', esvg.read_text())
    vx, vy, vw, vh = [float(t) for t in vb.group(1).split()]
    ex0, ey0, ex1, ey1 = bbox(epng)

    svg, png = export('B.Cu,Edge.Cuts', 'back')
    im = Image.open(png).convert('RGB')
    W, H = im.size
    sx = W / Image.open(epng).size[0]
    sy = H / Image.open(epng).size[1]

    def px(p):
        X = (ex0 + (p[0] - vx) / vw * (ex1 - ex0)) * sx
        Y = (ey0 + (p[1] - vy) / vh * (ey1 - ey0)) * sy
        return X, Y

    d = ImageDraw.Draw(im)
    drawn = 0
    for net, dr, dn, jr, jn in pairs:
        dp = pads_of(dr, dn)
        jp = pads_of(jr, jn)
        if not dp or not jp:
            continue
        a = px(xy(dp[0]))
        c = px(xy(jp[0]))
        d.line([a, c], fill=(220, 30, 30), width=4)
        drawn += 1

    for ref in ('J_W1', 'J_W2', 'J_W3', 'J_W4'):
        for p in pads_of(ref):
            X, Y = px(xy(p))
            d.rectangle([X - 9, Y - 9, X + 9, Y + 9], outline=(0, 150, 0), width=4)
    for ref in ('D_BP1', 'D_BP2', 'D_BP3', 'D_BP4'):
        for p in pads_of(ref):
            X, Y = px(xy(p))
            d.ellipse([X - 8, Y - 8, X + 8, Y + 8], outline=(30, 80, 230), width=4)

    d.rectangle([0, 0, W, 40], fill=(255, 255, 255))
    d.text((10, 12), 'B.Cu  |  red = span still needing copper  |  '
                     'green squares = J_W wing lands  |  blue = bypass diodes D_BP1-4',
           fill=(0, 0, 0))
    im.save(OUT / 'solar_bcu_problem.png')
    print('wrote', OUT / 'solar_bcu_problem.png', 'spans drawn:', drawn)


if __name__ == '__main__':
    main()
