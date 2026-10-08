#!/usr/bin/env python3
"""Render the Tier-0 / EIRP-cap figure for the independent visual consult.

    python3 docs/analysis/render_tier0_figure.py
writes docs/analysis/figures/tier0-eirp-capped-uplink.png
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(__file__), "figures", "tier0-eirp-capped-uplink.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

fig, axes = plt.subplots(1, 3, figsize=(19, 6.2))

# ---------------------------------------------------------------- Panel A ----
ax = axes[0]
g = list(range(0, 28))
def margin(gain, fs, ptx=12.0, cap=20.0, grx=10.0, s=-137.0):
    return min(ptx + gain, cap) + grx - s - fs
FSPL300, FSPL650 = 149.6, 156.3
m300 = [margin(x, FSPL300) for x in g]
m650 = [margin(x, FSPL650) for x in g]
ax.plot(g, m300, lw=2.6, color="#1f77b4", label="300 km")
ax.plot(g, m650, lw=2.6, color="#d62728", label="650 km")
ax.axvline(8, color="k", ls="--", lw=1.4)
ax.text(8.4, 1.0, "8 dBi = 20 dBm EIRP cap\n(PA max +12 dBm)", fontsize=9)
ax.axvspan(8, 29, color="grey", alpha=0.18)
ax.text(17.5, 7.0, "No uplink benefit\nunder the 20 dBm EIRP cap", ha="center", fontsize=10.5,
        weight="bold", color="#444")
for xn, lab in [(0, "omni\n0 dBi"), (8, "8 dBi\npanel"), (21.4, "0.6 m\ndish 21.4 dBi"),
                (27.4, "1.2 m\ndish 27.4 dBi")]:
    ax.axvline(xn, color="#888", lw=0.8, ls=":")
    ax.plot([xn], [0], marker="v", color="#888", ms=5)
    ax.text(xn, 21.4, lab, ha="center", va="top", fontsize=8.5, color="#444")
ax.set_xlim(-0.8, 29.5)
ax.set_ylim(-7.5, 21.5)
ax.set_xlabel("Ground 2.4 GHz antenna gain  (dBi)")
ax.set_ylabel("Uplink margin  (dB)")
ax.set_title("A. No uplink benefit above 8 dBi\n(2.4 GHz uplink only; 20 dBm total EIRP; PA max +12 dBm; no-LNA case in Table 1c)", fontsize=10)
ax.grid(alpha=0.3)
ax.legend(loc="lower right", fontsize=9)

# ---------------------------------------------------------------- Panel B ----
ax = axes[1]
labels = ["omni\n0 dBi", "small Yagi\n10 dBi", "Diamond\nA-430S10R\n13.1 dBi", "A-430S15R\n14.8 dBi"]
gains = [0.0, 10.0, 13.1, 14.8]
# 433 FLRC 2.6 Mbps, F33 +33 dBm
req_f33_2600 = 7.9   # dBi @650 km
req_lp_2600 = 18.9   # dBi @650 km (+22 dBm)
req_lp_650 = 12.4
m_f33 = [gg - req_f33_2600 for gg in gains]
m_lp = [gg - req_lp_2600 for gg in gains]
x = range(len(gains))
w = 0.38
ax.bar([i - w/2 for i in x], m_f33, w, color="#2ca02c", label="F33 +33 dBm, FLRC 2.6 Mbps")
ax.bar([i + w/2 for i in x], m_lp, w, color="#ff7f0e", label="low-power +22 dBm, FLRC 2.6 Mbps")
ax.axhline(0, color="k", lw=1.0)
ax.set_xticks(list(x)); ax.set_xticklabels(labels, fontsize=9)
ax.set_ylabel("433 downlink margin @650 km  (dB)")
ax.set_title("B. 433 downlink @650 km — F33 makes the plotted Yagi enough\n(plotted antennas + stated assumptions only; margins, not installed performance)", fontsize=10)
ax.grid(alpha=0.3, axis="y")
ax.legend(fontsize=8.5, loc="upper left")

# ---------------------------------------------------------------- Panel C ----
ax = axes[2]
names = ["Tier 0a\n2 omnis\nno pointing", "Tier 0b\nhand-aimed\nYagi", "Tier A\nre-costed\n(no dish)", "Tier A\noriginal\n(with dish)"]
lo = [90, 144, 616, 926.9]
hi = [245, 304, 685, 950.9]
x = range(len(names))
ax.bar(x, [h - l for h, l in zip(hi, lo)], bottom=lo, color="#4c72b0", alpha=0.85)
for i, (l, h) in enumerate(zip(lo, hi)):
    ax.text(i, h + 12, f"€{l:.0f}–{h:.0f}", ha="center", fontsize=10, weight="bold")
ax.set_xticks(list(x)); ax.set_xticklabels(names, fontsize=9)
ax.set_ylabel("Parts cost  (EUR)")
ax.set_title("C. The tiers — PARTS cost; dish removal saves €266–311\n(matched low/low & high/high; cross-endpoint range is €242–335)", fontsize=10)
ax.grid(alpha=0.3, axis="y")
ax.set_ylim(0, 1180)

fig.suptitle("Tier 0 (ultra-low-cost) ground station + re-costed Tier A — 2.4 GHz dish removed", fontsize=14, weight="bold")
fig.text(0.5, 0.005,
         "Panels B/C are parts cost for the plotted antennas and stated assumptions only. "
         "System-level claims (1.5 deg pointing budget, no-tracker Tier-0 viability) are derived in "
         "docs/analysis/tier0-accessible-ground-station.md sections 4-5, not by this figure.",
         ha="center", fontsize=8, style="italic", color="#555")
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(OUT, dpi=115)
print("wrote", OUT)
