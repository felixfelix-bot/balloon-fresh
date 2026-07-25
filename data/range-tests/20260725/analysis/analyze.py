#!/usr/bin/env python3
"""
Balloon Range Test Analysis — 2026-07-25 capture.

Parses PHASE_RESULT lines from two sweep logs, deduplicates by keeping
the entry with the highest rx count per (sweep, phase), writes a summary
CSV, and renders four matplotlib plots.
"""
import csv
import re
import sys
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

LOGS = [
    (1, Path.home() / "repos/balloon-fresh/data/range-tests/20260725/forwarded-040152.log"),
    (2, Path.home() / "repos/balloon-fresh/data/range-tests/20260725/forwarded-040519.log"),
]
OUT_DIR = Path.home() / "repos/balloon-fresh/data/range-tests/20260725/analysis"

# Dark theme
plt.style.use("dark_background")

# ─── Parsing ────────────────────────────────────────────────────────────────

PHASE_RE = re.compile(
    r"^PHASE_RESULT\s+"
    r"(?P<phase>\d+)\s+"
    r"(?P<mode>\S+)\s+"
    r"pktSize=(?P<pktSize>\d+)\s+"
    r"rx=(?P<rx>\d+)\s+"
    r"unique=(?P<unique>\d+)\s+"
    r"lost=(?P<lost>\d+)\s+"
    r"per=(?P<per>[\d.]+)\s+"
    r"rssi_avg=(?P<rssi_avg>-?\d+)\s+"
    r"rssi_min=(?P<rssi_min>-?\d+)\s+"
    r"crc_err=(?P<crc_err>\d+)\s+"
    r"garbage=(?P<garbage>\d+)"
)


def parse_mode(mode_str):
    """
    Split mode token like 'HF-LoRa-SF7-64' or 'CH-2412-FLRC1300-64' or
    'LF-FLRC-325-255' into (band, modulation, detail, label).

    band:        HF | LF | CH (channel scan; treated by caller)
    modulation:  LoRa | FLRC | FLRC1300 etc.
    detail:      SF7/SF9/SF12 or bandwidth 325/650/1300/2600 or channel tag
    """
    parts = mode_str.split("-")
    band = parts[0]            # HF | LF | CH
    rest = parts[1:]
    modulation = "LoRa" if rest and rest[0] == "LoRa" else "FLRC"
    detail = "-".join(rest)    # e.g. SF7-64, FLRC1300-64, 325-255
    return band, modulation, detail


def parse_logs():
    """Return list of dicts (one per kept PHASE_RESULT)."""
    # best[(sweep, phase)] = (rx, row_dict)
    best = {}
    for sweep, path in LOGS:
        if not path.exists():
            print(f"WARN: missing {path}", file=sys.stderr)
            continue
        with path.open() as f:
            for line in f:
                line = line.strip()
                # Strip the leading "NNN|" line-number prefix if present
                # (read_file adds it; raw logs do not). Robust either way.
                m_prefix = re.match(r"^\d+\|(.*)$", line)
                if m_prefix:
                    line = m_prefix.group(1)
                m = PHASE_RE.match(line)
                if not m:
                    continue
                d = m.groupdict()
                for k in ("phase", "pktSize", "rx", "unique", "lost",
                          "rssi_avg", "rssi_min", "crc_err", "garbage"):
                    d[k] = int(d[k])
                d["per"] = float(d["per"])
                d["sweep"] = sweep
                d["mode_raw"] = d["mode"]
                band, mod, detail = parse_mode(d["mode"])
                d["band"] = band
                d["modulation"] = mod
                d["detail"] = detail
                key = (sweep, d["phase"], d["mode"])
                prev = best.get(key)
                if prev is None or d["rx"] > prev["rx"]:
                    best[key] = d
    return list(best.values())


def mode_label(row):
    """Short human label for charts, e.g. 'LF LoRa SF7'."""
    b = row["band"]
    m = row["modulation"]
    # Extract the speed/SF token
    detail = row["detail"]
    # detail like 'SF7-64' or 'FLRC1300-64' or '325-255' or '2412-FLRC1300-64'
    if m == "LoRa":
        sf = detail.split("-")[0]              # SF7
        return f"{b} LoRa {sf}"
    else:
        # FLRC: pull bandwidth from detail
        # detail could be 'FLRC1300-64' (HF), '325-255' (LF), '2412-FLRC1300-64' (CH)
        bw = None
        if "FLRC" in detail:
            # e.g. 'FLRC1300-64' -> 1300 ; '2412-FLRC1300-64' -> 1300
            mm = re.search(r"FLRC(\d+)", detail)
            if mm:
                bw = mm.group(1)
        else:
            # '325-255' -> first token
            bw = detail.split("-")[0]
        if bw:
            return f"{b} FLRC {bw}"
        return f"{b} FLRC"


# ─── CSV output ─────────────────────────────────────────────────────────────

def write_csv(rows):
    out = OUT_DIR / "sweep-summary.csv"
    fields = ["phase", "mode", "band", "modulation", "detail", "pktSize",
              "rx", "unique", "lost", "per", "rssi_avg", "crc_err",
              "garbage", "sweep"]
    rows_sorted = sorted(rows, key=lambda r: (r["sweep"], r["phase"]))
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows_sorted:
            w.writerow(r)
    print(f"CSV written: {out}  ({len(rows_sorted)} rows)")


# ─── Plots ──────────────────────────────────────────────────────────────────

BAND_COLORS = {"HF": "#e74c3c", "LF": "#3498db", "CH": "#9b59b6"}


def _save(fig, name):
    path = OUT_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot saved: {path}")


def _prep_series(rows):
    """Aggregate per mode_label: average PER, RSSI, total rx. Returns sorted."""
    agg = defaultdict(lambda: {"per": [], "rssi": [], "rx": [],
                               "band": None, "mod": None})
    for r in rows:
        lbl = mode_label(r)
        agg[lbl]["per"].append(r["per"])
        agg[lbl]["rssi"].append(r["rssi_avg"] if r["rssi_avg"] != 0 else np.nan)
        agg[lbl]["rx"].append(r["rx"])
        agg[lbl]["band"] = r["band"]
        agg[lbl]["mod"] = r["modulation"]
    out = []
    for lbl, v in agg.items():
        out.append({
            "label": lbl,
            "per": float(np.nanmean(v["per"])) if v["per"] else 0.0,
            "rssi": float(np.nanmean(v["rssi"])) if v["rssi"] else np.nan,
            "rx": sum(v["rx"]),
            "band": v["band"],
            "mod": v["mod"],
        })
    # Sort: HF LoRa, HF FLRC, LF LoRa, LF FLRC, CH FLRC
    def sort_key(x):
        order = {"HF": 0, "LF": 1, "CH": 2}
        mod_order = {"LoRa": 0, "FLRC": 1}
        return (order.get(x["band"], 9), mod_order.get(x["mod"], 9), x["label"])
    out.sort(key=sort_key)
    return out


def plot_per(series):
    fig, ax = plt.subplots(figsize=(14, 6))
    labels = [s["label"] for s in series]
    pers = [s["per"] for s in series]
    colors = [BAND_COLORS.get(s["band"], "#888") for s in series]
    x = np.arange(len(labels))
    bars = ax.bar(x, pers, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Packet Error Rate (%)")
    ax.set_title("PER by Mode (avg over both sweeps; lower is better)")
    ax.set_ylim(0, 105)
    ax.axhline(50, color="#888", ls="--", lw=0.7, alpha=0.5)
    for bar, val in zip(bars, pers):
        ax.text(bar.get_x() + bar.get_width()/2, val + 1.5,
                f"{val:.0f}%", ha="center", va="bottom", fontsize=7)
    # legend
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=c, label=b) for b, c in BAND_COLORS.items()]
    ax.legend(handles=handles, loc="upper right")
    ax.grid(axis="y", alpha=0.2)
    _save(fig, "per-by-mode.png")


def plot_rssi(series):
    fig, ax = plt.subplots(figsize=(14, 6))
    labels = [s["label"] for s in series]
    rssis = [s["rssi"] for s in series]
    colors = [BAND_COLORS.get(s["band"], "#888") for s in series]
    x = np.arange(len(labels))
    bars = ax.bar(x, rssis, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("RSSI (dBm)")
    ax.set_title("RSSI by Mode (avg over both sweeps; stronger = closer to 0)")
    for bar, val in zip(bars, rssis):
        if np.isnan(val):
            continue
        ax.text(bar.get_x() + bar.get_width()/2, val - 1.5,
                f"{val:.0f}", ha="center", va="top", fontsize=7)
    ax.grid(axis="y", alpha=0.2)
    _save(fig, "rssi-by-mode.png")


def plot_rx(series):
    fig, ax = plt.subplots(figsize=(14, 6))
    labels = [s["label"] for s in series]
    rxs = [s["rx"] for s in series]
    colors = [BAND_COLORS.get(s["band"], "#888") for s in series]
    x = np.arange(len(labels))
    bars = ax.bar(x, rxs, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Packets received (sum across sweeps)")
    ax.set_title("Packet Throughput by Mode (higher = more received)")
    for bar, val in zip(bars, rxs):
        ax.text(bar.get_x() + bar.get_width()/2, val + 1,
                f"{val}", ha="center", va="bottom", fontsize=7)
    ax.grid(axis="y", alpha=0.2)
    _save(fig, "rx-by-mode.png")


def plot_flrc_per_vs_bw(rows):
    """FLRC PER vs bandwidth (325/650/1300/2600), both HF and LF bands."""
    bw_order = [325, 650, 1300, 2600]
    by_band_bw = defaultdict(list)  # (band, bw) -> [per,...]
    for r in rows:
        if r["modulation"] != "FLRC":
            continue
        if r["band"] not in ("HF", "LF"):
            continue
        # Extract bandwidth number from detail
        bw = None
        m = re.search(r"FLRC(\d+)", r["detail"])
        if m:
            bw = int(m.group(1))
        else:
            try:
                bw = int(r["detail"].split("-")[0])
            except ValueError:
                pass
        if bw is None or bw not in bw_order:
            continue
        by_band_bw[(r["band"], bw)].append(r["per"])

    fig, ax = plt.subplots(figsize=(9, 6))
    width = 0.35
    x = np.arange(len(bw_order))
    for i, band in enumerate(("HF", "LF")):
        vals = []
        for bw in bw_order:
            pers = by_band_bw.get((band, bw), [])
            vals.append(float(np.mean(pers)) if pers else np.nan)
        offset = (i - 0.5) * width
        bars = ax.bar(x + offset, vals, width, label=band,
                      color=BAND_COLORS[band], edgecolor="white", linewidth=0.5)
        for bar, val in zip(bars, vals):
            if np.isnan(val):
                continue
            ax.text(bar.get_x() + bar.get_width()/2, val + 1.5,
                    f"{val:.0f}%", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{b} kbps" for b in bw_order])
    ax.set_ylabel("Packet Error Rate (%)")
    ax.set_title("FLRC PER vs Bandwidth — HF (2.4 GHz) vs LF (sub-GHz)")
    ax.set_ylim(0, 60)
    ax.legend()
    ax.grid(axis="y", alpha=0.2)
    _save(fig, "flrc-per-vs-bw.png")


# ─── Summary table ──────────────────────────────────────────────────────────

def print_summary(rows):
    print("\n" + "=" * 110)
    print("RANGE TEST SUMMARY  —  2026-07-25  (best-rx per phase, both sweeps)")
    print("=" * 110)
    hdr = (f"{'sw':>2} {'ph':>3} {'mode':<26} {'pkt':>4} {'rx':>4} "
           f"{'uniq':>4} {'lost':>4} {'per%':>6} {'rssi':>5} "
           f"{'crc':>3} {'garb':>4}")
    print(hdr)
    print("-" * 110)
    for r in sorted(rows, key=lambda r: (r["sweep"], r["phase"], r["mode_raw"])):
        print(f"{r['sweep']:>2} {r['phase']:>3} {r['mode_raw']:<26} "
              f"{r['pktSize']:>4} {r['rx']:>4} {r['unique']:>4} "
              f"{r['lost']:>4} {r['per']:>6.1f} {r['rssi_avg']:>5} "
              f"{r['crc_err']:>3} {r['garbage']:>4}")
    print("-" * 110)
    print(f"Total kept rows: {len(rows)}")


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    rows = parse_logs()
    print(f"Parsed {len(rows)} unique (sweep, phase, mode) entries "
          f"(after dedup by highest rx).")
    write_csv(rows)
    series = _prep_series(rows)
    plot_per(series)
    plot_rssi(series)
    plot_rx(series)
    plot_flrc_per_vs_bw(rows)
    print_summary(rows)


if __name__ == "__main__":
    main()
