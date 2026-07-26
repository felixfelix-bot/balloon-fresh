#!/usr/bin/env python3
"""Generate plots from the walk test data (2026-07-24).

Maps RX packet rx_ms timestamps to wall-clock time via TIME_DIFF laptop_utc anchors,
then correlates with phone GPS distance.
"""
import re
import csv
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# ── Paths ──────────────────────────────────────────────────────────────────
DATA_DIR = os.path.expanduser("~/worktrees/balloon-range-tests/data")
RX_FILE = os.path.join(DATA_DIR, "walk-official-rx.txt")
GPS_FILE = os.path.join(DATA_DIR, "phone-gps-walk-20260724.csv")
PLOT_DIR = os.path.join(DATA_DIR, "plots")
os.makedirs(PLOT_DIR, exist_ok=True)

# ── Phase names ────────────────────────────────────────────────────────────
PHASE_NAMES = {
    0: "HF-LoRa-SF7", 1: "HF-LoRa-SF9", 2: "HF-LoRa-SF12",
    3: "HF-FLRC-2600", 4: "HF-FLRC-1300", 5: "HF-FLRC-650", 6: "HF-FLRC-325",
    7: "LF-LoRa-SF7", 8: "LF-LoRa-SF9", 9: "LF-LoRa-SF12",
    10: "LF-FLRC-2600", 11: "LF-FLRC-1300", 12: "LF-FLRC-650", 13: "LF-FLRC-325",
}

# Colors: HF = warm, LF = cool; FLRC = circle, LoRa = diamond
MODE_COLORS = {
    "HF-FLRC-2600": "#e41a1c", "HF-FLRC-1300": "#ff7f00", "HF-FLRC-650": "#fdbf6f", "HF-FLRC-325": "#ffff99",
    "LF-FLRC-2600": "#377eb8", "LF-FLRC-1300": "#4daf4a", "LF-FLRC-650": "#a6cee3", "LF-FLRC-325": "#b2df8a",
    "HF-LoRa-SF7": "#984ea3", "HF-LoRa-SF9": "#c7812e", "HF-LoRa-SF12": "#999999",
    "LF-LoRa-SF7": "#f781bf", "LF-LoRa-SF9": "#a65628", "LF-LoRa-SF12": "#666666",
}

HOME_LAT, HOME_LON = 32.6390, -16.9463

# ── Parse RX capture file ─────────────────────────────────────────────────
# Collect interleaved PKT and TIME_DIFF events with line numbers
pkt_re = re.compile(
    r'PKT rx=(\d+) seq=(\d+) rssi=(-?\d+) phase=(\d+) rx_ms=(\d+)'
)
td_re = re.compile(r'TIME_DIFF .*laptop_utc=(\d+)')

events = []  # (line_num, type, dict)
with open(RX_FILE) as f:
    for i, line in enumerate(f):
        if line.startswith("PKT "):
            m = pkt_re.search(line)
            if m:
                events.append((i, "PKT", {
                    "rx_count": int(m.group(1)),
                    "seq": int(m.group(2)),
                    "rssi": int(m.group(3)),
                    "phase": int(m.group(4)),
                    "rx_ms": int(m.group(5)),
                }))
        elif line.startswith("TIME_DIFF"):
            m = td_re.search(line)
            if m:
                events.append((i, "TIME_DIFF", {"laptop_utc": int(m.group(1))}))

print(f"Parsed {sum(1 for _,t,_ in events if t=='PKT')} PKT lines, "
      f"{sum(1 for _,t,_ in events if t=='TIME_DIFF')} TIME_DIFF lines")

# ── Build rx_ms → laptop_utc calibration ──────────────────────────────────
# For each PKT, grab the laptop_utc from the nearest TIME_DIFF line (by position).
# Then linear-fit laptop_utc = a * rx_ms + b for sub-second precision.
pkt_raw = []  # (rx_ms, laptop_utc_approx, rssi, phase, line_num)
last_laptop_utc = None
for line_num, etype, data in events:
    if etype == "TIME_DIFF":
        last_laptop_utc = data["laptop_utc"]
    elif etype == "PKT":
        pkt_raw.append({
            "rx_ms": data["rx_ms"],
            "laptop_utc_approx": last_laptop_utc,
            "rssi": data["rssi"],
            "phase": data["phase"],
            "line_num": line_num,
        })

rx_ms_arr = np.array([p["rx_ms"] for p in pkt_raw], dtype=float)
utc_arr = np.array([p["laptop_utc_approx"] for p in pkt_raw], dtype=float)

# Linear fit: laptop_utc = a * rx_ms + b
coeffs = np.polyfit(rx_ms_arr, utc_arr, 1)
a, b = coeffs
print(f"Calibration: laptop_utc = {a:.10f} * rx_ms + {b:.2f}")
print(f"  → rx_ms rate ≈ {1/a:.6f} ms per real-ms (should be ≈1.0)")

# Compute precise laptop_utc for each packet
for p in pkt_raw:
    p["laptop_utc"] = a * p["rx_ms"] + b
    p["laptop_utc_ms"] = p["laptop_utc"] * 1000.0  # to ms for GPS matching

# ── Parse phone GPS CSV ───────────────────────────────────────────────────
gps_lat = []
gps_lon = []
gps_ts_ms = []
gps_dist = []
gps_elev = []
with open(GPS_FILE) as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            gps_lat.append(float(row["lat"]))
            gps_lon.append(float(row["lon"]))
            gps_ts_ms.append(float(row["timestamp_ms"]))
            gps_dist.append(float(row["distance"]))
            gps_elev.append(float(row["elevation"]))
        except (ValueError, KeyError):
            continue

gps_lat = np.array(gps_lat)
gps_lon = np.array(gps_lon)
gps_ts_ms = np.array(gps_ts_ms)
gps_dist = np.array(gps_dist)
gps_elev = np.array(gps_elev)

print(f"GPS: {len(gps_lat)} points, distance 0–{gps_dist[-1]:.0f} m, "
      f"time {(gps_ts_ms[-1]-gps_ts_ms[0])/1000:.0f} s span")

# ── Match each packet to nearest GPS point ────────────────────────────────
gps_ts_sorted = gps_ts_ms  # already sorted
# For each packet's laptop_utc_ms, find nearest GPS timestamp
for p in pkt_raw:
    idx = np.argmin(np.abs(gps_ts_sorted - p["laptop_utc_ms"]))
    p["gps_idx"] = idx
    p["dist_m"] = gps_dist[idx]
    p["lat"] = gps_lat[idx]
    p["lon"] = gps_lon[idx]

# Compute time offset from walk start for each packet
walk_start_utc = gps_ts_ms[0] / 1000.0  # seconds
for p in pkt_raw:
    p["walk_time_min"] = (p["laptop_utc"] - walk_start_utc) / 60.0

# ── Aggregate by phase ────────────────────────────────────────────────────
phase_pkts = {}
for p in pkt_raw:
    phase_pkts.setdefault(p["phase"], []).append(p)

print("\nPackets per phase:")
for ph in sorted(phase_pkts.keys()):
    pkts = phase_pkts[ph]
    rssis = [p["rssi"] for p in pkts]
    print(f"  {ph:2d} {PHASE_NAMES.get(ph,'?'):16s}: {len(pkts):3d} pkts, "
          f"RSSI {min(rssis)} to {max(rssis)}, mean {np.mean(rssis):.1f}")

# ══════════════════════════════════════════════════════════════════════════
# PLOT 1: RSSI vs Distance (the money plot)
# ══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 7))

for ph in sorted(phase_pkts.keys()):
    pkts = phase_pkts[ph]
    name = PHASE_NAMES.get(ph, f"Phase {ph}")
    color = MODE_COLORS.get(name, "#333333")
    marker = "o" if "FLRC" in name else "D"
    dists = [p["dist_m"] for p in pkts]
    rssis = [p["rssi"] for p in pkts]
    ax.scatter(dists, rssis, c=color, marker=marker, s=40, label=name,
              edgecolors='white', linewidths=0.3, zorder=3, alpha=0.85)

ax.set_xlabel("Distance from Home (m)", fontsize=13)
ax.set_ylabel("RSSI (dBm)", fontsize=13)
ax.set_title("Signal Strength vs Distance — Walk Test 2026-07-24", fontsize=14, fontweight='bold')
ax.legend(fontsize=8, ncol=2, loc='lower left', framealpha=0.9)
ax.grid(True, alpha=0.3)
ax.set_xlim(-100, max(gps_dist) + 100)
ax.axhline(y=-90, color='red', linestyle='--', alpha=0.5, label='_noise floor')
ax.text(max(gps_dist) * 0.85, -89, '~noise floor', fontsize=8, color='red', alpha=0.7)
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "01_rssi_vs_distance.png"), dpi=150)
plt.close()
print("✓ Saved 01_rssi_vs_distance.png")

# ══════════════════════════════════════════════════════════════════════════
# PLOT 2: RSSI over Time
# ══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(14, 6))

for ph in sorted(phase_pkts.keys()):
    pkts = phase_pkts[ph]
    name = PHASE_NAMES.get(ph, f"Phase {ph}")
    color = MODE_COLORS.get(name, "#333333")
    marker = "o" if "FLRC" in name else "D"
    times = [p["walk_time_min"] for p in pkts]
    rssis = [p["rssi"] for p in pkts]
    ax.scatter(times, rssis, c=color, marker=marker, s=40, label=name,
              edgecolors='white', linewidths=0.3, zorder=3, alpha=0.85)

ax.set_xlabel("Time from Walk Start (min)", fontsize=13)
ax.set_ylabel("RSSI (dBm)", fontsize=13)
ax.set_title("RSSI over Time — Walk Test 2026-07-24", fontsize=14, fontweight='bold')
ax.legend(fontsize=8, ncol=2, loc='lower right', framealpha=0.9)
ax.grid(True, alpha=0.3)
# Shade the time range where walk was happening
walk_end_min = (gps_ts_ms[-1] / 1000.0 - walk_start_utc) / 60.0
ax.axvspan(0, walk_end_min, alpha=0.05, color='green')
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "02_rssi_over_time.png"), dpi=150)
plt.close()
print("✓ Saved 02_rssi_over_time.png")

# ══════════════════════════════════════════════════════════════════════════
# PLOT 3: Packets per Mode (bar chart)
# ══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 6))

# Sort phases: FLRC first (HF then LF), then LoRa
flrc_phases = sorted([ph for ph in phase_pkts if "FLRC" in PHASE_NAMES.get(ph, "")])
lora_phases = sorted([ph for ph in phase_pkts if "LoRa" in PHASE_NAMES.get(ph, "")])
all_phases = flrc_phases + lora_phases

names = [PHASE_NAMES.get(ph, f"P{ph}") for ph in all_phases]
counts = [len(phase_pkts[ph]) for ph in all_phases]
colors = [MODE_COLORS.get(n, "#888") for n in names]

bars = ax.bar(range(len(all_phases)), counts, color=colors, edgecolor='black', linewidth=0.5)
ax.set_xticks(range(len(all_phases)))
ax.set_xticklabels(names, rotation=45, ha='right', fontsize=9)
ax.set_ylabel("Packet Count", fontsize=13)
ax.set_title("Packets Received per Mode — Walk Test 2026-07-24", fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, axis='y')

# Add count labels on bars
for bar, count in zip(bars, counts):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
            str(count), ha='center', va='bottom', fontsize=9, fontweight='bold')

# Add separator between FLRC and LoRa
if flrc_phases and lora_phases:
    sep_x = len(flrc_phases) - 0.5
    ax.axvline(x=sep_x, color='gray', linestyle='--', alpha=0.5)
    ax.text(sep_x/2, max(counts)*0.95, 'FLRC', ha='center', fontsize=11, fontweight='bold', alpha=0.6)
    ax.text(sep_x + len(lora_phases)/2, max(counts)*0.95, 'LoRa', ha='center', fontsize=11, fontweight='bold', alpha=0.6)

plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "03_packets_per_mode.png"), dpi=150)
plt.close()
print("✓ Saved 03_packets_per_mode.png")

# ══════════════════════════════════════════════════════════════════════════
# PLOT 4: Phone GPS Walk Track
# ══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(10, 10))

# Color by time
time_frac = (gps_ts_ms - gps_ts_ms[0]) / (gps_ts_ms[-1] - gps_ts_ms[0])
sc = ax.scatter(gps_lon, gps_lat, c=time_frac, cmap='viridis', s=15, zorder=2)
plt.colorbar(sc, ax=ax, label='Time (fraction of walk)', shrink=0.7)

# Start/end markers
ax.scatter(gps_lon[0], gps_lat[0], c='lime', s=150, marker='o', zorder=5,
           edgecolors='black', linewidths=1.5, label='Start')
ax.scatter(gps_lon[-1], gps_lat[-1], c='red', s=150, marker='s', zorder=5,
           edgecolors='black', linewidths=1.5, label='End')

# Home position
ax.scatter(HOME_LON, HOME_LAT, c='gold', s=200, marker='*', zorder=6,
           edgecolors='black', linewidths=1.5, label='Home (RX balcony)')

ax.set_xlabel("Longitude", fontsize=12)
ax.set_ylabel("Latitude", fontsize=12)
ax.set_title("Phone GPS Walk Track — 2026-07-24 (5.7 km, ~53 min)", fontsize=14, fontweight='bold')
ax.legend(fontsize=10, loc='upper left')
ax.grid(True, alpha=0.3)
ax.set_aspect('equal', adjustable='datalim')
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "04_gps_walk_track.png"), dpi=150)
plt.close()
print("✓ Saved 04_gps_walk_track.png")

# ══════════════════════════════════════════════════════════════════════════
# PLOT 5: RSSI Distribution by Mode (box plot)
# ══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 7))

# Only include modes that actually got packets, sorted like plot 3
modes_with_data = [ph for ph in all_phases if len(phase_pkts.get(ph, [])) > 0]
box_data = [[p["rssi"] for p in phase_pkts[ph]] for ph in modes_with_data]
box_names = [PHASE_NAMES.get(ph, f"P{ph}") for ph in modes_with_data]
box_colors = [MODE_COLORS.get(n, "#888") for n in box_names]

bp = ax.boxplot(box_data, tick_labels=box_names, patch_artist=True, widths=0.6,
                medianprops=dict(color='black', linewidth=2))
for patch, color in zip(bp['boxes'], box_colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

# Overlay individual points
for i, (data, color) in enumerate(zip(box_data, box_colors)):
    x = np.random.normal(i + 1, 0.04, size=len(data))
    ax.scatter(x, data, c=color, s=20, zorder=3, alpha=0.6, edgecolors='black', linewidths=0.3)

ax.set_ylabel("RSSI (dBm)", fontsize=13)
ax.set_title("RSSI Distribution by Mode — Walk Test 2026-07-24", fontsize=14, fontweight='bold')
ax.set_xticklabels(box_names, rotation=45, ha='right', fontsize=9)
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "05_rssi_distribution.png"), dpi=150)
plt.close()
print("✓ Saved 05_rssi_distribution.png")

# ══════════════════════════════════════════════════════════════════════════
# PLOT 6: Combined Walk Track + Signal (map view colored by RSSI)
# ══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 10))

# Plot the full walk path in light gray
ax.plot(gps_lon, gps_lat, color='lightgray', linewidth=1, zorder=1, alpha=0.5)
ax.scatter(gps_lon, gps_lat, c='lightgray', s=5, zorder=1, alpha=0.3)

# Plot packet locations colored by RSSI
pkt_lons = [p["lon"] for p in pkt_raw]
pkt_lats = [p["lat"] for p in pkt_raw]
pkt_rssis = [p["rssi"] for p in pkt_raw]

sc = ax.scatter(pkt_lons, pkt_lats, c=pkt_rssis, cmap='RdYlGn', s=40,
                vmin=-60, vmax=-50, zorder=4, edgecolors='black', linewidths=0.5)
cbar = plt.colorbar(sc, ax=ax, label='RSSI (dBm)', shrink=0.7)

# Home position
ax.scatter(HOME_LON, HOME_LAT, c='gold', s=250, marker='*', zorder=6,
           edgecolors='black', linewidths=1.5, label='Home (RX)')

# Start/end
ax.scatter(gps_lon[0], gps_lat[0], c='lime', s=120, marker='o', zorder=5,
           edgecolors='black', linewidths=1, label='Walk Start')
ax.scatter(gps_lon[-1], gps_lat[-1], c='red', s=120, marker='s', zorder=5,
           edgecolors='black', linewidths=1, label='Walk End')

ax.set_xlabel("Longitude", fontsize=12)
ax.set_ylabel("Latitude", fontsize=12)
ax.set_title("Signal Reception Map — Where Packets Were Received\nWalk Test 2026-07-24",
             fontsize=14, fontweight='bold')
ax.legend(fontsize=10, loc='upper left')
ax.grid(True, alpha=0.2)
ax.set_aspect('equal', adjustable='datalim')
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "06_signal_map.png"), dpi=150)
plt.close()
print("✓ Saved 06_signal_map.png")

# ── Summary ───────────────────────────────────────────────────────────────
total_pkts = len(pkt_raw)
flrc_pkts = sum(1 for p in pkt_raw if "FLRC" in PHASE_NAMES.get(p["phase"], ""))
lora_pkts = sum(1 for p in pkt_raw if "LoRa" in PHASE_NAMES.get(p["phase"], ""))
dist_range = (min(p["dist_m"] for p in pkt_raw), max(p["dist_m"] for p in pkt_raw))

print(f"\n{'='*60}")
print(f"SUMMARY: {total_pkts} total packets")
print(f"  FLRC: {flrc_pkts}, LoRa: {lora_pkts}")
print(f"  Distance range with signal: {dist_range[0]:.0f} – {dist_range[1]:.0f} m")
print(f"  RSSI range: {min(p['rssi'] for p in pkt_raw)} to {max(p['rssi'] for p in pkt_raw)} dBm")
print(f"  Walk duration: {(gps_ts_ms[-1]-gps_ts_ms[0])/1000/60:.1f} min")
print(f"{'='*60}")
print(f"\nAll plots saved to {PLOT_DIR}/")
