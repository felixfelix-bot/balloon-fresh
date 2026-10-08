#!/usr/bin/env python3
"""Render the gain-per-dollar-cliff figures (PNG) for the doc and the consultant.

Reproduce:  python3 docs/analysis/render_gain_per_dollar_cliff_figures.py
Outputs:    docs/analysis/assets/gain-per-dollar/*.png
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gain_per_dollar_cliff_model as M   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "assets", "gain-per-dollar")
os.makedirs(OUT, exist_ok=True)

ROT_COLORS = {"yaesu": "#2e7d32", "spx": "#f9a825", "bigras": "#c62828"}
BG = "#101418"
FG = "#e8eef2"
GRID = "#2b343c"


def style(ax, title):
    ax.set_facecolor(BG)
    ax.set_title(title, color=FG, fontsize=11, pad=8)
    ax.tick_params(colors=FG, labelsize=8)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.grid(True, color=GRID, lw=0.5, alpha=0.7)
    ax.xaxis.label.set_color(FG)
    ax.yaxis.label.set_color(FG)


def dish_rows():
    rows = []
    for D in [0.6, 0.9, 0.93, 1.0, 1.2, 1.5, 1.9, 2.2, 2.4, 2.6, 3.0]:
        g = M.dish_gain_dBi(D, M.LAM_433)
        refl = M.reflector_price_est(D)[0]
        drag = M.area(D) * M.CD_SOLID
        nm, rot = M.rotator_price_for(drag)
        mast = M.mast_foundation_est(D)
        rows.append((D, g, drag, rot, refl + rot + mast))
    return rows


# ---------------------------------------------------------------- fig 1
def fig_cliff():
    rows = dish_rows()
    G = [r[1] for r in rows]
    T = [r[4] for r in rows]
    eur_db = [r[4] / (r[1] - G[0]) if r[1] > G[0] else float("nan") for r in rows]
    marg = []
    for i in range(1, len(rows)):
        dg = rows[i][1] - rows[i - 1][1]
        dc = rows[i][4] - rows[i - 1][4]
        marg.append(dc / dg)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2), facecolor=BG)

    # rotator-class bands
    for x0, x1, c, lab in [
            (min(G), M.dish_gain_dBi(1.0, M.LAM_433), ROT_COLORS["yaesu"],
             "Yaesu class  (EUR 359, <=1.0 m2 tower / 0.5 m2 mast)"),
            (M.dish_gain_dBi(1.0, M.LAM_433), M.dish_gain_dBi(1.53, M.LAM_433),
             ROT_COLORS["spx"], "SPX/SPID  (EUR 1132-1260)"),
            (M.dish_gain_dBi(1.53, M.LAM_433), max(G) + 0.2, ROT_COLORS["bigras"],
             "SPID BIG-RAS  (EUR 1775)")]:
        ax1.axvspan(x0, x1, color=c, alpha=0.13)
        ax2.axvspan(x0, x1, color=c, alpha=0.13)

    ax1.plot(G, eur_db, "-o", color="#4fc3f7", lw=2, ms=5)
    ax1.set_xlabel("433 MHz gain (dBi)")
    ax1.set_ylabel("whole-station EUR per dB (vs 0.6 m rung)")
    style(ax1, "The cliff: whole-station EUR/dB vs 433 gain (dish path)")
    ax1.set_yscale("log")
    for i, r in enumerate(rows):
        if r[0] in (0.6, 1.0, 1.2, 2.6, 3.0):
            ax1.annotate("%.1f m" % r[0], (G[i], eur_db[i]),
                         textcoords="offset points", xytext=(4, 8),
                         color=FG, fontsize=8)

    # Yagi-array frontier points on the right panel
    base = 530.0
    harness = {1: 0.0, 2: 55.0, 4: 130.0}
    for name, (gdbi, boom, price, url) in M.YAGIS.items():
        g = M.yagi_geometry(boom_m=boom)
        for nb in (2, 4):
            gain = gdbi + (M.db(nb) - 0.5)
            drag = nb * g["drag_m2"] + M.array_frame_area(nb, boom)
            tot = base + nb * price + harness[nb] + 70.0
            ax2.plot([gain], [tot / (gain - G[0])], "D", color="#ffb300", ms=6)
    bars_x = [round(((rows[i][1] + rows[i - 1][1]) / 2), 2) for i in range(1, len(rows))]
    cols = [ROT_COLORS["bigras"] if m > 300 else "#4fc3f7" for m in marg]
    ax2.bar(bars_x, marg, width=0.35, color=cols, alpha=0.85)
    ax2.set_xlabel("433 MHz gain (dBi)")
    ax2.set_ylabel("marginal EUR per dB (bar)   |   array station EUR/dB (diamond)")
    style(ax2, "Marginal EUR/dB: flat until the rotator steps (red = post-cliff)")
    ax2.set_yscale("log")
    handles = [Patch(color=ROT_COLORS["yaesu"], alpha=.4, label="Yaesu class (EUR 359)"),
               Patch(color=ROT_COLORS["spx"], alpha=.4, label="SPX/SPID (EUR 1132-1260)"),
               Patch(color=ROT_COLORS["bigras"], alpha=.4, label="SPID BIG-RAS (EUR 1775)"),
               plt.Line2D([], [], marker="D", ls="", color="#ffb300", label="Yagi array station")]
    ax2.legend(handles=handles, fontsize=7, facecolor="#1a2026", edgecolor=GRID,
               labelcolor=FG, loc="upper left")
    fig.suptitle("Balloon ground station: the cost cliff in gain-per-dollar (433 MHz dish) "
                 "— model output", color=FG, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    p = os.path.join(OUT, "fig1-cost-cliff.png")
    fig.savefig(p, dpi=140, facecolor=BG)
    plt.close(fig)
    return p


# ---------------------------------------------------------------- fig 2
def fig_yagi_vs_dish():
    fig, ax = plt.subplots(figsize=(12, 6.4), facecolor=BG)
    style(ax, "Yagi array vs the 2.6 m dish: 433 gain against WIND DRAG AREA\n"
              "(down-and-right is good: more gain, less wind load)")
    ax.set_xlabel("433 MHz gain (dBi)")
    ax.set_ylabel("effective drag area  Cd*A (m$^2$)")
    ax.set_yscale("log")

    # requirement lines
    for lvl, lab, c in [(18.9, "FLRC 2.6 Mbps @+22 dBm: +18.9 dBi", "#ef5350"),
                        (14.4, "FLRC 1.04 Mbps @+22 dBm: +14.4 dBi", "#ffa726"),
                        (12.4, "FLRC 650 kbps @+22 dBm: +12.4 dBi", "#66bb6a")]:
        ax.axvline(lvl, color=c, ls="--", lw=1.2, alpha=0.8)
        ax.text(lvl + 0.1, 9, lab, rotation=90, color=c, fontsize=8, va="top")
    # rotator class boundaries on drag area
    for lim, lab, c in [(0.50, "Yaesu MAST 0.50 m2", "#2e7d32"),
                        (1.00, "Yaesu TOWER 1.00 m2", "#7cb342"),
                        (2.65, "SPID BIG-RAS class ~2.65 m2", "#c62828")]:
        ax.axhline(lim, color=c, ls=":", lw=1.2, alpha=0.8)
        ax.text(9.2, lim * 1.05, lab, color=c, fontsize=8)

    # dish points
    dx, dy, dl = [], [], []
    for D in [1.2, 1.9, 2.4, 2.6, 3.0]:
        dx.append(M.dish_gain_dBi(D, M.LAM_433))
        dy.append(M.area(D) * M.CD_SOLID)
        dl.append("%.1f m solid" % D)
        dx.append(M.dish_gain_dBi(D, M.LAM_433))
        dy.append(M.area(D) * M.CD_MESH)
        dl.append("%.1f m mesh" % D)
    ax.scatter(dx, dy, s=70, c="#ef5350", marker="s", label="dish (solid=upper, mesh=lower)", zorder=4)
    for x, y, t in zip(dx, dy, dl):
        ax.annotate(t, (x, y), textcoords="offset points", xytext=(5, 4), color=FG, fontsize=7)

    # Yagi array points
    ax_x, ax_y, ax_l = [], [], []
    for name, (gdbi, boom, price, url) in M.YAGIS.items():
        g = M.yagi_geometry(boom_m=boom)
        for nb in (1, 2, 4):
            gain = gdbi + (M.db(nb) - (0.5 if nb == 2 else 0.8 if nb == 4 else 0.0))
            drag = nb * g["drag_m2"] + M.array_frame_area(nb, boom)
            ax_x.append(gain)
            ax_y.append(drag)
            if nb in (2, 4) and name in ("Diamond A-430S15R", "FlexaYagi FX 7044", "FlexaYagi FX 7073"):
                cost = 530.0 + nb * price + {1: 0.0, 2: 55.0, 4: 130.0}[nb] + 70.0
                ax_l.append((gain, drag, "%dx %s\nEUR %.0f" %
                             (nb, name.split()[-1], cost)))
    ax.scatter(ax_x, ax_y, s=45, c="#ffb300", marker="o", label="Yagi / Yagi array", zorder=5)
    for x, y, t in ax_l:
        ax.annotate(t, (x, y), textcoords="offset points", xytext=(6, 6),
                    color="#ffe082", fontsize=7)
    ax.legend(fontsize=8, facecolor="#1a2026", edgecolor=GRID, labelcolor=FG, loc="lower right")
    ax.set_xlim(9, 22)
    fig.tight_layout()
    p = os.path.join(OUT, "fig2-yagi-vs-dish.png")
    fig.savefig(p, dpi=140, facecolor=BG)
    plt.close(fig)
    return p


# ---------------------------------------------------------------- fig 3
def fig_frontier():
    rows = dish_rows()
    base = 530.0
    harness = {1: 0.0, 2: 55.0, 4: 130.0}
    pts = []
    for name, (gdbi, boom, price, url) in M.YAGIS.items():
        g = M.yagi_geometry(boom_m=boom)
        for nb in (1, 2, 4):
            gain = gdbi + (M.db(nb) - (0.5 if nb == 2 else 0.8 if nb == 4 else 0.0))
            drag = nb * g["drag_m2"] + M.array_frame_area(nb, boom)
            tot = base + nb * price + harness[nb] + (0.0 if nb == 1 else 70.0)
            pts.append(("yagi", "%dx %s" % (nb, name), gain, drag, tot))
    for D, g, drag, rot, tot in rows:
        if D >= 1.0:
            pts.append(("dish", "%.1f m" % D, g, drag, base + tot))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.6), facecolor=BG)
    for kind, col, mk in [("yagi", "#ffb300", "o"), ("dish", "#ef5350", "s")]:
        xs = [p[2] for p in pts if p[0] == kind]
        ys = [p[4] for p in pts if p[0] == kind]
        ax1.scatter(xs, ys, c=col, marker=mk, s=55, label=("Yagi array" if kind == "yagi" else "dish"),
                    zorder=4)
    style(ax1, "Station cost vs 433 gain (EUR, 433 path only + shared body)")
    ax1.set_xlabel("433 MHz gain (dBi)")
    ax1.set_ylabel("station cost (EUR)")
    ax1.legend(fontsize=8, facecolor="#1a2026", edgecolor=GRID, labelcolor=FG, loc="upper left")
    for p in pts:
        if p[1] in ("1 x Diamond A-430S10R", "4 x Diamond A-430S15R", "2.6 m", "3.0 m"):
            ax1.annotate(p[1], (p[2], p[4]), textcoords="offset points", xytext=(5, -10),
                         color=FG, fontsize=7)

    # right: drag area vs cost
    for kind, col, mk in [("yagi", "#ffb300", "o"), ("dish", "#ef5350", "s")]:
        xs = [p[3] for p in pts if p[0] == kind]
        ys = [p[4] for p in pts if p[0] == kind]
        ax2.scatter(xs, ys, c=col, marker=mk, s=55, zorder=4)
    ax2.axvline(0.50, color="#2e7d32", ls=":", lw=1.2)
    ax2.axvline(1.00, color="#7cb342", ls=":", lw=1.2)
    ax2.axvline(2.65, color="#c62828", ls=":", lw=1.2)
    ax2.text(0.52, 300, "Yaesu mast\n0.50 m2", color="#2e7d32", fontsize=7)
    ax2.text(1.02, 300, "Yaesu tower\n1.00 m2", color="#7cb342", fontsize=7)
    ax2.text(2.7, 300, "BIG-RAS\nclass", color="#c62828", fontsize=7)
    style(ax2, "Station cost vs WIND drag area — the cliff is where the rotator class steps")
    ax2.set_xlabel("effective drag area  Cd*A (m$^2$)")
    ax2.set_ylabel("station cost (EUR)")
    ax2.set_yscale("log")
    fig.suptitle("TWO decisions, one curve: gain and wind load against cost", color=FG, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    p = os.path.join(OUT, "fig3-frontier.png")
    fig.savefig(p, dpi=140, facecolor=BG)
    plt.close(fig)
    return p


if __name__ == "__main__":
    for f in (fig_cliff, fig_yagi_vs_dish, fig_frontier):
        print("wrote", f())
