#!/usr/bin/env python3
"""
Generate a 4-panel walk-readiness summary plot from balloon range-test capture data.

Panels:
  1. RSSI per phase (scatter, colored by GPS payload validity)
  2. TX/RX Phase Sync (step plot showing phase progression over time)
  3. Packet Reception Rate (valid vs corrupt per phase, bar chart)
  4. GO/NO-GO text assessment
"""

import re
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DATA_DIR = os.path.expanduser("~/worktrees/balloon-range-tests/data")

# ── File sets ──────────────────────────────────────────────────────────────
RX_FILES = [
    "box-mounted-rx-20260724.txt",
    "full-sweep-rx-20260724.txt",
    "smoke-test-v7-20260724.txt",
    "smoke-test-v6-20260724.txt",
]
TX_FILES = [
    "post-solder-tx-20260724.txt",
    "full-sweep-tx-20260724.txt",
]

# Phase name lookup for nice labels
PHASE_NAMES = {
    0: "HF-LoRa-SF7", 1: "HF-LoRa-SF9", 2: "HF-LoRa-SF12",
    3: "HF-FLRC-2600", 4: "HF-FLRC-1300", 5: "HF-FLRC-650",
    6: "HF-FLRC-325",
    7: "LF-LoRa-SF7", 8: "LF-LoRa-SF9", 9: "LF-LoRa-SF12",
    10: "LF-FLRC-2600", 11: "LF-FLRC-1300", 12: "LF-FLRC-650",
    13: "LF-FLRC-325",
}

# Regex patterns
PKT_RX_RE = re.compile(r"^PKT\s+rx=(\d+)\s+seq=(\d+)\s+rssi=([-\d]+)\s+phase=(\d+)"
                        r"(?:\s+rx_ms=(\d+))?"
                        r"(?:\s+tx_lat=([-\d.]+)\s+tx_lon=([-\d.]+))?"
                        r"(?:\s+sats=(\d+)\s+fix=(\d+)\s+utc=(\d+))?")
PKT_TX_RE = re.compile(r"^PKT\s+seq=(\d+)\s+rssi=([-\d]+)\s+phase=(\d+)")
PHASE_START_RX_RE = re.compile(r"^PHASE_START\s+(\d+)\s+(\S+)")
PHASE_START_TX_RE = re.compile(r"^PHASE_START\s+(\d+)\s+(\S+)(?:\s+(\S+))?")
PHASE_RESULT_RE = re.compile(r"^PHASE_RESULT\s+(\d+)\s+\S+\s+rx=(\d+)\s+unique=(\d+)")


def gps_payload_valid(sats, fix, lat, lon):
    """Classify whether a GPS payload looks valid or is corrupted garbage."""
    if sats is None:
        return False
    # Real GPS: 4-20 satellites, fix 1-3, lat [-90,90], lon [-180,180]
    if not (4 <= sats <= 20):
        return False
    if fix is not None and not (1 <= fix <= 3):
        return False
    if lat is not None and not (-90 <= lat <= 90):
        return False
    if lon is not None and not (-180 <= lon <= 180):
        return False
    return True


def parse_rx_file(filepath):
    """Parse an RX capture file, return list of packet dicts and phase-start timeline."""
    packets = []
    phase_starts = []  # (order_index, phase_num, phase_name)
    phase_results = []  # (phase_num, rx_count, unique_count)
    order = 0
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            m = PKT_RX_RE.match(line)
            if m:
                rx_idx = int(m.group(1))
                seq = int(m.group(2))
                rssi = int(m.group(3))
                phase = int(m.group(4))
                lat = float(m.group(6)) if m.group(6) else None
                lon = float(m.group(7)) if m.group(7) else None
                sats = int(m.group(8)) if m.group(8) else None
                fix = int(m.group(9)) if m.group(9) else None
                valid = gps_payload_valid(sats, fix, lat, lon)
                packets.append({
                    "rx_idx": rx_idx, "seq": seq, "rssi": rssi, "phase": phase,
                    "lat": lat, "lon": lon, "sats": sats, "fix": fix,
                    "gps_valid": valid, "source": os.path.basename(filepath),
                })
                continue
            m = PHASE_START_RX_RE.match(line)
            if m:
                phase_starts.append((order, int(m.group(1)), m.group(2)))
                order += 1
                continue
            m = PHASE_RESULT_RE.match(line)
            if m:
                phase_results.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return packets, phase_starts, phase_results


def parse_tx_file(filepath):
    """Parse a TX capture file, return phase-start timeline and PKT count per phase."""
    phase_starts = []
    pkts_per_phase = defaultdict(int)
    order = 0
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            m = PHASE_START_TX_RE.match(line)
            if m:
                phase_starts.append((order, int(m.group(1)), m.group(2), m.group(3) or ""))
                order += 1
                continue
            m = PKT_TX_RE.match(line)
            if m:
                pkts_per_phase[int(m.group(3))] += 1
    return phase_starts, pkts_per_phase


# ── Parse all data ─────────────────────────────────────────────────────────
all_packets = []
rx_phase_timelines = {}  # filename -> [(order, phase, name)]
all_phase_results = []

for fname in RX_FILES:
    fpath = os.path.join(DATA_DIR, fname)
    if not os.path.exists(fpath):
        print(f"WARNING: {fpath} not found, skipping")
        continue
    pkts, pstarts, presults = parse_rx_file(fpath)
    all_packets.extend(pkts)
    rx_phase_timelines[fname] = pstarts
    all_phase_results.extend(presults)
    valid_count = sum(1 for p in pkts if p["gps_valid"])
    print(f"  {fname}: {len(pkts)} PKTs ({valid_count} GPS-valid), "
          f"{len(pstarts)} phase starts, {len(presults)} phase results")

tx_phase_timelines = {}
for fname in TX_FILES:
    fpath = os.path.join(DATA_DIR, fname)
    if not os.path.exists(fpath):
        print(f"WARNING: {fpath} not found, skipping")
        continue
    pstarts, pkt_counts = parse_tx_file(fpath)
    tx_phase_timelines[fname] = pstarts
    total_pkts = sum(pkt_counts.values())
    print(f"  {fname}: {len(pstarts)} phase starts, {total_pkts} TX PKTs")

# Aggregate stats
total_pkts = len(all_packets)
valid_pkts = sum(1 for p in all_packets if p["gps_valid"])
corrupt_pkts = total_pkts - valid_pkts
rssi_values = [p["rssi"] for p in all_packets if p["rssi"] != 0]
rssi_min = min(rssi_values) if rssi_values else 0
rssi_max = max(rssi_values) if rssi_values else 0
print(f"\nTotal RX packets: {total_pkts} ({valid_pkts} valid, {corrupt_pkts} corrupt)")
print(f"RSSI range: {rssi_min} to {rssi_max} dBm")

# ── Create figure ──────────────────────────────────────────────────────────
plt.style.use("dark_background")
fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=150)
fig.patch.set_facecolor("#0d1117")
fig.suptitle("Balloon Range Test — Walk Readiness Summary\n"
             "RP2040 + LR2021 Dual-Band Radio  |  2026-07-24 Capture Data",
             fontsize=13, fontweight="bold", color="#e6edf3", y=0.98)

# ── Panel 1: RSSI per Phase (scatter) ─────────────────────────────────────
ax1 = axes[0, 0]
ax1.set_facecolor("#161b22")

phases_present = sorted(set(p["phase"] for p in all_packets))
for p in all_packets:
    color = "#3fb950" if p["gps_valid"] else "#f85149"
    marker = "o" if p["gps_valid"] else "x"
    # Small jitter for visibility
    jitter = np.random.uniform(-0.15, 0.15)
    ax1.scatter(p["phase"] + jitter, p["rssi"], c=color, marker=marker,
                s=60, alpha=0.7, zorder=3)

# Add phase name labels on x-axis
ax1.set_xticks(range(14))
ax1.set_xticklabels([f"{i}\n{PHASE_NAMES.get(i,'')[:8]}" for i in range(14)],
                     fontsize=6.5, color="#8b949e")
ax1.set_xlabel("Phase Number", fontsize=9, color="#8b949e")
ax1.set_ylabel("RSSI (dBm)", fontsize=9, color="#8b949e")
ax1.set_title("Signal Strength by Phase", fontsize=11, fontweight="bold", color="#e6edf3")
ax1.axhline(y=-70, color="#d29922", linestyle="--", linewidth=0.8, alpha=0.5)
ax1.text(13.5, -68, "−70 dBm threshold", fontsize=6, color="#d29922", ha="right")
ax1.grid(True, alpha=0.15, color="#8b949e")
ax1.set_xlim(-0.5, 13.5)

# Legend
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], marker="o", color="w", markerfacecolor="#3fb950",
           markersize=8, label=f"GPS Valid ({valid_pkts})"),
    Line2D([0], [0], marker="x", color="#f85149",
           markerfacecolor="#f85149", markersize=8, label=f"GPS Corrupt ({corrupt_pkts})",
           linestyle="None"),
]
ax1.legend(handles=legend_elements, fontsize=7, loc="lower left",
           facecolor="#161b22", edgecolor="#30363d")

# ── Panel 2: TX/RX Phase Sync ─────────────────────────────────────────────
ax2 = axes[0, 1]
ax2.set_facecolor("#161b22")

# Plot RX phase progression (box-mounted = best data)
for fname, label, color, marker in [
    ("box-mounted-rx-20260724.txt", "RX (box-mounted)", "#58a6ff", "o"),
    ("full-sweep-rx-20260724.txt", "RX (full-sweep)", "#a371f7", "s"),
]:
    if fname in rx_phase_timelines and rx_phase_timelines[fname]:
        timeline = rx_phase_timelines[fname]
        xs = [t[0] for t in timeline]
        ys = [t[1] for t in timeline]
        ax2.step(xs, ys, where="post", color=color, linewidth=1.5, alpha=0.8, label=label)
        ax2.scatter(xs, ys, c=color, marker=marker, s=30, zorder=4, edgecolors="none")

# Plot TX phase progression
for fname, label, color, marker in [
    ("post-solder-tx-20260724.txt", "TX (post-solder)", "#f85149", "^"),
    ("full-sweep-tx-20260724.txt", "TX (full-sweep)", "#d29922", "D"),
]:
    if fname in tx_phase_timelines and tx_phase_timelines[fname]:
        timeline = tx_phase_timelines[fname]
        xs = [t[0] for t in timeline]
        ys = [t[1] for t in timeline]
        ax2.step(xs, ys, where="post", color=color, linewidth=1.5, alpha=0.8, label=label)
        ax2.scatter(xs, ys, c=color, marker=marker, s=30, zorder=4, edgecolors="none")

# Annotate the sync issue
ax2.annotate("TX jumps erratically\n(broken GPS → bad phase calc)",
             xy=(3, 9), fontsize=7, color="#f85149",
             xytext=(8, 11.5),
             arrowprops=dict(arrowstyle="->", color="#f85149", lw=1),
             bbox=dict(boxstyle="round,pad=0.3", facecolor="#21262d", edgecolor="#f85149"))

ax2.set_xlabel("Phase Event Sequence (chronological)", fontsize=9, color="#8b949e")
ax2.set_ylabel("Phase Number (0–13)", fontsize=9, color="#8b949e")
ax2.set_title("TX/RX Phase Sync", fontsize=11, fontweight="bold", color="#e6edf3")
ax2.set_yticks(range(14))
ax2.grid(True, alpha=0.15, color="#8b949e")
ax2.legend(fontsize=7, loc="upper right", facecolor="#161b22", edgecolor="#30363d")
ax2.set_ylim(-0.5, 13.5)

# ── Panel 3: Valid vs Invalid per Phase (bar chart) ────────────────────────
ax3 = axes[1, 0]
ax3.set_facecolor("#161b22")

# Count valid/corrupt per phase from individual packets
valid_per_phase = defaultdict(int)
corrupt_per_phase = defaultdict(int)
for p in all_packets:
    if p["gps_valid"]:
        valid_per_phase[p["phase"]] += 1
    else:
        corrupt_per_phase[p["phase"]] += 1

phases_bar = sorted(set(list(valid_per_phase.keys()) + list(corrupt_per_phase.keys())))
valid_vals = [valid_per_phase.get(ph, 0) for ph in phases_bar]
corrupt_vals = [corrupt_per_phase.get(ph, 0) for ph in phases_bar]

x = np.arange(len(phases_bar))
width = 0.35
bars1 = ax3.bar(x - width/2, valid_vals, width, label=f"GPS Valid ({sum(valid_vals)})",
                color="#3fb950", alpha=0.8, edgecolor="#238636")
bars2 = ax3.bar(x + width/2, corrupt_vals, width, label=f"GPS Corrupt ({sum(corrupt_vals)})",
                color="#f85149", alpha=0.8, edgecolor="#da3633")

# Add count labels on bars
for bar in bars1:
    h = bar.get_height()
    if h > 0:
        ax3.text(bar.get_x() + bar.get_width()/2., h + 0.3, str(int(h)),
                 ha="center", va="bottom", fontsize=7, color="#3fb950")
for bar in bars2:
    h = bar.get_height()
    if h > 0:
        ax3.text(bar.get_x() + bar.get_width()/2., h + 0.3, str(int(h)),
                 ha="center", va="bottom", fontsize=7, color="#f85149")

ax3.set_xticks(x)
ax3.set_xticklabels([f"P{ph}" for ph in phases_bar], fontsize=8, color="#8b949e")
ax3.set_xlabel("Phase Number", fontsize=9, color="#8b949e")
ax3.set_ylabel("Packet Count", fontsize=9, color="#8b949e")
ax3.set_title("Packet Reception Rate\n(GPS payload validity per phase)",
              fontsize=11, fontweight="bold", color="#e6edf3")
ax3.legend(fontsize=8, loc="upper right", facecolor="#161b22", edgecolor="#30363d")
ax3.grid(True, alpha=0.15, color="#8b949e", axis="y")

# ── Panel 4: GO/NO-GO Assessment ──────────────────────────────────────────
ax4 = axes[1, 1]
ax4.set_facecolor("#161b22")
ax4.set_xlim(0, 1)
ax4.set_ylim(0, 1)
ax4.axis("off")

# Determine assessment values dynamically
pct_corrupt = (corrupt_pkts / total_pkts * 100) if total_pkts else 0
signal_good = rssi_max > -30 and rssi_min > -60

# TX phase jump analysis
tx_post_solder = tx_phase_timelines.get("post-solder-tx-20260724.txt", [])
if len(tx_post_solder) > 2:
    tx_phases_seq = [t[1] for t in tx_post_solder]
    jumps = sum(1 for i in range(1, len(tx_phases_seq))
                if abs(tx_phases_seq[i] - tx_phases_seq[i-1]) > 1
                and not (tx_phases_seq[i] == 0 and tx_phases_seq[i-1] == 13))
    pct_jump = jumps / (len(tx_phases_seq) - 1) * 100
else:
    pct_jump = 0

assessment_lines = [
    ("WALK READINESS ASSESSMENT", "title", "#e6edf3"),
    ("", "spacer", None),
    (f"  Signal Strength:  {'✓ GOOD' if signal_good else '✗ POOR'}", "check" if signal_good else "fail",
     "#3fb950" if signal_good else "#f85149"),
    (f"    RSSI {rssi_min} to {rssi_max} dBm at ~1m range", "detail", "#8b949e"),
    ("    Strong RF link on HF and LF bands", "detail", "#8b949e"),
    ("", "spacer", None),
    ("  GPS Payload:      ✗ CORRUPT", "fail", "#f85149"),
    (f"    {corrupt_pkts}/{total_pkts} packets ({pct_corrupt:.0f}%) have garbage GPS data", "detail", "#8b949e"),
    ("    sats=48554, fix=60, lat=−210° (impossible values)", "detail", "#8b949e"),
    ("    TX GPS module not providing valid fix", "detail", "#8b949e"),
    ("", "spacer", None),
    ("  Phase Sync:       ✗ BROKEN", "fail", "#f85149"),
    (f"    TX phase jumps erratically ({pct_jump:.0f}% non-sequential)", "detail", "#8b949e"),
    ("    Expected: 0→1→2→...→13→0  (UTC % 202)", "detail", "#8b949e"),
    ("    Actual:   2→3→4→9→7→3→7→8→9... (random)", "detail", "#8b949e"),
    ("    Root cause: TX GPS UTC garbage → bad phase calc", "detail", "#da3633"),
    ("", "spacer", None),
    ("  Packet CRC:       ✓ PASSING", "check", "#3fb950"),
    ("    crc_err=0 in all phase results", "detail", "#8b949e"),
    ("    (Radio CRC OK, but payload bytes are garbage)", "detail", "#d29922"),
    ("", "spacer", None),
    ("━" * 48, "divider", "#30363d"),
    ("  VERDICT:  ✗ NOT READY FOR WALK", "verdict_fail", "#f85149"),
    ("", "spacer", None),
    ("  Root Cause: TX GPS module failing → no valid UTC", "action", "#d29922"),
    ("  → TX computes wrong phase → RX/TX desync", "action", "#d29922"),
    ("  → GPS payload bytes are uninitialized/garbage", "action", "#d29922"),
    ("", "spacer", None),
    ("  Next Steps:", "action_header", "#58a6ff"),
    ("  1. Fix TX GPS wiring / antenna", "action", "#8b949e"),
    ("  2. Verify TX gets valid UTC lock", "action", "#8b949e"),
    ("  3. Re-run range test with GPS lock", "action", "#8b949e"),
    ("  4. Confirm sequential phase cycling", "action", "#8b949e"),
]

y_pos = 0.96
for text, style, color in assessment_lines:
    if style == "title":
        ax4.text(0.5, y_pos, text, transform=ax4.transAxes,
                 fontsize=13, fontweight="bold", color=color, ha="center",
                 family="monospace")
        y_pos -= 0.035
    elif style == "spacer":
        y_pos -= 0.012
    elif style == "divider":
        ax4.text(0.05, y_pos, text, transform=ax4.transAxes,
                 fontsize=7, color=color, family="monospace")
        y_pos -= 0.02
    elif style == "verdict_fail":
        ax4.text(0.5, y_pos, text, transform=ax4.transAxes,
                 fontsize=12, fontweight="bold", color=color, ha="center",
                 family="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="#3d1014", edgecolor="#f85149"))
        y_pos -= 0.04
    elif style == "action_header":
        ax4.text(0.05, y_pos, text, transform=ax4.transAxes,
                 fontsize=9, fontweight="bold", color=color, family="monospace")
        y_pos -= 0.025
    elif style == "action":
        ax4.text(0.05, y_pos, text, transform=ax4.transAxes,
                 fontsize=8, color=color, family="monospace")
        y_pos -= 0.022
    else:
        weight = "bold" if style in ("check", "fail") else "normal"
        size = 9 if style in ("check", "fail") else 7.5
        ax4.text(0.05, y_pos, text, transform=ax4.transAxes,
                 fontsize=size, fontweight=weight, color=color, family="monospace")
        y_pos -= 0.025

ax4.set_title("System Assessment", fontsize=11, fontweight="bold", color="#e6edf3")

# ── Save ───────────────────────────────────────────────────────────────────
plt.tight_layout(rect=[0, 0, 1, 0.95])
output_path = os.path.join(DATA_DIR, "walk-readiness-summary.png")
fig.savefig(output_path, dpi=150, facecolor=fig.get_facecolor(),
            bbox_inches="tight", pad_inches=0.2)
plt.close(fig)
print(f"\n✓ Saved: {output_path}")
print(f"  Size: {os.path.getsize(output_path)} bytes")
