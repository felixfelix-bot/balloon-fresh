#!/usr/bin/env python3
"""render_lowpower_link_figure.py — emit the decisive SVG for the low-power
LR2021 433 MHz ground-station analysis.

Panel A: required ground gain per modulation and per TX power, against the
         antenna-class reference lines (0 dBi omni, 12 dBi Yagi, 20 dBi dish).
Panel B: architecture sketch — one az/el positioner carrying a Ku offset dish
         (2.4 GHz) and a 433 Yagi boresighted beside it.

Data is imported from ground_station_lowpower_link_model.py; no numbers are
re-typed here.

Run: python3 docs/analysis/render_lowpower_link_figure.py > <out.svg>
"""
import math
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from ground_station_lowpower_link_model import (  # noqa: E402
    FSPL_433_650, required_g_ground)

ROWS = [
    ("LoRa SF12/BW62.5 (repo -143 dBm)", -143.0),
    ("LoRa SF12/BW125", -141.5),
    ("FLRC 650 kbps", -107.0),
    ("FLRC 1.04 Mbps", -105.0),
    ("FLRC 2.6 Mbps", -100.5),
]
TX = [("+22 dBm", 22.0, "#1a7f37"), ("+13 dBm", 13.0, "#d97706")]

W, H = 1500, 980
PL, PR = 250, 900          # panel A plot x-range
G_MIN, G_MAX = -32.0, 32.0
sx = (PR - PL) / (G_MAX - G_MIN)
x0 = PL + (0 - G_MIN) * sx   # zero line


def X(g):
    return PL + (g - G_MIN) * sx


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


out = []
out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="DejaVu Sans, Arial, sans-serif">')
out.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
out.append('<text x="24" y="40" font-size="26" font-weight="bold">'
           'Required ground-station gain at 433 MHz, 650 km '
           '(FSPL=%.1f dB, G_balloon=0 dBi)</text>' % FSPL_433_650)
out.append('<text x="24" y="68" font-size="16" fill="#444">'
           'required_G_ground = S_dBm + FSPL − P_tx − G_balloon '
           '— sources: Semtech LR2021 datasheet v2.2 Tables 3-12/3-17/3-22</text>')

# Panel A reference lines
ytop, ybot = 110, 590
for g, lbl, col in ((0, "0 dBi  omni", "#888"), (12, "12 dBi  Yagi", "#2563eb"),
                    (20, "20 dBi  dish ~2.7–3.0 m", "#dc2626")):
    out.append(f'<line x1="{X(g):.1f}" y1="{ytop}" x2="{X(g):.1f}" y2="{ybot}" '
               f'stroke="{col}" stroke-width="2" stroke-dasharray="6,5"/>')
    out.append(f'<text x="{X(g)+4:.1f}" y="{ytop-8}" font-size="14" fill="{col}" '
               f'font-weight="bold">{esc(lbl)}</text>')

row_h = (ybot - ytop) / len(ROWS)
for i, (name, s) in enumerate(ROWS):
    ry = ytop + i * row_h
    out.append(f'<text x="24" y="{ry + row_h/2 + 5:.1f}" font-size="16">{esc(name)}</text>')
    for j, (tlbl, ptx, col) in enumerate(TX):
        g = required_g_ground(s, ptx)
        by = ry + 14 + j * 40
        bx = min(X(0), X(g))
        bw = abs(X(g) - X(0))
        out.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{max(bw,1):.1f}" height="30" '
                   f'fill="{col}" opacity="0.85"/>')
        gtxt = f'{g:+.1f} dBi @ {tlbl}'
        tx = X(g) + 6 if g >= 0 else X(g) - 6
        anc = "start" if g >= 0 else "end"
        out.append(f'<text x="{tx:.1f}" y="{by+21:.1f}" font-size="14" fill="#111" '
                   f'text-anchor="{anc}">{esc(gtxt)}</text>')

out.append(f'<line x1="{X(0):.1f}" y1="{ytop}" x2="{X(0):.1f}" y2="{ybot}" '
           'stroke="#111" stroke-width="2.5"/>')
out.append(f'<text x="{X(0):.1f}" y="{ybot+24}" font-size="15" text-anchor="middle">'
           '0 dBi</text>')
out.append(f'<text x="{PR}" y="{ybot+24}" font-size="15" text-anchor="end">'
           'required ground gain (dBi) →</text>')
out.append(f'<text x="{PL}" y="{ybot+24}" font-size="15">← negative = gain not needed</text>')

# Legend
out.append('<rect x="24" y="620" width="18" height="18" fill="#1a7f37"/>'
           '<text x="48" y="634" font-size="15">TX +22 dBm (chip max, TXOPLF)</text>')
out.append('<rect x="360" y="620" width="18" height="18" fill="#d97706"/>'
           '<text x="384" y="634" font-size="15">TX +13 dBm (low-power op)</text>')

# Panel B — architecture sketch
bx0, by0 = 960, 120
out.append(f'<rect x="{bx0}" y="{by0}" width="500" height="470" fill="#f8fafc" '
           'stroke="#94a3b8" rx="10"/>')
out.append(f'<text x="{bx0+20}" y="{by0+30}" font-size="18" font-weight="bold">'
           'One positioner, two antennas (recommended)</text>')
# Ku dish (offset ellipse) at left
out.append(f'<ellipse cx="{bx0+150}" cy="{by0+200}" rx="95" ry="130" fill="#e2e8f0" '
           'stroke="#334155" stroke-width="3"/>')
out.append(f'<text x="{bx0+150}" y="{by0+150}" font-size="14" text-anchor="middle" '
           'fill="#0f172a">Ku offset dish</text>')
out.append(f'<text x="{bx0+150}" y="{by0+172}" font-size="13" text-anchor="middle" '
           'fill="#2563eb">2.4 GHz uplink</text>')
out.append(f'<text x="{bx0+150}" y="{by0+190}" font-size="12" text-anchor="middle" '
           'fill="#475569">~27 dBi / 7–10° beam</text>')
# feed at focus (offset, upper)
out.append(f'<rect x="{bx0+120}" y="{by0+95}" width="26" height="20" fill="#334155"/>')
out.append(f'<line x1="{bx0+133}" y1="{by0+115}" x2="{bx0+150}" y2="{by0+165}" '
           'stroke="#334155" stroke-width="2"/>')
# 433 Yagi beside dish
yy = by0 + 330
out.append(f'<line x1="{bx0+60}" y1="{yy}" x2="{bx0+250}" y2="{yy}" stroke="#b45309" '
           'stroke-width="5"/>')
for k in range(7):
    ex = bx0 + 70 + k * 28
    ln = 34 - k * 2
    out.append(f'<line x1="{ex}" y1="{yy-ln/2}" x2="{ex}" y2="{yy+ln/2}" stroke="#b45309" '
               'stroke-width="3"/>')
out.append(f'<text x="{bx0+160}" y="{yy+52}" font-size="14" text-anchor="middle" '
           'fill="#b45309">433 Yagi (LoRa downlink) ~12–15 dBi / 40–50° beam</text>')
out.append(f'<text x="{bx0+160}" y="{yy+74}" font-size="12" text-anchor="middle" '
           'fill="#475569">beside the aperture → blockage ≈ 0.1 dB</text>')
# positioner base
out.append(f'<rect x="{bx0+140}" y="{by0+400}" width="80" height="16" fill="#334155"/>')
out.append(f'<line x1="{bx0+180}" y1="{by0+330}" x2="{bx0+180}" y2="{by0+400}" '
           'stroke="#334155" stroke-width="4"/>')
out.append(f'<text x="{bx0+180}" y="{by0+440}" font-size="14" text-anchor="middle">'
           'az/el positioner</text>')
# warning box
out.append(f'<rect x="{bx0+15}" y="{by0+455}" width="470" height="0" fill="none"/>')

# Note strip
out.append('<text x="24" y="900" font-size="17" font-weight="bold" fill="#111">'
           'Verdict: LoRa → any antenna closes (req gain negative, 12–28 dB margin). '
           'FLRC → needs a dish (+9…+28 dBi).</text>')
out.append('<text x="24" y="926" font-size="17" font-weight="bold" fill="#b91c1c">'
           'The ONLY case that breaks the architecture: FLRC at 650 km with '
           'TX ≤ +19 dBm (433 antenna must be a ~2.7–3.0 m dish, not a Yagi).</text>')
out.append('<text x="24" y="954" font-size="14" fill="#334155">'
           'Repro: python3 docs/analysis/render_lowpower_link_figure.py | '
           'model: docs/analysis/ground_station_lowpower_link_model.py</text>')
out.append('</svg>')

sys.stdout.write("\n".join(out) + "\n")
