#!/usr/bin/env python3
"""Render the base-station backhaul topology options for visual consultation.

Three panels, one per architecture:
  A. Operator's proposal: station with cell reception relays internet to a
     station without -> balloon as a WAN relay.
  B. ADR-071 as written: each station is an internet gateway; users reach the
     internet THROUGH the balloon (balloon is a bent pipe for user traffic).
  C. Hybrid: independent cellular backhaul per station + balloon as the
     user-facing bent pipe.

Deterministic, no network. Output: PNG via matplotlib.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

INK = "#1a1a1a"
CELL = "#228B22"      # deployed / good reception
NOCELL = "#C71585"    # no reception
BALLOON = "#1f6feb"
WARN = "#b8860b"


def box(ax, x, y, w, h, label, color, sub=None, fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                                linewidth=1.6, edgecolor=color,
                                facecolor=color + "22"))
    ax.text(x + w / 2, y + h - 0.16, label, ha="center", va="top",
            fontsize=fs, color=INK, weight="bold")
    if sub:
        ax.text(x + w / 2, y + h - 0.42, sub, ha="center", va="top",
                fontsize=fs - 1.4, color=INK)


def arrow(ax, p, q, color=INK, style="-|>", ls="-", lw=1.6, rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, color=color,
                                 linewidth=lw, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}",
                                 mutation_scale=13, shrinkA=2, shrinkB=2))


def panel(ax, title, sub):
    ax.set_xlim(0, 10); ax.set_ylim(0, 6.4); ax.axis("off")
    ax.text(0.05, 1.02, title, fontsize=11.5, weight="bold", color=INK,
            transform=ax.transAxes, va="bottom")
    ax.text(0.05, 0.965, sub, fontsize=8.4, color=INK,
            transform=ax.transAxes, va="bottom")


fig, axes = plt.subplots(3, 1, figsize=(10.6, 15.0))

# ---------------- A: operator's proposal ----------------
ax = axes[0]
panel(ax, "A. Operator's proposal: balloon as a WAN relay",
      "Station WITH cell reception shares its internet to a station WITHOUT, over the balloon link.")
box(ax, 0.3, 0.5, 2.5, 1.5, "Station A", CELL, "cell: GOOD\n+ LTE modem")
box(ax, 7.2, 0.5, 2.5, 1.5, "Station B", NOCELL, "cell: NONE\nSSH/FIPS wanted")
box(ax, 3.6, 4.0, 2.8, 1.4, "BALLOON", BALLOON, "bent pipe (433 / 2.4 GHz)")
# balloon to each station
arrow(ax, (4.6, 4.0), (1.6, 2.05), BALLOON, rad=0.18)
arrow(ax, (5.4, 4.0), (8.4, 2.05), BALLOON, rad=-0.18)
ax.text(5.0, 3.15, "relayed WAN traffic", fontsize=8, color=BALLOON, ha="center")
# A to internet
arrow(ax, (1.5, 2.05), (1.5, 3.3), CELL)
ax.text(1.62, 2.55, "internet", fontsize=8, color=CELL)
ax.text(0.4, 1.15, "NOTE: does the balloon carry a THIRD PARTY's internet?", fontsize=8,
        color=WARN, style="italic")

# ---------------- B: ADR-071 as written ----------------
ax = axes[1]
panel(ax, "B. ADR-071 as written: each station is an internet gateway",
      "Users reach the internet THROUGH the balloon. Balloon = bent pipe for USER traffic.")
box(ax, 0.3, 0.5, 2.5, 1.5, "Station A", CELL, "user access\n(433 rx / 2.4 tx)")
box(ax, 7.2, 0.5, 2.5, 1.5, "Station B", CELL, "user access")
box(ax, 3.6, 4.0, 2.8, 1.4, "BALLOON", BALLOON, "bent pipe (433 / 2.4 GHz)")
arrow(ax, (4.6, 4.0), (1.6, 2.05), BALLOON, rad=0.18)
arrow(ax, (5.4, 4.0), (8.4, 2.05), BALLOON, rad=-0.18)
# each station has its OWN internet
arrow(ax, (1.5, 2.05), (1.5, 3.3), CELL)
ax.text(1.62, 2.55, "own internet", fontsize=7.6, color=CELL)
arrow(ax, (8.4, 2.05), (8.4, 3.3), CELL)
ax.text(8.5, 2.55, "own internet", fontsize=7.6, color=CELL)
ax.text(0.4, 1.15, "ADR-071 caveat: this is a LOCAL licence-exempt ISM service.", fontsize=8,
        color=WARN, style="italic")

# ---------------- C: hybrid ----------------
ax = axes[2]
panel(ax, "C. Hybrid: independent backhaul + balloon for user traffic",
      "Each station gets its OWN cellular backhaul. The balloon stays the user-facing bent pipe.")
box(ax, 0.3, 0.5, 2.5, 1.5, "Station A", CELL, "own LTE + SSH/FIPS")
box(ax, 7.2, 0.5, 2.5, 1.5, "Station B", CELL, "own LTE + SSH/FIPS")
box(ax, 3.6, 4.0, 2.8, 1.4, "BALLOON", BALLOON, "bent pipe (433 / 2.4 GHz)")
arrow(ax, (4.6, 4.0), (1.6, 2.05), BALLOON, rad=0.18)
arrow(ax, (5.4, 4.0), (8.4, 2.05), BALLOON, rad=-0.18)
arrow(ax, (1.5, 2.05), (1.5, 3.3), CELL)
arrow(ax, (8.4, 2.05), (8.4, 3.3), CELL)
ax.text(5.0, 3.15, "user traffic only", fontsize=8, color=BALLOON, ha="center")
ax.text(0.4, 1.15, "No dependence on A having reception; no third-party relay question.", fontsize=8,
        color=CELL, style="italic")

fig.suptitle("Base-station backhaul: three topologies (telco gap analysis)",
             fontsize=13.5, weight="bold", color=INK, y=0.995)
fig.tight_layout(rect=[0, 0, 1, 0.985])
out = "/home/c08r4d0r/TELCO-TOPOLOGY-OPTIONS.png"
fig.savefig(out, dpi=150, facecolor="white")
print("wrote", out)
