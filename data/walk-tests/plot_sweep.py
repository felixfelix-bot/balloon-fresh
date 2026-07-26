#!/usr/bin/env python3
"""
Plot sweep capture data from balloon-fresh walk-tests logs.

Reads PHASE_RESULT / PKT / BER lines, parses them (handles the timestamp
prefix), and produces 6 PNG plots.
"""
import os
import re
import sys
import glob
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.style.use("dark_background")
plt.rcParams.update({
    "figure.figsize": (14, 8),
    "font.size": 13,
    "axes.titlesize": 18,
    "axes.labelsize": 15,
    "xtick.labelsize": 11,
    "ytick.labelsize": 12,
    "legend.fontsize": 12,
    "axes.grid": True,
    "grid.alpha": 0.25,
})

DATA_DIR = os.path.expanduser("~/repos/balloon-fresh/data/walk-tests")
PLOTS_ROOT = os.path.join(DATA_DIR, "plots")
os.makedirs(PLOTS_ROOT, exist_ok=True)

# ---------------------------------------------------------------- parse
def find_best_log(strategy="most_complete"):
    """Pick a log file with PHASE_RESULT lines.

    strategy='most_complete' -> the log with the most PHASE_RESULT lines.
    strategy='most_recent'   -> the most-recently-modified log that has any.
    """
    candidates = sorted(glob.glob(os.path.join(DATA_DIR, "*.log")),
                        key=os.path.getmtime, reverse=True)
    if strategy == "most_recent":
        for path in candidates:
            try:
                with open(path, errors="replace") as fh:
                    if fh.read().count("PHASE_RESULT") > 0:
                        with open(path, errors="replace") as fh2:
                            n = fh2.read().count("PHASE_RESULT")
                        return path, n
            except OSError:
                continue
        return None, 0
    # most_complete
    best, best_count = None, 0
    for path in candidates:
        try:
            with open(path, errors="replace") as fh:
                n = fh.read().count("PHASE_RESULT")
        except OSError:
            continue
        if n > best_count:
            best_count = n
            best = path
    return best, best_count

# Allow a CLI arg to override:  python3 plot_sweep.py [most_complete|most_recent|/path/to.log]
arg = sys.argv[1] if len(sys.argv) > 1 else "most_complete"
if arg in ("most_complete", "most_recent"):
    LOG_PATH, n_results = find_best_log(strategy=arg)
elif os.path.isfile(arg):
    LOG_PATH = arg
    with open(LOG_PATH, errors="replace") as fh:
        n_results = fh.read().count("PHASE_RESULT")
else:
    print(f"ERROR: unknown argument {arg!r}", file=sys.stderr)
    sys.exit(2)

if not LOG_PATH or n_results == 0:
    print("ERROR: no log with PHASE_RESULT lines found", file=sys.stderr)
    sys.exit(1)

# Output subdir named after the log so multiple captures can coexist.
log_stem = os.path.splitext(os.path.basename(LOG_PATH))[0]
OUT_DIR = os.path.join(PLOTS_ROOT, log_stem)
os.makedirs(OUT_DIR, exist_ok=True)
print(f"Using log: {LOG_PATH}  ({n_results} PHASE_RESULT lines)")
print(f"Output dir: {OUT_DIR}")

# regexes
RE_PHASE_RESULT = re.compile(
    r"PHASE_RESULT\s+(\d+)\s+(\S+)\s+"
    r"pktSize=(\d+)\s+rx=(\d+)\s+unique=(\d+)\s+lost=(\d+)\s+"
    r"per=([\d.]+)\s+rssi_avg=(-?[\d.]+)\s+rssi_min=(-?[\d.]+)\s+"
    r"crc_err=(\d+)\s+garbage=(\d+)\s+"
    r"tx_lat=(-?[\d.]+)\s+tx_lon=(-?[\d.]+)\s+sats=(\d+)\s+fix=(\d+)\s+"
    r"utc=(\d+)"
)
RE_PKT = re.compile(
    r"PKT\s+rx=(\d+)\s+seq=(\d+)\s+rssi=(-?[\d.]+)\s+phase=(\d+)\s+"
    r"rx_ms=(\d+)\s+tx_lat=(-?[\d.]+)\s+tx_lon=(-?[\d.]+)\s+sats=(\d+)\s+"
    r"fix=(\d+)\s+utc=(\d+)"
)
RE_PHASE_START = re.compile(r"PHASE_START\s+(\d+)\s+(\S+)\s+pktSize=(\d+)")

phase_results = []  # list of dicts
pkts = []           # list of dicts
phase_start_ts = {}  # phase_num -> first_seen line timestamp (millis via rx_ms)

# We need to keep the order of PHASE_RESULT appearance (chronological).
phase_order = []
seen_phase_names = set()

with open(LOG_PATH, errors="replace") as fh:
    for line in fh:
        m = RE_PHASE_RESULT.search(line)
        if m:
            (pnum, pname, psize, rx, unique, lost, per,
             rssi_avg, rssi_min, crc_err, garbage,
             tx_lat, tx_lon, sats, fix, utc) = m.groups()
            d = dict(
                phase_num=int(pnum), name=pname, pktSize=int(psize),
                rx=int(rx), unique=int(unique), lost=int(lost),
                per=float(per), rssi_avg=float(rssi_avg),
                rssi_min=float(rssi_min), crc_err=int(crc_err),
                garbage=int(garbage), tx_lat=float(tx_lat),
                tx_lon=float(tx_lon), sats=int(sats), fix=int(fix),
                utc=int(utc),
            )
            phase_results.append(d)
            if pname not in seen_phase_names:
                seen_phase_names.add(pname)
                phase_order.append(pname)
            continue
        m = RE_PKT.search(line)
        if m:
            (rx, seq, rssi, phase, rx_ms, tx_lat, tx_lon,
             sats, fix, utc) = m.groups()
            pkts.append(dict(
                rx=int(rx), seq=int(seq), rssi=float(rssi),
                phase=int(phase), rx_ms=int(rx_ms),
                tx_lat=float(tx_lat), tx_lon=float(tx_lon),
                sats=int(sats), fix=int(fix), utc=int(utc),
            ))
            continue

print(f"Parsed: {len(phase_results)} PHASE_RESULT, {len(pkts)} PKT entries")

# ---------------------------------------------------------------- helpers
COLOR_LORA = "#3b82f6"   # blue
COLOR_FLRC = "#f59e0b"   # orange/amber
COLOR_HF   = "#ef4444"   # red (2.4 GHz)
COLOR_LF   = "#22c55e"   # green (868 MHz)

def classify(name):
    """Return (mod_type, band) from a phase name."""
    n = name.upper()
    if "LORA" in n:
        mod = "LoRa"
    elif "FLRC" in n:
        mod = "FLRC"
    else:
        mod = "?"
    # band: HF/LF prefix, or CH-24xx vs CH-8xx
    if n.startswith("HF-") or "-CH-24" in n or n.startswith("CH-24"):
        band = "HF"
    elif n.startswith("LF-") or n.startswith("CH-8"):
        band = "LF"
    else:
        band = "?"
    return mod, band

# Aggregate per phase name: average across multiple PHASE_RESULT entries
# (a phase can fire more than once in the interleave sweep).
agg = defaultdict(lambda: dict(
    per_vals=[], rx_total=0, lost_total=0, pktSize=None,
    rssi_avg_vals=[], rssi_min_vals=[], sats_vals=[],
    rx_ms_list=[], n_results=0, band="?", mod="?",
))
for d in phase_results:
    a = agg[d["name"]]
    # skip pure-zero/empty phases for RSSI averaging (rssi=0 means no rx)
    a["per_vals"].append(d["per"])
    a["rx_total"] += d["rx"]
    a["lost_total"] += d["lost"]
    a["pktSize"] = d["pktSize"]
    if d["rssi_avg"] != 0:
        a["rssi_avg_vals"].append(d["rssi_avg"])
    if d["rssi_min"] != 0:
        a["rssi_min_vals"].append(d["rssi_min"])
    if d["sats"] > 0:
        a["sats_vals"].append(d["sats"])
    a["n_results"] += 1
    mod, band = classify(d["name"])
    a["mod"] = mod
    a["band"] = band

# Attach per-phase rx_ms ranges from PKT lines for throughput estimation.
phase_ms = defaultdict(list)
for p in pkts:
    phase_ms[p["phase"]].append(p["rx_ms"])
# Map phase_num -> name using the latest PHASE_RESULT we saw for that num.
num_to_name = {d["phase_num"]: d["name"] for d in phase_results}
for pnum, mss in phase_ms.items():
    nm = num_to_name.get(pnum)
    if nm and mss:
        agg[nm]["rx_ms_list"].extend(mss)

# Build the ordered list of phase names (in capture order, then alphabetical
# for any stragglers) for plotting.
ordered_names = [n for n in phase_order if n in agg]
# Add any not seen in order
for nm in sorted(agg.keys()):
    if nm not in ordered_names:
        ordered_names.append(nm)

# Compute aggregated metrics
def avg(lst):
    return sum(lst) / len(lst) if lst else 0.0

rows = []
for nm in ordered_names:
    a = agg[nm]
    per_mean = avg(a["per_vals"])
    rssi_avg_mean = avg(a["rssi_avg_vals"])
    rssi_min_mean = avg(a["rssi_min_vals"])
    # phase duration estimate from rx_ms range (seconds); fall back to nominal
    if a["rx_ms_list"]:
        dur_s = (max(a["rx_ms_list"]) - min(a["rx_ms_list"])) / 1000.0
        # add a small epsilon; if only 1 pkt, use ~0.1s
        if dur_s <= 0:
            dur_s = 0.1
    else:
        dur_s = None
    throughput_bps = None
    if dur_s and a["pktSize"]:
        throughput_bps = (a["rx_total"] * a["pktSize"] * 8) / dur_s
    rows.append(dict(
        name=nm, mod=a["mod"], band=a["band"],
        pktSize=a["pktSize"], rx=a["rx_total"], lost=a["lost_total"],
        per=per_mean, rssi_avg=rssi_avg_mean, rssi_min=rssi_min_mean,
        sats=avg(a["sats_vals"]), n_results=a["n_results"],
        dur_s=dur_s, throughput_bps=throughput_bps,
    ))

print(f"Aggregated into {len(rows)} unique phases")

# Shorten labels for x-axis readability
def short(nm):
    # CH-2432-FLRC1300-64 -> "2432\nFLRC1300\n64B"
    # HF-FLRC-1300-64 -> "HF-FLRC1300\n64B"
    parts = nm.split("-")
    if len(parts) >= 4 and parts[0] == "CH":
        ch, modrate = parts[1], parts[2]
        psize = parts[3]
        return f"{ch}\n{modrate}\n{psize}B"
    return nm

labels = [short(r["name"]) for r in rows]
x = np.arange(len(rows))

def save(fig, fname):
    path = os.path.join(OUT_DIR, fname)
    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor="black")
    plt.close(fig)
    print(f"  saved: {path}")
    return path

# ================================================================ Plot 1: PER
fig, ax = plt.subplots()
colors = [COLOR_LORA if r["mod"] == "LoRa" else COLOR_FLRC for r in rows]
bars = ax.bar(x, [r["per"] for r in rows], color=colors, edgecolor="white", linewidth=0.4)
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=0, fontsize=8)
ax.set_ylabel("Packet Error Rate (%)")
ax.set_ylim(0, max(105, max(r["per"] for r in rows) * 1.05))
ax.set_title("Balloon RF Sweep — PER by Phase")
# legend
from matplotlib.patches import Patch
ax.legend(handles=[
    Patch(facecolor=COLOR_LORA, label="LoRa"),
    Patch(facecolor=COLOR_FLRC, label="FLRC"),
], loc="upper right")
# value labels
for bar, r in zip(bars, rows):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f"{r['per']:.0f}", ha="center", va="bottom", fontsize=8)
save(fig, "01_per_by_phase.png")

# ================================================================ Plot 2: RSSI
fig, ax = plt.subplots()
w = 0.38
rssi_avg_colors = [COLOR_HF if r["band"] == "HF" else COLOR_LF for r in rows]
rssi_min_colors = [COLOR_HF if r["band"] == "HF" else COLOR_LF for r in rows]
# Use lighter shade for rssi_min via alpha
b1 = ax.bar(x - w/2, [r["rssi_avg"] for r in rows], width=w,
            color=rssi_avg_colors, edgecolor="white", linewidth=0.4,
            label="RSSI avg")
b2 = ax.bar(x + w/2, [r["rssi_min"] for r in rows], width=w,
            color=rssi_min_colors, alpha=0.45, edgecolor="white", linewidth=0.4,
            label="RSSI min")
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=0, fontsize=8)
ax.set_ylabel("RSSI (dBm)")
ax.set_title("Balloon RF Sweep — RSSI by Phase (avg & min)")
ax.legend(handles=[
    Patch(facecolor=COLOR_HF, label="HF 2.4 GHz"),
    Patch(facecolor=COLOR_LF, label="LF 868 MHz"),
    plt.Line2D([], [], color="white", alpha=1.0, label="avg (solid)"),
    plt.Line2D([], [], color="white", alpha=0.45, label="min (faded)"),
], loc="best")
save(fig, "02_rssi_by_phase.png")

# ================================================================ Plot 3: rx vs lost
fig, ax = plt.subplots()
rx_vals = [r["rx"] for r in rows]
lost_vals = [r["lost"] for r in rows]
ax.bar(x, rx_vals, color="#22c55e", edgecolor="white", linewidth=0.4, label="Decoded (rx)")
ax.bar(x, lost_vals, bottom=rx_vals, color="#ef4444", edgecolor="white", linewidth=0.4, label="Lost")
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=0, fontsize=8)
ax.set_ylabel("Packet count")
ax.set_title("Balloon RF Sweep — Packets Decoded vs Lost (stacked)")
ax.legend(loc="upper right")
save(fig, "03_packets_decoded_vs_lost.png")

# ================================================================ Plot 4: Throughput
fig, ax = plt.subplots()
tp_vals = [r["throughput_bps"] or 0 for r in rows]
tp_colors = [COLOR_LORA if r["mod"] == "LoRa" else COLOR_FLRC for r in rows]
bars = ax.bar(x, [v/1000.0 for v in tp_vals], color=tp_colors, edgecolor="white", linewidth=0.4)
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=0, fontsize=8)
ax.set_ylabel("Throughput (kbps, estimated)")
ax.set_title("Balloon RF Sweep — Estimated Throughput by Phase")
ax.legend(handles=[
    Patch(facecolor=COLOR_LORA, label="LoRa"),
    Patch(facecolor=COLOR_FLRC, label="FLRC"),
], loc="upper right")
for bar, v in zip(bars, tp_vals):
    if v > 0:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f"{v/1000:.1f}k", ha="center", va="bottom", fontsize=8)
ax.text(0.99, 0.97,
        "Estimate: rx_count × pktSize × 8 / phase_duration_s\n"
        "(duration from rx_ms span of received packets)",
        transform=ax.transAxes, ha="right", va="top", fontsize=9,
        color="#aaaaaa", bbox=dict(facecolor="#222222", alpha=0.6, boxstyle="round"))
save(fig, "04_throughput_by_phase.png")

# ================================================================ Plot 5: RSSI vs seq
fig, ax = plt.subplots()
if pkts:
    seqs = np.array([p["seq"] for p in pkts])
    rssis = np.array([p["rssi"] for p in pkts])
    phases_arr = np.array([p["phase"] for p in pkts])
    # color by phase for variety
    sc = ax.scatter(seqs, rssis, c=phases_arr, cmap="viridis", s=22, alpha=0.85, edgecolor="none")
    cbar = plt.colorbar(sc, ax=ax, pad=0.01)
    cbar.set_label("Phase #")
    ax.set_xlabel("Packet sequence number")
    ax.set_ylabel("RSSI (dBm)")
    ax.set_title("Balloon RF Sweep — RSSI vs Packet Sequence (stability)")
    # running mean overlay
    if len(rssis) > 10:
        order = np.argsort(seqs)
        s_seq = seqs[order]
        s_rssi = rssis[order]
        win = max(5, len(s_rssi) // 30)
        if hasattr(np, "convolve"):
            kernel = np.ones(win) / win
            sm = np.convolve(s_rssi, kernel, mode="valid")
            ax.plot(s_seq[win-1:], sm, color="#ff6b6b", lw=2, alpha=0.8, label=f"Running mean (w={win})")
            ax.legend(loc="best")
else:
    ax.text(0.5, 0.5, "No PKT lines", transform=ax.transAxes, ha="center")
    ax.set_title("Balloon RF Sweep — RSSI vs Packet Sequence (no data)")
save(fig, "05_rssi_vs_sequence.png")

# ================================================================ Plot 6: GPS sats over time
fig, ax = plt.subplots()
if pkts:
    # Use rx_ms as the time axis (monotonic within capture)
    times = np.array([p["rx_ms"] for p in pkts])
    sats = np.array([p["sats"] for p in pkts])
    order = np.argsort(times)
    t = times[order]
    s = sats[order]
    # convert to seconds from start
    if t.max() > t.min():
        t_sec = (t - t.min()) / 1000.0
    else:
        t_sec = np.arange(len(t))
    ax.plot(t_sec, s, color="#38bdf8", lw=2, marker="o", markersize=4, alpha=0.85)
    ax.fill_between(t_sec, s, 0, color="#38bdf8", alpha=0.15)
    ax.set_xlabel("Capture time (s)")
    ax.set_ylabel("GPS satellites tracked")
    ax.set_title("Balloon RF Sweep — GPS Satellite Count Over Time")
    ax.set_ylim(bottom=0)
    if len(s):
        ax.axhline(4, color="#f59e0b", ls="--", lw=1, alpha=0.6, label="4-sat minimum fix")
        ax.legend(loc="best")
else:
    ax.text(0.5, 0.5, "No PKT lines", transform=ax.transAxes, ha="center")
    ax.set_title("Balloon RF Sweep — GPS Satellites (no data)")
save(fig, "06_gps_sats_over_time.png")

# ---------------------------------------------------------------- summary
print("\n=== SUMMARY ===")
print(f"Source log: {LOG_PATH}")
print(f"Phases (unique): {len(rows)}")
print(f"PKT entries: {len(pkts)}")
mod_counts = defaultdict(int)
band_counts = defaultdict(int)
for r in rows:
    mod_counts[r["mod"]] += 1
    band_counts[r["band"]] += 1
print(f"Modulations: {dict(mod_counts)}")
print(f"Bands: {dict(band_counts)}")
rx_total = sum(r["rx"] for r in rows)
lost_total = sum(r["lost"] for r in rows)
overall_per = 100.0 * lost_total / (rx_total + lost_total) if (rx_total + lost_total) else 0
print(f"Total decoded: {rx_total}, lost: {lost_total}, overall PER: {overall_per:.1f}%")
print(f"\nPlots saved to: {OUT_DIR}/")
for f in sorted(os.listdir(OUT_DIR)):
    if f.endswith(".png"):
        full = os.path.join(OUT_DIR, f)
        print(f"  {full}  ({os.path.getsize(full)} bytes)")
