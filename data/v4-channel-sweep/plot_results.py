#!/usr/bin/env python3
"""
plot_results.py — V4 Channel Sweep publication-quality plots

Parses PHASE_RESULT lines from any v4-channel-sweep capture log and produces
6 dark-themed PNG plots at 300 DPI:

  1. PER heatmap            (14 modes × 4 sizes)
  2. Channel sweep PER      (WiFi blue + EU868 green)
  3. RSSI by mode           (grouped by band)
  4. Decode summary         (pie chart, overall decode rate)
  5. PER comparison         (grouped bars: mode × size)
  6. Throughput per mode    (decoded bytes × 8 / phase time, kbps)

Phases come in two groups:
  • Mode sweep:     14 modes × 4 packet sizes  (HF/LF × LoRa/FLRC × SF/bitrate)
  • Channel sweep:  13 WiFi channels (CH-2412 … CH-2472) + 8 EU868 channels
                    (CH-863 … CH-870), all at FLRC-1300 / 64 B

Some phases are retried (duplicate PHASE_RESULT lines for the same mode/size
or channel). We de-duplicate by keeping the entry with the highest `unique`
packet count — i.e. the best successful attempt, not the fragment.

USAGE
  python3 plot_results.py                                 # default log
  python3 plot_results.py --log walk_test_055410.log --prefix walk_
  python3 plot_results.py --log <file> --prefix <pfx> --capture-name 'Walk Test'

Output: data/v4-channel-sweep/plots/<prefix>*.png
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LOG = SCRIPT_DIR / "rx_sweep_v4_035740.log"
PLOT_DIR = SCRIPT_DIR / "plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)

# 14 canonical modes (LF-LoRa-SF12 is often a SKIP mode → shows as NaN).
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

# Nominal per-phase duration (seconds) used for throughput if PKT rx_ms
# deltas are unavailable. Observed in v4 captures: ~3 s for FLRC modes.
NOMINAL_PHASE_SECONDS = 3.0

# Dark theme palette (GitHub dark)
BG = "#0d1117"
PANEL = "#161b22"
GRID = "#30363d"
TEXT = "#c9d1d9"
TEXT_DIM = "#8b949e"
HF_COLOR = "#58a6ff"      # blue  (HF band, 2.4 GHz, WiFi)
LF_COLOR = "#3fb950"      # green (LF band, sub-GHz, EU868)
WIFI_COLOR = "#58a6ff"    # blue
EU868_COLOR = "#3fb950"   # green
GOOD_COLOR = "#3fb950"
BAD_COLOR = "#f85149"


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

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

# PKT line for extracting per-phase timing:
#   PKT rx=N seq=N rssi=-N phase=N rx_ms=<monotonic ms>
PKT_RE = re.compile(
    r"^PKT\s+rx=\d+\s+seq=\d+\s+rssi=-?\d+\s+phase=(?P<phase>\d+)\s+"
    r"rx_ms=(?P<ms>\d+)"
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


def parse_phase_times(path: Path) -> dict[int, float]:
    """Return {phase_num: phase_duration_seconds} computed from PKT rx_ms deltas.

    For each phase we take the first observed packet rx_ms as a proxy for
    phase-start. Phase N duration is approximated as
    first_rx_ms(N+1) - first_rx_ms(N), clamped to [0.5, 60] s. Falls back to
    NOMINAL_PHASE_SECONDS when no PKT lines exist for a phase.
    """
    first_ms: dict[int, int] = {}
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            m = PKT_RE.match(line)
            if not m:
                continue
            p = int(m.group("phase"))
            ms = int(m.group("ms"))
            if p not in first_ms or ms < first_ms[p]:
                first_ms[p] = ms
    phases = sorted(first_ms)
    out: dict[int, float] = {}
    for i, p in enumerate(phases):
        if i + 1 < len(phases):
            d = (first_ms[phases[i + 1]] - first_ms[p]) / 1000.0
            # Clamp outliers (long skips, retried phases) to a sane window.
            d = max(0.5, min(60.0, d))
            out[p] = d
        else:
            out[p] = NOMINAL_PHASE_SECONDS
    return out


def mode_from_tag(tag: str) -> str | None:
    """Map 'HF-FLRC-325-64' or 'CH-868-FLRC1300-64' to canonical mode.
    Returns None for channel-sweep tags or SKIP-only tags."""
    if tag.startswith("CH-"):
        return None
    if tag.endswith("-SKIP"):
        # e.g. 'LF-LoRa-SF12-SKIP' — strip the -SKIP, but the rsplit below
        # would yield mode='LF-LoRa-SF12-SKIP' which is wrong; handle first.
        tag = tag[: -len("-SKIP")]
    parts = tag.rsplit("-", 1)
    if len(parts) != 2:
        return None
    return parts[0]


def channel_from_tag(tag: str) -> tuple[str, int] | None:
    """Map 'CH-2412-FLRC1300-64' to ('CH-2412', 2412). Returns None otherwise."""
    if not tag.startswith("CH-"):
        return None
    m = re.match(r"CH-(\d+)-", tag)
    if not m:
        return None
    freq = int(m.group(1))
    return (f"CH-{freq}", freq)


# --------------------------------------------------------------------------- #
# De-duplication: keep the best attempt per (mode, size) or per channel
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Plot helpers
# --------------------------------------------------------------------------- #

_state = {"prefix": "", "capture_name": "V4 Channel Sweep"}


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
    out = PLOT_DIR / f"{_state['prefix']}{name}"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  wrote {out.name}  ({out.stat().st_size // 1024} KB)")


def _title_suffix() -> str:
    return f"— {_state['capture_name']}"


# --------------------------------------------------------------------------- #
# Plot 1 — PER heatmap (mode × size)
# --------------------------------------------------------------------------- #

def plot_per_heatmap(mode_best, decode_pct):
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
    ax.set_title(f"PER by Mode × Size — {decode_pct:.0f}% decode {_title_suffix()}",
                 pad=14)

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


# --------------------------------------------------------------------------- #
# Plot 2 — Channel sweep bar chart
# --------------------------------------------------------------------------- #

def plot_channel_sweep(chan_best):
    apply_dark_theme()

    wifi = sorted([(lbl, freq, rec) for (lbl, freq), rec in chan_best.items()
                   if freq >= 2400], key=lambda x: x[1])
    eu = sorted([(lbl, freq, rec) for (lbl, freq), rec in chan_best.items()
                 if freq < 2400], key=lambda x: x[1])

    fig, ax = plt.subplots(figsize=(13, 6))
    xs = np.arange(len(wifi) + len(eu))
    wifi_x = np.arange(len(wifi))
    eu_x = np.arange(len(wifi), len(wifi) + len(eu))

    wifi_per = [r["per"] for _, _, r in wifi] or [0]
    eu_per = [r["per"] for _, _, r in eu] or [0]
    bar_w = 0.42

    ax.bar(wifi_x, wifi_per, bar_w * 2, color=WIFI_COLOR,
           label=f"WiFi 2.4 GHz (n={len(wifi)})", edgecolor=GRID, linewidth=0.5)
    ax.bar(eu_x, eu_per, bar_w * 2, color=EU868_COLOR,
           label=f"EU868 (n={len(eu)})", edgecolor=GRID, linewidth=0.5)

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
    ax.set_ylim(0, max(max(wifi_per), max(eu_per)) * 1.25 + 5)
    ax.set_title(f"Channel Sweep PER — All Frequencies {_title_suffix()}", pad=14)
    ax.legend(loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    save(fig, "02_channel_sweep.png")


# --------------------------------------------------------------------------- #
# Plot 3 — RSSI by mode (HF=blue, LF=green)
# --------------------------------------------------------------------------- #

def plot_rssi_by_mode(mode_best):
    apply_dark_theme()

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

    ax.bar(x, [v if not np.isnan(v) else 0 for v in vals],
           color=colors, edgecolor=GRID, linewidth=0.5, width=0.7)

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
    ax.set_title(f"Signal Strength by Mode {_title_suffix()}", pad=14)

    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor=HF_COLOR, edgecolor=GRID, label="HF band (2.4 GHz)"),
        Patch(facecolor=LF_COLOR, edgecolor=GRID, label="LF band (sub-GHz)"),
    ]
    ax.legend(handles=legend_elems, loc="lower right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.invert_yaxis()
    finite = [v for v in vals if not np.isnan(v)]
    if finite:
        ax.set_ylim(min(finite) - 5, max(finite) + 5)

    fig.tight_layout()
    save(fig, "03_rssi_by_mode.png")


# --------------------------------------------------------------------------- #
# Plot 4 — Decode summary (pie chart)
# --------------------------------------------------------------------------- #

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

    ax.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        startangle=90, counterclock=False,
        wedgeprops=dict(edgecolor=BG, linewidth=2.5),
        textprops=dict(color=TEXT, fontsize=12, fontweight="bold"),
    )
    ax.set_title(f"Phase Decode Summary ({decoded}/{total} = {pct:.0f}%) "
                 f"{_title_suffix()}", pad=20, fontsize=14)
    ax.text(0, 0, f"{pct:.0f}%", ha="center", va="center",
            color=TEXT, fontsize=28, fontweight="bold")
    fig.tight_layout()
    save(fig, "04_decode_summary.png")


# --------------------------------------------------------------------------- #
# Plot 5 — PER comparison grouped bars (mode × size)
# --------------------------------------------------------------------------- #

def plot_per_comparison(mode_best):
    apply_dark_theme()
    fig, ax = plt.subplots(figsize=(15, 7))

    n_modes = len(MODE_ORDER)
    n_sizes = len(PKT_SIZES)
    x = np.arange(n_modes)
    total_w = 0.82
    bar_w = total_w / n_sizes

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
        for i, v in enumerate(vals):
            if np.isnan(v):
                bars[i].set_hatch("//")
                bars[i].set_color("#21262d")
                bars[i].set_edgecolor(GRID)

    ax.set_xticks(x)
    ax.set_xticklabels(MODE_ORDER, rotation=45, ha="right")
    ax.set_xlabel("Mode", labelpad=8)
    ax.set_ylabel("PER (%)")
    ax.set_title(f"PER by Bitrate and Packet Size {_title_suffix()}", pad=14)
    ax.set_ylim(0, 110)
    ax.legend(title="Packet size", loc="upper right", ncol=n_sizes)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    save(fig, "05_per_comparison.png")


# --------------------------------------------------------------------------- #
# Plot 6 — Throughput per mode (kbps)
# --------------------------------------------------------------------------- #

def plot_throughput(mode_best, phase_times):
    """Decoded throughput per mode = Σ(unique × pktSize × 8) / Σ(phase_time),
    summed over the four packet sizes, expressed in kbps.

    `mode_best` is keyed by (mode, pktSize). `phase_times` maps phase_num →
    seconds (used as the divisor). When a phase has no time data we fall back
    to NOMINAL_PHASE_SECONDS.
    """
    apply_dark_theme()

    # Aggregate decoded bits and phase time per mode.
    mode_bits: dict[str, float] = defaultdict(float)
    mode_time: dict[str, float] = defaultdict(float)
    mode_phases: dict[str, int] = defaultdict(int)

    for (mode, size), rec in mode_best.items():
        phase_time = phase_times.get(rec["phase"], NOMINAL_PHASE_SECONDS)
        if rec["unique"] > 0 and phase_time > 0:
            mode_bits[mode] += rec["unique"] * size * 8
            mode_time[mode] += phase_time
            mode_phases[mode] += 1

    # Throughput in kbps; NaN if no decoded data.
    mode_kbps: dict[str, float] = {}
    for mode in MODE_ORDER:
        if mode_time[mode] > 0:
            mode_kbps[mode] = mode_bits[mode] / mode_time[mode] / 1000.0
        else:
            mode_kbps[mode] = np.nan

    fig, ax = plt.subplots(figsize=(13, 6.5))
    x = np.arange(len(MODE_ORDER))
    colors = [HF_COLOR if m.startswith("HF-") else LF_COLOR for m in MODE_ORDER]
    vals = [mode_kbps[m] for m in MODE_ORDER]
    finite_vals = [v for v in vals if not np.isnan(v) and v > 0]

    bars = ax.bar(x, [v if not np.isnan(v) else 0 for v in vals],
                  color=colors, edgecolor=GRID, linewidth=0.5, width=0.7)

    for xi, v in zip(x, vals):
        if np.isnan(v) or v <= 0:
            ax.text(xi, 0.5, "n/a", ha="center", va="bottom",
                    color="#484f58", fontsize=9, rotation=90)
        else:
            ax.text(xi, v + max(finite_vals, default=1) * 0.012,
                    f"{v:.1f}", ha="center", va="bottom",
                    color=TEXT, fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(MODE_ORDER, rotation=45, ha="right")
    ax.set_xlabel("Mode", labelpad=8)
    ax.set_ylabel("Throughput (kbps)")
    ax.set_title(
        f"Decoded Throughput per Mode — Σ(unique×payload×8) / Σ(phase_time) "
        f"{_title_suffix()}",
        pad=14,
    )

    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor=HF_COLOR, edgecolor=GRID, label="HF band (2.4 GHz)"),
        Patch(facecolor=LF_COLOR, edgecolor=GRID, label="LF band (sub-GHz)"),
    ]
    ax.legend(handles=legend_elems, loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    if finite_vals:
        ax.set_ylim(0, max(finite_vals) * 1.18)

    # Footnote on methodology
    ax.text(
        0.5, -0.32,
        f"Phase time derived from PKT rx_ms deltas (nominal "
        f"{NOMINAL_PHASE_SECONDS:.0f}s when unavailable). "
        f"Each mode = 4 phases (one per pktSize 32/64/128/255 B).",
        transform=ax.transAxes, ha="center", va="top",
        color=TEXT_DIM, fontsize=8, style="italic",
    )

    fig.tight_layout()
    save(fig, "06_throughput.png")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate publication-quality plots from a v4 channel "
                    "sweep capture log.")
    parser.add_argument(
        "--log", default=str(DEFAULT_LOG),
        help=f"Path to capture log (default: {DEFAULT_LOG.name})")
    parser.add_argument(
        "--prefix", default="",
        help="Filename prefix for saved plots (e.g. 'walk_'). Default: none.")
    parser.add_argument(
        "--capture-name", default="V4 Channel Sweep",
        help="Short capture name used in plot titles "
             "(e.g. 'Walk Test 93%').")
    args = parser.parse_args(argv)

    log_path = Path(args.log).resolve()
    if not log_path.is_absolute() or not log_path.exists():
        # Allow relative paths from the script directory.
        cand = SCRIPT_DIR / args.log
        if cand.exists():
            log_path = cand
        else:
            sys.exit(f"Log not found: {args.log}")

    _state["prefix"] = args.prefix
    _state["capture_name"] = args.capture_name

    print(f"Parsing {log_path.name} ...")
    records = parse_log(log_path)
    if not records:
        sys.exit("No PHASE_RESULT lines parsed.")
    print(f"  {len(records)} PHASE_RESULT lines parsed")

    phase_times = parse_phase_times(log_path)
    print(f"  phase-time map: {len(phase_times)} phases")

    mode_records = [r for r in records if mode_from_tag(r["tag"]) is not None]
    chan_records = [r for r in records if channel_from_tag(r["tag"]) is not None]
    print(f"  mode-sweep records: {len(mode_records)}")
    print(f"  channel-sweep records: {len(chan_records)}")

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

    decoded = sum(1 for r in records if r["rx"] > 0)
    decode_pct = decoded / len(records) * 100
    print(f"  decoded (rx>0): {decoded}/{len(records)} = {decode_pct:.1f}%")

    print("Generating plots:")
    plot_per_heatmap(mode_best, decode_pct)
    plot_channel_sweep(chan_best)
    plot_rssi_by_mode(mode_best)
    plot_decode_summary(records)
    plot_per_comparison(mode_best)
    plot_throughput(mode_best, phase_times)

    print("Done.")


if __name__ == "__main__":
    main()
