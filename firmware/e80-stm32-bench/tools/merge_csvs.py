#!/usr/bin/env python3
"""merge_csvs.py — Merge TX and RX logs from distributed range tests.

Supports BOTH log formats:
  - harmonized (default): tx-log = ``STAT,role=TX,...`` lines;
    rx-log = ``PKT,<23 fields>`` lines (no header)
  - legacy: header-row CSVs (16 columns), kept for old logs

Merge policy (2026-08-28, operator-approved): BEST PASS per
(session, config) — the replicate with the most received packets wins.
Passes are NEVER pooled: a union of passes biases PER low (a packet
received in any pass would count as received). A per-pass table is
included in the report so marginal configs stay visible. Raw logs are
never modified; re-runs land in their own session dirs.

Joins on (session, config, replicate, pkt_idx):
  - TX log: one row per config (n_pkts expected, after prime discard)
  - RX log: one row per received packet; pkt_idx normalized 0..N-1 per
    (session, config, replicate), sorted by firmware seq
  - Missing RX packet = lost = counts toward PER
  - Extra RX packets (session/config not in TX log) = flagged foreign

Outputs:
  - combined.csv (one row per expected+received packet, best pass)
  - combined-range-report.md (PER report + per-pass table)

Usage:
    python3 merge_csvs.py --tx tx-log.csv --rx rx-log.csv [--out-dir .]
"""
import argparse
import csv
import os
import re
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import e80_bench_ctl as ctl  # noqa: E402  (parse_pkt_line, DEFAULT_PRIME_DISCARD)

# Fallback PER denominator when a TX STAT line predates the n_pkts field:
# 'sent' includes the prime-discard warmup packets, so subtract them.
FALLBACK_PRIME = getattr(ctl, "DEFAULT_PRIME_DISCARD", 2)

_STAT_KV = re.compile(r"(\w+)=((?:\[[^\]]*\])|[^,]*)")


def parse_stat_line(line):
    """Parse a harmonized ``STAT,role=...`` line into a dict (or None).

    Handles the bracketed per_ci_x1e6=[lo,hi] value (contains a comma).
    """
    if not line or not line.strip().startswith("STAT,"):
        return None
    d = {}
    for k, v in _STAT_KV.findall(line.strip()):
        d[k] = v
    if "role" not in d:
        return None
    return d


def _to_int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Loaders (auto-detect format)
# ---------------------------------------------------------------------------

def load_tx_log(path):
    """TX log → list of {session, config, replicate, n_pkts, label, ...}.

    Harmonized: one entry per STAT,role=TX line. n_pkts comes from the
    n_pkts= field when present; older logs fall back to sent - prime.
    Legacy: one entry per CSV row (replicate=1).
    """
    with open(path, newline="") as f:
        lines = [ln.rstrip("\n") for ln in f if not ln.startswith("#")]
    rows = []
    for ln in lines:
        st = parse_stat_line(ln)
        if st is None or st.get("role") != "TX":
            continue
        sent = _to_int(st.get("sent"), 0)
        n_pkts = _to_int(st.get("n_pkts"))
        if n_pkts is None:
            n_pkts = max(sent - FALLBACK_PRIME, 0)
        rows.append({
            "session": str(st.get("session", "")),
            "config": str(st.get("config", "")),
            "replicate": _to_int(st.get("replicate"), 1),
            "n_pkts": n_pkts,
            "sent": sent,
            "sent_ok": _to_int(st.get("sent_ok"), 0),
            "label": st.get("label", ""),
            "plen": _to_int(st.get("plen")),
            "gap_us": _to_int(st.get("gap_us"), 0),
        })
    if rows:
        return rows
    # Legacy header CSV — normalize to the harmonized key names
    with open(path, newline="") as f:
        out = []
        for r in csv.DictReader(ln for ln in f if not ln.startswith("#")):
            n_pkts = _to_int(r.get("n_pkts"), 0)
            out.append({
                "session": str(r.get("session", "")),
                "config": str(r.get("config_idx", r.get("config", ""))),
                "replicate": 1,
                "n_pkts": n_pkts,
                "sent": n_pkts,
                "sent_ok": _to_int(r.get("sent_ok"), n_pkts),
                "label": r.get("label", ""),
                "plen": _to_int(r.get("plen")),
                "gap_us": _to_int(r.get("gap_us"), 0),
                "mod": r.get("mod", ""), "sf_or_br": r.get("sf_or_br", ""),
                "bw": r.get("bw", ""), "pa_dbm": r.get("pa_dbm", ""),
                "freq_hz": r.get("freq_hz", ""),
            })
        return out


def load_rx_log(path):
    """RX log → list of packet dicts.

    Harmonized: PKT lines via ctl.parse_pkt_line (mapped to the merge's
    field names). Legacy: header CSV rows.
    """
    with open(path, newline="") as f:
        lines = [ln.rstrip("\n") for ln in f if not ln.startswith("#")]
    rows = []
    for ln in lines:
        p = ctl.parse_pkt_line(ln)
        if p is None:
            continue
        rows.append({
            "session": str(p["session_id"]),
            "config": str(p["config_id"]),
            "replicate": int(p["replicate"]),
            "seq": int(p["seq"]),
            "pkt_idx": int(p["seq"]),
            "rssi_dbm": p["rssi_dbm"], "snr_db": p["snr_db"],
            "crc_ok": p["crc_ok"], "bit_err": p["bit_err"],
            "freq_hz": p["freq_hz"], "mod": p["mod"],
            "sf_or_br": p["sf"],  # firmware slot carries sf (lora) or br (flrc)
            "bw": p["bw_khz"], "pa_dbm": p["power_dbm"],
            "len": p["pkt_size"], "pcrc16": "",
        })
    if rows:
        return rows
    with open(path, newline="") as f:
        return [dict(r, replicate=_to_int(r.get("replicate"), 1))
                for r in csv.DictReader(
                    ln for ln in f if not ln.startswith("#"))]


# ---------------------------------------------------------------------------
# Best-pass merge
# ---------------------------------------------------------------------------

def group_rx(rx_rows):
    """Group RX rows by (session, config, replicate); normalize pkt_idx
    to 0..N-1 within each group (sorted by firmware seq)."""
    groups = defaultdict(list)
    for r in rx_rows:
        groups[(str(r["session"]), str(r["config"]),
                int(r.get("replicate", 1)))].append(r)
    for pkts in groups.values():
        pkts.sort(key=lambda p: int(p.get("seq", p.get("pkt_idx", 0))))
        for i, r in enumerate(pkts):
            r["pkt_idx"] = str(i)
    return groups


def pick_best_passes(tx_rows, rx_groups):
    """For each (session, config) pick the replicate with the most
    received packets (ties → lowest replicate number).

    Returns {(session, config): {"tx": tx_row, "replicate": r,
                                 "rx": [pkts], "all": {rep: count}}}.
    """
    best = {}
    tx_by_key = {}
    for tx in tx_rows:
        key = (str(tx["session"]), str(tx["config"]))
        tx_by_key.setdefault(key, []).append(tx)
    counts = defaultdict(dict)
    for (sess, cfg, rep), pkts in rx_groups.items():
        counts[(sess, cfg)][rep] = len(pkts)
    for key, txs in tx_by_key.items():
        reps = counts.get(key, {})
        chosen = None
        if reps:
            chosen = sorted(reps.items(),
                            key=lambda kv: (-kv[1], kv[0]))[0][0]
        elif len(txs) == 1:
            chosen = int(txs[0].get("replicate", 1))
        else:
            chosen = int(min(t.get("replicate", 1) for t in txs))
        tx_row = next((t for t in txs
                       if int(t.get("replicate", 1)) == chosen), txs[0])
        rx_pkts = rx_groups.get((key[0], key[1], chosen), [])
        best[key] = {"tx": tx_row, "replicate": chosen,
                     "rx": rx_pkts, "all": dict(reps)}
    return best


def merge_csvs(tx_path, rx_path, out_dir="."):
    """Merge TX and RX logs (best pass per config). Returns combined rows."""
    tx_rows = load_tx_log(tx_path)
    rx_rows = load_rx_log(rx_path)
    rx_groups = group_rx(rx_rows)
    best = pick_best_passes(tx_rows, rx_groups)

    combined = []
    foreign_pkts = [r for r in rx_rows
                    if (str(r["session"]), str(r["config"])) not in best]

    for (session, config), sel in sorted(best.items()):
        tx = sel["tx"]
        n_pkts = int(tx.get("n_pkts", 0))
        rx_lookup = {p["pkt_idx"]: p for p in sel["rx"]}
        for pkt_idx in range(n_pkts):
            key = str(pkt_idx)
            if key in rx_lookup:
                rx = rx_lookup[key]
                combined.append({
                    "session": session, "config": config,
                    "replicate": sel["replicate"], "pkt_idx": pkt_idx,
                    "status": "received",
                    "rssi_dbm": rx.get("rssi_dbm", ""),
                    "snr_db": rx.get("snr_db", ""),
                    "crc_ok": rx.get("crc_ok", ""),
                    "bit_err": rx.get("bit_err", ""),
                    "freq_hz": rx.get("freq_hz", tx.get("freq_hz", "")),
                    "mod": rx.get("mod", tx.get("mod", "")),
                    "sf_or_br": rx.get("sf_or_br", tx.get("sf_or_br", "")),
                    "bw": rx.get("bw", tx.get("bw", "")),
                    "pa_dbm": rx.get("pa_dbm", tx.get("pa_dbm", "")),
                    "len": rx.get("len", tx.get("plen", "")),
                    "pcrc16": rx.get("pcrc16", ""),
                    "label": tx.get("label", ""),
                })
            else:
                combined.append({
                    "session": session, "config": config,
                    "replicate": sel["replicate"], "pkt_idx": pkt_idx,
                    "status": "lost",
                    "rssi_dbm": "", "snr_db": "", "crc_ok": "",
                    "bit_err": "", "freq_hz": tx.get("freq_hz", ""),
                    "mod": tx.get("mod", ""), "sf_or_br": tx.get("sf_or_br", ""),
                    "bw": tx.get("bw", ""), "pa_dbm": tx.get("pa_dbm", ""),
                    "len": tx.get("plen", ""), "pcrc16": "",
                    "label": tx.get("label", ""),
                })

    csv_path = os.path.join(out_dir, "combined.csv")
    csv_cols = ["session", "config", "replicate", "pkt_idx", "status",
                "rssi_dbm", "snr_db", "crc_ok", "bit_err", "freq_hz",
                "mod", "sf_or_br", "bw", "pa_dbm", "len", "pcrc16", "label"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols, extrasaction="ignore")
        w.writeheader()
        for row in combined:
            w.writerow(row)

    # Per-config stats from the BEST pass
    config_stats = defaultdict(lambda: {"expected": 0, "received": 0, "lost": 0})
    rssi_vals = defaultdict(list)
    snr_vals = defaultdict(list)
    for row in combined:
        key = (row["session"], row["config"])
        config_stats[key]["expected"] += 1
        if row["status"] == "received":
            config_stats[key]["received"] += 1
            try:
                rssi_vals[key].append(float(row["rssi_dbm"]))
            except (ValueError, TypeError):
                pass
            try:
                snr_vals[key].append(float(row["snr_db"]))
            except (ValueError, TypeError):
                pass
        else:
            config_stats[key]["lost"] += 1

    report_path = os.path.join(out_dir, "combined-range-report.md")
    with open(report_path, "w") as f:
        f.write("# E80 Distributed Range Test — Merge Report\n\n")
        f.write("Merge policy: **best pass per config** (never pooled — "
                "union biases PER low). Raw logs untouched.\n\n")
        f.write("## Summary\n\n")
        total_expected = sum(s["expected"] for s in config_stats.values())
        total_received = sum(s["received"] for s in config_stats.values())
        total_lost = sum(s["lost"] for s in config_stats.values())
        overall_per = (total_lost / total_expected * 100) if total_expected else 0
        f.write("| Metric | Value |\n|--------|-------|\n")
        f.write("| Total expected | {} |\n".format(total_expected))
        f.write("| Total received | {} |\n".format(total_received))
        f.write("| Total lost | {} |\n".format(total_lost))
        f.write("| Overall PER | {:.1f}% |\n".format(overall_per))
        f.write("| Foreign packets | {} |\n\n".format(len(foreign_pkts)))

        f.write("## Per-Config Results (best pass)\n\n")
        f.write("| Config | Label | Pass | N | Received | Lost | PER | RSSI avg | SNR avg |\n")
        f.write("|--------|-------|------|---|----------|------|-----|----------|---------|\n")
        for (session, config) in sorted(config_stats.keys()):
            s = config_stats[(session, config)]
            sel = best.get((session, config), {})
            label = sel.get("tx", {}).get("label", "?")
            per = (s["lost"] / s["expected"] * 100) if s["expected"] else 0
            rssi_list = rssi_vals.get((session, config), [])
            snr_list = snr_vals.get((session, config), [])
            rssi_avg = "{:.1f}".format(sum(rssi_list) / len(rssi_list)) if rssi_list else "-"
            snr_avg = "{:.1f}".format(sum(snr_list) / len(snr_list)) if snr_list else "-"
            f.write("| {} | {} | r{} | {} | {} | {} | {:.0f}% | {} | {} |\n".format(
                config, label, sel.get("replicate", "?"), s["expected"],
                s["received"], s["lost"], per, rssi_avg, snr_avg))

        f.write("\n## Per-Pass Detail (received packets per replicate)\n\n")
        multi = {k: v for k, v in best.items() if len(v["all"]) > 1}
        if multi:
            f.write("| Config | Label | Passes (replicate: received) |\n")
            f.write("|--------|-------|------------------------------|\n")
            for (session, config), sel in sorted(multi.items()):
                passes = ", ".join("r{}: {}".format(r, n)
                                   for r, n in sorted(sel["all"].items()))
                chosen = "r{}".format(sel["replicate"])
                f.write("| {} | {} | {} → best {} |\n".format(
                    config, sel["tx"].get("label", "?"), passes, chosen))
        else:
            f.write("(single pass per config — no multi-pass data)\n")

        if foreign_pkts:
            f.write("\n## Foreign Packets (unknown session/config)\n\n")
            f.write("| Session | Config | Pkt Idx | RSSI | SNR | Mod |\n")
            f.write("|---------|--------|---------|------|-----|-----|\n")
            for fp in foreign_pkts:
                f.write("| {} | {} | {} | {} | {} | {} |\n".format(
                    fp.get("session", "?"), fp.get("config", "?"),
                    fp.get("pkt_idx", "?"), fp.get("rssi_dbm", "?"),
                    fp.get("snr_db", "?"), fp.get("mod", "?")))

        f.write("\n## Files\n\n")
        f.write("- `combined.csv` — machine-readable merged data (best pass)\n")
        f.write("- `tx-log.csv` — TX-side per-config log\n")
        f.write("- `rx-log.csv` — RX-side per-packet log\n")

    return combined


def main():
    ap = argparse.ArgumentParser(
        description="Merge TX and RX range test logs, compute PER "
                    "(best pass per config; harmonized + legacy formats)")
    ap.add_argument("--tx", required=True, help="TX log CSV (tx-log.csv)")
    ap.add_argument("--rx", required=True, help="RX log CSV (rx-log.csv)")
    ap.add_argument("--out-dir", default=".", help="output directory (default: .)")
    args = ap.parse_args()

    if not os.path.isfile(args.tx):
        sys.exit("ERROR: TX log not found: {}".format(args.tx))
    if not os.path.isfile(args.rx):
        sys.exit("ERROR: RX log not found: {}".format(args.rx))

    combined = merge_csvs(args.tx, args.rx, args.out_dir)

    received = sum(1 for r in combined if r["status"] == "received")
    lost = sum(1 for r in combined if r["status"] == "lost")
    total = len(combined)
    per = (lost / total * 100) if total else 0

    print("Merge complete (best pass): {}/{} received, {} lost, PER={:.1f}%".format(
        received, total, lost, per))
    print("  combined.csv:            {}/combined.csv".format(args.out_dir))
    print("  combined-range-report.md: {}/combined-range-report.md".format(args.out_dir))


if __name__ == "__main__":
    main()
