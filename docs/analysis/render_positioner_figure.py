#!/usr/bin/env python3
"""render_positioner_figure.py — deterministic SVG figure for the low-cost
positioner study (stdlib only; no matplotlib on this box).

Emits docs/analysis/figures/positioner-rightsizing.svg

    python3 docs/analysis/render_positioner_figure.py

Panel A: wind force vs dish diameter (solid Cd 1.2, mesh Cd 0.5, stowed Cd 1.2)
         at 20 m/s, with 0.6 / 0.9 / 1.2 m marked.
Panel B: **required ground gain** for the 2.4 GHz uplink vs dish diameter at
         300 km (licence-exempt EIRP cap), showing that the requirement is
         negative -> no dish is needed to close, and the 0.6 m point.
"""
import math, os

RHO, CD_SOLID, CD_MESH, V = 1.225, 1.2, 0.5, 20.0
LAM24 = 299792458.0 / 2.4e9
PAD = 60
W, H = 980, 460


def area(D):
    return math.pi * D * D / 4.0


def F(D, Cd):
    return 0.5 * RHO * V * V * area(D) * Cd


def gain(D, eta=0.55):
    return 10 * math.log10(eta * (math.pi * D / LAM24) ** 2)


def stowed_area(D, fod=0.45):
    f = fod * D
    sag = D * D / (16 * f)
    return (4.0 / 3.0) * math.sqrt(4 * f) * sag ** 1.5


def panel(x0, y0, w, h, xmax, ymax, xlab, ylab, title, ymin=0.0):
    s = [f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#0f1115" stroke="#3a3f4b"/>']
    s.append(f'<text x="{x0+w/2}" y="{y0-12}" fill="#e8eaf0" font-size="15" text-anchor="middle" font-family="sans-serif">{title}</text>')
    s.append(f'<text x="{x0+w/2}" y="{y0+h+42}" fill="#c8ccd6" font-size="12" text-anchor="middle" font-family="sans-serif">{xlab}</text>')
    s.append(f'<text x="{x0-44}" y="{y0+h/2}" fill="#c8ccd6" font-size="12" text-anchor="middle" font-family="sans-serif" transform="rotate(-90 {x0-44} {y0+h/2})">{ylab}</text>')
    # gridlines
    for i in range(6):
        yy = y0 + h - h * i / 5
        s.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x0+w}" y2="{yy:.1f}" stroke="#23262e"/>')
        s.append(f'<text x="{x0-8}" y="{yy+4:.1f}" fill="#8a90a0" font-size="10" text-anchor="end" font-family="sans-serif">{ymin+(ymax-ymin)*i/5:.0f}</text>')
    for i in range(5):
        xx = x0 + w * i / 4
        s.append(f'<line x1="{xx:.1f}" y1="{y0}" x2="{xx:.1f}" y2="{y0+h}" stroke="#23262e"/>')
        s.append(f'<text x="{xx:.1f}" y="{y0+h+16}" fill="#8a90a0" font-size="10" text-anchor="middle" font-family="sans-serif">{xmax*i/4:.1f}</text>')
    return s, (lambda X: x0 + w * X / xmax), (lambda Y: y0 + h - h * (Y - ymin) / (ymax - ymin))


def main():
    os.makedirs("docs/analysis/figures", exist_ok=True)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<rect width="100%" height="100%" fill="#08090c"/>']

    # ---- Panel A: force vs diameter ----
    xmax, ymax = 1.5, 550.0
    s, X, Y = panel(PAD, 50, 400, 300, xmax, ymax, "dish diameter D [m]",
                    "wind force [N]", "A. Wind force vs dish, v=20 m/s")
    def curve(fn, color, dash="", label=None):
        pts = []
        for i in range(151):
            D = max(xmax * i / 150.0, 0.02)
            pts.append(f"{X(D):.1f},{Y(min(fn(D),ymax)):.1f}")
        s.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2.4" {dash}/>')
    curve(lambda D: F(D, CD_SOLID), "#ff5d5d")
    curve(lambda D: F(D, CD_MESH), "#4fd1ff")
    curve(lambda D: 0.118 * F(D, CD_SOLID), "#7CE38B", 'stroke-dasharray="7 5"')
    for D in (0.6, 0.9, 1.2):
        s.append(f'<line x1="{X(D):.1f}" y1="50" x2="{X(D):.1f}" y2="350" stroke="#ffffff" stroke-opacity="0.25" stroke-dasharray="3 4"/>')
        s.append(f'<text x="{X(D):.1f}" y="44" fill="#e8eaf0" font-size="11" text-anchor="middle" font-family="sans-serif">{D:.1f} m</text>')
    ly = 66
    for color, txt in [("#ff5d5d", f"solid  Cd 1.2  ->  {F(0.6,CD_SOLID):.0f}/{F(0.9,CD_SOLID):.0f}/{F(1.2,CD_SOLID):.0f} N"),
                       ("#4fd1ff", f"mesh   Cd 0.5"),
                       ("#7CE38B", f"stowed aperture-up (11.8 %)")]:
        s.append(f'<rect x="{PAD+252}" y="{ly-9}" width="14" height="4" fill="{color}"/>')
        s.append(f'<text x="{PAD+272}" y="{ly-4}" fill="#c8ccd6" font-size="11" font-family="sans-serif">{txt}</text>')
        ly += 17
    out += s

    # ---- Panel B: required ground gain vs diameter ----
    xmax2, ymin2, ymax2 = 1.5, -22.0, 40.0
    s, X, Y = panel(PAD + 500, 50, 400, 300, xmax2, ymax2, "dish diameter D [m]",
                    "gain [dBi]", "B. 2.4 GHz uplink: gain REQUIRED (negative!)",
                    ymin=ymin2)
    # zero line and the two required-gain thresholds (negative -> no dish needed)
    s.append(f'<line x1="{PAD+500}" y1="{Y(0):.1f}" x2="{PAD+900}" y2="{Y(0):.1f}" stroke="#5a6070" stroke-width="1.2"/>')
    for req, col, lbl in [(-17.4, "#ffd166", "req G = -17.4 dBi @ 300 km"),
                          (-10.7, "#f6a6ff", "req G = -10.7 dBi @ 650 km")]:
        s.append(f'<line x1="{PAD+500}" y1="{Y(req):.1f}" x2="{PAD+900}" y2="{Y(req):.1f}" stroke="{col}" stroke-width="1.8" stroke-dasharray="6 4"/>')
        s.append(f'<text x="{PAD+506}" y="{Y(req)-6:.1f}" fill="{col}" font-size="11" font-family="sans-serif">{lbl}</text>')
    pts = []
    for i in range(151):
        D = max(xmax2 * i / 150.0, 0.02)
        pts.append(f"{X(D):.1f},{Y(gain(D)):.1f}")
    s.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#ffa94d" stroke-width="2.8"/>')
    for D, dy in [(0.6, -10), (1.2, -10)]:
        s.append(f'<circle cx="{X(D):.1f}" cy="{Y(gain(D)):.1f}" r="5" fill="#fff"/>')
        s.append(f'<text x="{X(D):.1f}" y="{Y(gain(D))+dy:.1f}" fill="#ffe0b3" font-size="11" text-anchor="middle" font-family="sans-serif">{D} m: {gain(D):.1f} dBi</text>')
    s.append(f'<text x="{PAD+506}" y="{Y(0)+16:.1f}" fill="#5a6070" font-size="10" font-family="sans-serif">0 dBi = an omni already closes the link</text>')
    s.append(f'<text x="{PAD+506}" y="{Y(36):.1f}" fill="#ffa94d" font-size="12" font-family="sans-serif">dish gain (dBi), 2.4 GHz, eta 0.55</text>')
    s.append(f'<text x="{PAD+506}" y="{Y(31):.1f}" fill="#9aa1b2" font-size="10" font-family="sans-serif">requirements assume balloon LNA, 10 dBi balloon ant, 20 dBm EIRP cap</text>')
    out += s

    out.append('</svg>')
    path = "docs/analysis/figures/positioner-rightsizing.svg"
    with open(path, "w") as f:
        f.write("\n".join(out))
    print("wrote", path)


if __name__ == "__main__":
    main()
