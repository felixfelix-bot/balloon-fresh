#!/usr/bin/env python3
"""
Generate TWO analysis plots from the most recent box-mounted RX capture
(box-mounted-rx-20260724.txt).

PLOT 1: recent-rssi-analysis.png  — RSSI vs time, green=rx=1, red=rx>1
PLOT 2: payload-corruption.png    — GPS payload fields vs expected values
"""

import re
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.style.use("dark_background")

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
RX_FILE = os.path.join(DATA_DIR, "box-mounted-rx-20260724.txt")

# Phase name lookup (from sweep cycle = 202s, 14 phases)
PHASE_NAMES = {
    0:  "HF-LoRa-SF7",
    1:  "HF-LoRa-SF9",
    2:  "HF-LoRa-SF12",
    3:  "HF-FLRC-2600",
    4:  "HF-FLRC-1300",
    5:  "HF-FLRC-650",
    6:  "HF-FLRC-325",
    7:  "LF-LoRa-SF7",
    8:  "LF-LoRa-SF9",
    9:  "LF-LoRa-SF12",
    10: "LF-FLRC-2600",
    11: "LF-FLRC-1300",
    12: "LF-FLRC-650",
    13: "LF-FLRC-325",
}

# Expected "truth" values for 2026-07-24 capture
EXPECTED = {
    "lat":  32.63,
    "lon": -16.95,
    "sats_low": 5,
    "sats_high": 11,
    "utc_base": 1784893000,   # ~2026-07-24
}


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------
PKT_RE = re.compile(
    r"PKT\s+rx=(?P<rx>-?\d+)\s+seq=(?P<seq>-?\d+)\s+rssi=(?P<rssi>-?\d+)\s+"
    r"phase=(?P<phase>\d+)\s+rx_ms=(?P<rx_ms>\d+)\s+"
    r"tx_lat=(?P<tx_lat>-?[\d.]+)\s+tx_lon=(?P<tx_lon>-?[\d.]+)\s+"
    r"sats=(?P<sats>\d+)\s+fix=(?P<fix>\d+)\s+utc=(?P<utc>\d+)"
)

packets = []
with open(RX_FILE) as f:
    for line in f:
        m = PKT_RE.search(line)
        if m:
            packets.append({
                "rx":     int(m.group("rx")),
                "seq":    int(m.group("seq")),
                "rssi":   int(m.group("rssi")),
                "phase":  int(m.group("phase")),
                "rx_ms":  int(m.group("rx_ms")),
                "tx_lat": float(m.group("tx_lat")),
                "tx_lon": float(m.group("tx_lon")),
                "sats":   int(m.group("sats")),
                "fix":    int(m.group("fix")),
                "utc":    int(m.group("utc")),
            })

print(f"Parsed {len(packets)} PKT lines")
n_rx1 = sum(1 for p in packets if p["rx"] == 1)
print(f"  rx=1 (primary decode): {n_rx1}")
print(f"  rx>1 (duplicate decode): {sum(1 for p in packets if p['rx'] > 1)}")


# ===========================================================================
# PLOT 1 — RSSI analysis
# ===========================================================================
fig1, ax1 = plt.subplots(figsize=(12, 8))

# Split by rx field: rx==1 = green (CRC-pass / primary), rx>1 = red
green = [p for p in packets if p["rx"] == 1]
red   = [p for p in packets if p["rx"] != 1]

# Use rx_ms as X (time in ms since boot), fall back to order index
x_g = [p["rx_ms"] for p in green]
y_g = [p["rssi"]  for p in green]
x_r = [p["rx_ms"] for p in red]
y_r = [p["rssi"]  for p in red]

ax1.scatter(x_g, y_g, c="#39ff14", s=180, marker="o", edgecolors="white",
            linewidths=1.2, zorder=5, label=f"rx=1  primary decode ({len(green)})")
ax1.scatter(x_r, y_r, c="#ff4444", s=110, marker="x", linewidths=2.0,
            zorder=4, label=f"rx>1  duplicate decode ({len(red)})")

# Annotate phase next to each green dot
for p in green:
    name = PHASE_NAMES.get(p["phase"], f"ph{p['phase']}")
    ax1.annotate(f"  {name}\n  rssi={p['rssi']}",
                 (p["rx_ms"], p["rssi"]),
                 textcoords="offset points", xytext=(8, 6),
                 fontsize=7, color="#cccccc", alpha=0.85)

# Threshold lines
ax1.axhline(-40,  color="#00ff88", linestyle="--", linewidth=1.0, alpha=0.6,
            label="-40 dBm  excellent")
ax1.axhline(-70,  color="#ffcc00", linestyle="--", linewidth=1.0, alpha=0.6,
            label="-70 dBm  usable")
ax1.axhline(-100, color="#ff4444", linestyle="--", linewidth=1.0, alpha=0.5,
            label="-100 dBm  noise floor")

# Shade zones
ax1.axhspan(0,    -40,  alpha=0.05, color="#00ff88")
ax1.axhspan(-40,  -70,  alpha=0.05, color="#ffcc00")
ax1.axhspan(-70,  -100, alpha=0.05, color="#ff8800")
ax1.axhspan(-100, -130, alpha=0.05, color="#ff4444")

ax1.set_xlabel("rx_ms  (milliseconds since RX boot)", fontsize=12)
ax1.set_ylabel("RSSI  (dBm)", fontsize=12)
ax1.set_title("Recent Capture: Signal IS getting through (RSSI -25 to -53 dBm)",
              fontsize=14, fontweight="bold", pad=14)
ax1.invert_yaxis()  # stronger signal (less negative) at top
ax1.set_ylim(10, -130)
ax1.grid(True, alpha=0.15)
ax1.legend(loc="lower right", fontsize=9, framealpha=0.7)

# Annotation box with counts
rssi_vals = [p["rssi"] for p in packets if p["rx"] == 1]
rssi_str  = f"{min(rssi_vals)} to {max(rssi_vals)}" if rssi_vals else "n/a"
ann = (f"Packets: {len(green)} primary (rx=1) / {len(packets)} total\n"
       f"RSSI range (rx=1): {rssi_str} dBm\n"
       f"Phases seen: {sorted({p['phase'] for p in packets})}\n"
       f"Best signal: {max(rssi_vals) if rssi_vals else 'n/a'} dBm  "
       f"(HF-LoRa-SF12, phase 2)")
ax1.text(0.02, 0.02, ann, transform=ax1.transAxes, fontsize=9,
         verticalalignment="bottom",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#1a1a2e",
                   edgecolor="#39ff14", alpha=0.85))

fig1.tight_layout()
out1 = os.path.join(DATA_DIR, "recent-rssi-analysis.png")
fig1.savefig(out1, dpi=150, facecolor="black")
plt.close(fig1)
print(f"Saved: {out1}")


# ===========================================================================
# PLOT 2 — Payload corruption
# ===========================================================================
fig2, axes = plt.subplots(2, 2, figsize=(12, 8))
fig2.suptitle("Payload Byte Alignment Bug: TX embeds GPS data, RX reads garbage",
              fontsize=14, fontweight="bold", y=0.995)

# Order packets by rx_ms for time axis
pkts_sorted = sorted(packets, key=lambda p: p["rx_ms"])
x_idx = np.arange(len(pkts_sorted))
x_labels = [f"ph{p['phase']}\nrx={p['rx']}" for p in pkts_sorted]

# Color: phase 2 (SF12, the only one with sensible sats) = green, else red
colors = []
for p in pkts_sorted:
    if p["phase"] == 2:
        colors.append("#39ff14")   # SF12 — looks valid
    else:
        colors.append("#ff4444")   # everything else — garbage

def _style(ax, title, ylabel):
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_xticks(x_idx)
    ax.set_xticklabels(x_labels, fontsize=7, rotation=45, ha="right")
    ax.grid(True, alpha=0.15, axis="y")
    ax.tick_params(axis="x", labelsize=7)

# --- (0,0) tx_lat ---
ax = axes[0, 0]
lats = [p["tx_lat"] for p in pkts_sorted]
ax.scatter(x_idx, lats, c=colors, s=90, zorder=5, edgecolors="white",
           linewidths=0.8)
ax.axhline(EXPECTED["lat"], color="#00ffff", linestyle="--", linewidth=1.5,
           label=f"expected = {EXPECTED['lat']}")
ax.axhspan(-90, 90, alpha=0.04, color="#00ff88")   # valid lat range
ax.axhspan(90, 250, alpha=0.06, color="#ff4444")   # invalid
ax.axhspan(-250, -90, alpha=0.06, color="#ff4444")
_style(ax, "tx_lat  (latitude)", "degrees")
ax.legend(fontsize=8, loc="upper right")

# --- (0,1) tx_lon ---
ax = axes[0, 1]
lons = [p["tx_lon"] for p in pkts_sorted]
ax.scatter(x_idx, lons, c=colors, s=90, zorder=5, edgecolors="white",
           linewidths=0.8)
ax.axhline(EXPECTED["lon"], color="#00ffff", linestyle="--", linewidth=1.5,
           label=f"expected = {EXPECTED['lon']}")
ax.axhspan(-180, 180, alpha=0.04, color="#00ff88")
ax.axhspan(180, 300, alpha=0.06, color="#ff4444")
ax.axhspan(-300, -180, alpha=0.06, color="#ff4444")
_style(ax, "tx_lon  (longitude)", "degrees")
ax.legend(fontsize=8, loc="upper right")

# --- (1,0) sats ---
ax = axes[1, 0]
sats = [p["sats"] for p in pkts_sorted]
ax.scatter(x_idx, sats, c=colors, s=90, zorder=5, edgecolors="white",
           linewidths=0.8)
ax.axhspan(EXPECTED["sats_low"], EXPECTED["sats_high"],
           alpha=0.20, color="#00ff88",
           label=f"expected {EXPECTED['sats_low']}-{EXPECTED['sats_high']}")
ax.set_yscale("symlog", linthresh=20)
_style(ax, "sats  (satellite count)", "# satellites (log)")
ax.legend(fontsize=8, loc="upper left")

# --- (1,1) utc ---
ax = axes[1, 1]
utcs = [p["utc"] for p in pkts_sorted]
ax.scatter(x_idx, utcs, c=colors, s=90, zorder=5, edgecolors="white",
           linewidths=0.8)
# Expected band: 1784893000 .. 1784895000 (~1 hour window on 2026-07-24)
ax.axhspan(EXPECTED["utc_base"], EXPECTED["utc_base"] + 2000,
           alpha=0.20, color="#00ff88",
           label=f"expected ~{EXPECTED['utc_base']} (2026-07-24)")
ax.set_yscale("log")
_style(ax, "utc  (unix timestamp)", "epoch seconds (log)")
ax.legend(fontsize=8, loc="upper left")

# Add a single legend explaining colors
from matplotlib.lines import Line2D
legend_elems = [
    Line2D([0], [0], marker="o", color="w", markerfacecolor="#39ff14",
           markersize=10, label="HF-LoRa-SF12 (phase 2) — only phase with valid sats"),
    Line2D([0], [0], marker="o", color="w", markerfacecolor="#ff4444",
           markersize=10, label="All other phases — payload garbage"),
    Line2D([0], [0], color="#00ffff", linestyle="--", linewidth=1.5,
           label="Expected value"),
]
fig2.legend(handles=legend_elems, loc="lower center", ncol=3,
            fontsize=9, framealpha=0.7, bbox_to_anchor=(0.5, -0.01))

fig2.tight_layout(rect=[0, 0.04, 1, 0.97])
out2 = os.path.join(DATA_DIR, "payload-corruption.png")
fig2.savefig(out2, dpi=150, facecolor="black")
plt.close(fig2)
print(f"Saved: {out2}")

print("\nDone.")
