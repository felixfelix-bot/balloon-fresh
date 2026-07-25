#!/usr/bin/env python3
"""
plot_results.py — V4 Channel Sweep publication-quality plots

Parses PHASE_RESULT lines from rx_sweep_v4_035740.log (the 82% decode capture)
and produces 5 dark-themed PNG plots at 300 DPI.

Phases come in two groups:
  • Mode sweep (phases 0–55): 14 modes × 4 packet sizes
  • Channel sweep (phases 56–76): 13 WiFi channels + 8 EU868 channels

Some phases were retried (duplicate PHASE_RESULT lines for the same mode/size
or channel). We de-duplicate by keeping the entry with the highest `unique`
packet count — i.e. the best successful attempt, not the fragment.

Output: data/v4-channel-sweep/plots/*.png
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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOG_PATH = Path(__file__).resolve().parent / "rx_sweep_v4_035740.log"
PLOT_DIR = Path(__file__).resolve().parent / "plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)

# 14 canonical modes, grouped by band then modulation/bitrate
# LF-LoRa-SF12 is a SKIP mode (kept for axis completeness, will show as NaN).
MODE_ORDER = [
    "HF-LoRa-SF7",
    "HF-LoRa-SF9",
    "HF-LoRa-SF12",
    "HF-FLRC-2600",
    "HF-FLRC-1300",
    "HF-FLRC-650",
    "HF-FLRC-325",
    "LF-LoRa-SF7",
    "LF-LoRa-SF9",
    "LF-LoRa-SF12",
    "LF-FLRC-2600",
    "LF-FLRC-1300",
    "LF-FLRC-650",
    "LF-FLRC-325",
]
PKT_SIZES = [32, 64, 128, 255]

# Dark theme palette
BG = "#0d1117"
PANEL = "#161b22"
GRID = "#30363d"
TEXT = "#c9d1d9"
TEXT_DIM = "#8b949e"
HF_COLOR = "#58a6ff"   # blue
LF_COLOR = "#3fb950"   # green
WIFI_COLOR = "#58a6ff"  # blue
EU868_COLOR = "#3fb950"  # green
GOOD_COLOR = "#3fb950"
BAD_COLOR = "#f85149"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# A PHASE_RESULT line looks like:
#   PHASE_RESULT <phase_num> <mode_tag> pktSize=N rx=N unique=N lost=N per=N.N
#       rssi_avg=N rssi_min=N crc_err=N garbage=N tx_lat=N tx_lon=N
#       sats=N fix=N utc=N [tx_fw=.. rx_fw=..]
PHASE_RE = re.compile(
    r"^PHASE_RESULT\s+(?P<phase>\d+)\s+(?P<tag>\S+)\s+"
    r"pktSize=(?P<pktSize>\d+)\s+"
    r"rx=(?P<rx>-?\d+)\s+"
    r"unique=(?P<unique>-?\d+)\s+"
    r"lost=(?P<lost>-?\d+)\s+"
    r"per=(?P<per>[\d.]+)\s+"
    r"rssi_avg=(?P<rssi_avg>-?\d+)\s+"
    r"rssi_min=(?P<rssi_min>-?\d+)\s+"
    r"crc_err=(?P<crc_err>\d+)\s+"
    r"garbage=(?P<garbage>\d+)\s+"
    r"tx_lat=(?P<tx_lat>[-\d.]+)\s+"
    r"tx_lon=(?P<tx_lon>[-\d.]+)\s+"
    r"sats=(?P<sats>\d+)\s+"
    r"fix=(?P<fix>\d+)\s+"
    r"utc=(?P<utc>-?\d+)"
)


def parse_log(path: Path) -> list[dict]:
    """Return a list of all parsed PHASE_RESULT records (including duplicates)."""
    records = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("PHASE_RESULT"):
                continue
            m = PHASE_RE.match(line)
            if not m:
                # Keep parsing resilient: try a looser fallback for odd lines
                continue
            d = m.groupdict()
            rec = {
                "phase": int(d["phase"]),
                "tag": d["tag"],
                "pktSize": int(d["pktSize"]),
                "rx": int(d["rx"]),
                "unique": int(d["unique"]),
                "lost": int(d["lost"]),
                "per": float(d["per"]),
                "rssi_avg": int(d["rssi_avg"]),
                "rssi_min": int(d["rssi_min"]),
                "crc_err": int(d["crc_err"]),
                "garbage": int(d["garbage"]),
                "tx_lat": float(d["tx_lat"]),
                "tx_lon": float(d["tx_lon"]),
                "sats": int(d["sats"]),
                "fix": int(d["fix"]),
                "utc": int(d["utc"]),
                "raw": line,
            }
            records.append(rec)
    return records


def mode_from_tag(tag: str) -> str | None:
    """Map a phase tag like 'HF-FLRC-325-64' or 'CH-868-FLRC1300-64' to a
    canonical mode name. Returns None for channel-sweep tags."""
    if tag.startswith("CH-"):
        return None
    # Strip trailing -<pktSize>
    parts = tag.rsplit("-", 1)
    if len(parts) != 2:
        return None
    return parts[0]


def channel_from_tag(tag: str) -> tuple[str, int] | None:
    """Map a channel-sweep tag like 'CH-2412-FLRC1300-64' to (label, freq_mhz).
    Returns None for non-channel tags."""
    if not tag.startswith("CH-"):
        return None
    m = re.match(r"CH-(\d+)-", tag)
    if not m:
        return None
    freq = int(m.group(1))
    return (f"CH-{freq}", freq)


# ---------------------------------------------------------------------------
# De-duplication: keep the best attempt per (mode, size) or per channel
# ---------------------------------------------------------------------------

def best_by_key(records, key_fn):
    """Group records by key_fn; for each key keep the record with max(unique)."""
    best = {}
    for rec in records:
        k = key_fn(rec)
        if k is None:
            continue
        if k not in best or rec["unique"] > best[k]["unique"]:
            best[k] = rec
    return best


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------

def apply_dark_theme():
    plt.rcParams.update({
        "figure.facecolor": BG,
        "axes.facecolor": PANEL,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT,
        "axes.titlecolor": TEXT,
        "xtick.color": TEXT_DIM,
        "ytick.color": TEXT_DIM,
        "text.color": TEXT,
        "grid.color": GRID,
        "grid.alpha": 0.5,
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "legend.facecolor": PANEL,
        "legend.edgecolor": GRID,
        "legend.labelcolor": TEXT,
        "savefig.facecolor": BG,
        "savefig.edgecolor": BG,
    })


def save(fig, name):
    out = PLOT_DIR / name
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  wrote {out.name}  ({out.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------------------
# Plot 1 — PER heatmap (mode × size)
# ---------------------------------------------------------------------------

def plot_per_heatmap(mode_best):
    apply_dark_theme()
    n_modes = len(MODE_ORDER)
    n_sizes = len(PKT_SIZES)
    data = np.full((n_modes, n_sizes), np.nan)
    for i, mode in enumerate(MODE_ORDER):
        for j, size in enumerate(PKT_SIZES):
            rec = mode_best.get((mode, size))
            if rec is not None:
                data[i, j] = rec["per"]

    fig, ax = plt.subplots(figsize=(8, 9))
    # Mask NaN for colormap; use a gray fallback
    masked = np.ma.masked_invalid(data)
    cmap = plt.cm.RdYlGn_r.copy()
    cmap.set_bad(color="#21262d")
    im = ax.imshow(masked, aspect="auto", cmap=cmap, vmin=0, vmax=100,
                   interpolation="nearest")

    ax.set_xticks(range(n_sizes))
    ax.set_xticklabels([str(s) for s in PKT_SIZES])
    ax.set_yticks(range(n_modes))
    ax.set_yticklabels(MODE_ORDER)
    ax.set_xlabel("Packet Size (bytes)", labelpad=8)
    ax.set_ylabel("Mode")
    ax.set_title("PER by Mode × Size — V4 Channel Sweep (82% decode)", pad=14)

    # Annotate each cell
    for i in range(n_modes):
        for j in range(n_sizes):
            val = data[i, j]
            if np.isnan(val):
                ax.text(j, i, "—", ha="center", va="center",
                        color="#484f58", fontsize=9)
            else:
                color = "white" if val > 55 or val < 20 else "black"
                ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                        color=color, fontsize=9, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, pad=0.02, fraction=0.046)
    cbar.set_label("PER (%)", color=TEXT)
    cbar.ax.yaxis.set_tick_params(color=TEXT_DIM)
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color=TEXT_DIM)

    fig.tight_layout()
    save(fig, "01_per_heatmap.png")


# ---------------------------------------------------------------------------
# Plot 2 — Channel sweep bar chart
# ---------------------------------------------------------------------------

def plot_channel_sweep(chan_best):
    apply_dark_theme()

    wifi = sorted([(lbl, freq, rec) for (lbl, freq), rec in chan_best.items()
                   if freq >= 2400], key=lambda x: x[1])
    eu = sorted([(lbl, freq, rec) for (lbl, freq), rec in chan_best.items()
                 if freq < 2400], key=lambda x: x[1])

    fig, ax = plt.subplots(figsize=(13, 6))
    bar_w = 0.42
    xs = np.arange(len(wifi) + len(eu))

    wifi_x = np.arange(len(wifi))
    eu_x = np.arange(len(wifi), len(wifi) + len(eu))

    wifi_per = [r["per"] for _, _, r in wifi]
    eu_per = [r["per"] for _, _, r in eu]

    ax.bar(wifi_x, wifi_per, bar_w * 2, color=WIFI_COLOR,
           label=f"WiFi 2.4 GHz (n={len(wifi)})", edgecolor=GRID, linewidth=0.5)
    ax.bar(eu_x, eu_per, bar_w * 2, color=EU868_COLOR,
           label=f"EU868 (n={len(eu)})", edgecolor=GRID, linewidth=0.5)

    # Annotate bars
    for x, per in zip(wifi_x, wifi_per):
        ax.text(x, per + 1.5, f"{per:.0f}%", ha="center", va="bottom",
                color=TEXT, fontsize=8)
    for x, per in zip(eu_x, eu_per):
        ax.text(x, per + 1.5, f"{per:.0f}%", ha="center", va="bottom",
                color=TEXT, fontsize=8)

    labels = [lbl for lbl, _, _ in wifi] + [lbl for lbl, _, _ in eu]
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_xlabel("Channel", labelpad=8)
    ax.set_ylabel("PER (%)")
    ax.set_ylim(0, max(max(wifi_per, default=0), max(eu_per, default=0)) * 1.25 + 5)
    ax.set_title("Channel Sweep PER — All Frequencies", pad=14)
    ax.legend(loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    save(fig, "02_channel_sweep.png")


# ---------------------------------------------------------------------------
# Plot 3 — RSSI by mode (HF=blue, LF=green)
# ---------------------------------------------------------------------------

def plot_rssi_by_mode(mode_best):
    apply_dark_theme()

    # Average RSSI across packet sizes for each mode (ignoring SKIP / NaN)
    mode_rssi = {}
    for mode in MODE_ORDER:
        rssi_vals = [rec["rssi_avg"] for size in PKT_SIZES
                     if (rec := mode_best.get((mode, size))) is not None
                     and rec["rssi_avg"] != 0]
        mode_rssi[mode] = (np.mean(rssi_vals) if rssi_vals else np.nan)

    fig, ax = plt.subplots(figsize=(13, 6))
    x = np.arange(len(MODE_ORDER))
    colors = [HF_COLOR if m.startswith("HF-") else LF_COLOR for m in MODE_ORDER]
    vals = [mode_rssi[m] for m in MODE_ORDER]

    bars = ax.bar(x, vals, color=colors, edgecolor=GRID, linewidth=0.5, width=0.7)

    for xi, v in zip(x, vals):
        if np.isnan(v):
            ax.text(xi, 2, "n/a", ha="center", va="bottom",
                    color="#484f58", fontsize=8, rotation=90)
        else:
            ax.text(xi, v + 1.5, f"{v:.0f}", ha="center", va="bottom",
                    color=TEXT, fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(MODE_ORDER, rotation=45, ha="right")
    ax.set_ylabel("Average RSSI (dBm)")
    ax.set_xlabel("Mode")
    ax.set_title("Signal Strength by Mode", pad=14)

    # Legend proxies
    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor=HF_COLOR, edgecolor=GRID, label="HF band (2.4 GHz)"),
        Patch(facecolor=LF_COLOR, edgecolor=GRID, label="LF band (sub-GHz)"),
    ]
    ax.legend(handles=legend_elems, loc="lower right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.invert_yaxis()  # stronger signal (less negative) on top
    ax.set_ylim(min(v for v in vals if not np.isnan(v)) - 5,
                max(v for v in vals if not np.isnan(v)) + 5)

    fig.tight_layout()
    save(fig, "03_rssi_by_mode.png")


# ---------------------------------------------------------------------------
# Plot 4 — Decode summary (pie chart)
# ---------------------------------------------------------------------------

def plot_decode_summary(records):
    apply_dark_theme()
    total = len(records)
    decoded = sum(1 for r in records if r["rx"] > 0)
    failed = total - decoded
    pct = decoded / total * 100 if total else 0.0

    fig, ax = plt.subplots(figsize=(8, 8))
    sizes = [decoded, failed]
    labels = [
        f"Decoded\n{decoded} phases ({pct:.1f}%)",
        f"Failed\n{failed} phases ({100 - pct:.1f}%)",
    ]
    colors = [GOOD_COLOR, BAD_COLOR]
    explode = (0.04, 0.04)

    wedges, texts = ax.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        startangle=90, counterclock=False,
        wedgeprops=dict(edgecolor=BG, linewidth=2.5),
        textprops=dict(color=TEXT, fontsize=12, fontweight="bold"),
    )
    ax.set_title(f"Phase Decode Summary ({decoded}/{total} = {pct:.0f}%)",
                 pad=20, fontsize=14)
    ax.text(0, 0, f"{pct:.0f}%", ha="center", va="center",
            color=TEXT, fontsize=28, fontweight="bold")
    fig.tight_layout()
    save(fig, "04_decode_summary.png")


# ---------------------------------------------------------------------------
# Plot 5 — Combined PER comparison (grouped bars: mode × size)
# ---------------------------------------------------------------------------

def plot_per_comparison(mode_best):
    apply_dark_theme()
    fig, ax = plt.subplots(figsize=(15, 7))

    n_modes = len(MODE_ORDER)
    n_sizes = len(PKT_SIZES)
    x = np.arange(n_modes)
    total_w = 0.82
    bar_w = total_w / n_sizes

    # Color gradient across packet sizes
    size_colors = ["#79c0ff", "#58a6ff", "#388bfd", "#1f6feb"]

    for j, size in enumerate(PKT_SIZES):
        vals = []
        for mode in MODE_ORDER:
            rec = mode_best.get((mode, size))
            vals.append(rec["per"] if rec is not None else np.nan)
        offset = (j - (n_sizes - 1) / 2) * bar_w
        xs = x + offset
        vals_arr = np.array(vals, dtype=float)
        bars = ax.bar(xs, np.nan_to_num(vals_arr, nan=0), bar_w,
                      color=size_colors[j], edgecolor=GRID, linewidth=0.4,
                      label=f"{size} B")
        # Hatch missing bars
        for i, v in enumerate(vals):
            if np.isnan(v):
                bars[i].set_hatch("//")
                bars[i].set_color("#21262d")
                bars[i].set_edgecolor(GRID)

    ax.set_xticks(x)
    ax.set_xticklabels(MODE_ORDER, rotation=45, ha="right")
    ax.set_xlabel("Mode", labelpad=8)
    ax.set_ylabel("PER (%)")
    ax.set_title("PER by Bitrate and Packet Size", pad=14)
    ax.set_ylim(0, 110)
    ax.legend(title="Packet size", loc="upper right", ncol=n_sizes)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    save(fig, "05_per_comparison.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not LOG_PATH.exists():
        sys.exit(f"Log not found: {LOG_PATH}")
    print(f"Parsing {LOG_PATH.name} ...")
    records = parse_log(LOG_PATH)
    print(f"  {len(records)} PHASE_RESULT lines parsed")

    # Split mode-sweep vs channel-sweep records
    mode_records = [r for r in records if mode_from_tag(r["tag"]) is not None]
    chan_records = [r for r in records if channel_from_tag(r["tag"]) is not None]
    print(f"  mode-sweep records: {len(mode_records)}")
    print(f"  channel-sweep records: {len(chan_records)}")

    # De-duplicate, keeping best attempt
    mode_best = best_by_key(
        mode_records,
        lambda r: (mode_from_tag(r["tag"]), r["pktSize"]),
    )
    chan_best = best_by_key(
        chan_records,
        lambda r: channel_from_tag(r["tag"]),
    )
    print(f"  unique (mode,size) cells: {len(mode_best)}")
    print(f"  unique channels: {len(chan_best)}")

    # Decode summary uses ALL records (132 = every attempt counted)
    decoded = sum(1 for r in records if r["rx"] > 0)
    print(f"  decoded (rx>0): {decoded}/{len(records)} = "
          f"{decoded / len(records) * 100:.1f}%")

    print("Generating plots:")
    plot_per_heatmap(mode_best)
    plot_channel_sweep(chan_best)
    plot_rssi_by_mode(mode_best)
    plot_decode_summary(records)
    plot_per_comparison(mode_best)

    print("Done.")


if __name__ == "__main__":
    main()
