#!/usr/bin/env python3
"""Turn RFA-1b matrix outdirs into a comparison table (markdown + CSV).

Reads the summary.json of each --outdir and prints the evidence table used in
docs/RFA1b-PRAM-PATCH-VERDICT-2026-10-14.md. The cells that produced no
packets are printed as "0 pkts" (a link/arming failure, NOT a CRC result) so
they can never be mistaken for a CRC-error row.

Usage: python3 tools/rfa1b_summarize.py outdir [outdir ...]
"""

from __future__ import annotations

import json
import os
import sys

HEAD = ("| arm | PA (dBm) | rate | len | TX sent/ok | RX pkts(ours) | RX rx / crc_err | "
        "crc_ok | crc_bad | RSSI avg | verdict |")
SEP = "|---|---|---|---|---|---|---|---|---|---|---|"


def row(path: str, cell: dict) -> str:
    arm = cell["arm"]
    sent = f"{cell['tx_stat'].get('sent')}/{cell['tx_stat'].get('sent_ok')}" if cell.get("tx_stat") else "?"
    rx = cell["rx_stat"] or {}
    rxc = f"{rx.get('rx')}/{rx.get('crc_err')}"
    rssi = rx.get("rssi_avg_dbm", "?")
    if cell["rx_pkts"] == 0:
        verdict = "NO PACKETS (not a CRC row)"
    elif cell["rx_crc_bad"] == 0:
        verdict = "CLEAN"
    else:
        verdict = "CRC ERRORS"
    return (f"| {arm} | {cell.get('pa_dbm')} | {cell['br_kbps']} kbps | {cell['len']} B | {sent} | "
            f"{cell['rx_pkts']} | {rxc} | {cell['rx_crc_ok']} | {cell['rx_crc_bad']} | {rssi} | "
            f"{verdict} |")


def main() -> int:
    outdirs = sys.argv[1:]
    if not outdirs:
        raise SystemExit(__doc__)
    print(HEAD)
    print(SEP)
    csv = ["arm,pa_dbm,br_kbps,len,tx_sent,tx_sent_ok,rx_pkts,rx,rx_crc_err,crc_ok,crc_bad,rssi_avg_dbm"]
    for d in outdirs:
        p = os.path.join(d, "summary.json")
        if not os.path.exists(p):
            print(f"| {d} | missing summary.json |", flush=True)
            continue
        s = json.load(open(p))
        for c in s["cells"]:
            print(row(d, c))
            rx = c["rx_stat"] or {}
            csv.append(",".join(str(x) for x in [
                c["arm"], c.get("pa_dbm"), c["br_kbps"], c["len"],
                (c.get("tx_stat") or {}).get("sent", ""), (c.get("tx_stat") or {}).get("sent_ok", ""),
                c["rx_pkts"], rx.get("rx", ""), rx.get("crc_err", ""), c["rx_crc_ok"],
                c["rx_crc_bad"], rx.get("rssi_avg_dbm", "")]))
    out_csv = os.path.join(os.path.dirname(outdirs[0]) or ".", "rfa1b-summary.csv")
    with open(out_csv, "w") as fh:
        fh.write("\n".join(csv) + "\n")
    print(f"\nCSV -> {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
