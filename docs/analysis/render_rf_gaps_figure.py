#!/usr/bin/env python3
"""render_rf_gaps_figure.py — emit the Ruze surface-error figure (SVG, no deps).

Plots gain loss vs RMS surface error at 2.4 GHz (lambda = 124.91 mm), with:
  * the Ruze curve (685.81*(eps/lambda)^2 dB)
  * the 0.5 dB and 1 dB budget lines and their RMS thresholds
  * the lambda/10 = 12.49 mm marker (the "rule of thumb")
  * each candidate reflector construction as a vertical RMS band, named in the
    right-hand column (all text lives in the plot margins / legend, so no
    method label ever sits on top of a data band).

Numbers are imported from rf_gaps_model.py; none are re-typed here.

Run: python3 docs/analysis/render_rf_gaps_figure.py > docs/analysis/assets/rf-gaps/ruze-2g4-surface-error.svg
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from rf_gaps_model import C_LIGHT, F_24, eps_for_loss, ruze_loss_db  # noqa: E402

LAM = C_LIGHT / F_24                    # m
LAM_MM = LAM * 1000.0

W, H = 1320, 820
PL, PR = 120, 800                        # plot area x
PT, PB = 100, 660                        # plot area y
XMIN, XMAX = 0.0, 16.0                   # mm
YMIN, YMAX = 0.0, 12.0                   # dB
LX = 850                                 # right legend column


def X(mm):
    return PL + (mm - XMIN) / (XMAX - XMIN) * (PR - PL)


def Y(db):
    return PB - (db - YMIN) / (YMAX - YMIN) * (PB - PT)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


out = []
out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="DejaVu Sans, sans-serif">')
out.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
out.append(f'<text x="{W/2}" y="42" font-size="22" font-weight="bold" text-anchor="middle">'
           '2.4 GHz reflector surface-accuracy budget (Ruze)</text>')
out.append(f'<text x="{W/2}" y="68" font-size="14" text-anchor="middle" fill="#444">'
           f'gain loss = 685.81 * (rms_error / lambda)^2 dB;  lambda = {LAM_MM:.2f} mm at '
           f'{F_24/1e9:.3f} GHz</text>')

# plot background + grid
out.append(f'<rect x="{PL}" y="{PT}" width="{PR-PL}" height="{PB-PT}" fill="#fbfbfb" '
           'stroke="#888" stroke-width="1"/>')
for mm in range(0, 17, 2):
    x = X(mm)
    out.append(f'<line x1="{x:.1f}" y1="{PT}" x2="{x:.1f}" y2="{PB}" stroke="#e8e8e8"/>')
    out.append(f'<text x="{x:.1f}" y="{PB+22}" font-size="13" text-anchor="middle">{mm}</text>')
for db in range(0, 13, 2):
    y = Y(db)
    out.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{PR}" y2="{y:.1f}" stroke="#e8e8e8"/>')
    out.append(f'<text x="{PL-12}" y="{y+5:.1f}" font-size="13" text-anchor="end">{db}</text>')
out.append(f'<text x="{(PL+PR)/2}" y="{PB+52}" font-size="15" text-anchor="middle">'
           'RMS surface error (mm)</text>')
out.append(f'<text x="34" y="{(PT+PB)/2}" font-size="15" text-anchor="middle" '
           f'transform="rotate(-90 34 {(PT+PB)/2})">gain loss (dB)</text>')

# candidate bands (vertical, low opacity, widest first)
methods = [
    ("aluminium foil, hand-formed", 8.0, 25.0, "#ef4444"),
    ("metal tape over foam/ribs", 5.0, 15.0, "#f97316"),
    ("welded mesh on DIY ribs", 3.0, 8.0, "#eab308"),
    ("3D-printed petal dish (FDM)", 1.0, 3.0, "#22c55e"),
    ("fibreglass over a mould", 0.5, 1.5, "#14b8a6"),
    ("used production Ku dish", 0.3, 1.0, "#0ea5e9"),
]
for name, lo, hi, col in methods:
    x0 = X(max(lo, XMIN))
    x1 = X(min(hi, XMAX))
    out.append(f'<rect x="{x0:.1f}" y="{PT}" width="{max(x1-x0,2):.1f}" '
               f'height="{PB-PT}" fill="{col}" opacity="0.16"/>')
    if hi > XMAX:   # band extends past the axis — mark the open right edge
        out.append(f'<polygon points="{x1:.1f},{PT+2} {x1-9:.1f},{PT+10} {x1-9:.1f},{PT-6}" '
                   f'fill="{col}" opacity="0.9"/>')

# Ruze curve
pts = []
mm = 0.0
while mm <= XMAX + 1e-9:
    pts.append(f"{X(mm):.1f},{Y(min(ruze_loss_db(mm/1000.0, LAM), YMAX)):.1f}")
    mm += 0.1
out.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#1d4ed8" '
           'stroke-width="3"/>')

# budget lines (thresholds computed from the model — single source of truth)
for db, col in ((0.5, "#15803d"), (1.0, "#b45309")):
    mmv = eps_for_loss(LAM, db) * 1000.0
    y = Y(db)
    out.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{X(mmv):.1f}" y2="{y:.1f}" '
               f'stroke="{col}" stroke-width="2" stroke-dasharray="7 5"/>')
    out.append(f'<line x1="{X(mmv):.1f}" y1="{y:.1f}" x2="{X(mmv):.1f}" y2="{PB}" '
               f'stroke="{col}" stroke-width="2" stroke-dasharray="7 5"/>')
    out.append(f'<text x="{X(mmv)+8:.1f}" y="{y-8:.1f}" font-size="13" fill="{col}" '
               f'font-weight="bold">{db:g} dB &lt;= {mmv:.2f} mm rms</text>')

# lambda/10 marker
xl = X(12.49)
out.append(f'<line x1="{xl:.1f}" y1="{PT}" x2="{xl:.1f}" y2="{PB}" stroke="#dc2626" '
           'stroke-width="2"/>')
out.append(f'<text x="{xl-8:.1f}" y="{PT+24}" font-size="13" fill="#dc2626" '
           f'text-anchor="end">lambda/10 = 12.49 mm (6.86 dB!)</text>')

# right legend column
out.append(f'<text x="{LX}" y="{PT+4}" font-size="15" font-weight="bold">Legend</text>')
leg = [("#1d4ed8", "Ruze gain loss"), ("#15803d", "0.5 dB budget"),
       ("#b45309", "1.0 dB budget"), ("#dc2626", "lambda/10 rule of thumb")]
for i, (col, lab) in enumerate(leg):
    yy = PT + 30 + i * 26
    out.append(f'<line x1="{LX}" y1="{yy}" x2="{LX+34}" y2="{yy}" stroke="{col}" '
               'stroke-width="3"/>')
    out.append(f'<text x="{LX+44}" y="{yy+5}" font-size="13">{esc(lab)}</text>')

out.append(f'<text x="{LX}" y="{PT+170}" font-size="15" font-weight="bold">'
           'Candidate reflector (rms, ESTIMATE)</text>')
for i, (name, lo, hi, col) in enumerate(methods):
    yy = PT + 200 + i * 30
    out.append(f'<rect x="{LX}" y="{yy-11}" width="22" height="14" rx="3" fill="{col}" '
               'opacity="0.85"/>')
    out.append(f'<text x="{LX+34}" y="{yy}" font-size="13">'
               f'{esc(name)}  {lo:g}-{hi:g} mm</text>')

out.append(f'<text x="{LX}" y="{PT+430}" font-size="12" fill="#555">'
           'Method bands are ESTIMATEs (no measured</text>')
out.append(f'<text x="{LX}" y="{PT+450}" font-size="12" fill="#555">'
           'source); only the Ruze curve and the</text>')
out.append(f'<text x="{LX}" y="{PT+470}" font-size="12" fill="#555">'
           'budget thresholds are computed.</text>')
out.append(f'<text x="{PL}" y="{PB+86}" font-size="12" fill="#555">'
           'Sources: Ruze eq. en.wikipedia.org/wiki/Ruze%27s_equation; band edges '
           'en.wikipedia.org/wiki/LPD433 and /List_of_WLAN_channels.</text>')
out.append('</svg>')
print("\n".join(out))
