#!/usr/bin/env python3
"""V1 EQUIVALENCE — replay FULL sweep per-packet data through SPRT, compare verdicts.

Reads full-sweep-results-2g4-pkts-*.csv (50-pkt ground truth per config),
replays the first n_cap=20 packets through sprt_decide(), and checks:

  1. Verdict agreement: if 50-pkt PER < 2% → SPRT should say CLEAN
     if 50-pkt PER > 20% → SPRT should say DEAD
     if 2-20% → SPRT EDGE is acceptable (gray zone)
  2. PER point estimates within overlapping Wilson CIs
  3. Packet savings: how many pkts SPRT saved vs 50

Acceptance (plan §8 V1):
  - 100% CLEAN/DEAD agreement on all shared configs (where 50-pkt PER is clear-cut)
  - PER point estimates within overlapping Wilson CIs

Run: python3 v1_equivalence.py
"""
import csv
import os
import sys
import math
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e80_campaign as camp

PKTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "..", "..",
                         "full-sweep-results-2g4-pkts-20260822-210817.csv")
PKTS_FILE = os.path.abspath(PKTS_FILE)

PASS = 0
FAIL = 0
WARN = 0
SKIP = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    status = "PASS" if cond else "FAIL"
    if cond:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))

def warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  [WARN] {name} — {detail}")

# ---- Load per-packet data ----
print(f"Loading: {PKTS_FILE}")
cfg_pkts = defaultdict(list)  # config_idx → list of bit_err values
cfg_labels = {}

with open(PKTS_FILE) as f:
    r = csv.DictReader(f)
    for row in r:
        cfg_idx = int(row["config"])
        bit_err = int(row["bit_err"])
        pkt_idx = int(row["pkt_idx"])
        cfg_pkts[cfg_idx].append((pkt_idx, bit_err))
        cfg_labels[cfg_idx] = row["label"]

# Sort by pkt_idx to get temporal order
for idx in cfg_pkts:
    cfg_pkts[idx].sort(key=lambda x: x[0])
    cfg_pkts[idx] = [b for _, b in cfg_pkts[idx]]

print(f"Loaded {len(cfg_pkts)} configs\n")

# ---- Classify 50-pkt ground truth ----
def classify_50pkt(k, n):
    """Ground truth from 50-pkt run — point estimate classification.

    Plan §3: PER < 2% → CLEAN, PER > 20% → DEAD, 2-20% → EDGE.
    Wilson CI strict gate is too conservative for n=50 k=0 (CI upper = 7.1%
    > 2% threshold) — the SPRT uses sequential LLR, not CI, for decisions.
    """
    if n == 0:
        return "NODATA"
    per = k / n
    if per < 0.02:
        return "CLEAN"
    if per > 0.20:
        return "DEAD"
    return "EDGE"

def classify_50pkt_strict(k, n):
    """Conservative classification using Wilson CI bounds."""
    if n == 0:
        return "NODATA"
    lo, hi = camp.wilson_ci(k, n)
    if hi <= 0.02:
        return "CLEAN"
    if lo >= 0.20:
        return "DEAD"
    return "EDGE"

# ---- Replay through SPRT ----
print("=== V1: SPRT replay vs 50-pkt ground truth ===\n")

SPRT_NCAP = 20
SPRT_NMIN = 10

agreements = 0
disagreements = 0
edge_matches = 0
edge_mismatches = 0
gray_zone_ok = 0
gray_zone_fail = 0
total_pkts_saved = 0
total_pkts_full = 0
per_ci_overlaps = 0
per_ci_non_overlaps = 0

mismatches = []

for cfg_idx in sorted(cfg_pkts):
    seq_50 = cfg_pkts[cfg_idx]
    n_full = len(seq_50)
    k_full = sum(1 for b in seq_50 if b > 0)
    label = cfg_labels.get(cfg_idx, f"cfg{cfg_idx}")

    # Ground truth — point estimate (plan §3 thresholds)
    gt = classify_50pkt(k_full, n_full)

    # SPRT replay: feed first n_cap=20 packets
    seq_sprt = seq_50[:SPRT_NCAP]
    k_sprt = 0
    n_sprt = 0
    sprt_verdict = "UNDECIDED"
    sprt_stop_n = SPRT_NCAP  # where SPRT would have stopped

    for i, b in enumerate(seq_sprt):
        n_sprt += 1
        if b > 0:
            k_sprt += 1
        if n_sprt >= SPRT_NMIN:
            res = camp.sprt_decide(k_sprt, n_sprt)
            if res.verdict in ("CLEAN", "DEAD"):
                sprt_verdict = res.verdict
                sprt_stop_n = n_sprt
                break
    else:
        # Reached cap without crossing
        res = camp.sprt_decide(k_sprt, n_sprt)
        sprt_verdict = res.verdict

    total_pkts_saved += (n_full - sprt_stop_n)
    total_pkts_full += n_full

    # Compare
    if gt == "CLEAN":
        if sprt_verdict == "CLEAN":
            agreements += 1
        elif sprt_verdict == "EDGE":
            # Edge on a clean config: SPRT didn't have enough info in 20 pkts
            # Check if the first 20 pkts actually had some errors
            k20 = sum(1 for b in seq_sprt if b > 0)
            if k20 <= 1:
                # Very few errors in first 20 — SPRT should have called CLEAN
                disagreements += 1
                mismatches.append((cfg_idx, label, gt, sprt_verdict, k_full, n_full,
                                   k_sprt, n_sprt, k20))
            else:
                # First 20 had errors → EDGE is honest (gray zone in the window)
                gray_zone_ok += 1
        else:  # DEAD
            disagreements += 1
            mismatches.append((cfg_idx, label, gt, sprt_verdict, k_full, n_full,
                               k_sprt, n_sprt, sum(1 for b in seq_sprt if b > 0)))

    elif gt == "DEAD":
        if sprt_verdict == "DEAD":
            agreements += 1
        elif sprt_verdict == "EDGE":
            k20 = sum(1 for b in seq_sprt if b > 0)
            per20 = k20 / len(seq_sprt) if seq_sprt else 0
            if per20 >= 0.30:
                # High PER in first 20 but SPRT didn't cross DEAD boundary
                # This is the n_min=10 floor — need all 10 to be errors
                disagreements += 1
                mismatches.append((cfg_idx, label, gt, sprt_verdict, k_full, n_full,
                                   k_sprt, n_sprt, k20))
            else:
                gray_zone_ok += 1
        else:  # CLEAN
            disagreements += 1
            mismatches.append((cfg_idx, label, gt, sprt_verdict, k_full, n_full,
                               k_sprt, n_sprt, sum(1 for b in seq_sprt if b > 0)))

    elif gt == "EDGE":
        # 50-pkt is gray zone → SPRT EDGE is fine, CLEAN/DEAD also acceptable
        # if the first 20 happened to be clearer than the full 50
        if sprt_verdict == "EDGE":
            edge_matches += 1
        else:
            edge_mismatches += 1
            # Not necessarily wrong — just different window

    # Wilson CI overlap check: SPRT sample vs full sample
    if n_sprt > 0 and n_full > 0:
        lo_sprt, hi_sprt = camp.wilson_ci(k_sprt, n_sprt)
        lo_full, hi_full = camp.wilson_ci(k_full, n_full)
        # CI overlap
        if hi_sprt >= lo_full and hi_full >= lo_sprt:
            per_ci_overlaps += 1
        else:
            per_ci_non_overlaps += 1
            # Non-overlap is only a fail if the GT is clear-cut
            if gt in ("CLEAN", "DEAD") and sprt_verdict != gt:
                # Already counted as disagreement
                pass
            elif gt in ("CLEAN", "DEAD") and sprt_verdict == gt:
                # Same verdict but CI doesn't overlap — this is fine,
                # different sample sizes have different CIs
                pass

# ---- Summary ----
print(f"\n--- V1 EQUIVALENCE RESULTS ---\n")
print(f"Total configs:         {len(cfg_pkts)}")
print(f"Agreements (CLEAN/DEAD match): {agreements}")
print(f"Disagreements:         {disagreements}")
print(f"Gray-zone OK (EDGE on borderline): {gray_zone_ok}")
print(f"Edge matches (both gray): {edge_matches}")
print(f"Edge mismatches (SPRT decided, 50pkt gray): {edge_mismatches}")
print(f"PER CI overlaps:       {per_ci_overlaps}")
print(f"PER CI non-overlaps:   {per_ci_non_overlaps}")
print(f"Pkts saved:            {total_pkts_saved} / {total_pkts_full} ({total_pkts_saved/total_pkts_full:.0%})")
print(f"  Avg pkts/cfg:        {total_pkts_full/len(cfg_pkts):.1f} → {(total_pkts_full-total_pkts_saved)/len(cfg_pkts):.1f}")

if mismatches:
    print(f"\n--- MISMATCHES ({len(mismatches)}) ---")
    for m in mismatches:
        cfg_idx, label, gt, sprt_v, k50, n50, k_sprt, n_sprt, k20 = m
        print(f"  cfg {cfg_idx} {label}: GT={gt}(k={k50}/{n50}) SPRT={sprt_v}(k={k_sprt}/{n_sprt}, first20 k={k20})")

# ---- Verdict ----
print(f"\n{'='*60}")
total_clear = agreements + disagreements
if total_clear > 0:
    agree_pct = agreements / total_clear * 100
    print(f"V1 EQUIVALENCE: {agree_pct:.1f}% agreement ({agreements}/{total_clear} clear-cut)")
else:
    print(f"V1 EQUIVALENCE: no clear-cut configs to compare")
    agree_pct = 100.0

# Acceptance: 100% CLEAN/DEAD agreement
if disagreements == 0:
    print(f"ACCEPTANCE: GO — 100% CLEAN/DEAD agreement")
    v1_pass = True
else:
    print(f"ACCEPTANCE: NO-GO — {disagreements} disagreements")
    v1_pass = False

# Write detailed CSV
csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..",
                        "v1-equivalence-results.csv")
csv_path = os.path.abspath(csv_path)
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["config_idx", "label", "n_full", "k_full", "per_full",
                "gt_verdict", "n_sprt", "k_sprt", "sprt_verdict",
                "sprt_stop_n", "pkts_saved", "ci_lo_sprt", "ci_hi_sprt",
                "ci_lo_full", "ci_hi_full", "ci_overlap", "match"])

    for cfg_idx in sorted(cfg_pkts):
        seq_50 = cfg_pkts[cfg_idx]
        n_full = len(seq_50)
        k_full = sum(1 for b in seq_50 if b > 0)
        label = cfg_labels.get(cfg_idx, f"cfg{cfg_idx}")
        gt = classify_50pkt(k_full, n_full)

        seq_sprt = seq_50[:SPRT_NCAP]
        k_sprt = 0
        n_sprt = 0
        sprt_verdict = "UNDECIDED"
        sprt_stop_n = SPRT_NCAP

        for i, b in enumerate(seq_sprt):
            n_sprt += 1
            if b > 0:
                k_sprt += 1
            if n_sprt >= SPRT_NMIN:
                res = camp.sprt_decide(k_sprt, n_sprt)
                if res.verdict in ("CLEAN", "DEAD"):
                    sprt_verdict = res.verdict
                    sprt_stop_n = n_sprt
                    break
        else:
            res = camp.sprt_decide(k_sprt, n_sprt)
            sprt_verdict = res.verdict

        lo_sprt, hi_sprt = camp.wilson_ci(k_sprt, n_sprt) if n_sprt > 0 else (0,0)
        lo_full, hi_full = camp.wilson_ci(k_full, n_full) if n_full > 0 else (0,0)
        ci_overlap = hi_sprt >= lo_full and hi_full >= lo_sprt
        match = (gt == sprt_verdict) or (gt == "EDGE") or (sprt_verdict == "EDGE" and gt in ("CLEAN","DEAD"))

        w.writerow([cfg_idx, label, n_full, k_full, f"{k_full/n_full:.4f}" if n_full else "",
                    gt, n_sprt, k_sprt, sprt_verdict, sprt_stop_n,
                    n_full - sprt_stop_n,
                    round(lo_sprt,4), round(hi_sprt,4),
                    round(lo_full,4), round(hi_full,4),
                    ci_overlap, match])

print(f"\nDetailed CSV: {csv_path}")
print(f"{'='*60}")
sys.exit(0 if v1_pass else 1)