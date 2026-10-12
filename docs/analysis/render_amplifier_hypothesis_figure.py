#!/usr/bin/env python3
"""Figure for docs/analysis/ground-station-amplifier-hypothesis-check.md.

Renders docs/analysis/assets/amplifier-hypothesis-ebar.png — the artifact put to the
independent visual consultant.

Panels
  A  the Q1 decomposition: what an LNA recovers vs what only directivity recovers
     (433 MHz receive chain, T_ant + feed + receiver terms, log y)
  B  beamwidth narrowing: element HPBW -> stacked HPBW, N=1/2/4 at d=0.5 lambda
  C  cost per NEEDED dB (log x), with the F33's 0.40 USD/dB bar drawn as the line
  D  the Q4 overdrive: P_rx at the balloon vs range, with the compression onset

Run: /usr/bin/python3 docs/analysis/render_amplifier_hypothesis_figure.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ground_station_amplifier_hypothesis_model as M  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "assets", "amplifier-hypothesis-ebar.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

fig = plt.figure(figsize=(18.5, 11.5))
gs = fig.add_gridspec(2, 2, hspace=0.44, wspace=0.36,
                      left=0.155, right=0.975, top=0.90, bottom=0.075)
fig.suptitle("Ground-station AMPLIFIER hypothesis — verification vs the F33's 0.40 USD/dB bar\n"
             "repro: /usr/bin/python3 docs/analysis/ground_station_amplifier_hypothesis_model.py",
             fontsize=13.5, y=0.975)

# ---------------------------------------------------------------- Panel A: Q1 split
axA = fig.add_subplot(gs[0, 0])
t_rx = M.t_from_nf(8.0)
KINDS = ["T_ant", "lna", "feed", "rx"]
cases = {}
order = ("no LNA\nwide-beam", "+ LNA\nwide-beam", "+ LNA\n+ cold-sky dish")
for key, ant, lna in ((order[0], M.T_ANT_WIDE, None),
                      (order[1], M.T_ANT_WIDE, (M.LNA433_GAIN, M.t_from_nf(M.LNA433_NF))),
                      (order[2], M.T_ANT_DISH, (M.LNA433_GAIN, M.t_from_nf(M.LNA433_NF)))):
    blocks = []
    if lna:
        blocks.append(("lna", lna[0], lna[1]))
    blocks += [("feed", -M.FEED_DB_433, M.T_FEED_433), ("rx", 0.0, t_rx)]
    t_sys, rows = M.cascade(blocks, ant)
    contrib = {"T_ant": ant}
    for r in rows:
        contrib[r[0]] = r[3]
    cases[key] = (t_sys, contrib)

x = list(range(len(cases)))
colors = {"T_ant": "#c0392b", "lna": "#2980b9", "feed": "#7f8c8d", "rx": "#f39c12"}
maxT = max(cases[k][0] for k in cases)
bottom = [0.0] * len(cases)
for kind in KINDS:
    vals = [cases[k][1].get(kind, 0.0) for k in cases]
    axA.bar(x, vals, bottom=bottom, color=colors[kind], edgecolor="black", linewidth=0.8)
    for xi, (v, b) in enumerate(zip(vals, bottom)):
        if v <= 0:
            continue
        inside = v > 0.06 * maxT
        axA.text(xi + (0 if inside else 0.16), b + v / 2, f"{v:.0f}",
                 ha="center", va="center", fontsize=7.5,
                 color="white" if inside else "black",
                 fontweight="bold" if inside else "normal")
    bottom = [b + v for b, v in zip(bottom, vals)]
for xi, k in enumerate(cases):
    axA.text(xi, bottom[xi] * 1.08, f"T_sys\n{bottom[xi]:.0f} K", ha="center",
             va="bottom", fontsize=9.5, fontweight="bold")
# explicit deltas, so the +9.73 / +3.80 dB claims are READABLE not measured
d1 = M.db(cases[order[0]][0] / cases[order[1]][0])
d2 = M.db(cases[order[1]][0] / cases[order[2]][0])
axA.annotate("", xy=(1, cases[order[1]][0] * 1.3), xytext=(0, cases[order[0]][0] * 1.3),
             arrowprops=dict(arrowstyle="<->", color="#2980b9", lw=1.8))
axA.text(0.5, cases[order[0]][0] * 1.5, f"LNA buys +{d1:.2f} dB", ha="center",
         fontsize=9.5, color="#2980b9", fontweight="bold")
axA.annotate("", xy=(2, cases[order[2]][0] * 1.3), xytext=(1, cases[order[1]][0] * 1.3),
             arrowprops=dict(arrowstyle="<->", color="#16a085", lw=1.8))
axA.text(1.5, cases[order[1]][0] * 1.5, f"cold sky adds +{d2:.2f} dB", ha="center",
         fontsize=9.5, color="#16a085", fontweight="bold")
axA.set_yscale("log")
axA.set_xticks(x)
axA.set_xticklabels(list(cases), fontsize=9)
axA.set_ylabel("noise temperature (K, log scale)")
axA.set_title("A  Q1 — the receive chain: LNA vs directivity (433 MHz, RX NF 8 dB)\n"
              "every segment is labelled; the deltas are annotated, not left to be measured",
              fontsize=10.5)
axA.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=colors[c]) for c in KINDS],
           labels=["T_ant", "LNA", "feed loss", "receiver"], fontsize=8.5, loc="lower left")
axA.grid(axis="y", alpha=0.25, which="both")
axA.set_ylim(10, 40000)

# ---------------------------------------------------------------- Panel B: beamwidth
axB = fig.add_subplot(gs[0, 1])
configs = [(1, "N=1\n(single)"), (2, "N=2\n(2-bay, d=0.5$\lambda$)"), (4, "N=4\n(4-bay, d=0.5$\lambda$)")]
for gi, (elem, name, col) in enumerate(((65.0, "3-el Yagi (7 dBi): 65° element", "#8e44ad"),
                                        (29.2, "10-el Yagi (14 dBi): 29.2° element", "#16a085"))):
    vals = [M.af_hpbw(n, 0.5, elem)[0] for n, _ in configs]
    offs = [-0.19, 0.19][gi]
    axB.bar([i + offs for i in range(3)], vals, width=0.36, color=col, edgecolor="black",
            linewidth=0.8, label=name)
    for i, v in enumerate(vals):
        axB.text(i + offs, v + 0.8, f"{v:.1f}°", ha="center", fontsize=8.5)
    for i in (1, 2):
        axB.text(i + offs, vals[i] / 2, f"×{vals[i]/vals[0]:.2f}", ha="center",
                 va="center", fontsize=9, color="white", fontweight="bold")
axB.set_xticks(range(3))
axB.set_xticklabels([c[1] for c in configs], fontsize=9.5)
axB.set_ylabel("−3 dB beamwidth in the STACKING plane (deg)")
axB.set_title("B  Q2 — arraying narrows the beam (pattern multiplication, d=0.5$\\lambda$)\n"
              "+3.01 dB (2-bay) / +6.02 dB (4-bay) ideal vs a narrower pointing window",
              fontsize=10.5)
axB.legend(fontsize=8.5, loc="upper right")
axB.grid(axis="y", alpha=0.25)
axB.set_ylim(0, 78)

# ---------------------------------------------------------------- Panel C: EUR/dB
axC = fig.add_subplot(gs[1, 0])
rows = [
    ("F33 on balloon\n(USD 8 / 20 dB) = THE BAR", 0.40, "#27ae60", True),
    ("433 masthead LNA\n(EUR 257 / 9.7 dB system)", M.LNA433_EUR / 9.73, "#2980b9", False),
    ("2-bay Yagi array\n(EUR 228.40 / 3 dB)", 228.40 / 3.0, "#d35400", False),
    ("4-bay Yagi array\n(EUR 562.40 / 6 dB)", 562.40 / 6.0, "#e67e22", False),
    ("1.9 m dish + tracker\ngain + cold-sky (6.64 dB)", 2297.0 / 6.64, "#95a5a6", False),
    ("1.9 m dish + tracker\nGAIN ONLY (2.84 dB)", 2297.0 / 2.84, "#7f8c8d", False),
]
ys = list(range(len(rows)))[::-1]
for y, (lab, val, col, is_bar) in zip(ys, rows):
    axC.barh(y, val, color=col, edgecolor="black", linewidth=0.8, height=0.62)
    axC.text(val * 1.15, y, f"{val:.2f}", va="center", fontsize=9, fontweight="bold")
axC.set_xscale("log")
axC.set_yticks(ys)
axC.set_yticklabels([r[0] for r in rows], fontsize=8.5)
axC.axvline(0.40, color="#27ae60", ls="--", lw=2)
axC.text(0.44, -0.62, "the 0.40 USD/dB BAR", color="#27ae60", fontsize=9.5, fontweight="bold")
axC.set_xlabel("cost per NEEDED dB (money/dB) — log scale  [2.4 GHz ground PA omitted: it buys 0 needed dB = INF]")
axC.set_title("C  Q5 — cost per needed dB, best at top\n"
              "definition: money per dB of link-budget improvement in the direction that NEEDS it",
              fontsize=10.5)
axC.grid(axis="x", alpha=0.25, which="both")
axC.set_xlim(0.2, 3000)
axC.set_ylim(-1.1, len(rows) - 0.3)

# ---------------------------------------------------------------- Panel D: overdrive
axD = fig.add_subplot(gs[1, 1])
import numpy as np
d = np.logspace(0, 5.2, 400)  # 1 m .. ~160 km
for p, col in ((20.0, "#27ae60"), (33.0, "#c0392b"), (40.8, "#8e44ad")):
    axD.semilogx(d, [M.p_rx_balloon(p, dd) for dd in d], color=col, lw=2,
                 label=f"ground TX +{p:.1f} dBm, 12.4 dBi Yagi")
axD.axhline(-20.0, color="black", ls="--", lw=1.6)
axD.text(3.0e4, -17.5, "−20 dBm: AGC/LNA compression onset\n(anchored on the repo's MEASURED saturation)",
         fontsize=8.5, va="bottom", ha="left")
axD.axvspan(1, 45.7, color="#c0392b", alpha=0.10)
axD.text(300.0, -108, "+33 dBm PA:\ncompresses inside 14.5 m\nhard-overloads inside 1.4 m",
         fontsize=9, color="#c0392b", fontweight="bold")
axD.axvline(20000, color="gray", ls=":", lw=1.5)
axD.text(1.2e4, -60, "20 km\nworking\nrange", fontsize=8.5, color="gray", ha="right")
axD.set_xlabel("range, ground → balloon (m, log scale)")
axD.set_ylabel("P_rx at the balloon (dBm)")
axD.set_title("D  Q4 — the overdrive hazard, and why an attenuator alone is not the fix\n"
              "sensitivity is −136 dBm: at 20 km the uplink sits ~53 dB above it",
              fontsize=10.5)
axD.legend(fontsize=8.5, loc="upper right")
axD.grid(alpha=0.25, which="both")
axD.set_ylim(-130, 0.5)
axD.set_xlim(1, 1.6e5)

fig.savefig(OUT, dpi=130, facecolor="white")
print("wrote", OUT)
