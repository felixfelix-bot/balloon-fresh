#!/usr/bin/env python3
"""Generate proof plots from the latest rx_sweep capture log.

Outputs (dark-theme PNGs) to ./plots/:
  1. per_vs_mode.png     — PER (%) grouped bar chart, all 7 modes × 2 antennas
  2. rssi_vs_mode.png    — average RSSI (dBm) grouped bar chart, all modes × antennas
  3. per_vs_channel.png  — PER (%) per channel frequency (channel sweep phases only)

Parsing rules
-------------
* PHASE_RESULT lines carry: phase name, pktSize, rx, lost, per, rssi_avg, crc_err, garbage.
* Duplicate phase entries (firmware restart/retry) are AVERAGED into a single observation.
* SKIP phases (e.g. LF-LoRa-SF12-SKIP) are dropped — they ran no real measurement.
* RSSI = 0 on a phase means "no packet decoded, radio reported no signal".
  These are rendered as missing bars on the RSSI plot (NaN), not as 0 dBm.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
LOG = HERE / "rx_sweep_201758.log"
PLOTS = HERE / "plots"
PLOTS.mkdir(exist_ok=True)

# --- parse -----------------------------------------------------------------
phase_re = re.compile(
    r"PHASE_RESULT\s+(\d+)\s+(\S+)\s+pktSize=(\d+)\s+rx=(\d+)\s+unique=(\d+)"
    r"\s+lost=(\d+)\s+per=([\d.]+)\s+rssi_avg=(-?\d+)\s+rssi_min=(-?\d+)"
    r"\s+crc_err=(\d+)\s+garbage=(\d+).*?tx_fw=(\S+)"
)

raw: list[dict] = []
with open(LOG) as f:
    for line in f:
        m = phase_re.search(line)
        if not m:
            continue
        raw.append({
            "phase":   int(m.group(1)),
            "name":    m.group(2),
            "size":    int(m.group(3)),
            "rx":      int(m.group(4)),
            "lost":    int(m.group(6)),
            "per":     float(m.group(7)),
            "rssi":    int(m.group(8)),   # rssi_avg
            "crc_err": int(m.group(10)),
            "garbage": int(m.group(11)),
            "tx_fw":   m.group(12),       # "unknown" = TX online; "none" = TX offline
        })

def tx_online(e: dict) -> bool:
    """True if transmitter was actually running during this phase."""
    return e["tx_fw"] != "none"

# Deduplicate: average identical (name, size) entries from firmware retries.
# IMPORTANT: only average entries where TX was online. If a (name,size) has both
# online + offline entries, the offline one represents a TX failure mid-capture
# and is dropped to avoid corrupting the average (e.g. LF-LoRa-SF12-32 has one
# good rx=1 entry and one tx_fw=none entry that would otherwise average to 50%).
groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
for r in raw:
    groups[(r["name"], r["size"])].append(r)

phases: list[dict] = []
phases_offline: list[dict] = []   # kept separately for channel-sweep annotation
for (name, size), entries in groups.items():
    online = [e for e in entries if tx_online(e)]
    pool = online if online else entries   # fall back to all if none online
    n = len(pool)
    rec = {
        "name":    name,
        "size":    size,
        "rx":      sum(e["rx"] for e in pool) // n,
        "lost":    sum(e["lost"] for e in pool) // n,
        "per":     sum(e["per"] for e in pool) / n,
        "rssi":    sum(e["rssi"] for e in pool) // n,
        "crc_err": sum(e["crc_err"] for e in pool) // n,
        "garbage": sum(e["garbage"] for e in pool) // n,
        "tx_online": bool(online),
        "n_online": len(online),
        "n_total":  n,
    }
    (phases if online else phases_offline).append(rec)

# Drop SKIP phases (no real measurement)
phases = [p for p in phases if "SKIP" not in p["name"]]

# --- split antenna/mode ----------------------------------------------------
MODE_ORDER = ["LoRa-SF7", "LoRa-SF9", "LoRa-SF12",
              "FLRC-325", "FLRC-650", "FLRC-1300", "FLRC-2600"]
ANTENNAS = ["HF", "LF"]   # high-band / low-band antenna ports on dev board

# Phase names look like "HF-LoRa-SF7-32" or "LF-FLRC-325-255" — strip the
# trailing pkt size to recover (antenna, mode).
mode_re = re.compile(r"^(HF|LF)-(LoRa-SF\d+|FLRC-\d+)-\d+$")

# (antenna, mode) -> list of phase dicts (one per pkt size)
by_am: dict[tuple[str, str], list[dict]] = defaultdict(list)
unmatched: list[str] = []
for p in phases:
    name = p["name"]
    if name.startswith("CH-"):
        continue   # channel sweep handled separately
    m = mode_re.match(name)
    if not m:
        unmatched.append(name)
        continue
    by_am[(m.group(1), m.group(2))].append(p)

if unmatched:
    print(f"[warn] unmatched non-CH phase names: {unmatched}", file=sys.stderr)

# Aggregate per (antenna, mode): mean PER across pkt sizes;
# mean RSSI across pkt sizes where rssi != 0 (i.e. signal was heard).
agg: dict[tuple[str, str], dict] = {}
for ant in ANTENNAS:
    for mode in MODE_ORDER:
        ps = by_am.get((ant, mode), [])
        if not ps:
            agg[(ant, mode)] = {"per": np.nan, "rssi": np.nan, "n_sizes": 0,
                                "total_rx": 0, "note": "MISSING"}
            continue
        per = float(np.mean([p["per"] for p in ps]))
        rssi_vals = [p["rssi"] for p in ps if p["rssi"] != 0]
        rssi = float(np.mean(rssi_vals)) if rssi_vals else np.nan
        agg[(ant, mode)] = {
            "per": per, "rssi": rssi, "n_sizes": len(ps),
            "total_rx": sum(p["rx"] for p in ps), "note": "ok",
        }

# --- dark theme ------------------------------------------------------------
plt.rcParams.update({
    "figure.facecolor": "#0d1117",
    "axes.facecolor":   "#0d1117",
    "axes.edgecolor":   "#30363d",
    "axes.labelcolor":  "#c9d1d9",
    "xtick.color":      "#c9d1d9",
    "ytick.color":      "#c9d1d9",
    "text.color":       "#c9d1d9",
    "axes.titlecolor":  "#f0f6fc",
    "grid.color":       "#21262d",
    "grid.alpha":       0.8,
    "legend.facecolor": "#161b22",
    "legend.edgecolor": "#30363d",
    "font.size":        11,
})

ANT_COLORS = {"HF": "#58a6ff", "LF": "#f0883e"}   # blue / orange
PER_OK    = "#3fb950"   # green
PER_WARN  = "#d29922"   # yellow
PER_BAD   = "#f85149"   # red

def per_color(per: float) -> str:
    if np.isnan(per):       return "#484f58"
    if per < 25:            return PER_OK
    if per < 75:            return PER_WARN
    return PER_BAD


# ===========================================================================
# Plot 1: PER vs mode (grouped by antenna), all 7 modes
# ===========================================================================
fig, ax = plt.subplots(figsize=(13, 7))
x = np.arange(len(MODE_ORDER))
w = 0.38

for i, ant in enumerate(ANTENNAS):
    pers = [agg[(ant, m)]["per"] for m in MODE_ORDER]
    # NaN -> 0 for plotting, but mask visually with hatch
    pers_plot = [0.0 if (p is None or np.isnan(p)) else p for p in pers]
    bars = ax.bar(x + (i - 0.5) * w, pers_plot, w,
                  label=f"{ant} antenna", color=ANT_COLORS[ant],
                  edgecolor="#30363d", linewidth=0.6)
    for j, b in enumerate(bars):
        val = pers[j]
        if np.isnan(val):
            b.set_hatch("//")
            b.set_color("#484f58")
            ax.text(b.get_x() + b.get_width()/2, 2, "no data",
                    ha="center", va="bottom", color="#8b949e", fontsize=8,
                    rotation=90)
        else:
            ax.text(b.get_x() + b.get_width()/2, val + 1.5, f"{val:.0f}%",
                    ha="center", va="bottom", color=ANT_COLORS[ant],
                    fontsize=9, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(MODE_ORDER, rotation=20, ha="right")
ax.set_ylabel("Packet Error Rate (%)")
ax.set_ylim(0, 110)
ax.set_title("PER vs Mode — v4 Channel Sweep Capture (rx_sweep_201758)\n"
             "lower is better  |  bars averaged over pkt sizes 32/64/128/255",
             fontsize=13, pad=12)
ax.grid(axis="y", linestyle="--")
ax.axhline(50, color=PER_WARN, linestyle=":", alpha=0.4, linewidth=1)
ax.axhline(100, color=PER_BAD,  linestyle=":", alpha=0.3, linewidth=1)
ax.legend(loc="upper left", title="Antenna port")
fig.text(0.99, 0.01,
         "Source: balloon-range-tests/data/v4-channel-sweep/",
         ha="right", va="bottom", fontsize=8, color="#6e7681")
fig.tight_layout()
out1 = PLOTS / "per_vs_mode.png"
fig.savefig(out1, dpi=140, facecolor=fig.get_facecolor())
plt.close(fig)
print(f"[ok] {out1}")


# ===========================================================================
# Plot 2: RSSI vs mode (grouped by antenna)
# ===========================================================================
fig, ax = plt.subplots(figsize=(13, 7))
for i, ant in enumerate(ANTENNAS):
    rssis = [agg[(ant, m)]["rssi"] for m in MODE_ORDER]
    rssi_plot = [-110 if (r is None or np.isnan(r)) else r for r in rssis]
    bars = ax.bar(x + (i - 0.5) * w, rssi_plot, w,
                  label=f"{ant} antenna", color=ANT_COLORS[ant],
                  edgecolor="#30363d", linewidth=0.6)
    for j, b in enumerate(bars):
        val = rssis[j]
        if np.isnan(val):
            b.set_hatch("//")
            b.set_color("#484f58")
            ax.text(b.get_x() + b.get_width()/2, -108, "no signal",
                    ha="center", va="bottom", color="#8b949e", fontsize=8,
                    rotation=90)
        else:
            ax.text(b.get_x() + b.get_width()/2, val + 1.5, f"{val:.0f}",
                    ha="center", va="bottom", color=ANT_COLORS[ant],
                    fontsize=9, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(MODE_ORDER, rotation=20, ha="right")
ax.set_ylabel("Average RSSI (dBm)")
ax.set_ylim(-115, 0)
ax.invert_yaxis()  # stronger signal (less negative) sits higher visually after invert? keep standard
# Actually invert makes -110 at top — we want strong signal (near 0) high. Don't invert.
ax.set_ylim(-115, 0)
ax.set_title("Average RSSI vs Mode — v4 Channel Sweep Capture (rx_sweep_201758)\n"
             "higher (closer to 0) = stronger signal  |  hatched = no packet decoded",
             fontsize=13, pad=12)
ax.grid(axis="y", linestyle="--")
ax.legend(loc="lower left", title="Antenna port")
fig.text(0.99, 0.01,
         "Source: balloon-range-tests/data/v4-channel-sweep/",
         ha="right", va="bottom", fontsize=8, color="#6e7681")
fig.tight_layout()
out2 = PLOTS / "rssi_vs_mode.png"
fig.savefig(out2, dpi=140, facecolor=fig.get_facecolor())
plt.close(fig)
print(f"[ok] {out2}")


# ===========================================================================
# Plot 3: PER per channel frequency (channel sweep phases only)
# ===========================================================================
# Merge online + offline channel phases; flag each.
ch_online  = [p for p in phases         if p["name"].startswith("CH-")]
ch_offline = [p for p in phases_offline if p["name"].startswith("CH-")]

ch_re = re.compile(r"^CH-(\d+)-FLRC(\d+)-(\d+)$")
ch_data: list[dict] = []
for d in ch_online + ch_offline:
    m = ch_re.match(d["name"])
    if not m:
        continue
    ch_data.append({
        "freq":   int(m.group(1)),
        "per":    d["per"],
        "rssi":   d["rssi"],
        "rx":     d["rx"],
        "online": d["tx_online"],
        "name":   d["name"],
    })

# One entry per frequency (max PER wins if somehow duplicated).
freq_agg: dict[int, dict] = {}
for d in ch_data:
    f = d["freq"]
    if f not in freq_agg or d["per"] > freq_agg[f]["per"]:
        freq_agg[f] = d

ch_sorted = sorted(freq_agg.values(), key=lambda d: d["freq"])
freqs    = [d["freq"]   for d in ch_sorted]
pers     = [d["per"]    for d in ch_sorted]
rssi_ch  = [d["rssi"]   for d in ch_sorted]
online_flags = [d["online"] for d in ch_sorted]
n_online = sum(online_flags)
n_offline = len(online_flags) - n_online

fig, ax = plt.subplots(figsize=(14, 7))
# Bar color encodes BOTH band (sub-GHz vs 2.4 GHz) AND TX status.
# Solid = TX was online during this phase; hatched gray = TX offline (PER meaningless).
bar_colors = []
for f, online in zip(freqs, online_flags):
    if not online:
        bar_colors.append("#484f58")         # gray = TX offline
    elif f < 900:
        bar_colors.append("#f0883e")         # orange = EU868, TX online
    else:
        bar_colors.append("#58a6ff")         # blue = 2.4 GHz, TX online

bars = ax.bar(range(len(freqs)), pers, color=bar_colors,
              edgecolor="#30363d", linewidth=0.6, width=0.75)
for j, b in enumerate(bars):
    label = f"{pers[j]:.0f}%"
    if not online_flags[j]:
        label = "TX off"
    ax.text(b.get_x() + b.get_width()/2, pers[j] + 1,
            label, ha="center", va="bottom",
            color="#f0f6fc" if online_flags[j] else "#8b949e",
            fontsize=8.5, fontweight="bold" if online_flags[j] else "normal")
    if not online_flags[j]:
        b.set_hatch("//")

ax.set_xticks(range(len(freqs)))
ax.set_xticklabels([str(f) for f in freqs], rotation=45, ha="right")
ax.set_xlabel("Channel center frequency (MHz)")
ax.set_ylabel("PER (%)")
ax.set_ylim(0, 112)
ax.set_title(
    "PER per Channel Frequency — Channel Sweep Phases (FLRC-1300, 64-byte pkts)\n"
    f"TX was online on only {n_online}/{len(freqs)} channels "
    f"(all in 2.4 GHz band — TX operates on 868 MHz, so the sweep hit the WRONG band)",
    fontsize=12.5, pad=12)
ax.grid(axis="y", linestyle="--")
ax.axhline(100, color=PER_BAD, linestyle=":", alpha=0.4, linewidth=1)

# Band separator
sub_ghz_n = sum(1 for f in freqs if f < 900)
if 0 < sub_ghz_n < len(freqs):
    ax.axvline(sub_ghz_n - 0.5, color="#6e7681", linestyle="--", alpha=0.6)
    ax.text(sub_ghz_n / 2 - 0.5, 107, "EU868 band\n(TX home band)",
            ha="center", color="#f0883e", fontsize=9, fontweight="bold")
    ax.text(sub_ghz_n + (len(freqs) - sub_ghz_n) / 2 - 0.5, 107,
            "2.4 GHz ISM band",
            ha="center", color="#58a6ff", fontsize=9, fontweight="bold")

from matplotlib.patches import Patch
legend_handles = [
    Patch(facecolor="#58a6ff", edgecolor="#30363d",
          label=f"2.4 GHz, TX online ({sum(1 for f,o in zip(freqs,online_flags) if f>=2400 and o)})"),
    Patch(facecolor="#f0883e", edgecolor="#30363d",
          label=f"EU868, TX online ({sum(1 for f,o in zip(freqs,online_flags) if f<900 and o)})"),
    Patch(facecolor="#484f58", edgecolor="#30363d", hatch="//",
          label=f"TX offline — PER meaningless ({n_offline})"),
]
ax.legend(handles=legend_handles, loc="lower right", fontsize=9)

fig.text(0.99, 0.01,
         "Source: balloon-range-tests/data/v4-channel-sweep/  |  Capture: rx_sweep_201758",
         ha="right", va="bottom", fontsize=8, color="#6e7681")
fig.tight_layout()
out3 = PLOTS / "per_vs_channel.png"
fig.savefig(out3, dpi=140, facecolor=fig.get_facecolor())
plt.close(fig)
print(f"[ok] {out3}")

# --- summary print ---------------------------------------------------------
print("\n=== PLOT DATA SUMMARY ===")
print(f"{'Ant':<4} {'Mode':<10} {'PER%':>6} {'RSSI':>6} {'#sizes':>7} {'RXtot':>6}")
for ant in ANTENNAS:
    for mode in MODE_ORDER:
        a = agg[(ant, mode)]
        rssi_s = "  —" if np.isnan(a["rssi"]) else f"{a['rssi']:+.0f}"
        per_s  = "  —" if np.isnan(a["per"])  else f"{a['per']:.0f}"
        print(f"{ant:<4} {mode:<10} {per_s:>6} {rssi_s:>6} {a['n_sizes']:>7} {a['total_rx']:>6}")

print(f"\nChannel sweep: {len(ch_sorted)} frequencies, "
      f"PER range {min(pers):.0f}%–{max(pers):.0f}%")
print("All output PNGs in:", PLOTS)
