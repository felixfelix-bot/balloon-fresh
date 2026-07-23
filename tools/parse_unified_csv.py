#!/usr/bin/env python3
"""
parse_unified_csv.py — Parse LR2021 sweep serial output into unified CSV.

Handles both TX and RX PHASE_RESULT lines from multi_radio_sweep.cpp.
Outputs the unified CSV format defined in LR2021-FULL-CHARACTERIZATION-PLAN.md
section 3.

Usage:
    python3 parse_unified_csv.py <input_log> [--output output.csv] [--distance 1] [--los Y]

    Can also read from stdin:
    cat /dev/ttyACM3 | python3 parse_unified_csv.py --distance 2 --los N

The parser handles:
    - Old format: PHASE_RESULT 0 HF-LoRa-SF7 sent=50 timeout=0 elapsed_ms=15000
    - New format: PHASE_RESULT 0 HF-LoRa-SF7 path=HF_LORA pa=OFF rx=32 crc_err=0 per=36.0 rssi_avg=-28.0 expected=50
    - Partial lines (missing fields get defaults)
"""

import sys
import re
import csv
import argparse
from datetime import datetime, timezone

CSV_FIELDS = [
    "timestamp_iso",
    "path",
    "freq_mhz",
    "modulation",
    "bitrate_kbps",
    "spreading_factor",
    "bandwidth_khz",
    "coding_rate",
    "tx_power_dbm",
    "pa_state",
    "distance_m",
    "los",
    "packets_sent",
    "packets_rx",
    "packets_unique",
    "per_percent",
    "throughput_kbps",
    "rssi_avg_dbm",
    "rssi_min_dbm",
    "rssi_max_dbm",
    "snr_avg_db",
    "pkt_size_bytes",
    "uptime_ms",
    "notes",
]

# Phase name → config mapping
PHASE_CONFIG = {
    "HF-LoRa-SF7":   {"mod": "LORA", "freq": 2440, "sf": 7,  "bw": 812, "cr": 45, "br": 0,   "pkt": 127},
    "HF-LoRa-SF9":   {"mod": "LORA", "freq": 2440, "sf": 9,  "bw": 812, "cr": 45, "br": 0,   "pkt": 127},
    "HF-LoRa-SF12":  {"mod": "LORA", "freq": 2440, "sf": 12, "bw": 812, "cr": 45, "br": 0,   "pkt": 127},
    "HF-FLRC-2600":  {"mod": "FLRC", "freq": 2440, "sf": 0,  "bw": 0,   "cr": 0,  "br": 2600, "pkt": 255},
    "HF-FLRC-1300":  {"mod": "FLRC", "freq": 2440, "sf": 0,  "bw": 0,   "cr": 0,  "br": 1300, "pkt": 255},
    "HF-FLRC-650":   {"mod": "FLRC", "freq": 2440, "sf": 0,  "bw": 0,   "cr": 0,  "br": 650,  "pkt": 255},
    "HF-FLRC-325":   {"mod": "FLRC", "freq": 2440, "sf": 0,  "bw": 0,   "cr": 0,  "br": 325,  "pkt": 255},
    "LF-LoRa-SF7":   {"mod": "LORA", "freq": 868,  "sf": 7,  "bw": 250, "cr": 45, "br": 0,   "pkt": 127},
    "LF-LoRa-SF9":   {"mod": "LORA", "freq": 868,  "sf": 9,  "bw": 250, "cr": 45, "br": 0,   "pkt": 127},
    "LF-LoRa-SF12":  {"mod": "LORA", "freq": 868,  "sf": 12, "bw": 250, "cr": 45, "br": 0,   "pkt": 127},
    "LF-FLRC-2600":  {"mod": "FLRC", "freq": 868,  "sf": 0,  "bw": 0,   "cr": 0,  "br": 2600, "pkt": 255},
    "LF-FLRC-1300":  {"mod": "FLRC", "freq": 868,  "sf": 0,  "bw": 0,   "cr": 0,  "br": 1300, "pkt": 255},
    "LF-FLRC-650":   {"mod": "FLRC", "freq": 868,  "sf": 0,  "bw": 0,   "cr": 0,  "br": 650,  "pkt": 255},
    "LF-FLRC-325":   {"mod": "FLRC", "freq": 868,  "sf": 0,  "bw": 0,   "cr": 0,  "br": 325,  "pkt": 255},
}

# Inferred path from phase name if not in output
def infer_path(name):
    if name.startswith("HF-"):
        return "HF_FLRC" if "FLRC" in name else "HF_LORA"
    elif name.startswith("LF-"):
        return "LF_FLRC" if "FLRC" in name else "LF_LORA"
    return "UNKNOWN"


def parse_kv_fields(text):
    """Parse key=value pairs from a PHASE_RESULT line."""
    fields = {}
    for match in re.finditer(r'(\w+)=(\S+)', text):
        fields[match.group(1)] = match.group(2)
    return fields


def parse_phase_result(line):
    """Parse a single PHASE_RESULT line. Returns dict or None."""
    # Match: PHASE_RESULT <idx> <name> [key=val ...]
    m = re.match(r'PHASE_RESULT\s+(\d+)\s+(\S+)\s*(.*)', line.strip())
    if not m:
        return None

    phase_idx = int(m.group(1))
    phase_name = m.group(2)
    rest = m.group(3)

    kv = parse_kv_fields(rest)
    config = PHASE_CONFIG.get(phase_name, {"mod": "?", "freq": 0, "sf": 0, "bw": 0, "cr": 0, "br": 0, "pkt": 0})

    # Determine if this is TX or RX output
    is_rx = "rx=" in rest
    is_tx = "sent=" in rest

    if is_rx:
        packets_rx = int(kv.get("rx", 0))
        packets_sent = int(kv.get("expected", 0))
        per = float(kv.get("per", 0))
        rssi = float(kv.get("rssi_avg", 0))
        crc_err = int(kv.get("crc_err", 0))
    elif is_tx:
        packets_sent = int(kv.get("sent", 0))
        packets_rx = 0  # TX doesn't receive
        per = 0
        rssi = 0
        crc_err = 0
    else:
        return None

    path = kv.get("path", infer_path(phase_name))
    pa = kv.get("pa", "OFF")

    row = {
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "path": path,
        "freq_mhz": config["freq"],
        "modulation": config["mod"],
        "bitrate_kbps": config["br"],
        "spreading_factor": config["sf"],
        "bandwidth_khz": config["bw"],
        "coding_rate": config["cr"],
        "tx_power_dbm": 12.5 if pa == "ON" else 0.0,
        "pa_state": pa,
        "packets_sent": packets_sent,
        "packets_rx": packets_rx,
        "packets_unique": packets_rx,  # TODO: dedup by seq if raw data available
        "per_percent": round(per, 1),
        "throughput_kbps": "",  # calculated post-hoc
        "rssi_avg_dbm": int(rssi) if rssi != 0 else "",
        "rssi_min_dbm": "",
        "rssi_max_dbm": "",
        "snr_avg_db": "NA" if config["mod"] == "FLRC" else "",
        "pkt_size_bytes": config["pkt"],
        "uptime_ms": kv.get("elapsed_ms", ""),
        "notes": f"phase={phase_idx} crc_err={crc_err}" if is_rx else f"phase={phase_idx} tx_side",
    }

    return row


def main():
    parser = argparse.ArgumentParser(description="Parse LR2021 sweep serial output → unified CSV")
    parser.add_argument("input", nargs="?", default="-", help="Input log file (default: stdin)")
    parser.add_argument("--output", "-o", default="-", help="Output CSV file (default: stdout)")
    parser.add_argument("--distance", type=float, default=0, help="Distance in meters (overrides per-row)")
    parser.add_argument("--los", default="", choices=["Y", "N", ""], help="Line of sight Y/N")
    parser.add_argument("--rx-only", action="store_true", help="Only output RX rows (skip TX)")
    args = parser.parse_args()

    # Open input
    if args.input == "-":
        infile = sys.stdin
    else:
        infile = open(args.input, "r")

    # Open output
    if args.output == "-":
        outfile = sys.stdout
    else:
        outfile = open(args.output, "w", newline="")

    writer = csv.DictWriter(outfile, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()

    count = 0
    for line in infile:
        if "PHASE_RESULT" not in line:
            continue

        row = parse_phase_result(line)
        if row is None:
            continue

        if args.rx_only and row["notes"].endswith("tx_side"):
            continue

        if args.distance > 0:
            row["distance_m"] = args.distance
        else:
            row["distance_m"] = row.get("distance_m", "")

        if args.los:
            row["los"] = args.los

        writer.writerow(row)
        count += 1

    if infile is not sys.stdin:
        infile.close()
    if outfile is not sys.stdout:
        outfile.close()

    print(f"\n# Parsed {count} PHASE_RESULT rows → CSV", file=sys.stderr)


if __name__ == "__main__":
    main()
