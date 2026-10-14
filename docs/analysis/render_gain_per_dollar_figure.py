#!/usr/bin/env python3
"""Figure for docs/analysis/ground-station-gain-per-dollar.md.

Renders docs/analysis/assets/gain-per-dollar-challenge.png, the artifact put to
the independent visual consultant with the ask "challenge the METRIC itself and
the RANKING".

Panels
  A  the metric definitions and what is inside EUR_total (so the metric can be attacked)
  B  MARGINAL EUR per dB across the ladder (log axis) - the non-monotonicity
  C  M2 = EUR per (kbps*km) for the worst-case low-power board - the ranking
  D  the choice table (A-E) the operator is asked to pick from

Run: python3 docs/analysis/render_gain_per_dollar_figure.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ground_station_gain_per_dollar_model as M  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "assets", "gain-per-dollar-challenge.png")

# ---- derived numbers from the model (single source of truth) --------------
rows = []
for c in M.CANDIDATES:
    kbps, d, q, _ = M.best_capability(c["g"], M.PROV["P_chip_max"][0])
    rows.append(dict(label=c["label"], g=c["g"], pos=c["poskey"],
                     peur=c["peur"], tot=c["total"], m1=c["total"] / c["g"],
                     m2=c["total"] / q, d=d, q=q))

# marginal EUR/dB (consecutive rungs, skipping the same-G pair)
marg = []
for a, b in zip(rows, rows[1:]):
    dg = b["g"] - a["g"]
    if abs(dg) > 1e-9:
        marg.append((b["label"], (b["tot"] - a["tot"]) / dg, b["pos"]))

fig = plt.figure(figsize=(20.0, 15.0))
gs = fig.add_gridspec(3, 2, height_ratios=[0.85, 1.25, 1.20],
                      hspace=0.42, wspace=0.22)

# ---------------------------------------------------------------- Panel A
axA = fig.add_subplot(gs[0, :]); axA.axis("off")
axA.set_title("A.  THE METRIC (attack this)", loc="left", fontsize=17, fontweight="bold")
metric_txt = (
 "EUR_total  = antenna + 433 feed + coax + connectors + POSITIONER/ROTATOR-OR-DIY-TRACKER\n"
 "             (motors, worm reducers, encoders, drivers, controller, ANEMOMETER) + mast + build allowance.\n"
 "\n"
 "M1   average gain-per-dollar      EUR_total / G433                [EUR per dB]      <- rewards any cheap gain; hides class jumps\n"
 "M1m  MARGINAL gain-per-dollar     dEUR_total / dG  (adjacent rungs) [EUR per dB]      <- exposes NON-MONOTONICITY\n"
 "M2   capability-per-dollar        EUR_total / max_R (R * d_max(R)) [EUR per (kbps*km)] <- THE metric: prices range AND throughput\n"
 "M3   range-per-dollar @ rate      EUR_total / d_max(650 kbps)     [EUR per km]       <- range-first complement to M2\n"
 "\n"
 "CLAIM: M2 is the most useful (the operator wants range AND throughput); M1m is the most diagnostic.\n"
 "CAVEAT stated in the doc: M2 weights RATE linearly and RANGE logarithmically -> it is throughput-first. M3 is the range-first check.\n"
 "d_max closes the 433 link for the WORST-CASE board (low-power LR2021, +22 dBm, 6 dB fade margin, 2.6 dB impl loss).\n"
 "Ratio of two candidates is EXACTLY independent of the fade-margin choice (a constant margin scales every d_max equally).")
axA.text(0.005, 0.02, metric_txt, family="DejaVu Sans Mono", fontsize=10.0, va="bottom", ha="left")

# ---------------------------------------------------------------- Panel B
axB = fig.add_subplot(gs[1, 0])
labels = [m[0].replace(" (DIY, frame TODO)", "*").replace(" (same dish, meshed)", " (mesh)")
          for m in marg]
vals = [m[1] for m in marg]
posk = [m[2] for m in marg]
colors = ["#1f77b4" if p in ("P1", "P2") else "#d62728" for p in posk]
y = range(len(vals))
axB.barh(list(y), vals, color=colors)
axB.set_yticks(list(y)); axB.set_yticklabels(labels, fontsize=8.2)
axB.set_xscale("log")
axB.axvline(50, color="k", ls="--", lw=1.0)
axB.text(52, len(vals) - 0.6, "EUR 50/dB", fontsize=9)
axB.set_xlabel("MARGINAL EUR per dB   (log scale)   -- blue = DIY P1/P2 tracker, red = commercial rotator class")
axB.set_title("B.  NON-MONOTONICITY: the price of the NEXT dB\n"
              "(blue: 5-69 EUR/dB on the Yagi + DIY ladder;  red: 127-598 EUR/dB once a rotator class is crossed)",
              loc="left", fontsize=12, fontweight="bold")
axB.grid(axis="x", which="both", alpha=0.25)

# ---------------------------------------------------------------- Panel C
axC = fig.add_subplot(gs[1, 1])
srt = sorted(rows, key=lambda r: r["m2"])
lb = [r["label"].replace(" (DIY, frame TODO)", "*") for r in srt]
vv = [r["m2"] for r in srt]
cc = ["#2ca02c" if ("Yagi" in r["label"] or "Diamond" in r["label"] or "Sirio" in r["label"]
       or "Flexa" in r["label"] or "stacked" in r["label"]) else "#d62728" for r in srt]
axC.barh(range(len(vv)), vv, color=cc)
axC.set_yticks(range(len(vv))); axC.set_yticklabels(lb, fontsize=8.2)
axC.set_xlabel("M2 = EUR per (kbps*km)  -- lower is better  (worst-case low-power LR2021, +22 dBm)")
axC.set_title("C.  THE RANKING (green = Yagi, red = dish)\n"
              "best: Diamond A-430S15R 14.8 dBi, EUR74.50, DIY P2 -> 0.0019;  every Yagi beats every purchasable dish",
              loc="left", fontsize=12, fontweight="bold")
axC.grid(axis="x", alpha=0.25)

# ---------------------------------------------------------------- Panel D
axD = fig.add_subplot(gs[2, :]); axD.axis("off")
axD.set_title("D.  THE CHOICE TABLE put to the operator (attack this too)",
              loc="left", fontsize=17, fontweight="bold")
choice = (
 "    option                                                      total EUR   G433 dBi  low-power: 2.6 Mbps to   with F33 (+33 dBm)\n"
 "A   CHEAPEST REPLICABLE  Diamond A-430S10R + DIY P1 + 0.6 m dish      ~650      13.1          123 km               438 km\n"
 "B   BALANCED (RECOMMENDED) Diamond A-430S15R + DIY P2 + 0.6 m dish    ~735      14.8          150 km               532 km\n"
 "C   MAX GAIN/EUR (Yagi)  FlexaYagi FX 7073 + Yaesu G-5500DC          ~1316      18.0          217 km               769 km\n"
 "D   MAX PERFORMANCE (dish) RFH 1.9 m mesh FPD 1M9 + SPID BIG-RAS     ~2878      16.8          190 km               673 km\n"
 "E   *alternative*        2x Sirio WY 400-10N stacked + DIY P2          ~971      17.0          193 km               686 km\n"
 "\n"
 "HEADLINE: option D costs 3.9x option B and buys LESS gain than option C (16.8 vs 18.0 dBi) for 2.2x the money.\n"
 "The single highest-leverage EUR is the ~$8 F33 MODULE on the balloon: it multiplies EVERY ground candidate's range by 3.55.\n"
 "FLRC at 650 km on the low-power board needs a 3.0-3.5 m dish whose parabolic FORMER no vendor sells (DIY-only).\n"
 "LoRa (SF12/62.5 kHz, -143 dBm) closes 650 km with ANY antenna incl. a 0 dBi omni -> the antenna choice is purely a FLRC decision.")
axD.text(0.005, 0.02, choice, family="DejaVu Sans Mono", fontsize=10.6, va="bottom", ha="left")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, dpi=125, bbox_inches="tight", facecolor="white")
print("wrote", OUT)
