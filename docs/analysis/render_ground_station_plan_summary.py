#!/usr/bin/env python3
"""Render the ground-station PLAN SUMMARY figure for the independent consultant.

One page, four panels, every number taken from the committed analyses (and the ADR set
071-082) — no new arithmetic is introduced here.

    /usr/bin/python3 docs/analysis/render_ground_station_plan_summary.py

The repo's default `python3` has no matplotlib; use /usr/bin/python3.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

OUT = "docs/analysis/assets/ground-station-plan-summary.png"

fig = plt.figure(figsize=(16.5, 11.0), dpi=110)
fig.suptitle(
    "Ground-station PLAN SUMMARY (balloon-fresh) — locked decisions consolidated as ADR-071..082",
    fontsize=15,
    fontweight="bold",
    y=0.985,
)

# ---------------------------------------------------------------- panel 1: architecture
ax = fig.add_axes([0.03, 0.55, 0.45, 0.38])
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")
ax.set_title("1. Architecture: full-duplex INTERNET GATEWAY via the balloon as a bent pipe", fontsize=11, loc="left")


def box(x, y, w, h, text, fc="#eef3fb", ec="#2b4a7d", fs=9, bold=False):
    ax.add_patch(
        mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.08", fc=fc, ec=ec, lw=1.4
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", wrap=True)


box(0.2, 7.4, 2.5, 1.4, "Ground users\n(WiFi / captive portal)", fc="#f7f7f7")
box(3.3, 7.0, 3.3, 2.2, "GROUND STATION\nfull-duplex\nInternet gateway\n(one az/el positioner,\ntwo boresighted antennas)", fc="#dff0e0", ec="#2f6b34", bold=True)
box(7.3, 7.4, 2.4, 1.4, "Internet", fc="#f7f7f7")
box(2.6, 3.6, 4.7, 2.4, "BALLOON — bent pipe\nF33 @433 TX (HIGH-POWER variant, amateur band)\n  − or −\nbare LR2021 @433 TX (LOW-POWER variant, licence-exempt)\nLR2021 @2.4 GHz RX", fc="#fdeee0", ec="#a05a12")

ax.annotate("", xy=(7.3, 4.8), xytext=(3.3, 4.8), arrowprops=dict(arrowstyle="->", lw=2, color="#b03030"))
ax.text(5.3, 5.05, "433 MHz DOWNLINK  ↑  balloon→ground\nFLRC at MAX throughput (LoRa rejected)\nRX side = the binding direction", ha="center", fontsize=8.5, color="#b03030")
ax.annotate("", xy=(3.3, 3.9), xytext=(7.3, 3.9), arrowprops=dict(arrowstyle="->", lw=2, color="#1a6fa8"))
ax.text(5.3, 3.35, "2.45 GHz UPLINK  ↓  ground→balloon\nband-split duplex: two band antennas, NO circulator\n(no half-duplex T/R relay — full duplex required)", ha="center", fontsize=8.5, color="#1a6fa8")
ax.text(5.0, 2.85, "433 RX / 2.45 TX = 5.65x apart  ->  duplex by BAND SEPARATION\n(one narrowband circulator cannot route two bands)", ha="center", fontsize=8, style="italic")
ax.text(5.0, 2.1, "2.4 GHz uplink: EIRP/PSD-capped -> ATTENUATE, don't amplify (DSA, not PA)", ha="center", fontsize=8, style="italic")
ax.text(5.0, 1.6, "Ground station uses: 433 BPF before LNA -> owned TQP3M9037 LNA (masthead)", ha="center", fontsize=8)
ax.text(5.0, 1.0, "433 ground antenna: option B = Diamond A-430S15R 14.8 dBi Yagi on DIY printed tracker P2", ha="center", fontsize=8)
ax.text(5.0, 0.4, "433 dish only if low-power FLRC-max is required; any 433 dish >=2 m MUST be coarse mesh (lambda/10 = 69 mm)", ha="center", fontsize=8)

# ---------------------------------------------------------------- panel 2: tier ladder
ax2 = fig.add_axes([0.53, 0.55, 0.45, 0.38])
tiers = [
    ("Tier 0a\n2 omnis, no motors", 90, 245, "LoRa only; fixed mast"),
    ("Tier 0b\nhand-aimed Yagi", 144, 304, "F33 FLRC 2.6 Mbps to 650 km\n(human points a ~40 deg beam)"),
    ("Tier A (dish removed)\n433 Yagi + 8 dBi panel", 546, 685, "auto pointing; LoRa-class uplink"),
    ("OPTION B (recommended)\nA-430S15R + DIY tracker P2", 700, 770, "150 km @2.6 Mbps low-power\n532 km WITH the F33"),
    ("Tier B / dish tiers\n4-bay array .. dish build", 2166, 10100, "pre-cliff array (2166)\nor post-cliff dish (5900-10100)"),
]
for i, (name, lo, hi, cap) in enumerate(tiers):
    y = i
    ax2.barh(y, hi - lo, left=lo, height=0.5, color="#3b6ea5", alpha=0.85)
    ax2.text(hi * 1.12, y, f"EUR {lo}-{hi}", va="center", fontsize=8.5)
    ax2.text(9, y + 0.33, cap, va="bottom", fontsize=7.4, color="#333")
ax2.set_yticks(range(len(tiers)))
ax2.set_yticklabels([t[0] for t in tiers], fontsize=8)
ax2.set_xscale("log")
ax2.set_xlim(60, 60000)
ax2.set_xlabel("indicative whole-station cost (EUR, log scale)", fontsize=9)
ax2.set_title("2. Tier ladder (cost NAMES its tier) — above ~8 dBi the 2.4 GHz ground gain is INERT", fontsize=11, loc="left")
ax2.grid(axis="x", alpha=0.25)
ax2.axvspan(60, 800, color="#2f6b34", alpha=0.06)
ax2.text(62, len(tiers) - 0.35, "pre-cliff / accessible band", fontsize=7.5, color="#2f6b34")

# ---------------------------------------------------------------- panel 3: F33 multiplier
ax3 = fig.add_axes([0.03, 0.06, 0.45, 0.38])
labels = ["low-power board\n(+22 dBm chip)", "F33 on balloon\n(+33 dBm, ~USD 8)"]
ranges = [150, 532]
bars = ax3.bar(labels, ranges, color=["#8a8f98", "#1f7a3d"], width=0.5)
for b, r in zip(bars, ranges):
    ax3.text(b.get_x() + b.get_width() / 2, r + 12, f"{r} km @ 2.6 Mbps", ha="center", fontsize=9, fontweight="bold")
ax3.set_ylabel("range at 2.6 Mbps (option B ground station)", fontsize=9)
ax3.set_title("3. The F33 is the cheapest dB: ~0.40 USD/dB, and 3.55x range on EVERY ground candidate", fontsize=11, loc="left")
ax3.text(0.5, 300, "ledger (money per NEEDED dB, direction-aware):\n"
                   "F33 0.40 USD/dB  <<  LNA 26.4 EUR/dB  <  2-bay array 76.1  <  4-bay 93.7  <  dish+tracker 346-809  <  2.4 GHz PA = INF (0 needed dB)",
         ha="center", fontsize=7.4, color="#333")
ax3.text(0.5, 120, "dish diameter collapse at 650 km FLRC-max:\n7.38 m (+13 dBm)  ->  2.62 m (+22 dBm)  ->  0.74 m (+33 dBm F33)",
         ha="center", fontsize=7.6, color="#7a1f1f")
ax3.set_ylim(0, 620)

# ---------------------------------------------------------------- panel 4: cliff
ax4 = fig.add_axes([0.53, 0.06, 0.45, 0.38])
runks = ["<=1.0 m\n(rotator EUR 359)", "1.00->1.20 m\n(rotator -> EUR 1132)", ">1.9 m mesh\n(BIG-RAS EUR 1775)"]
marg = [68, 592, 598]
ax4.bar(runks, marg, color=["#2f6b34", "#b03030", "#a05a12"], width=0.55)
for i, m in enumerate(marg):
    ax4.text(i, m + 15, f"{m} EUR/dB", ha="center", fontsize=9, fontweight="bold")
ax4.set_ylabel("marginal whole-station cost of the next dB", fontsize=9)
ax4.set_title("4. The CLIFF is the ROTATOR CLASS (~1.0 m2 wind area), not the reflector size: 6.9x at 1.0->1.2 m", fontsize=11, loc="left")
ax4.set_ylim(0, 700)
ax4.text(0.5, 350, "mesh (lambda/10 = 69 mm at 433 MHz) moves the cliff:\n"
                   "solid 2.40 m = 1.88x BIG-RAS rating (infeasible)\n"
                   "same dish as 6 mm mesh = 0.50x (fine)\n"
                   "mesh edge: 2.62 m = 0.65x ok | 3.00 m = 0.97x no margin | 3.49 m = 1.53x over",
         ha="center", fontsize=7.6, color="#333")

fig.savefig(OUT, bbox_inches="tight", facecolor="white")
print("wrote", OUT)
