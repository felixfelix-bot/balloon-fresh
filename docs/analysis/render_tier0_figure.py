#!/usr/bin/env python3
"""Render the Tier-0 / EIRP-cap figure for the independent visual consult.

    /opt/miniconda/bin/python3 docs/analysis/render_tier0_figure.py
writes docs/analysis/figures/tier0-eirp-capped-uplink.png

(Any interpreter with matplotlib works; the default `python3` on this box has none.)
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(__file__), "figures", "tier0-eirp-capped-uplink.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

fig, axes = plt.subplots(1, 3, figsize=(17.5, 7.6))

# ---------------------------------------------------------------- Panel A ----
ax = axes[0]
g = list(range(0, 28))
def margin(gain, fs, ptx=12.0, cap=20.0, grx=10.0, s=-137.0):
    return min(ptx + gain, cap) + grx - s - fs
FSPL300, FSPL650 = 149.6, 156.3
ax.plot(g, [margin(x, FSPL300) for x in g], lw=2.8, color="#1f77b4", label="300 km")
ax.plot(g, [margin(x, FSPL650) for x in g], lw=2.8, color="#d62728", label="650 km")
ax.axvline(8, color="k", ls="--", lw=1.5)
ax.axvspan(8, 29.5, color="grey", alpha=0.18)
ax.text(8.3, 3.2, "8 dBi = 20 dBm EIRP cap\n(PA max +12 dBm)", fontsize=9.5)
ax.text(19.0, 6.4, "No uplink benefit\nabove the cap", ha="center", fontsize=11.5,
        weight="bold", color="#333")
for xn, lab in [(0, "omni\n0 dBi"), (8, "8 dBi\npanel"), (21.4, "0.6 m dish\n21.4 dBi"),
                (27.4, "1.2 m dish\n27.4 dBi")]:
    ax.axvline(xn, color="#888", lw=0.9, ls=":")
    ax.plot([xn], [0], marker="v", color="#888", ms=6)
    ax.text(xn, 1.02, lab, transform=ax.get_xaxis_transform(), ha="center", va="bottom",
            fontsize=9, color="#333")
ax.set_xlim(-1.0, 30.0)
ax.set_ylim(-7.5, 19)
ax.set_xlabel("Ground 2.4 GHz antenna gain  (dBi)", fontsize=10.5)
ax.set_ylabel("Uplink margin  (dB)", fontsize=10.5)
ax.set_title("A. 2.4 GHz UPLINK only — modelled margin saturates at 8 dBi\n"
             "assumes the 20 dBm total-EIRP cap, a +12 dBm PA, and the balloon LNA",
             fontsize=10.5)
ax.grid(alpha=0.3)
ax.legend(loc="lower right", fontsize=10)

# ---------------------------------------------------------------- Panel B ----
ax = axes[1]
labels = ["omni\n0 dBi", "small Yagi\n10 dBi", "Diamond\nA-430S10R\n13.1 dBi", "A-430S15R\n14.8 dBi"]
gains = [0.0, 10.0, 13.1, 14.8]
m_f33 = [gg - 7.9 for gg in gains]
m_lp = [gg - 18.9 for gg in gains]
x = range(len(gains)); w = 0.38
ax.bar([i - w/2 for i in x], m_f33, w, color="#2ca02c", label="F33 = 2 W / +33 dBm, FLRC 2.6 Mbps")
ax.bar([i + w/2 for i in x], m_lp, w, color="#ff7f0e", label="low-power LR2021 +22 dBm, FLRC 2.6 Mbps")
ax.axhline(0, color="k", lw=1.0)
ax.set_xticks(list(x)); ax.set_xticklabels(labels, fontsize=9)
ax.set_ylabel("433 downlink modelled margin @650 km  (dB)", fontsize=10.5)
ax.set_title("B. 433 MHz DOWNLINK @650 km — modelled margins\n"
             "free-space model, balloon 433 gain 0 dBi; not installed performance",
             fontsize=10.5)
ax.grid(alpha=0.3, axis="y"); ax.legend(fontsize=9, loc="upper left")

# ---------------------------------------------------------------- Panel C ----
ax = axes[2]
names = ["Tier 0a\n2 omnis\nno pointing", "Tier 0b\nhand-aimed\nYagi", "Tier A\nre-costed\n(no dish)", "Tier A\noriginal\n(with dish)"]
lo = [90, 144, 616, 926.9]; hi = [245, 304, 685, 950.9]
x = range(len(names))
ax.bar(x, [h - l for h, l in zip(hi, lo)], bottom=lo, color="#4c72b0", alpha=0.85)
for i, (l, h) in enumerate(zip(lo, hi)):
    ax.text(i, h + 16, f"€{l:.0f}–{h:.0f}", ha="center", fontsize=10.5, weight="bold")
ax.set_xticks(list(x)); ax.set_xticklabels(names, fontsize=9.5)
ax.set_ylabel("Parts cost per station  (EUR)", fontsize=10.5)
ax.set_title("C. PARTS cost per station — the dish+feed (€326) is replaced by a panel (€15–60),\n"
             "saving €266–311 like-for-like (cross-endpoint extremes span €242–335)", fontsize=10.5)
ax.grid(alpha=0.3, axis="y"); ax.set_ylim(0, 1180)

fig.suptitle("Tier 0 (ultra-low-cost) ground station + re-costed Tier A — 2.4 GHz dish removed\n"
             "Figure scopes: panels A/B are 2.4 GHz uplink / 433 downlink LINK margins; panel C is PARTS cost. "
             "Tier-0 viability is conditional on the analysis document §§4–5.",
             fontsize=11.5, weight="bold")
fig.text(0.5, 0.012,
         "Model: free-space (FSPL) path loss; 433 MHz sensitivities from the Semtech LR2021 datasheet; balloon 433 gain 0 dBi; "
         "2.4 GHz uplink assumes the balloon LNA (without it, no ground antenna closes 650 km).\n"
         "System-level claims (the 1.5 deg pointing budget, and that no-tracker Tier 0 is viable) are DERIVED in "
         "docs/analysis/tier0-accessible-ground-station.md §§4–5 — this figure does not establish them.",
         ha="center", va="bottom", fontsize=8.5, style="italic", color="#444")

fig.tight_layout(rect=[0, 0.075, 1, 0.885])
fig.savefig(OUT, dpi=130)
print("wrote", OUT)
