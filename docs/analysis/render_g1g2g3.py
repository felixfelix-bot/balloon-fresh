#!/usr/bin/env python3
"""Render the G1 / G2 / G3 service model for the base station.

Operator asked for all three modes. They are three DIFFERENT services with
different legal faces and different hardware needs -- this figure makes that
visible. Rendered deterministically (no network).

  G1 Access Gateway    users reach the internet THROUGH the balloon  (ADR-071)
  G2 Backhaul Relay    station A's WAN is shared to station B over the balloon
  G3 Egress Election   the routing metric that picks WHICH station is the WAN
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

INK = "#1a1a1a"
OWN = "#C71585"     # our own device / traffic  (Felix's CHX deploy colour)
GOOD = "#228B22"    # has WAN / deployed
WAN = "#1f6feb"
NOTE = "#b8860b"


def box(ax, x, y, w, h, label, color, sub=None, fs=9.0, lw=1.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                                linewidth=lw, edgecolor=color, facecolor=color + "22"))
    ax.text(x + w / 2, y + h - 0.14, label, ha="center", va="top",
            fontsize=fs, color=INK, weight="bold")
    if sub:
        ax.text(x + w / 2, y + h - 0.40, sub, ha="center", va="top",
                fontsize=fs - 1.5, color=INK)


def arrow(ax, p, q, color=INK, ls="-", lw=1.7, rad=0.0, style="-|>"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, color=color, linewidth=lw,
                                 linestyle=ls, connectionstyle=f"arc3,rad={rad}",
                                 mutation_scale=13, shrinkA=2, shrinkB=2))


def panel(ax, title, sub):
    ax.set_xlim(0, 10); ax.set_ylim(0, 6.6); ax.axis("off")
    ax.text(0.05, 1.02, title, fontsize=11, weight="bold", color=INK,
            transform=ax.transAxes, va="bottom")
    ax.text(0.05, 0.962, sub, fontsize=8.2, color=INK,
            transform=ax.transAxes, va="bottom")


fig, axes = plt.subplots(3, 1, figsize=(10.8, 15.6))

# ---- G1 ----
ax = axes[0]
panel(ax, "G1 — ACCESS GATEWAY  (ADR-071 as written)",
      "Users reach the internet THROUGH the balloon. Each station has its own uplink. "
      "Legal load: ISM 10% duty ceiling + TKG service question.")
box(ax, 0.3, 0.55, 2.6, 1.5, "Station A", GOOD, "own uplink\n433 rx / 2.4 tx")
box(ax, 7.1, 0.55, 2.6, 1.5, "Station B", GOOD, "own uplink\n433 rx / 2.4 tx")
box(ax, 3.6, 4.0, 2.8, 1.4, "BALLOON", WAN, "bent pipe\n433 / 2.4 GHz")
arrow(ax, (4.6, 4.0), (1.7, 2.10), WAN, rad=0.20)
arrow(ax, (5.4, 4.0), (8.4, 2.10), WAN, rad=-0.20)
arrow(ax, (1.6, 2.05), (1.6, 3.35), GOOD); ax.text(1.72, 2.6, "own uplink", fontsize=7.4, color=GOOD)
arrow(ax, (8.4, 2.05), (8.4, 3.35), GOOD); ax.text(8.5, 2.6, "own uplink", fontsize=7.4, color=GOOD)
ax.text(5.0, 3.10, "USER traffic", fontsize=8.4, color=WAN, ha="center", weight="bold")
ax.text(0.35, 1.20, "every station needs its own WAN  ·  users are third parties", fontsize=8, color=NOTE, style="italic")

# ---- G2 ----
ax = axes[1]
panel(ax, "G2 — BACKHAUL RELAY  (station-to-station WAN sharing)",
      "Our device relays OUR OWN traffic. Think: phone hotspot. Station A is the WAN anchor; "
      "the balloon carries it to station B.")
box(ax, 0.3, 0.55, 2.6, 1.5, "Station A", GOOD, "ANCHOR\ncellular WAN")
box(ax, 7.1, 0.55, 2.6, 1.5, "Station B", OWN, "LEAF\nno signal")
box(ax, 3.6, 4.0, 2.8, 1.4, "BALLOON", WAN, "bent pipe\n433 / 2.4 GHz")
arrow(ax, (4.6, 4.0), (1.7, 2.10), WAN, rad=0.20)
arrow(ax, (5.4, 4.0), (8.4, 2.10), WAN, rad=-0.20)
arrow(ax, (1.6, 2.05), (1.6, 3.35), GOOD); ax.text(1.72, 2.6, "cellular", fontsize=7.4, color=GOOD)
ax.text(5.0, 3.10, "OUR traffic only", fontsize=8.4, color=OWN, ha="center", weight="bold")
box(ax, 3.3, 1.55, 3.4, 1.0, "FIPS L6 Noise XK", INK,
    "relay station never sees plaintext", fs=8.4)
ax.text(0.35, 1.20, "only the ANCHOR needs a SIM  ·  no third parties  ·  cheap to build first", fontsize=8, color=GOOD, style="italic")

# ---- G3 ----
ax = axes[2]
panel(ax, "G3 — EGRESS ELECTION  (the routing metric — not hardware)",
      "Decides BY DESIGN which station anchors the WAN, not by accident. "
      "ADR-012 records no cost metric: radio and cellular hops are not comparable today.")
box(ax, 0.3, 0.55, 2.6, 1.5, "Station A", GOOD, "cell: GOOD\ncost = 1")
box(ax, 3.6, 0.55, 2.6, 1.5, "Station B", NOTE, "cell: WEAK\ncost = 5")
box(ax, 7.1, 0.55, 2.6, 1.5, "Station C", OWN, "cell: NONE\ncost = inf")
box(ax, 3.6, 4.0, 2.8, 1.4, "BALLOON", WAN, "bent pipe\n433 / 2.4 GHz")
for (px, py), rad in (((1.7, 2.10), 0.20), ((5.0, 2.10), 0.0), ((8.4, 2.10), -0.20)):
    arrow(ax, (5.0, 4.0), (px, py), WAN, rad=rad, ls="--", lw=1.4)
arrow(ax, (1.6, 2.05), (1.6, 3.35), GOOD)
ax.text(5.0, 3.12, "election picks the cheapest egress", fontsize=8.4, color=WAN, ha="center", weight="bold")
ax.text(0.35, 1.20, "policy, not hardware  ·  step 1 of building G2 for real", fontsize=8, color=NOTE, style="italic")

fig.suptitle("Base-station services: G1 access gateway · G2 backhaul relay · G3 egress election",
             fontsize=13, weight="bold", color=INK, y=0.996)
fig.tight_layout(rect=[0, 0, 1, 0.988])
out = "/home/c08r4d0r/TELCO-G1-G2-G3-SERVICES.png"
fig.savefig(out, dpi=150, facecolor="white")
print("wrote", out)
