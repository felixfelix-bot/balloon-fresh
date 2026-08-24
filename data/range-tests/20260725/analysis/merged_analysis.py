#!/usr/bin/env python3
"""
Merged 3-sweep balloon range test analysis.

Inputs:
  ../forwarded-040152.log  (sweep 1)
  ../forwarded-040519.log  (sweep 2)
  ../forwarded-040913.log  (sweep 3)

Outputs (in this directory):
  merged-3sweep.csv
  merged-per-by-mode.png
  merged-rssi-by-mode.png
  merged-throughput.png
  flrc-per-vs-bw-merged.png
  consistency.png
  mode-reliability-matrix.png
  plus a stdout text summary.
"""
import csv
import os
import re
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.style.use("dark_background")

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)

SWEEPS = [
    (1, os.path.join(PARENT, "forwarded-040152.log")),
    (2, os.path.join(PARENT, "forwarded-040519.log")),
    (3, os.path.join(PARENT, "forwarded-040913.log")),
]

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_PHASE_RE = re.compile(r"^PHASE_RESULT\s+(\d+)\s+(\S+)\s+(.*)$")


def _kv(s):
    """Parse 'key=value key=value' tail into a dict with typed values."""
    out = {}
    for tok in s.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            try:
                out[k] = int(v)
            except ValueError:
                try:
                    out[k] = float(v)
                except ValueError:
                    out[k] = v
    return out


def parse_sweep(sweep_id, path):
    """Return list of dicts, one per PHASE_RESULT line, with sweep annotation."""
    rows = []
    with open(path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("PHASE_RESULT"):
                continue
            m = _PHASE_RE.match(line)
            if not m:
                continue
            phase = int(m.group(1))
            mode = m.group(2)
            kv = _kv(m.group(3))
            row = {
                "sweep": sweep_id,
                "phase": phase,
                "mode": mode,
                "pktSize": kv.get("pktSize", 0),
                "rx": kv.get("rx", 0),
                "unique": kv.get("unique", 0),
                "lost": kv.get("lost", 0),
                "per": float(kv.get("per", 100.0)),
                "rssi_avg": kv.get("rssi_avg", 0),
                "rssi_min": kv.get("rssi_min", 0),
                "crc_err": kv.get("crc_err", 0),
                "garbage": kv.get("garbage", 0),
                "sats": kv.get("sats", 0),
                "fix": kv.get("fix", 0),
            }
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Mode interpretation
# ---------------------------------------------------------------------------


def band_of(mode):
    """HF / LF / CH."""
    return mode.split("-", 1)[0]


def modulation_of(mode):
    """LoRa or FLRC."""
    if "LoRa" in mode:
        return "LoRa"
    if "FLRC" in mode:
        return "FLRC"
    return "Unknown"


def pkt_size_of(mode):
    """Trailing integer after last '-'."""
    parts = mode.split("-")
    try:
        return int(parts[-1])
    except ValueError:
        return None


def flrc_bw_of(mode):
    """FLRC bandwidth in kbps (325/650/1300/2600) or None."""
    if "FLRC" not in mode:
        return None
    for bw in (325, 650, 1300, 2600):
        if f"-{bw}-" in mode or mode.endswith(f"-{bw}"):
            return bw
    # CH modes embed bandwidth in the modulation token, e.g. CH-2417-FLRC1300-64
    m = re.search(r"FLRC(\d+)", mode)
    if m:
        return int(m.group(1))
    return None


def lora_sf_of(mode):
    if "LoRa" not in mode:
        return None
    m = re.search(r"SF(\d+)", mode)
    return int(m.group(1)) if m else None


def channel_freq_of(mode):
    """For CH-* modes, return the frequency MHz as int (else None)."""
    if not mode.startswith("CH-"):
        return None
    try:
        return int(mode.split("-")[1])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    # 1. Parse all sweeps
    all_rows = []
    raw_counts = {}
    for sweep_id, path in SWEEPS:
        rows = parse_sweep(sweep_id, path)
        raw_counts[sweep_id] = len(rows)
        all_rows.extend(rows)
    print(f"Parsed {len(all_rows)} raw PHASE_RESULT rows "
          f"(sweep1={raw_counts[1]}, sweep2={raw_counts[2]}, sweep3={raw_counts[3]})")

    # 2. Filter out noise:
    #    - rx=0 lines = missed phase (drop from decoded stats but note)
    #    - rx=1 AND per=99.0 = boundary desync noise
    missed = [r for r in all_rows if r["rx"] == 0]
    boundary = [r for r in all_rows if r["rx"] == 1 and abs(r["per"] - 99.0) < 0.01]
    print(f"Filtered: {len(missed)} rx=0 missed-phase lines, "
          f"{len(boundary)} rx=1/per=99 boundary-noise lines")

    keep = [r for r in all_rows if r["rx"] > 1 or (r["rx"] == 1 and abs(r["per"] - 99.0) >= 0.01)]
    # Also drop anything that's an explicit SKIP mode marker
    keep = [r for r in keep if "SKIP" not in r["mode"]]
    print(f"After filter+SKIP removal: {len(keep)} usable rows")

    # 3. Deduplicate: keep highest rx per (sweep, phase, mode)
    best = {}
    for r in keep:
        key = (r["sweep"], r["phase"], r["mode"])
        if key not in best or r["rx"] > best[key]["rx"]:
            best[key] = r
    dedup = list(best.values())
    print(f"After dedup (highest rx per sweep/phase/mode): {len(dedup)} rows")

    # 4. Write merged CSV
    csv_path = os.path.join(HERE, "merged-3sweep.csv")
    fieldnames = [
        "sweep", "phase", "mode", "band", "modulation", "pktSize",
        "rx", "unique", "lost", "per", "rssi_avg", "rssi_min",
        "crc_err", "garbage", "sats", "fix",
    ]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in sorted(dedup, key=lambda x: (x["sweep"], x["phase"], x["mode"])):
            rr = dict(r)
            rr["band"] = band_of(r["mode"])
            rr["modulation"] = modulation_of(r["mode"])
            w.writerow({k: rr.get(k, "") for k in fieldnames})
    print(f"Wrote merged CSV -> {csv_path}")

    # 5. Per-mode aggregation across all sweeps
    by_mode = defaultdict(list)
    for r in dedup:
        by_mode[r["mode"]].append(r)

    agg_rows = []
    for mode, rows in by_mode.items():
        pers = np.array([r["per"] for r in rows], dtype=float)
        rssis = np.array([r["rssi_avg"] for r in rows], dtype=float)
        crcs = np.array([r["crc_err"] for r in rows], dtype=float)
        garbs = np.array([r["garbage"] for r in rows], dtype=float)
        total_rx = sum(r["rx"] for r in rows)
        total_lost = sum(r["lost"] for r in rows)
        sweeps_seen = sorted({r["sweep"] for r in rows})
        agg_rows.append({
            "mode": mode,
            "band": band_of(mode),
            "modulation": modulation_of(mode),
            "pktSize": pkt_size_of(mode),
            "flrc_bw": flrc_bw_of(mode),
            "lora_sf": lora_sf_of(mode),
            "n_obs": len(rows),
            "n_sweeps": len(sweeps_seen),
            "sweeps": sweeps_seen,
            "per_mean": float(pers.mean()),
            "per_std": float(pers.std(ddof=1)) if len(pers) > 1 else 0.0,
            "rssi_mean": float(rssis.mean()),
            "rssi_std": float(rssis.std(ddof=1)) if len(rssis) > 1 else 0.0,
            "total_rx": total_rx,
            "total_lost": total_lost,
            "crc_mean": float(crcs.mean()),
            "garbage_mean": float(garbs.mean()),
        })
    # Sort modes by PER ascending for nicer plots
    agg_rows.sort(key=lambda x: x["per_mean"])

    # also store per-sweep PER for matrix/consistency
    mode_sweep_per = {}  # mode -> {sweep -> [per values]}
    for r in dedup:
        mode_sweep_per.setdefault(r["mode"], {}).setdefault(r["sweep"], []).append(r["per"])

    # ---------------------------------------------------------------------------
    # Plot a) merged-per-by-mode.png
    # ---------------------------------------------------------------------------
    band_colors = {"HF": "#ff5e5e", "LF": "#5e9eff", "CH": "#5effa0"}
    modes_sorted = [r["mode"] for r in agg_rows]
    pers_mean = np.array([r["per_mean"] for r in agg_rows])
    pers_std = np.array([r["per_std"] for r in agg_rows])
    colors = [band_colors.get(r["band"], "#cccccc") for r in agg_rows]

    # Group by band on x-axis: HF first, then LF, then CH, each sorted by PER asc
    band_order = ["HF", "LF", "CH"]
    grouped_modes = []
    grouped_means = []
    grouped_stds = []
    grouped_colors = []
    for b in band_order:
        sub = [r for r in agg_rows if r["band"] == b]
        for r in sub:
            grouped_modes.append(r["mode"])
            grouped_means.append(r["per_mean"])
            grouped_stds.append(r["per_std"])
            grouped_colors.append(band_colors[b])

    fig, ax = plt.subplots(figsize=(14, 8))
    x = np.arange(len(grouped_modes))
    ax.bar(x, grouped_means, yerr=grouped_stds, color=grouped_colors,
           capsize=4, edgecolor="white", linewidth=0.4, alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(grouped_modes, rotation=80, fontsize=8, ha="right")
    ax.set_ylabel("Packet Error Rate (%)", fontsize=11)
    ax.set_title("Merged 3-sweep PER by Mode (mean ± std, grouped by band)", fontsize=12)
    ax.set_ylim(0, max(105, max(grouped_means) * 1.1))
    ax.grid(axis="y", alpha=0.2)
    # band dividers
    cursor = 0
    for b in band_order:
        n = sum(1 for m in grouped_modes if m.startswith(b + "-"))
        if n > 0:
            ax.axvline(cursor - 0.5, color="white", lw=0.5, alpha=0.3)
            ax.text(cursor + n / 2 - 0.5, 102, b, ha="center",
                    fontsize=11, fontweight="bold",
                    color=band_colors[b])
            cursor += n
    # legend
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=band_colors[b], label=f"{b} ({'2.4GHz' if b=='HF' else 'sub-GHz 915MHz' if b=='LF' else 'channel scan'})")
               for b in band_order]
    ax.legend(handles=handles, loc="upper left", fontsize=9)
    plt.tight_layout()
    p = os.path.join(HERE, "merged-per-by-mode.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")

    # ---------------------------------------------------------------------------
    # Plot b) merged-rssi-by-mode.png
    # ---------------------------------------------------------------------------
    # sort by RSSI for nicer view
    rssi_sorted = sorted(agg_rows, key=lambda x: x["rssi_mean"])
    rmodes = [r["mode"] for r in rssi_sorted]
    rmean = np.array([r["rssi_mean"] for r in rssi_sorted])
    rstd = np.array([r["rssi_std"] for r in rssi_sorted])
    rcolors = [band_colors.get(r["band"], "#ccc") for r in rssi_sorted]

    fig, ax = plt.subplots(figsize=(14, 8))
    x = np.arange(len(rmodes))
    ax.bar(x, rmean, yerr=rstd, color=rcolors, capsize=4,
           edgecolor="white", linewidth=0.4, alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(rmodes, rotation=80, fontsize=8, ha="right")
    ax.set_ylabel("RSSI (dBm)", fontsize=11)
    ax.set_title("Merged 3-sweep RSSI by Mode (mean ± std)", fontsize=12)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(handles=handles, loc="lower right", fontsize=9)
    plt.tight_layout()
    p = os.path.join(HERE, "merged-rssi-by-mode.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")

    # ---------------------------------------------------------------------------
    # Plot c) merged-throughput.png  (log scale y of total packets received per mode)
    # ---------------------------------------------------------------------------
    thr_sorted = sorted(agg_rows, key=lambda x: -x["total_rx"])
    tmodes = [r["mode"] for r in thr_sorted]
    trx = np.array([r["total_rx"] for r in thr_sorted])
    tcolors = [band_colors.get(r["band"], "#ccc") for r in thr_sorted]

    fig, ax = plt.subplots(figsize=(14, 8))
    x = np.arange(len(tmodes))
    ax.bar(x, np.maximum(trx, 1), color=tcolors,
           edgecolor="white", linewidth=0.4, alpha=0.9)
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(tmodes, rotation=80, fontsize=8, ha="right")
    ax.set_ylabel("Total packets received (log scale)", fontsize=11)
    ax.set_title("Merged 3-sweep Total Packets Received by Mode", fontsize=12)
    ax.grid(axis="y", which="both", alpha=0.2)
    # annotate values
    for xi, val in zip(x, trx):
        ax.text(xi, val * 1.15 if val > 0 else 1.15, str(int(val)),
                ha="center", fontsize=7, color="white", alpha=0.8)
    ax.legend(handles=handles, loc="upper right", fontsize=9)
    plt.tight_layout()
    p = os.path.join(HERE, "merged-throughput.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")

    # ---------------------------------------------------------------------------
    # Plot d) flrc-per-vs-bw-merged.png
    # ---------------------------------------------------------------------------
    flrc_rows = [r for r in agg_rows if r["modulation"] == "FLRC" and r["flrc_bw"] is not None]
    # split by band (HF vs LF; ignore CH since CH embeds fixed bw=1300)
    fig, ax = plt.subplots(figsize=(14, 8))
    for b, color in (("HF", "#ff5e5e"), ("LF", "#5e9eff")):
        sub = [r for r in flrc_rows if r["band"] == b]
        if not sub:
            continue
        # group by bandwidth: average across pktSizes
        by_bw = defaultdict(list)
        for r in sub:
            by_bw[r["flrc_bw"]].append(r)
        bws = sorted(by_bw.keys())
        means = []
        stds = []
        for bw in bws:
            # combine all observations
            all_pers = []
            for r in by_bw[bw]:
                # spread per-obs across the aggregation — approximate with mean+std
                # for cross-sweep variance use per_obs directly
                pass
            # Better: re-aggregate raw per-obs from dedup for these modes
            ms = [r["mode"] for r in by_bw[bw]]
            obs = [row["per"] for row in dedup if row["mode"] in ms]
            obs = np.array(obs, dtype=float)
            means.append(obs.mean() if len(obs) else 0.0)
            stds.append(obs.std(ddof=1) if len(obs) > 1 else 0.0)
        ax.errorbar(bws, means, yerr=stds, marker="o", markersize=10,
                    capsize=6, linewidth=2, color=color, label=f"{b} ({'2.4GHz' if b=='HF' else 'sub-GHz 915MHz'})")
        for bw, m, s in zip(bws, means, stds):
            ax.annotate(f"{m:.1f}%", (bw, m), textcoords="offset points",
                        xytext=(0, 12), ha="center", fontsize=9, color=color)

    ax.set_xlabel("FLRC Bandwidth (kbps)", fontsize=11)
    ax.set_ylabel("Packet Error Rate (%)", fontsize=11)
    ax.set_title("FLRC PER vs Bandwidth — HF vs LF (3-sweep merged, mean ± std)", fontsize=12)
    ax.set_xticks([325, 650, 1300, 2600])
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=10)
    plt.tight_layout()
    p = os.path.join(HERE, "flrc-per-vs-bw-merged.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")

    # ---------------------------------------------------------------------------
    # Plot e) consistency.png  (per-sweep PER dots, 3 per mode)
    # ---------------------------------------------------------------------------
    cons_modes = [r["mode"] for r in agg_rows]
    fig, ax = plt.subplots(figsize=(14, 8))
    sweep_marker = {1: "o", 2: "s", 3: "^"}
    sweep_color = {1: "#ff5e5e", 2: "#5e9eff", 3: "#5effa0"}
    x = np.arange(len(cons_modes))
    for s in (1, 2, 3):
        ys = []
        for m in cons_modes:
            pers = mode_sweep_per.get(m, {}).get(s, [])
            ys.append(np.mean(pers) if pers else np.nan)
        xs = [xi for xi, y in zip(x, ys) if not np.isnan(y)]
        ys_valid = [y for y in ys if not np.isnan(y)]
        ax.scatter(xs, ys_valid, marker=sweep_marker[s], s=80,
                   color=sweep_color[s], edgecolor="white", linewidth=0.5,
                   label=f"Sweep {s}", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(cons_modes, rotation=80, fontsize=8, ha="right")
    ax.set_ylabel("PER (%) per sweep", fontsize=11)
    ax.set_title("Run-to-Run Consistency: PER in each sweep (3 dots per mode)", fontsize=12)
    ax.set_ylim(-2, 105)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=10, loc="upper left")
    plt.tight_layout()
    p = os.path.join(HERE, "consistency.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")

    # ---------------------------------------------------------------------------
    # Plot f) mode-reliability-matrix.png (heatmap modes x sweeps, color = PER)
    # ---------------------------------------------------------------------------
    matrix_modes = cons_modes
    mat = np.full((len(matrix_modes), 3), np.nan)
    for i, m in enumerate(matrix_modes):
        for j, s in enumerate((1, 2, 3)):
            pers = mode_sweep_per.get(m, {}).get(s, [])
            if pers:
                mat[i, j] = float(np.mean(pers))

    fig, ax = plt.subplots(figsize=(8, max(8, len(matrix_modes) * 0.32)))
    # mask NaN
    masked = np.ma.masked_invalid(mat)
    cmap = plt.cm.RdYlGn_r  # green=low PER good, red=high PER bad
    cmap.set_bad(color="#222222")  # dark for "not tested"
    im = ax.imshow(masked, aspect="auto", cmap=cmap, vmin=0, vmax=100,
                   interpolation="nearest")
    ax.set_xticks(range(3))
    ax.set_xticklabels([f"Sweep {s}" for s in (1, 2, 3)], fontsize=11)
    ax.set_yticks(range(len(matrix_modes)))
    ax.set_yticklabels(matrix_modes, fontsize=8)
    # annotate
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center",
                        fontsize=8, color="black" if v < 50 else "white",
                        fontweight="bold")
            else:
                ax.text(j, i, "—", ha="center", va="center",
                        fontsize=8, color="#666")
    ax.set_title("Mode Reliability Matrix — PER % per sweep\n(green=good, red=bad, dark=not tested)",
                 fontsize=12)
    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label("PER (%)", fontsize=10)
    plt.tight_layout()
    p = os.path.join(HERE, "mode-reliability-matrix.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")

    # ---------------------------------------------------------------------------
    # 7. Comprehensive text summary
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("MERGED 3-SWEEP ANALYSIS — TEXT SUMMARY")
    print("=" * 78)

    total_obs = len(dedup)
    total_rx = sum(r["total_rx"] for r in agg_rows)
    total_lost = sum(r["total_lost"] for r in agg_rows)
    overall_per = 100.0 * total_lost / max(1, total_lost + total_rx)
    print(f"\nTotal unique (sweep,phase,mode) observations: {total_obs}")
    print(f"Total packets received across all modes: {total_rx}")
    print(f"Total packets lost: {total_lost}")
    print(f"Overall PER (weighted by packets): {overall_per:.1f}%")
    print(f"Distinct modes tested: {len(agg_rows)}")

    # Best mode (lowest PER with >5 packets received total)
    eligible = [r for r in agg_rows if r["total_rx"] > 5]
    if eligible:
        best = min(eligible, key=lambda r: r["per_mean"])
        print(f"\nBEST MODE (lowest PER, >5 rx): {best['mode']}")
        print(f"   PER {best['per_mean']:.1f}% ± {best['per_std']:.1f}, "
              f"RSSI {best['rssi_mean']:.0f} dBm, "
              f"rx={best['total_rx']}, sweeps={best['n_sweeps']}")

    # Worst mode (highest PER with at least 1 rx)
    rx_modes = [r for r in agg_rows if r["total_rx"] > 0]
    if rx_modes:
        worst = max(rx_modes, key=lambda r: r["per_mean"])
        print(f"\nWORST MODE (highest PER among modes with any rx): {worst['mode']}")
        print(f"   PER {worst['per_mean']:.1f}% ± {worst['per_std']:.1f}, "
              f"RSSI {worst['rssi_mean']:.0f} dBm, rx={worst['total_rx']}")

    # Most consistent (lowest std, require at least 2 obs)
    multi = [r for r in agg_rows if r["n_obs"] >= 2]
    if multi:
        cons = min(multi, key=lambda r: r["per_std"])
        print(f"\nMOST CONSISTENT MODE (lowest PER std, ≥2 obs): {cons['mode']}")
        print(f"   PER {cons['per_mean']:.1f}% ± {cons['per_std']:.1f} "
              f"(range from {min(mode_sweep_per[cons['mode']].get(s,[100])[0] for s in (1,2,3) if mode_sweep_per[cons['mode']].get(s)):.1f}% "
              f"to {max(np.mean(mode_sweep_per[cons['mode']].get(s,[0])) for s in (1,2,3) if mode_sweep_per[cons['mode']].get(s)):.1f}%)")

    # FLRC bandwidth impact
    print("\n--- FLRC BANDWIDTH IMPACT ---")
    for b in ("HF", "LF"):
        sub = [r for r in agg_rows if r["band"] == b and r["modulation"] == "FLRC"]
        if not sub:
            print(f"  {b}: no FLRC data")
            continue
        bws = sorted({r["flrc_bw"] for r in sub if r["flrc_bw"] is not None})
        print(f"  {b}:")
        for bw in bws:
            ms = [r for r in sub if r["flrc_bw"] == bw]
            obs = [row["per"] for row in dedup if row["mode"] in {r["mode"] for r in ms}]
            obs = np.array(obs, dtype=float)
            print(f"    bw={bw:4d} kbps : PER mean={obs.mean():.1f}% "
                  f"std={obs.std(ddof=1) if len(obs) > 1 else 0:.1f}% "
                  f"(n={len(obs)} obs, modes: {', '.join(r['mode'] for r in ms)})")

    # Channel dead spots
    print("\n--- CHANNEL SCAN DEAD SPOTS ---")
    ch_modes = [r for r in agg_rows if r["band"] == "CH"]
    ch_dead = []
    ch_ok = []
    for r in ch_modes:
        freq = channel_freq_of(r["mode"])
        if freq is None:
            continue
        if r["total_rx"] == 0:
            ch_dead.append((freq, r))
        else:
            ch_ok.append((freq, r))
    if ch_dead:
        print(f"  Dead channels (0 rx across all sweeps):")
        for freq, r in sorted(ch_dead):
            print(f"    {freq} MHz ({r['mode']}): rx=0")
    if ch_ok:
        worst_ch = max(ch_ok, key=lambda fr: fr[1]["per_mean"])
        best_ch = min(ch_ok, key=lambda fr: fr[1]["per_mean"])
        print(f"  Best CH:  {best_ch[0]} MHz ({best_ch[1]['mode']}) "
              f"PER {best_ch[1]['per_mean']:.1f}%")
        print(f"  Worst CH: {worst_ch[0]} MHz ({worst_ch[1]['mode']}) "
              f"PER {worst_ch[1]['per_mean']:.1f}%")

    # Modes that failed in ALL sweeps (rx=0 in every sweep they appear)
    print("\n--- MODES THAT FAILED IN ALL SWEEPS (rx=0 everywhere) ---")
    # use raw missed+keep info: a mode that ONLY ever has rx=0 across all sweeps
    all_modes_seen = {r["mode"] for r in all_rows if "SKIP" not in r["mode"]}
    modes_with_any_rx = {r["mode"] for r in dedup}
    fully_failed = sorted(all_modes_seen - modes_with_any_rx)
    if fully_failed:
        for m in fully_failed:
            print(f"  {m} (only ever rx=0)")
    else:
        print("  (none)")

    # Modes tested in all 3 sweeps
    three_sweep_modes = sorted([r["mode"] for r in agg_rows if r["n_sweeps"] == 3])
    print(f"\nModes tested in ALL 3 sweeps: {len(three_sweep_modes)}")
    for m in three_sweep_modes:
        a = next(r for r in agg_rows if r["mode"] == m)
        sweep_pers = []
        for s in (1, 2, 3):
            ps = mode_sweep_per.get(m, {}).get(s, [])
            if ps:
                sweep_pers.append((s, np.mean(ps)))
        ps_str = ", ".join(f"S{s}={p:.1f}%" for s, p in sweep_pers)
        print(f"  {m:32s} : {ps_str}  | mean={a['per_mean']:.1f}% std={a['per_std']:.1f}%")

    print("\n" + "=" * 78)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
