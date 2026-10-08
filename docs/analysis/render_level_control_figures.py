#!/usr/bin/env python3
"""
Render the two level-control figures.
Requires matplotlib:  /opt/miniconda/bin/python3 docs/analysis/render_level_control_figures.py
Writes:
  docs/analysis/assets/level-control/receive-agc-chain.png|.svg
  docs/analysis/assets/level-control/dynamic-range-budget.png|.svg
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "level-control")
os.makedirs(OUT, exist_ok=True)


def block(ax, x, y, w, h, text, fc="#e8eef7", ec="#1f4e79"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
                                linewidth=1.4, edgecolor=ec, facecolor=fc))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.5, color="#111111")


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
                                 linewidth=1.4, color="#1f4e79"))


# ---------------------------------------------------------------- figure 1
fig, ax = plt.subplots(figsize=(11.0, 4.4))
ax.set_xlim(0, 16.4); ax.set_ylim(0, 5.6); ax.axis("off")
ax.set_title("Receive AGC chain — VGA AFTER the LNA (433 MHz downlink)", fontsize=12, weight="bold")

chain = [("433 MHz\nantenna\n14.8 dBi", 0.15),
         ("433 MHz\nBPF\n(ADR-072 INV-3)", 2.35),
         ("LNA\nTQP3M9037\n+20 dB, NF 0.4", 4.55),
         ("VGA / DVGA\n+15…-15 dB\nNF 2.8…8 dB", 6.75),
         ("receiver\nLR2021 433", 8.95)]
for label, x in chain:
    block(ax, x, 3.2, 2.0, 1.5, label)
for i in range(len(chain) - 1):
    arrow(ax, chain[i][1] + 2.0, 3.95, chain[i + 1][1], 3.95)

# feedback: detector + control
block(ax, 6.75, 0.7, 2.0, 1.2, "log detector\nAD8318 (1 MHz–8 GHz)\n70 dB, 10 ns", fc="#fdeaea", ec="#a33")
block(ax, 9.4, 0.7, 2.0, 1.2, "ADC + MCU\n(RP2040/ESP32-S3)\nSPI / VCTRL", fc="#eaf6ea", ec="#2a6")
arrow(ax, 8.75, 3.2, 8.2, 1.9)     # coupler tap -> detector
arrow(ax, 8.75, 1.3, 7.9, 1.3)
arrow(ax, 8.2, 1.3, 8.2, 3.2)
ax.text(11.55, 2.05,
        "VGA AFTER the LNA (Friis):\n"
        "  LNA → VGA  NF = 0.436 dB   (VGA adds +0.04 dB)\n"
        "  VGA → LNA  NF = 3.015 dB   (VGA adds +2.6 dB)\n"
        "the VGA's excess noise is divided by the\n"
        "LNA's 20 dB gain — that is why it goes second.",
        ha="left", va="center", fontsize=8.2, color="#1f4e79",
        bbox=dict(boxstyle="round,pad=0.4", fc="#f7f9fc", ec="#1f4e79"))
ax.text(0.15, 2.3, "manual / commanded mode is the BASELINE;\nthe loop is the enhancement (operator decision).",
        ha="left", va="center", fontsize=8.0, style="italic", color="#555555")
for ext in ("png", "svg"):
    fig.savefig(os.path.join(OUT, f"receive-agc-chain.{ext}"), dpi=160, bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- figure 2
fig, ax = plt.subplots(figsize=(10.5, 5.6))
d = np.logspace(np.log10(0.02), np.log10(800), 400)


def prx(dk):
    return 33.0 + 2.0 + 14.8 - (20 * np.log10(dk) + 20 * np.log10(433.0) + 32.44)


lvl = prx(d)
ax.semilogx(d, lvl, color="#1f4e79", lw=2.2, label="P_rx at ground (F33 +33 dBm, 14.8 dBi)")

S_TOP = -99.0
W = 35.0
# fixed-gain window: centre it so the top rate closes at 650 km -> upper edge at 650 km level + W
upper_fixed = prx(650.0) + W        # = -91.6 + 35 = -56.6 dBm
ax.axhspan(S_TOP, upper_fixed, color="#f2c200", alpha=0.18,
           label=f"fixed-gain usable window ({W:.0f} dB)")
ax.axhline(S_TOP, color="#c0392b", ls="--", lw=1.3)
ax.axhline(upper_fixed, color="#c0392b", ls="--", lw=1.3)
ax.text(0.021, S_TOP - 4.5, "top-rate sensitivity -99 dBm", fontsize=8, color="#c0392b")
ax.text(0.021, upper_fixed + 1.5, "fixed-gain compression onset", fontsize=8, color="#c0392b")

# AGC: the window is RECENTRED with range; its top follows the signal up to the
# authority limit (fixed top + the part's control range R).
for R, col, lab in ((31.5, "#2a6", "AGC window, DSA 0–31.75 dB (ADL5240/PE43711)"),
                    (57.0, "#8e44ad", "AGC window, VGA -35…+22 dB (ADL5330, 57 dB)")):
    top = np.minimum(lvl + 20.0, upper_fixed + R)
    bot = top - W
    ax.fill_between(d, bot, top, color=col, alpha=0.13, lw=0)
    ax.semilogx(d, top, color=col, ls="--", lw=1.3, label=lab)

ax.axvline(1.0, color="#999", lw=0.8); ax.axvline(650.0, color="#999", lw=0.8)
ax.text(1.0, 8.0, " 1 km", fontsize=8, color="#555")
ax.text(650.0, 8.0, " 650 km ", fontsize=8, color="#555", ha="right")
ax.set_xlabel("range (km)")
ax.set_ylabel("received level at the 433 MHz antenna port (dBm)")
ax.set_title("Dynamic-range budget: 56.3 dB of path-loss swing + 15 dB fade over 1 → 650 km",
             fontsize=11.5, weight="bold")
ax.grid(True, which="both", alpha=0.25)
ax.set_ylim(-110, 12)
ax.legend(loc="upper right", fontsize=8, framealpha=0.95)
fig.tight_layout()
for ext in ("png", "svg"):
    fig.savefig(os.path.join(OUT, f"dynamic-range-budget.{ext}"), dpi=160, bbox_inches="tight")
plt.close(fig)

print("wrote", OUT)
