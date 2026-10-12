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


def block(ax, x, y, w, h, text, fc="#e8eef7", ec="#1f4e79", fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
                                linewidth=1.4, edgecolor=ec, facecolor=fc))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color="#111111")


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
                                 linewidth=1.4, color="#1f4e79"))


# ---------------------------------------------------------------- figure 1
fig, ax = plt.subplots(figsize=(12.2, 4.5))
ax.set_xlim(0, 18.4); ax.set_ylim(0, 5.8); ax.axis("off")
ax.set_title("Receive AGC chain — VGA AFTER the LNA (433 MHz downlink)", fontsize=12, weight="bold")

#      (text, x, width, fontsize)
chain = [("433 MHz\nantenna\n14.8 dBi", 0.15, 1.9, 8.4),
         ("433 MHz\nBPF (ADR-072 INV-3)", 2.75, 1.9, 8.2),
         ("LNA\nTQP3M9037\n+20 dB, NF 0.4", 5.35, 1.9, 8.0),
         ("VGA / DVGA\nADL5240 / ADL5330\n-12 .. +22 dB span", 7.95, 2.3, 7.4),
         ("receiver\nLR2021 433", 10.85, 1.9, 8.4)]
for label, x, w, fs in chain:
    block(ax, x, 3.3, w, 1.6, label, fs=fs)
for i in range(len(chain) - 1):
    arrow(ax, chain[i][1] + chain[i][2], 4.10, chain[i + 1][1], 4.10)

# feedback: coupler tap -> log detector -> ADC/MCU -> VGA
block(ax, 7.95, 0.55, 2.3, 1.35, "log detector AD8318\n1 MHz-8 GHz, 70 dB\n433 BPF AT THE TAP",
      fc="#fdeaea", ec="#a33", fs=7.4)
block(ax, 10.85, 0.55, 2.3, 1.35, "ADC + MCU\n(RP2040 / ESP32-S3)\nSPI / VCTRL",
      fc="#eaf6ea", ec="#2a6", fs=7.6)
arrow(ax, 9.10, 3.30, 9.10, 1.90)      # tap from chain down to detector
arrow(ax, 10.25, 1.22, 10.85, 1.22)    # detector -> MCU
arrow(ax, 9.10, 1.22, 9.10, 3.30)      # MCU/detector -> VGA control

ax.text(13.55, 2.35,
        "VGA AFTER the LNA (Friis):\n"
        "  LNA -> VGA  NF = 0.436 dB  (VGA adds +0.04 dB)\n"
        "  VGA -> LNA  NF = 3.015 dB  (VGA adds +2.6 dB)\n"
        "the VGA's excess noise is divided by the LNA's\n"
        "20 dB gain - that is why it goes second.\n"
        "The VGA-first figure is the UNITY-GAIN worst point;\n"
        "a ~1 dB pre-LNA (BPF+limit) loss dominates the\n"
        "system NF and is NOT in the post-LNA VGA.",
        ha="left", va="center", fontsize=8.0, color="#1f4e79",
        bbox=dict(boxstyle="round,pad=0.4", fc="#f7f9fc", ec="#1f4e79"))
ax.text(0.15, 2.5,
        "manual / commanded mode is the BASELINE; the loop is the enhancement.\n"
        "loop: FAST ATTACK (overload guard, within one frame) + SLOW DECAY\n"
        "(tau 10-100 ms; below the fade rate, above the geometry rate).",
        ha="left", va="center", fontsize=7.9, style="italic", color="#555555")
for ext in ("png", "svg"):
    fig.savefig(os.path.join(OUT, f"receive-agc-chain.{ext}"), dpi=160, bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- figure 2
fig, ax = plt.subplots(figsize=(10.6, 5.8))
d = np.logspace(np.log10(0.02), np.log10(800), 400)


def prx(dk):
    return 33.0 + 2.0 + 14.8 - (20 * np.log10(dk) + 20 * np.log10(433.0) + 32.44)


lvl = prx(d)
ax.semilogx(d, lvl, color="#1f4e79", lw=2.2, label="P_rx at ground (F33 +33 dBm, 14.8 dBi)")

S_TOP = -99.0
W = 35.0
# fixed-gain window: EXACTLY W dB tall, bottom at the top-rate sensitivity.
upper_fixed = S_TOP + W          # = -64.0 dBm (compression onset)
ax.axhspan(S_TOP, upper_fixed, color="#f2c200", alpha=0.18,
           label=f"fixed-gain usable window ({W:.0f} dB)")
ax.axhline(S_TOP, color="#c0392b", ls="--", lw=1.3)
ax.axhline(upper_fixed, color="#c0392b", ls="--", lw=1.3)
ax.text(0.021, S_TOP - 4.2, "top-rate sensitivity -99 dBm", fontsize=8, color="#c0392b")
ax.text(0.021, upper_fixed + 1.4, "fixed-gain compression onset", fontsize=8, color="#c0392b")

# AGC: the window is RECENTRED with range; its top follows the signal up to the
# authority limit (fixed top + the part's control range R).
for R, col, lab in ((31.5, "#2a6", "AGC window, DSA 31.5 dB (ADL5240) / 31.75 dB (PE43711)"),
                    (57.0, "#8e44ad", "AGC window, VGA -35..+22 dB (ADL5330, 57 dB)")):
    top = np.minimum(lvl + 20.0, upper_fixed + R)
    bot = top - W
    ax.fill_between(d, bot, top, color=col, alpha=0.12, lw=0)
    ax.semilogx(d, top, color=col, ls="--", lw=1.3, label=lab)

ax.axvline(1.0, color="#999", lw=0.8); ax.axvline(650.0, color="#999", lw=0.8)
ax.text(1.0, 8.5, " 1 km", fontsize=8, color="#555")
ax.text(650.0, 8.5, " 650 km ", fontsize=8, color="#555", ha="right")
ax.set_xlabel("range (km)")
ax.set_ylabel("received level at the 433 MHz antenna port (dBm)")
ax.set_title("Dynamic-range budget: 56.3 dB of path-loss swing + 15 dB fade over 1 -> 650 km",
             fontsize=11.2, weight="bold")
ax.grid(True, which="both", alpha=0.25)
ax.set_ylim(-112, 14)
ax.legend(loc="upper right", fontsize=7.4, framealpha=0.95)
fig.tight_layout()
for ext in ("png", "svg"):
    fig.savefig(os.path.join(OUT, f"dynamic-range-budget.{ext}"), dpi=160, bbox_inches="tight")
plt.close(fig)

print("wrote", OUT)
