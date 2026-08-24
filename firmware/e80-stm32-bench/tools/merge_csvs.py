#!/usr/bin/env python3
"""merge_csvs.py — Merge TX and RX logs from distributed range test.

Joins on (session, config, pkt_idx):
  - TX log has one row per config (n_pkts expected)
  - RX log has one row per received packet
  - Missing RX packet = lost = counts toward PER
  - Extra RX packets (unknown session/config) = flagged as foreign

Outputs:
  - combined.csv (machine readable: one row per expected+received packet)
  - combined-range-report.md (human-readable PER report)

Usage:
    python3 merge_csvs.py --tx tx-log.csv --rx rx-log.csv [--out-dir .]
"""
import argparse
import csv
import os
import sys
from collections import defaultdict


def load_tx_log(path):
    """Load TX log: returns list of dicts with session, config_idx, n_pkts, ..."""
    with open(path, newline="") as f:
        reader = csv.DictReader(ln for ln in f if not ln.startswith("#"))
        return list(reader)


def load_rx_log(path):
    """Load RX log: returns list of dicts with session, config, pkt_idx, ..."""
    with open(path, newline="") as f:
        reader = csv.DictReader(ln for ln in f if not ln.startswith("#"))
        return list(reader)


def merge_csvs(tx_path, rx_path, out_dir="."):
    """Merge TX and RX logs. Returns list of combined dicts.

    Each dict has: session, config, pkt_idx, status (received/lost),
    rssi_dbm, snr_db, crc_ok, bit_err, freq_hz, mod, ..., label, n_pkts
    """
    tx_rows = load_tx_log(tx_path)
    rx_rows = load_rx_log(rx_path)

    # Build RX lookup: (session, config, pkt_idx) -> rx_row
    # Normalize pkt_idx: firmware uses global counter, merge expects per-config 0..N-1
    rx_lookup = {}
    rx_by_config = defaultdict(list)
    for r in rx_rows:
        rx_by_config[(str(r["session"]), str(r["config"]))].append(r)

    # Sort each config's packets by pkt_idx and normalize to 0..N-1
    for (sess, cfg), pkts in rx_by_config.items():
        pkts.sort(key=lambda p: int(p.get("pkt_idx", 0)))
        for i, r in enumerate(pkts):
            r["pkt_idx"] = str(i)
            rx_lookup[(sess, cfg, str(i))] = r

    # Build expected set from TX log
    combined = []
    tx_configs = {}  # (session, config) -> tx_row
    foreign_pkts = []

    for tx in tx_rows:
        session = str(tx["session"])
        config = str(tx["config_idx"])
        n_pkts = int(tx["n_pkts"])
        tx_configs[(session, config)] = tx

        for pkt_idx in range(n_pkts):
            key = (session, config, str(pkt_idx))
            if key in rx_lookup:
                rx = rx_lookup[key]
                combined.append({
                    "session": session,
                    "config": config,
                    "pkt_idx": pkt_idx,
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
                    "session": session,
                    "config": config,
                    "pkt_idx": pkt_idx,
                    "status": "lost",
                    "rssi_dbm": "",
                    "snr_db": "",
                    "crc_ok": "",
                    "bit_err": "",
                    "freq_hz": tx.get("freq_hz", ""),
                    "mod": tx.get("mod", ""),
                    "sf_or_br": tx.get("sf_or_br", ""),
                    "bw": tx.get("bw", ""),
                    "pa_dbm": tx.get("pa_dbm", ""),
                    "len": tx.get("plen", ""),
                    "pcrc16": "",
                    "label": tx.get("label", ""),
                })

    # Find foreign RX packets (session, config not in TX log)
    for r in rx_rows:
        key = (str(r["session"]), str(r["config"]))
        if key not in tx_configs:
            foreign_pkts.append(r)

    # Write combined.csv
    csv_path = os.path.join(out_dir, "combined.csv")
    csv_cols = ["session", "config", "pkt_idx", "status", "rssi_dbm", "snr_db",
                "crc_ok", "bit_err", "freq_hz", "mod", "sf_or_br", "bw",
                "pa_dbm", "len", "pcrc16", "label"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols, extrasaction="ignore")
        w.writeheader()
        for row in combined:
            w.writerow(row)

    # Compute PER per config
    config_stats = defaultdict(lambda: {"expected": 0, "received": 0, "lost": 0})
    for row in combined:
        key = (row["session"], row["config"])
        config_stats[key]["expected"] += 1
        if row["status"] == "received":
            config_stats[key]["received"] += 1
        else:
            config_stats[key]["lost"] += 1

    # Compute RSSI/SNR averages per config
    rssi_vals = defaultdict(list)
    snr_vals = defaultdict(list)
    for row in combined:
        if row["status"] == "received" and row["rssi_dbm"]:
            key = (row["session"], row["config"])
            try:
                rssi_vals[key].append(float(row["rssi_dbm"]))
            except ValueError:
                pass
            try:
                snr_vals[key].append(float(row["snr_db"]))
            except ValueError:
                pass

    # Write combined-range-report.md
    report_path = os.path.join(out_dir, "combined-range-report.md")
    with open(report_path, "w") as f:
        f.write("# E80 Distributed Range Test — Merge Report\n\n")
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

        f.write("## Per-Config Results\n\n")
        f.write("| Config | Label | N | Received | Lost | PER | RSSI avg | SNR avg |\n")
        f.write("|--------|-------|---|----------|------|-----|----------|---------|\n")
        for (session, config) in sorted(config_stats.keys()):
            s = config_stats[(session, config)]
            label = tx_configs.get((session, config), {}).get("label", "?")
            per = (s["lost"] / s["expected"] * 100) if s["expected"] else 0
            rssi_list = rssi_vals.get((session, config), [])
            snr_list = snr_vals.get((session, config), [])
            rssi_avg = "{:.1f}".format(sum(rssi_list) / len(rssi_list)) if rssi_list else "-"
            snr_avg = "{:.1f}".format(sum(snr_list) / len(snr_list)) if snr_list else "-"
            f.write("| {} | {} | {} | {} | {} | {:.0f}% | {} | {} |\n".format(
                config, label, s["expected"], s["received"], s["lost"],
                per, rssi_avg, snr_avg))

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
        f.write("- `combined.csv` — machine-readable merged data\n")
        f.write("- `tx-log.csv` — TX-side per-config log\n")
        f.write("- `rx-log.csv` — RX-side per-packet log\n")

    return combined


def main():
    ap = argparse.ArgumentParser(
        description="Merge TX and RX range test logs, compute PER")
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

    print("Merge complete: {}/{} received, {} lost, PER={:.1f}%".format(
        received, total, lost, per))
    print("  combined.csv:            {}/combined.csv".format(args.out_dir))
    print("  combined-range-report.md: {}/combined-range-report.md".format(args.out_dir))


if __name__ == "__main__":
    main()
