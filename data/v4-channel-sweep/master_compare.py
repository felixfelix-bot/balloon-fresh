#!/usr/bin/env python3
"""Master comparison: extract per-mode-per-size decode data from every capture.

Produces a unified table: mode x size x capture = rx, per, rssi.
Captures:
  BENCH   = v4-interleave-bench/full_cycle_152954.log (95%, pre-channel-sweep)
  PREFIX  = v4-channel-sweep/rx_sweep_201758.log       (39%, before 7700e22)
  POSTFIX = v4-channel-sweep/rx_sweep_fixed2_204425.log (36%, after 7700e22 + 536b418)
  FINAL   = v4-channel-sweep/rx_sweep_fixed_204825.log  (post b71ae70, extra capture)
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent  # data/

# BENCH test spans multiple files — combine all, take best rx per mode/size
BENCH_FILES = [
    DATA / "v4-interleave-bench" / "full_cycle_152954.log",
    DATA / "v4-interleave-bench" / "synced_run_151652.log",
    DATA / "v4-interleave-bench" / "flrc_focused_154639.log",
    DATA / "v4-interleave-bench" / "phase_sync_155609.log",
    DATA / "v4-interleave-bench" / "rx_interleave_063638.log",
    DATA / "v4-interleave-bench" / "rx_interleave_20260725_063345.log",
]

CAPTURES = [
    ("BENCH",   BENCH_FILES),
    ("PREFIX",  [DATA / "v4-channel-sweep" / "rx_sweep_201758.log"]),
    ("POSTFIX", [DATA / "v4-channel-sweep" / "rx_sweep_fixed2_204425.log"]),
    ("FINAL",   [DATA / "v4-channel-sweep" / "rx_sweep_fixed_204825.log"]),
]

phase_re = re.compile(
    r"PHASE_RESULT\s+(\d+)\s+(\S+)\s+pktSize=(\d+)\s+rx=(\d+)\s+unique=(\d+)"
    r"\s+lost=(\d+)\s+per=([\d.]+)\s+rssi_avg=(-?\d+)\s+rssi_min=(-?\d+)"
    r"\s+crc_err=(\d+)\s+garbage=(\d+)"
)

def parse(log_path):
    """Return list of phase dicts. For duplicate (phase,name,size), keep the best (max rx)."""
    if not log_path.exists():
        return []
    phases = []
    with open(log_path) as f:
        for line in f:
            m = phase_re.search(line)
            if m:
                phases.append({
                    "phase": int(m.group(1)),
                    "name": m.group(2),
                    "pkt_size": int(m.group(3)),
                    "rx": int(m.group(4)),
                    "unique": int(m.group(5)),
                    "lost": int(m.group(6)),
                    "per": float(m.group(7)),
                    "rssi_avg": int(m.group(8)),
                    "rssi_min": int(m.group(9)),
                    "crc_err": int(m.group(10)),
                    "garbage": int(m.group(11)),
                })
    # Dedupe: for repeated (phase, name, size), keep entry with max rx
    best = {}
    for p in phases:
        key = (p["phase"], p["name"], p["pkt_size"])
        if key not in best or p["rx"] > best[key]["rx"]:
            best[key] = p
    return list(best.values())

# Parse all captures (BENCH may span multiple files — merge, take best rx)
captures = {}
for label, paths in CAPTURES:
    merged = {}
    files_str = []
    for path in paths:
        if not path.exists():
            continue
        files_str.append(path.name)
        for p in parse(path):
            k = (p["phase"], p["name"], p["pkt_size"])
            if k not in merged or p["rx"] > merged[k]["rx"]:
                merged[k] = p
    phases = list(merged.values())
    captures[label] = phases
    n = len(phases)
    dec = sum(1 for p in phases if p["rx"] > 0)
    pct = (100.0 * dec / n) if n else 0
    print(f"{label:10s} {'+'.join(files_str)[:50]:52s} phases={n:4d} decoded={dec:3d} ({pct:4.1f}%)")

# Build unified mode list. Key = (band, family, bitrate_or_sf, size)
# e.g. (HF, LoRa, SF7, 32), (HF, FLRC, 325, 32), (CH, 2412, FLRC1300, 64)
def mode_key(p):
    name = p["name"]
    parts = name.split("-")
    if name.startswith("CH-"):
        # CH-2412-FLRC1300-64 or CH-869-...
        freq = parts[1]
        return ("CH", freq, "FLRC", p["pkt_size"])
    elif "FLRC" in name:
        band = parts[0]      # HF / LF
        bitrate = parts[2]   # 325, 650, 1300, 2600
        return (band, "FLRC", bitrate, p["pkt_size"])
    elif "LoRa" in name:
        band = parts[0]
        sf = parts[2] if len(parts) > 2 else "SF?"
        return (band, "LoRa", sf, p["pkt_size"])
    return (name, "", "", p["pkt_size"])

# For each capture: map mode_key -> best phase result
def index(phases):
    idx = {}
    for p in phases:
        k = mode_key(p)
        if k not in idx or p["rx"] > idx[k]["rx"]:
            idx[k] = p
    return idx

cap_idx = {label: index(phases) for label, phases in captures.items()}

# Collect all unique mode keys, ordered by phase number from the FULL PREFIX capture (which has the most)
all_keys = set()
for idx in cap_idx.values():
    all_keys.update(idx.keys())

# Sort: HF first, then LF, then CH. Within each, by phase order if available.
# Use phase from PREFIX capture as canonical order.
phase_order = {}
for p in captures["PREFIX"]:
    k = mode_key(p)
    if k not in phase_order:
        phase_order[k] = p["phase"]
# Fill missing from POSTFIX
for p in captures["POSTFIX"]:
    k = mode_key(p)
    if k not in phase_order:
        phase_order[k] = p["phase"]
for p in captures["FINAL"]:
    k = mode_key(p)
    if k not in phase_order:
        phase_order[k] = p["phase"]
for p in captures["BENCH"]:
    k = mode_key(p)
    if k not in phase_order:
        phase_order[k] = p["phase"]

def sort_key(k):
    band_rank = {"HF": 0, "LF": 1, "CH": 2}.get(k[0], 3)
    return (band_rank, phase_order.get(k, 999))

sorted_keys = sorted(all_keys, key=sort_key)

# Print master table
print("\n" + "=" * 130)
print("MASTER COMPARISON TABLE — rx count (PER% / RSSI dBm)")
print("=" * 130)
header = f"{'Mode':<22} {'Size':>5} | {'BENCH':>16} | {'PREFIX':>16} | {'POSTFIX':>16} | {'FINAL':>16}"
print(header)
print("-" * len(header))

# Group by mode family
def family_str(k):
    band, fam, br, size = k
    if band == "CH":
        return f"CH-{br}"
    return f"{band}-{fam}-{br}"

# Track per-mode-family summaries
fam_stats = defaultdict(lambda: defaultdict(lambda: {"dec": 0, "tot": 0, "rx_sum": 0}))

current_fam = None
for k in sorted_keys:
    fam = family_str(k)
    if fam != current_fam:
        if current_fam is not None:
            print()
        current_fam = fam
    band, famtype, br, size = k
    row = []
    for cap_label in ["BENCH", "PREFIX", "POSTFIX", "FINAL"]:
        p = cap_idx[cap_label].get(k)
        if p is None:
            cell = "—"
        elif p["rx"] == 0:
            cell = "0"
            fam_stats[fam][cap_label]["tot"] += 1
        else:
            cell = f"{p['rx']} ({p['per']:.0f}%/{p['rssi_avg']})"
            fam_stats[fam][cap_label]["dec"] += 1
            fam_stats[fam][cap_label]["tot"] += 1
            fam_stats[fam][cap_label]["rx_sum"] += p["rx"]
        row.append(cell)
    sz = k[3] if k[3] else ""
    print(f"{fam:<22} {sz:>5} | {row[0]:>16} | {row[1]:>16} | {row[2]:>16} | {row[3]:>16}")

print("\n" + "=" * 100)
print("PER-MODE-FAMILY SUMMARY (decoded / captured)")
print("=" * 100)
print(f"{'Mode Family':<22} | {'BENCH':>12} | {'PREFIX':>12} | {'POSTFIX':>12} | {'FINAL':>12} | Verdict")
print("-" * 100)
all_fams = sorted(fam_stats.keys(), key=lambda f: sort_key((f.split("-")[0], "", "", 0)))
for fam in all_fams:
    parts = []
    verdicts = []
    for cap_label in ["BENCH", "PREFIX", "POSTFIX", "FINAL"]:
        s = fam_stats[fam][cap_label]
        if s["tot"] == 0:
            parts.append("—")
            verdicts.append("?")
        else:
            parts.append(f"{s['dec']}/{s['tot']}")
            verdicts.append("✓" if s["dec"] > 0 else "✗")
    # Verdict
    worked_all = all(v == "✓" for v in verdicts if v != "?")
    never_worked = all(v == "✗" for v in verdicts if v != "?")
    if never_worked:
        verdict = "❌ NEVER WORKED"
    elif worked_all:
        verdict = "✅ ALWAYS OK"
    else:
        # broke?
        bench_ok = verdicts[0] == "✓"
        prefix_ok = verdicts[1] == "✓"
        postfix_ok = verdicts[2] == "✓"
        if bench_ok and prefix_ok and not postfix_ok:
            verdict = "⚠️ BROKE after 7700e22"
        elif not bench_ok and prefix_ok and not postfix_ok:
            verdict = "⚠️ bench-fail, prefix-ok, postfix-broke"
        elif bench_ok and not prefix_ok:
            verdict = "⚠️ broke at PREFIX (channel sweep era)"
        else:
            verdict = f"⚠️ mixed ({''.join(verdicts)})"
    print(f"{fam:<22} | {parts[0]:>12} | {parts[1]:>12} | {parts[2]:>12} | {parts[3]:>12} | {verdict}")

# Save machine-readable JSON
import json
out = {
    "captures": {label: [str(p.name) for p in paths] for label, paths in CAPTURES},
    "summary": {},
    "modes": {},
}
for label, phases in captures.items():
    n = len(phases)
    dec = sum(1 for p in phases if p["rx"] > 0)
    out["summary"][label] = {"phases": n, "decoded": dec, "pct": (100.0*dec/n) if n else 0}
for fam in all_fams:
    out["modes"][fam] = {}
    for cap_label in ["BENCH", "PREFIX", "POSTFIX", "FINAL"]:
        s = fam_stats[fam][cap_label]
        out["modes"][fam][cap_label] = dict(s)
with open(Path(__file__).parent / "master_compare.json", "w") as f:
    json.dump(out, f, indent=2)
print(f"\nSaved master_compare.json")
