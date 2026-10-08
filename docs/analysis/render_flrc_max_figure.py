#!/usr/bin/env python3
"""Figure for docs/analysis/ground-station-flrc-max-throughput.md.

Renders docs/analysis/assets/flrc-max-trade.png: two panels
  (a) required ground gain vs P_tx for FLRC 2.6 Mbps / 650 kbps, with the dish
      diameter annotated on each bar and the 12 dBi "Yagi" and 20 dBi reference lines;
  (b) mesh-vs-solid wind moment at 120 km/h against the SPID BIG-RAS holding torque.

Run: python3 docs/analysis/render_flrc_max_figure.py
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

C = 299_792_458.0
F = 433.05e6
LAM = C / F
ETA = 0.55
FSPL = 141.4
RHO = 1.225
CD = 1.38                 # derived from the Gibertini OP100SE vendor figure
BRAKE = 2712.0            # N.m  SPID BIG-RAS holding/brake torque (vendor spec sheet)
SIG_6MM = 1 - (6 / 7.0) ** 2      # 0.265

DBM = [13, 22, 33]
SENS = {"2.6 Mbps": -100.5, "650 kbps": -107.0}
COLORS = {"2.6 Mbps": "#c0392b", "650 kbps": "#2471a3"}

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 6.6))

# ---- panel (a) -------------------------------------------------------------
w = 0.34
xs = range(len(DBM))
for i, (rate, s) in enumerate(SENS.items()):
    vals, labels = [], []
    for p in DBM:
        g = s + FSPL - p
        d = (LAM / math.pi) * math.sqrt(10 ** (g / 10.0) / ETA)
        vals.append(g)
        labels.append(f"{g:+.1f} dBi\n\u2300 {d:.2f} m")
    pos = [x + (i - 0.5) * w for x in xs]
    b = ax1.bar(pos, vals, w, label=f"FLRC {rate}", color=COLORS[rate], alpha=0.9)
    ax1.bar_label(b, labels=labels, fontsize=8.5, padding=2)
ax1.axhline(12, ls=":",  c="k",  lw=1.2)
ax1.text(2.46, 12.4, "12 dBi Yagi", ha="right", fontsize=8.5)
ax1.axhline(20, ls="--", c="gray", lw=1.2)
ax1.text(2.46, 20.4, "20 dBi dish", ha="right", fontsize=8.5)
ax1.axhline(0, c="k", lw=0.8)
ax1.set_xticks(list(xs))
ax1.set_xticklabels([f"+{p} dBm" for p in DBM])
ax1.set_xlabel("Balloon 433 MHz TX power  (low-power LR2021 \u2192 chip max \u2192 F33 2 W)")
ax1.set_ylabel("required GROUND gain (dBi) at 650 km, G_balloon = 0 dBi")
ax1.set_title("(a) TX power vs the dish it implies\n"
              "reqG = S + FSPL \u2212 P_tx ;  D = (\u03bb/\u03c0)\u221a(10^(G/10)/\u03b7), \u03b7=0.55",
              fontsize=10)
ax1.legend(loc="upper right", fontsize=9)
ax1.grid(axis="y", alpha=0.25)

# ---- panel (b) -------------------------------------------------------------
DISHES = [1.24, 1.90, 2.40, 2.62, 3.00, 3.49]
V = 120 / 3.6
Q = 0.5 * RHO * V ** 2


def moment(d, solidity):
    return Q * (math.pi * (d / 2) ** 2) * CD * solidity * (0.5 * d)


solid = [moment(d, 1.0) / BRAKE for d in DISHES]
mesh = [moment(d, SIG_6MM) / BRAKE for d in DISHES]
pos = range(len(DISHES))
b1 = ax2.bar([x - 0.2 for x in pos], solid, 0.4, label="SOLID reflector", color="#c0392b", alpha=0.85)
b2 = ax2.bar([x + 0.2 for x in pos], mesh, 0.4, label=f"6 mm coarse mesh (\u03c3={SIG_6MM:.3f})",
             color="#27ae60", alpha=0.9)
ax2.bar_label(b1, fmt="%.2f\u00d7", fontsize=8.5)
ax2.bar_label(b2, fmt="%.2f\u00d7", fontsize=8.5)
ax2.axhline(1.0, ls="--", c="k", lw=1.4)
ax2.text(5.45, 1.06, "SPID BIG-RAS holding torque 2,712 N\u00b7m", ha="right", fontsize=8.5)
ax2.set_xticks(list(pos))
ax2.set_xticklabels([f"{d:.2f} m" for d in DISHES])
ax2.set_xlabel("433 MHz dish diameter  (lever arm = 0.5 \u00d7 D ***stated assumption***)")
ax2.set_ylabel("wind moment @ 120 km/h  \u00f7  BIG-RAS brake torque   (1.00 = at the rating)")
ax2.set_title("(b) the coarse MESH is what makes a large 433 dish viable\n"
              "F = \u00bd\u03c1v\u00b2\u00b7A\u00b7Cd\u00b7\u03c3 ; Cd = 1.38 derived from the Gibertini OP100SE vendor figure",
              fontsize=10)
ax2.set_ylim(0, 6.4)
ax2.legend(loc="upper left", fontsize=9)
ax2.grid(axis="y", alpha=0.25)

fig.suptitle("FLRC at maximum throughput on the 433 MHz downlink \u2014 the trade the operator must see",
             fontsize=12.5, y=0.99)
fig.tight_layout(rect=(0, 0, 1, 0.965))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "flrc-max-trade.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.savefig(out, dpi=150)
print("wrote", out)
