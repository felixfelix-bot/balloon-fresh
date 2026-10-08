#!/usr/bin/env python3
"""Render the amplifier-vs-antenna figure as SVG (no matplotlib needed).

Outputs: docs/analysis/assets/ground-station-amp-vs-ant-figure.svg
Rasterise: cairosvg <svg> -o <png> -s 2

Two panels:
  A) 2.4 GHz gain -> HPBW (log y-axis) -> tracker class (and its cost band)
  B) EUR per dB, effective, by source of dB

v2 (after consultant review): HPBW axis is LOG so the low-gain region is not
crowded; the 27 dBi callout was moved above its marker; subtitle and panel-B
footnotes were shortened so nothing is clipped at the canvas edge; heading typo
"pointiacy" -> "pointing" fixed.
"""
import math, os

W, H = 1440, 800
BG = "#0f1419"; FG = "#e8eaed"; GRID = "#2a323d"; ACC = "#4cc9f0"
C1 = "#f72585"; C2 = "#4cc9f0"; C3 = "#90be6d"; C4 = "#f9c74f"; C5 = "#f3722c"
FONT = "DejaVu Sans, sans-serif"

def hpbw(g_dbi, f=2400.0, eta=0.55):
    lam = 299.792458 / f
    D = (lam/math.pi)*math.sqrt(10**(g_dbi/10.0)/eta)
    return 70.0*lam/D

out = []; A = out.append
A(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
A(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
A(f'<text x="30" y="40" fill="{FG}" font-family="{FONT}" font-size="25" font-weight="bold">'
  'Ground-station amplifiers vs antenna gain: does a wider beam collapse the tracker?</text>')
A(f'<text x="30" y="68" fill="#9aa4b2" font-family="{FONT}" font-size="14">'
  'PA can replace 2.4 GHz TX antenna gain (EIRP, 1:1); an LNA cannot replace 433 RX gain (cascade cap ~6.4 dB).</text>')

# ---------------- Panel A ----------------
ax0, ay0, aw, ah = 105, 120, 590, 500
A(f'<text x="{ax0}" y="{ay0-20}" fill="{C2}" font-family="{FONT}" font-size="18" font-weight="bold">'
  'A. 2.4 GHz gain &#8594; beamwidth &#8594; pointing budget / tracker class</text>')
A(f'<rect x="{ax0}" y="{ay0}" width="{aw}" height="{ah}" fill="#151b22" stroke="{GRID}"/>')

gmax = 30.0
hmin, hmax = 6.0, 180.0
def X(g): return ax0 + (g/gmax)*aw
def Y(h):
    h = max(hmin, min(h, hmax))
    return ay0 + ah - (math.log10(h)-math.log10(hmin))/(math.log10(hmax)-math.log10(hmin))*ah

# tracker-class bands (log scale handled by Y). The top band's label is
# right-anchored because the curve descends through the low-gain region on the
# left (consultant caught the collision); the lower three are left-anchored,
# where the curve has already left the frame.
bands = [
 (60, 180, "#90be6d", "no tracker (omni)",                                    "end"),
 (20, 60,  "#f9c74f", "hand-aim / fixed",                                     "start"),
 (10, 20,  "#f3722c", "open-loop stepper  \u20ac40",                          "start"),
 (6,  10,  "#f72585", "closed-loop / commercial  \u20ac359\u2013\u20ac1775",   "start"),
]
for lo, hi, col, lab, anc in bands:
    y_hi, y_lo = Y(hi), Y(lo)
    A(f'<rect x="{ax0}" y="{y_hi:.1f}" width="{aw}" height="{(y_lo-y_hi):.1f}" fill="{col}" opacity="0.12"/>')
    tx = (ax0+aw-8) if anc == "end" else (ax0+8)
    A(f'<text x="{tx}" y="{(y_hi+y_lo)/2+4:.1f}" fill="{col}" text-anchor="{anc}" font-family="{FONT}" font-size="11.5" font-weight="bold">{lab}</text>')

for h in (6, 8, 10, 15, 20, 30, 40, 60, 90, 120, 180):
    yv = Y(h)
    A(f'<line x1="{ax0}" y1="{yv:.1f}" x2="{ax0+aw}" y2="{yv:.1f}" stroke="{GRID}" stroke-width="1"/>')
    A(f'<text x="{ax0-9}" y="{yv+4:.1f}" fill="#9aa4b2" text-anchor="end" font-family="{FONT}" font-size="11.5">{h}&#176;</text>')
for g in range(0, 31, 5):
    xv = X(g)
    A(f'<line x1="{xv:.1f}" y1="{ay0}" x2="{xv:.1f}" y2="{ay0+ah}" stroke="{GRID}" stroke-width="1"/>')
    A(f'<text x="{xv:.1f}" y="{ay0+ah+19}" fill="#9aa4b2" text-anchor="middle" font-family="{FONT}" font-size="11.5">{g}</text>')
A(f'<text x="{ax0+aw/2:.0f}" y="{ay0+ah+45}" fill="{FG}" text-anchor="middle" font-family="{FONT}" font-size="13.5">Ground antenna gain (dBi) @ 2.4 GHz</text>')
A(f'<text x="30" y="{ay0+ah/2:.0f}" fill="{FG}" text-anchor="middle" transform="rotate(-90 30 {ay0+ah/2:.0f})" font-family="{FONT}" font-size="13">HPBW (deg), log scale, 70&#183;&#955;/D, &#951;=0.55</text>')

pts = []; g = 0.5
while g <= 30.0:
    pts.append((X(g), Y(hpbw(g)))); g += 0.2
A('<polyline fill="none" stroke="%s" stroke-width="3.2" points="%s"/>' % (ACC, " ".join(f"{x:.1f},{y:.1f}" for x,y in pts)))

marks = [(6, "6 dBi / 81.7&#176;", "no tracker", C3, 22, -36),
         (15, "15 dBi / 29.0&#176;", "open-loop  \u20ac40", C4, 12, -14),
         (27, "27 dBi / 7.3&#176;", "commercial \u20ac1,260+", C1, -118, -34)]
for g, lab, sub, col, dx, dy in marks:
    x, y = X(g), Y(hpbw(g))
    A(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{col}" stroke="{BG}" stroke-width="2"/>')
    A(f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" fill="{col}" font-family="{FONT}" font-size="12.5" font-weight="bold">{lab}</text>')
    A(f'<text x="{x+dx:.1f}" y="{y+dy+15:.1f}" fill="#cfd6df" font-family="{FONT}" font-size="11">{sub}</text>')

# ---------------- Panel B ----------------
bx0, by0, bw, bh = 800, 120, 580, 500
A(f'<text x="{bx0}" y="{by0-20}" fill="{C2}" font-family="{FONT}" font-size="18" font-weight="bold">'
  'B. Cost per dB that reaches the link (&#8364;/dB)</text>')
A(f'<rect x="{bx0}" y="{by0}" width="{bw}" height="{bh}" fill="#151b22" stroke="{GRID}"/>')

items = [
 ("433 Yagi 13.1&#8594;14.8 dBi",       3.24, C3),
 ("2.4 PA 1 W (+12 dB EIRP)",           5.75, C3),
 ("2.4 PA 12 W (+22.3 dB EIRP)",        8.30, C4),
 ("433 Yagi 6&#8594;15 dBi",            8.30, C4),
 ("2.4 dish+feed 0.75 m (+18 dB)",     15.55, C4),
 ("13 cm Yagi 2.4 GHz (+12 dB)",       19.92, C5),
 ("433 LNA EFFECTIVE (&#247; 6.4 dB)", 40.41, C1),
 ("433 Yagi 14.8&#8594;18 dBi",        43.91, C1),
]
vmax = 46.0; rowh = 52; y = by0 + 32
for lab, val, col in items:
    xlen = (val/vmax)*bw*0.78
    A(f'<text x="{bx0+12}" y="{y-7}" fill="{FG}" font-family="{FONT}" font-size="12.5">{lab}</text>')
    A(f'<rect x="{bx0+12}" y="{y}" width="{xlen:.1f}" height="22" fill="{col}" opacity="0.85" rx="3"/>')
    A(f'<text x="{bx0+18+xlen:.1f}" y="{y+16}" fill="{FG}" font-family="{FONT}" font-size="12.5" font-weight="bold">&#8364;{val:.1f}</text>')
    y += rowh
A(f'<text x="{bx0+bw/2:.0f}" y="{by0+bh+34}" fill="#cfd6df" text-anchor="middle" font-family="{FONT}" font-size="12">'
  'An LNA&#39;s 20 dB gain is NOT 20 dB of link &#8212; the cascade caps it at ~6.4 dB,</text>')
A(f'<text x="{bx0+bw/2:.0f}" y="{by0+bh+52}" fill="#cfd6df" text-anchor="middle" font-family="{FONT}" font-size="12">'
  'so its honest price is &#8364;40/dB, 8&#215; a 433 Yagi. On TX a PA is 2&#8211;2.7&#215; the dish&#39;s value.</text>')

A('</svg>')
svg = "\n".join(out)
os.makedirs("docs/analysis/assets", exist_ok=True)
p = "docs/analysis/assets/ground-station-amp-vs-ant-figure.svg"
open(p, "w").write(svg)
print("wrote", p, len(svg), "bytes")
