#!/usr/bin/env python3
"""
plot_characterization.py — Generate characterization charts from unified CSV data.

Reads a unified CSV (as produced by parse_unified_csv.py) and generates five
types of PNG plots:

  1. PER vs Distance       — 4 curves overlaid (HF_FLRC, HF_LORA, LF_LORA, LF_FLRC)
  2. RSSI vs Distance      — 4 curves + theoretical FSPL for 2440 & 868 MHz
  3. Throughput vs Bitrate — Bar chart (FLRC only)
  4. PA Impact             — RSSI PA-on vs PA-off at each distance
  5. Sensitivity Comparison — LoRa SF7 vs SF9 vs SF12, PER vs distance

Usage:
    python3 tools/plot_characterization.py <csv_file> [--output-dir plots/]

Exit codes: 0 = success, 1 = no data / errors, 2 = usage error
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

# ─── Dark theme colours ─────────────────────────────────────────────────────

BG = "#0d1117"
FG = "#c9d1d9"
GRID = "#30363d"
SPINE = "#484f58"

# Per-path colour scheme
PATH_COLORS = {
    "HF_FLRC": "#58a6ff",   # blue
    "HF_LORA": "#f0883e",   # orange
    "LF_LORA": "#3fb950",   # green
    "LF_FLRC": "#f85149",   # red
}

# Theoretical FSPL colours
FSPL_COLORS = {
    2440: "#bc8cff",   # purple
    868: "#d2a8ff",    # light purple
}

SF_COLORS = {
    7: "#58a6ff",
    9: "#f0883e",
    12: "#3fb950",
}

# ─── Constants ──────────────────────────────────────────────────────────────

FREQ_HF = 2440.0
FREQ_LF = 868.0
TX_POWER_PA_ON = 12.5
TX_POWER_PA_OFF = 0.0

# Distance range for theoretical FSPL curves (metres)
FSPL_MIN_DIST = 1.0
FSPL_MAX_DIST = 20000.0  # 20 km

# ─── Helpers ────────────────────────────────────────────────────────────────


def _safe_float(val) -> Optional[float]:
    """Parse a CSV cell to float, returning None on failure."""
    if val is None:
        return None
    val = str(val).strip()
    if not val or val.upper() in ("NA", "N/A", "NAN", "INF", "-INF"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    f = _safe_float(val)
    return int(f) if f is not None else None


def normalize_pa_state(val) -> str:
    """Normalise various PA-state encodings to 'ON' / 'OFF' / 'UNKNOWN'."""
    if not val:
        return "UNKNOWN"
    s = str(val).strip().upper()
    if s in ("ON", "1", "TRUE", "ENABLED", "HIGH"):
        return "ON"
    if s in ("OFF", "0", "FALSE", "DISABLED", "LOW", ""):
        return "OFF" if s else "UNKNOWN"
    return "UNKNOWN"


def extract_path_category(row: dict) -> Optional[str]:
    """
    Extract the base path category from a CSV row.

    Tries the 'path' column first, then derives from freq_mhz + modulation.
    Returns one of: HF_FLRC, HF_LORA, LF_LORA, LF_FLRC, or None.
    """
    path_val = (row.get("path") or "").strip().upper()

    # Direct match on full path values
    for cat in PATH_COLORS:
        if path_val == cat or path_val.startswith(cat):
            return cat

    # Derive from freq + modulation if path is missing
    freq = _safe_float(row.get("freq_mhz"))
    mod = (row.get("modulation") or "").strip().upper()

    if freq is not None:
        is_hf = freq >= 1000.0
    else:
        # Try path name for freq hint
        is_hf = "HF" in path_val

    is_flrc = "FLRC" in mod or "FLRC" in path_val
    is_lora = "LORA" in mod or "LORA" in path_val

    if is_hf and is_flrc:
        return "HF_FLRC"
    if is_hf and is_lora:
        return "HF_LORA"
    if not is_hf and is_lora:
        return "LF_LORA"
    if not is_hf and is_flrc:
        return "LF_FLRC"

    return None


def compute_fspl_rssi(
    distance_m: float, freq_mhz: float, tx_power_dbm: float
) -> float:
    """
    Free-space path loss RSSI estimate.

    RSSI = TX_power - 20*log10(d) - 20*log10(f_MHz) + 27.55
    """
    return tx_power_dbm - 20.0 * math.log10(distance_m) - 20.0 * math.log10(freq_mhz) + 27.55


def median_safe(values: list) -> Optional[float]:
    """Return median of non-None values, or None if empty."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    if n % 2 == 0:
        return (vals[mid - 1] + vals[mid]) / 2.0
    return vals[mid]


def mean_safe(values: list) -> Optional[float]:
    """Return mean of non-None values, or None if empty."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


# ─── CSV loading ────────────────────────────────────────────────────────────


def load_csv(csv_path: str) -> list[dict]:
    """Load unified CSV into list of row dicts."""
    rows = []
    try:
        with open(csv_path, "r", newline="", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except FileNotFoundError:
        print(f"ERROR: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR reading {csv_path}: {exc}", file=sys.stderr)
        sys.exit(1)
    return rows


def enrich_rows(rows: list[dict]) -> list[dict]:
    """
    Pre-compute derived fields for each row.

    Adds: _path_cat, _pa_state, _distance, _per, _rssi_avg, _throughput,
          _bitrate, _sf, _freq
    """
    for row in rows:
        row["_path_cat"] = extract_path_category(row)
        row["_pa_state"] = normalize_pa_state(row.get("pa_state"))
        row["_distance"] = _safe_float(row.get("distance_m"))
        row["_per"] = _safe_float(row.get("per_percent"))
        row["_rssi_avg"] = _safe_float(row.get("rssi_avg_dbm"))
        row["_throughput"] = _safe_float(row.get("throughput_kbps"))
        row["_bitrate"] = _safe_float(row.get("bitrate_kbps"))
        row["_sf"] = _safe_int(row.get("spreading_factor"))
        row["_freq"] = _safe_float(row.get("freq_mhz"))
        row["_tx_power"] = _safe_float(row.get("tx_power_dbm"))
    return rows


def group_by_distance(
    rows: list[dict], path_cat: str
) -> dict[float, list[dict]]:
    """Group rows by distance (rounded to 0.1 m) for a given path category."""
    groups: dict[float, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("_path_cat") != path_cat:
            continue
        d = row.get("_distance")
        if d is not None and d >= 0:
            key = round(d, 1)
            groups[key].append(row)
    return dict(groups)


# ─── Matplotlib setup ───────────────────────────────────────────────────────


def setup_matplotlib():
    """Configure matplotlib with dark theme."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print(
            "ERROR: matplotlib is not installed.\n"
            "       Install with: pip install matplotlib",
            file=sys.stderr,
        )
        sys.exit(1)

    plt.rcParams.update(
        {
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "axes.edgecolor": SPINE,
            "axes.labelcolor": FG,
            "axes.titlecolor": FG,
            "text.color": FG,
            "xtick.color": FG,
            "ytick.color": FG,
            "grid.color": GRID,
            "grid.alpha": 0.4,
            "legend.facecolor": "#161b22",
            "legend.edgecolor": SPINE,
            "legend.labelcolor": FG,
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "savefig.facecolor": BG,
            "savefig.edgecolor": BG,
        }
    )
    return plt


def style_axes(ax):
    """Apply common dark-theme axis styling."""
    ax.grid(True, alpha=0.3, color=GRID)
    for spine in ax.spines.values():
        spine.set_color(SPINE)


def add_sparse_note(ax, note_text: str):
    """Add an annotation noting sparse/limited data."""
    ax.annotate(
        note_text,
        xy=(0.98, 0.02),
        xycoords="axes fraction",
        ha="right",
        va="bottom",
        fontsize=8,
        color="#8b949e",
        style="italic",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#161b22", edgecolor=SPINE, alpha=0.8),
    )


def save_plot(fig, output_dir: Path, filename: str) -> Path:
    """Save figure as PNG at 150 DPI and close."""
    out_path = output_dir / filename
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as plt

    plt.close(fig)
    print(f"  ✓ {out_path}")
    return out_path


# ─── Plot 1: PER vs Distance ──────────────────────────────────────────────


def plot_per_vs_distance(rows: list[dict], output_dir: Path, plt):
    """PER vs Distance — 4 curves overlaid, log-scale Y axis."""
    fig, ax = plt.subplots(figsize=(10, 6))
    style_axes(ax)

    has_data = False
    sparse_note = None

    for path_cat in ["HF_FLRC", "HF_LORA", "LF_LORA", "LF_FLRC"]:
        dist_groups = group_by_distance(rows, path_cat)
        if not dist_groups:
            continue

        distances = sorted(dist_groups.keys())
        per_vals = []
        for d in distances:
            group = dist_groups[d]
            pers = [r["_per"] for r in group if r["_per"] is not None]
            med = median_safe(pers)
            per_vals.append(med)

        # Filter out None PER values
        plot_d = [d for d, p in zip(distances, per_vals) if p is not None]
        plot_p = [p for p in per_vals if p is not None]

        if plot_d:
            has_data = True
            color = PATH_COLORS.get(path_cat, "#888")
            ax.plot(
                plot_d,
                plot_p,
                "o-",
                color=color,
                label=path_cat,
                markersize=6,
                linewidth=2,
            )

        if len(plot_d) <= 1:
            sparse_note = "⚠ Sparse data — more distance points needed"

    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("Packet Error Rate (%)")
    ax.set_title("PER vs Distance — All Paths")
    ax.set_yscale("log")
    ax.set_ylim(bottom=0.1, top=105)
    ax.legend(loc="best", framealpha=0.9)

    if sparse_note:
        add_sparse_note(ax, sparse_note)
    if not has_data:
        add_sparse_note(ax, "No PER vs distance data available yet")

    fig.tight_layout()
    return save_plot(fig, output_dir, "01_per_vs_distance.png")


# ─── Plot 2: RSSI vs Distance ─────────────────────────────────────────────


def plot_rssi_vs_distance(rows: list[dict], output_dir: Path, plt):
    """RSSI vs Distance — 4 curves + theoretical FSPL."""
    fig, ax = plt.subplots(figsize=(10, 6))
    style_axes(ax)

    has_data = False
    sparse_note = None

    # Plot measured curves
    for path_cat in ["HF_FLRC", "HF_LORA", "LF_LORA", "LF_FLRC"]:
        dist_groups = group_by_distance(rows, path_cat)
        if not dist_groups:
            continue

        distances = sorted(dist_groups.keys())
        rssi_vals = []
        for d in distances:
            group = dist_groups[d]
            rssi = [r["_rssi_avg"] for r in group if r["_rssi_avg"] is not None]
            med = median_safe(rssi)
            rssi_vals.append(med)

        plot_d = [d for d, r in zip(distances, rssi_vals) if r is not None]
        plot_r = [r for r in rssi_vals if r is not None]

        if plot_d:
            has_data = True
            color = PATH_COLORS.get(path_cat, "#888")
            ax.plot(
                plot_d,
                plot_r,
                "o-",
                color=color,
                label=f"{path_cat} (measured)",
                markersize=6,
                linewidth=2,
            )

        if len(plot_d) <= 1:
            sparse_note = "⚠ Sparse data — more distance points needed"

    # Plot theoretical FSPL curves
    import numpy as np

    fspl_d = np.logspace(
        math.log10(FSPL_MIN_DIST), math.log10(FSPL_MAX_DIST), 200
    )

    for freq, color in FSPL_COLORS.items():
        rssi_on = [
            compute_fspl_rssi(d, freq, TX_POWER_PA_ON) for d in fspl_d
        ]
        ax.plot(
            fspl_d,
            rssi_on,
            "--",
            color=color,
            alpha=0.6,
            linewidth=1.5,
            label=f"FSPL {freq} MHz (PA-on)",
        )

        rssi_off = [
            compute_fspl_rssi(d, freq, TX_POWER_PA_OFF) for d in fspl_d
        ]
        ax.plot(
            fspl_d,
            rssi_off,
            ":",
            color=color,
            alpha=0.4,
            linewidth=1.5,
            label=f"FSPL {freq} MHz (PA-off)",
        )

    ax.set_xscale("log")
    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("RSSI (dBm)")
    ax.set_title("RSSI vs Distance — Measured & Theoretical Free-Space Path Loss")
    ax.legend(loc="best", framealpha=0.9, fontsize=8)

    if sparse_note:
        add_sparse_note(ax, sparse_note)
    if not has_data:
        add_sparse_note(ax, "No RSSI vs distance data available yet")

    fig.tight_layout()
    return save_plot(fig, output_dir, "02_rssi_vs_distance.png")


# ─── Plot 3: Throughput vs Bitrate (FLRC only) ────────────────────────────


def plot_throughput_vs_bitrate(rows: list[dict], output_dir: Path, plt):
    """Throughput vs Bitrate — Bar chart for FLRC modes."""
    fig, ax = plt.subplots(figsize=(10, 6))
    style_axes(ax)

    # Collect FLRC rows with throughput and bitrate data
    flrc_rows = [
        r
        for r in rows
        if r.get("_path_cat", "").endswith("FLRC")
        and r.get("_throughput") is not None
        and r.get("_bitrate") is not None
        and r["_bitrate"] > 0
    ]

    if not flrc_rows:
        ax.text(
            0.5,
            0.5,
            "No FLRC throughput data available\n\nRun FLRC bitrate sweep to populate this chart",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=12,
            color="#8b949e",
        )
        ax.set_title("Throughput vs Bitrate (FLRC Only)")
        ax.set_xlabel("Configured Bitrate (kbps)")
        ax.set_ylabel("Measured Throughput (kbps)")
        fig.tight_layout()
        return save_plot(fig, output_dir, "03_throughput_vs_bitrate.png")

    # Group by (path_cat, bitrate), compute median throughput
    groups: dict[tuple[str, float], list[float]] = defaultdict(list)
    for r in flrc_rows:
        key = (r["_path_cat"], r["_bitrate"])
        groups[key].append(r["_throughput"])

    # Sort by path then bitrate
    sorted_keys = sorted(groups.keys(), key=lambda k: (k[0], k[1]))

    labels = []
    throughputs = []
    colors = []
    for (path_cat, bitrate) in sorted_keys:
        med = median_safe(groups[(path_cat, bitrate)])
        labels.append(f"{path_cat}\n{int(bitrate)}k")
        throughputs.append(med)
        colors.append(PATH_COLORS.get(path_cat, "#888"))

    x = range(len(labels))
    bars = ax.bar(x, throughputs, color=colors, width=0.6, edgecolor=SPINE, linewidth=0.5)

    # Annotate bars with values
    for bar, val in zip(bars, throughputs):
        if val is not None:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{val:.1f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color=FG,
            )

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_xlabel("Path / Configured Bitrate")
    ax.set_ylabel("Measured Throughput (kbps)")
    ax.set_title("Throughput vs Bitrate (FLRC Only)")

    # Add legend for path colours
    import matplotlib.patches as mpatches

    legend_handles = [
        mpatches.Patch(color=PATH_COLORS[cat], label=cat)
        for cat in ["HF_FLRC", "LF_FLRC"]
        if any(k[0] == cat for k in sorted_keys)
    ]
    if legend_handles:
        ax.legend(handles=legend_handles, loc="best", framealpha=0.9)

    fig.tight_layout()
    return save_plot(fig, output_dir, "03_throughput_vs_bitrate.png")


# ─── Plot 4: PA Impact ────────────────────────────────────────────────────


def plot_pa_impact(rows: list[dict], output_dir: Path, plt):
    """PA Impact — RSSI PA-on vs PA-off at each distance."""
    import numpy as np

    fig, ax = plt.subplots(figsize=(10, 6))
    style_axes(ax)

    # Collect rows with both RSSI and distance
    valid_rows = [
        r
        for r in rows
        if r.get("_rssi_avg") is not None
        and r.get("_distance") is not None
        and r["_distance"] >= 0
    ]

    pa_on = [r for r in valid_rows if r["_pa_state"] == "ON"]
    pa_off = [r for r in valid_rows if r["_pa_state"] == "OFF"]

    if not pa_on and not pa_off:
        ax.text(
            0.5,
            0.5,
            "No PA comparison data available\n\nRun tests with PA-on and PA-off\nat known distances to populate this chart",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=12,
            color="#8b949e",
        )
        ax.set_title("PA Impact — RSSI PA-on vs PA-off")
        ax.set_xlabel("Distance (m)")
        ax.set_ylabel("RSSI (dBm)")
        fig.tight_layout()
        return save_plot(fig, output_dir, "04_pa_impact.png")

    has_comparison = bool(pa_on and pa_off)

    def _group_and_plot(data_rows, label, color, marker):
        if not data_rows:
            return
        # Group by distance
        dist_groups: dict[float, list[float]] = defaultdict(list)
        for r in data_rows:
            d = round(r["_distance"], 1)
            dist_groups[d].append(r["_rssi_avg"])

        distances = sorted(dist_groups.keys())
        rssi_vals = [median_safe(dist_groups[d]) for d in distances]

        ax.plot(
            distances,
            rssi_vals,
            marker,
            color=color,
            label=label,
            markersize=7,
            linewidth=2,
        )

    _group_and_plot(pa_on, "PA-on (≥12.5 dBm)", "#3fb950", "s-")
    _group_and_plot(pa_off, "PA-off (0 dBm)", "#f85149", "^--")

    # If we have both PA states with matching distances, also try a grouped bar
    # But lines are cleaner for varying distances
    if has_comparison:
        # Group by distance for both states
        all_distances = sorted(
            set(round(r["_distance"], 1) for r in valid_rows)
        )
        bar_width = max(0.3, min(all_distances) * 0.15) if all_distances else 0.5

        # Use bar chart if distances are discrete and few
        if len(all_distances) <= 10:
            ax2 = ax  # overlay on same axes
            x = np.arange(len(all_distances))
            on_rssi = []
            off_rssi = []
            for d in all_distances:
                on_vals = [r["_rssi_avg"] for r in pa_on if round(r["_distance"], 1) == d]
                off_vals = [r["_rssi_avg"] for r in pa_off if round(r["_distance"], 1) == d]
                on_rssi.append(median_safe(on_vals))
                off_rssi.append(median_safe(off_vals))

            # Replace None with nan for matplotlib bar compatibility
            on_plot = [v if v is not None else float("nan") for v in on_rssi]
            off_plot = [v if v is not None else float("nan") for v in off_rssi]

            # Clear and redo as grouped bar
            ax.clear()
            style_axes(ax)

            bars_on = ax.bar(
                x - bar_width / 2,
                on_plot,
                bar_width,
                color="#3fb950",
                label="PA-on",
                edgecolor=SPINE,
                linewidth=0.5,
            )
            bars_off = ax.bar(
                x + bar_width / 2,
                off_plot,
                bar_width,
                color="#f85149",
                label="PA-off",
                edgecolor=SPINE,
                linewidth=0.5,
            )

            for bar, val in zip(bars_on, on_rssi):
                if val is not None:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.3,
                        f"{val:.0f}",
                        ha="center",
                        va="bottom",
                        fontsize=7,
                        color="#3fb950",
                    )
            for bar, val in zip(bars_off, off_rssi):
                if val is not None:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.3,
                        f"{val:.0f}",
                        ha="center",
                        va="bottom",
                        fontsize=7,
                        color="#f85149",
                    )

            ax.set_xticks(x)
            ax.set_xticklabels([f"{d:.0f}m" for d in all_distances], fontsize=9)
            ax.set_xlabel("Distance (m)")
            ax.set_ylabel("RSSI (dBm)")
            ax.set_title("PA Impact — RSSI PA-on vs PA-off at Each Distance")
            ax.legend(loc="best", framealpha=0.9)

            if len(all_distances) <= 2:
                add_sparse_note(ax, "⚠ Sparse data — more distance points needed")
        # else: lines already plotted above
    else:
        ax.set_xlabel("Distance (m)")
        ax.set_ylabel("RSSI (dBm)")
        ax.set_title("PA Impact — RSSI PA-on vs PA-off")
        ax.legend(loc="best", framealpha=0.9)
        missing = "PA-off" if not pa_off else "PA-on"
        add_sparse_note(ax, f"⚠ No {missing} data for comparison")

    fig.tight_layout()
    return save_plot(fig, output_dir, "04_pa_impact.png")


# ─── Plot 5: Sensitivity Comparison ────────────────────────────────────────


def plot_sensitivity(rows: list[dict], output_dir: Path, plt):
    """Sensitivity Comparison — LoRa SF7 vs SF9 vs SF12, PER vs distance."""
    fig, ax = plt.subplots(figsize=(10, 6))
    style_axes(ax)

    # Collect LoRa rows with PER and distance
    lora_rows = [
        r
        for r in rows
        if "LORA" in (r.get("_path_cat") or "")
        and r.get("_sf") is not None
        and r.get("_per") is not None
        and r.get("_distance") is not None
    ]

    # Also try rows without distance but with PER (for baseline)
    lora_no_dist = [
        r
        for r in rows
        if "LORA" in (r.get("_path_cat") or "")
        and r.get("_sf") is not None
        and r.get("_per") is not None
        and (r.get("_distance") is None)
    ]

    has_data = False
    sparse_note = None

    # Group by SF, then by distance
    for sf in [7, 9, 12]:
        sf_rows = [r for r in lora_rows if r["_sf"] == sf]
        if not sf_rows:
            continue

        # Group by distance
        dist_groups: dict[float, list[float]] = defaultdict(list)
        for r in sf_rows:
            d = round(r["_distance"], 1)
            dist_groups[d].append(r["_per"])

        distances = sorted(dist_groups.keys())
        per_vals = [median_safe(dist_groups[d]) for d in distances]

        plot_d = [d for d, p in zip(distances, per_vals) if p is not None]
        plot_p = [p for p in per_vals if p is not None]

        if plot_d:
            has_data = True
            color = SF_COLORS.get(sf, "#888")
            label_parts = [f"SF{sf}"]
            # Include band info
            bands = set(r.get("_path_cat", "") for r in sf_rows)
            if bands:
                label_parts.append(f"({', '.join(sorted(bands))})")
            ax.plot(
                plot_d,
                plot_p,
                "o-",
                color=color,
                label=" ".join(label_parts),
                markersize=6,
                linewidth=2,
            )

        if len(plot_d) <= 1:
            sparse_note = "⚠ Sparse data — more distance points needed"

    # If we have LoRa data but no distance, show a baseline note
    if lora_no_dist and not has_data:
        # Show a bar chart of baseline PER per SF
        sf_pers: dict[int, list[float]] = defaultdict(list)
        for r in lora_no_dist:
            sf_pers[r["_sf"]].append(r["_per"])

        sorted_sfs = sorted(sf_pers.keys())
        if sorted_sfs:
            bars = ax.bar(
                range(len(sorted_sfs)),
                [median_safe(sf_pers[sf]) for sf in sorted_sfs],
                color=[SF_COLORS.get(sf, "#888") for sf in sorted_sfs],
                width=0.5,
                edgecolor=SPINE,
                linewidth=0.5,
            )
            ax.set_xticks(range(len(sorted_sfs)))
            ax.set_xticklabels([f"SF{sf}" for sf in sorted_sfs])
            ax.set_title("LoRa Sensitivity — Baseline PER (indoor, no distance data)")
            ax.set_yscale("log")
            ax.set_ylim(bottom=0.1, top=105)
            add_sparse_note(
                ax, "Indoor baseline only — outdoor distance sweep needed"
            )
            has_data = True

    if not has_data:
        ax.text(
            0.5,
            0.5,
            "No LoRa sensitivity data available\n\nRun distance sweeps with LoRa SF7/SF9/SF12\nto populate this chart",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=12,
            color="#8b949e",
        )
        ax.set_title("Sensitivity Comparison — LoRa SF7 vs SF9 vs SF12")

    if has_data and not lora_no_dist:
        ax.set_xlabel("Distance (m)")
        ax.set_ylabel("Packet Error Rate (%)")
        ax.set_title("Sensitivity Comparison — LoRa SF7 vs SF9 vs SF12")
        ax.set_yscale("log")
        ax.set_ylim(bottom=0.1, top=105)
        ax.legend(loc="best", framealpha=0.9)
        if sparse_note:
            add_sparse_note(ax, sparse_note)

    fig.tight_layout()
    return save_plot(fig, output_dir, "05_sensitivity_comparison.png")


# ─── Summary ────────────────────────────────────────────────────────────────


def print_summary(rows: list[dict]):
    """Print data summary to stderr."""
    print("\n" + "=" * 60, file=sys.stderr)
    print("DATA SUMMARY", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    print(f"\nTotal rows: {len(rows)}", file=sys.stderr)

    # Per-path breakdown
    path_counts: dict[str, int] = defaultdict(int)
    dist_counts: dict[str, int] = defaultdict(int)
    pa_counts: dict[str, int] = defaultdict(int)

    for r in rows:
        cat = r.get("_path_cat") or "(unknown)"
        path_counts[cat] += 1
        if r.get("_distance") is not None:
            dist_counts[cat] += 1
        pa_counts[r.get("_pa_state", "UNKNOWN")] += 1

    print(f"\nPer-path breakdown:", file=sys.stderr)
    print(
        f"  {'Path':<12s} {'Rows':>6s} {'With dist':>10s}",
        file=sys.stderr,
    )
    print(f"  {'-'*12} {'-'*6} {'-'*10}", file=sys.stderr)
    for cat in sorted(path_counts):
        print(
            f"  {cat:<12s} {path_counts[cat]:>6d} {dist_counts.get(cat, 0):>10d}",
            file=sys.stderr,
        )

    print(f"\nPA state: {dict(pa_counts)}", file=sys.stderr)

    # Unique distances
    distances = sorted(set(r["_distance"] for r in rows if r.get("_distance") is not None))
    if distances:
        print(f"\nDistances (m): {distances}", file=sys.stderr)
    else:
        print("\n⚠ No distance data found — plots will show sparse-data notes", file=sys.stderr)

    print(file=sys.stderr)


# ─── Main ───────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate characterization charts from unified CSV data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python3 tools/plot_characterization.py data/results_unified.csv
  python3 tools/plot_characterization.py data/results_unified.csv --output-dir plots/
""",
    )
    parser.add_argument(
        "csv_file", help="Path to unified CSV file"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="plots/",
        help="Output directory for PNG plots (default: plots/)",
    )
    args = parser.parse_args()

    # Validate CSV
    if not os.path.isfile(args.csv_file):
        print(f"ERROR: file not found: {args.csv_file}", file=sys.stderr)
        return 2

    # Create output dir
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load and enrich data
    rows = load_csv(args.csv_file)
    if not rows:
        print(f"ERROR: no data rows in {args.csv_file}", file=sys.stderr)
        return 1

    rows = enrich_rows(rows)

    # Summary
    print_summary(rows)

    # Setup matplotlib
    plt = setup_matplotlib()

    # Generate all plots
    print(f"\nGenerating plots → {output_dir}/\n", file=sys.stderr)

    plot_per_vs_distance(rows, output_dir, plt)
    plot_rssi_vs_distance(rows, output_dir, plt)
    plot_throughput_vs_bitrate(rows, output_dir, plt)
    plot_pa_impact(rows, output_dir, plt)
    plot_sensitivity(rows, output_dir, plt)

    print(f"\nDone — 5 plots saved to {output_dir}/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
