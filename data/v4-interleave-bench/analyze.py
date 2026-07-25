#!/usr/bin/env python3
"""
Aggregate v4-interleave-bench captures: per-phase and per-mode statistics,
identify phases/modes that NEVER decoded successfully.

A "phase" is one (mode, pktSize) combination. There are 56 of them.
A "mode" aggregates all 4 sizes for the same radio mode.
"""
import os
import re
import glob
import json
from collections import defaultdict

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# Canonical 56 phases in order (matches what we observed in the logs).
MODES_ORDER = [
    # HF-LoRa
    ("HF-LoRa-SF7",  [32, 64, 128, 255]),
    ("HF-LoRa-SF9",  [32, 64, 128, 255]),
    ("HF-LoRa-SF12", [32, 64, 128, 255]),
    # HF-FLRC
    ("HF-FLRC-2600", [32, 64, 128, 255]),
    ("HF-FLRC-1300", [32, 64, 128, 255]),
    ("HF-FLRC-650",  [32, 64, 128, 255]),
    ("HF-FLRC-325",  [32, 64, 128, 255]),
    # LF-LoRa
    ("LF-LoRa-SF7",  [32, 64, 128, 255]),
    ("LF-LoRa-SF9",  [32, 64, 128, 255]),
    ("LF-LoRa-SF12", [32, 64, 128, 255]),
    # LF-FLRC
    ("LF-FLRC-2600", [32, 64, 128, 255]),
    ("LF-FLRC-1300", [32, 64, 128, 255]),
    ("LF-FLRC-650",  [32, 64, 128, 255]),
    ("LF-FLRC-325",  [32, 64, 128, 255]),
]
EXPECTED_PHASES = [(m, s) for m, sizes in MODES_ORDER for s in sizes]
assert len(EXPECTED_PHASES) == 56

# regexes
RE_PHASE_RESULT = re.compile(r"^PHASE_RESULT\s+(\d+)\s+(\S+)\s+(.*)$")
RE_PHASE_START  = re.compile(r"^PHASE_START\s+(\d+)\s+(\S+)")
RE_PKT          = re.compile(r"^PKT\s+(.*)$")
RE_BER          = re.compile(r"^BER\s+(.*)$")
KV_RE           = re.compile(r"(\w+)=(\S+)")


def kv(line):
    return dict(KV_RE.findall(line))


def iter_logical_lines(text):
    """
    Some log lines got concatenated without newlines (e.g. 'tx_lat=0PHASE_GUARD 500').
    Re-split on embedded markers so each PHASE_RESULT / PHASE_START / PHASE_GUARD /
    PKT / BER sits on its own logical line.
    """
    # Insert newlines before each known marker prefix
    for marker in ("PHASE_RESULT ", "PHASE_START ", "PHASE_GUARD ",
                   "PKT ", "BER ", "LORA_CFG ", "FLRC_CFG ",
                   "SYNC_OFFSET ", "APP_CRC_FAIL ", "SYNC_NOT_FOUND ",
                   "SYNC_LOST ", "TIME_DIFF ", "FLRC_RAW32:", "LORA_RAW:"):
        text = text.replace(marker, "\n" + marker)
    for ln in text.split("\n"):
        ln = ln.strip()
        if ln:
            yield ln


def parse_file(path):
    """
    Return (phase_results, pkt_bers, pid_to_canon_local).

    phase_results: list of dict per PHASE_RESULT line, each tagged with the
                   canonical (mode, size) derived from the mode string ON THAT
                   LINE (authoritative — phase_id is NOT globally unique across
                   captures).
    pkt_bers:      list of dict for BER lines, resolved to canonical (mode,size)
                   using this file's own pid_to_canon map (built from
                   PHASE_RESULT mode strings, with PHASE_START as fallback).
    """
    with open(path, "r", errors="replace") as f:
        raw = f.read()

    phase_results = []
    pkt_bers      = []
    pid_to_canon  = {}   # local to this file
    pid_seen_in   = {}   # phase_id -> set of canonical tuples (collision detection)

    # phase context for BER attribution
    start_ctx = {}        # phase_id (from most recent PHASE_START) -> (mode, size)
    current_phase = None
    current_mode  = None
    last_pkt      = None  # (phase_id, rssi) of most recent PKT line

    def canonical_from_mode(mode_raw, size_hint):
        """Return (mode, size) tuple from a PHASE_RESULT/PHASE_START mode string."""
        if mode_raw.endswith("SKIP"):
            return ("LF-LoRa-SF12", size_hint)
        parts = mode_raw.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return (parts[0], int(parts[1]))
        return (mode_raw, size_hint)

    for ln in iter_logical_lines(raw):
        m = RE_PHASE_START.match(ln)
        if m:
            current_phase = int(m.group(1))
            current_mode  = m.group(2)
            # parse size from the rest
            d = kv(ln)
            sz = int(d.get("pktSize", 0)) if str(d.get("pktSize", "")).isdigit() else 0
            start_ctx[current_phase] = canonical_from_mode(current_mode, sz)
            continue
        m = RE_PHASE_RESULT.match(ln)
        if m:
            pid  = int(m.group(1))
            mode = m.group(2)
            rest = m.group(3)
            d    = kv(rest)
            sz_hint = int(d.get("pktSize", 0)) if str(d.get("pktSize", "")).isdigit() else 0
            canon = canonical_from_mode(mode, sz_hint)
            # register in local pid map (warn on collision but keep first canonical)
            pid_seen_in.setdefault(pid, set()).add(canon)
            if pid not in pid_to_canon:
                pid_to_canon[pid] = canon
            skip = "SKIP" in ln or mode.endswith("SKIP")
            def fint(k):
                try: return int(d.get(k, 0))
                except: return 0
            def fflt(k):
                try: return float(d.get(k, 0))
                except: return 0.0
            phase_results.append(dict(
                phase_id=pid, mode=mode, canon=canon, skip=skip,
                size=sz_hint,
                rx=int(d.get("rx", 0) or 0),
                unique=int(d.get("unique", 0) or 0),
                lost=int(d.get("lost", 0) or 0),
                per=fflt("per"),
                rssi_avg=fflt("rssi_avg"),
                rssi_min=fflt("rssi_min"),
                crc=fint("crc_err"),
                garbage=fint("garbage"),
                source=os.path.basename(path),
            ))
            continue
        m = RE_PKT.match(ln)
        if m:
            d = kv(m.group(1))
            pid  = int(d.get("phase", -1))
            rssi = float(d.get("rssi", 0))
            last_pkt = (pid, rssi)
            continue
        m = RE_BER.match(ln)
        if m:
            d = kv(m.group(1))
            try:
                bits = int(d.get("bits", 0))
                errs = int(d.get("errs", 0))
            except ValueError:
                continue
            pid  = last_pkt[0] if last_pkt else -1
            rssi = last_pkt[1] if last_pkt else 0
            canon = pid_to_canon.get(pid) or start_ctx.get(pid) or (None, None)
            pkt_bers.append(dict(phase_id=pid, canon=canon, rssi=rssi,
                                 bits=bits, errs=errs,
                                 source=os.path.basename(path)))
            continue

    return phase_results, pkt_bers, pid_seen_in


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.log")))
    all_pr  = []
    all_ber = []
    per_file_counts = {}
    collisions = {}    # filename -> {pid: set of canonical tuples}
    for fp in files:
        prs, brs, pid_seen = parse_file(fp)
        per_file_counts[os.path.basename(fp)] = (len(prs), len(brs))
        all_pr.extend(prs)
        all_ber.extend(brs)
        # record collisions (a pid mapping to >1 canonical tuple within one file)
        file_col = {pid: ts for pid, ts in pid_seen.items() if len(ts) > 1}
        if file_col:
            collisions[os.path.basename(fp)] = {pid: sorted(t for t in ts) for pid, ts in file_col.items()}

    # Each phase_result record carries its own authoritative 'canon' (mode,size)
    # derived from the mode string on that line. We aggregate directly off it;
    # phase_id is NOT globally unique across captures (see `collisions`).

    # Aggregate per canonical (mode, size)
    # For PER aggregation: sum rx and lost across all captures (skip the SKIP ones).
    # For BER: sum bits/errs across all packets observed.
    # For RSSI: track min (strongest = least negative) and avg weighted by rx.
    agg = defaultdict(lambda: dict(
        rx=0, unique=0, lost=0, crc=0, garbage=0,
        rssi_sum=0.0, rssi_n=0,
        rssi_best=-999.0,        # strongest (max)
        rssi_worst=999.0,
        bits=0, errs=0,
        skip_count=0, run_count=0,
        sources=set(),
        per_values=[],
    ))

    for r in all_pr:
        canon = r["canon"]
        if canon is None or canon[0] is None:
            continue
        a = agg[canon]
        a["sources"].add(r["source"])
        if r["skip"]:
            a["skip_count"] += 1
            continue
        a["run_count"] += 1
        a["rx"]      += r["rx"]
        a["unique"]  += r["unique"]
        a["lost"]    += r["lost"]
        a["crc"]     += r["crc"]
        a["garbage"] += r["garbage"]
        if r["per"] > 0 or r["rx"] > 0 or r["lost"] > 0:
            a["per_values"].append(r["per"])
        # RSSI: only when packets were actually received in this phase
        if r["rx"] > 0:
            rssi = r["rssi_avg"]
            if rssi != 0:
                a["rssi_sum"] += rssi * r["rx"]
                a["rssi_n"]   += r["rx"]
            if r["rssi_min"] != 0:
                a["rssi_best"]  = max(a["rssi_best"], r["rssi_min"])
                a["rssi_worst"] = min(a["rssi_worst"], r["rssi_min"])

    for b in all_ber:
        canon = b["canon"]
        if canon is None or canon[0] is None:
            continue
        a = agg[canon]
        a["bits"] += b["bits"]
        a["errs"] += b["errs"]
        if b["rssi"] != 0:
            a["rssi_best"]  = max(a["rssi_best"], b["rssi"])
            a["rssi_worst"] = min(a["rssi_worst"], b["rssi"])

    # Report phase_id collisions across files (sanity / data-quality check)
    if collisions:
        print("=" * 110)
        print("WARNING: phase_id is not globally unique across captures.")
        print("Within-file collisions (same pid mapped to >1 mode/size):")
        for fn, mp in collisions.items():
            print(f"  {fn}:")
            for pid, ts in mp.items():
                print(f"    pid={pid} -> {ts}")
        print("=" * 110)

    # ---------- emit per-phase table ----------
    print("=" * 110)
    print("PER-PHASE TABLE  (56 phases, aggregated over all captures)")
    print("=" * 110)
    hdr = f"{'#':>2} {'Mode':<18} {'Sz':>4} {'rxTot':>6} {'lost':>6} {'aggPER%':>8} {'bestRSSI':>9} {'BER':>10} {'crc':>5} {'garb':>5} {'runs':>5} {'skips':>5}"
    print(hdr)
    print("-" * len(hdr))
    for idx, (mode, size) in enumerate(EXPECTED_PHASES):
        a = agg.get((mode, size))
        if a is None:
            print(f"{idx:>2} {mode:<18} {size:>4}    --- never observed in any capture ---")
            continue
        attempted = a["rx"] + a["lost"]
        agg_per = (100.0 * a["lost"] / attempted) if attempted else 0.0
        if a["bits"] > 0:
            ber = a["errs"] / a["bits"]
            ber_str = f"{ber:.2e}"
        else:
            ber_str = "  n/a"
        rssib = f"{a['rssi_best']:.0f}" if a["rssi_best"] > -900 else "  -"
        flag = "  <-- NEVER DECODED" if a["rx"] == 0 and a["run_count"] > 0 else ""
        print(f"{idx:>2} {mode:<18} {size:>4} {a['rx']:>6} {a['lost']:>6} {agg_per:>8.1f} "
              f"{rssib:>9} {ber_str:>10} {a['crc']:>5} {a['garbage']:>5} "
              f"{a['run_count']:>5} {a['skip_count']:>5}{flag}")

    # ---------- per-mode aggregate (collapse sizes) ----------
    print()
    print("=" * 110)
    print("PER-MODE SUMMARY  (14 modes, all sizes collapsed)")
    print("=" * 110)
    mode_agg = defaultdict(lambda: dict(rx=0, lost=0, bits=0, errs=0,
                                        rssi_best=-999.0, runs=0, crc=0, garbage=0,
                                        sizes_with_rx=set(), sizes_attempted=set()))
    for (mode, size), a in agg.items():
        ma = mode_agg[mode]
        ma["rx"]      += a["rx"]
        ma["lost"]    += a["lost"]
        ma["bits"]    += a["bits"]
        ma["errs"]    += a["errs"]
        ma["crc"]     += a["crc"]
        ma["garbage"] += a["garbage"]
        ma["runs"]    += a["run_count"]
        if a["rssi_best"] > -900:
            ma["rssi_best"] = max(ma["rssi_best"], a["rssi_best"])
        if a["run_count"] > 0:
            ma["sizes_attempted"].add(size)
        if a["rx"] > 0:
            ma["sizes_with_rx"].add(size)

    hdr2 = f"{'Mode':<18} {'rxTot':>6} {'lost':>7} {'aggPER%':>8} {'bestRSSI':>9} {'BER':>10} {'crc':>6} {'garb':>6} {'sizesOK':>18} {'verdict':<20}"
    print(hdr2)
    print("-" * len(hdr2))
    for mode, _sizes in MODES_ORDER:
        ma = mode_agg[mode]
        attempted = ma["rx"] + ma["lost"]
        agg_per = (100.0 * ma["lost"] / attempted) if attempted else 0.0
        if ma["bits"] > 0:
            ber_str = f"{ma['errs']/ma['bits']:.2e}"
        else:
            ber_str = "  n/a"
        rssib = f"{ma['rssi_best']:.0f}" if ma["rssi_best"] > -900 else "  -"
        if ma["rx"] == 0:
            verdict = "FAIL (no decode)"
        elif len(ma["sizes_with_rx"]) == 4:
            verdict = "OK all sizes"
        else:
            verdict = f"partial ({len(ma['sizes_with_rx'])}/4)"
        sok = ",".join(str(s) for s in sorted(ma["sizes_with_rx"])) or "-"
        print(f"{mode:<18} {ma['rx']:>6} {ma['lost']:>7} {agg_per:>8.1f} {rssib:>9} "
              f"{ber_str:>10} {ma['crc']:>6} {ma['garbage']:>6} {sok:>18} {verdict:<20}")

    # ---------- JSON dump for downstream tooling ----------
    per_phase_json = {}
    for (m, s), a in agg.items():
        key = m + "-" + str(s)
        attempted = a["rx"] + a["lost"]
        per_phase_json[key] = dict(
            rx=a["rx"], lost=a["lost"],
            agg_per=(100.0*a["lost"]/attempted if attempted else 0.0),
            ber=(a["errs"]/a["bits"] if a["bits"] else None),
            rssi_best=(a["rssi_best"] if a["rssi_best"] > -900 else None),
            crc=a["crc"], garbage=a["garbage"],
            runs=a["run_count"], skips=a["skip_count"],
            sources=sorted(a["sources"]),
        )
    per_mode_json = {}
    for m, ma in mode_agg.items():
        attempted = ma["rx"] + ma["lost"]
        per_mode_json[m] = dict(
            rx=ma["rx"], lost=ma["lost"],
            agg_per=(100.0*ma["lost"]/attempted if attempted else 0.0),
            ber=(ma["errs"]/ma["bits"] if ma["bits"] else None),
            rssi_best=(ma["rssi_best"] if ma["rssi_best"] > -900 else None),
            sizes_with_rx=sorted(ma["sizes_with_rx"]),
            sizes_attempted=sorted(ma["sizes_attempted"]),
            verdict=("FAIL" if ma["rx"] == 0 else
                     ("OK_ALL" if len(ma["sizes_with_rx"]) == 4 else "PARTIAL")),
        )
    out = dict(per_file=per_file_counts,
               per_phase=per_phase_json,
               per_mode=per_mode_json)
    with open(os.path.join(DATA_DIR, "analysis.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote analysis.json")


if __name__ == "__main__":
    main()
