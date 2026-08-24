#!/usr/bin/env python3
"""
parse_unified_csv.py — Parse LR2021 sweep serial output into unified CSV.

Handles ALL output formats:
    - LR2021_RESULT,path=...,freq_mhz=...  (new unified format, plan section 3.1)
    - PHASE_RESULT <idx> <name> key=val ... (legacy speed-tests format)
    - RANGE_RESULT_RX key=val ...           (range-tests format)
    - SWEEP_TX_RESULT key=val ...           (older sweep format)

Usage:
    # Parse a log file
    python3 parse_unified_csv.py sweep_log.txt --distance 1 --los N -o results.csv

    # Live capture from serial port
    cat /dev/ttyACM3 | python3 parse_unified_csv.py --distance 10 --los Y

    # With GPS time correlation
    python3 parse_unified_csv.py log.txt --gps-time 2026-07-24T12:00:00Z

    # Append mode (multiple files → one CSV)
    python3 parse_unified_csv.py log1.txt log2.txt -o combined.csv --append
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

# Phase name → config mapping (for legacy PHASE_RESULT format)
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

def infer_path(name):
    if name.startswith("HF-"):
        return "HF_FLRC" if "FLRC" in name else "HF_LORA"
    elif name.startswith("LF-"):
        return "LF_FLRC" if "FLRC" in name else "LF_LORA"
    return "UNKNOWN"


def parse_kv_fields(text):
    """Parse key=value pairs from text. Handles comma and space separators."""
    fields = {}
    # Split on commas first (for LR2021_RESULT format), then parse each segment
    # Also handle space-separated format (PHASE_RESULT, RANGE_RESULT_RX)
    # Strategy: find all key=value pairs where value ends at next comma/space
    for match in re.finditer(r'(\w+)=([^,\s]+)', text):
        fields[match.group(1)] = match.group(2)
    return fields


def parse_lr2021_result(line):
    """Parse LR2021_RESULT,key=val,... format (plan section 3.1)."""
    # Extract everything after the tag
    m = re.match(r'LR2021_RESULT[,\s]*(.*)', line.strip())
    if not m:
        return None

    kv = parse_kv_fields(m.group(1))
    if not kv:
        return None

    # Build row from explicit fields
    row = {f: "" for f in CSV_FIELDS}
    row["timestamp_iso"] = datetime.now(timezone.utc).isoformat()

    for k, v in kv.items():
        if k in row:
            row[k] = v
        elif k not in ("notes",):
            # Unknown field — append to notes
            if row["notes"]:
                row["notes"] += f" {k}={v}"
            else:
                row["notes"] = f"{k}={v}"

    # Derive PA state from tx_power if not explicit
    if not row.get("pa_state") and row.get("tx_power_dbm"):
        try:
            row["pa_state"] = "ON" if float(row["tx_power_dbm"]) >= 12.5 else "OFF"
        except ValueError:
            pass

    return row


def parse_phase_result(line):
    """Parse legacy PHASE_RESULT format from speed-tests firmware."""
    m = re.match(r'PHASE_RESULT\s+(\d+)\s+(\S+)\s*(.*)', line.strip())
    if not m:
        return None

    phase_idx = int(m.group(1))
    phase_name = m.group(2)
    rest = m.group(3)

    kv = parse_kv_fields(rest)
    config = PHASE_CONFIG.get(phase_name, {"mod": "?", "freq": 0, "sf": 0, "bw": 0, "cr": 0, "br": 0, "pkt": 0})

    is_rx = "rx=" in rest
    is_tx = "sent=" in rest

    row = {f: "" for f in CSV_FIELDS}
    row["timestamp_iso"] = datetime.now(timezone.utc).isoformat()
    row["path"] = kv.get("path", infer_path(phase_name))
    row["freq_mhz"] = config["freq"]
    row["modulation"] = config["mod"]
    row["bitrate_kbps"] = config["br"]
    row["spreading_factor"] = config["sf"]
    row["bandwidth_khz"] = config["bw"]
    row["coding_rate"] = config["cr"]
    row["pkt_size_bytes"] = config["pkt"]

    pa = kv.get("pa", "")
    row["pa_state"] = pa

    if "tx_power_dbm" in kv:
        row["tx_power_dbm"] = kv["tx_power_dbm"]
    elif pa == "ON":
        row["tx_power_dbm"] = "12.5"
    else:
        row["tx_power_dbm"] = "0.0"

    if is_rx:
        row["packets_rx"] = kv.get("rx", "0")
        row["packets_sent"] = kv.get("expected", "0")
        row["packets_unique"] = kv.get("rx", "0")
        row["per_percent"] = kv.get("per", "0")
        row["rssi_avg_dbm"] = kv.get("rssi_avg", "")
        row["snr_avg_db"] = "" if config["mod"] == "LORA" else "NA"
        row["uptime_ms"] = kv.get("elapsed_ms", "")
        row["notes"] = f"phase={phase_idx} crc_err={kv.get('crc_err', '0')}"
    elif is_tx:
        row["packets_sent"] = kv.get("sent", "0")
        row["packets_rx"] = "0"
        row["uptime_ms"] = kv.get("elapsed_ms", "")
        row["notes"] = f"tx_side phase={phase_idx} timeout={kv.get('timeout', '0')}"
    else:
        return None

    return row


def parse_range_result_rx(line):
    """Parse RANGE_RESULT_RX format from range-tests firmware."""
    m = re.match(r'RANGE_RESULT_RX[,\s]*(.*)', line.strip())
    if not m:
        return None

    kv = parse_kv_fields(m.group(1))
    if not kv:
        return None

    row = {f: "" for f in CSV_FIELDS}
    row["timestamp_iso"] = datetime.now(timezone.utc).isoformat()

    # Map range-tests fields to unified schema
    field_map = {
        "rx": "packets_rx", "sent": "packets_sent", "expected": "packets_sent",
        "unique": "packets_unique", "per": "per_percent",
        "rssi": "rssi_avg_dbm", "rssi_avg": "rssi_avg_dbm",
        "rssi_min": "rssi_min_dbm", "rssi_max": "rssi_max_dbm",
        "snr": "snr_avg_db", "snr_avg": "snr_avg_db",
        "path": "path", "pa": "pa_state", "freq": "freq_mhz",
        "freq_mhz": "freq_mhz", "mod": "modulation", "modulation": "modulation",
        "br": "bitrate_kbps", "bitrate_kbps": "bitrate_kbps",
        "sf": "spreading_factor", "spreading_factor": "spreading_factor",
        "bw": "bandwidth_khz", "bandwidth_khz": "bandwidth_khz",
        "pkt_sz": "pkt_size_bytes", "pkt_size_bytes": "pkt_size_bytes",
        "uptime": "uptime_ms", "uptime_ms": "uptime_ms",
        "distance": "distance_m", "distance_m": "distance_m",
        "los": "los",
    }

    for k, v in kv.items():
        unified_key = field_map.get(k, k)
        if unified_key in row:
            row[unified_key] = v
        else:
            row["notes"] = (row["notes"] + " " if row["notes"] else "") + f"{k}={v}"

    if not row.get("pa_state") and row.get("tx_power_dbm"):
        try:
            row["pa_state"] = "ON" if float(row["tx_power_dbm"]) >= 12.5 else "OFF"
        except ValueError:
            pass

    if not row.get("packets_unique") and row.get("packets_rx"):
        row["packets_unique"] = row["packets_rx"]

    return row


def parse_line(line):
    """Try all parsers, return first match."""
    line = line.strip()
    if not line:
        return None

    if line.startswith("LR2021_RESULT"):
        return parse_lr2021_result(line)
    elif line.startswith("PHASE_RESULT"):
        return parse_phase_result(line)
    elif line.startswith("RANGE_RESULT_RX"):
        return parse_range_result_rx(line)
    elif line.startswith("SWEEP_TX_RESULT"):
        # Similar to RANGE_RESULT_RX
        return parse_range_result_rx(line.replace("SWEEP_TX_RESULT", "RANGE_RESULT_RX"))
    elif line.startswith("SWEEP_RX_RESULT"):
        return parse_range_result_rx(line.replace("SWEEP_RX_RESULT", "RANGE_RESULT_RX"))

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Parse LR2021 sweep serial output → unified CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("inputs", nargs="*", default=["-"], help="Input log file(s) (default: stdin)")
    parser.add_argument("--output", "-o", default="-", help="Output CSV file (default: stdout)")
    parser.add_argument("--distance", type=float, default=0, help="Distance in meters")
    parser.add_argument("--los", default="", choices=["Y", "N", ""], help="Line of sight Y/N")
    parser.add_argument("--rx-only", action="store_true", help="Skip TX-side rows")
    parser.add_argument("--append", "-a", action="store_true", help="Append to existing output file")
    parser.add_argument("--gps-time", default="", help="GPS time ISO 8601 (overrides system time)")
    args = parser.parse_args()

    # Determine write mode
    write_header = True
    if args.append and args.output != "-":
        import os
        write_header = not os.path.exists(args.output)

    # Open output
    if args.output == "-":
        outfile = sys.stdout
    else:
        outfile = open(args.output, "a" if args.append else "w", newline="")

    writer = csv.DictWriter(outfile, fieldnames=CSV_FIELDS, extrasaction="ignore")
    if write_header:
        writer.writeheader()

    count = 0
    for input_path in args.inputs:
        if input_path == "-":
            infile = sys.stdin
        else:
            infile = open(input_path, "r")

        for line in infile:
            row = parse_line(line)
            if row is None:
                continue

            # Skip TX-only rows if --rx-only
            if args.rx_only and "tx_side" in row.get("notes", ""):
                continue
            if args.rx_only and row.get("packets_rx") == "0" and row.get("packets_sent", "0") != "0":
                continue

            # Apply overrides
            if args.gps_time:
                row["timestamp_iso"] = args.gps_time
            if args.distance > 0:
                row["distance_m"] = args.distance
            if args.los:
                row["los"] = args.los

            writer.writerow(row)
            count += 1

        if infile is not sys.stdin:
            infile.close()

    if outfile is not sys.stdout:
        outfile.close()

    print(f"\n# Parsed {count} result rows → CSV", file=sys.stderr)


if __name__ == "__main__":
    main()
